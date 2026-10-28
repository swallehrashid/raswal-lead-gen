from datetime import datetime, timedelta, timezone

import pytest

from pipeline.gates import GateContext, brand_match, cheap_gates, is_building_name, portal_match
from pipeline.models import Candidate, Review
from pipeline.utils.text import name_norm

NOW = datetime(2026, 10, 11, 18, 30, tzinfo=timezone.utc)


def cand(name="Kilima Homes", **kw) -> Candidate:
    defaults = dict(place_id="p1", name=name, name_norm=name_norm(name), subcategory="property_agency",
                    types=["real_estate_agency"], primary_type="real_estate_agency", address="", lat=-1.29, lng=36.78,
                    maps_url="", business_status="OPERATIONAL", phone_raw="0722 123456", phone_e164="+254722123456",
                    phone_type="MOBILE", website_url=None, rating=4.6, review_count=40,
                    reviews=[Review(1, 5, "Great", "A B", NOW - timedelta(days=10))], area="Kilimani")
    defaults.update(kw)
    return Candidate(**defaults)


@pytest.mark.parametrize("name,building", [
    ("Kilimani Heights Apartments", True),
    ("Lenana Court", True),
    ("Sunrise Villas", True),
    ("Woodlands Residency", True),
    ("Westpark Towers", True),
    ("Garden Estate", True),
    ("Riverside Suites", True),
    ("Greenspan Mall", True),
    ("Kilima Homes", False),
    ("Riverside Gardens Ltd", False),             # business word: ltd
    ("Jumuia Estate Agents", False),              # estate + agents
    ("Heights Properties", False),                # business word: properties
    ("Mlimani Real Estate", False),               # real estate is a business
    ("Court View Construction", False),
    ("Plaza Hardware", False),
])
def test_building_name_gate(cfg, name, building):
    assert is_building_name(name_norm(name), cfg.exclusions) is building


@pytest.mark.parametrize("name,brand", [
    ("Knight Frank Kenya", "knight frank"),
    ("HassConsult Real Estate", "hassconsult"),
    ("Crown Paints Kenya", "crown paints"),
    ("Tile & Carpet Centre", "tile and carpet centre"),  # "centre" is part of the brand, not a dealer word
    ("Mabati Rolling Mills", "mabati rolling mills"),
    ("Crown Paints Dealer Githurai", None),          # dealer exception
    ("Safal MRM Stockist Githurai", None),
    ("Basco Paints Depot Kahawa", None),
    ("Mabati Bora Roofing", None),                   # 'mabati' alone is not the brand
    ("Optiven Group", "optiven"),
])
def test_brand_gate_with_dealer_exceptions(cfg, name, brand):
    assert brand_match(name_norm(name), cfg.exclusions) == brand


def test_tile_and_carpet_centre_plus_area_is_still_brand(cfg):
    assert brand_match(name_norm("Tile and Carpet Centre Westlands"), cfg.exclusions) == "tile and carpet centre"


def test_portal_by_name_and_domain(cfg):
    assert portal_match(name_norm("BuyRentKenya Office"), None, cfg.exclusions)
    assert portal_match(name_norm("Some Agency"), "https://www.jiji.co.ke/x", cfg.exclusions)
    assert portal_match(name_norm("Kilima Homes"), "https://kilimahomes.co.ke", cfg.exclusions) is None


def test_clean_candidate_passes(cfg):
    assert cheap_gates(cand(), cfg, GateContext(), NOW) == []


@pytest.mark.parametrize("kw,code", [
    (dict(business_status="CLOSED_PERMANENTLY"), "NOT_OPERATIONAL"),
    (dict(phone_e164="+254202345678", phone_type="FIXED_LINE"), "NO_MOBILE"),
    (dict(phone_e164=None, phone_type=None), "NO_MOBILE"),
    (dict(types=["apartment_building"]), "EXCLUDED_TYPE"),
    (dict(types=["lodging", "hotel"]), "EXCLUDED_TYPE"),
    (dict(name="Lenana Court", name_norm="lenana court"), "BUILDING_NOT_BUSINESS"),
    (dict(name="Knight Frank Kenya", name_norm="knight frank kenya"), "BIG_BRAND"),
    (dict(name="Nairobi County Housing", name_norm="nairobi county housing"), "GOV_NGO"),
    (dict(review_count=4), "TOO_SMALL"),
    (dict(reviews=[Review(1, 5, "x", "A", NOW - timedelta(days=400))]), "DORMANT"),
    (dict(rating=3.4), "LOW_RATING"),
])
def test_each_gate(cfg, kw, code):
    assert code in cheap_gates(cand(**kw), cfg, GateContext(), NOW)


