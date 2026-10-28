"""API call counters with nightly and monthly hard caps (brief §6.4).

Every external call goes through `Budget.spend(api)` *before* the request is made.
When a cap is reached `BudgetExhausted` is raised and the caller stops that stage cleanly.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import date

log = logging.getLogger(__name__)


class BudgetExhausted(Exception):
    def __init__(self, api: str, reason: str):
        super().__init__(f"{api} budget exhausted: {reason}")
        self.api, self.reason = api, reason


@dataclass
class Cap:
    per_night: int
    per_month: int | None = None
    sku: str = "default"


@dataclass
class Budget:
    caps: dict[str, Cap]
    month_used: dict[str, int]                   # api → count already used this month (from api_usage)
    month: str
    recorder: object | None = None               # store with incr_usage(month, api, sku, n)
    night_used: dict[str, int] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @classmethod
    def from_config(cls, cfg, store, run_date: date, *, places_override: int | None = None,
                    dry_run: bool = False) -> Budget:
        b = cfg.budget
        places_night = places_override if places_override is not None else (
            b.places.dry_run_calls if dry_run else b.places.calls_per_night)
        # an override can lower the nightly cap, never raise it above the configured nightly cap
        places_night = min(places_night, b.places.calls_per_night)
        month = run_date.strftime("%Y-%m")
        # Place Details (New) reviews fetch — separate billed SKU, only for gate-passers.
        details_night = 20 if dry_run else getattr(b.places, "details_per_night", 50)
        details_month = getattr(b.places, "details_per_month", 1000)
        caps = {
            "places": Cap(places_night, b.places.calls_per_month, b.places.sku),
            "places_details": Cap(details_night, details_month, "place_details_enterprise"),
            "psi": Cap(b.psi.calls_per_night, None, "runpagespeed"),
            "gemini": Cap(b.gemini.calls_per_night, None, "generate_content"),
        }
        used = {api: store.get_usage(month, api) for api in caps}
        return cls(caps=caps, month_used=used, month=month, recorder=store)

    def remaining(self, api: str) -> int:
        cap = self.caps[api]
        left = cap.per_night - self.night_used.get(api, 0)
        if cap.per_month is not None:
            left = min(left, cap.per_month - self.month_used.get(api, 0))
        return max(0, left)

    def spend(self, api: str, n: int = 1) -> None:
        with self._lock:
            cap = self.caps[api]
            night = self.night_used.get(api, 0)
            month = self.month_used.get(api, 0)
            if night + n > cap.per_night:
                raise BudgetExhausted(api, f"nightly cap {cap.per_night} reached")
            if cap.per_month is not None and month + n > cap.per_month:
                raise BudgetExhausted(api, f"monthly cap {cap.per_month} reached ({month} used in {self.month})")
            self.night_used[api] = night + n
            self.month_used[api] = month + n
        if self.recorder is not None:
            self.recorder.incr_usage(self.month, api, cap.sku, n)

    def used(self, api: str) -> int:
        return self.night_used.get(api, 0)
