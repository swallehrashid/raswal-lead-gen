"""Persistence: Supabase (live), in-memory (offline/tests) and a read-only dry-run wrapper.

The pipeline only talks to the `Store` methods below. SupabaseStore uses the service-role
key (GitHub Actions secret only). DryRunStore reads from an inner store and never writes.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pipeline.gates import GateContext
from pipeline.models import Candidate, Cell

log = logging.getLogger(__name__)

CONTACTED_STATUSES = {"sent", "replied", "interested", "demo_queued", "demo_sent", "negotiating", "won", "lost",
                      "no_response", "snoozed", "opted_out"}
BUCKET = "leadgen"


def _iso(v):
    if isinstance(v, datetime | date):
        return v.isoformat()
    return v


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- row builders (shared)

def business_row(c: Candidate) -> dict[str, Any]:
    return {
        "place_id": c.place_id, "name": c.name, "name_norm": c.name_norm, "display_name": c.display_name,
        "subcategory": c.subcategory, "types": c.types, "primary_type": c.primary_type, "address": c.address,
        "area": c.area, "lat": c.lat, "lng": c.lng, "maps_url": c.maps_url, "phone_e164": c.phone_e164,
        "phone_type": c.phone_type, "website_url": c.website_url, "rating": c.rating, "review_count": c.review_count,
        "newest_review_at": _iso(c.newest_review_at), "branch_count": c.branch_count,
        "manages_listings": c.manages_listings, "merged_place_ids": c.merged_place_ids,
        "last_seen_at": _now().isoformat(),
    }


def audit_row(c: Candidate) -> dict[str, Any] | None:
    if not c.audit:
        return None
    a = c.audit.to_row()
    raw = {k: a.pop(k) for k in ("dead_marker", "social_platform", "free_builder", "free_host") if k in a}
    row = {k: v for k, v in a.items() if k in AUDIT_COLUMNS}
    row.update(place_id=c.place_id, audited_at=_now().isoformat(), dead_marker=raw.get("dead_marker"),
               raw={**raw, "weak_signals": a.get("weak_signals", [])})
    return row


AUDIT_COLUMNS = {"site_status", "website_url", "final_url", "status_code", "https_ok", "cert_error", "redirect_chain",
                 "html_bytes", "title", "platform", "copyright_year", "has_whatsapp_link", "has_tel_link",
                 "meta_viewport", "has_video", "blog_last_date", "word_count", "social_links", "weak_signals",
                 "psi_perf", "psi_lcp_s", "current_screenshot_path", "logo_url", "colours", "hero_image_url"}


def evaluation_row(c: Candidate, run_id: str | None, list_date: date) -> dict[str, Any]:
    s = c.score
    return {
        "id": c.evaluation_id, "run_id": run_id, "place_id": c.place_id, "list_date": list_date.isoformat(),
        "subcategory": c.subcategory, "track": c.track, "site_status": c.audit.site_status if c.audit else None,
        "pre_score": round(c.pre_score, 2), "score": round(s.total, 2) if s else None,
        "breakdown": s.breakdown if s else {},
        "scores": {t: {"total": sc.total, "eligible": sc.eligible, "breakdown": sc.breakdown} for t, sc in c.scores.items()},
        "gate_codes": c.gate_codes, "selected": c.selection is not None,
    }


def lead_row(c: Candidate, list_date: date) -> dict[str, Any]:
    from pipeline.facts import top_fact_code
    a = c.audit
    return {
        "id": c.lead_id, "place_id": c.place_id, "evaluation_id": c.evaluation_id, "list_date": list_date.isoformat(),
        "subcategory": c.subcategory, "track": c.track, "rank": c.rank,
        "status": "shortlisted" if c.selection == "finalist" else "reserve",
        "site_status": a.site_status if a else None, "area": c.area, "top_fact_code": top_fact_code(c),
        "message_variants": [{"message": v.message, "used_fact_ids": v.used_fact_ids, "source": v.source,
                              "swahili_touch": v.swahili_touch} for v in c.variants],
        "message_final": c.variants[0].message if c.variants else None,
        "chosen_variant": 0 if c.variants else None,
        "used_fact_ids": c.variants[0].used_fact_ids if c.variants else [],
        "variant_source": c.variant_source, "poster_lines": c.poster_lines, "teaser_path": c.teaser_path,
        "slug": c.slug,
        "brand": {"logo_path": c.logo_path, "hero_path": c.hero_path, **(a.colours if a else {})},
    }


# ---------------------------------------------------------------- in-memory store

class MemoryStore:
    """Complete store in memory. Used for --offline and tests; `dump()` writes JSON for inspection."""

    def __init__(self, files_dir: Path | None = None):
        self.tables: dict[str, dict[Any, dict]] = defaultdict(dict)
        self.usage: dict[tuple[str, str, str], int] = defaultdict(int)
        self.files: dict[str, bytes] = {}
        self.files_dir = files_dir
        self.events: list[dict] = []

    # reads
    def load_known_place_ids(self) -> set[str]:
        return set(self.tables["businesses"])

    def load_gate_context(self, cfg, today: date) -> GateContext:
        ctx = GateContext()
        for row in self.tables["suppression"].values():
            ctx.suppressed_phones.add(row["phone_e164"])
            if row.get("place_id"):
                ctx.suppressed_place_ids.add(row["place_id"])
        _fill_contacted(ctx, cfg, today, self.tables["leads"].values(),
                        lambda pid: (self.tables["businesses"].get(pid) or {}).get("phone_e164"))
        return ctx

    def load_cells(self, subcategory: str) -> list[Cell]:
        return [_cell_from_row(r) for r in self.tables["search_cells"].values() if r["subcategory"] == subcategory]

    def get_usage(self, month: str, api: str) -> int:
        return sum(n for (m, a, _s), n in self.usage.items() if m == month and a == api)

    def usage_rows(self, month: str) -> list[dict]:
        return [{"month": m, "api": a, "sku": s, "count": n} for (m, a, s), n in self.usage.items() if m == month]

    def get_psi_cache(self, domain: str, max_age_days: int) -> dict | None:
        row = self.tables["psi_cache"].get(domain)
        if row and datetime.fromisoformat(row["fetched_at"]) >= _now() - timedelta(days=max_age_days):
            return row
        return None

    def get_settings(self) -> dict[str, Any]:
        return {k: r["value"] for k, r in self.tables["settings"].items()}

    def get_lead_bundle(self, lead_id: str) -> dict | None:
        lead = self.tables["leads"].get(lead_id)
        if not lead:
            return None
        ev = self.tables["evaluations"].get(lead.get("evaluation_id")) or {}
        return {"lead": lead, "business": self.tables["businesses"].get(lead["place_id"]),
                "audit": self.tables["audits"].get(lead["place_id"]), "evaluation": ev,
                "facts": self.tables["facts"].get(lead.get("evaluation_id"))}

    def download(self, path: str) -> bytes | None:
        return self.files.get(path)

    def latest_places_raw(self, place_id: str) -> dict | None:
        rows = [r for r in self.tables["places_raw"].values() if r["place_id"] == place_id]
        return max(rows, key=lambda r: r["fetched_at"])["payload"] if rows else None

    # writes
    def upsert_cells(self, cells: list[Cell]) -> None:
        for c in cells:
            c.id = c.id or str(uuid.uuid4())
            self.tables["search_cells"][c.key] = _cell_row(c)

    def incr_usage(self, month: str, api: str, sku: str, n: int) -> None:
        self.usage[(month, api, sku)] += n

    def put_psi_cache(self, domain: str, perf, lcp, screenshot_path) -> None:
        self.tables["psi_cache"][domain] = {"domain": domain, "fetched_at": _now().isoformat(), "perf": perf,
                                            "lcp_s": lcp, "screenshot_path": screenshot_path}

    def start_run(self, list_date: date, subcategory: str | None, dry_run: bool) -> str:
        rid = str(uuid.uuid4())
        self.tables["runs"][rid] = {"id": rid, "list_date": list_date.isoformat(), "subcategory": subcategory,
                                    "started_at": _now().isoformat(), "status": "running", "dry_run": dry_run}
        return rid

    def finish_run(self, run_id: str, **fields) -> None:
        self.tables["runs"][run_id].update({k: _iso(v) for k, v in fields.items()}, finished_at=_now().isoformat())

    def save_candidates(self, cands: list[Candidate], run_id: str | None, list_date: date) -> None:
        for c in cands:
            prev = self.tables["businesses"].get(c.place_id)
            row = business_row(c)
            row["first_seen_at"] = prev["first_seen_at"] if prev else _now().isoformat()
            self.tables["businesses"][c.place_id] = row
            self.tables["places_raw"][(c.place_id, row["last_seen_at"])] = {"place_id": c.place_id, "payload": c.raw,
                                                                             "fetched_at": row["last_seen_at"]}
            if (a := audit_row(c)) is not None:
                self.tables["audits"][c.place_id] = a
            c.evaluation_id = c.evaluation_id or str(uuid.uuid4())
            self.tables["evaluations"][c.evaluation_id] = evaluation_row(c, run_id, list_date)
            if c.facts or c.review_facts:
                self.tables["facts"][c.evaluation_id] = {"evaluation_id": c.evaluation_id,
                                                         "facts": [f.to_dict() for f in c.facts],
                                                         "review_facts": c.review_facts}

    def save_leads(self, cands: list[Candidate], list_date: date) -> None:
        for c in cands:
            c.lead_id = c.lead_id or str(uuid.uuid4())
            row = lead_row(c, list_date)
            row.update(created_at=_now().isoformat(), updated_at=_now().isoformat())
            self.tables["leads"][c.lead_id] = row
            self.events.append({"lead_id": c.lead_id, "type": "created", "at": _now().isoformat(),
                                "payload": {"status": row["status"]}})

    def update_lead(self, lead_id: str, fields: dict) -> None:
        self.tables["leads"][lead_id].update({k: _iso(v) for k, v in fields.items()})

    def upload(self, path: str, data: bytes, content_type: str) -> str:
        self.files[path] = data
        if self.files_dir:
            p = self.files_dir / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        return path

    def remove_files(self, paths: list[str]) -> None:
        for p in paths:
            self.files.pop(p, None)

    def mirror_settings(self, payload: dict[str, Any], dashboard_owned: set[str]) -> None:
        for k, v in payload.items():
            if k in dashboard_owned and k in self.tables["settings"]:
                continue
            self.tables["settings"][k] = {"key": k, "value": v, "updated_by": "pipeline"}

    def purge(self, cfg, today: date) -> dict[str, int]:
        return _purge_memory(self, cfg, today)

    def heartbeat(self) -> bool:
        return True

    def dump(self, path: Path) -> None:
        data = {t: list(rows.values()) for t, rows in self.tables.items()}
        data["api_usage"] = self.usage_rows(date.today().strftime("%Y-%m"))
        data["events"] = self.events
        path.write_text(json.dumps(data, indent=1, default=str), encoding="utf-8")


def _fill_contacted(ctx: GateContext, cfg, today: date, leads, phone_of) -> None:
    d = cfg.scoring.dedupe
    cutoff = today - timedelta(days=d.relist_cooldown_days)
    for lead in leads:
        pid, status = lead["place_id"], lead["status"]
        phone = lead.get("phone_e164") or phone_of(pid)
        if lead.get("sent_at") or status in CONTACTED_STATUSES:
            ctx.contacted_place_ids.add(pid)
            if phone:
                ctx.contacted_phones.add(phone)
            continue
        listed = date.fromisoformat(str(lead["list_date"])[:10])
        if status in d.never_relist_statuses or listed >= cutoff:
            ctx.listed_place_ids.add(pid)
            if phone:
                ctx.listed_phones.add(phone)


def _cell_row(c: Cell) -> dict[str, Any]:
    return {"id": c.id, "subcategory": c.subcategory, "query_template": c.query_template, "area": c.area,
            "tier": c.tier, "last_run": _iso(c.last_run), "pages_fetched": c.pages_fetched,
            "last_new_ratio": c.last_new_ratio, "exhausted_streak": c.exhausted_streak, "exhausted": c.exhausted}


def _cell_from_row(r: dict) -> Cell:
    lr = r.get("last_run")
    return Cell(subcategory=r["subcategory"], query_template=r["query_template"], area=r["area"], tier=r["tier"],
                id=r.get("id"), last_run=datetime.fromisoformat(lr) if isinstance(lr, str) else lr,
                pages_fetched=r.get("pages_fetched") or 0,
                last_new_ratio=float(r["last_new_ratio"]) if r.get("last_new_ratio") is not None else None,
                exhausted_streak=r.get("exhausted_streak") or 0, exhausted=bool(r.get("exhausted")))


def _purge_files_for(leads, cfg, today: date) -> list[str]:
    """Teaser/current-site/brand files to delete (brief §14.4)."""
    r = cfg.budget.retention
    purge = set(r.purge_files_statuses)
    cutoff = today - timedelta(days=r.files_days)
    paths: list[str] = []
    for lead in leads:
        if lead["status"] not in purge:
            continue
        if date.fromisoformat(str(lead["list_date"])[:10]) >= cutoff:
            continue
        brand = lead.get("brand") or {}
        paths += [p for p in (lead.get("teaser_path"), brand.get("logo_path"), brand.get("hero_path")) if p]
        paths.append(f"current/{lead['place_id']}.jpg")
    return paths


def _purge_memory(store: MemoryStore, cfg, today: date) -> dict[str, int]:
    r = cfg.budget.retention
    cutoff = _now() - timedelta(days=r.places_raw_days)
    raw = store.tables["places_raw"]
    old = [k for k, v in raw.items() if datetime.fromisoformat(v["fetched_at"]) < cutoff]
    for k in old:
        del raw[k]
    paths = _purge_files_for(store.tables["leads"].values(), cfg, today)
    store.remove_files(paths)
    for lead in store.tables["leads"].values():
        if lead.get("teaser_path") in paths:
            lead["teaser_path"] = None
    return {"places_raw": len(old), "files": len(paths)}


# ---------------------------------------------------------------- dry run

class DryRunStore:
    """Reads from `inner` (Supabase, or an empty MemoryStore with --no-db); writes nothing."""

    def __init__(self, inner):
        self.inner = inner
        self._mem = MemoryStore()

    def __getattr__(self, name):
        # reads go to the real store
        if name in {"load_known_place_ids", "load_gate_context", "load_cells", "get_usage", "get_psi_cache",
                    "get_settings", "get_lead_bundle", "download", "usage_rows", "latest_places_raw"}:
            return getattr(self.inner, name)
        # everything else is a write: keep it in memory only
        return getattr(self._mem, name)

    def get_usage(self, month: str, api: str) -> int:
        return self.inner.get_usage(month, api) + self._mem.get_usage(month, api)

    def load_cells(self, subcategory: str) -> list[Cell]:
        mem = self._mem.load_cells(subcategory)
        return mem or self.inner.load_cells(subcategory)


# ---------------------------------------------------------------- Supabase

class SupabaseStore:
    PAGE = 1000

    def __init__(self, url: str, service_role_key: str):
        from supabase import create_client
        self.client = create_client(url, service_role_key)

    def _t(self, name: str):
        return self.client.table(name)

    def _all(self, table: str, columns: str, apply=lambda q: q) -> list[dict]:
        rows: list[dict] = []
        start = 0
        while True:
            q = apply(self._t(table).select(columns)).range(start, start + self.PAGE - 1)
            batch = q.execute().data or []
            rows += batch
            if len(batch) < self.PAGE:
                return rows
            start += self.PAGE

    # reads
    def load_known_place_ids(self) -> set[str]:
        return {r["place_id"] for r in self._all("businesses", "place_id")}

    def load_gate_context(self, cfg, today: date) -> GateContext:
        ctx = GateContext()
        for r in self._all("suppression", "phone_e164,place_id"):
            ctx.suppressed_phones.add(r["phone_e164"])
            if r.get("place_id"):
                ctx.suppressed_place_ids.add(r["place_id"])
        leads = self._all("leads", "place_id,status,list_date,sent_at,businesses(phone_e164)")
        for lead in leads:
            lead["phone_e164"] = (lead.pop("businesses", None) or {}).get("phone_e164")
        _fill_contacted(ctx, cfg, today, leads, lambda pid: None)
        return ctx

    def load_cells(self, subcategory: str) -> list[Cell]:
        return [_cell_from_row(r) for r in self._all("search_cells", "*", lambda q: q.eq("subcategory", subcategory))]

    def get_usage(self, month: str, api: str) -> int:
        rows = self._t("api_usage").select("count").eq("month", month).eq("api", api).execute().data or []
        return sum(int(r["count"]) for r in rows)

    def usage_rows(self, month: str) -> list[dict]:
        return self._t("api_usage").select("*").eq("month", month).execute().data or []

    def get_psi_cache(self, domain: str, max_age_days: int) -> dict | None:
        since = (_now() - timedelta(days=max_age_days)).isoformat()
        rows = self._t("psi_cache").select("*").eq("domain", domain).gte("fetched_at", since).execute().data
        return rows[0] if rows else None

    def get_settings(self) -> dict[str, Any]:
        return {r["key"]: r["value"] for r in self._t("settings").select("key,value").execute().data or []}

    def get_lead_bundle(self, lead_id: str) -> dict | None:
        rows = self._t("leads").select("*").eq("id", lead_id).execute().data
        if not rows:
            return None
        lead = rows[0]
        one = lambda t, col, v: ((self._t(t).select("*").eq(col, v).execute().data) or [None])[0]  # noqa: E731
        return {"lead": lead, "business": one("businesses", "place_id", lead["place_id"]),
                "audit": one("audits", "place_id", lead["place_id"]),
                "evaluation": one("evaluations", "id", lead["evaluation_id"]) if lead.get("evaluation_id") else None,
                "facts": one("facts", "evaluation_id", lead["evaluation_id"]) if lead.get("evaluation_id") else None}

    def latest_places_raw(self, place_id: str) -> dict | None:
        rows = (self._t("places_raw").select("payload").eq("place_id", place_id).order("fetched_at", desc=True)
                .limit(1).execute().data)
        return rows[0]["payload"] if rows else None

    def download(self, path: str) -> bytes | None:
        try:
            return self.client.storage.from_(BUCKET).download(path)
        except Exception:  # noqa: BLE001
            return None

    # writes
    def upsert_cells(self, cells: list[Cell]) -> None:
        rows = []
        for c in cells:
            row = _cell_row(c)
            if not row["id"]:
                row.pop("id")
            rows.append(row)
        if rows:
            data = self._t("search_cells").upsert(rows, on_conflict="subcategory,query_template,area").execute().data
            ids = {(r["subcategory"], r["query_template"], r["area"]): r["id"] for r in data or []}
            for c in cells:
                c.id = ids.get(c.key, c.id)

    def incr_usage(self, month: str, api: str, sku: str, n: int) -> None:
        self.client.rpc("increment_api_usage", {"p_month": month, "p_api": api, "p_sku": sku, "p_n": n}).execute()

    def put_psi_cache(self, domain: str, perf, lcp, screenshot_path) -> None:
        self._t("psi_cache").upsert({"domain": domain, "fetched_at": _now().isoformat(), "perf": perf, "lcp_s": lcp,
                                     "screenshot_path": screenshot_path}).execute()

    def start_run(self, list_date: date, subcategory: str | None, dry_run: bool) -> str:
        row = self._t("runs").insert({"list_date": list_date.isoformat(), "subcategory": subcategory,
                                      "dry_run": dry_run}).execute().data[0]
        return row["id"]

    def finish_run(self, run_id: str, **fields) -> None:
        fields = {k: _iso(v) for k, v in fields.items()}
        fields["finished_at"] = _now().isoformat()
        self._t("runs").update(fields).eq("id", run_id).execute()

    def _chunks(self, rows: list[dict], n: int = 200):
        for i in range(0, len(rows), n):
            yield rows[i:i + n]

    def save_candidates(self, cands: list[Candidate], run_id: str | None, list_date: date) -> None:
        biz = [business_row(c) for c in cands]
        for chunk in self._chunks(biz):
            self._t("businesses").upsert(chunk, on_conflict="place_id").execute()
        raw = [{"place_id": c.place_id, "payload": c.raw} for c in cands if c.raw]
        for chunk in self._chunks(raw, 100):
            self._t("places_raw").insert(chunk).execute()
        audits = [a for c in cands if (a := audit_row(c)) is not None]
        for chunk in self._chunks(audits):
            self._t("audits").upsert(chunk, on_conflict="place_id").execute()
        for c in cands:
            c.evaluation_id = c.evaluation_id or str(uuid.uuid4())
        evals = [evaluation_row(c, run_id, list_date) for c in cands]
        for chunk in self._chunks(evals):
            self._t("evaluations").insert(chunk).execute()
        facts = [{"evaluation_id": c.evaluation_id, "facts": [f.to_dict() for f in c.facts],
                  "review_facts": c.review_facts} for c in cands if c.facts or c.review_facts]
        for chunk in self._chunks(facts):
            self._t("facts").upsert(chunk, on_conflict="evaluation_id").execute()

    def save_leads(self, cands: list[Candidate], list_date: date) -> None:
        for c in cands:
            c.lead_id = c.lead_id or str(uuid.uuid4())
        rows = [lead_row(c, list_date) for c in cands]
        for chunk in self._chunks(rows):
            self._t("leads").upsert(chunk, on_conflict="place_id,list_date").execute()

    def update_lead(self, lead_id: str, fields: dict) -> None:
        self._t("leads").update({k: _iso(v) for k, v in fields.items()}).eq("id", lead_id).execute()

    def upload(self, path: str, data: bytes, content_type: str) -> str:
        self.client.storage.from_(BUCKET).upload(path, data, {"content-type": content_type, "upsert": "true"})
        return path

    def remove_files(self, paths: list[str]) -> None:
        for i in range(0, len(paths), 100):
            self.client.storage.from_(BUCKET).remove(paths[i:i + 100])

    def mirror_settings(self, payload: dict[str, Any], dashboard_owned: set[str]) -> None:
        existing = {r["key"] for r in self._t("settings").select("key").execute().data or []}
        rows = [{"key": k, "value": v, "updated_by": "pipeline", "updated_at": _now().isoformat()}
                for k, v in payload.items() if not (k in dashboard_owned and k in existing)]
        if rows:
            self._t("settings").upsert(rows, on_conflict="key").execute()

    def purge(self, cfg, today: date) -> dict[str, int]:
        r = cfg.budget.retention
        cutoff = (_now() - timedelta(days=r.places_raw_days)).isoformat()
        deleted = self._t("places_raw").delete(count="exact").lt("fetched_at", cutoff).execute()
        before = (today - timedelta(days=r.files_days)).isoformat()
        leads = self._all("leads", "id,status,list_date,teaser_path,place_id,brand",
                          lambda q: q.in_("status", r.purge_files_statuses).lt("list_date", before))
        paths = _purge_files_for(leads, cfg, today)
        if paths:
            self.remove_files(paths)
            gone = [lead["id"] for lead in leads if lead.get("teaser_path") in set(paths)]
            for i in range(0, len(gone), 100):
                self._t("leads").update({"teaser_path": None}).in_("id", gone[i:i + 100]).execute()
        return {"places_raw": deleted.count or 0, "files": len(paths)}

    def heartbeat(self) -> bool:
        self._t("settings").select("key").limit(1).execute()
        return True


def build_store(env, *, offline: bool, dry_run: bool, no_db: bool, files_dir: Path | None = None):
    """Pick the store for this run. A live run needs Supabase; nothing silently falls back."""
    if offline:
        mem = MemoryStore(files_dir=files_dir)
        return DryRunStore(mem) if dry_run else mem
    if dry_run and no_db:
        log.warning("--no-db: suppression, contacted and previously-listed checks are SKIPPED for this dry run")
        return DryRunStore(MemoryStore())
    env.require("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")
    real = SupabaseStore(env.supabase_url, env.supabase_service_role_key)
    return DryRunStore(real) if dry_run else real
