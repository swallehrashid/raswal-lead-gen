"""Colour helpers: hex/RGB, saturation, hue distance, WCAG contrast (brief §9.4)."""

from __future__ import annotations

import colorsys


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_to_hex(rgb) -> str:
    return "#{:02X}{:02X}{:02X}".format(*(max(0, min(255, int(round(c)))) for c in rgb[:3]))


def _lin(c: float) -> float:
    c = c / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb) -> float:
    r, g, b = rgb[:3]
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(a, b) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def hls(rgb) -> tuple[float, float, float]:
    r, g, b = (c / 255 for c in rgb[:3])
    return colorsys.rgb_to_hls(r, g, b)


def saturation(rgb) -> float:
    """HSV saturation weighted so very dark or very light colours rank lower."""
    r, g, b = (c / 255 for c in rgb[:3])
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return s * min(1.0, v * 1.4)


def hue_distance(a, b) -> float:
    ha, hb = hls(a)[0], hls(b)[0]
    d = abs(ha - hb)
    return min(d, 1 - d) * 360


def is_near_white(rgb, threshold: int = 235) -> bool:
    return min(rgb[:3]) >= threshold


def is_near_black(rgb, threshold: int = 30) -> bool:
    return max(rgb[:3]) <= threshold


def is_grey(rgb, tol: int = 14) -> bool:
    return max(rgb[:3]) - min(rgb[:3]) <= tol


def darken_for_white_text(rgb, min_ratio: float = 4.5) -> tuple[int, int, int]:
    """Darken (lower HLS lightness) until white text on it reaches min_ratio."""
    white = (255, 255, 255)
    h, l, s = hls(rgb)
    cur = tuple(rgb[:3])
    while contrast(white, cur) < min_ratio and l > 0.02:
        l -= 0.02
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        cur = (round(r * 255), round(g * 255), round(b * 255))
    return cur
