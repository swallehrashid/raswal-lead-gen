"""Teaser images: Playwright render of teasers/ templates + Pillow composite (brief §13).

Website teaser: desktop (1440×900) + mobile (390×844 @2x) renders of
teasers/web/<template>/index.html in laptop/phone frames on the brand colour.
Content teaser: poster-1..3.html at 1080×1350, one large + two small.
Output: 1080×1350 JPEG, quality ~82, at most 350 KB.
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

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from pipeline.models import Candidate
from pipeline.normalise import phone_display
from pipeline.settings import TEASERS_DIR
from pipeline.utils.colours import hex_to_rgb

log = logging.getLogger(__name__)

W, H = 1080, 1350
FONT_DIR = TEASERS_DIR / "shared" / "fonts"
PREVIEW_HOST = "raswaltechsolutions.com"


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


# ---------------------------------------------------------------- lead payload (window.LEAD)

def _b64(data: bytes | None, mime: str) -> str | None:
    return f"data:{mime};base64,{base64.b64encode(data).decode()}" if data else None


def lead_payload(c: Candidate, cfg) -> dict:
    sub = cfg.subcategories[c.subcategory]
    pal = sub.default_palette
    colours = (c.audit.colours if c.audit else {}) or {}
    return {
        "business_name": c.display_name,
        "area": c.area,
        "logo_data_url": _b64(c.audit.logo_bytes if c.audit else None, "image/png"),
        "primary": colours.get("primary") or pal.primary,
        "accent": colours.get("accent") or pal.accent,
        "ink": pal.ink,
        "bg": pal.bg,
        "hero_image_data_url": _b64(c.audit.hero_bytes if c.audit else None, "image/jpeg"),
        "headline": sub.headline.format(area=c.area),
        "subline": sub.subline,
        "poster_lines": c.poster_lines or sub.generic_poster_lines,
        "phone_display": phone_display(c.phone_e164),
        "preview_domain": f"{c.slug}.{PREVIEW_HOST}",
        # optional extras (templates may ignore them)
        "cta": sub.cta,
        "nav": sub.nav,
        "subcategory": c.subcategory,
        "track": c.track,
    }


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


# ---------------------------------------------------------------- compositing

def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(FONT_DIR / name), size)
    except OSError:
        return ImageFont.load_default(size)


def _frames() -> dict:
    return json.loads((TEASERS_DIR / "frames" / "frames.json").read_text(encoding="utf-8"))


def _rounded_mask(size, radius) -> Image.Image:
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255)
    return m


def _shadow(canvas: Image.Image, box, radius=24, blur=26, opacity=110, offset=(0, 18)) -> None:
    x0, y0, x1, y1 = box
    pad = blur * 3
    sh = Image.new("RGBA", (x1 - x0 + pad * 2, y1 - y0 + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([pad, pad, pad + x1 - x0, pad + y1 - y0], radius=radius, fill=(0, 0, 0, opacity))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    canvas.alpha_composite(sh, (x0 - pad + offset[0], y0 - pad + offset[1]))


def _fit(img: Image.Image, size) -> Image.Image:
    """Cover-resize then crop from the top (screenshots keep their header)."""
    tw, th = size
    scale = max(tw / img.width, th / img.height)
    img = img.resize((max(tw, round(img.width * scale)), max(th, round(img.height * scale))), Image.LANCZOS)
    return img.crop((0, 0, tw, th))


def _background(primary: str) -> Image.Image:
    r, g, b = hex_to_rgb(primary)
    top = tuple(min(255, int(c + (255 - c) * 0.18)) for c in (r, g, b))
    bg = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(bg)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(top[i] * (1 - t) + (r, g, b)[i] * t) for i in range(3)) + (255,))
    return bg


def _text_colour(primary: str) -> tuple[int, int, int]:
    from pipeline.utils.colours import contrast
    rgb = hex_to_rgb(primary)
    return (255, 255, 255) if contrast((255, 255, 255), rgb) >= 3 else (11, 27, 43)


def composite_web(desktop_png: bytes, mobile_png: bytes, lead: dict) -> Image.Image:
    fr = _frames()
    canvas = _background(lead["primary"])
    ink = _text_colour(lead["primary"])
    d = ImageDraw.Draw(canvas)
    d.text((60, 52), "WEBSITE PREVIEW", font=_font("inter-latin-600-normal.woff", 26), fill=ink + (200,))

    lap = fr["laptop"]
    lx, ly = (W - lap["size"][0]) // 2, 120
    sx, sy, sw, sh = lap["screen"]
    _shadow(canvas, (lx + 60, ly + 10, lx + lap["size"][0] - 60, ly + lap["size"][1] - 20), radius=30)
    desk = _fit(Image.open(io.BytesIO(desktop_png)).convert("RGBA"), (sw, sh))
    canvas.alpha_composite(desk, (lx + sx, ly + sy))
    canvas.alpha_composite(Image.open(TEASERS_DIR / "frames" / lap["file"]).convert("RGBA"), (lx, ly))
    ux, uy, uw, uh = lap["url_bar"]
    f = _font("inter-latin-400-normal.woff", 17)
    url = lead["preview_domain"]
    tw = d.textlength(url, font=f)
    d.text((lx + ux + (uw - tw) / 2, ly + uy + (uh - 21) / 2), url, font=f, fill=(60, 64, 72))

    ph = fr["phone"]
    px, py = W - ph["size"][0] - 70, H - ph["size"][1] - 70
    qx, qy, qw, qh = ph["screen"]
    _shadow(canvas, (px, py, px + ph["size"][0], py + ph["size"][1]), radius=52, opacity=140)
    mob = _fit(Image.open(io.BytesIO(mobile_png)).convert("RGBA"), (qw, qh))
    mob.putalpha(_rounded_mask((qw, qh), ph.get("screen_radius", 36)))
    canvas.alpha_composite(mob, (px + qx, py + qy))
    canvas.alpha_composite(Image.open(TEASERS_DIR / "frames" / ph["file"]).convert("RGBA"), (px, py))

    _heading(canvas, "A new website for", lead["business_name"], ink, x=60, bottom=H - 150, max_w=px - 100)
    _label(canvas, f"Preview for {lead['business_name']} · by Raswal", ink, max_w=px - 80)
    return canvas


def _wrap(d: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if d.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    return lines + [cur] if cur else lines


def _heading(canvas: Image.Image, kicker: str, name: str, colour, *, x: int, bottom: int, max_w: int) -> None:
    """Kicker + business name (display font, up to 3 lines), anchored to `bottom`. Makes no claim."""
    d = ImageDraw.Draw(canvas)
    size = 64
    while True:
        f = _font("montserrat-latin-800-normal.woff", size)
        lines = _wrap(d, name, f, max_w)
        if (len(lines) <= 3 and all(d.textlength(ln, font=f) <= max_w for ln in lines)) or size <= 30:
            break
        size -= 4
    line_h = int(size * 1.08)
    y = bottom - line_h * len(lines)
    kf = _font("inter-latin-600-normal.woff", 28)
    d.text((x, y - 46), kicker, font=kf, fill=tuple(colour) + (215,))
    for ln in lines:
        d.text((x, y), ln, font=f, fill=tuple(colour) + (255,))
        y += line_h


def _label(canvas: Image.Image, text: str, colour, max_w: int) -> None:
    d = ImageDraw.Draw(canvas)
    size = 30
    f = _font("inter-latin-600-normal.woff", size)
    while d.textlength(text, font=f) > max_w and size > 16:
        size -= 2
        f = _font("inter-latin-600-normal.woff", size)
    d.text((60, H - 70 - size), text, font=f, fill=tuple(colour) + (235,))


def composite_content(posters: list[bytes], lead: dict) -> Image.Image:
    canvas = Image.new("RGBA", (W, H), (239, 236, 230, 255))
    d = ImageDraw.Draw(canvas)
    d.text((60, 46), "SAMPLE POSTS", font=_font("inter-latin-600-normal.woff", 26), fill=(11, 27, 43, 170))
    big = _fit(Image.open(io.BytesIO(posters[0])).convert("RGBA"), (624, 780))
    small = [_fit(Image.open(io.BytesIO(p)).convert("RGBA"), (344, 430)) for p in posters[1:3]]
    places = [((50, 110), big, 0), ((694, 250), small[0] if small else None, 3),
              ((660, 730), small[1] if len(small) > 1 else None, -3)]
    for (x, y), img, angle in places:
        if img is None:
            continue
        img = img.copy()
        img.putalpha(_rounded_mask(img.size, 22))
        if angle:
            img = img.rotate(angle, resample=Image.BICUBIC, expand=True)
        _shadow(canvas, (x + 10, y + 10, x + img.width - 10, y + img.height - 10), radius=26, opacity=90)
        canvas.alpha_composite(img, (x, y))
    _heading(canvas, "Post ideas for", lead["business_name"], (11, 27, 43), x=60, bottom=H - 150, max_w=560)
    _label(canvas, f"Sample posts for {lead['business_name']} · by Raswal", (11, 27, 43), max_w=560)
    return canvas


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


# ---------------------------------------------------------------- public API

def template_paths(c: Candidate, cfg) -> list[Path]:
    tpl = cfg.subcategories[c.subcategory].template
    if c.track == "content":
        return [TEASERS_DIR / "content" / tpl / f"poster-{i}.html" for i in (1, 2, 3)]
    return [TEASERS_DIR / "web" / tpl / "index.html"]


def render_teasers(cands: list[Candidate], cfg) -> dict[str, bytes]:
    """Render teasers for the given candidates. Returns place_id → JPEG bytes (failures omitted)."""
    rc = cfg.budget.render
    cands = cands[: rc.max_per_night]
    shots: list[Shot] = []
    leads: dict[str, dict] = {}
    for c in cands:
        lead = lead_payload(c, cfg)
        leads[c.place_id] = lead
        paths = template_paths(c, cfg)
        missing = [p for p in paths if not p.exists()]
        if missing:
            log.error("missing teaser template(s) for %s: %s", c.subcategory, [str(p) for p in missing])
            continue
        if c.track == "content":
            for i, p in enumerate(paths):
                shots.append(Shot(f"{c.place_id}|p{i}", inject_lead(inline_template(p), lead), 1080, 1350))
        else:
            html = inject_lead(inline_template(paths[0]), lead)
            shots.append(Shot(f"{c.place_id}|desktop", html, 1440, 900))
            shots.append(Shot(f"{c.place_id}|mobile", html, 390, 844, scale=2, mobile=True))
    render_shots(shots, rc.concurrency)
    by_key = {s.key: s.png for s in shots}
    out: dict[str, bytes] = {}
    for c in cands:
        lead = leads[c.place_id]
        try:
            if c.track == "content":
                pngs = [by_key.get(f"{c.place_id}|p{i}") for i in range(3)]
                if not all(pngs):
                    continue
                img = composite_content(pngs, lead)
            else:
                dk, mb = by_key.get(f"{c.place_id}|desktop"), by_key.get(f"{c.place_id}|mobile")
                if not (dk and mb):
                    continue
                img = composite_web(dk, mb, lead)
            out[c.place_id] = to_jpeg(img, cfg)
        except Exception as e:  # noqa: BLE001
            log.error("composite failed for %s: %s", c.name, e)
    log.info("teasers: rendered %d of %d", len(out), len(cands))
    return out
