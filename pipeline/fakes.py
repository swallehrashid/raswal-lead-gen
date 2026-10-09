"""Fixture-backed clients for --offline runs and tests. Never used by a live run.

Places:  tests/fixtures/places/<subcategory>_c<cell>_p<page>.json, served cell by cell.
Sites:   tests/fixtures/sites/index.json (domain → behaviour) + sites/*.html templates.
PSI:     tests/fixtures/psi/psi_<profile>.json.
Gemini:  tests/fixtures/gemini/<place_id>.json if present, else synthesised from the prompt context.

Fixture review times are relative to 2026-10-09; they are shifted so that the data always
looks as fresh as it did on that date (otherwise every fixture business turns DORMANT).
"""

from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pipeline.settings import FIXTURES_DIR

FIXTURE_ANCHOR = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)


def _shift_reviews(place: dict, delta: timedelta) -> dict:
    for r in place.get("reviews", []) or []:
        t = r.get("publishTime")
        if t:
            dt = datetime.fromisoformat(t.replace("Z", "+00:00")) + delta
            r["publishTime"] = dt.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
    return place


class FixturePlaces:
    def __init__(self, subcategory: str | None = None, fixtures: Path = FIXTURES_DIR / "places",
                 now: datetime | None = None):
        self.dir = fixtures
        self.subcategory = subcategory
        self.delta = (now or datetime.now(timezone.utc)) - FIXTURE_ANCHOR
        self.calls: list[dict[str, Any]] = []
        self._next_cell = 1

    def _load(self, name: str) -> dict:
        path = self.dir / f"{name}.json"
        if not path.exists():
            return {}
        body = json.loads(path.read_text(encoding="utf-8"))
        body = copy.deepcopy(body)
        for p in body.get("places", []):
            _shift_reviews(p, self.delta)
        return body

    def search_text(self, query, lat, lng, radius_m, page_token=None):
        self.calls.append({"query": query, "lat": lat, "lng": lng, "radius_m": radius_m, "page_token": page_token})
        if page_token:
            return self._load(page_token.removeprefix("fixture:"))
        sub = self.subcategory or "property_agency"
        name = f"{sub}_c{self._next_cell}_p1"
        self._next_cell += 1
        return self._load(name)   # {} once the fixture cells run out (like an empty result)


# ---------------------------------------------------------------- site fetcher

