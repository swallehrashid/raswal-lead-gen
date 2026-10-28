"""Hard gates: reason codes for auto-rejection (brief §8). Any code rejects the business."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from pipeline.models import Candidate
from pipeline.utils.text import any_phrase, basic_norm, contains_phrase, remove_phrase
from pipeline.utils.urls import host, host_matches

ORDER = ["NOT_OPERATIONAL", "NO_MOBILE", "SUPPRESSED", "ALREADY_CONTACTED", "PREVIOUSLY_LISTED", "EXCLUDED_TYPE",
         "BUILDING_NOT_BUSINESS", "BIG_BRAND", "PORTAL_OR_CLASSIFIED", "GOV_NGO", "TOO_SMALL", "DORMANT",
         "LOW_RATING", "SCAM_RISK", "NO_HOOK"]


@dataclass
class GateContext:
    suppressed_phones: set[str] = field(default_factory=set)
    suppressed_place_ids: set[str] = field(default_factory=set)
    contacted_phones: set[str] = field(default_factory=set)
    contacted_place_ids: set[str] = field(default_factory=set)
    listed_phones: set[str] = field(default_factory=set)        # previously listed (skipped / recent)
    listed_place_ids: set[str] = field(default_factory=set)


# ---------------------------------------------------------------- predicates (unit-tested)

def building_word(norm: str, excl) -> str | None:
    for w in excl.building_words:
        if contains_phrase(norm, w):
            exceptions = excl.building_word_exceptions.get(w, [])
            if any(contains_phrase(norm, e) for e in exceptions):
                continue
            return w
    return None


def business_word(norm: str, excl) -> str | None:
    return any_phrase(norm, excl.business_words)


def is_building_name(norm: str, excl) -> bool:
    """Name looks like a building/estate and contains no business word."""
    return building_word(norm, excl) is not None and business_word(norm, excl) is None


def not_a_firm(c: Candidate, norm: str, excl) -> bool:
    """Strict rule for the ad verticals: no business word in the name AND a Places type that isn't a firm."""
    return (c.subcategory in excl.strict_subcategories and business_word(norm, excl) is None
            and c.primary_type not in excl.allowed_primary_types)


def brand_match(norm: str, excl) -> str | None:
    """The brand matched, unless the rest of the name has a dealer/stockist word."""
    for brand in excl.brands:
        if contains_phrase(norm, brand):
            rest = remove_phrase(norm, brand)
            if any(contains_phrase(rest, w) for w in excl.dealer_words):
                return None
            return brand
    return None


def portal_match(norm: str, website: str | None, excl) -> str | None:
    if p := any_phrase(norm, excl.portals.names):
        return p
    if website and (d := host_matches(host(website), excl.portals.domains)):
        return d
    return None


def gov_ngo_match(norm: str, excl) -> str | None:
    return any_phrase(norm, excl.gov_ngo_words)


# ---------------------------------------------------------------- gates

def _ids(c: Candidate) -> set[str]:
    return {c.place_id, *c.merged_place_ids}


def cheap_gates(c: Candidate, cfg, ctx: GateContext, now: datetime | None = None) -> list[str]:
    """All gates that don't need enrichment. Returns every code that applies (for stats)."""
    excl, g = cfg.exclusions, cfg.scoring.gates
    sub = cfg.subcategories[c.subcategory]
    now = now or datetime.now(timezone.utc)
    norm = c.name_norm
    codes: list[str] = []
    if c.business_status != "OPERATIONAL":
        codes.append("NOT_OPERATIONAL")
    if not c.phone_e164 or c.phone_type not in g.accepted_phone_types:
        codes.append("NO_MOBILE")
    ids = _ids(c)
    if (c.phone_e164 and c.phone_e164 in ctx.suppressed_phones) or ids & ctx.suppressed_place_ids:
        codes.append("SUPPRESSED")
    if (c.phone_e164 and c.phone_e164 in ctx.contacted_phones) or ids & ctx.contacted_place_ids:
        codes.append("ALREADY_CONTACTED")
    elif (c.phone_e164 and c.phone_e164 in ctx.listed_phones) or ids & ctx.listed_place_ids:
        codes.append("PREVIOUSLY_LISTED")
    if set(c.types) & set(excl.excluded_types) or (c.primary_type in excl.excluded_types):
        codes.append("EXCLUDED_TYPE")
    if is_building_name(norm, excl) or not_a_firm(c, norm, excl):
        codes.append("BUILDING_NOT_BUSINESS")
    if norm in {basic_norm(n) for n in excl.scam_blocklist}:
        codes.append("SCAM_RISK")
    if brand_match(norm, excl):
        codes.append("BIG_BRAND")
    if portal_match(norm, c.website_url, excl):
        codes.append("PORTAL_OR_CLASSIFIED")
    if gov_ngo_match(norm, excl):
        codes.append("GOV_NGO")
    if c.review_count < sub.min_reviews:
        codes.append("TOO_SMALL")
    # Places API (New) searchText does NOT return the reviews array (only rating +
    # userRatingCount), so newest_review_at is None for every live lead. Unknown recency
    # must not mean "dormant" — only reject when we actually have an old newest review.
    newest = c.newest_review_at
    if newest is not None and newest < now - timedelta(days=g.dormant_days):
        codes.append("DORMANT")
    if c.rating is None or c.rating < g.min_rating:
        codes.append("LOW_RATING")
    return codes


def hook_gate(c: Candidate) -> list[str]:
    """NO_HOOK: no true fact at all to open the message with (evaluated last). Any strength will do:
    the ads pitch is the offer, the fact is just a polite, specific opener."""
    return [] if c.facts_for("ads") else ["NO_HOOK"]


def name_is_business_like(name: str, excl) -> int:
    """Higher = more business-like (used to pick the name of a collapsed shared-phone group)."""
    norm = basic_norm(name)
    score = 0
    if business_word(norm, excl):
        score += 2
    if not building_word(norm, excl):
        score += 1
    return score
