import pytest

from pipeline.facts import build_facts
from pipeline.models import Review, Variant
from pipeline.validate import (
    LeadContext,
    count_emoji,
    fallback_variants,
    validate_pair,
    validate_review_fact,
    validate_variant,
)
from tests.helpers import NOW, make

SIGN = "— Swalleh, Raswal Tech Solutions"
GOOD = ("Habari Kilima Homes 👋 I tried kilimahomes.co.ke from your Google listing and it's showing an 'account "
        "suspended' page, which is a shame with 4.6★ from 62 reviews. I put together a quick preview of how Kilima "
        "Homes' website could look. It's in the image. Want me to send you the live preview link?\n" + SIGN)


@pytest.fixture
def lead(cfg):
    c = make("Kilima Homes", status="dead", website="http://kilimahomes.co.ke/", rating=4.6, reviews=62,
             review_texts=["They arranged a viewing the same afternoon I called, very responsive team.",
                           "Smooth process and the deposit was refunded on time when I moved out."])
    c.reviews[0].author, c.reviews[1].author = "Wanjiru Kamau", "Brian Otieno"
    c.track = "web"
    c.facts = build_facts(c, cfg, NOW)
    return c


@pytest.fixture
def ctx(lead):
    return LeadContext.from_candidate(lead)


def ids(ctx, *codes):
    return [f.id for f in ctx.facts.values() if f.code in codes]


def check(msg, ctx, cfg, used=None):
    return validate_variant(msg, used if used is not None else ids(ctx, "SITE_DEAD", "HIGH_RATING"), ctx, cfg)


def test_valid_message_passes(ctx, cfg):
    assert check(GOOD, ctx, cfg) == []


def test_length(ctx, cfg):
    assert any("length" in e for e in check("Hi Kilima Homes team. Preview attached.\n" + SIGN, ctx, cfg))
    long = GOOD.replace("Want me", "x " * 150 + "Want me")
    assert any("length" in e for e in check(long, ctx, cfg))


def test_business_name_required(ctx, cfg):
    msg = GOOD.replace("Kilima Homes", "Kilima Home")
    assert any("business name" in e for e in check(msg, ctx, cfg))


def test_signoff_required(ctx, cfg):
    assert any("sign-off" in e for e in check(GOOD.replace(SIGN, "— Swalleh"), ctx, cfg))


@pytest.mark.parametrize("insert,rule", [
    ("See https://kilima.raswaltechsolutions.com. ", "URL"),
    ("See www.example.com. ", "URL"),
    ("Sites start at KES 30,000. ", "money"),
    ("Only Ksh 25000. ", "money"),
    ("From 30k. ", "money"),
    ("Just 30,000/- ", "money"),
    ("This is revolutionary. ", "banned"),
    ("Dear Sir/Madam, ", "banned"),
    ("I noticed you need a site. ", "banned"),
])
def test_forbidden_content(ctx, cfg, insert, rule):
    msg = GOOD.replace("I put together", insert + "I put together")
    errs = check(msg, ctx, cfg)
    assert any(rule.lower() in e.lower() for e in errs), errs


def test_emoji_limit(ctx, cfg):
    assert count_emoji(GOOD) == 1
    assert any("emoji" in e for e in check(GOOD.replace("link?", "link? 🚀"), ctx, cfg))


def test_numbers_must_come_from_cited_facts(ctx, cfg):
    msg = GOOD.replace("62 reviews", "87 reviews")
    assert any("87" in e for e in check(msg, ctx, cfg))
    # 62 and 4.6 come from HIGH_RATING: dropping it from used ids makes them stray
    assert any("number" in e for e in check(GOOD, ctx, cfg, used=ids(ctx, "SITE_DEAD")))
    msg = GOOD.replace("which is a shame", "since 2015, which is a shame")
    assert any("2015" in e for e in check(msg, ctx, cfg))


def test_domains(ctx, cfg):
    assert check(GOOD, ctx, cfg) == []                   # own domain is fine
    msg = GOOD.replace("kilimahomes.co.ke", "kilima-homes.com")
    assert any("not the lead's own" in e for e in check(msg, ctx, cfg))


def test_fact_ids(ctx, cfg):
    assert any("empty" in e for e in check(GOOD, ctx, cfg, used=[]))
    assert any("unknown" in e for e in check(GOOD, ctx, cfg, used=["F1", "F99"]))


