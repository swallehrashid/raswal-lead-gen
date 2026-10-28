"""First-touch teaser: an illustrative sponsored post on a 3D phone, with the enquiries landing in WhatsApp (ads pivot).

Playwright renders teasers/ad/<direction>/index.html (self-contained: fonts and photos inlined) with the lead's
name, logo and colours injected as window.LEAD. The direction is chosen per subcategory in subcategories.yaml
(ad_direction): d1 Golden Hour · d2 Studio · d3 Two Phones. Output: 1080x1350 JPEG within render.max_kb.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import mimetypes
import re
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from pipeline.models import Candidate
from pipeline.settings import TEASERS_DIR

log = logging.getLogger(__name__)

AD_DIR = TEASERS_DIR / "ad"

# ---------------------------------------------------------------- template preparation

_LINK = re.compile(r"""<link\b[^>]*rel=["']stylesheet["'][^>]*href=["']([^"':]+)["'][^>]*>""", re.I)
_LINK2 = re.compile(r"""<link\b[^>]*href=["']([^"':]+)["'][^>]*rel=["']stylesheet["'][^>]*>""", re.I)
_SCRIPT = re.compile(r"""<script\b[^>]*src=["']([^"':]+)["'][^>]*>\s*</script>""", re.I)
_IMG = re.compile(r"""(<img\b[^>]*\bsrc=["'])([^"':]+)(["'])""", re.I)
_CSS_URL = re.compile(r"""url\((["']?)([^"')]+)\1\)""")


def _data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def _inline_css_urls(css: str, base: Path) -> str:
    def repl(m):
        ref = m.group(2).strip()
        if ref.startswith(("data:", "http:", "https:", "//", "#")):
            return m.group(0)
        p = (base / ref).resolve()
        return f'url("{_data_url(p)}")' if p.exists() else m.group(0)
    return _CSS_URL.sub(repl, css)


def inline_template(path: Path) -> str:
    """Inline relative stylesheets, scripts, images and CSS url()s so the page needs no requests."""
    html = path.read_text(encoding="utf-8")
    base = path.parent

    def css(m):
        p = (base / m.group(1)).resolve()
        return f"<style>{_inline_css_urls(p.read_text(encoding='utf-8'), p.parent)}</style>" if p.exists() else ""

    html = _LINK.sub(css, html)
    html = _LINK2.sub(css, html)

    def js(m):
        p = (base / m.group(1)).resolve()
        return f"<script>{p.read_text(encoding='utf-8')}</script>" if p.exists() else ""

    html = _SCRIPT.sub(js, html)

    def img(m):
        p = (base / m.group(2)).resolve()
        return f"{m.group(1)}{_data_url(p)}{m.group(3)}" if p.exists() else m.group(0)

    html = _IMG.sub(img, html)
    return _inline_css_urls(html, base)


def inject_lead(html: str, lead: dict) -> str:
    blob = json.dumps(lead, ensure_ascii=False).replace("</", "<\\/")
    tag = f"<script>window.LEAD = {blob};</script>"
    m = re.search(r"<head[^>]*>", html, re.I)
    return html[:m.end()] + tag + html[m.end():] if m else tag + html



# ---------------------------------------------------------------- rendering

@dataclass
class Shot:
    key: str
    html: str
    width: int
    height: int
    scale: float = 1
    mobile: bool = False
    png: bytes | None = None
    blocked: list[str] = field(default_factory=list)


async def _render(shots: list[Shot], concurrency: int) -> None:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--disable-gpu", "--font-render-hinting=none"])
        sem = asyncio.Semaphore(concurrency)

        async def one(s: Shot) -> None:
            for attempt in range(2):          # one retry: a busy runner occasionally times out
                await attempt_one(s)
                if s.png:
                    return
                log.warning("retrying render for %s (attempt %d failed)", s.key, attempt + 1)

        async def attempt_one(s: Shot) -> None:
            async with sem:
                ctx = await browser.new_context(viewport={"width": s.width, "height": s.height},
                                                device_scale_factor=s.scale, is_mobile=s.mobile, has_touch=s.mobile)
                try:
                    page = await ctx.new_page()

                    async def block(route):
                        url = route.request.url
                        if url.startswith(("data:", "about:", "blob:")):
                            await route.continue_()
                        else:
                            s.blocked.append(url)
                            await route.abort()

                    s.blocked.clear()
                    await page.route("**/*", block)
                    await page.set_content(s.html, wait_until="load", timeout=30_000)
                    await page.evaluate("document.fonts.ready.then(() => true)")
                    s.png = await page.screenshot(type="png", timeout=30_000)
                except Exception as e:  # noqa: BLE001
                    log.error("render failed for %s: %s", s.key, e)
                finally:
                    await ctx.close()

        await asyncio.gather(*(one(s) for s in shots))
        await browser.close()


def render_shots(shots: list[Shot], concurrency: int = 3) -> list[Shot]:
    asyncio.run(_render(shots, concurrency))
    for s in shots:
        if s.blocked:
            log.warning("template for %s tried to load external resources (blocked): %s", s.key, s.blocked[:3])
    return shots



def to_jpeg(img: Image.Image, cfg) -> bytes:
    r = cfg.budget.render
    rgb = img.convert("RGB")
    q = r.jpeg_quality
    while True:
        buf = io.BytesIO()
        rgb.save(buf, "JPEG", quality=q, optimize=True, progressive=True)
        if buf.tell() <= r.max_kb * 1024 or q <= r.jpeg_min_quality:
            return buf.getvalue()
        q -= 4



# ---------------------------------------------------------------- lead payload (window.LEAD)



def _b64(data: bytes | None, mime: str) -> str | None:
    return f"data:{mime};base64,{base64.b64encode(data).decode()}" if data else None


def _ad_photo(subcategory: str, name: str) -> str | None:
    f = AD_DIR / "photos" / subcategory / name
    return _b64(f.read_bytes(), "image/jpeg") if f.exists() else None


def ad_lead_payload(c: Candidate, cfg) -> dict:
    """window.LEAD for the ad mockup: their name/logo/colours on an illustrative sponsored post."""
    sub = cfg.subcategories[c.subcategory]
    pal = sub.ad_palette or {}
    colours = (c.audit.colours if c.audit else {}) or {}
    return {
        "business_name": c.display_name,
        "area": c.area,
        "subcategory": c.subcategory,
        "logo_data_url": _b64(c.audit.logo_bytes if c.audit else None, "image/png"),
        "primary": colours.get("primary") or pal.get("primary"),
        "accent": colours.get("accent") or pal.get("accent"),
        "ad_primary": pal.get("primary"),
        "ad_accent": pal.get("accent"),
        "ad_bg_data_url": _ad_photo(c.subcategory, "bg.jpg"),
        "ad_post_data_url": _ad_photo(c.subcategory, "post.jpg"),
        "ad": sub.ad_teaser,
    }




def render_teasers(cands: list[Candidate], cfg) -> dict[str, bytes]:
    """One 1080x1350 JPEG (<= render.max_kb) per candidate, using each subcategory's ad_direction.
    Returns place_id → bytes (failures omitted)."""
    rc = cfg.budget.render
    cands = cands[: rc.max_per_night]
    bases: dict[str, str] = {}
    shots: list[Shot] = []
    for c in cands:
        direction = cfg.subcategories[c.subcategory].ad_direction
        path = AD_DIR / direction / "index.html"
        if not path.exists():
            log.error("missing ad teaser template: %s", path)
            continue
        if direction not in bases:
            bases[direction] = inline_template(path)
        shots.append(Shot(c.place_id, inject_lead(bases[direction], ad_lead_payload(c, cfg)), 1080, 1350))
    render_shots(shots, rc.concurrency)
    out: dict[str, bytes] = {}
    for s_ in shots:
        if not s_.png:
            continue
        try:
            out[s_.key] = to_jpeg(Image.open(io.BytesIO(s_.png)), cfg)
        except Exception as e:  # noqa: BLE001
            log.error("ad teaser encode failed for %s: %s", s_.key, e)
    log.info("ad teasers: rendered %d of %d", len(out), len(cands))
    return out
