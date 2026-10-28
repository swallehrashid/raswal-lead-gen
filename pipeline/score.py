"""The single ads score (out of 100) with a breakdown, plus the message angle (ads pivot)."""

from __future__ import annotations

from datetime import datetime, timedelta

from pipeline.models import Candidate, Score


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


def ability_points(c: Candidate, cfg) -> tuple[float, dict[str, float]]:
    """Scale + area + branches (+ subcategory bonus), capped. Used for the pre-score only."""
    ab = cfg.scoring.ability
    sub = cfg.subcategories[c.subcategory]
    parts = {"reviews": review_points(c.review_count, cfg)}
    if set(c.area_flags) & {"premium", "growth"}:
        parts["area"] = ab.premium_or_growth_area
    if c.branch_count >= ab.multi_branch_min or c.manages_listings >= ab.manages_listings_min:
        parts["branches_or_listings"] = ab.multi_branch_or_listings
    if sub.ability_bonus:
        parts["subcategory"] = sub.ability_bonus
    return min(sum(parts.values()), ab.cap), parts


def pre_score(c: Candidate, cfg, now: datetime) -> float:
    """Orders gate-passers for enrichment: reviews, recency, rating (no ads/social signals yet)."""
    return ability_points(c, cfg)[0] + activity_points(c, cfg, now) + reputation_points(c.rating, cfg)


def derive_social_state(c: Candidate, now: datetime) -> str:
    """active: ads running or an Instagram post in the last 30 days; stale: a social link but no
    sign of recent activity; none: no social links at all."""
    if c.social_state:
        return c.social_state
    if c.ads_status == "active":
        return "active"
    last = (c.social or {}).get("ig_last_post_at")
    if last:
        try:
            if datetime.fromisoformat(str(last)) >= now - timedelta(days=30):
                return "active"
        except ValueError:
            pass
    links = (c.audit.social_links if c.audit else None) or {}
    if links or any((c.social or {}).get(k) for k in ("facebook", "instagram", "tiktok")):
        return "stale"
    return "none"


def derive_angle(c: Candidate, cfg) -> str:
    """B already advertising; C no or broken website (and not advertising); A everything else."""
    if c.ads_status == "active":
        return "B"
    status = c.audit.site_status if c.audit else "none"
    return "C" if status in cfg.scoring.ads.angle_c_statuses else "A"


def ads_score(c: Candidate, cfg, now: datetime) -> Score:
    a = cfg.scoring.ads
    status = c.audit.site_status if c.audit else "none"
    ab = cfg.scoring.ability
    sub = cfg.subcategories[c.subcategory]
    br: dict[str, float] = {
        "reviews": review_points(c.review_count, cfg),
        "activity": activity_points(c, cfg, now),
        "reputation": reputation_points(c.rating, cfg),
    }
    if status in a.website_statuses:
        br["website"] = a.website_points
    if c.ads_status == "active":
        br["ads_active"] = a.ads_active_points + (
            a.ads_long_running_bonus if (c.ads_longest_days or 0) >= a.ads_long_running_days else 0.0)
    social = a.social_points.get(derive_social_state(c, now), 0.0)
    if social:
        br["social"] = social
    if c.branch_count >= ab.multi_branch_min or c.manages_listings >= ab.manages_listings_min:
        br["branches_or_listings"] = ab.multi_branch_or_listings
    if set(c.area_flags) & {"premium", "growth"}:
        br["area"] = ab.premium_or_growth_area
    if sub.ability_bonus:
        br["subcategory"] = float(sub.ability_bonus)
    if c.scam_flag == "soft":
        br["scam_soft"] = a.scam_soft_penalty
    total = round(max(0.0, min(100.0, sum(br.values()))), 1)
    return Score("ads", total, br, True, a.min_score)


def score_candidate(c: Candidate, cfg, now: datetime) -> None:
    c.social_state = derive_social_state(c, now)
    c.angle = derive_angle(c, cfg)
    c.scores = {"ads": ads_score(c, cfg, now)}
    c.track = "ads"
