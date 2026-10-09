# Raswal Lead Generator — Project Brief

**For:** Claude Code
**Owner:** Swalleh Rashid, Raswal Tech Solutions (Nairobi, Kenya)
**Version:** 1.0, 9 October 2026
**First live list needed:** Monday 12 October 2026

---

## 0. How to use this brief

- Read the whole brief before writing code.
- Build in the milestone order in §17. M0–M5 is the "Monday minimum".
- Every tunable value (queries, areas, weights, thresholds, caps, message rules, holidays) lives in `config/*.yaml`. No magic numbers in code.
- Do not deviate from the hard constraints in §2 without asking Swalleh first.
- The five subcategory names in §5 are **working names**. Swalleh will rename them to match his five templates, and only `config/subcategories.yaml` should need to change.

---

## 1. What we are building

A nightly job plus a small private dashboard that delivers a short list of **strictly qualified** Kenyan real estate and construction businesses each weekday.

**Each night the job:**
1. Finds candidate businesses on Google Maps (Places API).
2. Audits their web presence.
3. Disqualifies poor fits.
4. Scores and routes the rest into two tracks.
5. For each finalist, prepares a verified fact sheet, a tailored WhatsApp caption and a teaser image.

**The two tracks:**
- **Website track (target 20/day):** no website, or a poor one. Pitch: a premium website. Teaser: a mockup of *their* website.
- **Content track (target 10/day):** a decent website but weak social or content. Pitch: posters, videos and infographics, per piece or on retainer. Teaser: 2–3 posters in *their* branding.

**Each morning Swalleh:**
1. Reviews about 40 candidates in the dashboard (10–15 minutes).
2. Approves up to 30 and sends them manually on WhatsApp: image plus caption, from 0114 129 809.
3. Tracks replies, follow-ups, demos and wins in the same dashboard.

**When a lead says yes,** the dashboard exports a **lead pack** (JSON plus assets) for Swalleh's separate web-demo and content-demo repos. Those repos turn it into a live preview link on a `*.raswaltechsolutions.com` subdomain. Those repos are **out of scope** here.

**Success is quality, not volume.** The metrics that matter are positive reply rate, demo rate and deposit rate, per subcategory and per track. A day with 22 strong leads beats 30 with 8 weak ones. **Never lower the bar to reach 30.**

---

## 2. Hard constraints

1. **Zero recurring cost.** Free tiers only, with hard budget guards in code (§6.4) and in Google Cloud quotas.
2. **No automated WhatsApp sending.**
   - No unofficial WhatsApp libraries (whatsapp-web.js, Baileys, etc.).
   - No WhatsApp Cloud API template blasting.
   - Swalleh sends every message by hand.
3. **No scraping Google Maps HTML, Facebook, Instagram or TikTok.** Use the Places API for Maps data and plain HTTP fetches of the business's *own* website only.
4. **Kenya only.**
5. **Facts only.** Every specific claim in a message or teaser must trace back to a stored, verifiable fact (§11). An LLM output that contains an unverifiable specific is rejected.
6. **Not on Swalleh's VPS.**
   - The job runs on GitHub Actions.
   - Data and auth live in Supabase (free plan).
   - The dashboard is a static build on Swalleh's existing Nova Host shared hosting.

### 2.1 Free-tier budget

Free allowances change, so re-check them during setup.

| Service | Used for | Free allowance (verify) | Our budget |
|---|---|---|---|
| Google Places API (New): Text Search **Enterprise + Atmosphere** SKU | Discovery: name, phone, website, rating, review count, up to 5 reviews | 1,000 billable calls/month. Each call returns up to 20 places. | ≤ 40 calls/night, ≤ 900/month, hard-stopped in code |
| PageSpeed Insights API v5 | Mobile performance plus final screenshot of their current site | 25,000 queries/day | ≤ 150/night |
| Gemini API (Flash) | Review themes, message drafts, poster lines | Free tier. Roughly 10 RPM / 250 RPD for 2.5 Flash per Google's docs; varies by model. | 1 call per finalist, ≤ 60/night, throttled to ≤ 6 RPM |
| Supabase Free | Postgres, Auth (magic link), Storage | 500 MB DB, 1 GB files. **Pauses after 7 days of inactivity.** | Daily heartbeat (§16) plus retention purge (§14.4) |
| GitHub Actions (private repo) | Nightly pipeline, deploys, CI | 2,000 minutes/month on GitHub Free | About 30–35 min/night, about 800 min/month |
| Nova Host (already paid) | Static dashboard at `leads.raswaltechsolutions.com` | n/a | n/a |

---

## 3. Architecture

```
GitHub Actions — nightly, Sun–Thu ~21:30 EAT (plus manual "Run workflow")
  pipeline/ (Python 3.12)
    plan → discover → normalise → gate → enrich (site audit, PSI, socials, logo, colours)
         → score → select (20 web + 10 content + reserves)
         → facts → Gemini (review themes + 2 caption variants + poster lines) → validate
         → teaser render (Playwright + Pillow) → upload
            │  service-role key
            ▼
Supabase: Postgres (+RLS) · Storage (private bucket) · Auth (magic link, one allowed email)
            ▲  anon key + user session
            │
Dashboard — React + Vite + Tailwind, static build, installable PWA
  deployed by FTP to Nova Host → https://leads.raswaltechsolutions.com
            │  wa.me / web.whatsapp.com / phone share sheet / copy-to-clipboard
            ▼
WhatsApp — sent by hand from 0114 129 809
            │  lead says yes → "Send to demo" → lead pack JSON + assets
            ▼
web-demo repo · content-demo repo  (OUT OF SCOPE)
```

---

## 4. Repository layout

