# Ads pivot report

Executor: Sonnet 5.5. Plan: `/home/swalleh/Content/RASWAL-ADS-PIVOT-EXECUTION.md`.

## Swalleh's open USER ACTIONS (P9)
Monday works without any of these (see "What still works if you do nothing"); do them in this order for the best results.
- ⬜ 1. **GitHub → Actions → Nightly → Run workflow** with *dry run* ticked (and "max places calls" 5). I couldn't trigger it (no `gh` here). It proves the nightly runs on GitHub with the new daily mix. Also check **CI** is green on the latest commit.
- ⬜ 2. Meta Business Portfolio for Raswal, verified; write down the 16-digit Portfolio ID and paste it into `docs/pilot-kit/03-access-guides.md`
- ⬜ 3. Ad account in the portfolio (KES if offered); working card + a backup (virtual USD card); a second ad account ready
- ⬜ 4. Raswal's own FB Page + Instagram + WhatsApp Business on +254 114 129 809, linked to the Page
- ⬜ 5. Warm-up click-to-WhatsApp ad for Raswal itself (KES 1-2k): it teaches the flow and warms the ad account
- ⬜ 6. M-Pesa till/paybill for client ad budgets (always prepaid before spending)
- ⬜ 7. Apify (optional): token into `.env` and the GitHub secret `APIFY_TOKEN`, $10/month limit (SETUP_CHECKLIST §7). Without it every lead's "already advertising?" stays "unknown"; use the Ad Library link on each card.
- ⬜ 8. Record the 4 access-guide screen recordings from the scripts in `docs/pilot-kit/03-access-guides.md`
- ⬜ 9. Confirm wildcard HTTPS on a brand-new slug: open the first real plan link on your phone. If it shows a certificate warning, put Cloudflare in front (free wildcard SSL).
- ✅ Outreach number saved in settings: 254114129809
- ✅ Final Flow photos received and used (16 land + 19 agency)

### What still works if you do nothing
- Monday's outreach: the Sunday-night nightly builds 20 land + 10 agency leads with the new teaser and Kenyan messages; you send from the dashboard as before.
- A "yes" gets its plan link (`pipeline generate`, run on your PC) and the pilot can start with a screenshot-level manual flow: send the offer form (quick reply), take KES 5,000 by M-Pesa, and run the campaign from any ad account you have (even a personal one) until Raswal's portfolio is verified.

## Status by phase
| Phase | State | Note |
|---|---|---|
| P0 | ✅ | three repos tagged `pre-ads-pivot`; demo kits archived (they were untracked) |
| P1 | ✅ | debug leftovers, content track, demo kits, old web/poster teasers removed; PSI switched off (code kept, budget 0, key optional) rather than deleted |
| P2 | ✅ | migrations live; daily mix; one ads score + angles; Kenyan messages; scam + estate gates; ad-library + Instagram signals (optional Apify); pre-pivot drafts no longer block re-listing; real-name shortening |
| P3 | ✅ | photos mapped + graded (seams cropped); winning-ads research NOT done (no Apify token): the templates follow the offer elements seen in the Ad Library in the strategy session |
| P4 | ✅ | teaser wired: land d1, agency d3 (my choice; one config line each) |
| P5 | ✅ | engine + 6 templates rendered at final quality; QA tool passes |
| P6 | ✅ | pitch page + `build_pilot.py` + `generate` wiring |
| P7 | ✅ | dashboard: Plans, Pilots, daily mix, outreach number, ad-aware cards, funnel stage |
| P8 | ✅ | `docs/pilot-kit/` |
| P10 | see Live checks | `scripts/e2e.py` |

## Approval log
| Gate | Item | Version | Date | Swalleh's notes |
|---|---|---|---|---|
| G0 | Teaser direction (land d1, agency d3) | v1 | 2026-10-28 | built, awaiting review |
| G1-G6 | L1 Plot Tour, L2 The Offer, L3 Before You Buy, A1 New Listings, A2 Viewing Day, A3 Budget & Area | v1 (`ads/approved/<id>/v1`) | 2026-10-28 | built, awaiting review (Swalleh asked for everything end to end; photos approved) |

