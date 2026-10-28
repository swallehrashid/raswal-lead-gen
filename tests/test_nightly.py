import csv
from datetime import date

import pytest

from pipeline.nightly import NightlyOptions, run_nightly
from pipeline.settings import Env, MissingSecrets
from pipeline.store import MemoryStore


def opts(tmp_path, **kw):
    base = dict(list_date=date(2026, 10, 12), subcategory=None, dry_run=True, offline=True,
                no_render=True, out_dir=tmp_path)
    base.update(kw)
    return NightlyOptions(**base)


def test_offline_dry_run_daily_mix_end_to_end(cfg, tmp_path):
    r = run_nightly(cfg, Env(), opts(tmp_path))
    assert r.status == "ok" and r.stats["places_calls"] <= 5
    assert sorted(p.name for p in r.csv_paths) == ["2026-10-12-land_developers.csv", "2026-10-12-property_agency.csv"]
    for p in r.csv_paths:
        rows = list(csv.DictReader(p.open()))
        assert rows and all("gate_codes" in row and "angle" in row for row in rows)
    fin = [c for c in r.candidates if c.selection == "finalist"]
    assert sum(c.subcategory == "land_developers" for c in fin) == 20
    assert sum(c.subcategory == "property_agency" for c in fin) == 10
    for c in fin:
        assert c.track == "ads" and c.angle in {"A", "B", "C"}
        assert len(c.variants) == 2 and all(not v.errors for v in c.variants), c.name
        assert all("enquiries on your WhatsApp" in v.message for v in c.variants)
        assert c.facts_for("ads") and c.lead_id and c.slug
    assert len({c.phone_e164 for c in fin}) == len(fin) and len({c.place_id for c in r.candidates}) == len(r.candidates)


def test_single_subcategory_manual_run(cfg, tmp_path):
    r = run_nightly(cfg, Env(), opts(tmp_path, subcategory="property_agency"))
    fin = [c for c in r.candidates if c.selection == "finalist"]
    assert {c.subcategory for c in fin} == {"property_agency"} and len(fin) == 10
    assert [p.name for p in r.csv_paths] == ["2026-10-12-property_agency.csv"]


def test_paused_vertical_can_still_be_run_by_hand(cfg, tmp_path):
    r = run_nightly(cfg, Env(), opts(tmp_path, subcategory="construction"))
    assert r.status == "ok"
    assert all(c.subcategory == "construction" for c in r.candidates)


def test_offline_live_run_writes_leads_and_settings(cfg, tmp_path):
    r = run_nightly(cfg, Env(), opts(tmp_path, dry_run=False))
    store: MemoryStore = r.store
    leads = list(store.tables["leads"].values())
    assert sum(lead["status"] == "shortlisted" for lead in leads) == 30
    assert sum(lead["status"] == "reserve" for lead in leads) >= 1
    assert {"calendar", "quick_replies", "followup_templates", "daily_mix", "outreach_whatsapp", "pilot"} \
        <= set(store.tables["settings"])
    assert all(lead["track"] == "ads" and lead["brand"]["angle"] in {"A", "B", "C"} for lead in leads)
    runs = list(store.tables["runs"].values())
    assert {r_["subcategory"] for r_ in runs} == {"property_agency", "land_developers"}
    assert all(r_["status"] == "ok" and r_["gate_counts"] for r_ in runs)
    assert sorted(r_["shipped_web"] for r_ in runs) == [10, 20]            # ads totals live in the *_web columns
    assert store.get_usage(date.today().strftime("%Y-%m"), "places") >= 1
    for lead in leads:                                                      # every lead links to its evaluation and facts
        assert lead["evaluation_id"] in store.tables["facts"]
    evals = list(store.tables["evaluations"].values())
    assert all(e["breakdown"].get("angle") in {"A", "B", "C", None} for e in evals)


def test_overlap_between_subcategories_yields_one_lead(cfg):
    from pipeline.nightly import resolve_overlap
    from tests.helpers import make
    a = make("Both Realtors", sub="property_agency")
    b = make("Both Realtors", sub="land_developers")
    b.place_id = a.place_id
    a.pre_score = b.pre_score = 10
    assert resolve_overlap([a, b]) == [b]                                   # tie → land_developers
    a.pre_score = 30
    assert resolve_overlap([a, b]) == [a]                                   # higher score wins
    a.gate_codes = ["TOO_SMALL"]
    assert resolve_overlap([a, b]) == [b]                                   # a candidate that passes gates beats one that fails


def test_holiday_is_skipped(cfg, tmp_path):
    r = run_nightly(cfg, Env(), opts(tmp_path, list_date=date(2026, 10, 20), subcategory=None))
    assert r.status == "skipped" and "Mashujaa" in r.skipped_reason


def test_live_run_without_keys_fails_fast_naming_everything(cfg, tmp_path):
    with pytest.raises(MissingSecrets) as e:
        run_nightly(cfg, Env(), opts(tmp_path, offline=False, dry_run=False))
    assert set(e.value.names) == {"GOOGLE_PLACES_API_KEY", "GEMINI_API_KEY", "SUPABASE_URL",
                                  "SUPABASE_SERVICE_ROLE_KEY"}


def test_dry_run_no_db_needs_no_supabase(cfg, tmp_path):
    with pytest.raises(MissingSecrets) as e:
        run_nightly(cfg, Env(), opts(tmp_path, offline=False, no_db=True, no_llm=True))
    assert set(e.value.names) == {"GOOGLE_PLACES_API_KEY"}


def test_cli_exit_code_and_message(capsys, monkeypatch):
    from pipeline.__main__ import main
    for k in ("GOOGLE_PLACES_API_KEY", "PSI_API_KEY", "GEMINI_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr("pipeline.settings.load_dotenv", lambda *a, **k: None)
    assert main(["nightly", "--dry-run", "--subcategory", "property_agency"]) == 2
    err = capsys.readouterr().err
    assert "GOOGLE_PLACES_API_KEY" in err and "SETUP_CHECKLIST.md" in err


def test_dashboard_daily_mix_and_pause_apply(cfg, tmp_path):
    store = MemoryStore()
    store.tables["settings"]["daily_mix"] = {"key": "daily_mix", "value": {"land_developers": 5, "property_agency": 2}}
    r = run_nightly(cfg, Env(), opts(tmp_path, dry_run=False, store=store))
    assert r.stats["per_subcategory"]["land_developers"]["shipped"] == 5
    assert r.stats["per_subcategory"]["property_agency"]["shipped"] == 2
    pause = [{"start": "2026-10-13", "end": "2026-10-13", "note": "funeral"}]
    store.tables["settings"]["pause_list"] = {"key": "pause_list", "value": pause}
    r = run_nightly(cfg, Env(), opts(tmp_path, dry_run=False, store=store, list_date=date(2026, 10, 13)))
    assert r.status == "skipped" and "funeral" in r.skipped_reason


def test_dashboard_daily_mix_ignores_bad_values(cfg):
    from pipeline.nightly import apply_dashboard_settings
    c2 = apply_dashboard_settings(cfg, {"daily_mix": {"land_developers": "x", "property_agency": -3, "nonsense": 9}})
    assert c2.scoring.selection.daily_mix == {"land_developers": 20, "property_agency": 0}
