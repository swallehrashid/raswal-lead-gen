import copy

from pipeline.facts import build_facts
from pipeline.score import score_candidate
from pipeline.select import select
from tests.helpers import NOW, make


def ready(c, cfg):
    c.facts = build_facts(c, cfg, NOW)
    score_candidate(c, cfg, NOW)
    return c


def small_cfg(cfg, agency=4, land=2, reserves=2, per_area=4, angle_share=1.0):
    c = copy.deepcopy(cfg)
    s = c.scoring.selection
    s.daily_mix = {"property_agency": agency, "land_developers": land}
    s.reserves = {"property_agency": reserves, "land_developers": reserves}
    s.max_per_area_per_subcategory = per_area
    s.max_angle_share = angle_share
    return c


def leads(cfg, n, area=lambda i: f"Area{i}", sub="property_agency", **kw):
    return [ready(make(f"Lead {chr(65 + i)} Homes {sub[:2]}", sub=sub, area=area(i), website=f"http://lead{i}{sub[:2]}.co.ke/",
                       **kw), cfg) for i in range(n)]


def test_targets_and_reserves(cfg):
    c2 = small_cfg(cfg)
    s = select(leads(cfg, 8), c2)
    assert len(s.finalists["property_agency"]) == 4 and len(s.reserves["property_agency"]) == 2
    assert [c.rank for c in s.finalists["property_agency"] + s.reserves["property_agency"]] == [1, 2, 3, 4, 5, 6]
    assert all(c.selection == "finalist" for c in s.finalists["property_agency"])


def test_each_subcategory_is_selected_separately(cfg):
    c2 = small_cfg(cfg, agency=2, land=3, reserves=0)
    pool = leads(cfg, 4) + leads(cfg, 5, sub="land_developers")
    s = select(pool, c2)
    assert len(s.finalists["property_agency"]) == 2 and len(s.finalists["land_developers"]) == 3
    assert {c.subcategory for c in s.finalists["land_developers"]} == {"land_developers"}


def test_explicit_mix_overrides_config(cfg):
    s = select(leads(cfg, 5), cfg, mix={"property_agency": 3})
    assert len(s.finalists["property_agency"]) == 3 and "land_developers" not in s.finalists


def test_never_pads(cfg):
    c2 = small_cfg(cfg)
    pool = leads(cfg, 3)
    pool.append(ready(make("Low Score Homes", status="none", reviews=9, rating=3.6, newest_days=300), cfg))
    s = select(pool, c2)
    assert len(s.finalists["property_agency"]) == 3 and not s.reserves["property_agency"]   # the low scorer is under 35


def test_threshold(cfg):
    c = ready(make("Under Homes", status="none", reviews=8, rating=3.5, newest_days=300), cfg)
    assert c.scores["ads"].total < cfg.scoring.ads.min_score
    assert select([c], cfg).all == []


def test_area_cap(cfg):
    c2 = small_cfg(cfg, agency=4, per_area=2, reserves=3)
    pool = leads(cfg, 6, area=lambda i: "Kilimani" if i < 4 else f"Other{i}")
    s = select(pool, c2)
    areas = [c.area for c in s.finalists["property_agency"]]
    assert areas.count("Kilimani") == 2 and len(s.finalists["property_agency"]) == 4
    assert {c.area for c in s.reserves["property_agency"]} == {"Kilimani"}   # overflow goes to reserves


def test_unique_phone_brand_domain_across_subcategories(cfg):
    c2 = small_cfg(cfg, agency=10, land=10)
    a = ready(make("Alpha Homes", phone="+254722000001", website="http://alpha.co.ke/"), cfg)
    same_phone = ready(make("Beta Homes", sub="land_developers", phone="+254722000001", website="http://beta.co.ke/"), cfg)
    same_brand = ready(make("Alpha Homes", website="http://alpha2.co.ke/"), cfg)
    same_domain = ready(make("Gamma Homes", website="https://www.alpha.co.ke/contact"), cfg)
    other = ready(make("Delta Homes", website="http://delta.co.ke/"), cfg)
    s = select([a, same_phone, same_brand, same_domain, other], c2)
    assert len(s.all) == 2 and {c.name for c in s.all} == {"Alpha Homes", "Delta Homes"}


def test_angle_cap_is_soft(cfg):
    c2 = small_cfg(cfg, agency=4, reserves=0, angle_share=0.5)          # at most 2 of one angle...
    a = leads(cfg, 3, status="good")                                    # angle A
    c = [ready(make(f"Dead {i} Homes", status="dead", website=f"http://d{i}.co.ke/", reviews=20), cfg) for i in range(2)]
    s = select(a + c, c2)
    angles = sorted(x.angle for x in s.finalists["property_agency"])
    assert angles == ["A", "A", "C", "C"]
    # ...but with no alternatives the list is still filled
    s = select(leads(cfg, 4, status="good"), c2)
    assert len(s.finalists["property_agency"]) == 4


def test_tie_breakers(cfg):
    c2 = small_cfg(cfg, agency=2, reserves=0)
    a = ready(make("Tie A Homes", reviews=60, website="http://a.co.ke/"), cfg)
    b = ready(make("Tie B Homes", reviews=70, website="http://b.co.ke/"), cfg)
    c = ready(make("Tie C Homes", reviews=55, website="http://c.co.ke/"), cfg)
    assert a.score.total == b.score.total == c.score.total
    s = select([a, b, c], c2)
    assert [x.name for x in s.finalists["property_agency"]] == ["Tie B Homes", "Tie A Homes"]   # reviews break the tie


def test_no_hook_rejected_and_next_one_taken(cfg):
    c2 = small_cfg(cfg, agency=1, reserves=0)
    nohook = ready(make("No Hook Homes", reviews=25, website="http://nh.co.ke/"), cfg)
    nohook.facts = []                                                         # nothing true to open with
    hooked = ready(make("Hooked Homes", reviews=20, website="http://h.co.ke/"), cfg)
    nohook.scores["ads"].total = 99                                           # force it first
    s = select([nohook, hooked], c2)
    assert s.finalists["property_agency"] == [hooked] and "NO_HOOK" in nohook.gate_codes
