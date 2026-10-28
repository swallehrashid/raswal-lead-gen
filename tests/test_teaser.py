import io
import re

import pytest
from PIL import Image

from pipeline.facts import build_facts
from pipeline.settings import TEASERS_DIR
from pipeline.teaser import (
    Shot,
    composite_content,
    composite_web,
    inject_lead,
    inline_template,
    lead_payload,
    render_shots,
    template_paths,
    to_jpeg,
)
from tests.helpers import NOW, make

CONTRACT_FIELDS = {"business_name", "area", "logo_data_url", "primary", "accent", "hero_image_data_url", "headline",
                   "subline", "poster_lines", "phone_display", "preview_domain"}


def all_templates(cfg):
    out = []
    for sub in cfg.subcategories.values():
        out.append(TEASERS_DIR / "web" / sub.template / "index.html")
        out += [TEASERS_DIR / "content" / sub.template / f"poster-{i}.html" for i in (1, 2, 3)]
    return out


def sample(cfg, track="web", sub="property_agency"):
    c = make("Kilima Homes & Lettings", sub=sub, status="dead" if track == "web" else "good")
    c.track = track
    c.slug = "kilima-homes-and-lettings"
    c.facts = build_facts(c, cfg, NOW)
    return c


def test_every_subcategory_has_all_templates(cfg):
    for p in all_templates(cfg):
        assert p.exists(), p


def test_payload_has_contract_fields(cfg):
    lead = lead_payload(sample(cfg), cfg)
    assert CONTRACT_FIELDS <= set(lead)
    assert lead["preview_domain"] == "kilima-homes-and-lettings.raswaltechsolutions.co.ke"
    assert lead["headline"] == "Homes to rent & buy in Kilimani"
    assert lead["logo_data_url"] is None and lead["primary"].startswith("#")


def test_inlined_templates_are_self_contained(cfg):
    for p in all_templates(cfg):
        html = inline_template(p)
        assert "@font-face" in html and "base64," in html, p
        assert not re.search(r"""<link[^>]+href=["'](?!data:)""", html), p
        assert not re.search(r"""<script[^>]+src=""", html), p
        assert not re.search(r"""(src|href)=["']https?://""", html), p
        for var in ("--brand-primary", "--brand-accent", "--brand-ink", "--brand-bg"):
            assert var in html, (p, var)
        assert "window.LEAD" in html


def test_inject_lead_escapes_script_close(cfg):
    html = inject_lead("<html><head></head><body></body></html>", {"business_name": "</script><b>x"})
    assert "</script><b>" not in html.split("window.LEAD", 1)[1].split(";</script>")[0]


@pytest.mark.render
def test_all_templates_render_without_network(cfg):
    lead = lead_payload(sample(cfg), cfg)
    lead["poster_lines"] = ["Book a viewing on WhatsApp", "Viewings arranged quickly", "Homes to rent and buy"]
    shots = []
    for p in all_templates(cfg):
        html = inject_lead(inline_template(p), lead)
        w, h = (1440, 900) if p.name == "index.html" else (1080, 1350)
        shots.append(Shot(str(p), html, w, h))
    render_shots(shots, concurrency=3)
    for s in shots:
        assert s.png, s.key
        assert s.blocked == [], (s.key, s.blocked)


@pytest.mark.render
def test_render_teasers_end_to_end(cfg):
    from pipeline.teaser import render_teasers
    web, content = sample(cfg, "web"), sample(cfg, "content", sub="land_developers")
    content.place_id = web.place_id + "c"
    out = render_teasers([web, content], cfg)
    for c in (web, content):
        img = Image.open(io.BytesIO(out[c.place_id]))
        assert img.size == (1080, 1350) and img.format == "JPEG"
        assert len(out[c.place_id]) <= cfg.budget.render.max_kb * 1024


def test_composites_and_jpeg_cap(cfg):
    def png(w, h, colour):
        b = io.BytesIO()
        Image.new("RGB", (w, h), colour).save(b, "PNG")
        return b.getvalue()
    lead = {"business_name": "A Very Long Business Name That Needs Wrapping Ltd", "primary": "#0F3D5E",
            "preview_domain": "a.raswaltechsolutions.com"}
    web = composite_web(png(1440, 900, "white"), png(780, 1688, "white"), lead)
    assert web.size == (1080, 1350)
    content = composite_content([png(1080, 1350, "red")] * 3, lead)
    assert content.size == (1080, 1350)
    noisy = Image.effect_noise((1080, 1350), 120).convert("RGB")       # worst case: stops at jpeg_min_quality
    assert to_jpeg(noisy, cfg)[:2] == b"\xff\xd8"
    assert len(to_jpeg(web, cfg)) <= cfg.budget.render.max_kb * 1024


def test_template_paths_follow_config_template(cfg):
    c = sample(cfg, "content")
    assert [p.name for p in template_paths(c, cfg)] == ["poster-1.html", "poster-2.html", "poster-3.html"]
