"""Phase 5 — generate the demo for leads that replied "yes" (status = demo_queued).

For each queued lead this:
  1. turns the lead into a brand dict (pipeline.brandpack),
  2. runs the matching builder in the raswal-pipeline repo —
       pilot → build_pilot.py (3 tailored ad videos + the scroll-story plan page: the default for ads leads)
       web   → build_site.py  (tailors + builds + deploys the website, the upsell demo)
     both deploy to {slug}.raswaltechsolutions.co.ke,
  3. writes the live demo_link + a ready-to-send WhatsApp message back onto the lead.

The lead stays in status `demo_queued` so it still shows in the dashboard's Demo queue —
now with the link pre-filled and the message ready; you send it on WhatsApp and tap
"Mark demo sent". Phase 5 never sends anything itself.

  python -m pipeline generate [--lead-id ID] [--limit N] [--track web|pilot] [--dry-run] [--final --offer FILE]

--dry-run builds locally without deploying and without writing to Supabase.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pipeline.brandpack import brand_dict
from pipeline.pilotcopy import fill
from pipeline.store import build_store
from pipeline.utils.text import display_name, possessive

log = logging.getLogger(__name__)

PIPELINE_DIR = Path(os.environ.get("RASWAL_PIPELINE_DIR", "/home/swalleh/Projects/raswal-pipeline"))
HOST = "raswaltechsolutions.co.ke"


def _demo_message(cfg, name: str, kind: str, link: str) -> str:
    if kind == "pilot":
        return fill(cfg.messaging.followups["plan_delivery"], cfg).format(business=name, link=link)
    greet = cfg.messaging.greetings.get("english", "Hello {business} team").format(business=name)
    body = (f"Here's the free preview I built for {possessive(name)} website — a full site you can "
            f"click through on your phone:\n{link}\n"
            "Take a look and tell me what you think. No obligation at all.")
    return f"{greet}\n{body}\n{cfg.messaging.signoff}"


def _lead_payload(bundle: dict, brand: dict, store, outreach: str) -> dict:
    """lead.json for build_pilot.py: the brand dict + logo file + the client's offer (if the offer form is in)."""
    lead = bundle["lead"]
    logo_path = None
    lp = (lead.get("brand") or {}).get("logo_path")
    if lp:
        data = store.download(lp)
        if data:
            f = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            f.write(data)
            f.close()
            logo_path = f.name
    b = lead.get("brand") or {}
    return {"slug": brand["slug"], "name": brand["name"], "short": brand["short"], "area": brand["area"],
            "phone_display": brand["phone_display"], "whatsapp": brand["whatsapp"], "primary": brand["primary"],
            "accent": brand["accent"], "logo_path": logo_path, "outreach_whatsapp": outreach,
            "offer": b.get("offer") or {}, "listings": b.get("listings") or []}


def _run_builder(kind: str, subcat: str, payload: dict, *, deploy: bool, final_offer: str | None = None) -> None:
    """Shell out to the raswal-pipeline builder; raises CalledProcessError on failure."""
    script = "build_pilot.py" if kind == "pilot" else "build_site.py"
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(payload, f)
        payload_path = f.name
    env = dict(os.environ)
    cmd = [sys.executable, script, subcat, payload_path]
    if kind == "pilot":
        if final_offer:
            cmd += ["--final", "--offer", final_offer]
        if not deploy:
            cmd.append("--no-deploy")
    elif not deploy:
        env["RASWAL_NO_DEPLOY"] = "1"
    try:
        subprocess.run(cmd, cwd=str(PIPELINE_DIR), env=env, check=True)
    finally:
        os.unlink(payload_path)
        if payload.get("logo_path"):
            Path(payload["logo_path"]).unlink(missing_ok=True)


def _kind(lead: dict) -> str:
    """ads leads get the pilot plan; a lead explicitly queued as a website demo gets the website."""
    k = lead.get("demo_type") or lead.get("track")
    return "web" if k == "web" else "pilot"


def _targets(store, args) -> list[dict]:
    if args.lead_id:
        b = store.get_lead_bundle(args.lead_id)
        if not b:
            log.error("lead %s not found", args.lead_id)
            return []
        return [b]
    bundles = []
    for lead in store.leads_by_status(["demo_queued"]):
        if args.track and _kind(lead) != args.track:
            continue
        b = store.get_lead_bundle(lead["id"])
        if b:
            bundles.append(b)
    if args.limit:
        bundles = bundles[: args.limit]
    return bundles


def generate(cfg, env, args) -> int:
    if not PIPELINE_DIR.exists():
        log.error("builder repo not found at %s (set RASWAL_PIPELINE_DIR)", PIPELINE_DIR)
        return 2
    store = build_store(env, offline=False, dry_run=args.dry_run, no_db=False)
    bundles = _targets(store, args)
    if not bundles:
        print("No demos queued." if not args.lead_id else "Nothing to do.")
        return 0

    outreach = str((store.get_settings() or {}).get("outreach_whatsapp") or "").strip()
    if not outreach:
        log.warning("settings.outreach_whatsapp is empty: the plan's Start button has no number. Set it in Settings.")
    ok, failed = 0, 0
    for b in bundles:
        lead = b["lead"]
        kind = _kind(lead)
        brand = brand_dict(b)
        name = display_name((b.get("business") or {}).get("display_name") or brand["name"])
        slug = brand["slug"]
        print(f"\n▶ {name} · {kind} · {slug}.{HOST}")
        try:
            payload = _lead_payload(b, brand, store, outreach) if kind == "pilot" else brand
            offer = getattr(args, "offer", None) if getattr(args, "final", False) else None
            _run_builder(kind, lead["subcategory"], payload, deploy=not args.dry_run, final_offer=offer)
        except subprocess.CalledProcessError as e:
            failed += 1
            log.error("  ✗ builder failed (exit %s) for %s", e.returncode, name)
            continue
        link = f"https://{slug}.{HOST}/pilot/" if kind == "pilot" else f"https://{slug}.{HOST}/"
        if args.dry_run:
            print(f"  ✓ built (dry run; not deployed, lead not updated) → would be {link}")
            ok += 1
            continue
        merged_brand = {**(lead.get("brand") or {}),
                        "demo_message": _demo_message(cfg, name, kind, link),
                        "demo_kind": kind,
                        "demo_generated_at": datetime.now(timezone.utc).isoformat()}
        store.update_lead(lead["id"], {"demo_link": link, "brand": merged_brand})
        print(f"  ✓ live → {link}  (link + message written to lead)")
        ok += 1

    print(f"\nDone: {ok} generated, {failed} failed.")
    return 0 if failed == 0 else 1
