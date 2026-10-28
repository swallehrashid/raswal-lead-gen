import pytest

from pipeline.facts import build_facts, sort_facts
from pipeline.models import Review, Variant
from pipeline.score import score_candidate
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
GOOD = (
    "Habari Kilima Homes team, hope business is going well.\n"
    "I came across Kilima Homes on Google, 4.6★ from 62 reviews; that trust is well earned.\n"
    "I'm Swalleh from Raswal Tech Solutions. We put more enquiries on your WhatsApp. We run Facebook and Instagram ads "
    "that send buyers straight into your WhatsApp, no website needed to start. I've mocked up how your ad could look "
    "(see the image).\n"
    "We can run a free 7-day pilot: you put only KES 5,000 into the ads, and we do the rest.\n"
    "May I send you the full plan? Asante.\n" + SIGN)


@pytest.fixture
def lead(cfg):
    c = make("Kilima Homes", status="dead", website="http://kilimahomes.co.ke/", rating=4.6, reviews=62,
             review_texts=["They arranged a viewing the same afternoon I called, very responsive team.",
                           "Smooth process and the deposit was refunded on time when I moved out."])
    c.reviews[0].author, c.reviews[1].author = "Wanjiru Kamau", "Brian Otieno"
    c.facts = build_facts(c, cfg, NOW)
    score_candidate(c, cfg, NOW)
    return c


@pytest.fixture
def ctx(lead, cfg):
    return LeadContext.from_candidate(lead, cfg)


def ids(ctx, *codes):
    return [f.id for f in ctx.facts.values() if f.code in codes]


def check(msg, ctx, cfg, used=None):
    return validate_variant(msg, used if used is not None else ids(ctx, "HIGH_RATING"), ctx, cfg)


def test_valid_message_passes(ctx, cfg):
    assert check(GOOD, ctx, cfg) == []
    assert ctx.angle == "C" and ctx.noun == "listings"


def test_length(ctx, cfg):
    assert any("length" in e for e in check("Hi Kilima Homes team. Preview attached.\n" + SIGN, ctx, cfg))
    long = GOOD.replace("May I", "x " * 150 + "May I")
    assert any("length" in e for e in check(long, ctx, cfg))


def test_business_name_required(ctx, cfg):
    msg = GOOD.replace("Kilima Homes", "Kilima Home")
    assert any("business name" in e for e in check(msg, ctx, cfg))


def test_signoff_required(ctx, cfg):
    assert any("sign-off" in e for e in check(GOOD.replace(SIGN, "— Swalleh"), ctx, cfg))


def test_core_promise_and_pilot_terms_are_required(ctx, cfg):
    assert any("enquiries on your WhatsApp" in e for e in check(GOOD.replace("enquiries on", "leads on"), ctx, cfg))
    assert any("free 7-day pilot" in e for e in check(GOOD.replace("free 7-day pilot", "trial"), ctx, cfg))
    assert any("KES 5,000" in e for e in check(GOOD.replace("KES 5,000", "a small budget"), ctx, cfg))


def test_must_spell_enquiries(ctx, cfg):
    errs = check(GOOD.replace("buyers straight", "inquiries from buyers straight"), ctx, cfg)
    assert any("enquiries" in e and "inquir" in e for e in errs)


def test_pilot_numbers_are_allowed_without_a_fact(ctx, cfg):
    assert "7-day" in GOOD and "KES 5,000" in GOOD
    assert check(GOOD, ctx, cfg) == []
    assert any("money" in e for e in check(GOOD.replace("KES 5,000", "KES 6,000"), ctx, cfg))


@pytest.mark.parametrize("insert,rule", [
    ("See https://kilima.raswaltechsolutions.co.ke. ", "URL"),
    ("See www.example.com. ", "URL"),
    ("Sites start at KES 30,000. ", "money"),
    ("Only Ksh 25000. ", "money"),
    ("From 30k. ", "money"),
    ("Just 30,000/- ", "money"),
    ("This is revolutionary. ", "banned"),
    ("Dear Sir/Madam, ", "banned"),
    ("Results are guaranteed. ", "banned"),
    ("Expect great ROI. ", "banned"),
    ("It is risk-free. ", "banned"),
])
def test_forbidden_content(ctx, cfg, insert, rule):
    msg = GOOD.replace("I've mocked up", insert + "I've mocked up")
    errs = check(msg, ctx, cfg)
    assert any(rule.lower() in e.lower() for e in errs), errs


def test_banned_words_match_whole_words_only(ctx, cfg):
    assert check(GOOD.replace("Instagram ads", "Instagram ads on Android phones"), ctx, cfg) == []     # 'roi' in android


def test_emoji_limit(ctx, cfg):
    assert count_emoji(GOOD) == 0
    assert check(GOOD.replace("Asante.", "Asante 🙏"), ctx, cfg) == []
    assert any("emoji" in e for e in check(GOOD.replace("Asante.", "Asante 🙏🚀"), ctx, cfg))


def test_numbers_must_come_from_cited_facts(ctx, cfg):
    msg = GOOD.replace("62 reviews", "87 reviews")
    assert any("87" in e for e in check(msg, ctx, cfg))
    # 62 and 4.6 come from HIGH_RATING: dropping it from used ids makes them stray
    assert any("number" in e for e in check(GOOD, ctx, cfg, used=ids(ctx, "RECENT_REVIEWS")))
    msg = GOOD.replace("that trust is well earned", "since 2015 that trust is well earned")
    assert any("2015" in e for e in check(msg, ctx, cfg))


