# Ads pivot report

Executor: Sonnet 5.5. Plan: `/home/swalleh/Content/RASWAL-ADS-PIVOT-EXECUTION.md`.

## Swalleh's open USER ACTIONS (P9)
- ⬜ 1. Meta Business Portfolio for Raswal, verified; note the 16-digit Portfolio ID
- ⬜ 2. Ad account in the portfolio (KES if offered)
- ⬜ 3. Working payment method + backup (virtual USD card); second ad account ready
- ⬜ 4. Raswal's own FB Page + Instagram + WhatsApp Business on the dedicated outreach number
- ⬜ 5. Warm-up click-to-WhatsApp ad for Raswal itself (KES 1–2k)
- ⬜ 6. M-Pesa till/paybill for client ad budgets
- ⬜ 7. Apify account + `APIFY_TOKEN` in `.env` and GitHub secret; $10/month limit
- ⬜ 8. Google Flow images from `raswal-pipeline/ads/assets/flow-prompts.md` (not written yet, P3.2)
- ⬜ 9. Record the 4 access-guide screen recordings (P8.3)
- ⬜ 10. Tell Sonnet the outreach WhatsApp number (needed for P2.1 `outreach_whatsapp` setting)
- ⬜ 11. Confirm wildcard HTTPS on a brand-new slug after the first pilot deploy

## Status by phase
| Phase | State | Note |
|---|---|---|
| P0 | ✅ | three repos tagged `pre-ads-pivot`; demo kits archived (they were untracked) |
| P1 | 🟡 | P1.1 ✅ debug leftovers · P1.2 ✅ content track + demo kits removed · **P1.3 teaser code, P1.4 PSI, P1.5 leftovers DEFERRED** (see deviations) |
| P2 | 🟡 | P2.1 ✅ migrations applied live · P2.2 ✅ config · P2.3 ✅ daily mix · P2.4 (c) scam + (d) estate filter ✅, **(a) ad-library sync + (b) social activity NOT yet** · P2.5 ✅ ads score (threshold needs live calibration) · P2.6 ✅ messages · P2.7 ✅ copy bank + live DB reseeded · **P2.8 existing 25 leads NOT yet** · **P2.9 push + workflow dry run NOT yet** |
| P3 | 🟡 | P3.2 ✅ Flow prompt sheet written (USER ACTION 8) · P3.1 winning-ads research, P3.3 prepare.py NOT yet |
| P4 | 🟡 | 3 directions built, rendered for 4 test brands; **waiting on gate G0** |
| P5–P10 | ⬜ | |

## Approval log
| Gate | Item | Version | Date | Swalleh's notes |
|---|---|---|---|---|

## Removal ledger
| Path | Repo | Why removed | References fixed |
|---|---|---|---|

## Decisions & deviations
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
| pytest (`-m "not render"`) | 278 | **367 passed** |
| pytest (`-m render`) | 2 | 2 passed |
| ruff | clean | clean |
| dashboard vitest | 24 | 24 passed |
| tsc --noEmit | clean | clean |

## Live checks
- Migrations applied to project `ribexxgkqmwyqfwspxje`: `ads_enums`, `ads_pivot`, `ads_pivot_touch_search_path`. Counts unchanged: leads 25, businesses 245, evaluations 245, events 27. RLS on `ad_library_ads`, `pilots`, `pilot_days`. Advisors: no new ERROR (one WARN on `pilots_touch` search_path was fixed).
- Offline nightly (daily mix): 20 land + 10 agency finalists, all variants valid, 5 Places calls, 2 CSVs. Angles in the offline data: A and C only (no ad-library data yet).
- Teaser render time: 4 test brands per direction in ~4 s; JPEGs 126–177 KB (limit 350 KB).

## Known gaps / risks
