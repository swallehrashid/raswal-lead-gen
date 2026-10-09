"""Load config/*.yaml into typed models and environment secrets with fail-fast checks.

Secrets are never logged: `install_secret_redaction()` adds a logging filter that
replaces any secret value with "***" in every log record.
"""

from __future__ import annotations

import logging
import os
from datetime import date
from functools import cached_property
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
FIXTURES_DIR = ROOT / "tests" / "fixtures"
OUT_DIR = ROOT / "out"
TEASERS_DIR = ROOT / "teasers"

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False)


# ---------------------------------------------------------------- subcategories


class Palette(_M):
    primary: str
    accent: str
    ink: str
    bg: str


class Subcategory(_M):
    key: str = ""
    label: str
    list_day: Literal["mon", "tue", "wed", "thu", "fri"]
    template: str = ""
    area_set: str
    min_reviews: int = 8
    tier3_enabled: bool = False
    ability_bonus: int = 0
    manages_listings_is_positive: bool = False
    queries: list[str]
    headline: str
    subline: str
    cta: str
    nav: list[str]
    generic_poster_lines: list[str]
    default_palette: Palette


# ---------------------------------------------------------------- areas


class Area(_M):
    name: str
    lat: float
    lng: float
    radius_m: int
    tier: int
    sets: list[str] = []
    flags: list[str] = []


class AreasConfig(_M):
    assign_max_km: float
    areas: list[Area]

    @model_validator(mode="after")
    def _unique(self):
        names = [a.name for a in self.areas]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            raise ValueError(f"duplicate area names in areas.yaml: {sorted(dupes)}")
        return self

    def by_name(self, name: str) -> Area | None:
        return next((a for a in self.areas if a.name == name), None)


# ---------------------------------------------------------------- exclusions


class Portals(_M):
    names: list[str]
    domains: list[str]


class ExclusionsConfig(_M):
    brands: list[str]
    dealer_words: list[str]
    portals: Portals
    excluded_types: list[str]
    building_types: list[str]
    building_words: list[str]
    building_word_exceptions: dict[str, list[str]] = {}
    business_words: list[str]
    gov_ngo_words: list[str]


# ---------------------------------------------------------------- scoring


class Band(_M):
    min: float | None = None
    max: float | None = None
    max_days: int | None = None
    min_strong: int | None = None
    points: float


class Dedupe(_M):
    near_duplicate_ratio: float
    near_duplicate_km: float
    shared_phone_min_listings: int
    relist_cooldown_days: int
    never_relist_statuses: list[str]


class Gates(_M):
    min_rating: float
    dormant_days: int
    accepted_phone_types: list[str]


class Ability(_M):
    premium_or_growth_area: float
    multi_branch_or_listings: float
    multi_branch_min: int
    manages_listings_min: int
    cap: float
    content_multiplier: float
    content_cap: float


class WebScoring(_M):
    pain: dict[str, float]
    hook_points: list[Band]
    min_score: float


class ContentGap(_M):
    no_social_links: float
    no_instagram_or_tiktok: float
    no_video_bonus: float
    stale_blog_bonus: float
    stale_blog_months: int
    cap: float


class ContentScoring(_M):
    gap: ContentGap
    hook_points: list[Band]
    min_score: float
    social_state_bonus: dict[str, float]
    social_state_skip: list[str]


class WeakSite(_M):
    min_signals: int
    psi_perf_below: float
    copyright_age_years: int
    min_words: int


class FactRules(_M):
    slow_mobile_strong_lcp_s: float
    slow_mobile_min_lcp_s: float
    no_site_strong_reviews: int
    recent_reviews_days: int
    recent_reviews_min: int
    high_rating_min: float
    high_rating_min_reviews: int
    good_site_min_perf: float
    generic_themes: list[str]


class Selection(_M):
    targets: dict[str, int]
    reserves: dict[str, int]
    max_per_area_per_track: int
    max_top_hook_share: float


class ScoringConfig(_M):
    dedupe: Dedupe
    gates: Gates
    enrich_limit: int
    review_bands: list[Band]
    ability: Ability
    activity_bands: list[Band]
    reputation_bands: list[Band]
    web: WebScoring
    content: ContentScoring
    weak_site: WeakSite
    facts: FactRules
    selection: Selection


# ---------------------------------------------------------------- messaging


class QuickReply(_M):
    key: str
    label: str
    text: str
    action: str | None = None


