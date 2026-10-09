"""Brand assets for teasers: logo, colours, hero image (brief §9.4). Never Google Maps photos."""

from __future__ import annotations

import io
import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from PIL import Image

from pipeline.models import Audit
from pipeline.utils.colours import (
    contrast,
    darken_for_white_text,
    hue_distance,
    is_grey,
    is_near_black,
    is_near_white,
    rgb_to_hex,
    saturation,
)

log = logging.getLogger(__name__)


def _sizes(attr: str | None) -> int:
    if not attr:
        return 0
    m = re.findall(r"(\d+)x(\d+)", attr)
    return max((min(int(a), int(b)) for a, b in m), default=0)


def logo_candidates(html: str, base_url: str) -> list[str]:
    """In order: apple-touch-icon / icon ≥128, <img> mentioning 'logo', square-ish og:image."""
    soup = BeautifulSoup(html, "lxml")
    out: list[str] = []
    for link in soup.find_all("link", href=True):
        rel = " ".join(link.get("rel") or []).lower()
        if "apple-touch-icon" in rel or ("icon" in rel and _sizes(link.get("sizes")) >= 128):
            out.append(urljoin(base_url, link["href"]))
    for img in soup.find_all("img", src=True):
        hay = " ".join([img.get("src", ""), img.get("alt", ""), " ".join(img.get("class") or []), img.get("id", "")])
        if "logo" in hay.lower():
            out.append(urljoin(base_url, img["src"]))
    og = soup.find("meta", attrs={"property": "og:image"})
    if og and og.get("content"):
        out.append("og:" + urljoin(base_url, og["content"]))
    seen, uniq = set(), []
    for u in out:
        if u not in seen and not u.lower().endswith(".svg"):
            seen.add(u)
            uniq.append(u)
    return uniq


def hero_candidates(html: str, base_url: str) -> list[tuple[str, int]]:
    soup = BeautifulSoup(html, "lxml")
    out: list[tuple[str, int]] = []
    og = soup.find("meta", attrs={"property": "og:image"})
    if og and og.get("content"):
        out.append((urljoin(base_url, og["content"]), -1))      # -1: og:image, accepted at any size
    for img in soup.find_all("img", src=True):
        if "logo" in (img.get("src", "") + img.get("alt", "") + " ".join(img.get("class") or [])).lower():
            continue
        w = img.get("width", "")
        out.append((urljoin(base_url, img["src"]), int(w) if str(w).isdigit() else 0))
    return out


def _open(data: bytes | None) -> Image.Image | None:
    if not data:
        return None
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
        return img
    except Exception:  # noqa: BLE001
        return None


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGBA").save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _jpeg(img: Image.Image, max_w: int = 1600) -> bytes:
    img = img.convert("RGB")
    if img.width > max_w:
        img = img.resize((max_w, round(img.height * max_w / img.width)))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=82)
    return buf.getvalue()


def extract_colours(img: Image.Image) -> dict[str, str] | None:
    """Quantise to 6 colours; ignore transparent, near-white, near-black and grey; primary = most saturated."""
    rgba = img.convert("RGBA")
    rgba.thumbnail((128, 128))
    data = rgba.get_flattened_data() if hasattr(rgba, "get_flattened_data") else rgba.getdata()
    px = [p for p in data if p[3] >= 128]
    if not px:
        return None
    flat = Image.new("RGB", (len(px), 1))
    flat.putdata([p[:3] for p in px])
    q = flat.quantize(colors=6, method=Image.Quantize.MEDIANCUT)
    palette = q.getpalette()[: 6 * 3]
    counts = sorted(q.getcolors() or [], reverse=True)
    colours = []
    for count, idx in counts:
        rgb = tuple(palette[idx * 3: idx * 3 + 3])
        if is_near_white(rgb) or is_near_black(rgb) or is_grey(rgb) or count < len(px) * 0.02:
            continue
        colours.append(rgb)
    if not colours:
        return None
    colours.sort(key=saturation, reverse=True)
    primary = colours[0]
    accent = next((c for c in colours[1:] if hue_distance(c, primary) >= 30), None)
    primary = darken_for_white_text(primary)
    out = {"primary": rgb_to_hex(primary)}
    if accent:
        out["accent"] = rgb_to_hex(accent)
    out["white_on_primary_contrast"] = round(contrast((255, 255, 255), primary), 2)
    return out


def find_brand_assets(a: Audit, fetcher, cfg) -> Audit:
    """Fill logo/colour/hero fields on the audit (only for sites we fetched)."""
    ac = cfg.audit
    if not a.html or not a.final_url:
        return a
    for cand in logo_candidates(a.html, a.final_url)[: ac.max_image_candidates]:
        is_og = cand.startswith("og:")
        url = cand[3:] if is_og else cand
        img = _open(fetcher.fetch_bytes(url))
        if img is None or min(img.size) < ac.logo_min_px:
            continue
        if is_og and not (0.8 <= img.width / img.height <= 1.25):
            continue
        a.logo_url, a.logo_bytes = url, _png(img)
        if colours := extract_colours(img):
            a.colours = colours
        break
    for url, width in hero_candidates(a.html, a.final_url)[: ac.max_image_candidates]:
        if 0 < width < ac.hero_min_width_px:
            continue
        img = _open(fetcher.fetch_bytes(url))
        if img is None:
            continue
        if width != -1 and img.width < ac.hero_min_width_px:
            continue
        a.hero_image_url, a.hero_bytes = url, _jpeg(img)
        break
    return a
