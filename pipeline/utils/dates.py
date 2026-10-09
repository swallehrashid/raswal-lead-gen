"""Working days, list dates and follow-up dates (brief §5, §12.6, §15.2).

The dashboard has a TypeScript twin (dashboard/src/lib/workdays.ts). Both are tested
against the same vectors in tests/fixtures/workdays_cases.json.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def weekday_key(d: date) -> str:
    return WEEKDAY_KEYS[d.weekday()]


class WorkCalendar:
    def __init__(self, send_days, holidays: dict[date, str], pauses: list[tuple[date, date, str]],
                 pauses_block_followups: bool = True, tz: str = "Africa/Nairobi"):
        self.send_days = set(send_days)
        self.holidays = dict(holidays)
        self.pauses = list(pauses)
        self.pauses_block_followups = pauses_block_followups
        self.tz = ZoneInfo(tz)

    @classmethod
    def from_config(cls, cal) -> WorkCalendar:
        return cls(
            send_days=cal.send_days,
            holidays={h.date: h.name for h in cal.holidays},
            pauses=[(p.start, p.end, p.name) for p in cal.pauses],
            pauses_block_followups=cal.pauses_block_followups,
            tz=cal.timezone,
        )

    def pause_for(self, d: date) -> str | None:
        for start, end, name in self.pauses:
            if start <= d <= end:
                return name
        return None

    def is_send_day(self, d: date) -> bool:
        return weekday_key(d) in self.send_days

    def is_working_day(self, d: date, *, for_followups: bool = True) -> bool:
        if not self.is_send_day(d) or d in self.holidays:
            return False
        if self.pause_for(d) and (self.pauses_block_followups or not for_followups):
            return False
        return True

    def skip_reason(self, list_date: date) -> str | None:
        """Why no list should be built for list_date (None = build it)."""
        if not self.is_send_day(list_date):
            return f"{list_date} is not a send day"
        if list_date in self.holidays:
            return f"{list_date} is a public holiday ({self.holidays[list_date]})"
        if name := self.pause_for(list_date):
            return f"{list_date} is inside a pause ({name})"
        return None

    def add_working_days(self, start: date, n: int) -> date:
        """The date n working days after start (start itself is never counted)."""
        d, left = start, n
        while left > 0:
            d += timedelta(days=1)
            if self.is_working_day(d):
                left -= 1
        return d

    def now(self) -> datetime:
        return datetime.now(self.tz)

    def next_list_date(self, today: date | None = None) -> date:
        """The list built tonight is for the next send day after today (local time).

        Holidays are NOT skipped here: a holiday list date makes the run exit cleanly
        (brief §16.1), so the themed day is simply missed that week.
        """
        d = (today or self.now().date()) + timedelta(days=1)
        while not self.is_send_day(d):
            d += timedelta(days=1)
        return d
