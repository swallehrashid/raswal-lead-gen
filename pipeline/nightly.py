"""The nightly run: plan → discover → normalise → gate → enrich → score → select → facts →
draft → validate → render → upload (brief §3)."""

from __future__ import annotations

import logging
import time
import traceback
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from pipeline.budget import Budget
from pipeline.clients import Clients, build_clients
from pipeline.discover import discover
from pipeline.enrich import enrich
from pipeline.gates import ORDER, cheap_gates
from pipeline.models import Candidate
from pipeline.normalise import normalise
from pipeline.plan import Plan, make_plan, resolve_list_date
from pipeline.report import write_csv
from pipeline.seed import DASHBOARD_OWNED_KEYS, settings_payload
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


@dataclass
class RunContext:
    cfg: Config
    opts: NightlyOptions
    plan: Plan
    clients: Clients
    budget: Budget
    store: object
    run_id: str | None
    now: datetime
    errors: list[dict] = field(default_factory=list)

    def error(self, stage: str, exc: BaseException | str, place_id: str | None = None) -> None:
        msg = str(exc) if isinstance(exc, str) else f"{type(exc).__name__}: {exc}"
        log.error("[%s] %s%s", stage, f"{place_id}: " if place_id else "", msg)
        self.errors.append({"stage": stage, "place_id": place_id, "error": msg[:500]})


def required_env(opts: NightlyOptions) -> list[str]:
    if opts.offline:
        return []
    names = ["GOOGLE_PLACES_API_KEY", "PSI_API_KEY"]
    if not opts.no_llm:
        names.append("GEMINI_API_KEY")
    if not (opts.dry_run and opts.no_db):
        names += ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"]
    return names


def run_nightly(cfg: Config, env: Env, opts: NightlyOptions) -> RunResult:
    t0 = time.monotonic()
    env.require(*required_env(opts))                 # fail fast, listing every missing variable at once
    files_dir = opts.out_dir / "offline_storage" if opts.offline and not opts.dry_run else None
    store = build_store(env, offline=opts.offline, dry_run=opts.dry_run, no_db=opts.no_db, files_dir=files_dir)
    now = datetime.now(timezone.utc)
    list_date = resolve_list_date(cfg, opts.list_date)
    plan = make_plan(cfg, store, list_date=list_date, subcategory=opts.subcategory)
    sub_key = plan.subcategory.key if plan.subcategory else None
    if plan.skip_reason:
        log.info("No list for %s: %s", plan.list_date, plan.skip_reason)
        rid = store.start_run(plan.list_date, sub_key, opts.dry_run)
        store.finish_run(rid, status="skipped", skipped_reason=plan.skip_reason)
        return RunResult("skipped", plan.list_date, sub_key, skipped_reason=plan.skip_reason, store=store)

    log.info("Building list for %s (%s)%s%s", plan.list_date, sub_key, " [DRY RUN]" if opts.dry_run else "",
             " [OFFLINE]" if opts.offline else "")
    if plan.low_on_cells:
        log.warning("%s is running low on unexhausted tier-1 search cells", sub_key)
    clients = build_clients(env, cfg, offline=opts.offline, use_llm=not opts.no_llm, subcategory=sub_key)
    budget = Budget.from_config(cfg, store, plan.list_date, places_override=opts.max_places_calls, dry_run=opts.dry_run)
    run_id = store.start_run(plan.list_date, sub_key, opts.dry_run)
    ctx = RunContext(cfg, opts, plan, clients, budget, store, run_id, now)
    try:
        store.mirror_settings(settings_payload(cfg), DASHBOARD_OWNED_KEYS)
        result = _run_stages(ctx)
    except Exception as e:  # noqa: BLE001
        ctx.error("run", e)
        log.error(traceback.format_exc())
        store.finish_run(run_id, status="failed", errors=ctx.errors, places_calls=budget.used("places"),
                         psi_calls=budget.used("psi"), gemini_calls=budget.used("gemini"))
        raise
    result.stats["seconds"] = round(time.monotonic() - t0, 1)
    log.info("Done in %.0fs: %s", result.stats["seconds"], {k: v for k, v in result.stats.items() if k != "gate_counts"})
    return result


def _run_stages(ctx: RunContext) -> RunResult:
    cfg, opts, plan, store = ctx.cfg, ctx.opts, ctx.plan, ctx.store
    sub = plan.subcategory
    # ---- discover
    known = store.load_known_place_ids()
    disc = discover(cfg, plan, ctx.clients.places, ctx.budget, known, now=ctx.now,
                    sleep=(lambda s: None) if opts.offline else time.sleep)
    store.upsert_cells(disc.cells_run)
    # ---- normalise + cheap gates
    cands = normalise(disc.places, disc.cell_of, cfg, sub.key)
    gate_ctx = store.load_gate_context(cfg, plan.list_date)
    for c in cands:
        c.gate_codes = cheap_gates(c, cfg, gate_ctx, ctx.now)
    passed = [c for c in cands if not c.gate_codes]
    log.info("gates: %d of %d candidates passed", len(passed), len(cands))

    # ---- enrich: site audit + PSI for the top `enrich_limit` by pre-score
    enriched = enrich(passed, cfg, ctx.clients.fetcher, ctx.clients.psi, ctx.budget, store, ctx.now,
                      limit=opts.limit, sleep=(lambda s: None) if opts.offline else None)
    selected: list[Candidate] = []

    # ---- persist + report
    gate_counts = Counter(code for c in cands for code in c.gate_codes)
    stats = {
        "raw_candidates": len(disc.places), "passed_gates": len(passed), "enriched": len(enriched),
        "qualified_web": sum(1 for c in cands if c.scores.get("web") and c.scores["web"].eligible
                             and c.scores["web"].margin >= 0 and not c.gate_codes),
        "qualified_content": sum(1 for c in cands if c.scores.get("content") and c.scores["content"].eligible
                                 and c.scores["content"].margin >= 0 and not c.gate_codes),
        "shipped_web": sum(1 for c in selected if c.track == "web" and c.selection == "finalist"),
        "shipped_content": sum(1 for c in selected if c.track == "content" and c.selection == "finalist"),
        "gate_counts": {k: gate_counts[k] for k in ORDER if gate_counts.get(k)},
    }
    store.save_candidates(cands, ctx.run_id, plan.list_date)
    store.save_leads(selected, plan.list_date)
    teaser_files: dict[str, str] = {}
    csv_path = None
    if opts.dry_run or opts.offline:
        csv_path = write_csv(cands, opts.out_dir, plan.list_date, sub.key, teaser_files)
        log.info("CSV: %s", csv_path)
    if not opts.dry_run:
        try:
            log.info("retention purge: %s", store.purge(cfg, plan.list_date))
        except Exception as e:  # noqa: BLE001
            ctx.error("purge", e)
    store.finish_run(ctx.run_id, status="ok", places_calls=ctx.budget.used("places"), psi_calls=ctx.budget.used("psi"),
                     gemini_calls=ctx.budget.used("gemini"), errors=ctx.errors,
                     **{k: v for k, v in stats.items()})
    stats.update(places_calls=ctx.budget.used("places"), psi_calls=ctx.budget.used("psi"),
                 gemini_calls=ctx.budget.used("gemini"), errors=len(ctx.errors))
    return RunResult("ok", plan.list_date, sub.key, cands, csv_path, teaser_files, stats, store)
