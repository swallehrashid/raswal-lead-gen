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
