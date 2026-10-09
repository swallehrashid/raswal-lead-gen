from datetime import date

import pytest

from pipeline.utils.dates import WorkCalendar
from tests.conftest import load_json

CASES = load_json("workdays_cases.json")["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_working_day_vectors(cfg, case):
    cal = WorkCalendar.from_config(cfg.calendar)
    cal.pauses_block_followups = case["pauses_block_followups"]
    got = cal.add_working_days(date.fromisoformat(case["start"]), case["n"])
    assert got.isoformat() == case["expect"]


def test_list_dates(cfg):
    cal = WorkCalendar.from_config(cfg.calendar)
    assert cal.next_list_date(date(2026, 10, 11)) == date(2026, 10, 12)   # Sun night → Mon
    assert cal.next_list_date(date(2026, 10, 15)) == date(2026, 10, 16)   # Thu night → Fri
    assert cal.next_list_date(date(2026, 10, 16)) == date(2026, 10, 19)   # (manual Fri run) → Mon
    tue = cal.next_list_date(date(2026, 10, 19))
    assert tue == date(2026, 10, 20) and "Mashujaa" in cal.skip_reason(tue)
    assert "December break" in cal.skip_reason(date(2026, 12, 22))
    assert cal.skip_reason(date(2026, 10, 12)) is None