class Fallback(_M):
    default_web: str
    default_content: str
    by_code: dict[str, str]
    filler: dict[str, str]


class MessagingConfig(_M):
    signoff: str
    length: dict[str, int]
    max_emoji: int
    swahili_touch_rate: float
    review_copy_max_words: int
    paraphrase_max_words: int
    greetings: dict[str, str]
    bridges: dict[str, str]
    questions: dict[str, list[str]]
    swahili_closers: list[str]
    banned_phrases: list[str]
    fact_texts: dict[str, str]
    fact_priority: list[str]
    fallback: Fallback
    followups: dict[str, str]
    quick_replies: list[QuickReply]
    examples: list[str]


# ---------------------------------------------------------------- budget


class PlacesBudget(_M):
    calls_per_night: int
    calls_per_month: int
    dry_run_calls: int
    target_raw: int
    page_size: int
    max_pages_per_cell: int
    next_page_min_new_ratio: float
    exhausted_new_ratio: float
    exhausted_after_runs: int
    sku: str


class PsiBudget(_M):
    calls_per_night: int
    concurrency: int
    attempts: int
    cache_days: int
    timeout_s: float


class GeminiBudget(_M):
    calls_per_night: int
    rpm: float
    temperature: float
    timeout_s: float


class SiteFetch(_M):
    concurrency: int
    timeout_s: float
    max_redirects: int
    max_bytes: int
    blog_fetch: bool


class RenderBudget(_M):
    concurrency: int
    max_per_night: int
    jpeg_quality: int
    jpeg_min_quality: int
    max_kb: int


class Retention(_M):
    places_raw_days: int
    files_days: int
    purge_files_statuses: list[str]
    db_cap_mb: int
    storage_cap_mb: int


class BudgetConfig(_M):
    places: PlacesBudget
    psi: PsiBudget
    gemini: GeminiBudget
    site_fetch: SiteFetch
    render: RenderBudget
    retention: Retention


# ---------------------------------------------------------------- calendar


class Holiday(_M):
    date: date
    name: str


class Pause(_M):
    start: date
    end: date
    name: str


class Window(_M):
    start: str
    end: str


class CalendarConfig(_M):
    timezone: str
    send_days: list[str]
    holidays: list[Holiday]
    pauses: list[Pause]
    pauses_block_followups: bool
    followups: dict[str, Any]
    pacing: dict[str, Any]
    demo_cap: dict[str, int]
    same_day_demo_cutoff: str


# ---------------------------------------------------------------- audit


class AuditConfig(_M):
    user_agent: str
    social_as_site_hosts: list[str]
    social_as_site_google_paths: list[str]
    platform_names: dict[str, str]
    dead_redirect_hosts: list[str]
    parking_hosts: list[str]
    parked_markers: dict[str, str]
    coming_soon_markers: dict[str, str]
    coming_soon_max_text_chars: int
    default_page_max_text_chars: int
    default_page_markers: list[str]
    error_markers: dict[str, str]
    free_builder_hosts: dict[str, str]
    platform_markers: dict[str, list[str]]
    social_hosts: dict[str, list[str]]
    social_ignore_paths: list[str]
    video_embed_hosts: list[str]
    whatsapp_link_markers: list[str]
    blog_link_words: list[str]
    logo_min_px: int
    hero_min_width_px: int
    max_image_candidates: int


# ---------------------------------------------------------------- top level


