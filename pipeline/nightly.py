"""The nightly run: plan → discover → normalise → gate → enrich → score → select → facts →
draft → validate → render → upload (brief §3)."""

from __future__ import annotations

import logging
import time
import traceback
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from pipeline.budget import Budget
from pipeline.clients import Clients, build_clients
from pipeline.discover import discover
from pipeline.draft import Drafter, make_draft_finalizer
from pipeline.enrich import enrich
from pipeline.facts import build_facts
from pipeline.gates import ORDER, cheap_gates
from pipeline.models import Candidate
from pipeline.normalise import normalise
from pipeline.plan import DayPlan, make_day_plan, resolve_list_date
from pipeline.report import write_csv
from pipeline.score import score_candidate
from pipeline.seed import DASHBOARD_OWNED_KEYS, settings_payload
from pipeline.select import select
from pipeline.settings import OUT_DIR, Config, Env
from pipeline.store import build_store

log = logging.getLogger(__name__)


@dataclass
class NightlyOptions:
    list_date: date | None = None
    subcategory: str | None = None
    dry_run: bool = False
    no_llm: bool = False
    no_render: bool = False
    max_places_calls: int | None = None
    limit: int | None = None
    offline: bool = False
    no_db: bool = False
    out_dir: Path = OUT_DIR
    store: object | None = None          # inject a store (tests / export-mock)

    @classmethod
    def from_args(cls, a) -> NightlyOptions:
        return cls(list_date=a.list_date, subcategory=a.subcategory, dry_run=a.dry_run, no_llm=a.no_llm,
                   no_render=a.no_render, max_places_calls=a.max_places_calls, limit=a.limit, offline=a.offline,
                   no_db=a.no_db)


@dataclass
class RunResult:
    status: str
    list_date: date
    subcategory: str | None
    candidates: list[Candidate] = field(default_factory=list)
    csv_path: Path | None = None
    teaser_files: dict[str, str] = field(default_factory=dict)
    stats: dict = field(default_factory=dict)
    store: object | None = None
    skipped_reason: str | None = None
    csv_paths: list[Path] = field(default_factory=list)


@dataclass
class RunContext:
    cfg: Config
    opts: NightlyOptions
    day: DayPlan
    clients: Clients
    budget: Budget
    store: object
    run_ids: dict[str, str | None]       # subcategory → runs.id
    now: datetime
    mix: dict[str, int]                  # subcategory → today's finalist target
    errors: list[dict] = field(default_factory=list)
    drafter: object | None = None
    places: dict[str, object] = field(default_factory=dict)       # subcategory → places client

    def error(self, stage: str, exc: BaseException | str, place_id: str | None = None) -> None:
        msg = str(exc) if isinstance(exc, str) else f"{type(exc).__name__}: {exc}"
        log.error("[%s] %s%s", stage, f"{place_id}: " if place_id else "", msg)
        self.errors.append({"stage": stage, "place_id": place_id, "error": msg[:500]})


def apply_dashboard_settings(cfg: Config, settings: dict) -> Config:
    """Dashboard edits win for the daily mix (Settings screen)."""
    mix = settings.get("daily_mix")
    if not isinstance(mix, dict):
        return cfg
    cfg = cfg.model_copy(deep=True)
    out = {}
    for k, v in cfg.scoring.selection.daily_mix.items():
        try:
            out[k] = max(0, int(mix.get(k, v)))
        except (TypeError, ValueError):
            out[k] = v
    cfg.scoring.selection.daily_mix = out
    return cfg


def paused_by_dashboard(settings: dict, d: date) -> str | None:
    for p in settings.get("pause_list") or []:
        if str(p.get("start", "")) <= d.isoformat() <= str(p.get("end", "")):
            return p.get("note") or "pause"
    return None


def required_env(opts: NightlyOptions) -> list[str]:
    if opts.offline:
        return []
    names = ["GOOGLE_PLACES_API_KEY", "PSI_API_KEY"]
    if not opts.no_llm:
        names.append("GEMINI_API_KEY")
    if not (opts.dry_run and opts.no_db):
        names += ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"]
    return names


def day_mix(cfg: Config, day: DayPlan) -> dict[str, int]:
    """Today's finalist target per planned subcategory. A manual single-subcategory run that isn't in
    the daily mix (e.g. a paused vertical) falls back to 10."""
    mix = cfg.scoring.selection.daily_mix
    return {p.subcategory.key: (mix.get(p.subcategory.key) or 10) for p in day.plans}


