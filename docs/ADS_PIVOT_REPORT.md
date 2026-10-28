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
| P0 | 🟡 | tags done; push pending |
| P1–P10 | ⬜ | |

## Approval log
| Gate | Item | Version | Date | Swalleh's notes |
|---|---|---|---|---|

## Removal ledger
| Path | Repo | Why removed | References fixed |
|---|---|---|---|

## Decisions & deviations
- **P0: demo kits are NOT in git.** In `content-creation-pipeline`, `content/templates/` and `content/businesses/tpl-*` (and `baraka-homes`, `sahilpay`) are untracked, so the `pre-ads-pivot` tag cannot restore them and P1.2's `git rm -r` would fail. Archived the templates and the five `tpl-*` businesses to `~/Projects/_archive-pre-ads-pivot/content-demo-templates.tar.gz` (616 MB, 426 entries) before any removal. Restore with `tar -xzf` into `content/`.
- **P0:** `content-creation-pipeline` branch is `content-studio`, not `main`. Tag is on that branch.
- **P0:** committed the previously untracked `src/components/graphics/Infographics.tsx` with the tracked graphics edits, since the other edits depend on it.
- **P0:** fixed one stale dashboard assertion (`actions.test.ts` expected `.com`; code is correctly `.co.ke`), so the baseline is fully green.

## Test results
| Suite | Baseline (before pivot) |
|---|---|
| pytest (`-m "not render"`) | 278 passed, 2 deselected |
| ruff | clean |
| dashboard vitest | 24 passed (after the `.co.ke` assertion fix; 23/24 before) |
| tsc --noEmit | clean |

## Live checks

## Known gaps / risks
