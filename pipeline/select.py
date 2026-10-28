"""Top-N per subcategory with thresholds, diversity rules and reserves (brief §10.4).

One ads score for everyone; the daily mix says how many leads of each subcategory to ship. Never pads:
if fewer candidates qualify, fewer are shipped.
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

from pipeline.gates import hook_gate
from pipeline.models import Candidate
from pipeline.utils.urls import registered_domain

log = logging.getLogger(__name__)


@dataclass
class Selection:
    finalists: dict[str, list[Candidate]] = field(default_factory=dict)      # subcategory → ranked finalists
    reserves: dict[str, list[Candidate]] = field(default_factory=dict)
    no_hook: list[Candidate] = field(default_factory=list)
    diversity_skips: Counter = field(default_factory=Counter)

    @property
    def all(self) -> list[Candidate]:
        return [c for g in self.finalists for c in self.finalists[g] + self.reserves.get(g, [])]


def rank_key(c: Candidate):
    s = c.score
    return (-s.total, -s.breakdown.get("activity", 0), -s.breakdown.get("reputation", 0), -c.review_count, c.place_id)


def qualified(cands: list[Candidate], subcategory: str) -> list[Candidate]:
    return sorted([c for c in cands if not c.gate_codes and c.subcategory == subcategory and c.score
                   and c.score.eligible and c.score.margin >= 0], key=rank_key)


def _brand_key(c: Candidate) -> str:
    return c.name_key or c.name_norm


def _domain_key(c: Candidate) -> str | None:
    if not c.audit or c.audit.site_status in ("none", "social_as_site"):
        return None
    return registered_domain(c.website_url)


def deterministic_finalize(c: Candidate) -> bool:
    return not hook_gate(c)


def select(cands: list[Candidate], cfg, finalize: Callable[[Candidate], bool] = deterministic_finalize,
           mix: dict[str, int] | None = None) -> Selection:
    """Greedy selection per subcategory. `finalize(c)` runs on each accepted candidate (drafting) and
    returns False if the candidate has no usable fact after all (NO_HOOK).

    Phones, brands and domains are shared across subcategories, so one business is never listed twice
    in the same night. The angle cap is soft: deferred candidates still fill a list that would
    otherwise come up short."""
    sel_cfg = cfg.scoring.selection
    mix = {k: v for k, v in (mix if mix is not None else sel_cfg.daily_mix).items()
           if v > 0 and k in cfg.subcategories and cfg.subcategories[k].active}
    out = Selection()
    used_phones: set[str] = set()
    used_brands: set[str] = set()
    used_domains: set[str] = set()

    def duplicate(c: Candidate) -> bool:
        dom = _domain_key(c)
        return bool((c.phone_e164 and c.phone_e164 in used_phones) or _brand_key(c) in used_brands
                    or (dom and dom in used_domains))

    for group, target in mix.items():
        n_res = sel_cfg.reserves.get(group, 0)
        angle_cap = max(1, math.ceil(target * sel_cfg.max_angle_share))
        out.finalists[group], out.reserves[group] = [], []
        area_count: Counter = Counter()
        angle_count: Counter = Counter()

        def accept(c: Candidate, as_finalist: bool, group=group, area_count=area_count, angle_count=angle_count) -> bool:
            if not finalize(c):
                if "NO_HOOK" not in c.gate_codes:
                    c.gate_codes.append("NO_HOOK")
                out.no_hook.append(c)
                return False
            used_brands.add(_brand_key(c))
            if c.phone_e164:
                used_phones.add(c.phone_e164)
            if dom := _domain_key(c):
                used_domains.add(dom)
            if as_finalist:
                c.selection = "finalist"
                out.finalists[group].append(c)
                area_count[c.area] += 1
                angle_count[c.angle] += 1
            else:
                c.selection = "reserve"
                out.reserves[group].append(c)
            return True

        deferred: list[Candidate] = []
        for c in qualified(cands, group):
            if len(out.finalists[group]) >= target and len(out.reserves[group]) >= n_res:
                break
            if duplicate(c):
                out.diversity_skips["shared_phone_brand_or_domain"] += 1
                continue
            as_finalist = len(out.finalists[group]) < target
            if as_finalist:
                if area_count[c.area] >= sel_cfg.max_per_area_per_subcategory:
                    out.diversity_skips["area_cap"] += 1
                    as_finalist = False
                elif angle_count[c.angle] >= angle_cap:
                    out.diversity_skips["angle_cap"] += 1
                    deferred.append(c)
                    continue
            if not as_finalist and len(out.reserves[group]) >= n_res:
                continue
            accept(c, as_finalist)
        for c in deferred:                              # soft cap: fill the remaining finalist slots
            if len(out.finalists[group]) >= target:
                break
            if duplicate(c) or area_count[c.area] >= sel_cfg.max_per_area_per_subcategory:
                continue
            accept(c, True)
        for i, c in enumerate(out.finalists[group] + out.reserves[group], start=1):
            c.rank = i
        log.info("select %s: %d finalists (target %d), %d reserves; skips %s", group, len(out.finalists[group]),
                 target, len(out.reserves[group]), dict(out.diversity_skips))
    return out