```
raswal-lead-generator/
├── README.md
├── docs/
│   ├── PROJECT_BRIEF.md          ← this file
│   ├── DAILY_PLAYBOOK.md
│   └── SETUP_CHECKLIST.md
├── config/
│   ├── subcategories.yaml        # 5 subcategories: weekday, queries, area tiers, ICP knobs
│   ├── areas.yaml                # area lists + lat/lng centres + radius, by tier
│   ├── exclusions.yaml           # brand seed list, name patterns, place types, keywords
│   ├── scoring.yaml              # gates, weights, bands, thresholds, daily targets
│   ├── messaging.yaml            # tone rules, sign-off, banned phrases, follow-up + quick-reply templates
│   ├── budget.yaml               # API caps per night / per month
│   └── calendar.yaml             # send days, Kenyan public holidays, wind-down dates
├── pipeline/
│   ├── __main__.py               # CLI (see §16.3)
│   ├── settings.py               # loads env + YAML, pydantic models
│   ├── plan.py                   # picks the subcategory + search cells for tonight
│   ├── discover.py               # Places Text Search (New), pagination, budget guard
│   ├── normalise.py              # phones, names, areas, dedupe, branch detection
│   ├── gates.py                  # hard disqualifiers (returns reason codes)
│   ├── audit_site.py             # HTTP fetch + HTML checks + site_status classification
│   ├── psi.py                    # PageSpeed Insights (mobile), screenshot extraction
│   ├── brand.py                  # logo discovery, colour extraction, hero image pick
│   ├── score.py                  # website + content scoring with breakdowns
│   ├── select.py                 # top-N per track, diversity rules, reserves
│   ├── facts.py                  # deterministic fact extraction (§11)
│   ├── llm.py                    # Gemini client, JSON-schema output, throttling
│   ├── draft.py                  # prompt building + 2 variants per lead
│   ├── validate.py               # message validator (§12.5) + deterministic fallback
│   ├── teaser.py                 # Playwright render + Pillow composite
│   ├── store.py                  # Supabase client: upserts, storage uploads, usage counters
│   ├── budget.py                 # call counters, nightly/monthly caps, abort logic
│   └── utils/ (http.py, text.py, dates.py, colours.py)
├── teasers/
│   ├── web/<subcategory>/index.html       # hero section of that subcategory's website template
│   ├── content/<subcategory>/poster-1.html, poster-2.html, poster-3.html
│   ├── frames/ (laptop.png, phone.png)    # device frames for compositing
│   └── shared/ (fonts as base64 CSS, tokens.css)
├── dashboard/                    # React + Vite + Tailwind + supabase-js, PWA
├── supabase/
│   ├── migrations/*.sql          # schema, enums, RLS, storage policies
│   └── seed.sql                  # admin email, settings, initial search cells
├── tests/
│   ├── fixtures/ (places_*.json, sites/*.html, psi_*.json)
│   └── test_*.py
└── .github/workflows/
    ├── nightly.yml
    ├── heartbeat.yml
    ├── deploy-dashboard.yml
    └── ci.yml
```

**Python dependencies:**
- `httpx`, `tenacity`
- `phonenumbers`
- `beautifulsoup4`, `lxml`
- `pydantic`, `pyyaml`
- `supabase`
- `google-genai`
- `playwright`, `pillow`
- `tldextract`, `rapidfuzz`
- `python-dateutil`
- `pytest`

**Dashboard dependencies:** React, Vite, Tailwind, `@supabase/supabase-js`, `vite-plugin-pwa`.

---

## 5. Subcategories, themed days and search plan

One subcategory per weekday. The list for date **D** is built on the evening before D: Sunday night builds Monday's list, and Thursday night builds Friday's.

| List day | Key (working name) | Covers | Example query templates |
|---|---|---|---|
| Mon | `property_agency` | Estate and letting agents, property managers, house sales | `real estate agency in {area}`, `property management company in {area}`, `letting agents {area}` |
| Tue | `land_developers` | Land-selling companies, small and mid-size developers | `land for sale company {area}`, `real estate developers {area}`, `plots for sale {area}` |
| Wed | `construction` | Building contractors, renovation, interior fit-out | `building contractors {area}`, `construction company {area}`, `renovation contractors {area}` |
| Thu | `hardware_supplies` | Hardware shops, plumbing suppliers, paint and tile shops | `hardware shop {area}`, `plumbing supplies {area}`, `paint shop {area}`, `tiles shop {area}` |
| Fri | `roofing_steel` | Mabati and roofing suppliers, steel suppliers, fabricators | `mabati roofing sheets {area}`, `steel suppliers {area}`, `roofing company {area}` |

### 5.1 Area tiers

Start with Nairobi, then move outwards. Each area in `config/areas.yaml` has a centre lat/lng and a radius.

**Tier 1: Nairobi core (property and land offices)**
- Westlands, Parklands, Kilimani, Kileleshwa, Lavington
- Upper Hill, CBD, Ngong Road, Karen, Lang'ata
- South B, South C, Kasarani/Roysambu (Thika Road), Embakasi, Runda/Gigiri

**Tier 1: Nairobi core (hardware, roofing and steel)**
- Kirinyaga Road (CBD), Industrial Area, Mombasa Road, Kariobangi, Kangemi
- Githurai, Kahawa, Ngong Road, Embakasi, Kasarani

**Tier 2: Nairobi metro**
- Ruaka, Kiambu Road, Ruiru, Juja, Thika, Kikuyu, Limuru
- Syokimani/Mlolongo, Athi River, Kitengela, Isinya
- Rongai, Ngong, Kiserian, Kamulu/Joska

**Tier 3: Other towns (disabled by default)**
- Nakuru, Mombasa, Kisumu, Eldoret, Nyeri, Machakos, Naivasha, Nanyuki, Meru

### 5.2 Search-cell rotation

A **search cell** is one combination of (subcategory, query template, area).

The `search_cells` table tracks for each cell:
- `last_run`
- `pages_fetched`
- `new_place_ratio`
- `exhausted`

**Nightly plan for the target subcategory:**
1. Order cells by `(tier, last_run ASC NULLS FIRST)`.
2. For each cell, fetch page 1.
3. Fetch page 2 or 3 only if the previous page's new-place ratio is ≥ 0.5 (a "new place" is a `place_id` never seen before).
4. Stop when either:
   - unique new candidates reach `target_raw` (default 350), or
   - the nightly call cap is reached.
5. Mark a cell `exhausted` after 2 consecutive runs with less than 20% new places.

**Tier progression:**
- When every tier-1 cell for a subcategory is exhausted, start using tier 2.
- Tier 3 stays off until `tier3_enabled: true` is set for that subcategory.
- The dashboard shows a banner when a subcategory is running low.

---

## 6. Discovery (Google Places API, New)

### 6.1 Request

`POST https://places.googleapis.com/v1/places:searchText`

**Headers:**
- `X-Goog-Api-Key`
- `X-Goog-FieldMask`

**Body:**
- `textQuery`
- `regionCode: "KE"`
- `languageCode: "en"`
- `pageSize: 20`
- `locationBias.circle`: the area centre and radius
- `pageToken` when paginating

**Field mask (keep exactly this; adding fields can change the billed SKU):**
```
places.id,places.displayName,places.formattedAddress,places.location,places.types,
places.primaryType,places.businessStatus,places.googleMapsUri,places.nationalPhoneNumber,
places.internationalPhoneNumber,places.websiteUri,places.rating,places.userRatingCount,
places.reviews,nextPageToken
```

### 6.2 Billing

