from datetime import date, datetime, timezone

import httpx
import pytest

from pipeline.audit_site import PENDING, audit_website, copyright_year, finalize_status
from pipeline.fakes import FixtureFetcher
from pipeline.utils.http import classify_error

NOW = datetime(2026, 10, 11, 18, 30, tzinfo=timezone.utc)


@pytest.fixture
def fetcher():
    f = FixtureFetcher()
    f.index = {
        "good.co.ke": {"file": "good_wordpress.html", "name": "Good Homes", "phone": "0722 123456",
                       "blog": "blog_stale.html", "logo_colour": "#0E6BA8"},
        "nosocial.co.ke": {"file": "good_no_social.html", "name": "No Social", "phone": "0722 123456"},
        "video.co.ke": {"file": "good_with_video.html", "name": "Video Co", "phone": "0722 123456"},
        "old.co.ke": {"file": "weak_old_desktop.html", "name": "Old Co", "phone": "0722 123456"},
        "thin.co.ke": {"file": "weak_thin.html", "name": "Thin Co"},
        "wixslow.co.ke": {"file": "weak_wix_slow.html", "name": "Wix Co"},
        "insecure.co.ke": {"file": "insecure_http_only.html", "name": "Insecure Co", "https": "ssl_error"},
        "acme.wixsite.com": {"file": "free_builder_wixsite.html", "name": "Acme"},
        "suspended.co.ke": {"file": "parked_suspended.html"},
        "expired.co.ke": {"file": "parked_expired.html"},
        "forsale.co.ke": {"file": "parked_for_sale.html"},
        "soon.co.ke": {"file": "coming_soon.html"},
        "default.co.ke": {"file": "hosting_default.html"},
        "indexof.co.ke": {"file": "index_of.html"},
        "nxdomain.co.ke": {"error": "dns"},
        "missing.co.ke": {"file": "error_404.html", "status": 404},
        "down.co.ke": {"file": "error_503.html", "status": 503},
        "oldgbp.co.ke": {"redirect_to": "https://oldgbp.business.site/", "error_after_redirect": "dns"},
    }
    return f


def status(url, fetcher, cfg, psi_perf=None):
    a = audit_website(url, fetcher, cfg, NOW)
    if a.site_status in (PENDING, "insecure", "free_builder"):
        a.psi_perf = psi_perf
    return finalize_status(a, cfg, NOW)


def test_none(cfg, fetcher):
    assert status(None, fetcher, cfg).site_status == "none"


@pytest.mark.parametrize("url,platform", [
    ("https://www.facebook.com/kilimahomes", "Facebook"),
    ("https://web.facebook.com/kilimahomes", "Facebook"),
    ("https://instagram.com/kilimahomes", "Instagram"),
    ("https://www.tiktok.com/@kilima", "TikTok"),
    ("https://linktr.ee/kilima", "Linktree"),
    ("https://wa.me/254722000111", "WhatsApp"),
    ("https://x.com/kilima", "X"),
    ("https://maps.app.goo.gl/AbC123", "Google Maps"),
    ("https://www.google.com/maps/place/Kilima+Homes", "Google Maps"),
])
def test_social_as_site(cfg, fetcher, url, platform):
    a = status(url, fetcher, cfg)
    assert a.site_status == "social_as_site" and a.social_platform == platform
    assert fetcher.fetched == []      # never fetch social pages


@pytest.mark.parametrize("url,marker", [
    ("http://suspended.co.ke/", "account suspended"),
    ("http://expired.co.ke/", "domain expired"),
    ("http://forsale.co.ke/", "domain for sale"),
    ("http://soon.co.ke/", "coming soon"),
    ("http://default.co.ke/", "default page"),
    ("http://indexof.co.ke/", "Index of"),
    ("http://nxdomain.co.ke/", "can't be reached"),
    ("http://missing.co.ke/", "404"),
    ("http://down.co.ke/", "server error"),
    ("http://oldgbp.co.ke/", "Google Business Profile"),
    ("https://kilimahomes.business.site/", "Google Business Profile"),
])
def test_dead(cfg, fetcher, url, marker):
    a = status(url, fetcher, cfg)
    assert a.site_status == "dead"
    assert marker.lower() in a.dead_marker.lower()


