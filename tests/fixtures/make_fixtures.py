"""Generate realistic Places API (New) Text Search fixtures for every subcategory.

    .venv/bin/python tests/fixtures/make_fixtures.py

Writes:
  places/<subcategory>_c<cell>_p<page>.json   one Text Search response per file (≤20 places)
  sites/index.json                            domain → how the fake fetcher/PSI should behave

All businesses, names, phones and reviews are fictional. Times are relative to
ANCHOR (2026-10-09); the fixture Places client shifts them so the data always looks current.
Deterministic: re-running produces identical files.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ANCHOR = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
rng = random.Random(20261009)

AREAS = {
    "Westlands": (-1.2676, 36.8108), "Kilimani": (-1.2900, 36.7840), "Kileleshwa": (-1.2810, 36.7790),
    "Lavington": (-1.2770, 36.7690), "Upper Hill": (-1.2990, 36.8150), "Nairobi CBD": (-1.2864, 36.8232),
    "Ngong Road": (-1.3005, 36.7800), "Karen": (-1.3197, 36.7073), "Lang'ata": (-1.3416, 36.7530),
    "South B": (-1.3100, 36.8350), "South C": (-1.3190, 36.8270), "Kasarani": (-1.2200, 36.8920),
    "Embakasi": (-1.3200, 36.9000), "Runda": (-1.2200, 36.8100), "Parklands": (-1.2615, 36.8170),
    "Kirinyaga Road": (-1.2800, 36.8250), "Industrial Area": (-1.3050, 36.8500), "Mombasa Road": (-1.3250, 36.8600),
    "Kariobangi": (-1.2560, 36.8850), "Kangemi": (-1.2640, 36.7470), "Githurai": (-1.2030, 36.9120),
    "Kahawa": (-1.1830, 36.9230), "Ruiru": (-1.1460, 36.9600), "Kitengela": (-1.4730, 36.9600),
    "Syokimau": (-1.3700, 36.9350), "Ruaka": (-1.2090, 36.7770), "Juja": (-1.1020, 37.0140),
}
STREETS = {
    "Westlands": ["Woodvale Grove", "Mpaka Rd", "Waiyaki Way", "Ring Rd Westlands"],
    "Kilimani": ["Argwings Kodhek Rd", "Lenana Rd", "Ralph Bunche Rd", "Kirichwa Rd"],
    "Kileleshwa": ["Othaya Rd", "Laikipia Rd", "Mandera Rd"], "Lavington": ["James Gichuru Rd", "Muthangari Dr"],
    "Upper Hill": ["Upper Hill Rd", "Ragati Rd", "Matumbato Rd"], "Nairobi CBD": ["Moi Ave", "Kimathi St", "Tom Mboya St"],
    "Ngong Road": ["Ngong Rd", "Kindaruma Rd"], "Karen": ["Karen Rd", "Langata South Rd", "Dagoretti Rd"],
    "Lang'ata": ["Langata Rd", "Otiende Rd"], "South B": ["Mchumbi Rd", "Kapiti Rd"], "South C": ["Muhoho Ave", "Mugoya Rd"],
    "Kasarani": ["Thika Rd", "Kasarani-Mwiki Rd"], "Embakasi": ["Outer Ring Rd", "Embakasi Rd"], "Runda": ["Kiambu Rd", "Runda Dr"],
    "Parklands": ["Limuru Rd", "3rd Parklands Ave"], "Kirinyaga Road": ["Kirinyaga Rd", "Racecourse Rd", "Luthuli Ave"],
    "Industrial Area": ["Enterprise Rd", "Lunga Lunga Rd", "Likoni Rd"], "Mombasa Road": ["Mombasa Rd", "Old Mombasa Rd"],
    "Kariobangi": ["Outer Ring Rd", "Kariobangi North Rd"], "Kangemi": ["Waiyaki Way", "Kangemi Rd"],
    "Githurai": ["Kamiti Rd", "Thika Rd"], "Kahawa": ["Thika Rd", "Kahawa Sukari Ave"], "Ruiru": ["Ruiru-Kiambu Rd", "Thika Rd"],
    "Kitengela": ["Namanga Rd", "EPZ Rd"], "Syokimau": ["Syokimau Rd", "Katani Rd"], "Ruaka": ["Limuru Rd", "Ruaka Rd"],
    "Juja": ["Thika Rd", "Juja Farm Rd"],
}
AUTHORS = ["Wanjiru Kamau", "Brian Otieno", "Achieng Odhiambo", "Kevin Mutua", "Faith Njeri", "Abdi Hassan",
           "Mercy Chebet", "Dennis Kiprop", "Grace Wambui", "Peter Mwangi", "Lucy Akinyi", "Samuel Kariuki",
           "Fatuma Ali", "James Ochieng", "Esther Wairimu", "Collins Kipchumba", "Mary Nduta", "Hassan Omar",
           "Joy Atieno", "Daniel Kimani", "Purity Moraa", "Ian Waweru", "Nancy Jeptoo", "Victor Onyango"]

REVIEWS = {
    "property_agency": {
        "pos": ["They arranged a viewing the same afternoon I called. Very responsive team.",
                "Found my two bedroom in Kilimani through them and the whole process was smooth, deposit refunded on time when I moved.",
                "The agent was patient and showed us four houses in one day. Highly recommend for anyone house hunting.",
                "They manage our block and repairs are always sorted quickly. Tenants are happy.",
                "Honest agents, no hidden fees. They explained the lease clearly before I signed.",
                "Quick viewings and they answer on WhatsApp even on weekends.",
                "Very professional, helped me find a bedsitter within my budget in two days."],
        "neg": ["Hard to find their available units anywhere online, I had to call several times to get a list.",
                "Took long to respond to my enquiry, but once they did the viewing was fine.",
                "I wish they posted photos of the houses somewhere, wasted a trip to see a unit that was already taken."],
    },
    "land_developers": {
        "pos": ["Bought a plot in Kitengela with them, title deed was ready as promised. Genuine company.",
                "The site visit was well organised, they picked us from town and showed us the beacons.",
                "Transparent process, they took us through the search at the lands office before payment.",
                "Flexible payment plan and they kept updating me until I got my title.",
                "Office staff are welcoming and explain every step. I've bought two plots with them now."],
        "neg": ["Took a while to get the title but they kept communicating.",
                "Could not find much information about their projects online before visiting the office.",
                "I wish they had a website showing which plots are still available, had to call many times."],
    },
    "construction": {
        "pos": ["They built our four bedroom house in Ruiru and the finishing is very neat. Finished on time.",
                "Did a full kitchen renovation for us, clean work and they left the site tidy every day.",
                "Very professional contractors, they shared progress photos every week while we were abroad.",
                "The foreman was always on site and the quality of the masonry is excellent.",
                "They handled the approvals and the build. Neat work and honest about costs."],
        "neg": ["Good work but it was hard to see examples of their previous projects before hiring them.",
                "Slight delays because of rain but the final work was good.",
                "Wish they had a portfolio online, I only hired them because a friend referred me."],
    },
    "hardware_supplies": {
        "pos": ["They have almost everything for plumbing and the prices are fair. Delivered to my site the same day.",
                "Friendly staff, they helped me pick the right tiles and calculated how many boxes I needed.",
                "Good stock of paint and they mix colours quickly. Fair prices.",
                "My go-to hardware for building materials, delivery is fast within Ruiru.",
                "Genuine products and they give receipts. Staff know their stuff."],
        "neg": ["Had to call to check if they had stock before driving there, wish I could check online.",
                "Long queue on Saturday but they eventually served me well.",
                "Prices are not displayed anywhere so you have to ask for everything."],
    },
    "roofing_steel": {
        "pos": ["Bought mabati for my house, the gauge was exactly as quoted and they delivered to Juja the next day.",
                "Very good quality roofing sheets and the colours are as shown. Fair prices.",
                "They fabricated our gate and window grills, strong work and finished on time.",
                "Helpful team, they came to measure the roof and gave an accurate quote.",
                "Steel was genuine and well priced compared to other suppliers on Mombasa Road."],
        "neg": ["I could not find their price list or gauges anywhere, had to visit to get a quote.",
                "Delivery took an extra day but the roofing sheets were good.",
                "Wish they had their profiles and colours online so I could choose before visiting."],
    },
}

TYPES = {
    "property_agency": (["real_estate_agency", "point_of_interest", "establishment"], "real_estate_agency"),
    "land_developers": (["real_estate_agency", "point_of_interest", "establishment"], "real_estate_agency"),
    "construction": (["general_contractor", "point_of_interest", "establishment"], "general_contractor"),
    "hardware_supplies": (["hardware_store", "home_goods_store", "store", "point_of_interest", "establishment"], "hardware_store"),
    "roofing_steel": (["roofing_contractor", "point_of_interest", "establishment"], "roofing_contractor"),
}

# Site behaviours the fake fetcher understands (see tests/fixtures/sites/README.md).
SITE_KINDS = {
    "good_wp": {"file": "good_wordpress.html", "psi": "fast", "logo": True, "og": True, "blog": "blog_stale.html"},
    "good_nosocial": {"file": "good_no_social.html", "psi": "fast", "logo": True, "og": True},
    "good_fbonly": {"file": "good_fb_only.html", "psi": "medium_good", "logo": True, "og": False},
    "good_video": {"file": "good_with_video.html", "psi": "fast", "logo": True, "og": True},
    "weak_old": {"file": "weak_old_desktop.html", "psi": "slow", "logo": True},
    "weak_wix": {"file": "weak_wix_slow.html", "psi": "slow", "logo": True},
    "weak_thin": {"file": "weak_thin.html", "psi": "medium", "logo": False},
    "insecure": {"file": "insecure_http_only.html", "psi": "medium", "https": "ssl_error", "logo": True},
    "free_wix": {"file": "free_builder_wixsite.html", "psi": "medium", "logo": True},
    "dead_suspended": {"file": "parked_suspended.html"},
    "dead_expired": {"file": "parked_expired.html"},
    "dead_forsale": {"file": "parked_for_sale.html"},
    "dead_soon": {"file": "coming_soon.html"},
    "dead_default": {"file": "hosting_default.html"},
    "dead_index": {"file": "index_of.html"},
    "dead_dns": {"error": "dns"},
    "dead_404": {"file": "error_404.html", "status": 404},
    "dead_500": {"status": 503, "file": "error_503.html"},
    "dead_bizsite": {"redirect_to": "https://{slug}.business.site/", "error_after_redirect": "dns"},
}
LOGO_COLOURS = ["#0E6BA8", "#C0392B", "#1E8449", "#7D3C98", "#D35400", "#117A65", "#2E4053", "#B7950B"]


def pid(n: int) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
    r = random.Random(n * 7919)
    return "ChIJ" + "".join(r.choice(alphabet) for _ in range(23))


def mobile() -> tuple[str, str]:
    prefix = rng.choice(["0712", "0722", "0723", "0724", "0727", "0733", "0745", "0757", "0768", "0790", "0796",
                         "0110", "0111", "0113", "0100", "0702", "0706", "0717", "0729", "0740"])
    rest = f"{rng.randint(0, 999999):06d}"
    return f"{prefix} {rest}", f"+254 {prefix[1:]} {rest}"


def landline() -> tuple[str, str]:
    rest = f"{rng.randint(2000000, 4999999)}"
    return f"020 {rest}", f"+254 20 {rest}"


def slug(name: str) -> str:
    return "".join(c for c in name.lower() if c.isalnum())[:22]


def jitter(area: str, km: float = 1.2) -> tuple[float, float]:
    lat, lng = AREAS[area]
    return round(lat + rng.uniform(-km, km) / 111, 6), round(lng + rng.uniform(-km, km) / 111, 6)


def reviews_for(sub: str, n: int, newest_days: int, rating: float, pain: bool = False) -> list[dict]:
    pool = REVIEWS[sub]
    out = []
    ages = sorted([newest_days] + [newest_days + rng.randint(5, 300) for _ in range(n - 1)])
    texts = rng.sample(pool["pos"], k=min(len(pool["pos"]), n))
    if pain:
        texts[-1] = rng.choice(pool["neg"])
    authors = rng.sample(AUTHORS, k=n)
    for i in range(n):
        t = ANCHOR - timedelta(days=ages[i], hours=rng.randint(0, 20))
        stars = 5 if rating >= 4.5 else rng.choice([4, 5]) if rating >= 4 else rng.choice([2, 3, 4])
        if pain and i == n - 1:
            stars = 3
        txt = texts[i % len(texts)]
        rid = f"r{rng.randint(10**8, 10**9)}"
        out.append({
            "name": f"places/PLACE/reviews/{rid}",
            "relativePublishTimeDescription": rel(ages[i]),
            "rating": stars,
            "text": {"text": txt, "languageCode": "en"},
            "originalText": {"text": txt, "languageCode": "en"},
            "authorAttribution": {"displayName": authors[i],
                                  "uri": f"https://www.google.com/maps/contrib/{rng.randint(10**20, 10**21)}/reviews",
                                  "photoUri": "https://lh3.googleusercontent.com/a/fixture=s128-c0x00000000-cc-rp-mo"},
            "publishTime": t.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
            "flagContentUri": "https://www.google.com/local/review/rap/report?postId=fixture",
            "googleMapsUri": f"https://www.google.com/maps/reviews/data=fixture-{rid}",
        })
    # Places returns "most relevant" order, not newest first
    rng.shuffle(out)
    return out


def rel(days: int) -> str:
    if days < 7:
        return f"{max(days, 1)} days ago" if days > 1 else "a day ago"
    if days < 30:
        return f"{days // 7} weeks ago" if days >= 14 else "a week ago"
    if days < 365:
        return f"{days // 30} months ago" if days >= 60 else "a month ago"
    return f"{days // 365} years ago" if days >= 730 else "a year ago"


_counter = [0]
sites: dict[str, dict] = {}


def place(sub: str, name: str, area: str, *, reviews: int = 40, rating: float = 4.5, newest_days: int = 12,
          site: str | None = None, phone: str = "mobile", status: str = "OPERATIONAL", types=None,
          n_reviews_returned: int = 5, pain: bool = False, website: str | None = None, logo_colour: str | None = None,
          latlng: tuple[float, float] | None = None, fixed_phone: tuple[str, str] | None = None) -> dict:
    _counter[0] += 1
    place_id = pid(_counter[0])
    lat, lng = latlng or jitter(area)
    tps, primary = types or TYPES[sub]
    p = {
        "id": place_id,
        "displayName": {"text": name, "languageCode": "en"},
        "formattedAddress": f"{rng.choice(STREETS[area])}, Nairobi, Kenya" if area not in ("Ruiru", "Kitengela", "Juja", "Syokimau", "Ruaka") else f"{rng.choice(STREETS[area])}, {area}, Kenya",
        "location": {"latitude": lat, "longitude": lng},
        "types": list(tps),
        "primaryType": primary,
        "businessStatus": status,
        "googleMapsUri": f"https://maps.google.com/?cid={rng.randint(10**18, 10**19)}",
    }
    if fixed_phone:
        p["nationalPhoneNumber"], p["internationalPhoneNumber"] = fixed_phone
    elif phone == "mobile":
        p["nationalPhoneNumber"], p["internationalPhoneNumber"] = mobile()
    elif phone == "landline":
        p["nationalPhoneNumber"], p["internationalPhoneNumber"] = landline()
    elif phone == "intl_only":
        p["internationalPhoneNumber"] = mobile()[1]
    if website:
        p["websiteUri"] = website
    elif site:
        kind = SITE_KINDS[site]
        s = slug(name)
        if site == "free_wix":
            host = f"{s}.wixsite.com"
            url = f"https://{host}/home"
        else:
            tld = rng.choice([".co.ke", ".co.ke", ".com", ".ke"])
            host = f"{s}{tld}"
            url = rng.choice([f"http://{host}/", f"https://{host}/", f"http://www.{host}/"])
        p["websiteUri"] = url
        entry = {"kind": site, **{k: v for k, v in kind.items()}, "name": name, "phone": p.get("nationalPhoneNumber", "")}
        if "redirect_to" in entry:
            entry["redirect_to"] = entry["redirect_to"].format(slug=s)
        if kind.get("logo"):
            entry["logo_colour"] = logo_colour or rng.choice(LOGO_COLOURS)
        sites[host] = entry
    if reviews:
        p["rating"] = rating
        p["userRatingCount"] = reviews
        p["reviews"] = reviews_for(sub, min(n_reviews_returned, reviews), newest_days, rating, pain)
        for r in p["reviews"]:
            r["name"] = r["name"].replace("PLACE", place_id)
    return p


def good_mix(sub: str, names: list[str], areas: list[str], site_cycle: list[str | None]) -> list[dict]:
    out = []
    for i, name in enumerate(names):
        site = site_cycle[i % len(site_cycle)]
        reviews = rng.choice([14, 22, 31, 38, 47, 58, 76, 93, 124, 167, 212, 260])
        rating = rng.choice([4.1, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9])
        newest = rng.choice([3, 6, 9, 15, 22, 34, 48, 70, 110])
        out.append(place(sub, name, areas[i % len(areas)], reviews=reviews, rating=rating, newest_days=newest,
                         site=site, pain=(i % 4 == 0)))
    return out


def property_agency() -> list[dict]:
    S = "property_agency"
    A = ["Westlands", "Kilimani", "Kileleshwa", "Lavington", "Upper Hill", "Nairobi CBD", "Ngong Road", "Karen",
         "Lang'ata", "South B", "South C", "Kasarani", "Embakasi", "Runda", "Parklands"]
    good_names = ["Kilima Homes", "Mwangaza Realty", "Savanna Property Managers", "Jumuia Estate Agents",
                  "Baraka Properties Ltd", "Nyumba Bora Agencies", "Tujenge Realtors", "Kijani Homes & Lettings",
                  "Amani Property Consultants", "Zuri Nyumba Ltd", "Mlimani Real Estate", "Bahari Realty",
                  "Ndovu Property Management", "Simba Homes Agency", "Twiga Lettings", "Upendo Properties",
                  "Kito Realtors", "Imara Property Services", "Neema Homes Ltd", "Rafiki Estate Agents",
                  "Mapema Lettings", "Shwari Homes", "Faraja Property Managers", "Kifaru Realty",
                  "Jamii Housing Agents", "Starlight Properties Kenya", "Greenline Realtors", "Hillcrest Property Managers",
                  "Keja Hunters Kenya", "Urban Nest Realty", "Prime Keys Properties", "Westgate Homes Agency",
                  "Lavender Property Group", "Maji Mazuri Agencies", "Garden City Lettings", "Southlands Property Managers",
                  "Riverbank Realtors", "Acacia Property Agents", "Highpoint Lettings", "Makao Bora Realty",
                  "Tulivu Homes Agency", "Jirani Property Services", "Mvule Realtors", "Nyota Lettings Ltd",
                  "Kahawa Homes Agency", "Pembe Property Managers", "Fahari Realty", "Sauti Homes"]
    cycle = [None, "good_wp", "dead_suspended", "social_fb", "good_nosocial", "weak_old", None, "good_fbonly",
             "insecure", "dead_expired", "good_video", "free_wix", "social_ig", "weak_wix", "dead_dns", "good_wp",
             "weak_thin", "dead_soon", None, "good_nosocial", "dead_404", "social_linktree", "dead_bizsite",
             "good_fbonly", "dead_default", "weak_old", "social_wa", "dead_500", "good_nosocial", "dead_index",
             "dead_forsale", "social_maps"]
    social_urls = {"social_fb": "https://www.facebook.com/{s}", "social_ig": "https://instagram.com/{s}",
                   "social_linktree": "https://linktr.ee/{s}", "social_wa": "https://wa.me/254722000111",
                   "social_maps": "https://maps.app.goo.gl/Fx{s}"}
    out = []
    for i, name in enumerate(good_names):
        kind = cycle[i % len(cycle)]
        reviews = rng.choice([16, 22, 31, 38, 47, 58, 76, 93, 124, 167, 212, 260])
        rating = rng.choice([4.2, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9])
        newest = rng.choice([3, 6, 9, 15, 22, 34, 48, 70])
        if kind and kind.startswith("social_"):
            out.append(place(S, name, A[i % len(A)], reviews=reviews, rating=rating, newest_days=newest,
                             website=social_urls[kind].format(s=slug(name)), pain=(i % 3 == 0)))
        else:
            out.append(place(S, name, A[i % len(A)], reviews=reviews, rating=rating, newest_days=newest,
                             site=kind, pain=(i % 3 == 0)))
    # --- bad leads ---
    bad = [
        place(S, "Kenya Homes Centre", "Nairobi CBD", reviews=88, phone="landline", site="good_wp"),
        place(S, "Capital Realty Ltd", "Upper Hill", reviews=54, phone="landline"),
        place(S, "Metro Lettings Bureau", "Nairobi CBD", reviews=23, phone="landline", site="dead_suspended"),
        place(S, "Ridgeways Property Consultants", "Runda", reviews=31, phone="landline"),
        place(S, "Kilimani Heights Apartments", "Kilimani", reviews=19, types=(["apartment_building", "point_of_interest", "establishment"], "apartment_building")),
        place(S, "Lenana Court", "Kilimani", reviews=12),
        place(S, "Sunrise Villas", "Karen", reviews=27),
        place(S, "Woodlands Residency", "Westlands", reviews=15, types=(["apartment_complex", "point_of_interest", "establishment"], "apartment_complex")),
        place(S, "Garden Estate", "Kasarani", reviews=44),
        place(S, "Westpark Towers", "Westlands", reviews=61),
        place(S, "Knight Frank Kenya", "Upper Hill", reviews=310, site="good_wp"),
        place(S, "HassConsult Real Estate", "Westlands", reviews=280, site="good_video"),
        place(S, "Pam Golding Properties Kenya", "Karen", reviews=145, site="good_wp"),
        place(S, "BuyRentKenya Office", "Westlands", reviews=40, website="https://www.buyrentkenya.com/"),
        place(S, "National Housing Corporation", "Nairobi CBD", reviews=210, phone="landline"),
        place(S, "Nairobi County Housing Department", "Nairobi CBD", reviews=35),
        place(S, "Wema Agencies", "Embakasi", reviews=4, rating=5.0),
        place(S, "Peter Kamau Properties", "Kasarani", reviews=6, rating=4.8),
        place(S, "Dalali Halisi", "South B", reviews=3, rating=5.0),
        place(S, "Old Town Realtors", "Parklands", reviews=26, newest_days=420, rating=4.3),
        place(S, "Eastlands Housing Agents", "Embakasi", reviews=18, newest_days=700, rating=4.1),
        place(S, "Quickfix Lettings", "South C", reviews=33, rating=2.9, site="weak_old"),
        place(S, "Fast Homes Agency", "Kasarani", reviews=21, rating=3.2),
        place(S, "Closed Door Realty", "Kileleshwa", reviews=40, status="CLOSED_PERMANENTLY"),
        place(S, "Pause Properties", "Lavington", reviews=29, status="CLOSED_TEMPORARILY"),
        place(S, "Silent Realtors", "Lang'ata", reviews=25, phone="none"),
        place(S, "Jipange Property Agents", "Ngong Road", reviews=0),
        place(S, "Bidii Homes", "Embakasi", reviews=52, rating=4.6, phone="intl_only"),
    ]
    out += bad
    # --- shared phone: an agent's number on 4 building listings + their agency listing ---
    agent_phone = ("0721 908877", "+254 721 908877")
    shared = [
        place(S, "Amani Gardens Apartments", "Kileleshwa", reviews=14, fixed_phone=agent_phone,
              types=(["apartment_building", "point_of_interest", "establishment"], "apartment_building")),
        place(S, "Kileleshwa Court", "Kileleshwa", reviews=9, fixed_phone=agent_phone),
        place(S, "Othaya Road Suites", "Kileleshwa", reviews=11, fixed_phone=agent_phone,
              types=(["apartment_building", "point_of_interest", "establishment"], "apartment_building")),
        place(S, "Mandera Heights", "Kileleshwa", reviews=8, fixed_phone=agent_phone),
        place(S, "Kipande Property Managers", "Kileleshwa", reviews=36, rating=4.6, newest_days=8,
              fixed_phone=agent_phone, site="dead_dns"),
    ]
    out += shared
    # --- duplicates: same place twice, near-duplicate name, branches ---
    dup_src = out[0]
    lat, lng = dup_src["location"]["latitude"], dup_src["location"]["longitude"]
    near = place(S, dup_src["displayName"]["text"] + " Ltd", "Westlands", reviews=9, latlng=(lat + 0.003, lng + 0.002))
    branch_a = place(S, "Makazi Realtors Westlands", "Westlands", reviews=64, rating=4.7, newest_days=5)
    branch_b = place(S, "Makazi Realtors Karen", "Karen", reviews=41, rating=4.6, newest_days=11)
    out += [near, branch_a, branch_b]
    rng.shuffle(out)
    out.insert(45, json.loads(json.dumps(dup_src)))       # exact duplicate on a later page
    return out


def simple(sub: str, names: list[str], areas: list[str], cycle: list[str | None], bad: list[dict]) -> list[dict]:
    out = good_mix(sub, names, areas, cycle) + bad
    rng.shuffle(out)
    return out


def land() -> list[dict]:
    S = "land_developers"
    names = ["Ardhi Bora Properties", "Shamba Yetu Investments", "Plotwise Kenya", "Fanaka Land Company",
             "Mavuno Plots Ltd", "Taifa Land Developers", "Haki Land Investments", "Kisima Developers",
             "Uwanja Land Ltd", "Bonde Properties", "Mali Safi Land Company", "Kesho Bora Developers",
             "Nchi Yetu Plots", "Upeo Land Investments", "Tazama Homes Developers", "Milele Land Ltd",
             "Hekima Real Estate Developers", "Baraka Plots Kitengela", "Mlima Land Company", "Sifa Developers",
             "Panda Land Investments", "Kivuko Properties", "Mwamba Land Ltd", "Pendo Plots", "Dira Land Company",
             "Mapato Developers", "Jua Kali Plots Ltd", "Kanaan Land Investments", "Tumaini Developers",
             "Vuna Land Company", "Mizizi Properties", "Chemchemi Plots", "Utulivu Developers", "Mashamba Bora Ltd",
             "Kilele Land Company", "Simama Developers"]
    A = ["Westlands", "Upper Hill", "Nairobi CBD", "Kilimani", "Ngong Road", "Karen", "Kasarani", "Embakasi"]
    cycle = [None, "dead_suspended", "good_nosocial", "good_wp", "weak_old", "free_wix", "dead_expired", "good_fbonly",
             "insecure", None, "good_video", "weak_wix", "dead_dns", "good_nosocial"]
    bad = [place(S, "Optiven Group", "Westlands", reviews=900, site="good_video"),
           place(S, "Username Investments", "Nairobi CBD", reviews=640, site="good_wp"),
           place(S, "Cytonn Investments", "Westlands", reviews=410),
           place(S, "Ngong Plots Office", "Ngong Road", reviews=17, phone="landline"),
           place(S, "Ruiru Gardens", "Kasarani", reviews=22),
           place(S, "Small Plots Agency", "Embakasi", reviews=5),
           place(S, "Kenya Land Board Office", "Nairobi CBD", reviews=60),
           place(S, "Stale Land Ltd", "Karen", reviews=30, newest_days=500)]
    return simple(S, names, A, cycle, bad)


def construction() -> list[dict]:
    S = "construction"
    names = ["Tausi Builders", "Jenga Imara Contractors", "Msingi Construction Ltd", "Ujenzi Bora Builders",
             "Kuta Renovations", "Paa Fit-Out Interiors", "Nguzo Construction", "Mjengo Masters Ltd",
             "Ramani Builders", "Kiwango Contractors", "Simiti Construction", "Dari Interiors & Fit-Out",
             "Mwalimu Builders", "Tofali Construction Company", "Nyumba Safi Renovations", "Jengo Contractors",
             "Sakafu Interiors", "Mfumo Builders Ltd", "Kipimo Construction", "Mawe Contractors", "Uimara Builders",
             "Kazi Safi Renovations", "Boma Construction Ltd", "Ngazi Builders", "Kiunzi Contractors",
             "Mbao & Mawe Fit-Out", "Kona Renovations", "Upana Construction", "Dirisha Builders", "Mlango Contractors",
             "JKL Builders", "Zege Construction"]
    A = ["Westlands", "Kilimani", "Karen", "Kasarani", "Embakasi", "Ngong Road", "South C", "Runda"]
    cycle = [None, "dead_suspended", "good_nosocial", "weak_old", "good_wp", None, "free_wix", "dead_soon",
             "good_fbonly", "insecure", "weak_thin", "good_video", "dead_dns"]
    bad = [place(S, "China Road and Bridge Corporation", "Upper Hill", reviews=150),
           place(S, "China Wu Yi Kenya", "Mombasa Road", reviews=90),
           place(S, "Nairobi County Public Works", "Nairobi CBD", reviews=40),
           place(S, "National Construction Authority", "Upper Hill", reviews=300, phone="landline"),
           place(S, "Fundi Mmoja", "Kasarani", reviews=3),
           place(S, "Low Score Builders", "Embakasi", reviews=19, rating=3.1)]
    return simple(S, names, A, cycle, bad)


def hardware() -> list[dict]:
    S = "hardware_supplies"
    names = ["Mwangaza Hardware", "Kirinyaga Plumbing Supplies", "Rangi Paint Centre", "Tile World Ruiru",
             "Baraka Hardware & Electricals", "Juja Road Hardware", "Fundi Supplies Ltd", "Bomba Plumbing Centre",
             "Rangi Bora Paints", "Kigae Tiles & Sanitary", "Nguvu Hardware", "Msingi Building Supplies",
             "Mabomba Plumbing Ltd", "Pamoja Hardware Githurai", "Mjenzi Hardware", "Simba Tiles Centre",
             "Wekeza Hardware", "Kahawa Paint House", "Thika Road Hardware", "Bidii Building Materials",
             "Malighafi Supplies", "Rangi Mbili Paints", "Zawadi Hardware", "Mfereji Plumbing Supplies",
             "Imara Hardware Kariobangi", "Kangemi Building Supplies", "Twende Hardware", "Ufundi Tools & Hardware",
             "Kona Tiles", "Sakafu Bora Tiles"]
    A = ["Kirinyaga Road", "Industrial Area", "Mombasa Road", "Kariobangi", "Kangemi", "Githurai", "Kahawa",
         "Ngong Road", "Embakasi", "Kasarani"]
    cycle = [None, "social_fb", "good_nosocial", "weak_old", None, "dead_expired", "good_fbonly", "weak_wix",
             "free_wix", None, "good_wp", "dead_dns"]
    out = []
    for i, name in enumerate(names):
        kind = cycle[i % len(cycle)]
        kw = dict(reviews=rng.choice([22, 35, 48, 66, 90, 130, 175, 240]), rating=rng.choice([4.2, 4.4, 4.5, 4.6, 4.8]),
                  newest_days=rng.choice([2, 5, 9, 14, 25, 40, 75]), pain=(i % 4 == 0))
        if kind == "social_fb":
            out.append(place(S, name, A[i % len(A)], website=f"https://web.facebook.com/{slug(name)}", **kw))
        else:
            out.append(place(S, name, A[i % len(A)], site=kind, **kw))
    out += [place(S, "Crown Paints Kenya", "Industrial Area", reviews=210, site="good_wp"),
            place(S, "Crown Paints Dealer Githurai", "Githurai", reviews=45, rating=4.5, newest_days=6),
            place(S, "Tile and Carpet Centre", "Mombasa Road", reviews=380, site="good_video"),
            place(S, "Basco Paints Depot Kahawa", "Kahawa", reviews=28, rating=4.4, newest_days=12),
            place(S, "Kiosk ya Mama Hardware", "Kariobangi", reviews=7),
            place(S, "Old Kirinyaga Hardware", "Kirinyaga Road", reviews=44, phone="landline"),
            place(S, "Paint & Tile Mall", "Mombasa Road", reviews=120,
                  types=(["shopping_mall", "point_of_interest", "establishment"], "shopping_mall"))]
    rng.shuffle(out)
    return out


def roofing() -> list[dict]:
    S = "roofing_steel"
    names = ["Mabati Bora Roofing", "Imara Steel Suppliers", "Paa Safi Roofing", "Chuma Fabricators",
             "Gauge 30 Roofing Ltd", "Bati Imara Ltd", "Nyota Steel & Hardware", "Paa Letu Roofing",
             "Kali Steel Fabricators", "Mwamba Roofing Solutions", "Tile Roof Masters", "Chuma Bora Steel",
             "Vigae Roofing Company", "Mabati Express", "Simba Steel Supplies", "Kifuniko Roofing",
             "Pembe Fabrication Works", "Juja Roofing Centre", "Upepo Roofing", "Nguzo Steel Ltd",
             "Dari Roofing Systems", "Mvua Roofing Kenya", "Mabati Yetu", "Chuma Safi Welders",
             "Kasarani Roofing Mart", "Embakasi Steel Works", "Paa Bora Roofing"]
    A = ["Industrial Area", "Mombasa Road", "Kirinyaga Road", "Githurai", "Kahawa", "Embakasi", "Kasarani", "Kariobangi"]
    cycle = [None, "dead_suspended", "weak_old", "good_nosocial", None, "free_wix", "good_fbonly", "dead_dns",
             "insecure", "weak_thin", "good_wp", "dead_500"]
    bad = [place(S, "Mabati Rolling Mills", "Mombasa Road", reviews=520, site="good_video"),
           place(S, "Safal MRM Kenya", "Mombasa Road", reviews=180),
           place(S, "Devki Steel Mills", "Industrial Area", reviews=240, phone="landline"),
           place(S, "Safal MRM Stockist Githurai", "Githurai", reviews=33, rating=4.5, newest_days=10),
           place(S, "Small Welding Shop", "Kariobangi", reviews=4)]
    return simple(S, names, A, cycle, bad)


def paginate(sub: str, places: list[dict], pages_per_cell: list[int]) -> dict[str, dict]:
    files: dict[str, dict] = {}
    i = 0
    for c, n_pages in enumerate(pages_per_cell, start=1):
        for p in range(1, n_pages + 1):
            chunk = places[i:i + 20]
            i += 20
            if not chunk:
                break
            body: dict = {"places": chunk}
            more = p < n_pages and i < len(places)
            if more:
                body["nextPageToken"] = f"fixture:{sub}_c{c}_p{p + 1}"
            files[f"{sub}_c{c}_p{p}.json"] = body
    return files


def main() -> None:
    out_dir = HERE / "places"
    out_dir.mkdir(exist_ok=True)
    for f in out_dir.glob("*.json"):
        f.unlink()
    sets = {
        "property_agency": (property_agency(), [3, 2, 1]),
        "land_developers": (land(), [2, 1]),
        "construction": (construction(), [2, 1]),
        "hardware_supplies": (hardware(), [2, 1]),
        "roofing_steel": (roofing(), [2, 1]),
    }
    total = 0
    for sub, (places, pages) in sets.items():
        files = paginate(sub, places, pages)
        for name, body in files.items():
            (out_dir / name).write_text(json.dumps(body, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        total += len(places)
        print(f"{sub}: {len(places)} places in {len(files)} pages")
    (HERE / "sites").mkdir(exist_ok=True)
    (HERE / "sites" / "index.json").write_text(json.dumps(dict(sorted(sites.items())), indent=1) + "\n", encoding="utf-8")
    print(f"total {total} places, {len(sites)} site domains")


if __name__ == "__main__":
    main()