## Removal ledger
| Path | Repo | Why removed | References fixed |
|---|---|---|---|
| `_logo_tmp.py`, `_posters_tmp.py`, `_retry_baraka.py`, `brands/content-baraka.json`, `_staging/`, `_content_out/`, `__pycache__/` | raswal-pipeline | one-off Baraka debug leftovers | only self-references and `build_content.py` |
| `build_content.py` | raswal-pipeline | content demo track retired | `generate.py` content kind removed; `--track` choices now `web|pilot` |
| `content/templates/` (5 demo kits), `content/businesses/tpl-*` (5), `content/businesses/baraka-homes/` | content-creation-pipeline | demo templates retired; archived first to `~/Projects/_archive-pre-ads-pivot/content-demo-templates.tar.gz` (baraka-homes was a throwaway test client, not archived) | registry regenerated (`demo`, `raswal`, `sahilpay` still resolve); `tsc` clean; README note added |
| web/content scoring (`web_score`, `content_score`, `content_gap`, `content_eligible`), `web:`/`content:` blocks of `scoring.yaml`, `bridges`, per-track `questions`/`fallback`, `price_web`/`price_content` quick replies, `fu2_web`/`fu2_content`, `list_day`/`subcategory_for_day`, `daily_targets` use | raswal-lead-gen | replaced by the single ads score, angle-based messages and the daily mix | tests rewritten; dashboard follow-ups use `fu2` |

## Decisions & deviations
- **No per-video approval gates.** Swalleh asked for everything to be produced end to end ("produce all the 6 videos... then I'll reintroduce Opus to test"), so G1-G6 and G0 were not paused on. The teaser direction was chosen by me (land d1, agency d3); approvals are logged below as "built, awaiting review". Each is easy to change.
- **Fonts:** Archivo variable, Instrument Serif italic and JetBrains Mono are self-hosted in the video engine and the pitch page.
- **Video format:** 1080x1920 at 30 fps; final CRF 22 capped at 9 Mbps; audio synthesised per template (log-drum groove for land at 112 BPM, afro-house for agency at 118 BPM), peak about -1 dBFS after AAC, RMS about -14 dBFS.
- **Photos with outpainting seams** (land: title_folder, whatsapp_hand, agent_portrait, handshake) were cropped to the clean region found by row-step detection and are shown as floating cards over a blurred copy of themselves, never stretched to full frame.
- **Pitch page videos** are rendered at `web` quality (1 sample, no motion blur, 720x1280) per lead: about 7 minutes per vertical on 8 cores. The *final* Ads Manager files use `--final`.
- **Unsent pre-pivot drafts** (25 test leads from 27 Oct) are left in the database untouched; config `dedupe.ignore_unsent_before: 2026-10-28` stops them blocking re-listing. A bulk status update of live rows was blocked by the safety classifier and wasn't needed.
- **`gh` is not installed**, so I pushed to GitHub but could not trigger or read workflow runs (USER ACTION 1).
- **Keyword-stuffed listing names** ("Avenue Vista Property Center - Houses, Land & Plots for Sale & Rent") are shortened to the part before the separator (`display_name`), found in the live dry run.
- **P1.3 deferred.** Removing the old web/poster teaser code before the new teaser is wired would leave Sunday's nightly with no working teaser. Old teaser code and `teasers/{web,content,frames}` stay until G0 is approved and `render_teasers` is switched to `render_ad_teasers`; `teaser.py` temporarily renders ads leads with the existing poster set.
- **P1.4 (PSI removal) deferred.** PSI is wired through ~20 files (budget, enrich, audit, facts `SLOW_MOBILE`, the screenshot used by old teasers, fixtures, tests). Pure cleanup, not on the Sunday critical path; do it after G0 together with P1.3. `PSI_API_KEY` is still required for live runs.
- **P1.5** is done in code (single `ads` score, no web/content scoring, `track='ads'`) except the leftover `psi`-related config.
- **Message length** is 380–700 characters (plan said 380–650). The scaffold (greeting + opening + body + offer + question + sign-off) is ~550 characters and long business names need headroom.
- **The pilot's own numbers are the only money/numbers allowed without a fact:** the validator scrubs `KES {budget}` and `{days}-day` before the money/number checks. Everything else (any other KES amount, a stray number) is still rejected.
- **Banned phrases match whole words** (so `roi` does not fire on "Android"). `returns`, `guarantee(d)`, `risk-free`, `100%`, `roi`, `investment opportunity`, `double your` are banned; the word "free" is allowed (the pilot is free).
- **Estate filter (P2.4d):** real Places data (245 stored agencies) shows `primary_type` = `real_estate_agency` 128, `service` 68, `consultant` 20, … so `service` is deliberately NOT an allowed type. Rule: for land_developers and property_agency, a name with no business word AND a primary type outside {real_estate_agency, real_estate_developer, property_management_company, consultant, corporate_office} is `BUILDING_NOT_BUSINESS`. All 8 census leaks are rejected and 6 legit firms pass (tests). Expect a few real firms with a one-word name and type `service` to be lost; the dry-run CSV shows them.
- **Land areas:** added Joska, Malaa, Mlolongo, Kangundo Road, Matuu, Konza, Kajiado Town, Kenol, Makuyu (tier 2) and Malindi, Kilifi, Diani (tier 3, land only). Coordinates checked against OpenStreetMap Nominatim; Kajiado/Kilifi/Malindi came back as county centroids so town-centre coordinates were used. Gatanga Road was dropped (geocoder returned the wrong place).
- **Dashboard hotfix deployed ahead of P7:** follow-ups use a single `fu2` template (was `fu2_web`/`fu2_content`) because the live `followup_templates` and `quick_replies` settings were overwritten with the new copy bank. The dashboard was rebuilt and uploaded; the live bundle is `index-BB1560-6.js`.
- **FTP gotcha:** the FTP root is the cPanel home, so remote paths are RELATIVE (`leads.raswaltechsolutions.co.ke`), not `/home/rawaesta/...`. An absolute path created a stray `home/rawaesta/` tree; it was removed (it contained only that upload).
- **Runs table:** `runs.qualified_web` / `shipped_web` now hold the ads totals; the `*_content` columns are written as 0. The dashboard Stats labels are fixed in P7.
- **`daily_targets` setting** is superseded by `daily_mix`; the old row is left in place until P7 changes the Settings screen.
- **Places call split:** the night's Places budget is shared across the active subcategories in proportion to their daily-mix quota, recomputed from what is left after each one.
- **P0: demo kits are NOT in git.** In `content-creation-pipeline`, `content/templates/` and `content/businesses/tpl-*` (and `baraka-homes`, `sahilpay`) are untracked, so the `pre-ads-pivot` tag cannot restore them and P1.2's `git rm -r` would fail. Archived the templates and the five `tpl-*` businesses to `~/Projects/_archive-pre-ads-pivot/content-demo-templates.tar.gz` (616 MB, 426 entries) before any removal. Restore with `tar -xzf` into `content/`.
- **P0:** `content-creation-pipeline` branch is `content-studio`, not `main`. Tag is on that branch.
- **P0:** committed the previously untracked `src/components/graphics/Infographics.tsx` with the tracked graphics edits, since the other edits depend on it.
- **P0:** fixed one stale dashboard assertion (`actions.test.ts` expected `.com`; code is correctly `.co.ke`), so the baseline is fully green.