def run_nightly(cfg: Config, env: Env, opts: NightlyOptions) -> RunResult:
    t0 = time.monotonic()
    env.require(*required_env(opts))                 # fail fast, listing every missing variable at once
    files_dir = opts.out_dir / "offline_storage" if opts.offline and not opts.dry_run else None
    store = opts.store or build_store(env, offline=opts.offline, dry_run=opts.dry_run, no_db=opts.no_db,
                                      files_dir=files_dir)
    now = datetime.now(timezone.utc)
    list_date = resolve_list_date(cfg, opts.list_date)
    cfg = apply_dashboard_settings(cfg, store.get_settings())
    day = make_day_plan(cfg, store, list_date=list_date, subcategory=opts.subcategory)
    if not day.skip_reason and (p := paused_by_dashboard(store.get_settings(), list_date)):
        day.skip_reason = f"{list_date} is paused in the dashboard ({p})"
    sub_keys = [p.subcategory.key for p in day.plans]
    label = opts.subcategory or ("+".join(sub_keys) if sub_keys else None)
    if day.skip_reason:
        log.info("No list for %s: %s", day.list_date, day.skip_reason)
        rid = store.start_run(day.list_date, opts.subcategory, opts.dry_run)
        store.finish_run(rid, status="skipped", skipped_reason=day.skip_reason)
        return RunResult("skipped", day.list_date, label, skipped_reason=day.skip_reason, store=store)

    mix = day_mix(cfg, day)
    log.info("Building list for %s (%s)%s%s", day.list_date, ", ".join(f"{k} {v}" for k, v in mix.items()),
             " [DRY RUN]" if opts.dry_run else "", " [OFFLINE]" if opts.offline else "")
    for p in day.plans:
        if p.low_on_cells:
            log.warning("%s is running low on unexhausted tier-1 search cells", p.subcategory.key)
    clients = build_clients(env, cfg, offline=opts.offline, use_llm=not opts.no_llm,
                            subcategory=sub_keys[0] if sub_keys else None)
    places = {k: (build_clients(env, cfg, offline=True, use_llm=False, subcategory=k).places if opts.offline
                  else clients.places) for k in sub_keys}
    budget = Budget.from_config(cfg, store, day.list_date, places_override=opts.max_places_calls, dry_run=opts.dry_run)
    run_ids = {k: store.start_run(day.list_date, k, opts.dry_run) for k in sub_keys}
    ctx = RunContext(cfg, opts, day, clients, budget, store, run_ids, now, mix, places=places)
    try:
        store.mirror_settings(settings_payload(cfg), DASHBOARD_OWNED_KEYS)
        result = _run_stages(ctx)
    except Exception as e:  # noqa: BLE001
        ctx.error("run", e)
        log.error(traceback.format_exc())
        for rid in run_ids.values():
            store.finish_run(rid, status="failed", errors=ctx.errors, places_calls=budget.used("places"),
                             psi_calls=budget.used("psi"), gemini_calls=budget.used("gemini"))
        raise
    result.stats["seconds"] = round(time.monotonic() - t0, 1)
    log.info("Done in %.0fs: %s", result.stats["seconds"], {k: v for k, v in result.stats.items() if k != "gate_counts"})
    return result


def make_finalizer(ctx: RunContext):
    """Called by select() for each accepted candidate: drafts it. Returns False → NO_HOOK."""
    ctx.drafter = Drafter(ctx.cfg, ctx.clients.llm, ctx.budget,
                          sleep=(lambda s: None) if ctx.opts.offline else time.sleep)
    return make_draft_finalizer(ctx.cfg, ctx.drafter, ctx.now)


def resolve_overlap(cands: list[Candidate], prefer: str = "land_developers") -> list[Candidate]:
    """One business can be found by two subcategories (LM Realtors, kwetu...). Keep a single candidate per
    place: the one that passes gates, then scores higher; ties go to `prefer`."""
    def key(c: Candidate):
        s = c.score.total if c.score else c.pre_score
        return (not c.gate_codes, s, c.subcategory == prefer)

    best: dict[str, Candidate] = {}
    for c in cands:
        if c.place_id not in best or key(c) > key(best[c.place_id]):
            best[c.place_id] = c
    return [c for c in cands if best[c.place_id] is c]