- Billing is **per request (page)**, not per place returned. An empty page still costs one call.
- This mask is expected to bill as **Text Search Enterprise + Atmosphere**.
- The setup checklist includes confirming this in Cloud Billing reports after the first test run.

### 6.3 Places API data handling

- Store `place_id` permanently.
- Store the raw Places payload in `places_raw`, and purge it after 30 days (§14.4).
- Lead and CRM rows keep only the contact fields needed to work the lead.

### 6.4 Budget guard (`budget.py`)

Every external call increments `api_usage(month, api, sku, count)`. Before each Places call, check:
- nightly Places calls < `places_calls_per_night` (default 40)
- monthly Places calls < `places_calls_per_month` (default 900)

If either cap is hit, stop discovery cleanly and continue the pipeline with what was found.

The same pattern applies to:
- PSI: `psi_calls_per_night` = 150
- Gemini: `gemini_calls_per_night` = 60, `gemini_rpm` = 6

---

## 7. Normalisation and dedupe

### 7.1 Phones

- Parse with `phonenumbers` (region `KE`) and store `phone_e164` and `phone_type`.
- Accept only `MOBILE` or `FIXED_LINE_OR_MOBILE`.
- `FIXED_LINE` numbers (e.g. 020…) fail the gate, because they can't receive WhatsApp.

### 7.2 Names

- Store `name_norm`: lowercase, strip punctuation, collapse "limited/ltd/co." into a canonical form.

### 7.3 Dedupe

1. **By `place_id`.**
2. **By `phone_e164`, across all time.** A phone ever contacted, or in `suppression`, is never shortlisted again.
3. **By near-duplicate name** (rapidfuzz ratio ≥ 92) within 2 km. Keep the listing with more reviews.

### 7.4 Branch detection

The same `name_norm` at different locations means a multi-branch business. Set `branch_count`; it raises the ability-to-pay score.

### 7.5 Shared phone

If one mobile number appears on 3 or more listings with building-like names, it is probably an agent or property manager listing their buildings.
- Collapse those listings into one lead.
- Keep the most business-like name.
- Set `manages_listings = n`. This counts as a positive signal for `property_agency`.

---

## 8. Hard gates (auto-reject)

`gates.py` returns a list of reason codes. Any code means the business is rejected. Codes are stored so the weekly review can see what was filtered.

| Code | Rule |
|---|---|
| `NOT_OPERATIONAL` | `businessStatus` ≠ `OPERATIONAL` |
| `NO_MOBILE` | No phone, invalid number, or fixed line only |
| `SUPPRESSED` | Phone or `place_id` in `suppression` (opt-outs, existing clients, manual list) |
| `ALREADY_CONTACTED` | Phone or `place_id` has ever been sent a message |
| `EXCLUDED_TYPE` | Types include `apartment_building`, `apartment_complex`, `condominium_complex`, `housing_complex`, `lodging`, `hotel`, `motel`, `guest_house`, `hostel`, `bed_and_breakfast`, `extended_stay_hotel`, `shopping_mall`, `school`, `church`, `local_government_office` |
| `BUILDING_NOT_BUSINESS` | Name matches a building pattern (`apartments`, `court`, `heights`, `residence(s)`, `residency`, `suites`, `towers`, `villas`, `gardens`, `plaza`, `mall`, or `estate` without `agent`) **and** contains no business word (`agency`, `agents`, `realty`, `realtors`, `properties`, `property management`, `homes ltd`, `investments`, `land`, `developers`, `construction`, `builders`, `contractors`, `hardware`, `steel`, `roofing`, `mabati`, `paints`, `plumbing`, `ltd`, `limited`, `enterprises`, `company`) |
| `BIG_BRAND` | Name matches `exclusions.yaml → brands` (see below) and has no dealer or stockist words |
| `PORTAL_OR_CLASSIFIED` | Name or domain matches listing portals and classifieds (`exclusions.yaml → portals`) |
| `GOV_NGO` | Government, county, authority, board, NGO or church keywords |
| `TOO_SMALL` | `userRatingCount` < `min_reviews[subcategory]` (default 8; hardware 10) |
| `DORMANT` | No review in the last 365 days, or no reviews returned |
| `LOW_RATING` | `rating` < 3.5 |
| `NO_HOOK` | After enrichment and facts, fewer than 1 *strong* fact (§11). Evaluated last. |

**Brand seed list** in `exclusions.yaml`. Swalleh will extend it; match case-insensitively on `name_norm`:
- Large agencies and developers: Knight Frank, HassConsult, Pam Golding, Lloyd Masika, Cytonn, Optiven, Username Investments, Centum, Superior Homes, Tatu City
- Manufacturers and brands: Mabati Rolling Mills, Safal, Devki, Crown Paints, Basco, Sadolin, Tile & Carpet
- International contractors: China Road and Bridge, China Wu Yi

**Dealer and stockist words** (the brand name plus one of these is *allowed*): `dealer`, `stockist`, `distributor`, `agent`, `hardware`, `centre`, `shop`, `depot`, `enterprises`.

---

## 9. Enrichment (website audit)

Run enrichment only on candidates that pass the cheap gates. Order them by a **pre-score** based on reviews, recency and rating, and enrich the top `enrich_limit` (default 150).

### 9.1 Site fetch (`audit_site.py`)

- `httpx`, 15 s timeout, follow redirects (maximum 5), a real browser User-Agent.
- Try `https://` first, then `http://`.

**Record:**
- `final_url`, `status_code`
- `https_ok`, `cert_error`
- `redirect_chain`
- `html_bytes`, `title`
- `meta_viewport`
- `copyright_year` (regex on footer text: the latest `©`/`copyright` year)
- `has_whatsapp_link` (`wa.me`, `api.whatsapp.com`, `whatsapp://`)
- `has_tel_link`
- `platform` (Wix, WordPress, Squarespace, Webflow, Shopify, custom, from markers)
- `social_links` (Facebook, Instagram, TikTok, YouTube, LinkedIn, X)
- `has_video` (`<video>` or YouTube/Vimeo/TikTok embeds)
- `blog_last_date` (if a blog/news page is linked and dates are parseable)

### 9.2 `site_status` classification

Apply the first rule that matches, in this order.

