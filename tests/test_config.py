import shutil

import pytest
import yaml

from pipeline.seed import config_cells, generate_seed_sql
from pipeline.settings import CONFIG_DIR, load_config


def test_config_loads(cfg):
    assert len(cfg.subcategories) == 5
    assert [s.key for s in cfg.active_subcategories] == ["property_agency", "land_developers"]
    assert cfg.scoring.selection.daily_mix == {"land_developers": 20, "property_agency": 10}
    assert cfg.budget.places.calls_per_night == 40
    assert cfg.budget.places.calls_per_month == 900
    assert cfg.scoring.ads.min_score == 35
    assert cfg.pilot.budget_kes == 5000 and cfg.pilot.pilot_days == 7


def test_paused_subcategories_are_inactive(cfg):
    for key in ("construction", "hardware_supplies", "roofing_steel"):
        assert not cfg.subcategories[key].active


def test_every_subcategory_has_tier1_cells(cfg):
    cells = config_cells(cfg)
    for key, sub in cfg.subcategories.items():
        assert any(c.subcategory == key and c.tier == 1 for c in cells), key
        assert any(c.subcategory == key and c.tier == 3 for c in cells) == sub.tier3_enabled


def test_new_land_areas_are_in_tier_two_and_three(cfg):
    names = {a.name: a.tier for a in cfg.areas.areas}
    for n in ("Joska", "Malaa", "Mlolongo", "Kangundo Road", "Matuu", "Konza", "Kajiado Town", "Kenol", "Makuyu"):
        assert names[n] == 2, n
    for n in ("Malindi", "Kilifi", "Diani"):
        assert names[n] == 3, n


def test_subcategory_rename_needs_subcategories_and_daily_mix(tmp_path):
    """Renaming a subcategory key touches config/subcategories.yaml and its daily_mix/reserves keys only."""
    d = tmp_path / "config"
    shutil.copytree(CONFIG_DIR, d)
    data = yaml.safe_load((d / "subcategories.yaml").read_text())
    data["subcategories"]["estate_agents"] = data["subcategories"].pop("property_agency")
    (d / "subcategories.yaml").write_text(yaml.safe_dump(data))
    sc = yaml.safe_load((d / "scoring.yaml").read_text())
    for k in ("daily_mix", "reserves"):
        sc["selection"][k]["estate_agents"] = sc["selection"][k].pop("property_agency")
    (d / "scoring.yaml").write_text(yaml.safe_dump(sc))
    cfg = load_config(d)
    assert "estate_agents" in [s.key for s in cfg.active_subcategories]
    assert cfg.subcategories["estate_agents"].template == "property_agency"   # teaser folder unchanged
    assert "estate_agents" in generate_seed_sql(cfg)


def test_daily_mix_with_unknown_subcategory_rejected(tmp_path):
    d = tmp_path / "config"
    shutil.copytree(CONFIG_DIR, d)
    sc = yaml.safe_load((d / "scoring.yaml").read_text())
    sc["selection"]["daily_mix"]["nonsense"] = 5
    (d / "scoring.yaml").write_text(yaml.safe_dump(sc))
    with pytest.raises(ValueError, match="daily_mix"):
        load_config(d)


def test_seed_sql_is_current(cfg):
    """supabase/seed.sql must match config (regenerate with `python -m pipeline gen-seed`)."""
    from pipeline.settings import ROOT
    assert (ROOT / "supabase" / "seed.sql").read_text() == generate_seed_sql(cfg)


def test_pilot_numbers_flow_into_copy(cfg):
    """Prices and the budget are written once (pilot.yaml) and filled into quick replies / follow-ups."""
    from pipeline.seed import settings_payload
    payload = settings_payload(cfg)
    texts = " ".join(q["text"] for q in payload["quick_replies"]) + " ".join(payload["followup_templates"].values())
    assert "{budget}" not in texts and "{engine_intro}" not in texts and "{days}" not in texts
    assert "10,000" in texts and "5,000" in texts and "12,000" in texts and "{business}" in texts
