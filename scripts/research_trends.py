"""Trend research for the ad templates: what land/property advertisers in Kenya are running and posting right now.

Pulls (via Apify, each run hard-capped with maxTotalChargeUsd):
  - Facebook Ad Library, Kenya, active ads for land / rental keywords (long-running ads = ads that pay)
  - TikTok hashtag videos, Instagram hashtag posts/reels for the same niche
Raw JSON goes to docs/research/<date>/raw/; summarise.py-style digest to docs/research/<date>/digest.json.

Usage: .venv/bin/python scripts/research_trends.py [--budget 2.0]
Re-run every few weeks to re-tailor the templates (see docs/research/README.md).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import time
import urllib.parse
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.apify.com/v2"

ADLIB_QUERIES = {
    "land": ["plots for sale", "land for sale", "ready title deed"],
    "agency": ["apartment for rent Nairobi", "house for rent"],
}
TIKTOK_TAGS = ["landforsaleinkenya", "plotsforsaleinkenya", "kenyarealestate", "nairobiapartments",
               "househuntingkenya", "kitengela"]
IG_TAGS = ["landforsaleinkenya", "nairobirealestate", "apartmentsforrentnairobi", "househuntingnairobi"]


def adlib_url(q: str) -> str:
    qs = urllib.parse.urlencode({"active_status": "active", "ad_type": "all", "country": "KE", "q": q,
                                 "search_type": "keyword_unordered", "media_type": "all"})
    return f"https://www.facebook.com/ads/library/?{qs}"


def jobs(budget: float) -> list[dict]:
    """(name, actor, input, cap $). Caps sum to the budget."""
    share = {"fb_ads": .55, "tiktok": .25, "instagram": .20}
    return [
        {"name": "fb_ads", "actor": "apify~facebook-ads-scraper", "cap": budget * share["fb_ads"],
         "input": {"startUrls": [{"url": adlib_url(q)} for qs in ADLIB_QUERIES.values() for q in qs], "resultsLimit": 40}},
        {"name": "tiktok", "actor": "clockworks~tiktok-hashtag-scraper", "cap": budget * share["tiktok"],
         "input": {"hashtags": TIKTOK_TAGS, "resultsPerPage": 25}},
        {"name": "instagram", "actor": "apify~instagram-hashtag-scraper", "cap": budget * share["instagram"],
         "input": {"hashtags": IG_TAGS, "resultsLimit": 30, "resultsType": "posts"}},
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=2.0, help="total USD across all runs (hard cap)")
    args = ap.parse_args()
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
    token = os.environ["APIFY_TOKEN"]
    out = ROOT / "docs" / "research" / dt.date.today().isoformat()
    (out / "raw").mkdir(parents=True, exist_ok=True)
    c = httpx.Client(timeout=60)
    runs = {}
    for j in jobs(args.budget):
        params = {"token": token, "maxTotalChargeUsd": f"{j['cap']:.2f}"}
        r = c.post(f"{API}/acts/{j['actor']}/runs", params=params, json=j["input"])
        r.raise_for_status()
        runs[j["name"]] = r.json()["data"]
        print(f"started {j['name']} (cap ${j['cap']:.2f})", flush=True)
    pending = set(runs)
    t0 = time.time()
    while pending and time.time() - t0 < 1500:
        time.sleep(15)
        for name in list(pending):
            d = c.get(f"{API}/actor-runs/{runs[name]['id']}", params={"token": token}).json()["data"]
            if d["status"] not in ("READY", "RUNNING"):
                items = c.get(f"{API}/datasets/{d['defaultDatasetId']}/items", params={"token": token, "clean": "true"}).json()
                (out / "raw" / f"{name}.json").write_text(json.dumps(items, ensure_ascii=False, indent=1))
                print(f"{name}: {d['status']}, {len(items)} items, ${d.get('usageTotalUsd') or 0:.3f}", flush=True)
                pending.discard(name)
    for name in pending:
        print(f"{name}: still running after 25 min; aborting it", flush=True)
        c.post(f"{API}/actor-runs/{runs[name]['id']}/abort", params={"token": token})


if __name__ == "__main__":
    main()