| `site_status` | Detection | Track |
|---|---|---|
| `none` | No `websiteUri` | Website |
| `social_as_site` | Domain is facebook.com, instagram.com, tiktok.com, linktr.ee, wa.me, x.com, or a Google Maps link | Website |
| `dead` | DNS failure, connection error, 4xx/5xx, or a parked/expired page (markers: "domain for sale", "this domain has expired", "account suspended", cPanel/Hostinger/Nova Host default pages, "Index of /", "coming soon" with under 2 KB of text), or a redirect into `business.site` (Google Business Profile websites were shut down in 2024, so those redirects now end in an error) | Website |
| `insecure` | HTTPS fails or certificate invalid, site only on HTTP | Website |
| `free_builder` | Served on a free subdomain: `wixsite.com`, `wordpress.com`, `blogspot.com`, `weebly.com`, `godaddysites.com`, `site123.me`, `webnode.page`, etc. | Website |
| `weak` | At least 2 of: PSI mobile performance < 50; no viewport meta; `copyright_year` ≤ current year − 3; no WhatsApp link; no `tel:` link; under 300 words of visible text on the homepage | Website |
| `good` | Everything else | Content |

### 9.3 PageSpeed Insights (`psi.py`)

**When:** only for `weak`/`good`/`free_builder`/`insecure` sites that are still in contention after pre-scoring.

**Request:** `strategy=mobile`, `category=performance`.

**Extract:**
- `performance_score`
- LCP in seconds
- `final-screenshot` (a base64 JPEG). Store it as `current/{place_id}.jpg` so the dashboard can show their current site.

**Other rules:**
- Cache PSI results per domain for 30 days.
- Concurrency: 4.
- Retry: 2 attempts, with tenacity backoff.

### 9.4 Brand assets (`brand.py`), for teasers

**Logo**, tried in this order:
1. `<link rel="apple-touch-icon">` or an `icon` with size ≥ 128
2. An `<img>` whose src, alt, class or id contains "logo"
3. `og:image` if roughly square

The logo must be at least 96 px. If none is found, set `logo = null` and the teaser renders a **wordmark** of the business name in the template's display font.

**Never use Google Maps photos** (customers upload many of them, so ownership is unclear).

**Colours:**
- Quantise the logo to 6 colours with Pillow.
- Ignore transparent, near-white and near-black colours.
- `primary` = the most saturated remaining colour; `accent` = the next distinct hue.
- Enforce WCAG contrast ≥ 4.5 for white text on `primary` by darkening if needed.
- Fall back to the template's default palette.

**Hero image:**
- Their `og:image`, or the first `<img>` on their own site that is at least 1000 px wide.
- Otherwise, the subcategory's default template image.

---

## 10. ICP and scoring

### 10.1 Ideal customer profile (Kenya, affordability-led)

Raswal's niche template sites cost **KES 30,000–60,000+**. Content retainers start at **KES 6,000/month**, and per-piece content is also available.

The ICP is an **owner-run SME** that:
- earns enough per sale or job that KES 30–60k is clearly worth it,
- is visibly active,
- is not big enough to already have an agency.

| Subcategory | Sweet spot | Avoid | Website-track angle | Content-track angle |
|---|---|---|---|---|
| `property_agency` | Independent agencies or property managers, about 15–300 reviews, in middle and upper-middle areas, or managing several listed buildings (`manages_listings`) | National brands; solo brokers with only a personal name and under 15 reviews | Listings only on Facebook or WhatsApp, a dead or slow site, no "book a viewing" or WhatsApp button | Weekly listing posters, viewing-day videos, "why rent with us" reels |
| `land_developers` | Land companies and small or mid developers. Heavy users of Facebook ads, so they are used to spending. | The large national developers on the brand list | **Trust:** buyers fear land fraud. A credible site with a clear process, office location and site-visit booking. | Site-visit videos, plot-launch posters, buyer-education infographics |
| `construction` | Contractors and fit-out firms with a project portfolio and 15+ reviews | Large international contractors | No portfolio online, a dead or weak site, social used as the website | Before-and-after reels, project progress videos |
| `hardware_supplies` | Established hardware, plumbing, paint or tile shops with 20+ reviews, on main roads or in growth areas; multiple branches is a plus | Small kiosks, manufacturers | No online catalogue, no WhatsApp ordering, no delivery-area page | Price-list posters, new-stock posts, "how to choose" videos |
| `roofing_steel` | Mabati, roofing and steel suppliers and fabricators with 15+ reviews (Premar Roofing is the proof case) | Manufacturers | Product and gauge catalogue, quote-request form, delivery areas | Product explainer videos, project showcases |

### 10.2 Website-track score (0–100)

| Component | Points | Rule |
|---|---|---|
| **Pain** | 0–35 | `dead` 35 · `social_as_site` 30 · `insecure` 28 · `free_builder` 25 · `weak` 20 · `none` 18 |
| **Ability to pay** | 0–25 | Reviews: 8–19 → 8, 20–49 → 14, 50–149 → 20, 150–400 → 25, over 400 → 15 (probably large). Then +4 for a premium or growth area (from `areas.yaml` flags), +4 if `branch_count ≥ 2` or `manages_listings ≥ 3`, +3 for `land_developers` or `construction`. Capped at 25. |
| **Activity** | 0–20 | Newest review ≤ 30 days → 20 · ≤ 90 → 14 · ≤ 180 → 8 · ≤ 365 → 3 |
| **Reputation** | 0–10 | Rating ≥ 4.5 → 10 · 4.0–4.4 → 7 · 3.5–3.9 → 3 |
| **Hook quality** | 0–10 | 3 or more strong facts → 10 · 2 → 6 · 1 → 3 |

**Why `none` scores lower than `dead`:** a business that already paid for a website (even one that is now dead) is a proven buyer. A business with no website at all usually still has to be convinced that it needs one.

### 10.3 Content-track score (0–100)

**Gate:** `site_status = good`, or `weak` but with working HTTPS and a mobile viewport.

| Component | Points | Rule |
|---|---|---|
| **Content gap** | 0–30 | No social links on the site → 22 · links present but no Instagram or TikTok → 14 · no video on the site → +5 · blog stale over 6 months → +5. Capped at 30. |
| **Ability to pay** | 0–35 | Same review bands as the website track, scaled up (×1.4). Content is recurring revenue, so this matters more. |
| **Activity** | 0–20 | Same as the website track |
| **Reputation** | 0–10 | Same as the website track |
| **Hook quality** | 0–5 | 2 or more strong facts → 5 · 1 → 3 |

**Human check in the dashboard:** for content leads, Swalleh taps each social link and sets `social_state` to `none`, `stale`, `active` or `polished`.
- `polished` → skip (they probably already have an agency).
- `stale` or `none` → +5 on the displayed score.

### 10.4 Thresholds and selection (`select.py`)

**Thresholds:**
- `web_min_score` = 65
- `content_min_score` = 62

These are initial values, to be tuned weekly using the funnel data.

**Daily targets:**
- 20 website + 10 content, plus reserves of 5 per track.
- If fewer qualify, **ship fewer**. Never pad the list.

