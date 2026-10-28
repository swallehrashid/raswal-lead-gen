"""Discovery via Places API (New) Text Search, with pagination, rotation and budget guard (brief §5.2, §6)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from pipeline.budget import Budget, BudgetExhausted
from pipeline.models import Cell

log = logging.getLogger(__name__)

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"

# Keep EXACTLY this. Adding fields can change the billed SKU (brief §6.1). Snapshot-tested.
FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,places.location,places.types,"
    "places.primaryType,places.businessStatus,places.googleMapsUri,places.nationalPhoneNumber,"
    "places.internationalPhoneNumber,places.websiteUri,places.rating,places.userRatingCount,"
    "places.reviews,nextPageToken"
)


class LivePlacesClient:
    def __init__(self, api_key: str, cfg):
        self._key = api_key
        self._page_size = cfg.budget.places.page_size
        self._http = httpx.Client(timeout=30)

    def request_body(self, query: str, lat: float, lng: float, radius_m: int, page_token: str | None) -> dict:
        body: dict[str, Any] = {
            "textQuery": query,
            "regionCode": "KE",
            "languageCode": "en",
            "pageSize": self._page_size,
            "locationBias": {"circle": {"center": {"latitude": lat, "longitude": lng},
                                        "radius": float(min(radius_m, 50000))}},
        }
        if page_token:
            body["pageToken"] = page_token
        return body

    def search_text(self, query, lat, lng, radius_m, page_token=None):
        # No automatic retry: every attempt is a billed request and must pass the budget guard.
        r = self._http.post(
            PLACES_URL,
            headers={"X-Goog-Api-Key": self._key, "X-Goog-FieldMask": FIELD_MASK, "Content-Type": "application/json"},
            json=self.request_body(query, lat, lng, radius_m, page_token),
        )
        if r.status_code >= 400:
            # Never echo headers (they contain the key); the body is Google's error message.
            log.error("Places API error %s: %s", r.status_code, r.text[:500])
        r.raise_for_status()
        return r.json()

    def place_details(self, place_id: str) -> dict:
        """Place Details (New) — searchText does not return reviews, so fetch them here.
        A separate billed request; the caller must pass the budget guard first."""
        r = self._http.get(
            f"https://places.googleapis.com/v1/places/{place_id}",
            headers={"X-Goog-Api-Key": self._key, "X-Goog-FieldMask": "id,reviews"},
        )
        if r.status_code >= 400:
            log.error("Places details error %s: %s", r.status_code, r.text[:300])
            return {}
        return r.json()


@dataclass
class DiscoveryResult:
    places: dict[str, dict[str, Any]] = field(default_factory=dict)      # place_id → raw place
    cell_of: dict[str, Cell] = field(default_factory=dict)                # place_id → cell that found it
    new_ids: set[str] = field(default_factory=set)
    calls: int = 0
    stopped_reason: str = ""
    cells_run: list[Cell] = field(default_factory=list)


def discover(cfg, plan, places_client, budget: Budget, known_place_ids: set[str], *, now: datetime | None = None,
             sleep=time.sleep) -> DiscoveryResult:
    pb = cfg.budget.places
    res = DiscoveryResult()
    now = now or datetime.now(timezone.utc)
    seen: set[str] = set(known_place_ids)
    for cell in plan.cells:
        if len(res.new_ids) >= pb.target_raw:
            res.stopped_reason = f"target_raw {pb.target_raw} reached"
            break
        area = cfg.areas.by_name(cell.area)
        if area is None:
            log.warning("cell %s: area '%s' not in areas.yaml; skipping", cell.key, cell.area)
            continue
        query = cell.query_template.format(area=area.name)
        token: str | None = None
        cell_total = cell_new = pages = 0
        stop_all = False
        for _page in range(pb.max_pages_per_cell):
            try:
                budget.spend("places")
            except BudgetExhausted as e:
                res.stopped_reason = str(e)
                stop_all = True
                break
            if token:
                sleep(2)   # next_page tokens need a moment to become valid
            try:
                body = places_client.search_text(query, area.lat, area.lng, area.radius_m, token)
            except Exception as e:  # noqa: BLE001  - one bad cell must not kill the night
                log.error("Places call failed for %r in %s: %s", query, area.name, e)
                break
            res.calls += 1
            pages += 1
            page_places = body.get("places", []) or []
            page_new = 0
            for p in page_places:
                pid = p.get("id")
                if not pid:
                    continue
                if pid not in seen:
                    page_new += 1
                    seen.add(pid)
                    res.new_ids.add(pid)
                if pid not in res.places:
                    res.places[pid] = p
                    res.cell_of[pid] = cell
            cell_total += len(page_places)
            cell_new += page_new
            ratio = page_new / len(page_places) if page_places else 0.0
            log.info("places: %r @ %s page %d → %d places, %d new (%.0f%%)", query, area.name, pages,
                     len(page_places), page_new, ratio * 100)
            token = body.get("nextPageToken")
            if not token or ratio < pb.next_page_min_new_ratio or len(res.new_ids) >= pb.target_raw:
                break
        if pages:
            ratio = cell_new / cell_total if cell_total else 0.0
            cell.last_run = now
            cell.pages_fetched += pages
            cell.last_new_ratio = round(ratio, 3)
            cell.exhausted_streak = cell.exhausted_streak + 1 if ratio < pb.exhausted_new_ratio else 0
            cell.exhausted = cell.exhausted_streak >= pb.exhausted_after_runs
            res.cells_run.append(cell)
        if stop_all:
            break
    if not res.stopped_reason:
        res.stopped_reason = "all planned cells done"
    log.info("discovery: %d calls, %d unique places, %d new (%s)", res.calls, len(res.places), len(res.new_ids),
             res.stopped_reason)
    return res
