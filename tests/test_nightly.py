import csv
from datetime import date

import pytest

from pipeline.nightly import NightlyOptions, run_nightly
from pipeline.settings import Env, MissingSecrets
from pipeline.store import MemoryStore


def opts(tmp_path, **kw):
    base = dict(list_date=date(2026, 10, 12), subcategory="property_agency", dry_run=True, offline=True,
                no_render=True, out_dir=tmp_path)
    base.update(kw)
    return NightlyOptions(**base)


def test_offline_dry_run_end_to_end(cfg, tmp_path):
    r = run_nightly(cfg, Env(), opts(tmp_path))
    assert r.status == "ok" and r.stats["places_calls"] <= 5
    rows = list(csv.DictReader(r.csv_path.open()))
    assert len(rows) >= 78 and all("gate_codes" in row for row in rows)
    fin = [c for c in r.candidates if c.selection == "finalist"]
    assert sum(c.track == "web" for c in fin) == 20 and sum(c.track == "content" for c in fin) == 10
    for c in fin:
        assert len(c.variants) == 2 and all(not v.errors for v in c.variants), c.name
        assert any(f.strength == "strong" for f in c.facts_for(c.track))
        assert c.lead_id and c.slug


def test_offline_live_run_writes_leads_and_settings(cfg, tmp_path):
    r = run_nightly(cfg, Env(), opts(tmp_path, dry_run=False))
    store: MemoryStore = r.store
    leads = list(store.tables["leads"].values())
    assert sum(lead["status"] == "shortlisted" for lead in leads) == 30
    assert sum(lead["status"] == "reserve" for lead in leads) >= 1
    assert {"calendar", "quick_replies", "followup_templates"} <= set(store.tables["settings"])
    run = next(iter(store.tables["runs"].values()))
    assert run["status"] == "ok" and run["shipped_web"] == 20 and run["gate_counts"]
    assert store.get_usage(date.today().strftime("%Y-%m"), "places") >= 1
    # every lead links to its evaluation and facts
    for lead in leads:
        assert lead["evaluation_id"] in store.tables["facts"]


def test_holiday_is_skipped(cfg, tmp_path):
    r = run_nightly(cfg, Env(), opts(tmp_path, list_date=date(2026, 10, 20), subcategory=None))
    assert r.status == "skipped" and "Mashujaa" in r.skipped_reason


def test_live_run_without_keys_fails_fast_naming_everything(cfg, tmp_path):
    with pytest.raises(MissingSecrets) as e:
        run_nightly(cfg, Env(), opts(tmp_path, offline=False, dry_run=False))
    assert set(e.value.names) == {"GOOGLE_PLACES_API_KEY", "PSI_API_KEY", "GEMINI_API_KEY", "SUPABASE_URL",
                                  "SUPABASE_SERVICE_ROLE_KEY"}


def test_dry_run_no_db_needs_no_supabase(cfg, tmp_path):
    with pytest.raises(MissingSecrets) as e:
        run_nightly(cfg, Env(), opts(tmp_path, offline=False, no_db=True, no_llm=True))
    assert set(e.value.names) == {"GOOGLE_PLACES_API_KEY", "PSI_API_KEY"}


def test_cli_exit_code_and_message(capsys, monkeypatch):
    from pipeline.__main__ import main
    for k in ("GOOGLE_PLACES_API_KEY", "PSI_API_KEY", "GEMINI_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr("pipeline.settings.load_dotenv", lambda *a, **k: None)
    assert main(["nightly", "--dry-run", "--subcategory", "property_agency"]) == 2
    err = capsys.readouterr().err
    assert "GOOGLE_PLACES_API_KEY" in err and "SETUP_CHECKLIST.md" in err
