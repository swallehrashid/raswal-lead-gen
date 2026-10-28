"""Pick tonight's list date, subcategory and search cells (brief §5, §5.2)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from pipeline.models import Cell
from pipeline.seed import config_cells
from pipeline.settings import Config, Subcategory
from pipeline.utils.dates import WorkCalendar


@dataclass
class Plan:
    list_date: date
    subcategory: Subcategory | None
    skip_reason: str | None
    cells: list[Cell]
    low_on_cells: bool = False


def resolve_list_date(cfg: Config, list_date: date | None, today: date | None = None) -> date:
    cal = WorkCalendar.from_config(cfg.calendar)
    return list_date or cal.next_list_date(today)


@dataclass
class DayPlan:
    """What tonight's run builds: one Plan per subcategory in the daily mix."""
    list_date: date
    skip_reason: str | None
    plans: list[Plan]


def make_day_plan(cfg: Config, store, *, list_date: date | None = None, subcategory: str | None = None,
                  today: date | None = None) -> DayPlan:
    cal = WorkCalendar.from_config(cfg.calendar)
    d = resolve_list_date(cfg, list_date, today)
    if subcategory:
        if subcategory not in cfg.subcategories:
            raise SystemExit(f"Unknown subcategory '{subcategory}'. Known: {', '.join(cfg.subcategories)}")
        subs = [cfg.subcategories[subcategory]]
        # an explicit --subcategory is a manual run: only refuse holidays/pauses, not weekends
        skip = cal.skip_reason(d) if (d in cal.holidays or cal.pause_for(d)) else None
    else:
        skip = cal.skip_reason(d)
        subs = cfg.active_subcategories
        if not subs and not skip:
            skip = "no active subcategory has a daily-mix quota"
    if skip:
        return DayPlan(d, skip, [])
    plans = []
    for sub in subs:
        cells = order_cells(cfg, sub, sync_cells(cfg, store, sub))
        active = [c for c in cells if not c.exhausted]
        tier1 = [c for c in cells if c.tier == 1]
        low = bool(tier1) and sum(not c.exhausted for c in tier1) <= max(1, len(tier1) // 5)
        plans.append(Plan(d, sub, None, active, low_on_cells=low))
    return DayPlan(d, None, plans)


def sync_cells(cfg: Config, store, sub: Subcategory) -> list[Cell]:
    """Load this subcategory's cells, inserting any new (query, area) combinations from config."""
    wanted = [c for c in config_cells(cfg) if c.subcategory == sub.key]
    have = {c.key: c for c in store.load_cells(sub.key)}
    missing = [c for c in wanted if c.key not in have]
    if missing:
        store.upsert_cells(missing)
        for c in missing:
            have[c.key] = c
    wanted_keys = {c.key for c in wanted}
    # cells removed from config are ignored (kept in the DB for history)
    return [c for k, c in have.items() if k in wanted_keys]


def order_cells(cfg: Config, sub: Subcategory, cells: list[Cell]) -> list[Cell]:
    """Order by (tier, last_run ASC NULLS FIRST); use the next tier only when the lower is exhausted."""
    never = datetime.min.replace(tzinfo=timezone.utc)
    cells = sorted(cells, key=lambda c: (c.tier, c.last_run or never, c.query_template, c.area))
    max_tier = 3 if sub.tier3_enabled else 2
    out: list[Cell] = []
    for tier in (1, 2, 3):
        if tier > max_tier:
            break
        in_tier = [c for c in cells if c.tier == tier]
        out += in_tier
        if any(not c.exhausted for c in in_tier):
            break
    return out
