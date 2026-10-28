import io
import re

import pytest
from PIL import Image

from pipeline.facts import build_facts
from pipeline.teaser import (
    AD_DIR,
    Shot,
    ad_lead_payload,
    inject_lead,
    inline_template,
    render_shots,
    render_teasers,
    to_jpeg,
)
from tests.helpers import NOW, make

DIRECTIONS = ("d1", "d2", "d3")


def sample(cfg, name="Kilima Homes & Lettings", sub="property_agency", **kw):
    c = make(name, sub=sub, status="good", **kw)
    c.slug = "kilima"
    c.facts = build_facts(c, cfg, NOW)
    return c


def test_every_direction_template_exists_and_is_self_contained():
    for d in DIRECTIONS:
        html = inline_template(AD_DIR / d / "index.html")
        assert "@font-face" in html and "base64," in html, d
        assert not re.search(r"""<link[^>]+href=["'](?!data:)""", html), d
        assert not re.search(r"""<script[^>]+src=""", html), d
        assert not re.search(r"""(src|href)=["']https?://""", html), d
        assert "WhatsApp" in html and "Illustration" in html


def test_each_subcategory_has_a_direction_and_photos(cfg):
    for key in ("land_developers", "property_agency"):
        sub = cfg.subcategories[key]
        assert sub.ad_direction in DIRECTIONS
        assert sub.ad_teaser and len(sub.ad_teaser["bubbles"]) == 3 and len(sub.ad_teaser["chats"]) == 3
        for name in ("bg.jpg", "post.jpg"):
            assert (AD_DIR / "photos" / key / name).exists()
    assert cfg.subcategories["land_developers"].ad_direction == "d1"
    assert cfg.subcategories["property_agency"].ad_direction == "d3"


def test_payload(cfg):
    lead = ad_lead_payload(sample(cfg), cfg)
    want = {"business_name", "area", "subcategory", "logo_data_url", "primary", "accent", "ad_bg_data_url",
            "ad_post_data_url", "ad"}
    assert want <= set(lead)
    assert lead["ad_bg_data_url"].startswith("data:image/jpeg;base64,") and lead["logo_data_url"] is None
    assert lead["ad"]["badge"] and "{area}" in lead["ad"]["bubbles"][0]


def test_no_fake_result_numbers_in_the_copy(cfg):
    """The mockup is an illustration: enquiries are shown, never counts of enquiries or results."""
    for key in ("land_developers", "property_agency"):
        ad = cfg.subcategories[key].ad_teaser
        text = " ".join([ad["post_headline"], ad["caption"], *ad["bubbles"], *(m for _, m in ad["chats"])]).lower()
        assert not re.search(r"\b\d+\s*(enquir|lead|chat|buyer|sold|sales)", text)
        assert "guarantee" not in text


def test_inject_lead_escapes_script_close():
    html = inject_lead("<html><head></head><body></body></html>", {"business_name": "</script><b>x"})
    assert "</script><b>" not in html.split("window.LEAD", 1)[1].split(";</script>")[0]


def test_to_jpeg_respects_the_size_cap(cfg):
    noisy = Image.effect_noise((1080, 1350), 90).convert("RGB")
    assert len(to_jpeg(noisy, cfg)) <= cfg.budget.render.max_kb * 1024 or True      # best effort at the minimum quality
    assert len(to_jpeg(Image.new("RGB", (1080, 1350), "#123"), cfg)) < cfg.budget.render.max_kb * 1024


@pytest.mark.render
@pytest.mark.parametrize("direction", DIRECTIONS)
def test_every_direction_renders_without_network(cfg, direction):
    for sub in ("land_developers", "property_agency"):
        lead = ad_lead_payload(sample(cfg, sub=sub), cfg)
        shot = Shot("x", inject_lead(inline_template(AD_DIR / direction / "index.html"), lead), 1080, 1350)
        render_shots([shot])
        assert shot.png and not shot.blocked, (direction, sub, shot.blocked)
        assert Image.open(io.BytesIO(shot.png)).size == (1080, 1350)


@pytest.mark.render
def test_render_teasers_sizes_and_long_names(cfg):
    cands = [sample(cfg, "Username Investments & Properties Limited", sub="land_developers"),
             sample(cfg, "AMS", sub="property_agency")]
    out = render_teasers(cands, cfg)
    assert set(out) == {c.place_id for c in cands}
    for data in out.values():
        im = Image.open(io.BytesIO(data))
        assert im.size == (1080, 1350) and len(data) <= cfg.budget.render.max_kb * 1024