def test_domains(ctx, cfg):
    assert check(GOOD.replace("Google,", "Google (kilimahomes.co.ke),"), ctx, cfg) == []     # own domain is fine
    msg = GOOD.replace("Google,", "Google (kilima-homes.com),")
    assert any("not the lead's own" in e for e in check(msg, ctx, cfg))


def test_fact_ids(ctx, cfg):
    assert any("empty" in e for e in check(GOOD, ctx, cfg, used=[]))
    assert any("unknown" in e for e in check(GOOD, ctx, cfg, used=["F1", "F99"]))


def test_reviewer_names(ctx, cfg):
    assert any("reviewer" in e for e in check(GOOD.replace("that trust", "Wanjiru Kamau loved it, that trust"), ctx, cfg))
    assert any("reviewer" in e for e in check(GOOD.replace("that trust", "Brian says hi, that trust"), ctx, cfg))


def test_six_words_copied_from_review(ctx, cfg):
    msg = GOOD.replace("that trust is well earned", "they arranged a viewing the same afternoon, well earned")
    assert any("consecutive words" in e for e in check(msg, ctx, cfg))
    ok = GOOD.replace("that trust is well earned", "arranged a viewing the same day, well earned")   # 5 words is fine
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


def test_negative_review_themes_never_become_facts(cfg):
    from pipeline.validate import review_fact_to_fact
    neg = {"review_index": 1, "theme": "slow", "sentiment": "negative", "paraphrase": "Slow replies", "addressable_by": "none"}
    assert review_fact_to_fact(neg, "R1", "ads", cfg) is None
    pos = {"review_index": 1, "theme": "fast viewings", "sentiment": "positive",
           "paraphrase": "A reviewer mentioned how quickly you arranged a viewing"}
    f = review_fact_to_fact(pos, "R1", "ads", cfg)
    assert f.code == "REVIEW_THEME" and f.track == "any" and f.strength == "strong"


# ---------------------------------------------------------------- deterministic messages

FALLBACK_CASES = [
    ("dead", dict(status="dead"), "C"),
    ("social_as_site", dict(status="social_as_site"), "C"),
    ("none_87", dict(status="none", reviews=87), "C"),
    ("none_31", dict(status="none", reviews=31, rating=4.2), "C"),
    ("insecure", dict(status="insecure", https_ok=False), "A"),
    ("weak", dict(status="weak", copyright_year=2018, meta_viewport=False), "A"),
    ("good", dict(status="good", social_links={}, has_video=False), "A"),
    ("good_ads", dict(status="good", ads="active", ads_days=10), "B"),
    ("dead_ads_long", dict(status="dead", ads="active", ads_days=90), "B"),
]


@pytest.mark.parametrize("kw,angle", [c[1:] for c in FALLBACK_CASES], ids=[c[0] for c in FALLBACK_CASES])
@pytest.mark.parametrize("sub", ["property_agency", "land_developers"])
@pytest.mark.parametrize("name", ["Kilima Homes", "Gauge 30 Roofing", "Southlands Property Managers Kenya"])
def test_fallback_messages_always_valid(cfg, kw, angle, sub, name):
    c = make(name, sub=sub, website="http://kilimahomes.co.ke/", **kw)
    c.facts = build_facts(c, cfg, NOW)
    score_candidate(c, cfg, NOW)
    assert c.angle == angle
    ctx = LeadContext.from_candidate(c, cfg)
    vs = fallback_variants(ctx, cfg, c.place_id, sort_facts(c.facts_for("ads"), cfg))
    assert len(vs) == 2
    for v in vs:
        assert v.errors == [], (v.message, v.errors)
        assert v.source == "fallback" and "enquiries on your WhatsApp" in v.message
        assert name in v.message and "plots" in v.message or "listings" in v.message or angle == "B" or angle == "C"
    assert vs[0].message.startswith("Habari") and vs[1].message.startswith("Hello")
    if len(ctx.facts) > 1:
        assert validate_pair(vs, ctx) == []


def test_land_messages_say_plots_and_agency_messages_say_listings(cfg):
    for sub, noun in (("land_developers", "plots"), ("property_agency", "listings")):
        c = make("Ardhi Bora", sub=sub, status="good", website="http://ardhi.co.ke/")
        c.facts = build_facts(c, cfg, NOW)
        score_candidate(c, cfg, NOW)
        vs = fallback_variants(LeadContext.from_candidate(c, cfg), cfg, c.place_id, c.facts_for("ads"))
        assert f"for your {noun}" in vs[0].message


def test_fallback_never_names_reviewers(cfg):
    c = make("Kilima Homes", status="none", reviews=40)
    c.reviews = [Review(1, 5, "Great", "Kilima Mwangi", NOW)]
    c.facts = build_facts(c, cfg, NOW)
    score_candidate(c, cfg, NOW)
    vs = fallback_variants(LeadContext.from_candidate(c, cfg), cfg, c.place_id, c.facts_for("ads"))
    assert all("Mwangi" not in v.message for v in vs)
