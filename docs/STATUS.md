# Status

Last updated 10 Oct 2026. Everything in the brief (M0–M8) is built and passes its tests **without any keys**. What is *not* proven is anything that talks to a real service: those paths are written and contract-tested against fixtures, but nobody has run them live yet (§2).

## 1. Milestones

| # | Milestone | State |
|---|---|---|
| M0 | Skeleton, config, migrations + RLS, CI | Done |
| M1 | Discovery, normalise, gates, budget guard | Done (live Places call untested) |
| M2 | Site audit, PSI, brand assets | Done (live fetch/PSI untested) |
| M3 | Scoring, selection, diversity, reserves | Done |
| M4 | Facts, Gemini drafting, validator, fallback | Done (live Gemini untested) |
| M5 | Teasers, storage upload, nightly workflow | Done (live upload and the Actions run untested) |
| M6 | Dashboard: auth, Review, Send, No WhatsApp → reserve | Done on mock data; live auth untested |
| M7 | Follow-ups, inbox, quick replies, demo queue + lead pack, suppression | Done on mock data |
| M8 | Pipeline view, stats, usage, retention, heartbeat | Done on mock data |

**Verified here:** 281 pytest tests, ruff, 24 dashboard unit tests, `tsc` + production build, and the migrations applied twice to Postgres (PGlite) with RLS checks. `python -m pipeline nightly --offline --dry-run` runs the whole pipeline on fixtures (about 25 s) and writes `out/<date>-<subcategory>.csv` plus 37 rendered teasers in `out/teasers/<date>/`. I also clicked through the dashboard on mock data (Review → Send → Follow-ups → Demos → Inbox → Stats) at phone width in a headless browser with no console errors.

**Not verified:**
- **Supabase was checked on PGlite, not a real Supabase stack.** There's no Docker or Supabase CLI here, so GoTrue, the Storage API and `supabase db push` are untested.
- **The live dashboard and the Supabase client code** have never run against a real project.
- **GitHub Actions workflows** are syntax-checked only.
- **Real phones and WhatsApp:** I have not tested Share image + caption on Android, or Copy image on WhatsApp Web.

## 2. Needs real keys to verify (checklist)

- [ ] Places: the field mask bills under *Text Search Enterprise + Atmosphere* (Cloud Billing → Reports; SETUP_CHECKLIST §2). **If it shows another SKU, stop** (§6 below).
- [ ] Places: a real response parses (`reviews[].publishTime`, `nationalPhoneNumber`, `userRatingCount`) and the CSV looks sensible.
- [ ] Places: the Cloud quota (45/day) is set and `--max-places-calls` works.
- [ ] PSI: real response gives performance, LCP and a `final-screenshot` (the live fetcher and PSI client have only been exercised against fixtures and mocked HTTP).
- [ ] Site fetch: real sites classify correctly. Spot-check `dead`, `insecure` and `social_as_site` against what you see in a browser; the marker lists are in `config/audit.yaml`.
- [ ] Gemini: your `GEMINI_MODEL` accepts `response_schema` and returns valid JSON; check the free-tier daily limit for it (§6).
- [ ] Gemini: a daily-quota 429 is recognised (the code matches on the error text; I couldn't test Google's real wording).
- [ ] Supabase: `supabase db push --include-seed` applies cleanly; the `leadgen` bucket exists and stays private.
- [ ] Supabase: magic-link login works for `swallehmtawazo@gmail.com`; another email is refused; turn sign-ups off afterwards (SETUP_CHECKLIST §4).
- [ ] Supabase: a live (non-dry) run writes leads, teasers upload, and the dashboard shows them via signed URLs.
- [ ] Supabase: `promote_reserve` and the status-event trigger work through the real API (RPC call from the browser).
- [ ] GitHub: nightly workflow (manual dispatch), heartbeat, and CI run green.
- [ ] Nova Host: FTP deploy works (try `protocol: ftp` in `deploy-dashboard.yml` if FTPS is refused) and `.htaccess` is honoured (deep links like `/stats` load, HTTP redirects to HTTPS).
- [ ] Phone: install the PWA on your Android phone; test **Share image + caption**, then **Copy image** on WhatsApp Web.

## 3. Your first live test

One-time setup:

```bash
uv venv -p 3.12 .venv && uv pip install -p .venv -r requirements-dev.txt
.venv/bin/playwright install chromium
cp .env.example .env        # fill in the keys; never paste them into chat
supabase link --project-ref <ref> && supabase db push --include-seed
```

