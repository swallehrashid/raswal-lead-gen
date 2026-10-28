"""Ad-library and Instagram signals via Apify (ads pivot P2.4). Optional: without APIFY_TOKEN every lead stays 'unknown'.

  python -m pipeline adlib-sync        # weekly: scrape Kenyan active ads into ad_library_ads
  nightly                              # matches candidates to that index (phone first, then name) and, if a token is set,
                                       # checks Instagram activity for the best candidates

Scraping Meta's public Ad Library is against its terms; this is research use only (no login, weekly at most, capped)."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from rapidfuzz import fuzz

from pipeline.models import Candidate
from pipeline.utils.text import name_norm

log = logging.getLogger(__name__)

AD_LIBRARY = "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=KE&q={q}&search_type=keyword_unordered"


# ---------------------------------------------------------------- parsing
def wa_phone_from_link(url: str | None) -> str | None:
    """+254… from a wa.me/<digits> or api.whatsapp.com/send?phone=<digits> link (Kenya only)."""
    if not url:
        return None
    u = urlparse(unquote(url))
    digits = None
    if u.netloc.endswith("wa.me"):
        digits = re.sub(r"\D", "", u.path)
    elif "whatsapp.com" in u.netloc:
        digits = re.sub(r"\D", "", (parse_qs(u.query).get("phone") or [""])[0])
    if not digits:
        return None
    if digits.startswith("0") and len(digits) == 10:
        digits = "254" + digits[1:]
    return f"+{digits}" if digits.startswith("254") and len(digits) == 12 else None


def _first(d: dict, *keys, default=None):
    for k in keys:
        cur: Any = d
        for part in k.split("."):
            cur = cur.get(part) if isinstance(cur, dict) else None
            if cur is None:
                break
        if cur not in (None, ""):
            return cur
    return default


def _date(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, int | float):
        return datetime.fromtimestamp(v if v < 1e11 else v / 1000, timezone.utc).date().isoformat()
    return str(v)[:10]


def parse_ad(item: dict, query: str = "") -> dict | None:
    """One Apify facebook-ads-scraper item → an ad_library_ads row (tolerant of field-name variants)."""
    ad_id = _first(item, "adArchiveID", "ad_archive_id", "adArchiveId", "id")
    page = _first(item, "pageName", "page_name", "snapshot.page_name")
    if not ad_id or not page:
        return None
    link = _first(item, "snapshot.link_url", "link_url", "linkUrl", "snapshot.cta_link")
    page_id = str(_first(item, "pageID", "page_id", "pageId", default="")) or None
    return {"ad_archive_id": str(ad_id), "page_id": page_id, "page_name": page,
            "page_name_norm": name_norm(page), "wa_phone_e164": wa_phone_from_link(link), "link_url": link,
            "cta_type": _first(item, "snapshot.cta_type", "cta_type", "ctaType"),
            "body": str(_first(item, "snapshot.body.text", "snapshot.body", "body", default="") or "")[:500],
            "start_date": _date(_first(item, "startDate", "start_date", "startDateFormatted")), "query": query}


# ---------------------------------------------------------------- Apify clients
class ApifyClient:
    def __init__(self, token: str, timeout: int = 300, max_usd_per_run: float | None = None):
        self.token, self.timeout, self.max_usd = token, timeout, max_usd_per_run

    def run(self, actor: str, payload: dict) -> list[dict]:
        url = f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
        params = {"token": self.token}
        if self.max_usd:                                   # hard cap per run: the free plan is $5/month
            params["maxTotalChargeUsd"] = f"{self.max_usd:.2f}"
        r = httpx.post(url, params=params, json=payload, timeout=self.timeout)
        if r.status_code >= 400:
            raise RuntimeError(f"Apify {actor} HTTP {r.status_code}: {r.text[:200]}")
        return r.json()


# ---------------------------------------------------------------- weekly sync
def sync(cfg, env, store, *, client=None, today: date | None = None) -> dict:
    ab = cfg.budget.apify
    if client is None:
        if not env.apify_token:
            log.info("adlib-sync skipped: no APIFY_TOKEN")
            return {"status": "skipped", "reason": "no APIFY_TOKEN"}
        client = ApifyClient(env.apify_token, ab.timeout_s, ab.max_usd_per_month / 4.3 / max(1, len(ab.queries)))
    per_query = max(10, ab.max_ads_per_week // max(1, len(ab.queries)))
    rows: dict[str, dict] = {}
    for q in ab.queries:
        try:
            url = AD_LIBRARY.format(q=q.replace(" ", "%20"))
            items = client.run(ab.actor_ads, {"startUrls": [{"url": url}], "resultsLimit": per_query})
        except Exception as e:  # noqa: BLE001 - one bad query must not lose the rest
            log.error("adlib query %r failed: %s", q, e)
            continue
        for it in items:
            if (row := parse_ad(it, q)):
                rows[row["ad_archive_id"]] = row
    store.upsert_ads(list(rows.values()))
    log.info("adlib-sync: %d ads from %d queries", len(rows), len(ab.queries))
    return {"status": "ok", "ads": len(rows)}


# ---------------------------------------------------------------- matching (nightly)
def match(c: Candidate, ads: list[dict], cfg, today: date) -> list[dict]:
    """Ads that belong to this business: same WhatsApp number first, else the page name is a near-duplicate."""
    out = []
    nn = name_norm(c.name)
    for ad in ads:
        if c.phone_e164 and ad.get("wa_phone_e164") == c.phone_e164:
            out.append(ad)
        elif ad.get("page_name_norm") and fuzz.ratio(nn, ad["page_name_norm"]) >= cfg.scoring.dedupe.near_duplicate_ratio:
            out.append(ad)
    return out


def apply_ads_index(cands: list[Candidate], store, cfg, today: date) -> dict:
    """Set ads_* on candidates from the stored index. 'none' only when the index is fresh; otherwise 'unknown'."""
    ads = store.load_ad_library(cfg.budget.apify.fresh_days)
    if not ads:
        for c in cands:
            c.ads_status = c.ads_status or "unknown"
        return {"index": 0}
    for c in cands:
        hits = match(c, ads, cfg, today)
        if not hits:
            c.ads_status, c.ads_active_count, c.ads_longest_days, c.ads_sample = "none", 0, 0, []
            continue
        starts = [date.fromisoformat(a["start_date"]) for a in hits if a.get("start_date")]
        c.ads_status, c.ads_active_count = "active", len(hits)
        c.ads_longest_days = (today - min(starts)).days if starts else 0
        oldest = sorted(hits, key=lambda x: x.get("start_date") or "")[:3]
        c.ads_sample = [{"ad_archive_id": a["ad_archive_id"], "start_date": a.get("start_date"),
                         "body": (a.get("body") or "")[:200], "cta_type": a.get("cta_type"), "link": a.get("link_url")}
                        for a in oldest]
    return {"index": len(ads), "matched": sum(1 for c in cands if c.ads_status == "active")}


# ---------------------------------------------------------------- Instagram activity (nightly, best candidates only)
def parse_instagram(item: dict, today: date) -> dict:
    posts = item.get("latestPosts") or []
    stamps = [_date(_first(p, "timestamp", "takenAtTimestamp")) for p in posts]
    stamps = sorted(s for s in stamps if s)
    recent = [s for s in stamps if date.fromisoformat(s) >= today - timedelta(days=30)]
    return {"ig_last_post_at": (stamps[-1] + "T00:00:00+00:00") if stamps else None,
            "ig_followers": item.get("followersCount"), "ig_posts_30d": len(recent)}


def apply_instagram(cands: list[Candidate], cfg, env, today: date, *, client=None, limit: int | None = None) -> int:
    """Fill c.social for the candidates that have an Instagram link. No token → no-op."""
    if client is None:
        if not env.apify_token:
            return 0
        client = ApifyClient(env.apify_token, cfg.budget.apify.timeout_s, .05)
    ab = cfg.budget.apify
    cap = limit if limit is not None else ab.instagram_per_night
    todo = [c for c in cands if c.audit and (c.audit.social_links or {}).get("instagram")][:cap]
    n = 0
    for c in todo:
        handle = urlparse(c.audit.social_links["instagram"]).path.strip("/").split("/")[0]
        if not handle:
            continue
        try:
            items = client.run(ab.actor_instagram, {"usernames": [handle]})
        except Exception as e:  # noqa: BLE001
            log.warning("instagram check failed for %s: %s", handle, e)
            continue
        if items:
            c.social = {**(c.social or {}), "instagram": c.audit.social_links["instagram"], **parse_instagram(items[0], today)}
            n += 1
    return n
