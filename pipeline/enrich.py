"""Enrichment: pre-score gate-passers, audit the top N sites, run PSI (brief §9)."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from pipeline.audit_site import audit_website, finalize_status, needs_psi
from pipeline.models import Audit, Candidate
from pipeline.psi import run_psi_batch
from pipeline.score import pre_score

log = logging.getLogger(__name__)


def enrich(passed: list[Candidate], cfg, fetcher, psi_client, budget, store, now: datetime,
           limit: int | None = None, sleep=None) -> list[Candidate]:
    for c in passed:
        c.pre_score = pre_score(c, cfg, now)
    n = limit if limit is not None else cfg.scoring.enrich_limit
    top = sorted(passed, key=lambda c: -c.pre_score)[:n]
    log.info("enrich: auditing %d of %d gate-passers (enrich_limit %d)", len(top), len(passed), n)

    def audit(c: Candidate) -> None:
        try:
            c.audit = audit_website(c.website_url, fetcher, cfg, now)
        except Exception as e:  # noqa: BLE001
            log.warning("audit failed for %s (%s): %s", c.name, c.website_url, e)
            c.audit = Audit("dead", website_url=c.website_url, dead_marker=cfg.audit.error_markers["other"])

    with ThreadPoolExecutor(max_workers=cfg.budget.site_fetch.concurrency) as pool:
        list(pool.map(audit, top))
    kw = {"sleep": sleep} if sleep else {}
    psi_cands = [c for c in top if needs_psi(c.audit)]
    run_psi_batch(psi_cands, psi_client, budget, store, cfg, **kw)
    for c in top:
        finalize_status(c.audit, cfg, now)
    counts: dict[str, int] = {}
    for c in top:
        counts[c.audit.site_status] = counts.get(c.audit.site_status, 0) + 1
    log.info("site_status: %s", counts)
    return top