class FixtureFetcher:
    """Serves tests/fixtures/sites according to sites/index.json."""

    def __init__(self, fixtures: Path = FIXTURES_DIR):
        self.dir = fixtures / "sites"
        self.img_dir = fixtures / "images"
        self.index: dict[str, dict] = json.loads((self.dir / "index.json").read_text(encoding="utf-8"))
        self.fetched: list[str] = []

    def _entry(self, url: str) -> tuple[str, dict | None]:
        from pipeline.utils.urls import host
        h = host(url)
        return h, self.index.get(h)

    def _render(self, file: str, entry: dict, host: str) -> str:
        html = (self.dir / file).read_text(encoding="utf-8")
        year = datetime.now(timezone.utc).year
        return (html.replace("{{NAME}}", entry.get("name", "Business"))
                .replace("{{PHONE}}", entry.get("phone", ""))
                .replace("{{PHONE_INTL}}", re.sub(r"\D", "", entry.get("phone", "")).replace("0", "254", 1))
                .replace("{{HOST}}", host)
                .replace("{{YEAR}}", str(year))
                .replace("{{SLUG}}", host.split(".")[0]))

    def fetch(self, url: str):
        from pipeline.models import FetchResult
        from pipeline.utils.urls import with_scheme
        self.fetched.append(url)
        h, e = self._entry(url)
        if e is None:
            if h.endswith("business.site"):
                return FetchResult(url=url, error="dns", error_detail="fixture: business.site is gone")
            # Unknown hosts behave like a site that doesn't exist.
            return FetchResult(url=url, error="dns", error_detail="fixture: unknown host")
        scheme = url.split("://", 1)[0] if "://" in url else "http"
        if e.get("error"):
            return FetchResult(url=url, error=e["error"], error_detail="fixture")
        if e.get("https") == "ssl_error" and scheme == "https":
            return FetchResult(url=url, error="ssl", error_detail="CERTIFICATE_VERIFY_FAILED (fixture)")
        if e.get("redirect_to"):
            target = e["redirect_to"]
            return FetchResult(url=url, final_url=target, redirect_chain=[url, target],
                               error=e.get("error_after_redirect", "dns"), error_detail="fixture redirect")
        final = with_scheme(url, scheme)
        if e.get("https") == "ssl_error":
            final = with_scheme(url, "http")
        path = url.split(h, 1)[-1]
        file = e.get("blog") if e.get("blog") and any(w in path for w in ("/blog", "/news")) else e.get("file")
        html = self._render(file, e, h) if file else ""
        return FetchResult(url=url, final_url=final, status_code=e.get("status", 200), html=html,
                           redirect_chain=[url] if final == url else [url, final],
                           headers={"content-type": "text/html; charset=utf-8"})

    def fetch_bytes(self, url: str, max_bytes: int = 5_000_000) -> bytes | None:
        from pipeline.utils.urls import host
        h = host(url)
        e = self.index.get(h)
        if not e:
            return None
        path = url.split(h, 1)[-1]
        if "logo" in path or "apple-touch-icon" in path:
            colour = (e.get("logo_colour") or "#0E6BA8").lstrip("#").upper()
            f = self.img_dir / f"logo_{colour}.png"
        elif "og" in path or "hero" in path:
            idx = sum(map(ord, h)) % 3 + 1
            f = self.img_dir / f"hero_{idx}.jpg"
        elif "blog" in path or "news" in path:
            return None
        else:
            return None
        return f.read_bytes() if f.exists() else None


# ---------------------------------------------------------------- PSI

class FixturePsi:
    def __init__(self, fixtures: Path = FIXTURES_DIR):
        self.dir = fixtures / "psi"
        self.index: dict[str, dict] = json.loads((fixtures / "sites" / "index.json").read_text(encoding="utf-8"))
        self.calls: list[str] = []

    def run(self, url: str) -> dict:
        from pipeline.utils.urls import host
        self.calls.append(url)
        profile = (self.index.get(host(url)) or {}).get("psi", "medium")
        data = json.loads((self.dir / f"psi_{profile}.json").read_text(encoding="utf-8"))
        data["id"] = url
        data["lighthouseResult"]["finalUrl"] = url
        return data


# ---------------------------------------------------------------- Gemini

THEMES = [  # keyword in review → (theme, paraphrase, poster line)
    ("viewing", "fast viewings", "A reviewer mentioned how quickly you arranged a viewing", "Book a viewing on WhatsApp"),
    ("deposit", "smooth move-in", "A reviewer said the whole process was smooth, deposit included", "Smooth, honest lettings"),
    ("title", "titles delivered", "A buyer said their title deed was ready as promised", "Genuine plots, clear titles"),
    ("site visit", "organised site visits", "A buyer praised how well organised the site visit was", "Book a free site visit"),
    ("finishing", "neat finishing", "A client praised the neat finishing on their house", "Neat work, finished on time"),
    ("renovation", "clean renovations", "A client said the renovation was clean and tidy", "Renovations done right"),
    ("progress photos", "progress updates", "A client valued the weekly progress photos while abroad", "Weekly progress updates"),
    ("delivered", "fast delivery", "A customer said you delivered to their site the same day", "Delivery to your site"),
    ("tiles", "helpful advice", "A customer said your staff helped them pick the right tiles", "Ask us what you need"),
    ("paint", "quick colour mixing", "A customer liked how quickly you mix paint colours", "Colours mixed while you wait"),
    ("gauge", "accurate quotes", "A customer said the gauge was exactly as quoted", "Get a roofing quote on WhatsApp"),
    ("fabricated", "strong fabrication", "A client praised the strong gate and grill work", "Gates and grills built to last"),
    ("whatsapp", "responsive on WhatsApp", "A reviewer said you answer on WhatsApp even at weekends", "Chat with us on WhatsApp"),
    ("professional", "professional team", "A reviewer described your team as very professional", "A team you can rely on"),
]
PAINS = [
    ("online", "hard to find online", "A reviewer said it was hard to find your details online", "website"),
    ("photos", "no photos to browse", "A reviewer wished they could see photos before visiting", "website"),
    ("price", "no price list", "A customer said prices aren't listed anywhere", "website"),
    ("portfolio", "no portfolio", "A client said it was hard to see your past projects", "website"),
    ("respond", "slow responses", "A reviewer mentioned waiting a while for a response", "none"),
]


