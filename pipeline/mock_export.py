"""Build the dashboard's mock dataset from the fixtures (no keys, no network).

    python -m pipeline export-mock        (or: cd dashboard && npm run mock)

Runs the offline pipeline for Mon 12 – Fri 16 Oct 2026 into one in-memory store, then
simulates a realistic week (sends, follow-ups, replies, demos, a win, an opt-out) so every
dashboard screen has data. "Today" in the mock is Friday 16 Oct: the roofing list is fresh
(Review mode), earlier lists have history. Output: dashboard/public/mock/.
"""

from __future__ import annotations

import io
import json
import logging
import random
import shutil
from datetime import date, datetime, timedelta, timezone

from PIL import Image

from pipeline.models import Candidate
from pipeline.nightly import NightlyOptions, run_nightly
from pipeline.seed import config_cells
from pipeline.settings import OUT_DIR, ROOT, Config, Env
from pipeline.store import MemoryStore
from pipeline.utils.dates import WorkCalendar

log = logging.getLogger(__name__)

TODAY = date(2026, 10, 16)
DAYS = [date(2026, 10, 12), date(2026, 10, 13), date(2026, 10, 14), date(2026, 10, 15), date(2026, 10, 16)]
OUT = ROOT / "dashboard" / "public" / "mock"
EAT = timezone(timedelta(hours=3))


def _at(d: date, hh: int, mm: int) -> str:
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=EAT).astimezone(timezone.utc).isoformat()


