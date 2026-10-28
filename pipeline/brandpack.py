"""Phase 5 — turn a stored lead into the brand dict the demo builders expect.

`build_site.py <subcat> <brand.json>` and `build_content.py <subcat> <brand.json>`
(in the raswal-pipeline repo) both read a brand dict with the keys below. A lead only
carries the real facts we scraped (name, area, phone, colours); the editorial copy
(tagline, promise, subline, description) is derived here with deterministic, per-vertical
templates so a demo can be generated with no extra API calls. The baked templates already
supply the premium design — this only swaps in the business's own name, area and colours.
"""

from __future__ import annotations

import re

import phonenumbers

from pipeline.utils.text import display_name, slugify

# Per-subcategory editorial defaults. {name}/{area} are filled per lead.
VERTICAL = {
    "property_agency": dict(
        subline="PROPERTIES",
        tagline="Find your home in {area}.",
        promise="Verified homes, honest prices, viewings within 48 hours.",
        description="Estate agency and property management in {area}: homes for rent and sale, "
                    "letting and full management for landlords.",
        palette=("#123A5A", "#C9922B"),
    ),
    "land_developers": dict(
        subline="LAND & HOMES",
        tagline="Own land you can trust in {area}.",
        promise="Title-ready plots, transparent pricing, site visits every week.",
        description="Land sales and development in {area}: serviced plots and controlled developments "
                    "with ready title deeds and flexible payment plans.",
        palette=("#1F5132", "#C9922B"),
    ),
    "construction": dict(
        subline="BUILDERS",
        tagline="Build it right in {area}.",
        promise="Quality workmanship, clear quotes, finished on schedule.",
        description="Construction and project management in {area}: residential and commercial builds, "
                    "renovations and finishes delivered on time and on budget.",
        palette=("#273043", "#D98324"),
    ),
    "hardware_supplies": dict(
        subline="HARDWARE",
        tagline="Everything your site needs in {area}.",
        promise="Genuine stock, fair prices, fast delivery and WhatsApp ordering.",
        description="Hardware and building supplies in {area}: cement, steel, plumbing, electrical and "
                    "tools, with quick delivery and order-by-WhatsApp.",
        palette=("#8A1C1C", "#1F2937"),
    ),
    "roofing_steel": dict(
        subline="ROOFING & STEEL",
        tagline="Roofing that lasts in {area}.",
        promise="Durable sheets and steel, accurate measures, clean installs.",
        description="Roofing and steel supply in {area}: iron sheets, trusses and structural steel, "
                    "cut to size with supply-and-fix options.",
        palette=("#374151", "#D98324"),
    ),
}


def _slug_bare(name: str) -> str:
    """Business-name slug without the area suffix, for a plausible demo email domain."""
    s = re.sub(r"[^a-z0-9]+", "", display_name(name).lower()) or "business"
    return s[:24]


def _phones(e164: str | None) -> dict[str, str]:
    e164 = (e164 or "").strip()
    display = e164
    try:
        num = phonenumbers.parse(e164, "KE")
        display = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    except phonenumbers.NumberParseException:
        pass
    return {
        "phone_display": display,                       # +254 712 345 678
        "phone_tel": e164,                              # +254712345678
        "whatsapp": re.sub(r"\D", "", e164),            # 254712345678
    }


def brand_dict(bundle: dict) -> dict:
    """Map a lead bundle (lead + business + audit) to the builder's 18-key brand dict."""
    lead = bundle["lead"]
    biz = bundle.get("business") or {}
    audit = bundle.get("audit") or {}
    sub = lead["subcategory"]
    v = VERTICAL.get(sub, VERTICAL["property_agency"])

    name = display_name(biz.get("display_name") or biz.get("name") or "Business")
    area = (lead.get("area") or biz.get("area") or "Nairobi").strip()
    city = (biz.get("city") or "Nairobi").strip()
    slug = lead.get("slug") or slugify(name.lower())

    # colours: prefer what we scraped off their real site/logo, else the vertical default
    lead_brand = lead.get("brand") or {}
    colours = audit.get("colours") or {}
    primary = lead_brand.get("primary") or colours.get("primary") or v["palette"][0]
    accent = lead_brand.get("accent") or colours.get("accent") or v["palette"][1]

    bare = _slug_bare(name)
    short = " ".join(name.split()[:2]) or name
    return {
        "slug": slug,
        "name": name,
        "short": short,
        "wordmark": name.upper(),
        "subline": v["subline"],
        "tagline": v["tagline"].format(area=area),
        "promise": v["promise"],
        "description": v["description"].format(area=area),
        "city": city,
        "area": area,
        "mapsQuery": (biz.get("address") or f"{area}, {city}").strip(),
        **_phones(biz.get("phone_e164")),
        "email_display": f"hello@{bare}.co.ke",
        "email_href": f"mailto:hello@{bare}.co.ke",
        "primary": primary,
        "accent": accent,
    }
