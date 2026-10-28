import pytest

from pipeline.score import (
    ability_points,
    activity_points,
    ads_score,
    derive_angle,
    derive_social_state,
    review_points,
    score_candidate,
)
from tests.helpers import NOW, make


@pytest.mark.parametrize("n,pts", [(7, 0), (8, 8), (19, 8), (20, 14), (49, 14), (50, 20), (149, 20), (150, 25),
                                   (400, 25), (401, 18), (2000, 18)])
def test_review_bands(cfg, n, pts):
    assert review_points(n, cfg) == pts


@pytest.mark.parametrize("days,pts", [(5, 15), (30, 15), (31, 10), (90, 10), (180, 5), (181, 0), (400, 0)])
def test_activity_bands(cfg, days, pts):
    assert activity_points(make(newest_days=days), cfg, NOW) == pts


@pytest.mark.parametrize("rating,pts", [(4.9, 10), (4.5, 10), (4.4, 7), (4.0, 7), (3.9, 3), (3.5, 3)])
def test_reputation_bands(cfg, rating, pts):
    assert ads_score(make(rating=rating), cfg, NOW).breakdown["reputation"] == pts


@pytest.mark.parametrize("status,has", [("good", True), ("weak", True), ("insecure", True), ("free_builder", True),
                                        ("dead", False), ("none", False), ("social_as_site", False)])
def test_working_website_points(cfg, status, has):
    br = ads_score(make(status=status), cfg, NOW).breakdown
    assert ("website" in br) == has and (br.get("website") == 10 if has else True)


def test_ads_active_and_long_running_bonus(cfg):
    assert "ads_active" not in ads_score(make(), cfg, NOW).breakdown
    assert ads_score(make(ads="active", ads_days=10), cfg, NOW).breakdown["ads_active"] == 20
    assert ads_score(make(ads="active", ads_days=60), cfg, NOW).breakdown["ads_active"] == 25
    assert "ads_active" not in ads_score(make(ads="none"), cfg, NOW).breakdown


def test_social_state_points(cfg):
    assert derive_social_state(make(social_links={}), NOW) == "none"
    assert derive_social_state(make(social_links={"facebook": "x"}), NOW) == "stale"
    assert derive_social_state(make(ads="active"), NOW) == "active"
    c = make()
    c.social = {"ig_last_post_at": "2026-10-01T00:00:00+00:00"}
    assert derive_social_state(c, NOW) == "active"
    assert ads_score(make(ads="active"), cfg, NOW).breakdown["social"] == 10
    assert ads_score(make(social_links={"facebook": "x"}), cfg, NOW).breakdown["social"] == 4
    assert "social" not in ads_score(make(social_links={}), cfg, NOW).breakdown


def test_soft_scam_flag_penalises(cfg):
    base = ads_score(make(reviews=200), cfg, NOW)
    soft = ads_score(make(reviews=200, scam="soft"), cfg, NOW)
    assert soft.breakdown["scam_soft"] == -15 and soft.total == base.total - 15


def test_ability_bonuses_and_cap(cfg):
    c = make(reviews=200, flags=["premium"], sub="construction")
    c.branch_count = 2
    total, parts = ability_points(c, cfg)
    assert parts == {"reviews": 25, "area": 5, "branches_or_listings": 5, "subcategory": 3} and total == 35
    c = make(reviews=25, flags=["growth"])
    c.manages_listings = 4
    assert ability_points(c, cfg)[0] == 14 + 5 + 5


def test_score_is_capped_at_100_and_threshold_is_config(cfg):
    c = make(status="good", reviews=200, flags=["premium"], ads="active", ads_days=90, social_links={"instagram": "x"})
    c.branch_count = 3
    s = ads_score(c, cfg, NOW)
    assert s.total <= 100 and s.threshold == cfg.scoring.ads.min_score and s.eligible


def test_angle(cfg):
    assert derive_angle(make(ads="active", status="dead"), cfg) == "B"          # advertising beats a dead site
    assert derive_angle(make(status="dead"), cfg) == "C"
    assert derive_angle(make(status="none"), cfg) == "C"
    assert derive_angle(make(status="social_as_site"), cfg) == "C"
    assert derive_angle(make(status="good"), cfg) == "A"
    assert derive_angle(make(status="weak"), cfg) == "A"


def test_score_candidate_sets_single_ads_track(cfg):
    c = make(status="good", ads="none")
    score_candidate(c, cfg, NOW)
    assert c.track == "ads" and c.angle == "A" and set(c.scores) == {"ads"} and c.social_state == "none"
