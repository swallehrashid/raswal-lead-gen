"""Runtime records passed between pipeline stages."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass
class Review:
    index: int                      # 1-based, as shown to the LLM
    rating: float | None
    text: str
    author: str
    publish_time: datetime | None


@dataclass
class Cell:
    subcategory: str
    query_template: str
    area: str
    tier: int
    id: str | None = None
    last_run: datetime | None = None
    pages_fetched: int = 0
    last_new_ratio: float | None = None
    exhausted_streak: int = 0
    exhausted: bool = False

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.subcategory, self.query_template, self.area)


@dataclass
class FetchResult:
    url: str
    final_url: str | None = None
    status_code: int | None = None
    redirect_chain: list[str] = field(default_factory=list)
    html: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    error: str | None = None        # dns | connect | timeout | ssl | too_many_redirects | other
    error_detail: str = ""

    @property
    def ok(self) -> bool:
        return self.error is None and self.status_code is not None and self.status_code < 400


@dataclass
class Audit:
    site_status: str
    website_url: str | None = None
    final_url: str | None = None
    status_code: int | None = None
    https_ok: bool | None = None
    cert_error: bool = False
    redirect_chain: list[str] = field(default_factory=list)
    html_bytes: int = 0
    title: str | None = None
    meta_viewport: bool | None = None
    copyright_year: int | None = None
    has_whatsapp_link: bool | None = None
    has_tel_link: bool | None = None
    platform: str | None = None
    social_links: dict[str, str] = field(default_factory=dict)
    has_video: bool | None = None
    blog_last_date: date | None = None
    word_count: int = 0
    dead_marker: str | None = None
    social_platform: str | None = None
    free_builder: str | None = None
    free_host: str | None = None
    weak_signals: list[str] = field(default_factory=list)
    psi_perf: float | None = None
    psi_lcp_s: float | None = None
    psi_screenshot: bytes | None = None
    current_screenshot_path: str | None = None
    logo_url: str | None = None
    logo_bytes: bytes | None = None
    colours: dict[str, str] = field(default_factory=dict)
    hero_image_url: str | None = None
    hero_bytes: bytes | None = None
    html: str = ""                  # kept in memory for brand discovery; never stored

    def to_row(self) -> dict[str, Any]:
        d = asdict(self)
        for k in ("psi_screenshot", "logo_bytes", "hero_bytes", "html"):
            d.pop(k)
        if d["blog_last_date"]:
            d["blog_last_date"] = d["blog_last_date"].isoformat()
        return d


@dataclass
class Fact:
    id: str
    code: str
    strength: str                   # strong | medium
    text: str
    evidence: dict[str, Any]
    track: str                      # web | content | any
    source: str                     # audit | places | psi | llm

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Score:
    track: str
    total: float
    breakdown: dict[str, float]
    eligible: bool
    threshold: float

    @property
    def margin(self) -> float:
        return self.total - self.threshold


@dataclass
class Variant:
    message: str
    used_fact_ids: list[str]
    source: str                     # llm | fallback
    swahili_touch: bool = False
    errors: list[str] = field(default_factory=list)


@dataclass
class Candidate:
    place_id: str
    name: str
    name_norm: str
    subcategory: str
    types: list[str]
    primary_type: str | None
    address: str | None
    lat: float | None
    lng: float | None
    maps_url: str | None
    business_status: str | None
    phone_raw: str | None
    phone_e164: str | None
    phone_type: str | None
    website_url: str | None
    rating: float | None
    review_count: int
    reviews: list[Review]
    area: str
    cell_key: tuple[str, str, str] | None = None
    name_key: str = ""
    display_name: str = ""
    area_tier: int | None = None
    area_flags: list[str] = field(default_factory=list)
    branch_count: int = 1
    manages_listings: int = 0
    merged_place_ids: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    gate_codes: list[str] = field(default_factory=list)
    pre_score: float = 0.0
    audit: Audit | None = None
    facts: list[Fact] = field(default_factory=list)
    scores: dict[str, Score] = field(default_factory=dict)
    track: str | None = None
    selection: str | None = None    # finalist | reserve
    rank: int | None = None
    slug: str = ""
    review_facts: list[dict[str, Any]] = field(default_factory=list)
    poster_lines: list[str] = field(default_factory=list)
    variants: list[Variant] = field(default_factory=list)
    variant_source: str | None = None
    teaser_jpeg: bytes | None = None
    teaser_path: str | None = None
    lead_id: str | None = None
    evaluation_id: str | None = None

    @property
    def newest_review_at(self) -> datetime | None:
        times = [r.publish_time for r in self.reviews if r.publish_time]
        return max(times) if times else None

    @property
    def domain(self) -> str | None:
        from pipeline.utils.urls import registered_domain
        url = (self.audit.final_url if self.audit and self.audit.final_url else None) or self.website_url
        return registered_domain(url) if url else None

    @property
    def score(self) -> Score | None:
        return self.scores.get(self.track) if self.track else None

    def facts_for(self, track: str) -> list[Fact]:
        return [f for f in self.facts if f.track in (track, "any")]
