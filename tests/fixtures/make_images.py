"""Generate fixture images and PageSpeed Insights responses (deterministic).

    .venv/bin/python tests/fixtures/make_images.py

images/logo_<RRGGBB>.png   256×256 logos (a coloured mark + a second colour, transparent background)
images/hero_<n>.jpg        1200×630 "og:image" photos (abstract buildings)
psi/psi_<profile>.json     PSI v5 responses (mobile, performance) with a final-screenshot data URL
"""

from __future__ import annotations

import base64
import io
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
LOGO_COLOURS = ["#0E6BA8", "#C0392B", "#1E8449", "#7D3C98", "#D35400", "#117A65", "#2E4053", "#B7950B"]
SECOND = {"#0E6BA8": "#F5B041", "#C0392B": "#F4D03F", "#1E8449": "#F39C12", "#7D3C98": "#48C9B0",
          "#D35400": "#2E86C1", "#117A65": "#E74C3C", "#2E4053": "#F1C40F", "#B7950B": "#1F618D"}


def hex_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def logo(colour: str) -> Image.Image:
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c1, c2 = hex_rgb(colour), hex_rgb(SECOND[colour])
    d.polygon([(128, 24), (232, 112), (24, 112)], fill=c1 + (255,))            # roof
    d.rectangle([52, 112, 204, 220], fill=c1 + (255,))                          # house
    d.rectangle([108, 150, 148, 220], fill=c2 + (255,))                         # door
    d.rectangle([66, 128, 96, 156], fill=(255, 255, 255, 255))
    d.rectangle([160, 128, 190, 156], fill=(255, 255, 255, 255))
    d.ellipse([196, 36, 236, 76], fill=c2 + (255,))                             # sun / accent
    return img


def hero(n: int) -> Image.Image:
    r = random.Random(n)
    w, h = 1200, 630
    sky = [(70, 130, 180), (230, 150, 90), (90, 160, 140)][n - 1]
    img = Image.new("RGB", (w, h), sky)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        d.line([(0, y), (w, y)], fill=tuple(int(c * (1 - 0.45 * t) + 255 * 0.15 * t) for c in sky))
    x = 0
    while x < w:
        bw, bh = r.randint(70, 160), r.randint(180, 520)
        shade = r.randint(40, 110)
        d.rectangle([x, h - bh, x + bw, h], fill=(shade, shade + 10, shade + 20))
        for wy in range(h - bh + 20, h - 20, 28):
            for wx in range(x + 10, x + bw - 14, 22):
                if r.random() < 0.7:
                    d.rectangle([wx, wy, wx + 10, wy + 14], fill=(240, 220, 150) if r.random() < 0.4 else (200, 210, 220))
        x += bw + r.randint(4, 18)
    return img.filter(ImageFilter.SMOOTH)


def screenshot(kind: str) -> str:
    """A 412×823 phone screenshot of a generic site, as a JPEG data URL (like PSI's final-screenshot)."""
    w, h = 412, 823
    img = Image.new("RGB", (w, h), (250, 250, 250))
    d = ImageDraw.Draw(img)
    top = {"fast": (20, 60, 110), "medium": (120, 120, 120), "medium_good": (30, 90, 60), "slow": (160, 40, 40)}[kind]
    d.rectangle([0, 0, w, 70], fill=top)
    d.rectangle([16, 20, 120, 50], fill=(255, 255, 255))
    if kind == "slow":                       # desktop layout shrunk down: tiny text columns
        for y in range(90, h - 40, 14):
            d.line([(12, y), (w - 12 - (y % 70), y)], fill=(170, 170, 170), width=4)
    else:
        d.rectangle([0, 70, w, 330], fill=tuple(min(255, c + 90) for c in top))
        d.rectangle([24, 260, 200, 300], fill=top)
        for y in range(360, h - 40, 34):
            d.line([(24, y), (w - 24 - (y % 90), y)], fill=(160, 160, 160), width=10)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=60)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


