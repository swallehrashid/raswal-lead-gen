import pytest

from pipeline.normalise import parse_phone

ACCEPTED = {"MOBILE", "FIXED_LINE_OR_MOBILE"}


@pytest.mark.parametrize("raw,e164", [
    ("0722 123456", "+254722123456"),       # Safaricom 07xx
    ("0712-345-678", "+254712345678"),
    ("0110 123456", "+254110123456"),       # Safaricom 01xx
    ("0111 234567", "+254111234567"),
    ("0733 123456", "+254733123456"),       # Airtel 07xx
    ("0100 123456", "+254100123456"),       # Airtel 010x
    ("0757 123456", "+254757123456"),
    ("+254 722 123456", "+254722123456"),   # international formats
    ("+254722123456", "+254722123456"),
    ("254722123456", "+254722123456"),
])
def test_kenyan_mobiles_accepted(raw, e164):
    got, kind = parse_phone(raw, None)
    assert got == e164 and kind in ACCEPTED


@pytest.mark.parametrize("raw", ["020 2345678", "+254 20 2345678", "(020) 444 5555", "0207 123456", "041 2223344"])
def test_landlines_rejected(raw):
    _, kind = parse_phone(raw, None)
    assert kind == "FIXED_LINE"


@pytest.mark.parametrize("raw", ["12345", "", None, "not a phone"])
def test_invalid(raw):
    assert parse_phone(raw, None) == (None, None)


def test_international_preferred_over_national():
    assert parse_phone("0722 123456", "+254 733 999888")[0] == "+254733999888"


def test_foreign_landline_not_accepted():
    _, kind = parse_phone("+44 20 7946 0958", None)
    assert kind not in ACCEPTED
