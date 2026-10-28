import copy
import json

import pytest
from pydantic import ValidationError

from pipeline.budget import Budget, Cap
from pipeline.draft import Drafter, make_draft_finalizer, system_prompt, user_prompt
from pipeline.facts import build_facts
from pipeline.fakes import FixtureLlm
from pipeline.llm import GeminiOutput, LlmUnavailable, RateLimited
from pipeline.score import score_candidate
from pipeline.settings import FIXTURES_DIR
from tests.helpers import NOW, make


def fixture(name):
    return json.loads((FIXTURES_DIR / "gemini" / name).read_text())


class Scripted:
    model = "scripted"

    def __init__(self, *responses):
        self.responses = list(responses)
        self.prompts = []

    def generate_json(self, system, prompt, schema, *, context):
        self.prompts.append(prompt)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return copy.deepcopy(r)


def budget(n=60):
    return Budget(caps={"gemini": Cap(n)}, month_used={}, month="2026-10")


def kilima(cfg):
    c = make("Kilima Homes", status="dead", website="http://kilimahomes.co.ke/", rating=4.6, reviews=62,
             review_texts=["They arranged a viewing the same afternoon I called.",
                           "Smooth process and the deposit came back on time.",
                           "Could not find which units were available anywhere online, had to call."])
    c.facts = build_facts(c, cfg, NOW)
    score_candidate(c, cfg, NOW)
    return c


def test_schema_contract():
    for name in ("valid_ads.json", "invalid_first_then_valid.json"):
        GeminiOutput.model_validate(fixture(name))
    with pytest.raises(ValidationError):
        GeminiOutput.model_validate(fixture("malformed.json"))
    schema = GeminiOutput.model_json_schema()
    assert set(schema["properties"]) == {"review_facts", "variants", "poster_lines"}


def test_prompt_contains_rules_facts_and_no_reviewer_names(cfg):
    c = kilima(cfg)
    c.reviews[0].author = "Wanjiru Kamau"
    p = user_prompt(c, cfg, opening=["F1", "F2"])
    assert "Kilima Homes" in p and "F1" in p and "Angle: C" in p
    assert "account suspended" not in p                # website problems are never first-message material
    assert "Habari Kilima Homes team" in p and "Hello Kilima Homes team" in p and "free 7-day pilot" in p
    assert "Wanjiru" not in p
    s = system_prompt(cfg)
    assert "— Swalleh, Raswal Tech Solutions" in s and "380-700" in s and "never \"inquiries\"" in s


def test_valid_llm_output(cfg):
    c = kilima(cfg)
    llm = Scripted(fixture("valid_ads.json"))
    d = Drafter(cfg, llm, budget(), sleep=lambda s: None)
    d.draft(c)
    assert c.variant_source == "llm" and all(v.source == "llm" for v in c.variants)
    assert "REVIEW_THEME" in {f.code for f in c.facts}
    assert "REVIEW_PAIN" not in {f.code for f in c.facts}
    assert len(llm.prompts) == 1
    assert c.poster_lines[0] == "Book a viewing on WhatsApp"


def test_retry_with_errors_then_valid(cfg):
    c = kilima(cfg)
    llm = Scripted(fixture("invalid_first_then_valid.json"), fixture("valid_ads.json"))
    d = Drafter(cfg, llm, budget(), sleep=lambda s: None)
    d.draft(c)
    assert c.variant_source == "llm" and len(llm.prompts) == 2
    assert "rejected for these reasons" in llm.prompts[1] and "URL" in llm.prompts[1]


def test_two_failures_use_fallback(cfg):
    c = kilima(cfg)
    bad = fixture("invalid_first_then_valid.json")
    d = Drafter(cfg, Scripted(bad, bad), budget(), sleep=lambda s: None)
    d.draft(c)
    assert c.variant_source == "fallback" and all(not v.errors for v in c.variants)
    # invalid poster lines (price, domain, invented numbers) are replaced by generic ones
    assert c.poster_lines == cfg.subcategories["property_agency"].generic_poster_lines