**Diversity rules:**
- At most 4 leads per area per track.
- No two leads sharing a phone, brand or domain.
- No more than 50% of a track using the same top hook code (§11).

**Tie-breakers:** activity, then reputation, then review count.

**Reserves:** when Swalleh marks a lead "No WhatsApp" or "Skip" in the dashboard, the highest reserve in the same track is promoted.

---

## 11. Facts (the personalisation engine)

A **fact** is something specific and verifiable about the business. Messages and teasers may only use facts.

### 11.1 Fact schema

```json
{
  "id": "F3",
  "code": "SITE_DEAD",
  "strength": "strong",
  "text": "acmehomes.co.ke shows an 'account suspended' page",
  "evidence": {"url": "...", "status": 200, "marker": "account suspended"},
  "track": "web",
  "source": "audit"
}
```

### 11.2 Deterministic fact catalogue (`facts.py`)

| Code | Strength | Example text (the LLM may rephrase, but not change the claim) |
|---|---|---|
| `SITE_DEAD` | strong | "{domain}, the website on your Google listing, isn't loading. It shows {marker}." |
| `SOCIAL_AS_SITE` | strong | "The Website button on your Google listing opens your {platform} page." |
| `SITE_INSECURE` | strong | "Chrome shows a 'Not secure' warning on {domain}." |
| `FREE_BUILDER` | strong | "Your site runs on a free {builder} address ({host})." |
| `SLOW_MOBILE` | strong if LCP ≥ 6 s, else medium | "{domain} takes about {lcp}s to load on a phone." |
| `NO_VIEWPORT` | medium | "{domain} isn't set up for phones; it shows the desktop layout shrunk down." |
| `OLD_COPYRIGHT` | medium | "Your site footer still says © {year}." |
| `NO_WHATSAPP_BUTTON` | medium | "There's no WhatsApp button on {domain}." |
| `NO_SITE_HIGH_REVIEWS` | strong if reviews ≥ 30 | "{n} Google reviews, but no website on your listing." |
| `RECENT_REVIEWS` | medium | "{k} new Google reviews in the last 3 months." |
| `HIGH_RATING` | medium | "{rating}★ from {n} reviews." |
| `MANAGES_LISTINGS` | medium | "Your number is on {n} property listings on Google Maps." |
| `BRANCHES` | medium | "{n} branches on Google Maps." |
| `GOOD_SITE` | medium (content track) | "Your website is solid: it loads fast on mobile and looks current." |
| `NO_SOCIAL_LINKS` | strong (content track) | "Your website doesn't link to any social pages." |
| `NO_VIDEO` | medium (content track) | "There's no video anywhere on your site." |
| `STALE_BLOG` | medium (content track) | "The latest post on your news page is from {month year}." |
| `REVIEW_THEME` | strong if positive and specific | From Gemini (§11.3), e.g. "Several reviews mention how quickly you arrange viewings." |
| `REVIEW_PAIN` | strong if the website could fix it | From Gemini, e.g. "A reviewer mentioned struggling to find available units." |

### 11.3 Review themes (LLM, structured)

- Gemini receives the up-to-5 reviews and returns up to 3 themes.
- **Theme schema:** `review_index`, `theme`, `sentiment`, and a `paraphrase` of at most 12 words.
- Validation:
  - `review_index` must exist.
  - The paraphrase must not include the reviewer's name.
  - Pain themes are kept only if a website or content would plausibly address them.
- **Never quote reviewer names, and never copy review text verbatim** into messages.

---

## 12. Message drafting (`draft.py`, `llm.py`, `validate.py`)

### 12.1 One Gemini call per finalist

**Input:**
- business name
- subcategory and track
- area
- the fact list (with ids)
- up to 5 review texts (for §11.3)
- style rules from `messaging.yaml`

**Output** (JSON schema enforced via the `response_schema` / JSON mode of `google-genai`):
```json
{
  "review_facts": [{"review_index": 2, "theme": "fast viewings", "sentiment": "positive", "paraphrase": "..."}],
  "variants": [
    {"message": "...", "used_fact_ids": ["F1","F4"]},
    {"message": "...", "used_fact_ids": ["F2"]}
  ],
  "poster_lines": ["...", "...", "..."]
}
```

**Model:** set by the env var `GEMINI_MODEL`. Default to the current Flash model and keep it swappable.

**Settings:** temperature 0.7, with a 6 RPM throttle and retry on 429.

### 12.2 Message structure

The message is sent as the **caption on the teaser image**.

1. **Greeting to the business:** "Hi {Business} team 👋" or "Habari {Business} 👋".
2. **One specific observation (1–2 facts),** with the strongest first. It should read like a person noticed it, not like an audit report.
3. **Bridge to the image:**
   - Website track: "I put together a quick preview of how {Business}'s website could look. It's in the image."
   - Content track: "I mocked up a few posts in your colours. Have a look."
4. **One low-friction question:** "Want me to send you the live preview link?" or "Should I send the full preview?"
5. **Sign-off:** `— Swalleh, Raswal Tech Solutions`

### 12.3 Style rules

**Length and language:**
- 280–480 characters. WhatsApp captions allow more, but keep it short.
- English by default. In about 30% of variants (`swahili_touch_rate: 0.3`), add a light Swahili touch: "Habari", "Asante", "Karibu". No heavy Sheng.

**Tone:**
- Warm, direct and respectful.
- No hype words ("revolutionary", "skyrocket", "game-changer").
- No "Dear Sir/Madam".
- At most 1 emoji.

**Never include:**
- A link or URL in the first message.
- A price or "KES".
- Discounts.
- Fake urgency.

**Facts and assumptions:**
- Never guess a person's name. Address the business, because the number may belong to a receptionist.
- Never claim anything that is not in a fact: prices, units, years in business, awards, staff counts.
- Never say "I noticed you need…". Show the observation instead.

**The two variants must use different opening facts.**

### 12.4 Examples (fictional businesses, for prompt few-shots)

**Website track, dead site:**
> Habari Kilima Homes 👋 I tried kilimahomes.co.ke from your Google listing and it's showing an "account suspended" page, which is a shame with 62 reviews mostly praising your viewings. I put together a quick preview of how Kilima Homes' site could look (in the image). Want me to send you the live link?
> — Swalleh, Raswal Tech Solutions

**Website track, social used as the website:**
> Hi Mwangaza Hardware team. The Website button on your Google listing opens your Facebook page, so people searching "hardware Ruiru" can't see your stock or prices. I mocked up what a Mwangaza Hardware site with WhatsApp ordering could look like (attached). Should I send the full preview?
> — Swalleh, Raswal Tech Solutions