1. **Dry run, 5 Places calls, no Supabase writes** (still reads Supabase for suppression and contacted checks; add `--no-db` to skip that if Supabase isn't ready yet, but then those checks are skipped):
   ```bash
   .venv/bin/python -m pipeline nightly --subcategory property_agency --dry-run
   ```
   Open `out/<date>-property_agency.csv` and `out/teasers/<date>/`. Look at gate codes, `site_status` and the messages.

2. **Capped real run, ≤ 10 Places calls, writes to Supabase:**
   ```bash
   .venv/bin/python -m pipeline nightly --subcategory property_agency --max-places-calls 10
   ```
   Then check the dashboard, and the Cloud Billing SKU.

3. Other commands: `python -m pipeline usage` (calls this month), `cells --subcategory property_agency` (rotation state), `rerender --lead-id <id>`, `redraft --lead-id <id>`.

**Dashboard:**
- Locally on mock data: `cd dashboard && npm install && npm run dev`. If `public/mock/dataset.json` is missing, run `npm run mock` first (or `python -m pipeline export-mock`). Set `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` in `dashboard/.env.local` to use the real backend.
- Deploy: add the secrets from SETUP_CHECKLIST (`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `FTP_*`), then push to `main` or run **Deploy dashboard** from the Actions tab. The workflow builds with the Supabase env and uploads `dashboard/dist/`.
- Also add the other GitHub secrets: `GOOGLE_PLACES_API_KEY`, `PSI_API_KEY`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `SUPABASE_SERVICE_ROLE_KEY`.
- Before Sunday night: run the **Nightly** workflow once manually with `dry_run` ticked and download the artifact.

## 4. Plugging in your real templates

Full guide: [teasers/README.md](../teasers/README.md). In short: for each subcategory, paste your hero section into `teasers/web/<template>/index.html` and the posters into `teasers/content/<template>/poster-1..3.html`, replace content with `data-lead="…"` hooks and colours with `var(--brand-primary)` etc., keep the shared `fonts.css` / `tokens.css` / `lead.js` links, and check with `python -m pipeline rerender --offline`. To rename a subcategory, change its key in `config/subcategories.yaml` (the `template:` field keeps pointing at the existing folder).

Also: add your existing clients' phone numbers (Premar, Jamar, Rawa…) in **Settings → Suppression list** in the dashboard (works after the first sign-in).

## 5. Things to know about how it behaves

- **Fewer than 30 is normal.** Selection never pads. On fixtures a night ships about 20 web + 10 content; real numbers will differ and the thresholds (65 / 62) are untested on real data.
- **Review recency is a lower bound.** Places returns at most 5 reviews, "most relevant" first, so `DORMANT` and the Activity score can misjudge an active business. Watch `dormant` in the Stats gate counts in week 1.
- **Gemini failing never stops a night.** Quota, rate limit or invalid output falls back to deterministic templates (`variant_source: fallback`, visible in Stats and on each card).
- **A teaser render failure doesn't lose the lead.** It's logged in the run's errors; `rerender --lead-id` fixes it.
- **The dashboard banner** says "Tomorrow's list ready" or shows the error; it also warns when a subcategory is low on tier-1 search areas.
- Phone numbers are stored in Supabase (as the brief specifies) and are the only personal-ish data. Reviewer names are never sent to Gemini or stored in messages. See `docs/DECISIONS.md` for the ~95 small choices I made.
- Runtime budget: Places ≤ 40/night and ≤ 900/month, PSI ≤ 150, Gemini ≤ 60 (≤ 6 RPM), all hard-stopped in code.

## 6. Open questions for you

1. **Gemini free-tier limits.** What's the RPD for your `GEMINI_MODEL` in AI Studio? If it's under ~60, part of each night will use fallback messages. A Flash-Lite model may be a better fit. Which model do you want?
2. **Places SKU.** If Billing shows anything other than *Text Search Enterprise + Atmosphere*, the field mask needs changing. Do you want me to prepare a reduced mask (dropping `reviews`) as a fallback? That would lose review themes and the activity/`DORMANT` signals.
3. **Google's Places terms** only allow `place_id` to be stored indefinitely, but the brief keeps name, phone and rating in `businesses`. I followed the brief. OK?
4. **Wildcard subdomains** on Nova Host (SETUP_CHECKLIST §5): the teaser's URL bar shows `{slug}.raswaltechsolutions.com` whatever the answer, but if wildcards aren't supported, previews will not resolve at that address. Should the teaser show a path-style URL instead?
5. **Holidays.** I listed the 2026–27 Kenyan public holidays from memory in `config/calendar.yaml`, including Utamaduni/Moi Day on 10 Oct 2026 and observed-day shifts. Please check them against the Gazette; Islamic holidays (Idd) aren't included because they depend on the moon sighting.
6. **Tue 20 Oct (Mashujaa Day)** has no list, as in your playbook, so Land & developers is skipped that week. Do you want it moved to Wednesday that week?
7. **Nova Host FTPS vs FTP** (see above), and whether the account allows folder-scoped FTP.
8. **Brand seed list and business-word list** were extended slightly (see DECISIONS.md M1). Review `config/exclusions.yaml` after the first CSV: it's the main lever for false positives.

## 7. Known gaps

- Dashboard stats are tables and bars, not trend charts, and use all-time data (no date filter yet).
- The dashboard does not edit message templates beyond follow-ups/quick replies; first-message style rules live in `config/messaging.yaml`.
- No automated browser test for the dashboard beyond unit tests of the logic; I clicked through it manually in headless Chrome.
- `places_raw` retention and file purge run at the end of each live nightly; the first purge happens 30 days after the first run.
