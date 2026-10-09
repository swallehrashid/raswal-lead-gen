"""PageSpeed Insights v5 (mobile, performance): score, LCP and the final screenshot (brief §9.3)."""

from __future__ import annotations

import base64
import io
import logging
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
from PIL import Image

from pipeline.budget import Budget, BudgetExhausted
from pipeline.models import Candidate
from pipeline.utils.urls import registered_domain

log = logging.getLogger(__name__)

PSI_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


class PsiError(Exception):
    pass


class LivePsiClient:
    def __init__(self, api_key: str, cfg):
        self._key = api_key
        self._http = httpx.Client(timeout=cfg.budget.psi.timeout_s)

    def run(self, url: str) -> dict:
        r = self._http.get(PSI_URL, params={"url": url, "strategy": "mobile", "category": "performance",
                                            "key": self._key})
        if r.status_code >= 400:
            # the error body is safe to log; the request URL (with the key) is not
            raise PsiError(f"PSI HTTP {r.status_code}: {r.text[:300]}")
        return r.json()


def parse_psi(data: dict) -> tuple[float | None, float | None, bytes | None]:
    """→ (performance 0–100, LCP seconds, final screenshot as JPEG bytes)."""
    lh = data.get("lighthouseResult") or {}
    score = ((lh.get("categories") or {}).get("performance") or {}).get("score")
    perf = round(score * 100, 1) if isinstance(score, int | float) else None
    audits = lh.get("audits") or {}
    lcp_ms = (audits.get("largest-contentful-paint") or {}).get("numericValue")
    lcp = round(lcp_ms / 1000, 2) if isinstance(lcp_ms, int | float) else None
    shot = ((audits.get("final-screenshot") or {}).get("details") or {}).get("data")
    return perf, lcp, decode_screenshot(shot) if shot else None


def decode_screenshot(data_url: str) -> bytes | None:
    try:
        b64 = data_url.split(",", 1)[1] if "," in data_url else data_url
        img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=80)
        return buf.getvalue()
    except Exception:  # noqa: BLE001
        return None


def run_psi_batch(cands: list[Candidate], client, budget: Budget, store, cfg, *, sleep=time.sleep) -> int:
    """Run PSI for candidates whose audit needs it. Cached per registered domain for cache_days."""
    pc = cfg.budget.psi
    todo: dict[str, list[Candidate]] = {}
    for c in cands:
        url = c.audit.final_url or c.audit.website_url
        dom = registered_domain(url)
        cached = store.get_psi_cache(dom, pc.cache_days) if dom else None
        if cached:
            c.audit.psi_perf = float(cached["perf"]) if cached.get("perf") is not None else None
            c.audit.psi_lcp_s = float(cached["lcp_s"]) if cached.get("lcp_s") is not None else None
            c.audit.current_screenshot_path = cached.get("screenshot_path")
            continue
        todo.setdefault(dom or url, []).append(c)

    def one(key: str) -> None:
        group = todo[key]
        url = group[0].audit.final_url or group[0].audit.website_url
        for attempt in range(pc.attempts):
            try:
                budget.spend("psi")
            except BudgetExhausted:
                return
            try:
                perf, lcp, shot = parse_psi(client.run(url))
                for c in group:
                    c.audit.psi_perf, c.audit.psi_lcp_s, c.audit.psi_screenshot = perf, lcp, shot
                store.put_psi_cache(key, perf, lcp, None)
                return
            except Exception as e:  # noqa: BLE001
                log.warning("PSI attempt %d failed for %s: %s", attempt + 1, registered_domain(url), e)
                sleep(2 ** (attempt + 1))

    with ThreadPoolExecutor(max_workers=pc.concurrency) as pool:
        list(pool.map(one, list(todo)))
    return len(todo)