**Website track, no website but many reviews:**
> Hi Tausi Builders team 👋 87 Google reviews and several mention how neat your finishing is, but there's no website to show that work. I put together a preview of a Tausi Builders portfolio site (in the image). Want me to send you the live link?
> — Swalleh, Raswal Tech Solutions

**Content track, good site but no social:**
> Hi Savanna Plots team. Your website is genuinely solid and fast on mobile, but it doesn't link to any social pages, which is where most plot buyers scroll. I made a few sample posts in your colours (attached). Should I send you the full set, including a short video?
> — Swalleh, Raswal Tech Solutions

### 12.5 Validator (`validate.py`)

Reject a variant if any of these are true:
- Length is outside 280–480 characters.
- The exact business display name is missing.
- The sign-off is missing.
- It contains a URL, "KES", "Ksh" or a price pattern.
- It contains a banned phrase from `messaging.yaml`.
- It has more than 1 emoji.
- Any number in the message (count, year, seconds, rating) does not appear in the fact texts or evidence for `used_fact_ids`.
- Any domain mentioned is not the lead's own domain.
- `used_fact_ids` is empty, or references unknown ids.
- It contains a reviewer's name, or 6 or more consecutive words copied from a review.

**On failure:**
1. Retry once with the validator errors appended to the prompt.
2. If it still fails, use the **deterministic fallback template** for the top fact code (templates live in `messaging.yaml`).

Store `variant_source` (`llm` or `fallback`) for stats.

### 12.6 Follow-ups

Follow-ups are template-based (no LLM), live in `messaging.yaml`, and Swalleh can edit them in the dashboard.

- **FU1, sent date + 3 working days (text only):** "Hi {Business} team, just checking you saw the preview I sent on {weekday}? Happy to share the live link; it takes a minute to look through. — Swalleh"
- **FU2, sent date + 8 working days (last one):** a different angle per track, plus "If now isn't the right time, no problem at all, I won't keep messaging. — Swalleh"
- **After FU2:** status becomes `no_response`. **Never contact them again** unless they reply.

### 12.7 Quick replies (starter set, editable in the dashboard)

- **"How much?"** — Websites like the preview start from KES 30,000 depending on pages and features. Should I send the live preview first so you can see exactly what you'd get?
- **"How much?" (content)** — Content packages start from KES 6,000 a month, or per piece. Want to see the full sample set first?
- **"Who is this / how did you get my number?"** — I'm Swalleh from Raswal Tech Solutions, a web and content studio in Nairobi. I found {Business} on Google Maps; your number is on the listing. If you'd prefer I don't message again, just say so.
- **"We already have someone."** — Great, glad you're covered. Keep the preview, and all the best!
  - Mark the lead `lost`, with reason `has_provider`.
- **"Not now."** — No problem at all. Should I check back in January?
  - Mark the lead `snoozed`, with a date.
- **"Stop" / not interested.** — Sorry for the bother, I won't message again.
  - Mark the lead `opted_out` and add the phone to `suppression` immediately.

---

## 13. Teaser images (`teaser.py`)

### 13.1 Template contract

Every file in `teasers/` is a self-contained HTML file with these properties:
- It reads a JSON blob injected as `window.LEAD`.
- It sets the CSS variables `--brand-primary`, `--brand-accent`, `--brand-ink` and `--brand-bg`.
- Fonts are embedded as base64. **No external requests.**

**Fields in `window.LEAD`:**
- `business_name`
- `area`
- `logo_data_url` (or null, which means render a wordmark)
- `primary`, `accent`
- `hero_image_data_url`
- `headline`
- `subline`
- `poster_lines[]`
- `phone_display`
- `preview_domain` (`{slug}.raswaltechsolutions.com`)

Swalleh will paste the hero section of each finished website template and the poster templates in, then add the placeholders.

**Headlines are subcategory templates in config, and they make no claims.** Examples:
- `property_agency`: "Homes to rent & buy in {area}"
- `land_developers`: "Plots for sale around {area}"
- `construction`: "Building & renovation in {area}"
- `hardware_supplies`: "Hardware & building materials in {area}"
- `roofing_steel`: "Roofing & steel supplies in {area}"

### 13.2 Website teaser (1080×1350 JPEG, quality about 82, at most 350 KB)

1. Render `teasers/web/{subcategory}/index.html` with Playwright Chromium at desktop size (1440×900).
2. Render it again at mobile size (390×844 at device scale 2).
3. Composite with Pillow onto a background in the brand primary colour:
   - the laptop frame (desktop shot) at the top,
   - the phone frame (mobile shot) overlapping at the bottom right,
   - small text at the bottom left: "Preview for {Business} · by Raswal".
4. The browser bar in the laptop frame shows `{slug}.raswaltechsolutions.com`.
   - `slug` = `name_norm` turned into a kebab-case slug, at most 30 characters.

### 13.3 Content teaser (1080×1350 JPEG)

1. Render `poster-1..3.html` at 1080×1350 each.
2. Composite them as one large poster plus two smaller ones on a neutral background.
3. Add a small "Sample posts for {Business} · by Raswal" label.

**Poster rules:**
- Poster copy comes from `poster_lines`.
- It may only be generic category copy ("Book a viewing on WhatsApp") or come from facts or review themes.
- **No invented prices, unit counts or claims.**

### 13.4 Rendering and storage

- One browser instance for the whole night. Render pages in parallel (3 at a time).
- Upload to Supabase Storage at `teasers/{list_date}/{lead_id}.jpg` in the private bucket `leadgen`.
- Render teasers for **finalists and reserves only** (at most 40/night).

---

## 14. Data model (Supabase Postgres)

### 14.1 Enums

**`lead_status`:**
- `shortlisted`, `reserve`, `approved`, `skipped`
- `sent`, `no_whatsapp`, `replied`, `interested`
- `demo_queued`, `demo_sent`, `negotiating`
- `won`, `lost`, `no_response`, `snoozed`, `opted_out`

**`track`:** `web`, `content`

**`site_status`:** `none`, `social_as_site`, `dead`, `insecure`, `free_builder`, `weak`, `good`

### 14.2 Tables (key columns)

- **`businesses`**
  - `place_id` (PK), `name`, `name_norm`, `subcategory`, `types[]`, `primary_type`
  - `address`, `area`, `lat`, `lng`, `maps_url`
  - `phone_e164`, `phone_type`, `website_url`, `rating`, `review_count`
  - `newest_review_at`, `branch_count`, `manages_listings`
  - `first_seen_at`, `last_seen_at`
- **`places_raw`**
  - `place_id`, `fetched_at`, `payload jsonb` (purged after 30 days)
