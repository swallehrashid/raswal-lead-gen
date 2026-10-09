"""Generate the PWA icons (navy square, gold R). Run: ../.venv/bin/python scripts/make_icons.py"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FONT = HERE.parent.parent / "teasers" / "shared" / "fonts" / "montserrat-latin-800-normal.woff"
NAVY, GOLD, CYAN = (2, 20, 34), (212, 151, 15), (58, 149, 194)


def icon(size: int, maskable: bool) -> Image.Image:
    img = Image.new("RGB", (size, size), NAVY)
    d = ImageDraw.Draw(img)
    scale = 0.5 if maskable else 0.62
    f = ImageFont.truetype(str(FONT), int(size * scale))
    box = d.textbbox((0, 0), "R", font=f)
    w, h = box[2] - box[0], box[3] - box[1]
    d.text(((size - w) / 2 - box[0], (size - h) / 2 - box[1] - size * 0.02), "R", font=f, fill=GOLD)
    bar = size * (0.16 if maskable else 0.1)
    d.rectangle([size / 2 - bar, size * (0.78 if maskable else 0.84), size / 2 + bar, size * (0.80 if maskable else 0.865)],
                fill=CYAN)
    return img


out = HERE.parent / "public" / "icons"
for s in (192, 512):
    icon(s, False).save(out / f"icon-{s}.png", optimize=True)
icon(512, True).save(out / "maskable-512.png", optimize=True)
icon(180, False).save(out / "apple-touch-icon.png", optimize=True)
icon(64, False).save(out / "favicon.png", optimize=True)
print("icons written")
