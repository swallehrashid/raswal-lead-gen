"""Builders for candidates with audits, used across tests."""

from datetime import datetime, timedelta, timezone

from pipeline.models import Audit, Candidate, Review
from pipeline.utils.text import display_name, name_key, name_norm

NOW = datetime(2026, 10, 11, 18, 30, tzinfo=timezone.utc)
_n = [0]


def make(name="Kilima Homes", *, sub="property_agency", reviews=60, rating=4.6, newest_days=10, area="Kilimani",
         flags=(), status="dead", phone=None, website="http://kilimahomes.co.ke/", review_texts=None, **audit_kw):
    _n[0] += 1
    norm = name_norm(name)
    texts = review_texts or ["They arranged a viewing the same afternoon I called.", "Smooth process, deposit refunded."]
    revs = [Review(i + 1, 5, t, f"Reviewer {i}", NOW - timedelta(days=newest_days + i * 20)) for i, t in enumerate(texts)]
    c = Candidate(place_id=f"p{_n[0]}", name=name, name_norm=norm, subcategory=sub, types=["real_estate_agency"],
                  primary_type="real_estate_agency", address="", lat=-1.29, lng=36.78, maps_url="https://maps.google.com/?cid=1",
                  business_status="OPERATIONAL", phone_raw="", phone_e164=phone or f"+2547220{_n[0]:05d}",
                  phone_type="MOBILE", website_url=None if status == "none" else website, rating=rating,
                  review_count=reviews, reviews=revs, area=area, area_flags=list(flags), name_key=name_key(norm),
                  display_name=display_name(name))
    defaults = dict(website_url=c.website_url, final_url=c.website_url, https_ok=True, meta_viewport=True,
                    has_whatsapp_link=True, has_tel_link=True, word_count=500, copyright_year=NOW.year,
                    social_links={}, has_video=False, psi_perf=80.0, psi_lcp_s=2.0)
    if status == "dead":
        defaults.update(dead_marker="an 'account suspended' page", status_code=200)
    if status == "social_as_site":
        defaults.update(social_platform="Facebook")
    defaults.update(audit_kw)
    c.audit = Audit(status, **defaults)
    return c
