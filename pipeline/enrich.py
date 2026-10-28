"""Enrichment: pre-score gate-passers, audit the top N sites, run PSI (brief §9)."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from pipeline.audit_site import audit_website, finalize_status, needs_psi
from pipeline.models import Audit, Candidate
from pipeline.normalise import parse_reviews
from pipeline.psi import run_psi_batch
from pipeline.scam import scam_check
from pipeline.score import pre_score

log = logging.getLogger(__name__)


def _fetch_reviews(top: list[Candidate], places, budget) -> None:
    """Google Places searchText returns no reviews; fetch them via Place Details for the
    candidates we're about to score. Offline fixtures already carry reviews, so skip those.
    Capped by the 'places_details' budget."""
    if places is None or not hasattr(places, "place_details"):
        return
    fetched = 0
    for c in top:
        if c.reviews:
            continue
        if budget.remaining("places_details") <= 0:
            log.info("reviews: places_details budget exhausted after %d", fetched)
            break
        try:
            d = places.place_details(c.place_id)
            budget.spend("places_details")
            c.reviews = parse_reviews(d.get("reviews"))
            fetched += 1
        except Exception as e:  # noqa: BLE001
            log.warning("reviews fetch failed for %s: %s", c.name, e)
    if fetched:
        log.info("reviews: fetched Place Details for %d candidates", fetched)


def enrich(passed: list[Candidate], cfg, fetcher, psi_client, budget, store, now: datetime,
           limit: int | None = None, sleep=None, places=None) -> list[Candidate]:
    for c in passed:
        c.pre_score = pre_score(c, cfg, now)
    n = limit if limit is not None else cfg.scoring.enrich_limit
    top = sorted(passed, key=lambda c: -c.pre_score)[:n]
    log.info("enrich: auditing %d of %d gate-passers (enrich_limit %d)", len(top), len(passed), n)
    _fetch_reviews(top, places, budget)
    for c in top:
        scam_check(c, cfg)

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
