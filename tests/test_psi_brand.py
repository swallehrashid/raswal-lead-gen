import io
from datetime import date

from PIL import Image

from pipeline.brand import extract_colours, find_brand_assets
from pipeline.budget import Budget
from pipeline.fakes import FixtureFetcher, FixturePsi
from pipeline.models import Audit, Candidate
from pipeline.psi import parse_psi, run_psi_batch
from pipeline.store import MemoryStore
from pipeline.utils.colours import contrast, hex_to_rgb
from tests.conftest import load_json


def test_parse_psi_profiles():
    perf, lcp, shot = parse_psi(load_json("psi/psi_slow.json"))
    assert perf == 27.0 and lcp == 8.42
    img = Image.open(io.BytesIO(shot))
    assert img.format == "JPEG" and img.width == 412
    perf, lcp, _ = parse_psi(load_json("psi/psi_fast.json"))
    assert perf == 91.0 and lcp == 1.85


def test_parse_psi_handles_missing_fields():
    assert parse_psi({}) == (None, None, None)


def _cand(pid, url):
    c = Candidate(place_id=pid, name="X", name_norm="x", subcategory="property_agency", types=[], primary_type=None,
                  address=None, lat=None, lng=None, maps_url=None, business_status="OPERATIONAL", phone_raw=None,
                  phone_e164=None, phone_type=None, website_url=url, rating=4.5, review_count=20, reviews=[], area="")
    c.audit = Audit("_pending", website_url=url, final_url=url)
    return c


def test_psi_batch_dedupes_by_domain_and_caches(cfg):
    store = MemoryStore()
    psi = FixturePsi()
    budget = Budget.from_config(cfg, store, date(2026, 10, 12))
    budget.caps["psi"].per_night = 150            # PSI is off by default in config; this tests the batch itself
    a, b = _cand("a", "https://www.x.co.ke/"), _cand("b", "https://x.co.ke/about")
    run_psi_batch([a, b], psi, budget, store, cfg, sleep=lambda s: None)
    assert len(psi.calls) == 1 and a.audit.psi_perf == b.audit.psi_perf
    c = _cand("c", "https://x.co.ke/")
    run_psi_batch([c], psi, budget, store, cfg, sleep=lambda s: None)
    assert len(psi.calls) == 1 and c.audit.psi_perf == a.audit.psi_perf     # served from the 30-day cache
    assert budget.used("psi") == 1


def test_psi_budget_cap_stops_cleanly(cfg):
    store = MemoryStore()
    budget = Budget.from_config(cfg, store, date(2026, 10, 12))
    budget.caps["psi"].per_night = 1
    cands = [_cand(str(i), f"https://site{i}.co.ke/") for i in range(3)]
    run_psi_batch(cands, FixturePsi(), budget, store, cfg, sleep=lambda s: None)
    assert sum(c.audit.psi_perf is not None for c in cands) == 1


def test_brand_assets_from_wordpress_site(cfg):
    f = FixtureFetcher()
    f.index = {"good.co.ke": {"file": "good_wordpress.html", "name": "Good Homes", "logo_colour": "#1E8449"}}
    page = f.fetch("https://good.co.ke/")
    a = Audit("good", final_url=page.final_url, html=page.html)
    find_brand_assets(a, f, cfg)
    assert a.logo_url and "apple-touch-icon" in a.logo_url
    assert a.colours["primary"].startswith("#")
    assert contrast((255, 255, 255), hex_to_rgb(a.colours["primary"])) >= 4.5
    assert a.hero_image_url and a.hero_bytes                    # og:image
    assert Image.open(io.BytesIO(a.logo_bytes)).format == "PNG"


def test_no_logo_means_wordmark(cfg):
    f = FixtureFetcher()
    f.index = {"thin.co.ke": {"file": "weak_thin.html", "name": "Thin"}}
    page = f.fetch("https://thin.co.ke/")
    a = find_brand_assets(Audit("weak", final_url=page.final_url, html=page.html), f, cfg)
    assert a.logo_url is None and a.colours == {}


def test_colour_extraction_ignores_white_black_and_grey():
    img = Image.new("RGBA", (200, 200), (255, 255, 255, 255))
    for x in range(200):
        for y in range(200):
            if x < 80:
                img.putpixel((x, y), (250, 204, 21, 255))        # bright yellow (fails white-text contrast)
            elif x < 120:
                img.putpixel((x, y), (20, 20, 20, 255))
            elif x < 150:
                img.putpixel((x, y), (37, 99, 235, 255))         # blue
    col = extract_colours(img)
    assert contrast((255, 255, 255), hex_to_rgb(col["primary"])) >= 4.5   # darkened
    assert "accent" in col
    assert extract_colours(Image.new("RGBA", (50, 50), (0, 0, 0, 0))) is None


def test_psi_is_off_by_default_and_costs_nothing(cfg):
    store = MemoryStore()
    psi = FixturePsi()
    budget = Budget.from_config(cfg, store, date(2026, 10, 12))
    assert cfg.budget.psi.calls_per_night == 0
    run_psi_batch([_cand("a", "https://x.co.ke/")], psi, budget, store, cfg, sleep=lambda s: None)
    assert psi.calls == [] and budget.used("psi") == 0