class FixtureLlm:
    """Synthesises Gemini-shaped JSON from the prompt context (deterministic).

    A fixture file tests/fixtures/gemini/<place_id>.json, if present, is returned instead.
    Every 5th business (by place_id) gets a first answer that breaks a rule (a link), so
    the retry path runs offline; every 11th breaks it twice, exercising the fallback.
    """

    model = "fixture-gemini"

    def __init__(self, cfg, fixtures: Path = FIXTURES_DIR):
        self.cfg = cfg
        self.dir = fixtures / "gemini"
        self.calls: list[dict[str, Any]] = []

    def generate_json(self, system: str, prompt: str, schema: type, *, context: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(context)
        f = self.dir / f"{context['place_id']}.json"
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
        h = sum(map(ord, context["place_id"]))
        attempt = context.get("attempt", 0)
        broken = (h % 5 == 0 and attempt == 0) or h % 11 == 0
        return self._synth(context, broken)

    def _synth(self, ctx: dict[str, Any], broken: bool) -> dict[str, Any]:
        reviews = ctx["reviews"]
        review_facts, posters = [], []
        for r in reviews:
            low = r["text"].lower()
            if (r.get("rating") or 5) >= 4:
                for kw, theme, para, poster in THEMES:
                    if kw in low and all(rf["theme"] != theme for rf in review_facts):
                        review_facts.append({"review_index": r["index"], "theme": theme, "sentiment": "positive",
                                             "paraphrase": para, "addressable_by": "none"})
                        posters.append(poster)
                        break
            else:
                for kw, theme, para, fix in PAINS:
                    if kw in low:
                        review_facts.append({"review_index": r["index"], "theme": theme, "sentiment": "negative",
                                             "paraphrase": para, "addressable_by": fix})
                        break
            if len(review_facts) == 3:
                break
        facts = {f["id"]: f for f in ctx["facts"]}
        ids = list(facts) + [f"R{i}" for i in range(1, len(review_facts) + 1)]
        texts = {**{k: v["text"] for k, v in facts.items()},
                 **{f"R{i}": rf["paraphrase"] + "." for i, rf in enumerate(review_facts, start=1)}}
        variants = []
        for i in range(2):
            open_id = ctx["opening"][i] if ctx["opening"][i] in facts else ids[0]
            second = next((x for x in ids if x != open_id and x != ctx["opening"][1 - i]), None)
            greet = (f"Habari {ctx['business']}" if ctx["swahili"][i] else f"Hi {ctx['business']} team") + (
                " 👋" if i == 0 else ".")
            body = texts[open_id]
            used = [open_id]
            msg = f"{greet} {body} {ctx['bridge']} {ctx['questions'][i % len(ctx['questions'])]}"
            if second and len(msg) + len(ctx["signoff"]) < 330:
                msg = f"{greet} {body} {texts[second]} {ctx['bridge']} {ctx['questions'][i % len(ctx['questions'])]}"
                used.append(second)
            if ctx["swahili"][i]:
                msg += " Asante!"
            if len(msg) + len(ctx["signoff"]) + 1 < 280:
                msg += " It only takes a minute to look through, and you can tell me what you would change."
            if broken and i == 0:
                msg += " See https://raswaltechsolutions.com"
            variants.append({"message": f"{msg}\n{ctx['signoff']}", "used_fact_ids": used})
        posters = (posters + ctx["generic_poster_lines"])[:3]
        return {"review_facts": review_facts, "variants": variants, "poster_lines": posters}