PSI_PROFILES = {
    "fast": dict(score=0.91, lcp=1850.4, fcp=1210.2, tbt=40, cls=0.01, si=2100.5),
    "medium_good": dict(score=0.74, lcp=3320.7, fcp=1800.3, tbt=180, cls=0.05, si=3400.1),
    "medium": dict(score=0.55, lcp=4610.2, fcp=2400.9, tbt=420, cls=0.08, si=5100.4),
    "slow": dict(score=0.27, lcp=8420.6, fcp=4300.1, tbt=1350, cls=0.21, si=9800.7),
}


def psi(profile: str) -> dict:
    p = PSI_PROFILES[profile]

    def metric(id_, title, value, unit, score):
        disp = f"{value / 1000:.1f} s" if unit == "ms" and value >= 1000 else (
            f"{value:.0f} ms" if unit == "ms" else f"{value:.3f}")
        return {"id": id_, "title": title, "score": score, "scoreDisplayMode": "numeric", "displayValue": disp,
                "numericValue": value, "numericUnit": "millisecond" if unit == "ms" else "unitless"}

    return {
        "captchaResult": "CAPTCHA_NOT_NEEDED",
        "kind": "pagespeedonline#result",
        "id": "https://example.co.ke/",
        "loadingExperience": {"initial_url": "https://example.co.ke/"},
        "lighthouseResult": {
            "requestedUrl": "https://example.co.ke/",
            "finalUrl": "https://example.co.ke/",
            "lighthouseVersion": "12.8.2",
            "userAgent": "Mozilla/5.0 (Linux; Android 11; moto g power (2022)) AppleWebKit/537.36 Chrome-Lighthouse",
            "fetchTime": "2026-10-09T18:41:02.123Z",
            "environment": {"networkUserAgent": "Mozilla/5.0 Chrome-Lighthouse", "hostUserAgent": "HeadlessChrome",
                            "benchmarkIndex": 1180},
            "runWarnings": [],
            "configSettings": {"emulatedFormFactor": "mobile", "formFactor": "mobile", "locale": "en-US",
                               "onlyCategories": ["performance"], "channel": "lr"},
            "audits": {
                "first-contentful-paint": metric("first-contentful-paint", "First Contentful Paint", p["fcp"], "ms", None),
                "largest-contentful-paint": metric("largest-contentful-paint", "Largest Contentful Paint", p["lcp"], "ms", None),
                "total-blocking-time": metric("total-blocking-time", "Total Blocking Time", p["tbt"], "ms", None),
                "cumulative-layout-shift": metric("cumulative-layout-shift", "Cumulative Layout Shift", p["cls"], "", None),
                "speed-index": metric("speed-index", "Speed Index", p["si"], "ms", None),
                "final-screenshot": {"id": "final-screenshot", "title": "Final Screenshot", "score": None,
                                     "scoreDisplayMode": "informative",
                                     "details": {"type": "screenshot", "timing": p["lcp"] + 400,
                                                 "timestamp": 2468101214, "data": screenshot(profile)}},
            },
            "categories": {"performance": {"id": "performance", "title": "Performance", "score": p["score"],
                                           "auditRefs": [{"id": "largest-contentful-paint", "weight": 25}]}},
            "timing": {"total": 14231.5},
        },
        "analysisUTCTimestamp": "2026-10-09T18:41:02.123Z",
    }


def main() -> None:
    (HERE / "images").mkdir(exist_ok=True)
    (HERE / "psi").mkdir(exist_ok=True)
    for c in LOGO_COLOURS:
        logo(c).save(HERE / "images" / f"logo_{c.lstrip('#').upper()}.png", optimize=True)
    for n in (1, 2, 3):
        hero(n).save(HERE / "images" / f"hero_{n}.jpg", "JPEG", quality=70, optimize=True)
    for prof in PSI_PROFILES:
        (HERE / "psi" / f"psi_{prof}.json").write_text(json.dumps(psi(prof), indent=1) + "\n", encoding="utf-8")
    print("images and PSI fixtures written")


if __name__ == "__main__":
    main()
