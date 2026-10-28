from pipeline.generate import _demo_message, _kind, _lead_payload
from pipeline.store import MemoryStore


def test_ads_leads_get_the_pilot_and_explicit_web_demos_keep_the_website():
    assert _kind({"track": "ads"}) == "pilot"
    assert _kind({"track": "ads", "demo_type": "ads"}) == "pilot"
    assert _kind({"track": "ads", "demo_type": "web"}) == "web"
    assert _kind({"track": "web"}) == "web"


def test_plan_message_has_the_link_and_the_pilot_budget(cfg):
    m = _demo_message(cfg, "Kilima Homes", "pilot", "https://kilima-homes.raswaltechsolutions.co.ke/pilot/")
    assert "Habari Kilima Homes team" in m and "https://kilima-homes.raswaltechsolutions.co.ke/pilot/" in m
    assert "KES 5,000" in m and "7-day" in m and "{" not in m
    assert "Swalleh" in m


def test_lead_payload_carries_brand_logo_offer_and_the_outreach_number(tmp_path):
    store = MemoryStore()
    store.files["brand/p1/logo.png"] = b"\x89PNG fake"
    bundle = {"lead": {"brand": {"logo_path": "brand/p1/logo.png", "offer": {"project": "Joska Heights", "price_cash": 600000}}}}
    brand = {"slug": "joska-plots", "name": "Joska Plots", "short": "Joska", "area": "Joska", "phone_display": "+254 712 345 678",
             "whatsapp": "254712345678", "primary": "#0E4D3A", "accent": "#D4A537"}
    p = _lead_payload(bundle, brand, store, "254114129809")
    assert p["outreach_whatsapp"] == "254114129809" and p["offer"]["project"] == "Joska Heights"
    assert p["logo_path"] and open(p["logo_path"], "rb").read().startswith(b"\x89PNG")
    assert p["slug"] == "joska-plots" and p["listings"] == []
