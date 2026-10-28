from datetime import date, datetime, timezone

import pytest

from pipeline.budget import Budget, BudgetExhausted, Cap
from pipeline.discover import FIELD_MASK, LivePlacesClient, discover
from pipeline.fakes import FixturePlaces
from pipeline.models import Cell
from pipeline.plan import make_day_plan, order_cells
from pipeline.store import MemoryStore


def test_field_mask_snapshot():
    """Changing the field mask can change the billed SKU (brief §6.1). Update only deliberately."""
    assert FIELD_MASK == (
        "places.id,places.displayName,places.formattedAddress,places.location,places.types,"
        "places.primaryType,places.businessStatus,places.googleMapsUri,places.nationalPhoneNumber,"
        "places.internationalPhoneNumber,places.websiteUri,places.rating,places.userRatingCount,"
        "places.reviews,nextPageToken"
    )


def test_request_body(cfg):
    body = LivePlacesClient("k", cfg).request_body("hardware shop Ruiru", -1.14, 36.96, 4000, "tok")
    assert body == {"textQuery": "hardware shop Ruiru", "regionCode": "KE", "languageCode": "en", "pageSize": 20,
                    "locationBias": {"circle": {"center": {"latitude": -1.14, "longitude": 36.96}, "radius": 4000.0}},
                    "pageToken": "tok"}


def test_live_client_sends_key_and_mask_headers(cfg):
    import httpx
    import respx
    with respx.mock(assert_all_called=True) as m:
        route = m.post("https://places.googleapis.com/v1/places:searchText").mock(
            return_value=httpx.Response(200, json={"places": []}))
        LivePlacesClient("KEY123", cfg).search_text("q", 0, 0, 100)
        req = route.calls.last.request
        assert req.headers["X-Goog-Api-Key"] == "KEY123"
        assert req.headers["X-Goog-FieldMask"] == FIELD_MASK


def _budget(night=40, month_used=0, month_cap=900):
    return Budget(caps={"places": Cap(night, month_cap)}, month_used={"places": month_used}, month="2026-10")


def test_budget_guard_nightly_and_monthly():
    b = _budget(night=2)
    b.spend("places"); b.spend("places")
    with pytest.raises(BudgetExhausted, match="nightly"):
        b.spend("places")
    b = _budget(month_used=900)
    with pytest.raises(BudgetExhausted, match="monthly"):
        b.spend("places")


def test_dry_run_defaults_to_5_calls_and_override_cannot_exceed_nightly(cfg):
    s = MemoryStore()
    assert Budget.from_config(cfg, s, date(2026, 10, 12), dry_run=True).caps["places"].per_night == 5
    assert Budget.from_config(cfg, s, date(2026, 10, 12), dry_run=True, places_override=10).caps["places"].per_night == 10
    assert Budget.from_config(cfg, s, date(2026, 10, 12), places_override=500).caps["places"].per_night == 40


def test_budget_records_usage(cfg):
    s = MemoryStore()
    b = Budget.from_config(cfg, s, date(2026, 10, 12))
    b.spend("places"); b.spend("gemini")
    assert s.get_usage("2026-10", "places") == 1 and s.get_usage("2026-10", "gemini") == 1


def _plan(cfg, sub="property_agency"):
    return make_day_plan(cfg, MemoryStore(), list_date=date(2026, 10, 12), subcategory=sub).plans[0]


def test_discovery_stops_at_cap_and_paginates(cfg):
    plan = _plan(cfg)
    fake = FixturePlaces("property_agency")
    res = discover(cfg, plan, fake, _budget(night=5), set(), sleep=lambda s: None)
    assert res.calls == 5 and "nightly cap" in res.stopped_reason
    assert len(res.places) >= 80
    assert [c["page_token"] is not None for c in fake.calls] == [False, True, True, False, True]


def test_next_page_only_when_new_ratio_high(cfg):
    plan = _plan(cfg)
    fake = FixturePlaces("property_agency")
    first = fake._load("property_agency_c1_p1")
    known = {p["id"] for p in first["places"]}      # page 1 entirely known → ratio 0 → no page 2
    fake = FixturePlaces("property_agency")
    res = discover(cfg, plan, fake, _budget(night=2), known, sleep=lambda s: None)
    assert fake.calls[1]["page_token"] is None
    assert res.cells_run[0].last_new_ratio == 0 and res.cells_run[0].exhausted_streak == 1


def test_cell_exhaustion_after_two_low_runs(cfg):
    plan = _plan(cfg)
    first = FixturePlaces("property_agency")._load("property_agency_c1_p1")
    known = {p["id"] for p in first["places"]}
    cell = plan.cells[0]
    cell.exhausted_streak = 1
    plan.cells = [cell]
    discover(cfg, plan, FixturePlaces("property_agency"), _budget(night=1), known, sleep=lambda s: None)
    assert cell.exhausted


def test_tier_progression(cfg):
    sub = cfg.subcategories["property_agency"]
    t = datetime(2026, 10, 1, tzinfo=timezone.utc)
    cells = [Cell("property_agency", "q", "A", 1, last_run=t), Cell("property_agency", "q", "B", 1),
             Cell("property_agency", "q", "C", 2)]
    ordered = order_cells(cfg, sub, cells)
    assert [c.area for c in ordered] == ["B", "A"]           # never-run first; tier 2 not yet
    for c in cells[:2]:
        c.exhausted = True
    assert [c.area for c in order_cells(cfg, sub, cells)][-1] == "C"


def test_day_plan_skips_holiday_and_plans_both_active_subcategories(cfg):
    d = make_day_plan(cfg, MemoryStore(), list_date=date(2026, 10, 20))
    assert "Mashujaa" in d.skip_reason and d.plans == []
    d = make_day_plan(cfg, MemoryStore(), list_date=date(2026, 10, 12))
    assert [p.subcategory.key for p in d.plans] == ["property_agency", "land_developers"]
    assert all(p.cells and all(c.tier == 1 for c in p.cells) for p in d.plans)


def test_paused_verticals_are_never_planned(cfg):
    d = make_day_plan(cfg, MemoryStore(), list_date=date(2026, 10, 12))
    assert not {"construction", "hardware_supplies", "roofing_steel"} & {p.subcategory.key for p in d.plans}


def test_discovery_respects_per_subcategory_call_share(cfg):
    plan = _plan(cfg)
    res = discover(cfg, plan, FixturePlaces("property_agency"), _budget(night=40), set(), sleep=lambda s: None,
                   max_calls=3)
    assert res.calls == 3 and "share" in res.stopped_reason
