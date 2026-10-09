"""Gemini client: JSON-schema output, ≤ N requests/minute, 429 handling (brief §12.1).

Free-tier daily quotas are small and change over time. A per-day 429 trips a circuit
breaker: every later lead that night uses the deterministic fallback instead of retrying.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Literal

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- output schema (contract-tested)

class ReviewFactOut(BaseModel):
    review_index: int = Field(description="1-based index of the review this theme comes from")
    theme: str = Field(description="2-4 word theme, e.g. 'fast viewings'")
    sentiment: Literal["positive", "negative", "neutral"]
    paraphrase: str = Field(description="At most 12 words, in your own words, no names, no quotes")
    addressable_by: Literal["website", "content", "none"] = Field(
        description="For negative themes: could a website or social content fix it? 'none' otherwise")


class VariantOut(BaseModel):
    message: str
    used_fact_ids: list[str]


class GeminiOutput(BaseModel):
    review_facts: list[ReviewFactOut]
    variants: list[VariantOut]
    poster_lines: list[str]


class LlmUnavailable(Exception):
    """Daily quota reached, budget spent or the API is down: use the fallback."""


class RateLimited(Exception):
    """Per-minute limit: wait and retry."""


class GeminiClient:
    def __init__(self, api_key: str, model: str, cfg):
        from google import genai
        from google.genai import types

        self._types = types
        g = cfg.budget.gemini
        self.model = model
        self.temperature = g.temperature
        self.min_interval = 60.0 / g.rpm
        self.client = genai.Client(api_key=api_key,
                                   http_options=types.HttpOptions(timeout=int(g.timeout_s * 1000)))
        self._last = 0.0
        self._lock = threading.Lock()
        self.daily_quota_hit = False

    def _throttle(self) -> None:
        with self._lock:
            wait = self._last + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()

    def generate_json(self, system: str, prompt: str, schema: type, *, context: dict) -> dict:
        from google.genai import errors

        if self.daily_quota_hit:
            raise LlmUnavailable("Gemini daily quota already reached tonight")
        self._throttle()
        cfg = self._types.GenerateContentConfig(system_instruction=system, temperature=self.temperature,
                                                response_mime_type="application/json", response_schema=schema)
        try:
            resp = self.client.models.generate_content(model=self.model, contents=prompt, config=cfg)
        except errors.ClientError as e:
            text = str(e)
            if getattr(e, "code", None) == 429:
                if "perday" in text.lower().replace(" ", "") or "per_day" in text.lower() or "daily" in text.lower():
                    self.daily_quota_hit = True
                    log.warning("Gemini daily quota reached: remaining leads use the fallback")
                    raise LlmUnavailable(text[:200]) from e
                raise RateLimited(text[:200]) from e
            if getattr(e, "code", None) in (401, 403, 404):
                # bad key / model name: no point retrying tonight
                self.daily_quota_hit = True
                log.error("Gemini rejected the request (%s). Check GEMINI_API_KEY / GEMINI_MODEL.", getattr(e, "code", ""))
                raise LlmUnavailable(text[:200]) from e
            raise
        except errors.ServerError as e:
            raise RateLimited(str(e)[:200]) from e
        if getattr(resp, "parsed", None) is not None:
            parsed = resp.parsed
            return parsed.model_dump() if hasattr(parsed, "model_dump") else parsed
        return json.loads(resp.text)
