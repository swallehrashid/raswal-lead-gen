import json
from datetime import date

from pipeline.adlib import apply_ads_index, apply_instagram, match, parse_ad, parse_instagram, sync, wa_phone_from_link
from pipeline.settings import FIXTURES_DIR, Env
from pipeline.store import MemoryStore
from tests.helpers import make

TODAY = date(2026, 10, 28)
ITEMS = json.loads((FIXTURES_DIR / "apify" / "facebook_ads.json").read_text())


class FakeApify:
    def __init__(self, data):
        self.data, self.calls = data, []

    def run(self, actor, payload):
        self.calls.append((actor, payload))
        return self.data


def test_whatsapp_numbers_from_links():
    assert wa_phone_from_link("https://wa.me/254722000111?text=Hi") == "+254722000111"
    assert wa_phone_from_link("https://api.whatsapp.com/send?phone=0722000111") == "+254722000111"
    assert wa_phone_from_link("https://wa.me/447700900123") is None            # not a Kenyan number
    assert wa_phone_from_link("https://kingsdevelopers.co.ke/plots") is None and wa_phone_from_link(None) is None


def test_parse_ad_is_tolerant_and_skips_rows_without_an_id_or_page():
    rows = [parse_ad(i) for i in ITEMS]
    assert [r["ad_archive_id"] for r in rows if r] == ["111", "112", "113", "115"]
    assert rows[0]["wa_phone_e164"] == "+254722000111" and rows[0]["page_name_norm"] == "fanaka real estate"
    assert rows[2]["start_date"] and rows[2]["wa_phone_e164"] is None


def test_sync_without_a_token_is_a_clean_skip(cfg):
    assert sync(cfg, Env(), MemoryStore())["status"] == "skipped"


def test_sync_stores_the_ads_once(cfg):
    store, fake = MemoryStore(), FakeApify(ITEMS)
    r = sync(cfg, Env(), store, client=fake)
    assert r == {"status": "ok", "ads": 4} and len(store.tables["ad_library_ads"]) == 4
    assert len(fake.calls) == len(cfg.budget.apify.queries)
    sync(cfg, Env(), store, client=fake)                                   # idempotent: same archive ids
    assert len(store.tables["ad_library_ads"]) == 4


def test_match_by_phone_then_name(cfg):
    store = MemoryStore()
    sync(cfg, Env(), store, client=FakeApify(ITEMS))
    ads = store.load_ad_library(8)
    by_phone = make("Totally Different Name", sub="land_developers", phone="+254722000111")
    by_name = make("Kings Developers Limited", sub="land_developers")
    nobody = make("Quiet Plots", sub="land_developers")
    assert len(match(by_phone, ads, cfg, TODAY)) == 2
    assert len(match(by_name, ads, cfg, TODAY)) == 1 and match(nobody, ads, cfg, TODAY) == []


def test_apply_index_sets_status_count_and_longest_run(cfg):
    store = MemoryStore()
    sync(cfg, Env(), store, client=FakeApify(ITEMS))
    a = make("Fanaka Real Estate", sub="land_developers", phone="+254722000111")
    b = make("Quiet Plots", sub="land_developers")
    apply_ads_index([a, b], store, cfg, TODAY)
    assert (a.ads_status, a.ads_active_count, a.ads_longest_days) == ("active", 2, 88)       # 1 Aug → 28 Oct
    assert a.ads_sample and a.ads_sample[0]["start_date"] == "2026-08-01"
    assert b.ads_status == "none"


def test_no_index_means_unknown_never_none(cfg):
    c = make("Quiet Plots", sub="land_developers")
    apply_ads_index([c], MemoryStore(), cfg, TODAY)
    assert c.ads_status == "unknown"


def test_stale_index_is_ignored(cfg):
    store = MemoryStore()
    sync(cfg, Env(), store, client=FakeApify(ITEMS))
    for r in store.tables["ad_library_ads"].values():
        r["last_seen_at"] = "2026-09-01T00:00:00+00:00"
    c = make("Fanaka Real Estate", sub="land_developers", phone="+254722000111")
    apply_ads_index([c], store, cfg, TODAY)
    assert c.ads_status == "unknown"


def test_instagram_activity(cfg):
    ig = json.loads((FIXTURES_DIR / "apify" / "instagram.json").read_text())
    got = parse_instagram(ig[0], TODAY)
    assert got["ig_followers"] == 4200 and got["ig_posts_30d"] == 2 and got["ig_last_post_at"].startswith("2026-10-20")
    c = make("Kilima Homes", social_links={"instagram": "https://instagram.com/kilimahomes/"})
    assert apply_instagram([c], cfg, Env(), TODAY, client=FakeApify(ig)) == 1
    assert c.social["ig_posts_30d"] == 2
    assert apply_instagram([make("No IG")], cfg, Env(), TODAY) == 0                     # no token, no client: a no-op
