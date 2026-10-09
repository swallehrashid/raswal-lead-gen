import copy
import json

from pipeline.models import Cell
from pipeline.normalise import normalise
from pipeline.settings import FIXTURES_DIR
from pipeline.utils.text import display_name, name_key, name_norm, slugify

CELL = Cell("property_agency", "real estate agency in {area}", "Kileleshwa", 1)


def raw(pid, name, phone="0722 111222", lat=-1.281, lng=36.779, reviews=20, types=("real_estate_agency",)):
    return {"id": pid, "displayName": {"text": name}, "location": {"latitude": lat, "longitude": lng},
            "types": list(types), "businessStatus": "OPERATIONAL", "nationalPhoneNumber": phone,
            "userRatingCount": reviews, "rating": 4.5}


def run(cfg, places):
    d = {p["id"]: p for p in places}
    return normalise(d, {k: CELL for k in d}, cfg, "property_agency")


def test_name_norm_collapses_legal_suffixes():
    assert name_norm("Kilima Homes Co. Ltd") == "kilima homes ltd"
    assert name_norm("KILIMA HOMES LIMITED") == "kilima homes ltd"
    assert name_norm("Kijani Homes & Lettings") == "kijani homes and lettings"
    assert name_key("makazi realtors westlands ltd", ["Westlands"]) == "makazi realtors"


def test_display_name_and_slug():
    assert display_name("KILIMA HOMES LIMITED") == "Kilima Homes"
    assert display_name("JKL BUILDERS LTD") == "JKL Builders"
    assert display_name("Baraka Properties Ltd") == "Baraka Properties"
    assert display_name("Gauge 30 Roofing Ltd") == "Gauge 30 Roofing"
    assert slugify("kijani homes and lettings ltd") == "kijani-homes-and-lettings"
    assert len(slugify("a very long business name that keeps going and going")) <= 30


def test_same_phone_keeps_most_reviews(cfg):
    out = run(cfg, [raw("a", "Kito Realtors", reviews=10), raw("b", "Kito Realtors Office", reviews=50, lat=-1.30)])
    assert len(out) == 1 and out[0].place_id == "b" and "a" in out[0].merged_place_ids


def test_shared_phone_collapses_buildings_into_agent(cfg):
    p = "0721 908877"
    out = run(cfg, [raw("b1", "Amani Gardens Apartments", p, types=("apartment_building",)),
                    raw("b2", "Kileleshwa Court", p), raw("b3", "Othaya Road Suites", p), raw("b4", "Mandera Heights", p),
                    raw("ag", "Kipande Property Managers", p, reviews=36)])
    assert len(out) == 1
    lead = out[0]
    assert lead.name == "Kipande Property Managers"
    assert lead.manages_listings == 4
    assert set(lead.merged_place_ids) == {"b1", "b2", "b3", "b4"}


def test_two_buildings_sharing_a_phone_are_not_an_agent(cfg):
    out = run(cfg, [raw("b1", "Kileleshwa Court", "0721 000001"), raw("b2", "Mandera Heights", "0721 000001", reviews=30)])
    assert len(out) == 1 and out[0].manages_listings == 0


def test_near_duplicate_within_2km(cfg):
    out = run(cfg, [raw("a", "Kilima Homes", "0722 000001", reviews=62),
                    raw("b", "Kilima Homes Ltd", "0733 000002", reviews=9, lat=-1.284, lng=36.781)])
    assert len(out) == 1 and out[0].place_id == "a" and out[0].branch_count == 1


def test_branches_far_apart(cfg):
    out = run(cfg, [raw("w", "Makazi Realtors Westlands", "0722 000003", lat=-1.2676, lng=36.8108, reviews=64),
                    raw("k", "Makazi Realtors Karen", "0733 000004", lat=-1.3197, lng=36.7073, reviews=41)])
    assert len(out) == 1 and out[0].place_id == "w" and out[0].branch_count == 2


def test_fixture_property_agency_has_80_candidates(cfg):
    places = {}
    for f in sorted((FIXTURES_DIR / "places").glob("property_agency_*.json")):
        for p in json.loads(f.read_text())["places"]:
            places.setdefault(p["id"], copy.deepcopy(p))
    assert len(places) >= 80