- **`audits`**
  - `place_id`, `audited_at`, `site_status`, `final_url`, `https_ok`, `platform`
  - `copyright_year`, `has_whatsapp_link`, `has_tel_link`, `meta_viewport`, `has_video`
  - `blog_last_date`, `social_links jsonb`
  - `psi_perf`, `psi_lcp_s`, `current_screenshot_path`
  - `logo_url`, `colours jsonb`, `hero_image_url`, `raw jsonb`
- **`evaluations`** (one per business per night it was considered)
  - `id`, `run_id`, `place_id`, `list_date`, `track`
  - `pre_score`, `score`, `breakdown jsonb`
  - `gate_codes[]`, `selected bool`
- **`facts`**
  - `evaluation_id`, `facts jsonb`
- **`leads`**
  - Identity: `id`, `place_id`, `list_date`, `subcategory`, `track`, `rank`, `status`
  - Message: `message_variants jsonb`, `message_final`, `used_fact_ids[]`, `variant_source`
  - Assets: `teaser_path`, `slug`, `social_state`
  - Review: `skip_reason`, `notes`
  - Timeline: `approved_at`, `sent_at`, `fu1_due`, `fu1_sent_at`, `fu2_due`, `fu2_sent_at`, `replied_at`, `snoozed_until`
  - Demo and outcome: `demo_type`, `demo_link`, `demo_sent_at`, `outcome_value_kes`, `lost_reason`
- **`events`**
  - `id`, `lead_id`, `at`, `type`, `payload jsonb` (the audit trail of every status change)
- **`suppression`**
  - `phone_e164` (PK), `place_id`, `reason` (`opted_out`, `client`, `manual`, `do_not_contact`), `added_at`
- **`search_cells`**
  - `id`, `subcategory`, `query_template`, `area`, `tier`, `last_run`
  - `pages_fetched`, `last_new_ratio`, `exhausted_streak`, `exhausted`
- **`runs`**
  - `id`, `list_date`, `subcategory`, `started_at`, `finished_at`, `status`
  - `places_calls`, `psi_calls`, `gemini_calls`
  - `raw_candidates`, `passed_gates`, `enriched`
  - `qualified_web`, `qualified_content`, `shipped_web`, `shipped_content`
  - `errors jsonb`
- **`api_usage`**
  - `month`, `api`, `sku`, `count` (unique on month, api, sku)
- **`settings`**
  - `key`, `value jsonb`: holidays, daily targets, quick replies, follow-up templates. Mirrored from YAML on every run; dashboard edits win for templates and quick replies.

### 14.3 Security

- RLS is enabled on every table.
- Policy: `auth.jwt() ->> 'email' = (select value->>'admin_email' from settings where key='admin')`.
- The pipeline uses the service-role key, which **only ever lives in GitHub Actions secrets.**
- The dashboard uses the anon key plus the user's session.
- The storage bucket `leadgen` is private, and the dashboard uses signed URLs (1 hour).

### 14.4 Retention (nightly, end of run)

- Purge `places_raw` older than 30 days.
- Delete teaser and current-site files older than 30 days for leads in `skipped`, `no_response`, `lost`, `opted_out` or never-approved states.
- Keep files for `interested` and later statuses.
- Stay under 400 MB DB and 800 MB storage. The dashboard shows usage.

---

## 15. Dashboard

### 15.1 General

- React + Vite + Tailwind, built as a static app.
- Installable PWA, mobile first, and also comfortable on desktop.
- Brand colours: navy `#021422`, gold `#D4970F`, cyan `#3A95C2`, white.
- `<meta name="robots" content="noindex">`.
- `.htaccess` for SPA fallback, HTTPS redirect and basic security headers.

**Auth:** Supabase magic link. Only the admin email can sign in, and the session persists.

### 15.2 Screens

**1. Today: Review mode** (default before any sends)

- **Header:** list date, subcategory, and counts (web X/20, content Y/10, reserves).
- **Tabs:** Website · Content · Reserves.
- **Lead card contents:**
  - name, area, rating, review count, Maps link
  - score and breakdown chips, and a site-status badge
  - the fact list (each fact shows its evidence on tap)
  - the current-site screenshot (if any) next to the teaser
  - message variants A/B as radio buttons, with an editable text area showing a live character count
  - for content leads: social-link buttons and the `social_state` selector
- **Actions:** **Approve**, **Skip** (reason picker: `wrong_category`, `too_big`, `too_small`, `looks_closed`, `weak_hook`, `bad_teaser`, `has_agency`, `other`).
- Skipping promotes a reserve.

**2. Today: Send mode** (approved leads, in rank order)

The steps are numbered on the card.
- **Phone flow:**
  1. **Open chat** opens `https://wa.me/2547XXXXXXXX`, which creates or opens the chat.
  2. Come back and tap **Share image + caption**, which uses `navigator.share({files:[teaser], text: caption})`.
  3. Pick the chat, which is now at the top of WhatsApp's recents.
  - Fallback buttons: **Save image** and **Copy caption**.
- **Desktop flow:**
  1. **Open chat** opens `https://web.whatsapp.com/send?phone=2547XXXXXXXX`.
  2. **Copy image** copies a PNG to the clipboard (convert the JPEG via canvas; the Clipboard API only reliably supports PNG).
  3. Paste it into the chat.
  4. **Copy caption**, then paste it into the caption box and send.
- **Then:** tap **Sent ✓**, which sets `sent_at` and computes `fu1_due` and `fu2_due` in working days using `calendar.yaml` holidays.
- Or tap **No WhatsApp**, which sets `no_whatsapp` and promotes a reserve.
- **Pacing helper:**
  - Shows "sent in the last hour".
  - Suggests a pause after 15 in an hour.
  - Shows the batch windows (configurable, default 09:30–11:00 and 14:00–15:30).

**3. Follow-ups:** the FU1, FU2, demo follow-ups and snoozes due today, with the same open, copy and mark-sent controls.

**4. Inbox log:** search a lead by name or phone, then record what happened.
- **Log reply:** pick a type (`interested`, `question`, `price`, `not_now`, `has_provider`, `stop`) and optionally paste the reply text.
- **Quick replies:** a one-tap copy for each snippet.
- **Mark interested:** opens the demo choice (website or content). It moves the lead to `demo_queued`.

**5. Demo queue:**
- Lists `demo_queued` leads, oldest first.
- Daily cap: **3 website + 3 content** (`demo_cap` in settings). Leads over the cap show "tomorrow" and give a suggested holding reply.
- **Per lead:**
  - **Export lead pack**: copies the JSON and downloads a ZIP of the logo, hero image and teaser.
  - **Paste demo link**
  - **Mark demo sent**: schedules a demo follow-up at +1 and +4 working days.

