import pytest

from pipeline.models import Review
from pipeline.scam import scam_check
from tests.helpers import NOW, make


def with_reviews(*pairs):
    c = make("Plots Ltd", sub="land_developers", status="good")
    c.reviews = [Review(i + 1, rating, text, f"R{i}", NOW) for i, (rating, text) in enumerate(pairs)]
    return c


def test_hard_term_in_low_review_excludes(cfg):
    c = with_reviews((1, "These people are scammers, they took my deposit"), (5, "Great"))
    scam_check(c, cfg)
    assert c.scam_flag == "hard" and "scammers" in c.scam_terms and "SCAM_RISK" in c.gate_codes


def test_swahili_terms(cfg):
    c = with_reviews((1, "Ni matapeli, wameniibia pesa yangu"))
    scam_check(c, cfg)
    assert c.scam_flag == "hard" and {"matapeli", "wameniibia", "pesa yangu"} <= set(c.scam_terms)


def test_phrase_terms(cfg):
    c = with_reviews((2, "I lost my money and never refunded"))
    scam_check(c, cfg)
    assert c.scam_flag == "hard"


def test_high_rating_review_mentioning_scam_does_not_fire(cfg):
    c = with_reviews((5, "I was afraid it was a scam but they delivered my title on time"))
    scam_check(c, cfg)
    assert c.scam_flag is None and not c.gate_codes


def test_soft_term_penalises_without_excluding(cfg):
    c = with_reviews((3, "Still waiting for my title after months, no refund either"))
    scam_check(c, cfg)
    assert c.scam_flag == "soft" and "SCAM_RISK" not in c.gate_codes
    assert "still waiting for my title" in c.scam_terms


def test_soft_term_in_a_happy_review_is_ignored(cfg):
    c = with_reviews((4, "Easy refund policy explained clearly"))
    scam_check(c, cfg)
    assert c.scam_flag is None


def test_matching_is_whole_word(cfg):
    c = with_reviews((1, "Their staff were rude, the police station is next door"))
    scam_check(c, cfg)
    assert c.scam_flag == "hard" and c.scam_terms == ["police"]
    c = with_reviews((1, "Rude people, a very unfaithful and fakeness-filled experience"))   # no whole-word term
    scam_check(c, cfg)
    assert c.scam_flag is None


def test_hard_beats_soft_and_flag_resets(cfg):
    c = with_reviews((1, "scam, avoid"))
    scam_check(c, cfg)
    assert c.scam_flag == "hard"
    c.reviews = []
    c.gate_codes = []
    scam_check(c, cfg)
    assert c.scam_flag is None and c.scam_terms == []


@pytest.mark.parametrize("flag,penalty", [("soft", -15), (None, None)])
def test_flag_feeds_the_score(cfg, flag, penalty):
    from pipeline.score import ads_score
    c = make(scam=flag)
    assert ads_score(c, cfg, NOW).breakdown.get("scam_soft") == penalty