def test_reviewer_names(ctx, cfg):
    assert any("reviewer" in e for e in check(GOOD.replace("which is a shame", "Wanjiru Kamau loved it, a shame"), ctx, cfg))
    assert any("reviewer" in e for e in check(GOOD.replace("which is a shame", "Brian says hi, a shame"), ctx, cfg))


def test_six_words_copied_from_review(ctx, cfg):
    msg = GOOD.replace("which is a shame", "they arranged a viewing the same afternoon, a shame")
    assert any("consecutive words" in e for e in check(msg, ctx, cfg))
    ok = GOOD.replace("which is a shame", "arranged a viewing the same day, a shame")   # 5 words is fine
    assert not any("consecutive" in e for e in check(ok, ctx, cfg))


def test_pair_needs_different_openers(ctx):
    a = Variant("x", ["F1", "F2"], "llm")
    b = Variant("y", ["F1"], "llm")
    assert validate_pair([a, b], ctx)
    assert validate_pair([a, Variant("y", ["F2"], "llm")], ctx) == []


@pytest.mark.parametrize("rf,rule", [
    ({"review_index": 7, "paraphrase": "A reviewer praised your viewings", "sentiment": "positive"}, "does not exist"),
    ({"review_index": 1, "paraphrase": "Wanjiru praised your viewings", "sentiment": "positive"}, "name"),
    ({"review_index": 1, "paraphrase": "they arranged a viewing the same afternoon I called", "sentiment": "positive"},
     "verbatim"),
    ({"review_index": 1, "paraphrase": "A reviewer said 3 viewings in one day", "sentiment": "positive"}, "number"),
    ({"review_index": 1, "paraphrase": " ".join(["word"] * 13), "sentiment": "positive"}, "longer"),
    ({"review_index": 1, "paraphrase": "Reviewers mention slow replies", "sentiment": "negative",
      "addressable_by": "none"}, "would not address"),
])
def test_review_fact_rules(ctx, cfg, rf, rule):
    errs = validate_review_fact(rf, ctx, cfg, n_reviews=2)
    assert any(rule in e for e in errs), errs


def test_several_needs_two_reviews(ctx, cfg):
    rf = {"review_index": 1, "paraphrase": "Several reviews praise your quick viewings", "sentiment": "positive"}
    assert validate_review_fact(rf, ctx, cfg, n_reviews=1)
    assert validate_review_fact(rf, ctx, cfg, n_reviews=2) == []


# ---------------------------------------------------------------- fallback templates

FALLBACK_CASES = [
    dict(status="dead"),
    dict(status="social_as_site"),
    dict(status="none", reviews=87),
    dict(status="none", reviews=31, rating=4.2),
    dict(status="insecure", https_ok=False),
    dict(status="free_builder", free_builder="Wix", free_host="kilimahomes.wixsite.com"),
    dict(status="weak", psi_lcp_s=8.4, copyright_year=2018, meta_viewport=False),
    dict(status="good", social_links={}, has_video=False),
    dict(status="good", social_links={"facebook": "x"}, has_video=False),
]


@pytest.mark.parametrize("kw", FALLBACK_CASES, ids=[k["status"] for k in FALLBACK_CASES])
@pytest.mark.parametrize("name", ["Kilima Homes", "Gauge 30 Roofing", "Southlands Property Managers Kenya"])
def test_fallback_templates_always_valid(cfg, kw, name):
    c = make(name, website="http://kilimahomes.co.ke/", **kw)
    c.facts = build_facts(c, cfg, NOW)
    from pipeline.score import score_candidate
    score_candidate(c, cfg, NOW)
    c.track = c.track or "web"
    ctx = LeadContext.from_candidate(c)
    vs = fallback_variants(ctx, cfg, c.place_id, c.facts_for(c.track))
    assert len(vs) == 2
    for v in vs:
        assert v.errors == [], (v.message, v.errors)
        assert v.source == "fallback"
    if len(ctx.facts) > 1:
        assert validate_pair(vs, ctx) == []


def test_fallback_uses_reviews_names_never(cfg):
    c = make("Kilima Homes", status="none", reviews=40)
    c.reviews = [Review(1, 5, "Great", "Kilima Mwangi", NOW)]
    c.facts = build_facts(c, cfg, NOW)
    c.track = "web"
    vs = fallback_variants(LeadContext.from_candidate(c), cfg, c.place_id, c.facts_for("web"))
    assert all("Mwangi" not in v.message for v in vs)
