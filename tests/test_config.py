import shutil

import pytest
import yaml

from pipeline.seed import config_cells, generate_seed_sql
from pipeline.settings import CONFIG_DIR, load_config


def test_config_loads(cfg):
    assert len(cfg.subcategories) == 5
    days = sorted(s.list_day for s in cfg.subcategories.values())
    assert days == sorted(["mon", "tue", "wed", "thu", "fri"])
    assert cfg.budget.places.calls_per_night == 40
    assert cfg.budget.places.calls_per_month == 900
    assert cfg.scoring.web.min_score == 38 and cfg.scoring.content.min_score == 42


def test_every_subcategory_has_tier1_cells(cfg):
    cells = config_cells(cfg)
    for key in cfg.subcategories:
        assert any(c.subcategory == key and c.tier == 1 for c in cells), key
        assert not any(c.subcategory == key and c.tier == 3 for c in cells), "tier 3 is off by default"


def test_subcategory_rename_is_config_only(tmp_path):
    """Renaming a subcategory key only needs config/subcategories.yaml (brief §0)."""
    d = tmp_path / "config"
    shutil.copytree(CONFIG_DIR, d)
    data = yaml.safe_load((d / "subcategories.yaml").read_text())
    data["subcategories"]["estate_agents"] = data["subcategories"].pop("property_agency")
    (d / "subcategories.yaml").write_text(yaml.safe_dump(data))
    cfg = load_config(d)
    sub = cfg.subcategory_for_day("mon")
    assert sub.key == "estate_agents"
    assert sub.template == "property_agency"   # teaser folder unchanged
    assert "estate_agents" in generate_seed_sql(cfg)


def test_duplicate_list_day_rejected(tmp_path):
    d = tmp_path / "config"
    shutil.copytree(CONFIG_DIR, d)
    data = yaml.safe_load((d / "subcategories.yaml").read_text())
    data["subcategories"]["construction"]["list_day"] = "mon"
    (d / "subcategories.yaml").write_text(yaml.safe_dump(data))
    with pytest.raises(ValueError, match="list_day"):
        load_config(d)


def test_seed_sql_is_current(cfg):
    """supabase/seed.sql must match config (regenerate with `python -m pipeline gen-seed`)."""
    from pipeline.settings import ROOT
    assert (ROOT / "supabase" / "seed.sql").read_text() == generate_seed_sql(cfg)
