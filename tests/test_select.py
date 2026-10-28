import copy

from pipeline.facts import build_facts
from pipeline.score import score_candidate
from pipeline.select import select
from tests.helpers import NOW, make


def ready(c, cfg):
    c.facts = build_facts(c, cfg, NOW)
    score_candidate(c, cfg, NOW)
    return c


def small_cfg(cfg, web=4, content=2, reserves=2, per_area=4, hook_share=1.0):
    c = copy.deepcopy(cfg)
    c.scoring.selection.targets = {"web": web, "content": content}
    c.scoring.selection.reserves = {"web": reserves, "content": reserves}
    c.scoring.selection.max_per_area_per_track = per_area
    c.scoring.selection.max_top_hook_share = hook_share
    return c


def dead_leads(cfg, n, area=lambda i: f"Area{i}", **kw):
    return [ready(make(f"Lead {chr(65 + i)} Homes", area=area(i), website=f"http://lead{i}.co.ke/", **kw), cfg)
            for i in range(n)]


def test_targets_and_reserves(cfg):
    c2 = small_cfg(cfg)
    leads = dead_leads(cfg, 8)
    s = select(leads, c2)
    assert len(s.finalists["web"]) == 4 and len(s.reserves["web"]) == 2
    assert [c.rank for c in s.finalists["web"] + s.reserves["web"]] == [1, 2, 3, 4, 5, 6]
    assert all(c.selection == "finalist" for c in s.finalists["web"])


def test_never_pads(cfg):
    c2 = small_cfg(cfg)
    leads = dead_leads(cfg, 3)
    leads.append(ready(make("Low Score Homes", status="none", reviews=9, rating=3.6, newest_days=300), cfg))
    s = select(leads, c2)
    assert len(s.finalists["web"]) == 3 and not s.reserves["web"]   # the low scorer is under 65


def test_threshold(cfg):
    # below both thresholds: weak site (low web pain), has socials (no content gap), generic review (no theme)
    c = ready(make("Under Homes", status="weak", reviews=8, rating=3.5, newest_days=300,
                   social_links={"instagram": "https://instagram.com/x"}, review_texts=["good service"]), cfg)
    assert c.scores["web"].total < cfg.scoring.web.min_score
    assert c.scores["content"].total < cfg.scoring.content.min_score
    assert select([c], cfg).all == []


def test_area_cap(cfg):
    c2 = small_cfg(cfg, web=4, per_area=2, reserves=3)
    leads = dead_leads(cfg, 6, area=lambda i: "Kilimani" if i < 4 else f"Other{i}")
    s = select(leads, c2)
    areas = [c.area for c in s.finalists["web"]]
    assert areas.count("Kilimani") == 2 and len(s.finalists["web"]) == 4
    assert {c.area for c in s.reserves["web"]} == {"Kilimani"}   # overflow goes to reserves


def test_unique_phone_brand_domain(cfg):
    c2 = small_cfg(cfg, web=10)
    a = ready(make("Alpha Homes", phone="+254722000001", website="http://alpha.co.ke/"), cfg)
    same_phone = ready(make("Beta Homes", phone="+254722000001", website="http://beta.co.ke/"), cfg)
    same_brand = ready(make("Alpha Homes", website="http://alpha2.co.ke/"), cfg)
    same_domain = ready(make("Gamma Homes", website="https://www.alpha.co.ke/contact"), cfg)
    other = ready(make("Delta Homes", website="http://delta.co.ke/"), cfg)
    s = select([a, same_phone, same_brand, same_domain, other], c2)
    names = {c.name for c in s.all}
    assert len(s.all) == 2 and "Delta Homes" in names


def test_top_hook_share(cfg):
    c2 = small_cfg(cfg, web=4, reserves=4, hook_share=0.5)
    dead = dead_leads(cfg, 4)                                                           # SITE_DEAD
    social = [ready(make(f"Social {i} Homes", status="social_as_site", website=f"https://facebook.com/s{i}",
                         reviews=60), cfg) for i in range(3)]
    s = select(dead + social, c2)
    from pipeline.facts import top_fact_code
    codes = [top_fact_code(c) for c in s.finalists["web"]]
    assert codes.count("SITE_DEAD") <= 2 and len(s.finalists["web"]) == 4


def test_tie_breakers(cfg):
    c2 = small_cfg(cfg, web=2, reserves=0)
    a = ready(make("Tie A Homes", reviews=60, website="http://a.co.ke/"), cfg)
    b = ready(make("Tie B Homes", reviews=70, website="http://b.co.ke/"), cfg)
    c = ready(make("Tie C Homes", reviews=55, website="http://c.co.ke/"), cfg)
    assert a.score.total == b.score.total == c.score.total
    s = select([a, b, c], c2)
    assert [x.name for x in s.finalists["web"]] == ["Tie B Homes", "Tie A Homes"]   # review count breaks the tie


def test_no_hook_rejected_and_next_one_taken(cfg):
    c2 = small_cfg(cfg, web=1, reserves=0)
    nohook = ready(make("No Hook Homes", status="none", reviews=25, website=None), cfg)   # NO_SITE (medium) only
    hooked = ready(make("Hooked Homes", status="dead", reviews=20, website="http://h.co.ke/"), cfg)
    nohook.scores["web"].total = 99                                                         # force it first
    s = select([nohook, hooked], c2)
    assert s.finalists["web"] == [hooked] and "NO_HOOK" in nohook.gate_codes


def test_content_track_selected_separately(cfg):
    c2 = small_cfg(cfg, web=2, content=2)
    good = [ready(make(f"Good {i} Homes", status="good", reviews=200, website=f"https://g{i}.co.ke/",
                       social_links={}), cfg) for i in range(3)]
    s = select(good + dead_leads(cfg, 2), c2)
    assert len(s.finalists["content"]) == 2 and len(s.finalists["web"]) == 2