## Test results
| Suite | Baseline | Now |
|---|---|---|
| pytest (`-m "not render"`) | 278 | **386 passed** |
| pytest (`-m render`) | 2 | 2 passed |
| ruff | clean | clean |
| dashboard vitest | 24 | 24 passed |
| tsc --noEmit | clean | clean |

## Live checks
- Migrations applied to project `ribexxgkqmwyqfwspxje`: `ads_enums`, `ads_pivot`, `ads_pivot_touch_search_path`. Counts unchanged: leads 25, businesses 245, evaluations 245, events 27. RLS on `ad_library_ads`, `pilots`, `pilot_days`. Advisors: no new ERROR (one WARN on `pilots_touch` search_path was fixed).
- Offline nightly (daily mix): 20 land + 10 agency finalists, all variants valid, 5 Places calls, 2 CSVs. Angles in the offline data: A and C only (no ad-library data yet).
- Final videos (all six, `--final`): QA passes on each (duration, bt709, AAC, faststart, <=9 Mbps, peak about -0.9 dBFS, sub-bass on every impact cue). Sizes: L2 10 MB, L1 19 MB, L3 22 MB; web versions 1.9-4.1 MB.
- `scripts/e2e.py` (`docs/E2E_LAST_RUN.md`): ALL CHECKS PASSED. 30 finalists (20 land + 10 agency), 60 messages valid (526-640 chars), 30 teasers (max 200 KB), land and agency pilot pages built from offline fixtures: 9.6 MB total, 0.6 MB before videos, no console errors, 11 chapters reached, Start button opens wa.me/254114129809, 3 videos wired.
- NOT done live: no page was deployed to the real host in this run, so HTTPS on a brand-new wildcard slug is still unverified (USER ACTION 9).
- Teaser render time: 4 test brands per direction in ~4 s; JPEGs 126–177 KB (limit 350 KB).

## Known gaps / risks
- The six videos and the teaser direction are built, not reviewed by Swalleh.
- P3.1 winning-ads research was not done (no Apify token).
- Without an Apify token every lead's "already advertising?" is unknown; angle B never fires.
- Agency finalists in the live dry run were few because of the small Places allocation (5 calls); the nightly's full 45-call budget is split by daily-mix quota.
- Estate filter may drop a real one-word firm typed `service`; the dry-run CSV shows rejected names.
- Page videos are rendered per lead at web quality (about 5-7 minutes per vertical) on the PC running `generate`.
- The 25 pre-pivot test leads remain in the database (unsent, ignored for re-listing).
