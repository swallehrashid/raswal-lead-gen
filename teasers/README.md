# Teaser templates

Every lead gets a 1080×1350 JPEG teaser rendered from the HTML in this folder:

| Track | Template(s) | Rendered at | Composite |
|---|---|---|---|
| Website | `web/<template>/index.html`: the hero section of that subcategory's website template | 1440×900 (desktop) **and** 390×844 @2x (mobile) | laptop + phone frames on the brand colour |
| Content | `content/<template>/poster-1.html`, `poster-2.html`, `poster-3.html` | 1080×1350 each | one large + two small posters |

`<template>` is the `template:` value of the subcategory in `config/subcategories.yaml` (it defaults to the key).
**The files here now are placeholders** in Raswal colours, so rendering works today. Swap in your real ones as below.

## The contract (brief §13.1)

1. **`window.LEAD`.** The renderer injects `<script>window.LEAD = {...}</script>` as the first thing in `<head>`. Fields:

   | Field | Example | Notes |
   |---|---|---|
   | `business_name` | `Kilima Homes` | display name (legal suffix dropped) |
   | `area` | `Kilimani` | |
   | `logo_data_url` | `data:image/png;base64,...` or `null` | `null` → show a **wordmark** of `business_name` |
   | `primary`, `accent` | `#0F3D5E`, `#D4970F` | from their logo, else the subcategory's `default_palette` |
   | `hero_image_data_url` | `data:image/jpeg;base64,...` or `null` | their og:image / big site image; `null` → your default art |
   | `headline` | `Homes to rent & buy in Kilimani` | from config, makes no claims |
   | `subline` | `Homes to rent and buy, with viewings…` | from config, makes no claims |
   | `poster_lines` | `["Book a viewing on WhatsApp", …]` | 3 lines (Gemini, validated, or generic) |
   | `phone_display` | `0722 123456` | their listing number |
   | `preview_domain` | `kilima-homes.raswaltechsolutions.com` | |
   | *extras* `ink`, `bg`, `cta`, `nav`, `subcategory`, `track` | | optional, use if helpful |

2. **CSS variables.** Use `--brand-primary`, `--brand-accent`, `--brand-ink` and `--brand-bg` for every brand colour. `shared/lead.js` sets them from `window.LEAD`.
3. **No external requests.** No Google Fonts, CDNs, analytics or remote images. The renderer blocks network requests and logs a warning naming the template. Fonts must be base64 (`shared/fonts.css`).
4. **Relative files are fine.** `<link rel="stylesheet" href="…">`, `<script src="…">`, `<img src="…">` and CSS `url(…)` pointing at **relative paths** are inlined automatically at render time (images become data URLs). So you can keep images next to the template, e.g. `web/property_agency/hero-default.jpg`.

## Swapping in your real website hero

For each subcategory (repeat for all five):

1. Open your finished website template and copy **just the hero**: header/nav + the first screen. Paste it into `web/<template>/index.html`, replacing the placeholder `<body>` content. Keep these lines from the placeholder:
   ```html
   <link rel="stylesheet" href="../../shared/fonts.css">
   <link rel="stylesheet" href="../../shared/tokens.css">
   …your CSS (inline <style> or a relative <link>)…
   …
   <script src="../../shared/lead.js"></script>   <!-- last thing in <body> -->
   ```
2. Replace hard-coded content with hooks (`lead.js` fills them):
   - business name: `<span data-lead="business_name"></span>`
   - logo: `<div class="logo" data-lead="logo"></div>` (it becomes an `<img>`, or `<span class="wordmark">` when there's no logo; style both)
   - headline / subline: `data-lead="headline"`, `data-lead="subline"`
   - area, phone, preview domain: `data-lead="area"`, `data-lead="phone_display"`, `data-lead="preview_domain"`
   - hero image box: `data-lead="hero"` (gets `background-image` and class `has-hero`, or class `no-hero`, in which case show your default image/art)
   - nav links (optional): `<span data-lead="nav"></span>`
3. Replace your template's colours with `var(--brand-primary)`, `var(--brand-accent)`, `var(--brand-ink)` and `var(--brand-bg)`.
4. Fonts: if the template uses other fonts, put the `.woff2` files in `shared/fonts/`, add them to `FACES` in `shared/build_fonts.py`, run it, and use the family names in your CSS.
5. Make sure the hero looks right at **1440×900** and at **390 px wide** (mobile). The renderer screenshots the top of the page only.

Or write your own binding: `window.LEAD` is a plain object, so any inline script can read it.

## Swapping in your real posters

Same steps for `content/<template>/poster-1.html` … `poster-3.html`. Each page should be exactly **1080×1350** (`html, body { width:1080px; height:1350px; overflow:hidden }`). Use `data-lead="poster_line" data-index="0|1|2"` for the three lines. Poster copy comes only from `poster_lines` (validated: no prices, invented numbers or claims).

## Check your work

```bash
.venv/bin/python -m pipeline rerender --offline            # all five subcategories → out/teasers/samples/
.venv/bin/python -m pipeline rerender --offline --subcategory construction
.venv/bin/pytest -m render tests/test_teaser.py            # contract: renders, no external requests
```
You can also open any template file directly in Chrome: the preview `window.LEAD` inside each file is used when no lead is injected.

## Device frames

`frames/laptop.png` and `frames/phone.png` are placeholders drawn by `frames/make_frames.py`. To use real mockup frames, replace the PNGs (the screen area must be transparent) and update `frames/frames.json`:
- `screen`: `[x, y, width, height]` of the screen inside the PNG
- `url_bar` (laptop): where `{slug}.raswaltechsolutions.com` is written
- `screen_radius` (phone): corner radius of the screen

## Renaming a subcategory

Change the key in `config/subcategories.yaml` and keep `template:` pointing at the existing folder, or rename the folders here to match and update `template:`.
