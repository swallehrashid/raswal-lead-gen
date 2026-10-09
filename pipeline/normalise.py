"""Turn raw Places results into candidates: phones, names, areas, dedupe, branches, shared phones (brief §7)."""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import datetime
from typing import Any

import phonenumbers
from dateutil import parser as dtparser
from phonenumbers import PhoneNumberType
from rapidfuzz import fuzz

from pipeline.gates import is_building_name, name_is_business_like
from pipeline.models import Candidate, Cell, Review
from pipeline.utils.text import display_name, name_key, name_norm

log = logging.getLogger(__name__)

_TYPE_NAMES = {v: k for k, v in vars(PhoneNumberType).items() if isinstance(v, int)}


def parse_phone(national: str | None, international: str | None) -> tuple[str | None, str | None]:
    """→ (E.164, phonenumbers type name). Invalid or missing → (None, None)."""
    for raw in (international, national):
        if not raw:
            continue
        try:
            num = phonenumbers.parse(raw, "KE")
        except phonenumbers.NumberParseException:
            continue
        if not phonenumbers.is_valid_number(num):
            continue
        e164 = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
        return e164, _TYPE_NAMES.get(phonenumbers.number_type(num), "UNKNOWN")
    return None, None


def phone_display(e164: str | None) -> str:
    """+254722123456 → 0722 123 456 (how Kenyans write it; used on teasers)."""
    if not e164:
        return ""
    try:
        num = phonenumbers.parse(e164, "KE")
        return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.NATIONAL)
    except phonenumbers.NumberParseException:
        return e164


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def assign_area(cfg, lat: float | None, lng: float | None, fallback: str, area_set: str | None = None):
    """Nearest area centre (within assign_max_km) among this subcategory's areas."""
    pool = [a for a in cfg.areas.areas if area_set is None or a.tier > 1 or area_set in a.sets]
    if lat is not None and lng is not None and pool:
        best = min(pool, key=lambda a: haversine_km((lat, lng), (a.lat, a.lng)))
        if haversine_km((lat, lng), (best.lat, best.lng)) <= cfg.areas.assign_max_km:
            return best
    return cfg.areas.by_name(fallback)


