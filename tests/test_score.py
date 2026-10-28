import pytest

from pipeline.facts import build_facts
from pipeline.score import ability_points, content_score, review_points, score_candidate, web_score
from tests.helpers import NOW, make


@pytest.mark.parametrize("n,pts", [(7, 0), (8, 8), (19, 8), (20, 14), (49, 14), (50, 20), (149, 20), (150, 25),
                                   (400, 25), (401, 15), (2000, 15)])
def test_review_bands(cfg, n, pts):
    assert review_points(n, cfg) == pts


@pytest.mark.parametrize("status,pain", [("dead", 35), ("social_as_site", 30), ("insecure", 28), ("free_builder", 25),
                                         ("weak", 20), ("none", 24), ("good", 0)])
def test_pain_points(cfg, status, pain):
    c = make(status=status)
    s = web_score(c, cfg, NOW)
    assert s.breakdown["pain"] == pain and s.eligible == (status != "good")


@pytest.mark.parametrize("days,pts", [(5, 20), (30, 20), (31, 14), (90, 14), (180, 8), (365, 3), (400, 0)])
def test_activity_bands(cfg, days, pts):
    assert web_score(make(newest_days=days), cfg, NOW).breakdown["activity"] == pts


@pytest.mark.parametrize("rating,pts", [(4.9, 10), (4.5, 10), (4.4, 7), (4.0, 7), (3.9, 3), (3.5, 3)])
def test_reputation_bands(cfg, rating, pts):
    assert web_score(make(rating=rating), cfg, NOW).breakdown["reputation"] == pts


def test_ability_bonuses_and_cap(cfg):
    c = make(reviews=200, flags=["premium"], sub="construction")
    c.branch_count = 2
    total, parts = ability_points(c, cfg)
    assert parts == {"reviews": 25, "area": 4, "branches_or_listings": 4, "subcategory": 3} and total == 25
    c = make(reviews=25, flags=["growth"])
    c.manages_listings = 4
    assert ability_points(c, cfg)[0] == 14 + 4 + 4
    assert ability_points(make(reviews=200), cfg, content=True)[0] == 35      # 25 × 1.4


def test_hook_points_from_strong_facts(cfg):
    c = make(status="dead", reviews=60)
    c.facts = build_facts(c, cfg, NOW)              # SITE_DEAD strong only
    assert web_score(c, cfg, NOW).breakdown["hook"] == 3
    c = make(status="weak", psi_lcp_s=7.5)          # SLOW_MOBILE strong
    c.audit.copyright_year = 2018
    c.facts = build_facts(c, cfg, NOW)
    assert web_score(c, cfg, NOW).breakdown["hook"] == 3


def test_content_gate_and_gap(cfg):
    good = make(status="good", social_links={}, has_video=False)
    s = content_score(good, cfg, NOW)
    assert s.eligible and s.breakdown["gap"] == 22 + 5
    fb_only = make(status="good", social_links={"facebook": "x"}, has_video=True)
    assert content_score(fb_only, cfg, NOW).breakdown["gap"] == 14
    polished = make(status="good", social_links={"instagram": "x", "tiktok": "y"}, has_video=True)
    assert content_score(polished, cfg, NOW).breakdown["gap"] == 0
    weak_ok = make(status="weak", https_ok=True, meta_viewport=True)
    assert content_score(weak_ok, cfg, NOW).eligible
    weak_bad = make(status="weak", https_ok=True, meta_viewport=False)
    assert not content_score(weak_bad, cfg, NOW).eligible
    assert not content_score(make(status="dead"), cfg, NOW).eligible


def test_stale_blog_bonus(cfg):
    from datetime import date
    c = make(status="good", social_links={"facebook": "x"}, has_video=True, blog_last_date=date(2025, 2, 14))
    assert content_score(c, cfg, NOW).breakdown["gap"] == 14 + 5


def test_routing_good_goes_content_dead_goes_web(cfg):
    good = make(status="good")
    good.facts = build_facts(good, cfg, NOW)
    score_candidate(good, cfg, NOW)
    assert good.track == "content"
    dead = make(status="dead")
    dead.facts = build_facts(dead, cfg, NOW)
    score_candidate(dead, cfg, NOW)
    assert dead.track == "web"


def test_weak_https_viewport_routes_by_margin(cfg):
    c = make(status="weak", https_ok=True, meta_viewport=True, social_links={}, has_video=False, reviews=200,
             psi_lcp_s=7.0, psi_perf=30.0)
    c.facts = build_facts(c, cfg, NOW)
    score_candidate(c, cfg, NOW)
    w, ct = c.scores["web"], c.scores["content"]
    assert w.eligible and ct.eligible
    assert c.track == ("web" if w.margin >= ct.margin else "content")
