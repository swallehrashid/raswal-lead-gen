# Decisions log

Small ambiguities resolved during the build. One line each: what and why.

## M0: skeleton
- Moved PROJECT_BRIEF/DAILY_PLAYBOOK/SETUP_CHECKLIST from the repo root into `docs/`, as the brief's layout and your instructions expect.
- RLS uses a `SECURITY DEFINER` function `public.is_admin()` instead of the inline sub-select in §14.3, because the inline version on `settings` fails with "infinite recursion detected in policy" (verified on Postgres).
- Explicit `GRANT`s to `authenticated`/`service_role` and `REVOKE` from `anon` on every table, because newer Supabase projects no longer auto-expose new tables to the Data API.
- `subcategory` is a `text` column, not an enum, so renaming a subcategory needs no migration (config only).
- Each subcategory has a `template:` field (the teasers/ folder name, defaulting to the key), so renaming a key needs no teaser folder rename.
- Added an `audits.place_id` primary key (latest audit per business), a `psi_cache` table (30-day per-domain cache), a `leads.evaluation_id` link to facts, demo follow-up columns, and `runs.gate_counts`/`skipped_reason`/`dry_run`, all needed by the dashboard and stats.
- An insert/update trigger on `leads` writes every status change to `events`, so the audit trail can't be skipped by any client.
- Reserve promotion is a Postgres function `promote_reserve(lead_id)` (runs under RLS as the admin), so the phone and desktop flows behave the same.
- `increment_api_usage()` is executable by `service_role` only: the dashboard can read usage but not change it.
- Added `config/audit.yaml` (parked-page markers, free-builder hosts, platform markers) because these are tunables and §9 lists many of them.
- `seed.sql` is generated from config by `python -m pipeline gen-seed` (a test fails if it's stale). It is applied with `supabase db push --include-seed`. The pipeline also syncs any new search cells at run start.
- Settings the dashboard owns (quick replies, follow-up templates, demo cap, daily targets, pause list) are inserted only if missing; everything else is overwritten from YAML on every run.
- `gen_random_uuid()` is core Postgres (13+), so the `pgcrypto` extension isn't required.
- Migrations are verified on PGlite (Postgres in WASM) with stubbed `auth`/`storage` schemas (`scripts/verify-migrations`), because Docker and the Supabase CLI aren't available here. It also runs in CI.
- Local dev uses Python 3.12 via `uv` (the system Python is 3.14), to match the Actions runtime.
- Kenyan holidays are listed through 2027 in `calendar.yaml`; the Dec 21–Jan 1 break is a "pause" that blocks both new lists and follow-ups (`pauses_block_followups: true`).
- Construction uses the "property & land offices" tier-1 area list (the brief gives two tier-1 lists; construction firms keep offices in the same areas). Ngong Road, Kasarani and Embakasi appear in both lists, so they are in both sets.
- "Syokimani" in the brief is taken to mean Syokimau.
- Removed `foundation` and `sacco` from the GOV_NGO words: "Foundation Builders" and land-selling SACCOs are legitimate leads.

## M1: discovery, normalise, gates, budget
- New gate `PREVIOUSLY_LISTED`: a place or phone that was on an earlier list and was skipped or marked No WhatsApp, or listed in the last 60 days (`relist_cooldown_days`), isn't listed again. Otherwise a skipped business would come back every week on its themed day.
- Places calls are never retried automatically: each attempt is a billed request, so each must pass the budget guard.
- The nightly Places cap is per run. A manual re-run the same night starts a new count; the monthly cap (900) and the Google Cloud daily quota (45) are the backstops.
- `--max-places-calls` can lower the nightly cap but never raise it above `calls_per_night` (40).
- New `--no-db` flag lets a live `--dry-run` skip Supabase reads; it logs a loud warning that suppression and contacted checks are skipped. Without it, a dry run needs Supabase read access.
- A business's `area` is the nearest area centre (within 12 km) among the subcategory's own areas. Otherwise property offices near the CBD were tagged "Kirinyaga Road".
- Near-duplicate and branch detection compare `name_key`, which is the name without the legal suffix and without a trailing area name (e.g. "Makazi Realtors Karen" → "makazi realtors"). `branch_count` counts distinct locations more than 2 km apart.
- Shared phone (§7.5): if no listing on the shared number has a business-like name, the lead keeps the building name and is rejected by `BUILDING_NOT_BUSINESS`. We'd have no way to address them.
- Added business words the brief's list misses: real estate, lettings, agencies, property managers, consultants, services, supplies, interiors, renovations, fabricators, tiles. Otherwise "Mlimani Real Estate" and "Garden City Lettings" were rejected as buildings.
- Brand "Tile & Carpet" is stored as "tile and carpet centre" (the chain's full name), because "centre" alone is a dealer word that would let the chain through.
- When Places returns both formats, the international phone number is parsed first.
- Fixture review times are shifted relative to 2026-10-09, so offline runs look the same on any date.

## M2: site audit, PSI, brand assets
- Classification runs in two steps: fetch and parse (none/social/dead/insecure/free_builder are decided here), then weak/good once PSI has run. If PSI fails or the budget is spent, weak/good is decided from the other five signals.
- "Default hosting page" markers (cPanel, Nova Host, "Default Web Site Page") only count on pages with under 1,500 characters of text, so a footer credit on a real site doesn't mark it dead. "Coming soon" keeps the brief's under-2 KB rule.
- `Index of /` only counts when it's the page title.
- A `*.business.site` website URL, or any redirect into one, is `dead` without a fetch.
- A Wix/WordPress site on its own domain is classified normally (often `weak`), not `free_builder`. `free_builder` is only for free subdomains (wixsite.com etc.).
- The blog/news page is fetched only for sites still in the running for weak/good, and only when a same-host link exists.
- Every PSI attempt (including the retry) counts against the PSI budget. Results are cached per registered domain for 30 days in `psi_cache`.
- Current-site screenshots (`current/{place_id}.jpg`) and brand files are uploaded only for finalists and reserves, which are the only ones the dashboard shows. That keeps storage small.
- Brand assets (logo, colours, hero) are fetched only for finalists and reserves (≤ 40/night), not for all 150 audited sites.
- SVG logos are skipped (Pillow can't read them); the teaser then shows a wordmark. `og:image` is accepted as a hero at any size; other `<img>` heroes need ≥ 1000 px width.
- Colour extraction also drops grey colours and any colour under 2% of the logo's pixels, so anti-aliasing noise isn't picked as the brand colour.

## M3: scoring, selection, diversity, reserves
- Deterministic facts (§11.2) are built before scoring, because hook points and `NO_HOOK` need them. Gemini review facts are added during drafting (M4).
- A candidate eligible for both tracks (weak, with HTTPS and a viewport) goes to the track where its score clears the threshold by more; ties go to web.
- `NO_HOOK` is checked during selection, in rank order. A candidate with no strong deterministic fact gets its Gemini call first (a review theme can be a strong fact). If it still has none, it's rejected and the next candidate is taken. This keeps Gemini calls to the people we'd actually ship.
- The 50% top-hook cap uses the track's target, not the final count (≤ 10 web, ≤ 5 content with the same top fact), so the cap is predictable when fewer qualify.
- Area and top-hook caps apply to finalists. A candidate that only fails those caps can still be a reserve. Phone/brand/domain uniqueness applies to the whole list, reserves included.
- Domain uniqueness ignores leads with no site or a social page as their site. Free-builder sites are told apart by full host (`acme.wixsite.com`), using the public-suffix list's private section. The PSI cache uses the same key.
- `GOOD_SITE` is only claimed when PSI performance ≥ 70 and the copyright year is current or last year, since the fact text says "loads fast" and "looks current".
- `SLOW_MOBILE` is a web-track fact only (content leads have good sites by definition). LCP is rounded to whole seconds in the text ("about 8s"); the exact value is in the evidence.
- `MANAGES_LISTINGS` is only produced for subcategories with `manages_listings_is_positive` (property agencies).

## M4: facts, Gemini drafting, validator, fallback
- Added `addressable_by` (website | content | none) to the Gemini review-theme schema. §11.3 says pain themes are kept only if a website or content would plausibly fix them; this lets the model say which.
- Review themes get ids R1–R3 in the order Gemini lists them, and variants may cite them. Invalid themes (bad index, reviewer name, verbatim copy, a number, "several" with one review, over 12 words) are dropped, and any variant citing one fails validation.
- `REVIEW_THEME` is strong when positive, not generic (`generic_themes` in scoring.yaml) and at least 4 words. `REVIEW_PAIN` is strong when it's fixable by this lead's track.
- Reviewer names are never sent to Gemini; only the numbered review texts are. The validator still checks for names (full name, or a capitalised first/last name of 3+ letters).
- "6 or more consecutive words copied" is checked on lowercased word 6-grams (`review_copy_max_words: 5`).
- Number check: every number in the message (excluding the sign-off) must appear in the text or evidence of a cited fact, or in the business/area name. 4.6 and 4,6 are treated as the same number.
- Domain check: the only domain allowed is the lead's own (their website host, the final URL host, or their free-builder host). Any `http(s)://` or `www.` link is rejected even for their own site, because the first message has no links.
- Money: KES/Ksh/Shs, "30k", "/-", "bob" and currency symbols are rejected. The word "prices" is allowed (one of the brief's examples uses it).
- ★ isn't counted as an emoji (it's part of the rating fact).
- Swahili touch is decided per variant with a deterministic RNG (seeded by place_id) at `swahili_touch_rate`. The stored flag reflects what the final message actually contains.
- Retry: one retry with the validator errors appended. Valid variants from either attempt are kept and the rest come from the fallback. Each Gemini attempt (and each per-minute 429 retry, up to 3) counts against the nightly Gemini budget.
- A daily-quota 429, or a 401/403/404 (bad key or model), trips a circuit breaker: the rest of the night uses fallback messages and no more calls are made.
- `variant_source` on the lead is the source of the variant currently chosen; each variant also stores its own source. The dashboard updates it when you pick B.
- Poster lines from Gemini must have ≤ 10 words, no domain/URL/money, no numbers outside the facts, and no reviewer names. Rejected lines are replaced by the subcategory's generic lines.
- The fixture Gemini client synthesises answers from the prompt context; a fifth of businesses get a broken first answer (retry path) and about a tenth fail twice (fallback path), so offline runs exercise everything.

## M5: teasers, storage upload, nightly workflow
- Templates link the shared files (`../../shared/fonts.css`, `tokens.css`, `lead.js`) with relative paths, and the renderer inlines all of them (CSS, JS, images, CSS `url()`). The rendered page is fully self-contained, and the files still open directly in a browser.
- `window.LEAD` carries the §13.1 fields plus optional extras (`ink`, `bg`, `cta`, `nav`, `subcategory`, `track`) that templates may ignore.
- Every network request from a template is blocked and logged with the template name, and a test asserts all 20 templates render with zero requests.
- Fonts are Montserrat 700/800 and Inter 400/600 (SIL OFL, latin subsets) as base64 `woff2`. The same families in `.woff` are used by Pillow for the composite labels.
- The composite adds a "WEBSITE PREVIEW" / "SAMPLE POSTS" label and an "A new website for {Business}" / "Post ideas for {Business}" heading to fill the free space. Neither makes a claim. "In your colours" was avoided because a lead without a logo gets the template's default palette.
- Removed claims from config copy that appears on every teaser: "Verified listings", "genuine title deeds", "New listings every week" and "New stock this week" were replaced with neutral lines.
- Lead ids are generated before saving, so the teaser path `teasers/{list_date}/{lead_id}.jpg` is known when the lead row is written.
- Teasers render finalists first, then reserves (≤ 40/night). If rendering fails, the lead still ships without a teaser, the error goes to `runs.errors`, and `python -m pipeline rerender --lead-id` fixes it later.
- JPEG quality starts at 82 and steps down by 4 (minimum 60) until the file is ≤ 350 KB. Typical teasers are 90–130 KB.
- The heartbeat uses `curl` against the REST API (no Python install), so it takes seconds of Actions time.
- The dashboard deploy uses FTPS by default; the workflow comment says how to switch to plain FTP if Nova Host refuses TLS.
- Dry runs upload `out/` (CSV, rendered teasers, log) as a 7-day artifact. Live runs upload only the log, keeping phone lists out of artifacts.

## M6–M8: dashboard, follow-ups, demo queue, stats, retention
- The dashboard is React 19 + TypeScript + Vite 8 + Tailwind 4 + vite-plugin-pwa, with React Router (BrowserRouter; the `.htaccess` SPA fallback makes deep links work on Nova Host).
- One `Api` interface has two implementations. Supabase is used when `VITE_SUPABASE_URL` is set at build time; otherwise a mock is used. The mock reads `public/mock/dataset.json`, generated from the pipeline fixtures by `python -m pipeline export-mock` (a simulated week, "today" = Fri 16 Oct 2026), and keeps your clicks in localStorage. A live build deletes `dist/mock/`.
- All state transitions are pure functions (`src/lib/actions.ts`, unit-tested) used by both implementations. Supabase's trigger logs status changes; the mock imitates the trigger.
- Working days are computed in the browser with a TypeScript twin of the Python code, tested on the same vectors. Pauses added in the dashboard also move follow-up dates.
- The phone flow (Share image + caption) is offered when the browser can share files (Android Chrome, installed PWA); otherwise the WhatsApp Web flow. A toggle switches between them.
- Copy image converts the JPEG to PNG through a canvas (the Clipboard API reliably supports only PNG).
- Marking FU2 sent sets `no_response`, so the sequence ends there (§12.6). A later reply can still be logged.
- A snooze that comes due appears in Follow-ups; marking it done sets the lead back to `replied`.
- "Not now" defaults to a check-back on Mon 4 Jan 2027 (the brief suggests January).
- Daily targets and the pause list set in the dashboard are read by the next nightly run: targets override `scoring.yaml`, and a paused list date is skipped like a holiday. The demo cap is dashboard-only.
- The Demo queue fills today's slots (3 website + 3 content, minus demos already sent today) oldest first; the rest show "tomorrow" with the holding reply.
- The lead pack ZIP holds `lead-pack.json`, `logo.png`, `hero.jpg` and `teaser.jpg`. In the ZIP's JSON, logo/hero point at the bundled files; the copied JSON uses 1-hour signed URLs.
- The Stats funnel is computed from the events log and checked against lead timestamps (the screen says whether they match, and a test asserts it on the mock data). Breakdowns are tables with rates, not charts.
- Supabase DB/storage size comes from a `usage_stats()` RPC (admin-only, security definer) that sums `storage.objects` sizes.
- The PWA service worker caches only the app shell; Supabase data is never cached.
- `.htaccess` forces HTTPS, rewrites to `index.html`, sends `noindex` and security headers (CSP allows only self and `*.supabase.co`), and never caches `index.html`/`sw.js`.
- Teaser renders retry once before counting as failed (a busy runner can time out).
