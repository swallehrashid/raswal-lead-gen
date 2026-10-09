"""Dry-run CSV: every candidate with gate codes, score breakdown, facts and drafts (brief §16.3)."""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from pipeline.models import Candidate

COLUMNS = ["place_id", "name", "display_name", "area", "phone_e164", "phone_type", "website_url", "rating",
           "review_count", "newest_review_at", "branch_count", "manages_listings", "merged_place_ids", "gate_codes",
           "pre_score", "site_status", "weak_signals", "psi_perf", "psi_lcp_s", "web_score", "content_score", "track",
           "score", "breakdown", "selection", "rank", "facts", "variant_a", "variant_b", "variant_source",
           "teaser_file"]


def candidate_row(c: Candidate, teaser_file: str = "") -> dict:
    a = c.audit
    s = c.score
    web, content = c.scores.get("web"), c.scores.get("content")
    return {
        "place_id": c.place_id, "name": c.name, "display_name": c.display_name, "area": c.area,
        "phone_e164": c.phone_e164 or "", "phone_type": c.phone_type or "", "website_url": c.website_url or "",
        "rating": c.rating if c.rating is not None else "", "review_count": c.review_count,
        "newest_review_at": c.newest_review_at.date().isoformat() if c.newest_review_at else "",
        "branch_count": c.branch_count, "manages_listings": c.manages_listings,
        "merged_place_ids": " ".join(c.merged_place_ids), "gate_codes": " ".join(c.gate_codes),
        "pre_score": round(c.pre_score, 1), "site_status": a.site_status if a else "",
        "weak_signals": " ".join(a.weak_signals) if a else "",
        "psi_perf": a.psi_perf if a and a.psi_perf is not None else "",
        "psi_lcp_s": a.psi_lcp_s if a and a.psi_lcp_s is not None else "",
        "web_score": round(web.total, 1) if web and web.eligible else "",
        "content_score": round(content.total, 1) if content and content.eligible else "",
        "track": c.track or "", "score": round(s.total, 1) if s else "",
        "breakdown": json.dumps(s.breakdown) if s else "",
        "selection": c.selection or "", "rank": c.rank or "",
        "facts": " | ".join(f"{f.id} {f.code} ({f.strength}): {f.text}" for f in c.facts),
        "variant_a": c.variants[0].message if len(c.variants) > 0 else "",
        "variant_b": c.variants[1].message if len(c.variants) > 1 else "",
        "variant_source": c.variant_source or "", "teaser_file": teaser_file,
    }


def sort_key(c: Candidate):
    sel = {"finalist": 0, "reserve": 1}.get(c.selection or "", 2)
    return (sel, c.track or "z", c.rank or 9999, bool(c.gate_codes), -(c.score.total if c.score else c.pre_score))


def write_csv(cands: list[Candidate], out_dir: Path, list_date: date, subcategory: str,
              teaser_files: dict[str, str] | None = None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{list_date.isoformat()}-{subcategory}.csv"
    teaser_files = teaser_files or {}
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        for c in sorted(cands, key=sort_key):
            w.writerow(candidate_row(c, teaser_files.get(c.place_id, "")))
    return path
