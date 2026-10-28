"""Fill the pilot's numbers (config/pilot.yaml) into outbound copy (config/messaging.yaml).

Only the known tokens below are replaced, so per-lead placeholders such as {business} and {weekday}
are left alone for later. This is the one place pilot numbers become text."""

from __future__ import annotations


def tokens(cfg) -> dict[str, str]:
    p = cfg.pilot
    est = [v for k, v in p.estimates.items() if isinstance(v, dict) and "chats" in v]
    pr = p.pricing
    return {
        "budget": f"{p.budget_kes:,}",
        "days": str(p.pilot_days),
        "vat_note": p.vat_note,
        "engine_intro": f"{pr['engine_intro_kes']:,}",
        "engine_standard": f"{pr['engine_standard_kes']:,}",
        "website_setup": f"{pr['website_setup_kes']:,}",
        "website_monthly": f"{pr['website_monthly_kes']:,}",
        "website_min_months": str(pr["website_min_months"]),
        "december_pack": f"{pr['december_pack_kes']:,}",
        # widest honest range across the verticals
        "chats_low": str(min(e["chats"][0] for e in est)),
        "chats_high": str(max(e["chats"][1] for e in est)),
    }


def fill(text: str, cfg) -> str:
    for k, v in tokens(cfg).items():
        text = text.replace("{" + k + "}", v)
    return text
