"""Generate the placeholder device frames (laptop.png, phone.png) and frames.json.

    .venv/bin/python teasers/frames/make_frames.py

To use your own frames: replace the PNGs (transparent where the screen is) and edit
frames.json so `screen` is the [x, y, width, height] of the screen area inside each PNG.
For the laptop, `url_bar` is where the {slug}.raswaltechsolutions.com text is drawn.
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
S = 2  # draw at 2× then downsample for smooth edges


def laptop() -> dict:
    w, h = 1000, 650
    img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([60 * S, 0, 940 * S, 604 * S], radius=30 * S, fill=(24, 28, 34, 255))       # lid
    d.rounded_rectangle([84 * S, 22 * S, 916 * S, 74 * S], radius=10 * S, fill=(238, 240, 243, 255))  # browser bar
    d.rectangle([84 * S, 60 * S, 916 * S, 74 * S], fill=(238, 240, 243, 255))
    for i, col in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        cx = (106 + i * 22) * S
        d.ellipse([cx - 7 * S, 41 * S, cx + 7 * S, 55 * S], fill=col + (255,))
    d.rounded_rectangle([250 * S, 32 * S, 750 * S, 64 * S], radius=16 * S, fill=(255, 255, 255, 255))   # url pill
    d.rectangle([84 * S, 74 * S, 916 * S, 594 * S], fill=(0, 0, 0, 0))                                # screen (transparent)
    d.polygon([(0, 604 * S), (1000 * S, 604 * S), (960 * S, 640 * S), (40 * S, 640 * S)], fill=(201, 205, 210, 255))  # base
    d.rounded_rectangle([430 * S, 604 * S, 570 * S, 616 * S], radius=6 * S, fill=(170, 175, 182, 255))
    img.resize((w, h), Image.LANCZOS).save(HERE / "laptop.png", optimize=True)
    return {"file": "laptop.png", "size": [w, h], "screen": [84, 74, 832, 520], "url_bar": [262, 32, 476, 32]}


def phone() -> dict:
    w, h = 330, 680
    img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w * S - 1, h * S - 1], radius=52 * S, fill=(17, 17, 17, 255))
    d.rounded_rectangle([14 * S, 14 * S, (w - 14) * S, (h - 14) * S], radius=40 * S, fill=(0, 0, 0, 0))
    d.rounded_rectangle([125 * S, 24 * S, 205 * S, 46 * S], radius=11 * S, fill=(17, 17, 17, 255))   # camera pill
    img.resize((w, h), Image.LANCZOS).save(HERE / "phone.png", optimize=True)
    return {"file": "phone.png", "size": [w, h], "screen": [14, 14, 302, 652], "screen_radius": 40}


if __name__ == "__main__":
    spec = {"laptop": laptop(), "phone": phone()}
    (HERE / "frames.json").write_text(json.dumps(spec, indent=1) + "\n", encoding="utf-8")
    print("frames written")