def test_hardware_needs_ten_reviews(cfg):
    c = cand(name="Mwangaza Hardware", name_norm="mwangaza hardware", subcategory="hardware_supplies", review_count=9)
    assert "TOO_SMALL" in cheap_gates(c, cfg, GateContext(), NOW)
    c.review_count = 10
    assert "TOO_SMALL" not in cheap_gates(c, cfg, GateContext(), NOW)


def test_suppression_contacted_and_listed(cfg):
    ctx = GateContext(suppressed_phones={"+254722123456"})
    assert "SUPPRESSED" in cheap_gates(cand(), cfg, ctx, NOW)
    ctx = GateContext(suppressed_place_ids={"merged"})
    assert "SUPPRESSED" in cheap_gates(cand(merged_place_ids=["merged"]), cfg, ctx, NOW)
    ctx = GateContext(contacted_phones={"+254722123456"})
    assert "ALREADY_CONTACTED" in cheap_gates(cand(), cfg, ctx, NOW)
    ctx = GateContext(listed_place_ids={"p1"})
    assert "PREVIOUSLY_LISTED" in cheap_gates(cand(), cfg, ctx, NOW)


# ---------------------------------------------------------------- ads pivot: stricter estate / building filter

CENSUS_LEAKS = [
    ("Phenom Park", "service"),
    ("Five Star Paradise Runda", "service"),
    ("Ineza Runda Gate A", "service"),
    ("Westlands Business Park", "service"),
    ("The Cycads", "service"),
    ("Kwa Wangari", "service"),
    ("Mbandu Complex", "service"),
    ("PrestigeHomes Bnb", "service"),
]
LEGIT = [
    ("Kenya Homes", "real_estate_agency"),
    ("Fanaka Real Estate", "real_estate_agency"),
    ("Kings Developers", "service"),
    ("Username Properties", "real_estate_agency"),
    ("LM Realtors", "real_estate_agency"),
    ("Coral Property International", "consultant"),
]


@pytest.mark.parametrize("sub", ["land_developers", "property_agency"])
@pytest.mark.parametrize("name,ptype", CENSUS_LEAKS)
def test_census_leaks_are_rejected(cfg, sub, name, ptype):
    c = cand(name, subcategory=sub, primary_type=ptype, types=[ptype])
    assert "BUILDING_NOT_BUSINESS" in cheap_gates(c, cfg, GateContext(), NOW)


@pytest.mark.parametrize("sub", ["land_developers", "property_agency"])
@pytest.mark.parametrize("name,ptype", LEGIT)
def test_legit_firms_pass_the_estate_filter(cfg, sub, name, ptype):
    c = cand(name, subcategory=sub, primary_type=ptype, types=[ptype])
    assert "BUILDING_NOT_BUSINESS" not in cheap_gates(c, cfg, GateContext(), NOW)


def test_strict_rule_only_applies_to_the_ad_verticals(cfg):
    c = cand("Kwa Wangari", subcategory="hardware_supplies", primary_type="service", types=["service"])
    assert "BUILDING_NOT_BUSINESS" not in cheap_gates(c, cfg, GateContext(), NOW)


def test_blocklisted_name_is_scam_risk(cfg):
    import copy
    c2 = copy.deepcopy(cfg)
    c2.exclusions.scam_blocklist = ["Bad Plots Ltd"]
    c = cand("Bad Plots Ltd", subcategory="land_developers")
    assert "SCAM_RISK" in cheap_gates(c, c2, GateContext(), NOW)
    assert "SCAM_RISK" not in cheap_gates(cand("Good Plots Ltd", subcategory="land_developers"), c2, GateContext(), NOW)


FIRM_NAMES = ["Emmaus Affordable Homes and Property", "Mapema luxury homes", "Pearl Housing Co-op", "Zuri Developments"]


@pytest.mark.parametrize("name", FIRM_NAMES)
def test_firms_named_with_homes_property_or_development_are_not_buildings(cfg, name):
    c = cand(name, subcategory="land_developers", primary_type="service", types=["service"])
    assert "BUILDING_NOT_BUSINESS" not in cheap_gates(c, cfg, GateContext(), NOW)
