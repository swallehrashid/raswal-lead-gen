"""Top-N per track with thresholds, diversity rules and reserves (brief §10.4).

Never pads: if fewer candidates qualify, fewer are shipped.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

from pipeline.facts import top_fact_code
from pipeline.gates import hook_gate
from pipeline.models import Candidate
from pipeline.utils.urls import registered_domain

log = logging.getLogger(__name__)

TRACKS = ("web", "content")


@dataclass
class Selection:
    finalists: dict[str, list[Candidate]] = field(default_factory=lambda: {t: [] for t in TRACKS})
    reserves: dict[str, list[Candidate]] = field(default_factory=lambda: {t: [] for t in TRACKS})
    no_hook: list[Candidate] = field(default_factory=list)
    diversity_skips: Counter = field(default_factory=Counter)

    @property
    def all(self) -> list[Candidate]:
        return [c for t in TRACKS for c in self.finalists[t] + self.reserves[t]]


def rank_key(c: Candidate):
    s = c.score
    return (-s.total, -s.breakdown.get("activity", 0), -s.breakdown.get("reputation", 0), -c.review_count, c.place_id)


def qualified(cands: list[Candidate], track: str) -> list[Candidate]:
    return sorted([c for c in cands if not c.gate_codes and c.track == track and c.score and c.score.eligible
                   and c.score.margin >= 0], key=rank_key)


def _brand_key(c: Candidate) -> str:
    return c.name_key or c.name_norm


def _domain_key(c: Candidate) -> str | None:
    if not c.audit or c.audit.site_status in ("none", "social_as_site"):
        return None
    return registered_domain(c.website_url)


def deterministic_finalize(c: Candidate) -> bool:
    return not hook_gate(c)


def select(cands: list[Candidate], cfg, finalize: Callable[[Candidate], bool] = deterministic_finalize) -> Selection:
    """Greedy selection per track. `finalize(c)` runs on each accepted candidate (drafting in M4)
    and returns False if the candidate has no strong fact after all (NO_HOOK)."""
    sel_cfg = cfg.scoring.selection
    out = Selection()
    used_phones: set[str] = set()
    used_brands: set[str] = set()
    used_domains: set[str] = set()

    for track in TRACKS:
        target, n_res = sel_cfg.targets.get(track, 0), sel_cfg.reserves.get(track, 0)
        hook_cap = max(1, int(target * sel_cfg.max_top_hook_share))
        area_count: Counter = Counter()
        hook_count: Counter = Counter()
        for c in qualified(cands, track):
            if len(out.finalists[track]) >= target and len(out.reserves[track]) >= n_res:
                break
            dom = _domain_key(c)
            if (c.phone_e164 and c.phone_e164 in used_phones) or _brand_key(c) in used_brands or \
                    (dom and dom in used_domains):
                out.diversity_skips["shared_phone_brand_or_domain"] += 1
                continue
            as_finalist = len(out.finalists[track]) < target
            if as_finalist:
                hook = top_fact_code(c, cfg)
                if area_count[c.area] >= sel_cfg.max_per_area_per_track:
                    out.diversity_skips["area_cap"] += 1
                    if len(out.reserves[track]) >= n_res:
                        continue
                    as_finalist = False
                elif hook and hook_count[hook] >= hook_cap:
                    out.diversity_skips["top_hook_cap"] += 1
                    if len(out.reserves[track]) >= n_res:
                        continue
                    as_finalist = False
            if not as_finalist and len(out.reserves[track]) >= n_res:
                continue
            if not finalize(c):
                if "NO_HOOK" not in c.gate_codes:
                    c.gate_codes.append("NO_HOOK")
                out.no_hook.append(c)
                continue
            used_brands.add(_brand_key(c))
            if c.phone_e164:
                used_phones.add(c.phone_e164)
            if dom:
                used_domains.add(dom)
            if as_finalist:
                c.selection = "finalist"
                out.finalists[track].append(c)
                area_count[c.area] += 1
                hook_count[top_fact_code(c, cfg)] += 1
            else:
                c.selection = "reserve"
                out.reserves[track].append(c)
        for i, c in enumerate(out.finalists[track] + out.reserves[track], start=1):
            c.rank = i
        log.info("select %s: %d finalists (target %d), %d reserves; skips %s", track, len(out.finalists[track]),
                 target, len(out.reserves[track]), dict(out.diversity_skips))
    return out