class Sim:
    def __init__(self, store: MemoryStore, cfg: Config):
        self.s, self.cfg = store, cfg
        self.cal = WorkCalendar.from_config(cfg.calendar)
        self.rng = random.Random(1610)

    def ev(self, lead: dict, type_: str, at: str, **payload) -> None:
        self.s.events.append({"lead_id": lead["id"], "type": type_, "at": at, "payload": payload})

    def status(self, lead: dict, to: str, at: str, **fields) -> None:
        self.ev(lead, "status", at, **{"from": lead["status"], "to": to})
        lead.update(status=to, updated_at=at, **fields)

    def promote(self, lead: dict, at: str) -> dict | None:
        res = sorted([r for r in self.s.tables["leads"].values() if r["list_date"] == lead["list_date"]
                      and r["track"] == lead["track"] and r["status"] == "reserve"], key=lambda r: r["rank"])
        if not res:
            return None
        self.status(res[0], "shortlisted", at)
        self.ev(res[0], "promoted", at, replaces=lead["id"])
        return res[0]

    def work(self, d: date, n: int) -> date:
        return self.cal.add_working_days(d, n)

    def run_list(self, d: date) -> None:
        leads = sorted([r for r in self.s.tables["leads"].values() if r["list_date"] == d.isoformat()],
                       key=lambda r: (r["track"], r["rank"]))
        queue = [r for r in leads if r["status"] == "shortlisted"]
        minute = 0
        while queue:
            lead = queue.pop(0)
            hh, mm = (9, 35) if minute < 90 else (14, 5)
            t = _at(d, hh + (mm + minute % 90) // 60, (mm + minute % 90) % 60)
            minute += 4
            self.status(lead, "approved", _at(d, 8, 40), approved_at=_at(d, 8, 40))
            roll = self.rng.random()
            if roll < 0.07:
                self.status(lead, "skipped", _at(d, 8, 45),
                            skip_reason=self.rng.choice(["too_big", "wrong_category", "weak_hook", "bad_teaser"]))
                if (p := self.promote(lead, _at(d, 8, 45))) is not None:
                    queue.append(p)
                continue
            if roll < 0.11:
                self.status(lead, "no_whatsapp", t)
                if (p := self.promote(lead, t)) is not None:
                    queue.append(p)
                continue
            self.status(lead, "sent", t, sent_at=t, fu1_due=self.work(d, 3).isoformat(), fu2_due=self.work(d, 8).isoformat())
            self.after_send(lead, d)

    def after_send(self, lead: dict, d: date) -> None:
        if self.rng.random() < 0.3:
            rd = self.work(d, self.rng.choice([0, 0, 1, 2]))
            if rd >= TODAY:
                rd = d
            at = _at(rd, self.rng.choice([10, 11, 15, 16, 19]), self.rng.randint(0, 59))
            kind = self.rng.choices(["interested", "price", "question", "not_now", "has_provider", "stop"],
                                    [40, 20, 15, 10, 10, 5])[0]
            text = {"interested": "Yes please send the link", "price": "How much is this?",
                    "question": "Who made this?", "not_now": "Not now, maybe next year",
                    "has_provider": "We already have a web guy", "stop": "Please stop messaging"}[kind]
            self.ev(lead, "reply", at, reply_type=kind, text=text)
            lead.update(replied_at=at, reply_type=kind)
            if kind == "interested":
                self.status(lead, "demo_queued", at, demo_type=lead["track"], demo_queued_at=at)
                self.ev(lead, "interested", at, demo_type=lead["track"])
                if d <= date(2026, 10, 13) and self.rng.random() < 0.75:
                    sd = self.work(rd, 0) if rd < TODAY else rd
                    st = _at(sd, 17, 30)
                    link = f"https://{lead['slug']}.raswaltechsolutions.com"
                    lead["demo_link"] = link
                    self.ev(lead, "demo_link", st, link=link)
                    self.status(lead, "demo_sent", st, demo_sent_at=st, demo_fu1_due=self.work(sd, 1).isoformat(),
                                demo_fu2_due=self.work(sd, 4).isoformat())
                    if self.work(sd, 1) <= TODAY:
                        lead["demo_fu1_sent_at"] = _at(self.work(sd, 1), 14, 20)
                        self.ev(lead, "demo_fu1_sent", lead["demo_fu1_sent_at"])
                    if d == date(2026, 10, 12) and self.rng.random() < 0.7:
                        self.status(lead, "negotiating", _at(self.work(sd, 1), 15, 0))
                        if self.rng.random() < 0.6:
                            self.status(lead, "won", _at(self.work(sd, 2), 12, 0), outcome_value_kes=45000,
                                        closed_at=_at(self.work(sd, 2), 12, 0))
            elif kind in ("price", "question"):
                self.status(lead, "replied", at)
            elif kind == "not_now":
                self.status(lead, "snoozed", at, snoozed_until=TODAY.isoformat())
            elif kind == "has_provider":
                self.status(lead, "lost", at, lost_reason="has_provider", closed_at=at)
            else:
                self.status(lead, "opted_out", at, closed_at=at)
                biz = self.s.tables["businesses"][lead["place_id"]]
                self.s.tables["suppression"][biz["phone_e164"]] = {
                    "phone_e164": biz["phone_e164"], "place_id": lead["place_id"], "reason": "opted_out", "note": None,
                    "added_at": at}
            return
        fu1 = date.fromisoformat(lead["fu1_due"])
        if fu1 < TODAY:
            lead["fu1_sent_at"] = _at(fu1, 14, 30)
            self.ev(lead, "fu1_sent", lead["fu1_sent_at"])


def _storyline(self: Sim) -> None:
    """Guarantee every screen has an example: a win, demos sent (one follow-up due today), an opt-out."""
    leads = self.s.tables["leads"].values()

    def pick(list_day: date, track: str | None = None) -> dict | None:
        return next((r for r in sorted(leads, key=lambda r: r["rank"]) if r["list_date"] == list_day.isoformat()
                     and r["status"] == "sent" and not r.get("replied_at") and (track is None or r["track"] == track)), None)

    def interested(r: dict, day: date, hh: int) -> str:
        at = _at(day, hh, 10)
        self.ev(r, "reply", at, reply_type="interested", text="Yes, send me the link")
        r.update(replied_at=at, reply_type="interested")
        self.status(r, "demo_queued", at, demo_type=r["track"], demo_queued_at=at)
        self.ev(r, "interested", at, demo_type=r["track"])
        return at

    def demo(r: dict, day: date) -> None:
        st = _at(day, 16, 45)
        link = f"https://{r['slug']}.raswaltechsolutions.com"
        r["demo_link"] = link
        self.ev(r, "demo_link", st, link=link)
        self.status(r, "demo_sent", st, demo_sent_at=st, demo_fu1_due=self.work(day, 1).isoformat(),
                    demo_fu2_due=self.work(day, 4).isoformat())

    mon, tue, wed, thu = DAYS[:4]
    if (r := pick(mon, "web")) is not None:                       # won
        interested(r, mon, 11)
        demo(r, mon)
        r["demo_fu1_sent_at"] = _at(tue, 14, 0)
        self.ev(r, "demo_fu1_sent", r["demo_fu1_sent_at"])
        self.status(r, "negotiating", _at(tue, 15, 30))
        self.status(r, "won", _at(wed, 10, 0), outcome_value_kes=45000, closed_at=_at(wed, 10, 0))
    if (r := pick(mon, "content")) is not None:                   # content demo, waiting
        interested(r, tue, 9)
        demo(r, tue)
        r["demo_fu1_sent_at"] = _at(wed, 14, 0)
        self.ev(r, "demo_fu1_sent", r["demo_fu1_sent_at"])
    if (r := pick(tue, "web")) is not None:                       # demo follow-up due today
        interested(r, wed, 16)
        demo(r, thu)
    if (r := pick(wed)) is not None:                              # opt-out → suppression
        at = _at(wed, 12, 5)
        self.ev(r, "reply", at, reply_type="stop", text="Please don't message again")
        r.update(replied_at=at, reply_type="stop")
        self.status(r, "opted_out", at, closed_at=at)
        phone = self.s.tables["businesses"][r["place_id"]]["phone_e164"]
        self.s.tables["suppression"][phone] = {"phone_e164": phone, "place_id": r["place_id"], "reason": "opted_out",
                                               "note": None, "added_at": at}


Sim.storyline = _storyline


def _shrink(jpeg: bytes, w: int = 720, q: int = 76) -> bytes:
    img = Image.open(io.BytesIO(jpeg)).convert("RGB")
    img = img.resize((w, round(img.height * w / img.width)), Image.LANCZOS)
    b = io.BytesIO()
    img.save(b, "JPEG", quality=q, optimize=True, progressive=True)
    return b.getvalue()


def export_mock(cfg: Config, env: Env, args) -> int:
    logging.getLogger("pipeline").setLevel(logging.WARNING)
    store = MemoryStore()
    cands: dict[str, Candidate] = {}
    for d in DAYS:
        res = run_nightly(cfg, env, NightlyOptions(list_date=d, offline=True, dry_run=False, no_render=True,
                                                    max_places_calls=40, store=store, out_dir=OUT_DIR / "mock-run"))
        for c in res.candidates:
            if c.lead_id:
                cands[c.lead_id] = c
        run = store.tables["runs"][next(reversed(store.tables["runs"]))]
        start = datetime(d.year, d.month, d.day, tzinfo=EAT) - timedelta(hours=2, minutes=30)
        run.update(started_at=start.astimezone(timezone.utc).isoformat(),
                   finished_at=(start + timedelta(minutes=31)).astimezone(timezone.utc).isoformat())
        print(f"{d} {res.subcategory}: {res.stats.get('shipped_web')} web / {res.stats.get('shipped_content')} content")
    # created events at list time
    for e in store.events:
        lead = store.tables["leads"][e["lead_id"]]
        e["at"] = _at(date.fromisoformat(lead["list_date"]) - timedelta(days=1), 22, 1)
    sim = Sim(store, cfg)
    for d in DAYS[:-1]:
        sim.run_list(d)
    sim.storyline()

    # files: today's list + anything in the demo pipeline gets full assets
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "files").mkdir(parents=True)
    leads = list(store.tables["leads"].values())
    today = TODAY.isoformat()
    due_today = {r["id"] for r in leads if r["status"] == "sent" and (r.get("fu1_due") or "9") <= today
                 and not r.get("fu1_sent_at")}
    want = [r for r in leads if r["list_date"] == today or r["id"] in due_today
            or r["status"] in ("demo_queued", "demo_sent", "negotiating", "won", "snoozed")]
    files: dict[str, str] = {}
    if not args.no_render:
        from pipeline.teaser import render_teasers
        to_render = [cands[r["id"]] for r in want if r["id"] in cands]
        for i in range(0, len(to_render), 40):
            jpegs = render_teasers(to_render[i:i + 40], cfg.model_copy(update={}))
            for c in to_render[i:i + 40]:
                if c.place_id in jpegs:
                    path = f"teasers/{store.tables['leads'][c.lead_id]['list_date']}/{c.lead_id}.jpg"
                    store.tables["leads"][c.lead_id]["teaser_path"] = path
                    _write(path, _shrink(jpegs[c.place_id], 540, 72), files)
    for r in want:
        c = cands.get(r["id"])
        if not c or not c.audit:
            continue
        a = c.audit
        if a.psi_screenshot and a.current_screenshot_path and r["list_date"] == today:
            _write(a.current_screenshot_path, a.psi_screenshot, files)
        if a.logo_bytes and c.logo_path:
            _write(c.logo_path, a.logo_bytes, files)
        if a.hero_bytes and c.hero_path:
            _write(c.hero_path, _shrink(a.hero_bytes, 800, 65), files)
    for r in leads:     # leads without files keep their paths only if the file exists
        if r.get("teaser_path") not in files:
            r["teaser_path"] = None

    dataset = build_dataset(store, cfg, files)
    (OUT / "dataset.json").write_text(json.dumps(dataset, default=str, separators=(",", ":")), encoding="utf-8")
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"mock dataset: {len(dataset['leads'])} leads, {len(files)} files, {size / 1e6:.1f} MB → {OUT}")
    return 0


