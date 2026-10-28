"""Phase 5 — generate the demo for leads that replied "yes" (status = demo_queued).

For each queued lead this:
  1. turns the lead into a brand dict (pipeline.brandpack),
  2. runs the matching builder in the raswal-pipeline repo —
       web   → build_site.py  (tailors + builds + deploys the website, the upsell demo)
       pilot → build_pilot.py (ads pilot-plan page; arrives in ads-pivot P6)
     both deploy to {slug}.raswaltechsolutions.co.ke,
  3. writes the live demo_link + a ready-to-send WhatsApp message back onto the lead.

The lead stays in status `demo_queued` so it still shows in the dashboard's Demo queue —
now with the link pre-filled and the message ready; you send it on WhatsApp and tap
"Mark demo sent". Phase 5 never sends anything itself.

  python -m pipeline generate [--lead-id ID] [--limit N] [--track web|pilot] [--dry-run]

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
from pipeline.store import build_store
from pipeline.utils.text import display_name, possessive

log = logging.getLogger(__name__)

PIPELINE_DIR = Path(os.environ.get("RASWAL_PIPELINE_DIR", "/home/swalleh/Projects/raswal-pipeline"))
HOST = "raswaltechsolutions.co.ke"


def _demo_message(cfg, name: str, kind: str, link: str) -> str:
    greet = cfg.messaging.greetings.get("english", "Hi {business} team 👋").format(business=name)
    body = (f"Here's the free preview I built for {possessive(name)} website — a full site you can "
            f"click through on your phone:\n{link}\n"
            "Take a look and tell me what you think. No obligation at all.")
    return f"{greet}\n{body}\n{cfg.messaging.signoff}"


def _run_builder(kind: str, subcat: str, brand: dict, *, deploy: bool) -> None:
    """Shell out to the raswal-pipeline builder; raises CalledProcessError on failure."""
    if kind != "web":
        raise NotImplementedError(f"no builder for demo kind '{kind}' yet (pilot arrives in ads-pivot P6)")
    script = "build_site.py"
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(brand, f)
        brand_path = f.name
    env = dict(os.environ)
    cmd = [sys.executable, script, subcat, brand_path]
    if not deploy:
        env["RASWAL_NO_DEPLOY"] = "1"
    try:
        subprocess.run(cmd, cwd=str(PIPELINE_DIR), env=env, check=True)
    finally:
        os.unlink(brand_path)


def _targets(store, args) -> list[dict]:
    if args.lead_id:
        b = store.get_lead_bundle(args.lead_id)
        if not b:
            log.error("lead %s not found", args.lead_id)
            return []
        return [b]
    bundles = []
    for lead in store.leads_by_status(["demo_queued"]):
        if args.track and (lead.get("demo_type") or lead.get("track")) != args.track:
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

    ok, failed = 0, 0
    for b in bundles:
        lead = b["lead"]
        kind = lead.get("demo_type") or lead["track"]
        brand = brand_dict(b)
        name = display_name((b.get("business") or {}).get("display_name") or brand["name"])
        slug = brand["slug"]
        print(f"\n▶ {name} · {kind} demo · {slug}.{HOST}")
        try:
            _run_builder(kind, lead["subcategory"], brand, deploy=not args.dry_run)
        except subprocess.CalledProcessError as e:
            failed += 1
            log.error("  ✗ builder failed (exit %s) for %s", e.returncode, name)
            continue
        link = f"https://{slug}.{HOST}/"
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