def prepare_assets(ctx: RunContext, selected: list[Candidate]) -> None:
    """Brand assets + storage paths for finalists and reserves (≤ 40/night)."""
    from concurrent.futures import ThreadPoolExecutor

    from pipeline.brand import find_brand_assets
    from pipeline.utils.text import slugify

    def one(c: Candidate) -> None:
        try:
            if c.audit and c.audit.html:
                find_brand_assets(c.audit, ctx.clients.fetcher, ctx.cfg)
        except Exception as e:  # noqa: BLE001
            ctx.error("brand", e, c.place_id)

    with ThreadPoolExecutor(max_workers=ctx.cfg.budget.site_fetch.concurrency) as pool:
        list(pool.map(one, selected))
    for c in selected:
        c.lead_id = c.lead_id or str(uuid.uuid4())
        c.slug = slugify(c.name_norm)
        a = c.audit
        if a and a.psi_screenshot:
            a.current_screenshot_path = f"current/{c.place_id}.jpg"
        if a and a.logo_bytes:
            c.logo_path = f"brand/{c.place_id}/logo.png"
        if a and a.hero_bytes:
            c.hero_path = f"brand/{c.place_id}/hero.jpg"


def render_and_store_teasers(ctx: RunContext, selected: list[Candidate]) -> dict[str, str]:
    """Render teasers (finalists first, then reserves). Dry/offline runs also write them to out/teasers/."""
    if ctx.opts.no_render or not selected:
        return {}
    from pipeline.teaser import render_teasers

    order = sorted(selected, key=lambda c: (c.selection != "finalist", c.subcategory, c.rank or 0))
    try:
        jpegs = render_teasers(order, ctx.cfg)
    except Exception as e:  # noqa: BLE001  - never lose the list because rendering broke
        ctx.error("render", e)
        return {}
    files: dict[str, str] = {}
    local = ctx.opts.dry_run or ctx.opts.offline
    out = ctx.opts.out_dir / "teasers" / ctx.day.list_date.isoformat()
    for c in selected:
        if c.place_id not in jpegs:
            ctx.error("render", "no teaser rendered", c.place_id)
            continue
        c.teaser_jpeg = jpegs[c.place_id]
        c.teaser_path = f"teasers/{ctx.day.list_date.isoformat()}/{c.lead_id}.jpg"
        if local:
            out.mkdir(parents=True, exist_ok=True)
            f = out / f"{c.subcategory}-{c.rank:02d}-{c.selection}-{c.slug}.jpg"
            f.write_bytes(c.teaser_jpeg)
            files[c.place_id] = str(f.relative_to(ctx.opts.out_dir))
    return files


def upload_assets(ctx: RunContext, selected: list[Candidate]) -> None:
    for c in selected:
        a = c.audit
        try:
            if c.teaser_jpeg and c.teaser_path:
                ctx.store.upload(c.teaser_path, c.teaser_jpeg, "image/jpeg")
            if a and a.psi_screenshot and a.current_screenshot_path:
                ctx.store.upload(a.current_screenshot_path, a.psi_screenshot, "image/jpeg")
            if a and a.logo_bytes and c.logo_path:
                ctx.store.upload(c.logo_path, a.logo_bytes, "image/png")
            if a and a.hero_bytes and c.hero_path:
                ctx.store.upload(c.hero_path, a.hero_bytes, "image/jpeg")
        except Exception as e:  # noqa: BLE001
            ctx.error("upload", e, c.place_id)


