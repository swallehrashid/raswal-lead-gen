"""Scam check on Place Details reviews (ads pivot). A scam-adjacent business must never get an outreach
message that puts Raswal's name next to it.

hard (review rated <= 2 with a hard term)  → SCAM_RISK gate, excluded
soft (review rated <= 3 with a soft term)  → score penalty and a red chip in the dashboard
"""

from __future__ import annotations

import re

from pipeline.models import Candidate

HARD_MAX_RATING = 2
SOFT_MAX_RATING = 3


def _compile(terms: list[str]) -> list[tuple[str, re.Pattern]]:
    return [(t, re.compile(rf"(?<![a-z0-9]){re.escape(t.lower())}(?![a-z0-9])")) for t in terms]


def scam_check(c: Candidate, cfg) -> None:
    """Sets c.scam_flag ('hard' | 'soft' | None) and c.scam_terms from the reviews we have."""
    hard, soft = _compile(cfg.exclusions.scam_terms.get("hard", [])), _compile(cfg.exclusions.scam_terms.get("soft", []))
    hard_hits: set[str] = set()
    soft_hits: set[str] = set()
    for r in c.reviews:
        text = (r.text or "").lower()
        if not text or r.rating is None:
            continue
        if r.rating <= HARD_MAX_RATING:
            hard_hits |= {t for t, rx in hard if rx.search(text)}
        if r.rating <= SOFT_MAX_RATING:
            soft_hits |= {t for t, rx in soft if rx.search(text)}
    if hard_hits:
        c.scam_flag, c.scam_terms = "hard", sorted(hard_hits)
        if "SCAM_RISK" not in c.gate_codes:
            c.gate_codes.append("SCAM_RISK")
    elif soft_hits:
        c.scam_flag, c.scam_terms = "soft", sorted(soft_hits)
    else:
        c.scam_flag, c.scam_terms = None, []
