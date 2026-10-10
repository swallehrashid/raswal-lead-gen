# Raswal Lead Generator

A nightly job plus a small private dashboard that builds a short list of strictly qualified Kenyan
real estate and construction businesses each weekday. Messages are sent by hand on WhatsApp.

- Spec: [docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md) · daily routine: [docs/DAILY_PLAYBOOK.md](docs/DAILY_PLAYBOOK.md) · accounts and secrets: [docs/SETUP_CHECKLIST.md](docs/SETUP_CHECKLIST.md)
- **What's built, what still needs real keys, and your first live test: [docs/STATUS.md](docs/STATUS.md)**
- Small decisions made while building: [docs/DECISIONS.md](docs/DECISIONS.md) · swapping in your templates: [teasers/README.md](teasers/README.md)

## Try it with no keys

```bash
uv venv -p 3.12 .venv && uv pip install -p .venv -r requirements-dev.txt
.venv/bin/playwright install chromium
.venv/bin/pytest                                               # 281 tests
.venv/bin/python -m pipeline nightly --offline --dry-run       # whole pipeline on fixtures → out/ (CSV + teaser JPEGs)
.venv/bin/python -m pipeline rerender --offline                # teaser samples for all 5 subcategories → out/teasers/samples/
cd dashboard && npm install && npm run dev                     # dashboard on mock data, no backend
```

## Layout

| Path | What |
|---|---|
| `config/*.yaml` | every tunable: queries, areas, weights, thresholds, caps, message rules, holidays |
| `pipeline/` | the nightly job (`python -m pipeline --help`) |
| `teasers/` | HTML templates, fonts and device frames for teaser images |
| `dashboard/` | React + Vite + Tailwind PWA (mock data layer or Supabase) |
| `supabase/` | migrations, RLS, storage policy, generated `seed.sql` |
| `scripts/verify-migrations/` | applies the migrations to in-process Postgres and tests RLS |
| `tests/` | pytest suite and fixtures (Places, sites, PSI, Gemini) |

Secrets live in `.env` (git-ignored; see `.env.example`) or GitHub Actions secrets, never in the repo.