def _parse_time(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return dtparser.isoparse(s)
    except (ValueError, OverflowError):
        return None


def parse_reviews(raw: list[dict[str, Any]] | None) -> list[Review]:
    out = []
    for i, r in enumerate(raw or [], start=1):
        text = ((r.get("text") or {}).get("text") or (r.get("originalText") or {}).get("text") or "").strip()
        out.append(Review(index=i, rating=r.get("rating"), text=text,
                          author=((r.get("authorAttribution") or {}).get("displayName") or "").strip(),
                          publish_time=_parse_time(r.get("publishTime"))))
    return out


def to_candidate(raw: dict[str, Any], cell: Cell | None, cfg, subcategory: str) -> Candidate:
    name = ((raw.get("displayName") or {}).get("text") or "").strip()
    loc = raw.get("location") or {}
    lat, lng = loc.get("latitude"), loc.get("longitude")
    e164, ptype = parse_phone(raw.get("nationalPhoneNumber"), raw.get("internationalPhoneNumber"))
    area = assign_area(cfg, lat, lng, cell.area if cell else "", cfg.subcategories[subcategory].area_set)
    area_names = [a.name for a in cfg.areas.areas]
    norm = name_norm(name)
    return Candidate(
        place_id=raw["id"], name=name, name_norm=norm, subcategory=subcategory,
        types=list(raw.get("types") or []), primary_type=raw.get("primaryType"),
        address=raw.get("formattedAddress"), lat=lat, lng=lng, maps_url=raw.get("googleMapsUri"),
        business_status=raw.get("businessStatus"),
        phone_raw=raw.get("nationalPhoneNumber") or raw.get("internationalPhoneNumber"),
        phone_e164=e164, phone_type=ptype, website_url=raw.get("websiteUri"),
        rating=raw.get("rating"), review_count=int(raw.get("userRatingCount") or 0),
        reviews=parse_reviews(raw.get("reviews")),
        area=area.name if area else (cell.area if cell else ""),
        area_tier=area.tier if area else None, area_flags=list(area.flags) if area else [],
        cell_key=cell.key if cell else None, name_key=name_key(norm, area_names), display_name=display_name(name),
        raw=raw,
    )


def _is_buildingish(c: Candidate, excl) -> bool:
    return is_building_name(c.name_norm, excl) or bool(set(c.types) & set(excl.building_types))


def _merge_into(keep: Candidate, others: list[Candidate]) -> None:
    for o in others:
        keep.merged_place_ids += [o.place_id, *o.merged_place_ids]


def collapse_shared_phones(cands: list[Candidate], cfg) -> list[Candidate]:
    """§7.3 (by phone) + §7.5: one lead per mobile number.

    A number on ≥ shared_phone_min_listings building-like listings is an agent/manager:
    keep the most business-like name and set manages_listings.
    """
    excl = cfg.exclusions
    by_phone: dict[str, list[Candidate]] = defaultdict(list)
    out: list[Candidate] = []
    for c in cands:
        if c.phone_e164:
            by_phone[c.phone_e164].append(c)
        else:
            out.append(c)
    for _phone, group in by_phone.items():
        if len(group) == 1:
            out.append(group[0])
            continue
        buildings = [c for c in group if _is_buildingish(c, excl)]
        if len(buildings) >= cfg.scoring.dedupe.shared_phone_min_listings:
            keep = max(group, key=lambda c: (name_is_business_like(c.name, excl), c.review_count))
            keep.manages_listings = len(buildings)
        else:
            keep = max(group, key=lambda c: c.review_count)
        _merge_into(keep, [c for c in group if c is not keep])
        out.append(keep)
    return out


def dedupe_near_names(cands: list[Candidate], cfg) -> list[Candidate]:
    """§7.3 step 3: rapidfuzz ratio ≥ threshold within N km → keep the listing with more reviews."""
    d = cfg.scoring.dedupe
    cands = sorted(cands, key=lambda c: -c.review_count)
    kept: list[Candidate] = []
    for c in cands:
        dup_of = None
        for k in kept:
            if None in (c.lat, c.lng, k.lat, k.lng):
                continue
            if fuzz.ratio(c.name_key or c.name_norm, k.name_key or k.name_norm) >= d.near_duplicate_ratio and \
                    haversine_km((c.lat, c.lng), (k.lat, k.lng)) <= d.near_duplicate_km:
                dup_of = k
                break
        if dup_of:
            _merge_into(dup_of, [c])
        else:
            kept.append(c)
    return kept


def _locations(group: list[Candidate], km: float) -> int:
    """Number of distinct locations (listings more than `km` apart)."""
    centres: list[tuple[float, float]] = []
    for c in group:
        if c.lat is None or c.lng is None:
            continue
        if all(haversine_km((c.lat, c.lng), p) > km for p in centres):
            centres.append((c.lat, c.lng))
    return max(1, len(centres))


def detect_branches(cands: list[Candidate], cfg) -> list[Candidate]:
    """§7.4: the same brand key at different locations is one multi-branch business."""
    groups: dict[str, list[Candidate]] = defaultdict(list)
    for c in cands:
        groups[c.name_key or c.name_norm].append(c)
    out = []
    for _key, group in groups.items():
        keep = max(group, key=lambda c: c.review_count)
        if len(group) > 1:
            keep.branch_count = _locations(group, cfg.scoring.dedupe.near_duplicate_km)
            _merge_into(keep, [c for c in group if c is not keep])
        out.append(keep)
    return out


def normalise(places: dict[str, dict], cell_of: dict[str, Cell], cfg, subcategory: str) -> list[Candidate]:
    cands = [to_candidate(raw, cell_of.get(pid), cfg, subcategory) for pid, raw in places.items()]
    n0 = len(cands)
    cands = collapse_shared_phones(cands, cfg)
    n1 = len(cands)
    cands = dedupe_near_names(cands, cfg)
    n2 = len(cands)
    cands = detect_branches(cands, cfg)
    log.info("normalise: %d places → %d after phone dedupe → %d after near-duplicates → %d after branches",
             n0, n1, n2, len(cands))
    return cands