def _run_stages(ctx: RunContext) -> RunResult:
    cfg, opts, day, store = ctx.cfg, ctx.opts, ctx.day, ctx.store
    sub_keys = [p.subcategory.key for p in day.plans]
    known = store.load_known_place_ids()
    gate_ctx = store.load_gate_context(cfg, day.list_date)
    sleep = (lambda s: None) if opts.offline else time.sleep

    # ---- discover + normalise + cheap gates, per subcategory (Places calls shared by the mix)
    all_places = 0
    cands: list[Candidate] = []
    weight_left = sum(ctx.mix.values()) or 1
    for p in day.plans:
        key = p.subcategory.key
        share = max(1, round(ctx.budget.remaining("places") * ctx.mix[key] / weight_left))
        weight_left -= ctx.mix[key]
        disc = discover(cfg, p, ctx.places[key], ctx.budget, known, now=ctx.now, sleep=sleep, max_calls=share)
        store.upsert_cells(disc.cells_run)
        known = known | set(disc.places)
        all_places += len(disc.places)
        cands += normalise(disc.places, disc.cell_of, cfg, key)
    for c in cands:
        c.gate_codes = cheap_gates(c, cfg, gate_ctx, ctx.now)
    passed = [c for c in cands if not c.gate_codes]
    log.info("gates: %d of %d candidates passed", len(passed), len(cands))

    # ---- enrich: site audit + PSI for the top `enrich_limit` by pre-score
    enriched = enrich(passed, cfg, ctx.clients.fetcher, ctx.clients.psi, ctx.budget, store, ctx.now,
                      limit=opts.limit, sleep=(lambda s: None) if opts.offline else None,
                      places=ctx.clients.places)

    # ---- deterministic facts + scores, then selection (drafting happens inside `finalize`)
    for c in enriched:
        c.facts = build_facts(c, cfg, ctx.now)
        score_candidate(c, cfg, ctx.now)
    cands = resolve_overlap(cands)
    keep = {id(c) for c in cands}
    enriched = [c for c in enriched if id(c) in keep]
    selection = select(enriched, cfg, finalize=make_finalizer(ctx), mix=ctx.mix)
    selected = selection.all

    # ---- assets for finalists + reserves: brand, storage paths, teasers
    prepare_assets(ctx, selected)
    teaser_files = render_and_store_teasers(ctx, selected)

    # ---- persist + report
    gate_counts = Counter(code for c in cands for code in c.gate_codes)
    per_sub = {}
    for key in sub_keys:
        mine = [c for c in cands if c.subcategory == key]
        per_sub[key] = {
            "raw_candidates": len(mine), "passed_gates": sum(1 for c in mine if not c.gate_codes),
            "enriched": sum(1 for c in enriched if c.subcategory == key),
            "qualified": sum(1 for c in mine if c.score and c.score.margin >= 0 and not c.gate_codes),
            "shipped": sum(1 for c in selected if c.subcategory == key and c.selection == "finalist"),
            "angles": dict(Counter(c.angle for c in selected if c.subcategory == key and c.selection == "finalist")),
        }
    stats = {
        "raw_candidates": all_places, "passed_gates": len(passed), "enriched": len(enriched),
        "qualified": sum(v["qualified"] for v in per_sub.values()),
        "shipped": sum(v["shipped"] for v in per_sub.values()),
        "per_subcategory": per_sub,
        "gate_counts": {k: gate_counts[k] for k in ORDER if gate_counts.get(k)},
    }
    first_run = next(iter(ctx.run_ids.values()))
    store.save_candidates(cands, first_run, day.list_date)
    store.save_leads(selected, day.list_date)
    upload_assets(ctx, selected)
    label = opts.subcategory or "+".join(sub_keys)
    csv_paths: list[Path] = []
    if opts.dry_run or opts.offline:
        for key in sub_keys:
            mine = [c for c in cands if c.subcategory == key]
            csv_paths.append(write_csv(mine, opts.out_dir, day.list_date, key, teaser_files))
        log.info("CSV: %s", ", ".join(str(p) for p in csv_paths))
    if not opts.dry_run:
        try:
            log.info("retention purge: %s", store.purge(cfg, day.list_date))
        except Exception as e:  # noqa: BLE001
            ctx.error("purge", e)
    for key, rid in ctx.run_ids.items():
        v = per_sub[key]
        # runs.qualified_web / shipped_web hold the ads totals; the *_content columns are unused now
        store.finish_run(rid, status="ok", places_calls=ctx.budget.used("places"), psi_calls=ctx.budget.used("psi"),
                         gemini_calls=ctx.budget.used("gemini"), errors=ctx.errors,
                         raw_candidates=v["raw_candidates"], passed_gates=v["passed_gates"], enriched=v["enriched"],
                         qualified_web=v["qualified"], shipped_web=v["shipped"], qualified_content=0, shipped_content=0,
                         gate_counts=stats["gate_counts"])
    stats.update(places_calls=ctx.budget.used("places"), psi_calls=ctx.budget.used("psi"),
                 gemini_calls=ctx.budget.used("gemini"), errors=len(ctx.errors))
    return RunResult("ok", day.list_date, label, cands, csv_paths[0] if csv_paths else None, teaser_files, stats, store,
                     csv_paths=csv_paths)