**6. Pipeline:** a list by status, with filters by subcategory, track and date. Lead detail shows the timeline (events), notes, outcome value and won/lost reason.

**7. Stats:**
- **Funnel:** sent → replied → interested → demo → won.
- **Broken down by:** subcategory, track, site status, top fact code, variant source (LLM or fallback), Swahili touch yes/no, send hour.
- **Gate rejection counts** per night.
- **API usage** this month against caps.
- **Supabase** DB and storage used.

**8. Settings:**
- Add to suppression (phone)
- Edit quick replies and follow-up templates
- Demo cap
- Daily targets
- Pause list (holiday)

### 15.3 Lead pack (initial shape; the demo repos can change it)

```json
{
  "lead_id": "uuid",
  "track": "web",
  "subcategory": "property_agency",
  "template_id": "property_agency",
  "business": {
    "name": "...", "slug": "...", "area": "...", "address": "...",
    "phone_e164": "+2547...", "website_url": "...", "maps_url": "..."
  },
  "brand": {"logo_url": "...", "primary": "#...", "accent": "#...", "hero_image_url": "..."},
  "facts": [{"code": "...", "text": "..."}],
  "review_themes": [{"theme": "...", "paraphrase": "..."}],
  "poster_lines": ["..."],
  "preview_domain": "slug.raswaltechsolutions.com"
}
```

---

## 16. GitHub Actions

### 16.1 Workflows

**`nightly.yml`**
- **Triggers:**
  - `schedule`: `cron: "30 18 * * 0-4"` (21:30 EAT, Sunday–Thursday). GitHub may start scheduled jobs late, so the run must not depend on exact timing.
  - `workflow_dispatch` inputs: `list_date`, `subcategory`, `dry_run`, `max_places_calls`.
- **Steps:**
  1. Checkout
  2. Set up Python 3.12
  3. `pip install`
  4. `playwright install --with-deps chromium`
  5. `python -m pipeline nightly`
- **Holidays:** if `list_date` is a holiday in `calendar.yaml`, exit cleanly and record a skipped run.
- **Timeout:** 60 minutes.
- **Concurrency group:** `nightly`.
- **Artifacts:** upload the dry-run CSV and logs.
- **Dashboard banner:** at the end, write a run summary to `runs`. The dashboard shows "Tomorrow's list ready: 18 web / 9 content", or the error.

**`heartbeat.yml`**
- Daily cron `0 6 * * *`.
- Runs one trivial Supabase query so the free project never pauses. This matters over the December break.

**`deploy-dashboard.yml`**
- Triggered on push to `dashboard/**`.
- Steps: `npm ci && npm run build`, then FTP-deploy `dist/` to the Nova Host subdomain document root (e.g. `SamKirkland/FTP-Deploy-Action`).
- Build-time env vars: `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`.

**`ci.yml`**
- On every push: `pytest` and `ruff`; build the dashboard on pull requests.

### 16.2 Secrets

| Secret | Value |
|---|---|
| `GOOGLE_PLACES_API_KEY` | Restricted to Places API (New) |
| `PSI_API_KEY` | Restricted to the PageSpeed Insights API |
| `GEMINI_API_KEY` | Google AI Studio key |
| `GEMINI_MODEL` | Current Flash model name |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Pipeline only |
| `SUPABASE_ANON_KEY` | Dashboard build |
| `FTP_SERVER`, `FTP_USERNAME`, `FTP_PASSWORD`, `FTP_DIR` | Nova Host FTP account scoped to the subdomain folder |

### 16.3 CLI

```
python -m pipeline nightly [--list-date YYYY-MM-DD] [--subcategory KEY] [--dry-run]
                           [--no-llm] [--no-render] [--max-places-calls N] [--limit N]
python -m pipeline rerender --lead-id ID
python -m pipeline redraft  --lead-id ID
python -m pipeline cells    --subcategory KEY        # show rotation state
python -m pipeline usage                             # API usage this month
```

**`--dry-run`:**
- Uses at most 5 Places calls (unless overridden).
- Skips Supabase writes.
- Writes `out/{list_date}-{subcategory}.csv` with every candidate, its gate codes, score breakdown, facts and drafts.

---

## 17. Milestones

The Monday minimum is **M0–M5**. If M5 slips, Monday's list goes out with the teaser rendered from the template's static hero, using name and colour injection only.

| # | Milestone | Done when |
|---|---|---|
| M0 | Skeleton: repo layout, config loading, Supabase migrations and RLS, CI | `pytest` passes; migrations apply cleanly; one admin login works |
| M1 | Discovery + normalise + gates + budget guard | A dry run for `property_agency` prints at least 80 candidates with gate codes, using ≤ 5 Places calls |
| M2 | Site audit + PSI + brand assets | The fixture tests classify every `site_status`; a live dry run shows a status for every candidate with a site |
| M3 | Scoring + selection + diversity + reserves | The dry-run CSV ranks candidates with breakdowns; selection respects targets, thresholds and diversity rules |
| M4 | Facts + Gemini drafting + validator + fallback | Every finalist has 2 valid variants; the validator tests cover every rejection rule |
| M5 | Teaser rendering + storage upload + nightly workflow | The nightly run on Actions produces up to 30 + reserves with teasers in under 45 minutes |
| M6 | Dashboard: auth, Review, Send (phone and desktop flows), No WhatsApp → reserve promotion | Swalleh can review and send Monday's list from his phone |
| M7 | Follow-ups, inbox log, quick replies, demo queue + lead pack, suppression | The FU1/FU2 queues compute correctly around holidays; opt-out suppresses instantly |
| M8 | Pipeline view, stats, usage panel, retention purge, heartbeat | The stats funnel matches the events log; storage stays under caps |

---

## 18. Testing

**Unit tests:**
- Phone parsing (Safaricom 07xx and 01xx, Airtel, 020 landlines, international formats)
- Building-name gate
- Brand gate with dealer exceptions
- Every `site_status` fixture
- Score bands
- Selection diversity
- Working-day follow-up dates across Mashujaa Day and Christmas
- Every validator rule
- Fallback templates

**Contract tests:**
- The Places field mask is unchanged (a snapshot test, so nobody silently changes the billed SKU).
- The Gemini JSON schema parses correctly.

**Visual check:**
- `python -m pipeline rerender` on fixtures for all five subcategories, saved to `out/teasers/` for manual review.

---

## 19. Out of scope (for now)

- Building websites and content demos (separate repos)
- Sending WhatsApp messages automatically
- Payments and invoicing
- Non-real-estate categories (healthcare, beauty), which come later via new entries in `subcategories.yaml`
- International leads
