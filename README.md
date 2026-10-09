# Raswal Lead Generator

A nightly job plus a small private dashboard that builds a short list of strictly qualified Kenyan
real estate and construction businesses each weekday. See [docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md)
for the spec, [docs/DAILY_PLAYBOOK.md](docs/DAILY_PLAYBOOK.md) for the daily routine and
[docs/STATUS.md](docs/STATUS.md) for what's built and how to run it.

## Quick start (no keys needed)

```bash
uv venv -p 3.12 .venv && uv pip install -p .venv -r requirements-dev.txt   # or python3.12 -m venv + pip
.venv/bin/playwright install chromium
.venv/bin/pytest
.venv/bin/python -m pipeline nightly --offline --dry-run      # whole pipeline on fixtures → out/
```
