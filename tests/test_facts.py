from datetime import date

from pipeline.facts import build_facts
from tests.helpers import NOW, make


def codes(c, cfg):
    return {f.code: f for f in build_facts(c, cfg, NOW)}


def test_site_dead_fact(cfg):
    f = codes(make(status="dead", website="http://www.kilimahomes.co.ke/"), cfg)["SITE_DEAD"]
    assert f.strength == "strong" and f.track == "web"
    assert f.text == "kilimahomes.co.ke, the website on your Google listing, isn't loading. It shows an 'account suspended' page."
    assert f.evidence["url"] == "http://www.kilimahomes.co.ke/"


def test_social_insecure_free_builder(cfg):
    assert codes(make(status="social_as_site"), cfg)["SOCIAL_AS_SITE"].text == \
        "The Website button on your Google listing opens your Facebook page."
    assert "Not secure" in codes(make(status="insecure", https_ok=False), cfg)["SITE_INSECURE"].text
    f = codes(make(status="free_builder", free_builder="Wix", free_host="acme.wixsite.com"), cfg)["FREE_BUILDER"]
    assert f.text == "Your site runs on a free Wix address (acme.wixsite.com)."


def test_slow_mobile_strength(cfg):
    assert codes(make(status="weak", psi_lcp_s=8.42), cfg)["SLOW_MOBILE"].strength == "strong"
    f = codes(make(status="weak", psi_lcp_s=4.6), cfg)["SLOW_MOBILE"]
    assert f.strength == "medium" and "about 5s" in f.text
    assert "SLOW_MOBILE" not in codes(make(status="weak", psi_lcp_s=3.0), cfg)


def test_weak_site_details(cfg):
    fs = codes(make(status="weak", meta_viewport=False, copyright_year=2018, has_whatsapp_link=False), cfg)
    assert fs["OLD_COPYRIGHT"].text == "Your site footer still says © 2018."
    assert {"NO_VIEWPORT", "NO_WHATSAPP_BUTTON"} <= set(fs)


def test_no_site_strength_by_reviews(cfg):
    assert codes(make(status="none", reviews=87), cfg)["NO_SITE_HIGH_REVIEWS"].strength == "strong"
    assert codes(make(status="none", reviews=20), cfg)["NO_SITE_HIGH_REVIEWS"].strength == "medium"
    assert codes(make(status="none", reviews=87), cfg)["NO_SITE_HIGH_REVIEWS"].text == \
        "87 Google reviews, but no website on your listing."


def test_places_facts(cfg):
    c = make(status="dead", rating=4.7, reviews=62, newest_days=5,
             review_texts=["a", "b", "c"])                                  # days 5, 25, 45 → 3 recent
    c.branch_count = 3
    c.manages_listings = 4
    fs = codes(c, cfg)
    assert fs["HIGH_RATING"].text == "4.7★ from 62 reviews."
    assert fs["RECENT_REVIEWS"].text == "At least 3 new Google reviews in the last 3 months."
    assert fs["BRANCHES"].text == "3 branches on Google Maps."
    assert fs["MANAGES_LISTINGS"].text == "Your number is on 4 property listings on Google Maps."
    c.subcategory = "hardware_supplies"
    assert "MANAGES_LISTINGS" not in codes(c, cfg)                          # only positive for property agencies


def test_content_facts(cfg):
    fs = codes(make(status="good", social_links={}, has_video=False, psi_perf=91, blog_last_date=date(2025, 2, 14)), cfg)
    assert fs["NO_SOCIAL_LINKS"].strength == "strong" and fs["NO_SOCIAL_LINKS"].track == "content"
    assert fs["GOOD_SITE"].track == "content"
    assert fs["STALE_BLOG"].text == "The latest post on your news page is from February 2025."
    assert "NO_VIDEO" in fs
    assert "GOOD_SITE" not in codes(make(status="good", psi_perf=55), cfg)


def test_ids_strongest_first(cfg):
    facts = build_facts(make(status="dead", rating=4.8, reviews=62), cfg, NOW)
    assert facts[0].id == "F1" and facts[0].code == "SITE_DEAD"
    assert [f.strength for f in facts] == sorted([f.strength for f in facts], key=lambda s: s != "strong")
