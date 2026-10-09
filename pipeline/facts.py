"""Deterministic fact extraction (brief §11). Messages and teasers may only use facts.

Every fact has evidence that the dashboard shows on tap, so Swalleh can check it in seconds.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from pipeline.models import Candidate, Fact
from pipeline.utils.urls import host

WEB_STATUSES_FETCHED = {"insecure", "free_builder", "weak", "good"}


def _fmt_rating(r: float) -> str:
    return f"{r:.1f}"


def _fmt_lcp(s: float) -> str:
    return str(int(round(s)))


def _site_domain(c: Candidate) -> str:
    return host(c.website_url) or host(c.audit.final_url if c.audit else "")


def build_facts(c: Candidate, cfg, now: datetime) -> list[Fact]:
    """All deterministic facts for a candidate (both tracks), strongest first, ids F1.. ."""
    fr = cfg.scoring.facts
    texts = cfg.messaging.fact_texts
    a = c.audit
    raw: list[tuple[str, str, dict, str, str]] = []   # (code, strength, evidence, track, source)

    def add(code, strength, track, source, **ev):
        raw.append((code, strength, ev, track, source))

    status = a.site_status if a else None
    dom = _site_domain(c)
    if status == "dead":
        add("SITE_DEAD", "strong", "web", "audit", domain=dom, marker=a.dead_marker, url=c.website_url,
            status=a.status_code, final_url=a.final_url)
    elif status == "social_as_site":
        add("SOCIAL_AS_SITE", "strong", "web", "places", platform=a.social_platform, url=c.website_url)
    elif status == "none":
        strength = "strong" if c.review_count >= fr.no_site_strong_reviews else "medium"
        add("NO_SITE_HIGH_REVIEWS", strength, "web", "places", n=c.review_count)
    if status == "insecure":
        add("SITE_INSECURE", "strong", "web", "audit", domain=dom, url=a.final_url, cert_error=a.cert_error)
    if status == "free_builder":
        add("FREE_BUILDER", "strong", "web", "audit", builder=a.free_builder, host=a.free_host, url=a.final_url)
    if status in WEB_STATUSES_FETCHED:
        if a.psi_lcp_s is not None and a.psi_lcp_s >= fr.slow_mobile_min_lcp_s and status != "good":
            strength = "strong" if a.psi_lcp_s >= fr.slow_mobile_strong_lcp_s else "medium"
            add("SLOW_MOBILE", strength, "web", "psi", domain=dom, lcp=_fmt_lcp(a.psi_lcp_s), lcp_s=a.psi_lcp_s,
                performance=a.psi_perf)
        if a.meta_viewport is False:
            add("NO_VIEWPORT", "medium", "web", "audit", domain=dom, url=a.final_url)
        if a.copyright_year and a.copyright_year <= now.year - cfg.scoring.weak_site.copyright_age_years:
            add("OLD_COPYRIGHT", "medium", "web", "audit", year=a.copyright_year, url=a.final_url)
        if a.has_whatsapp_link is False:
            add("NO_WHATSAPP_BUTTON", "medium", "web", "audit", domain=dom, url=a.final_url)
    if status in ("good", "weak"):
        if status == "good" and (a.psi_perf or 0) >= fr.good_site_min_perf and \
                (a.copyright_year is None or a.copyright_year >= now.year - 1):
            add("GOOD_SITE", "medium", "content", "psi", performance=a.psi_perf, lcp_s=a.psi_lcp_s, url=a.final_url)
        if not a.social_links:
            add("NO_SOCIAL_LINKS", "strong", "content", "audit", url=a.final_url)
        if a.has_video is False:
            add("NO_VIDEO", "medium", "content", "audit", url=a.final_url)
        if a.blog_last_date and (now.date() - a.blog_last_date).days > cfg.scoring.content.gap.stale_blog_months * 30:
            add("STALE_BLOG", "medium", "content", "audit", month_year=a.blog_last_date.strftime("%B %Y"),
                date=a.blog_last_date.isoformat())
    recent = [r for r in c.reviews if r.publish_time and r.publish_time >= now - timedelta(days=fr.recent_reviews_days)]
    if len(recent) >= fr.recent_reviews_min:
        add("RECENT_REVIEWS", "medium", "any", "places", k=len(recent), days=fr.recent_reviews_days,
            returned_reviews=len(c.reviews))
    if c.rating is not None and c.rating >= fr.high_rating_min and c.review_count >= fr.high_rating_min_reviews:
        add("HIGH_RATING", "medium", "any", "places", rating=_fmt_rating(c.rating), n=c.review_count)
    sub = cfg.subcategories[c.subcategory]
    if sub.manages_listings_is_positive and c.manages_listings >= cfg.scoring.ability.manages_listings_min:
        add("MANAGES_LISTINGS", "medium", "any", "places", n=c.manages_listings, place_ids=c.merged_place_ids)
    if c.branch_count >= cfg.scoring.ability.multi_branch_min:
        add("BRANCHES", "medium", "any", "places", n=c.branch_count)

    prio = {code: i for i, code in enumerate(cfg.messaging.fact_priority)}
    raw.sort(key=lambda t: (t[1] != "strong", prio.get(t[0], 99)))
    facts = []
    for i, (code, strength, ev, track, source) in enumerate(raw, start=1):
        text = texts[code].format(**{k: v for k, v in ev.items() if v is not None})
        facts.append(Fact(id=f"F{i}", code=code, strength=strength, text=text, evidence=ev, track=track, source=source))
    return facts


def sort_facts(facts: list[Fact], cfg) -> list[Fact]:
    prio = {code: i for i, code in enumerate(cfg.messaging.fact_priority)}
    return sorted(facts, key=lambda f: (f.strength != "strong", prio.get(f.code, 99)))


def top_fact(c: Candidate, cfg=None) -> Fact | None:
    facts = c.facts_for(c.track) if c.track else c.facts
    if not facts:
        return None
    if cfg is not None:
        facts = sort_facts(facts, cfg)
    return facts[0]


def top_fact_code(c: Candidate, cfg=None) -> str | None:
    f = top_fact(c, cfg)
    return f.code if f else None