def _write(path: str, data: bytes, files: dict[str, str]) -> None:
    p = OUT / "files" / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    files[path] = f"/mock/files/{path}"


def build_dataset(store: MemoryStore, cfg: Config, files: dict[str, str]) -> dict:
    t = store.tables
    leads = []
    for r in t["leads"].values():
        biz = dict(t["businesses"][r["place_id"]])
        audit = t["audits"].get(r["place_id"])
        if audit:
            audit = {**audit, **{k: audit.get("raw", {}).get(k) for k in ("weak_signals",)}}
        biz["audit"] = audit
        ev = t["evaluations"].get(r["evaluation_id"]) or {}
        facts = t["facts"].get(r["evaluation_id"])
        lead = {k: r.get(k) for k in LEAD_FIELDS}
        lead.update(business=biz, evaluation={"score": ev.get("score"), "breakdown": ev.get("breakdown") or {},
                                              "facts": {"facts": facts["facts"], "review_facts": facts["review_facts"]}
                                              if facts else None})
        leads.append(lead)
    events = [{"id": i + 1, **e} for i, e in enumerate(sorted(store.events, key=lambda e: e["at"]))]
    cells = []
    for sub in cfg.subcategories:
        total = sum(1 for c in config_cells(cfg) if c.subcategory == sub and c.tier == 1)
        active = 2 if sub == "hardware_supplies" else total - 3     # show the "running low" banner once
        cells.append({"subcategory": sub, "tier1_active": active, "tier1_total": total})
    month = TODAY.strftime("%Y-%m")
    usage = [{"month": month, "api": "places", "sku": cfg.budget.places.sku, "count": 168},
             {"month": month, "api": "psi", "sku": "runpagespeed", "count": 512},
             {"month": month, "api": "gemini", "sku": "generate_content", "count": 191}]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(), "today": TODAY.isoformat(),
        "settings": {k: v["value"] for k, v in t["settings"].items()},
        "runs": list(t["runs"].values()), "leads": leads, "events": events, "api_usage": usage, "cells": cells,
        "suppression": list(t["suppression"].values()),
        "usage_stats": {"db_bytes": 41_500_000, "storage_bytes": 96_000_000, "storage_files": 412},
        "files": files,
    }


LEAD_FIELDS = ["id", "place_id", "evaluation_id", "list_date", "subcategory", "track", "rank", "status", "site_status",
               "area", "top_fact_code", "message_variants", "message_final", "chosen_variant", "used_fact_ids",
               "variant_source", "poster_lines", "teaser_path", "slug", "social_state", "brand", "skip_reason", "notes",
               "approved_at", "sent_at", "fu1_due", "fu1_sent_at", "fu2_due", "fu2_sent_at", "replied_at", "reply_type",
               "snoozed_until", "demo_type", "demo_queued_at", "demo_link", "demo_sent_at", "demo_fu1_due",
               "demo_fu1_sent_at", "demo_fu2_due", "demo_fu2_sent_at", "outcome_value_kes", "lost_reason", "closed_at",
               "created_at", "updated_at"]