class Config(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    subcategories: dict[str, Subcategory]
    areas: AreasConfig
    exclusions: ExclusionsConfig
    scoring: ScoringConfig
    messaging: MessagingConfig
    budget: BudgetConfig
    calendar: CalendarConfig
    audit: AuditConfig

    @model_validator(mode="after")
    def _check(self):
        days = [s.list_day for s in self.subcategories.values()]
        dupes = {d for d in days if days.count(d) > 1}
        if dupes:
            raise ValueError(f"two subcategories share a list_day: {sorted(dupes)}")
        sets = {s for a in self.areas.areas for s in a.sets}
        for key, sub in self.subcategories.items():
            if sub.area_set not in sets:
                raise ValueError(f"subcategory {key}: area_set '{sub.area_set}' has no tier-1 areas")
        return self

    def subcategory_for_day(self, weekday: str) -> Subcategory | None:
        return next((s for s in self.subcategories.values() if s.list_day == weekday), None)

    @cached_property
    def holiday_dates(self) -> dict[date, str]:
        return {h.date: h.name for h in self.calendar.holidays}


def _read_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_config(config_dir: Path = CONFIG_DIR) -> Config:
    subs_raw = _read_yaml(config_dir / "subcategories.yaml")["subcategories"]
    subs = {}
    for key, body in subs_raw.items():
        body = dict(body)
        body.setdefault("template", key)
        subs[key] = Subcategory(key=key, **body)
    return Config(
        subcategories=subs,
        areas=AreasConfig(**_read_yaml(config_dir / "areas.yaml")),
        exclusions=ExclusionsConfig(**_read_yaml(config_dir / "exclusions.yaml")),
        scoring=ScoringConfig(**_read_yaml(config_dir / "scoring.yaml")),
        messaging=MessagingConfig(**_read_yaml(config_dir / "messaging.yaml")),
        budget=BudgetConfig(**_read_yaml(config_dir / "budget.yaml")),
        calendar=CalendarConfig(**_read_yaml(config_dir / "calendar.yaml")),
        audit=AuditConfig(**_read_yaml(config_dir / "audit.yaml")),
    )


# ---------------------------------------------------------------- environment / secrets

# variable → (SETUP_CHECKLIST section that explains how to get it, is_secret)
ENV_VARS: dict[str, tuple[str, bool]] = {
    "GOOGLE_PLACES_API_KEY": ("§2 Google Cloud: Places API + PageSpeed Insights", True),
    "PSI_API_KEY": ("§2 Google Cloud: Places API + PageSpeed Insights", True),
    "GEMINI_API_KEY": ("§3 Gemini API", True),
    "GEMINI_MODEL": ("§3 Gemini API", False),
    "SUPABASE_URL": ("§4 Supabase", False),
    "SUPABASE_SERVICE_ROLE_KEY": ("§4 Supabase", True),
    "SUPABASE_ANON_KEY": ("§4 Supabase", True),
}

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


class MissingSecrets(SystemExit):
    def __init__(self, names: list[str]):
        lines = ["Missing required environment variable(s):"]
        for n in names:
            section = ENV_VARS.get(n, ("see .env.example", False))[0]
            lines.append(f"  - {n}  (how to get it: docs/SETUP_CHECKLIST.md {section})")
        lines.append("Set them in .env for local runs, or as GitHub Actions secrets for the nightly job.")
        lines.append("For a run with no keys at all, use --offline (fixtures only).")
        super().__init__("\n".join(lines))
        self.names = names


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Minimal .env loader (KEY=VALUE lines). Existing environment variables win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


class Env(BaseModel):
    google_places_api_key: str | None = None
    psi_api_key: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str = DEFAULT_GEMINI_MODEL
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None

    @classmethod
    def from_environ(cls) -> Env:
        load_dotenv()
        get = lambda k: os.environ.get(k) or None  # noqa: E731
        return cls(
            google_places_api_key=get("GOOGLE_PLACES_API_KEY"),
            psi_api_key=get("PSI_API_KEY"),
            gemini_api_key=get("GEMINI_API_KEY"),
            gemini_model=get("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL,
            supabase_url=get("SUPABASE_URL"),
            supabase_service_role_key=get("SUPABASE_SERVICE_ROLE_KEY"),
        )

    def require(self, *names: str) -> None:
        missing = [n for n in names if not getattr(self, n.lower(), None)]
        if missing:
            raise MissingSecrets(missing)

    def secret_values(self) -> list[str]:
        vals = [self.google_places_api_key, self.psi_api_key, self.gemini_api_key, self.supabase_service_role_key]
        vals.append(os.environ.get("SUPABASE_ANON_KEY"))
        return [v for v in vals if v and len(v) >= 8]


class _RedactFilter(logging.Filter):
    def __init__(self, secrets: list[str]):
        super().__init__()
        self.secrets = secrets

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        redacted = redact(msg, self.secrets)
        if redacted != msg:
            record.msg, record.args = redacted, ()
        return True


def redact(text: str, secrets: list[str]) -> str:
    for s in secrets:
        text = text.replace(s, "***")
    return text


def install_secret_redaction(env: Env) -> None:
    flt = _RedactFilter(env.secret_values())
    root = logging.getLogger()
    for h in root.handlers:
        h.addFilter(flt)
    # httpx logs full request URLs (PSI puts the key in the query string): keep it quiet.
    for noisy in ("httpx", "httpcore", "hpack", "google_genai", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