def test_insecure(cfg, fetcher):
    a = status("https://insecure.co.ke/", fetcher, cfg, psi_perf=60)
    assert a.site_status == "insecure" and a.https_ok is False and a.cert_error is True


def test_free_builder(cfg, fetcher):
    a = status("https://acme.wixsite.com/home", fetcher, cfg, psi_perf=60)
    assert a.site_status == "free_builder" and a.free_builder == "Wix" and a.free_host == "acme.wixsite.com"


def test_weak_old_desktop_site(cfg, fetcher):
    a = status("http://old.co.ke/", fetcher, cfg, psi_perf=27)
    assert a.site_status == "weak"
    assert {"psi_slow", "no_viewport", "old_copyright", "no_whatsapp"} <= set(a.weak_signals)
    assert a.copyright_year == 2018


def test_weak_thin_site_without_psi(cfg, fetcher):
    a = status("https://thin.co.ke/", fetcher, cfg, psi_perf=None)
    assert a.site_status == "weak" and {"no_whatsapp", "no_tel", "thin_text"} <= set(a.weak_signals)


def test_wix_site_on_own_domain_is_weak_not_free_builder(cfg, fetcher):
    a = status("https://wixslow.co.ke/", fetcher, cfg, psi_perf=27)
    assert a.site_status == "weak" and a.platform == "Wix"


def test_good_site_and_features(cfg, fetcher):
    a = status("http://good.co.ke/", fetcher, cfg, psi_perf=91)
    assert a.site_status == "good", a.weak_signals
    assert a.https_ok and a.meta_viewport and a.has_whatsapp_link and a.has_tel_link
    assert a.platform == "WordPress"
    assert a.copyright_year == NOW.year              # "© 2019 - {YEAR}" → the later year
    assert set(a.social_links) == {"facebook", "instagram"}
    assert "sharer" not in a.social_links["facebook"]
    assert a.blog_last_date == date(2025, 2, 14)
    assert not a.has_video


def test_video_and_all_socials(cfg, fetcher):
    a = status("https://video.co.ke/", fetcher, cfg, psi_perf=91)
    assert a.site_status == "good" and a.has_video and a.platform == "Webflow"
    assert set(a.social_links) == {"instagram", "tiktok", "youtube", "linkedin", "x"}


def test_no_social_links(cfg, fetcher):
    a = status("https://nosocial.co.ke/", fetcher, cfg, psi_perf=91)
    assert a.site_status == "good" and a.social_links == {}


def test_long_page_mentioning_coming_soon_or_cpanel_is_not_dead(cfg, fetcher):
    fetcher.index["busy.co.ke"] = {"file": "good_no_social.html", "name": "Busy"}
    from pathlib import Path
    tmp = Path(fetcher.dir) / "_tmp_busy.html"
    tmp.write_text((Path(fetcher.dir) / "good_no_social.html").read_text().replace(
        "</footer>", "New branch coming soon! Hosting control panel: cPanel.</footer>"))
    try:
        fetcher.index["busy.co.ke"]["file"] = "_tmp_busy.html"
        assert status("https://busy.co.ke/", fetcher, cfg, psi_perf=91).site_status == "good"
    finally:
        tmp.unlink()


@pytest.mark.parametrize("text,year", [
    ("© 2019 - 2026 Kilima Homes", 2026),
    ("Copyright &copy; 2018 Old Co", 2018),
    ("Copyright © 2021 by Wix Co", 2021),
    ("(c) 2015–2017 Some Co", 2017),
    ("Founded 1998, no notice", None),
])
def test_copyright_year(text, year):
    assert copyright_year(text.replace("&copy;", "©"), NOW.date()) == year


def test_error_classification():
    req = httpx.Request("GET", "https://x.co.ke")
    assert classify_error(httpx.ConnectError("[Errno -2] Name or service not known", request=req)) == "dns"
    assert classify_error(httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed", request=req)) == "ssl"
    assert classify_error(httpx.ConnectTimeout("timed out", request=req)) == "timeout"
    assert classify_error(httpx.ConnectError("Connection refused", request=req)) == "connect"
    assert classify_error(httpx.TooManyRedirects("too many", request=req)) == "too_many_redirects"
