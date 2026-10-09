"""Website- and content-track scores with breakdowns (brief §10.2, §10.3)."""

from __future__ import annotations

from datetime import datetime

from pipeline.models import Candidate, Score

WEB_STATUSES = {"none", "social_as_site", "dead", "insecure", "free_builder", "weak"}


def review_points(n: int, cfg) -> float:
    for b in cfg.scoring.review_bands:
        if n >= (b.min or 0) and (b.max is None or n <= b.max):
            return b.points
    return 0.0


def activity_points(c: Candidate, cfg, now: datetime) -> float:
    newest = c.newest_review_at
    if newest is None:
        return 0.0
    age = (now - newest).days
    for b in cfg.scoring.activity_bands:
        if age <= b.max_days:
            return b.points
    return 0.0


def reputation_points(rating: float | None, cfg) -> float:
    if rating is None:
        return 0.0
    for b in cfg.scoring.reputation_bands:
        if rating >= b.min:
            return b.points
    return 0.0


def _bands(n_strong: int, bands) -> float:
    for b in bands:
        if n_strong >= b.min_strong:
            return b.points
    return 0.0


def ability_points(c: Candidate, cfg, *, content: bool = False) -> tuple[float, dict[str, float]]:
    ab = cfg.scoring.ability
    sub = cfg.subcategories[c.subcategory]
    parts = {"reviews": review_points(c.review_count, cfg)}
    if set(c.area_flags) & {"premium", "growth"}:
        parts["area"] = ab.premium_or_growth_area
    if c.branch_count >= ab.multi_branch_min or c.manages_listings >= ab.manages_listings_min:
        parts["branches_or_listings"] = ab.multi_branch_or_listings
    if sub.ability_bonus:
        parts["subcategory"] = sub.ability_bonus
    total = min(sum(parts.values()), ab.cap)
    if content:
        total = min(total * ab.content_multiplier, ab.content_cap)
    return total, parts


def pre_score(c: Candidate, cfg, now: datetime) -> float:
    """Orders gate-passers for enrichment: reviews, recency, rating (no pain/hook yet)."""
    return ability_points(c, cfg)[0] + activity_points(c, cfg, now) + reputation_points(c.rating, cfg)


def strong_count(c: Candidate, track: str) -> int:
    return sum(1 for f in c.facts_for(track) if f.strength == "strong")


def web_score(c: Candidate, cfg, now: datetime) -> Score:
    w = cfg.scoring.web
    status = c.audit.site_status if c.audit else "none"
    eligible = status in WEB_STATUSES
    ability, _ = ability_points(c, cfg)
    br = {
        "pain": w.pain.get(status, 0.0) if eligible else 0.0,
        "ability": ability,
        "activity": activity_points(c, cfg, now),
        "reputation": reputation_points(c.rating, cfg),
        "hook": _bands(strong_count(c, "web"), w.hook_points),
    }
    return Score("web", round(sum(br.values()), 1), br, eligible, w.min_score)


def content_eligible(c: Candidate) -> bool:
    a = c.audit
    if not a:
        return False
    return a.site_status == "good" or (a.site_status == "weak" and bool(a.https_ok) and bool(a.meta_viewport))


def content_gap(c: Candidate, cfg, now: datetime) -> float:
    g = cfg.scoring.content.gap
    a = c.audit
    links = a.social_links or {}
    pts = 0.0
    if not links:
        pts += g.no_social_links
    elif not ({"instagram", "tiktok"} & set(links)):
        pts += g.no_instagram_or_tiktok
    if not a.has_video:
        pts += g.no_video_bonus
    if a.blog_last_date and (now.date() - a.blog_last_date).days > g.stale_blog_months * 30:
        pts += g.stale_blog_bonus
    return min(pts, g.cap)


def content_score(c: Candidate, cfg, now: datetime) -> Score:
    cs = cfg.scoring.content
    eligible = content_eligible(c)
    ability, _ = ability_points(c, cfg, content=True)
    br = {
        "gap": content_gap(c, cfg, now) if eligible else 0.0,
        "ability": round(ability, 1),
        "activity": activity_points(c, cfg, now),
        "reputation": reputation_points(c.rating, cfg),
        "hook": _bands(strong_count(c, "content"), cs.hook_points),
    }
    return Score("content", round(sum(br.values()), 1), br, eligible, cs.min_score)


def score_candidate(c: Candidate, cfg, now: datetime) -> None:
    """Score both tracks and route to the eligible track with the larger margin over its threshold."""
    c.scores = {"web": web_score(c, cfg, now), "content": content_score(c, cfg, now)}
    eligible = [s for s in c.scores.values() if s.eligible]
    if not eligible:
        c.track = None
        return
    best = max(eligible, key=lambda s: (s.margin, s.track == "web"))
    c.track = best.track
