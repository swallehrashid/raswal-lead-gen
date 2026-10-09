"""Interfaces for every external call, and the factory that picks live or fixture clients.

Live clients need keys and fail fast (MissingSecrets) when one is missing. Fixture clients
are only used with --offline (or in tests); a live run never silently falls back to them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from pipeline.models import FetchResult


class PlacesClient(Protocol):
    def search_text(self, query: str, lat: float, lng: float, radius_m: int,
                    page_token: str | None = None) -> dict[str, Any]:
        """One Text Search (New) request. Returns the raw JSON ({places: [...], nextPageToken})."""


class SiteFetcher(Protocol):
    def fetch(self, url: str) -> FetchResult:
        """GET a page, following redirects. Never raises: errors are reported in FetchResult."""

    def fetch_bytes(self, url: str, max_bytes: int = 5_000_000) -> bytes | None:
        """GET an image or other binary. Returns None on any failure."""


class PsiClient(Protocol):
    def run(self, url: str) -> dict[str, Any]:
        """PageSpeed Insights v5, strategy=mobile, category=performance. Raw JSON."""


class LlmClient(Protocol):
    model: str

    def generate_json(self, system: str, prompt: str, schema: type, *, context: dict[str, Any]) -> dict[str, Any]:
        """One structured-output call. `context` is ignored by the live client (fakes use it)."""


@dataclass
class Clients:
    places: PlacesClient
    fetcher: SiteFetcher
    psi: PsiClient
    llm: LlmClient | None
    offline: bool


def build_clients(env, cfg, *, offline: bool, use_llm: bool, subcategory: str | None = None) -> Clients:
    if offline:
        from pipeline.fakes import FixtureFetcher, FixtureLlm, FixturePlaces, FixturePsi
        return Clients(
            places=FixturePlaces(subcategory=subcategory),
            fetcher=FixtureFetcher(),
            psi=FixturePsi(),
            llm=FixtureLlm(cfg) if use_llm else None,
            offline=True,
        )
    names = ["GOOGLE_PLACES_API_KEY", "PSI_API_KEY"] + (["GEMINI_API_KEY"] if use_llm else [])
    env.require(*names)
    from pipeline.discover import LivePlacesClient
    from pipeline.llm import GeminiClient
    from pipeline.psi import LivePsiClient
    from pipeline.utils.http import LiveFetcher
    return Clients(
        places=LivePlacesClient(env.google_places_api_key, cfg),
        fetcher=LiveFetcher(cfg),
        psi=LivePsiClient(env.psi_api_key, cfg),
        llm=GeminiClient(env.gemini_api_key, env.gemini_model, cfg) if use_llm else None,
        offline=False,
    )