def test_malformed_json_retried(cfg):
    c = kilima(cfg)
    d = Drafter(cfg, Scripted(fixture("malformed.json"), fixture("valid_ads.json")), budget(),
                sleep=lambda s: None)
    d.draft(c)
    assert c.variant_source == "llm"


def test_unavailable_and_budget_use_fallback(cfg):
    c = kilima(cfg)
    Drafter(cfg, Scripted(LlmUnavailable("quota")), budget(), sleep=lambda s: None).draft(c)
    assert c.variant_source == "fallback"
    c = kilima(cfg)
    llm = Scripted()
    Drafter(cfg, llm, budget(0), sleep=lambda s: None).draft(c)
    assert c.variant_source == "fallback" and llm.prompts == []


def test_rate_limit_retried(cfg):
    c = kilima(cfg)
    llm = Scripted(RateLimited("429"), fixture("valid_ads.json"))
    b = budget()
    Drafter(cfg, llm, b, sleep=lambda s: None).draft(c)
    assert c.variant_source == "llm" and b.used("gemini") == 2


def test_no_llm_fallback(cfg):
    c = kilima(cfg)
    Drafter(cfg, None, budget(), sleep=lambda s: None).draft(c)
    assert c.variant_source == "fallback" and len(c.variants) == 2


def test_finalizer_review_theme_can_supply_the_opener(cfg):
    c = make("Tausi Builders", sub="construction", status="good", reviews=25, rating=4.7,
             review_texts=["They built our house and the finishing is very neat.", "Finished on time."])
    c.facts = build_facts(c, cfg, NOW)
    score_candidate(c, cfg, NOW)
    fin = make_draft_finalizer(cfg, Drafter(cfg, FixtureLlm(cfg), budget(), sleep=lambda s: None), NOW)
    assert fin(c) is True
    assert any(f.code == "REVIEW_THEME" and f.strength == "strong" for f in c.facts)
    assert len(c.variants) == 2 and all(not v.errors for v in c.variants)
    assert "for your projects" in c.variants[0].message


def test_finalizer_rejects_unhooked_without_llm(cfg):
    c = make("Plain Homes", status="good", reviews=25, rating=None, review_texts=["ok"])   # nothing true to open with
    c.facts = build_facts(c, cfg, NOW)
    score_candidate(c, cfg, NOW)
    assert c.facts_for("ads") == []
    fin = make_draft_finalizer(cfg, Drafter(cfg, None, budget(), sleep=lambda s: None), NOW)
    assert fin(c) is False


def test_gemini_client_daily_quota_trips_breaker(cfg):
    from google.genai import errors

    from pipeline.llm import GeminiClient
    gc = GeminiClient("test-key", "gemini-2.5-flash", cfg)
    gc.min_interval = 0
    calls = []

    def boom(**kw):
        calls.append(kw)
        msg = "Quota exceeded. GenerateRequestsPerDayPerProjectPerModel-FreeTier"
        raise errors.ClientError(429, {"error": {"code": 429, "message": msg, "status": "RESOURCE_EXHAUSTED"}})
    gc.client.models.generate_content = boom
    with pytest.raises(LlmUnavailable):
        gc.generate_json("s", "p", GeminiOutput, context={})
    with pytest.raises(LlmUnavailable):
        gc.generate_json("s", "p", GeminiOutput, context={})
    assert len(calls) == 1          # second call never reached the API


def test_gemini_client_per_minute_429_is_retryable(cfg):
    from google.genai import errors

    from pipeline.llm import GeminiClient
    gc = GeminiClient("test-key", "gemini-2.5-flash", cfg)
    gc.min_interval = 0

    def boom(**kw):
        raise errors.ClientError(429, {"error": {"code": 429, "message": "Resource exhausted. Please try again later.",
                                                 "status": "RESOURCE_EXHAUSTED"}})
    gc.client.models.generate_content = boom
    with pytest.raises(RateLimited):
        gc.generate_json("s", "p", GeminiOutput, context={})
    assert not gc.daily_quota_hit
