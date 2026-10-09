"""Smaller CLI commands: rerender, redraft, cells, usage, heartbeat, purge (brief §16.3)."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from pipeline.models import Audit, Candidate, Fact
from pipeline.normalise import parse_reviews
from pipeline.settings import OUT_DIR, Config, Env
from pipeline.utils.text import name_key, slugify

log = logging.getLogger(__name__)


def _live_store(env: Env):
    from pipeline.store import SupabaseStore
    env.require("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")
    return SupabaseStore(env.supabase_url, env.supabase_service_role_key)


def candidate_from_bundle(b: dict, store) -> Candidate:
    """Rebuild a Candidate from stored rows (for rerender / redraft)."""
    lead, biz, audit = b["lead"], b["business"] or {}, b["audit"] or {}
    raw = store.latest_places_raw(lead["place_id"]) or {}          # reviews (kept 30 days)
    reviews = parse_reviews(raw.get("reviews"))
    c = Candidate(place_id=lead["place_id"], name=biz.get("name", ""), name_norm=biz.get("name_norm", ""),
                  subcategory=lead["subcategory"], types=biz.get("types") or [], primary_type=biz.get("primary_type"),
                  address=biz.get("address"), lat=biz.get("lat"), lng=biz.get("lng"), maps_url=biz.get("maps_url"),
                  business_status="OPERATIONAL", phone_raw=None, phone_e164=biz.get("phone_e164"),
                  phone_type=biz.get("phone_type"), website_url=biz.get("website_url"),
                  rating=float(biz["rating"]) if biz.get("rating") is not None else None,
                  review_count=biz.get("review_count") or 0, reviews=reviews, area=lead.get("area") or biz.get("area", ""))
    c.display_name = biz.get("display_name") or c.name
    c.name_key = name_key(c.name_norm)
    c.track, c.rank, c.lead_id = lead["track"], lead["rank"], lead["id"]
    c.selection = "finalist" if lead["status"] != "reserve" else "reserve"
    c.slug = lead.get("slug") or slugify(c.name_norm)
    c.poster_lines = lead.get("poster_lines") or []
    c.teaser_path = lead.get("teaser_path")
    c.evaluation_id = lead.get("evaluation_id")
    a = Audit(audit.get("site_status") or lead.get("site_status") or "none", website_url=audit.get("website_url"),
              final_url=audit.get("final_url"), https_ok=audit.get("https_ok"),
              free_host=(audit.get("raw") or {}).get("free_host"))
    a.colours = audit.get("colours") or {}
    brand = lead.get("brand") or {}
    if brand.get("logo_path"):
        a.logo_bytes = store.download(brand["logo_path"])
    if brand.get("hero_path"):
        a.hero_bytes = store.download(brand["hero_path"])
    c.audit = a
    facts = (b.get("facts") or {}).get("facts") or []
    c.facts = [Fact(**f) for f in facts]
    return c


def rerender(cfg: Config, env: Env, args) -> int:
    from pipeline.teaser import render_teasers
    if args.offline or not args.lead_id:
        return rerender_samples(cfg, env, args.subcategory)
    store = _live_store(env)
    b = store.get_lead_bundle(args.lead_id)
    if not b:
        print(f"lead {args.lead_id} not found")
        return 1
    c = candidate_from_bundle(b, store)
    out = render_teasers([c], cfg)
    if c.place_id not in out:
        print("render failed (see log)")
        return 1
    path = c.teaser_path or f"teasers/{b['lead']['list_date']}/{c.lead_id}.jpg"
    store.upload(path, out[c.place_id], "image/jpeg")
    store.update_lead(c.lead_id, {"teaser_path": path})
    local = OUT_DIR / "teasers" / "rerender" / f"{c.slug}.jpg"
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_bytes(out[c.place_id])
    print(f"re-rendered {c.display_name} → {path} (copy: {local})")
    return 0


def rerender_samples(cfg: Config, env: Env, only: str | None = None) -> int:
    """Visual check (brief §18): render fixture leads for every subcategory to out/teasers/samples/."""
    from pipeline.nightly import NightlyOptions, run_nightly
    from pipeline.teaser import render_teasers
    out_dir = OUT_DIR / "teasers" / "samples"
    out_dir.mkdir(parents=True, exist_ok=True)
    subs = [only] if only else list(cfg.subcategories)
    written = []
    for sub in subs:
        day = cfg.subcategories[sub].list_day
        d = {"mon": 12, "tue": 13, "wed": 14, "thu": 15, "fri": 16}[day]
        res = run_nightly(cfg, env, NightlyOptions(list_date=date(2026, 10, d), subcategory=sub, dry_run=True,
                                                    offline=True, no_render=True, max_places_calls=10,
                                                    out_dir=OUT_DIR / "samples-run"))
        picks = []
        for track in ("web", "content"):
            sel = [c for c in res.candidates if c.track == track and c.selection == "finalist"]
            with_logo = [c for c in sel if c.audit and c.audit.logo_bytes]
            without = [c for c in sel if not (c.audit and c.audit.logo_bytes)]
            picks += (with_logo[:1] + without[:1]) if sel else []
        jpegs = render_teasers(picks, cfg)
        for c in picks:
            if c.place_id in jpegs:
                kind = "logo" if c.audit.logo_bytes else "wordmark"
                f = out_dir / f"{sub}-{c.track}-{kind}.jpg"
                f.write_bytes(jpegs[c.place_id])
                written.append(f)
    for f in written:
        print(f)
    return 0 if written else 1


def redraft(cfg: Config, env: Env, args) -> int:
    from pipeline.budget import Budget
    from pipeline.draft import Drafter
    from pipeline.llm import GeminiClient
    store = _live_store(env)
    b = store.get_lead_bundle(args.lead_id)
    if not b:
        print(f"lead {args.lead_id} not found")
        return 1
    c = candidate_from_bundle(b, store)
    llm = None
    if not args.no_llm:
        env.require("GEMINI_API_KEY")
        llm = GeminiClient(env.gemini_api_key, env.gemini_model, cfg)
    budget = Budget.from_config(cfg, store, datetime.now(timezone.utc).date())
    Drafter(cfg, llm, budget).draft(c)
    variants = [{"message": v.message, "used_fact_ids": v.used_fact_ids, "source": v.source,
                 "swahili_touch": v.swahili_touch} for v in c.variants]
    store.update_lead(c.lead_id, {"message_variants": variants, "message_final": variants[0]["message"],
                                  "chosen_variant": 0, "used_fact_ids": variants[0]["used_fact_ids"],
                                  "variant_source": c.variant_source, "poster_lines": c.poster_lines})
    for i, v in enumerate(variants):
        print(f"--- variant {'AB'[i]} ({v['source']}, {len(v['message'])} chars)\n{v['message']}")
    return 0


def show_cells(cfg: Config, env: Env, args) -> int:
    from pipeline.plan import order_cells, sync_cells
    from pipeline.store import MemoryStore
    store = MemoryStore() if args.offline else _live_store(env)
    sub = cfg.subcategories.get(args.subcategory)
    if not sub:
        print(f"unknown subcategory {args.subcategory}")
        return 1
    cells = order_cells(cfg, sub, sync_cells(cfg, store, sub))
    all_cells = sorted(sync_cells(cfg, store, sub), key=lambda c: (c.tier, c.area, c.query_template))
    active = {c.key for c in cells if not c.exhausted}
    print(f"{'tier':4} {'area':16} {'query':42} {'last run':16} {'pages':>5} {'new%':>5} {'streak':>6}  state")
    for c in all_cells:
        lr = c.last_run.strftime("%Y-%m-%d %H:%M") if c.last_run else "never"
        ratio = f"{c.last_new_ratio * 100:.0f}" if c.last_new_ratio is not None else "-"
        state = "EXHAUSTED" if c.exhausted else ("next" if c.key in active else "waiting (lower tier active)")
        print(f"{c.tier:<4} {c.area[:16]:16} {c.query_template[:42]:42} {lr:16} {c.pages_fetched:>5} {ratio:>5} "
              f"{c.exhausted_streak:>6}  {state}")
    t1 = [c for c in all_cells if c.tier == 1]
    print(f"\n{sum(not c.exhausted for c in t1)} of {len(t1)} tier-1 cells still active")
    return 0


def show_usage(cfg: Config, env: Env) -> int:
    store = _live_store(env)
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    rows = store.usage_rows(month)
    caps = {"places": cfg.budget.places.calls_per_month}
    print(f"API usage for {month}:")
    for r in sorted(rows, key=lambda r: r["api"]):
        cap = caps.get(r["api"])
        print(f"  {r['api']:8} {r['sku']:36} {r['count']:>6}" + (f" / {cap}" if cap else ""))
    if not rows:
        print("  (no calls yet)")
    return 0


def heartbeat(cfg: Config, env: Env) -> int:
    ok = _live_store(env).heartbeat()
    print("Supabase heartbeat ok" if ok else "heartbeat failed")
    return 0 if ok else 1


def purge(cfg: Config, env: Env) -> int:
    res = _live_store(env).purge(cfg, datetime.now(timezone.utc).date())
    print(f"purged: {res}")
    return 0
