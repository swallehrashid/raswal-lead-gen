"""End-to-end check of the whole ads pipeline, offline and without touching the live database or the live site.

  .venv/bin/python scripts/e2e.py [--skip-render]       (takes ~10-15 minutes: it renders real videos)

1. nightly (offline fixtures, the full daily mix) → 20 land + 10 agency leads, valid messages, one teaser JPEG each
2. a "yes" from one land and one agency lead → `pipeline generate` builds each pilot plan page (3 videos each) locally
3. both pages are opened in a phone-sized browser and scrolled end to end: no console errors, every chapter reached,
   the video sources load, the Start button links to the outreach number
Writes docs/E2E_LAST_RUN.md and exits non-zero on the first failed check."""

from __future__ import annotations

import argparse
import io
import re
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
PIPELINE = Path("/home/swalleh/Projects/raswal-pipeline")
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(("PASS  " if ok else "FAIL  ") + name + (f"  [{detail}]" if detail else ""), flush=True)
    if not ok:
        write_report()
        sys.exit(1)


def write_report() -> None:
    lines = ["# Last end-to-end run", "", f"Run at {time.strftime('%Y-%m-%d %H:%M')} by `scripts/e2e.py`.", "", "| Check | Result | Detail |", "|---|---|---|"]
    lines += [f"| {n} | {'✅' if ok else '❌'} | {d} |" for n, ok, d in RESULTS]
    (ROOT / "docs" / "E2E_LAST_RUN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-render", action="store_true", help="reuse the last built pages instead of rendering videos")
    a = ap.parse_args()

    from PIL import Image

    from pipeline.generate import generate
    from pipeline.nightly import NightlyOptions, run_nightly
    from pipeline.settings import Env, load_config
    from pipeline.store import MemoryStore

    cfg = load_config()
    out = Path(tempfile.mkdtemp(prefix="e2e_"))
    store = MemoryStore()

    # ---- 1 · nightly
    t0 = time.time()
    r = run_nightly(cfg, Env(), NightlyOptions(list_date=date(2026, 11, 2), dry_run=False, offline=True, no_render=False, out_dir=out, store=store))
    leads = list(store.tables["leads"].values())
    fin = [x for x in leads if x["status"] == "shortlisted"]
    check("nightly runs the daily mix", r.status == "ok" and len(fin) == 30, f"{len(fin)} finalists in {time.time() - t0:.0f}s")
    by = {s: sum(1 for x in fin if x["subcategory"] == s) for s in ("land_developers", "property_agency")}
    check("20 land + 10 agency", by == {"land_developers": 20, "property_agency": 10}, str(by))
    check("every lead is an ads lead with an angle", all(x["track"] == "ads" and x["brand"]["angle"] in "ABC" for x in leads))
    msgs = [v["message"] for x in fin for v in x["message_variants"]]
    check("60 opening messages carry the core promise", len(msgs) == 60 and all("enquiries on your WhatsApp" in m and "KES 5,000" in m and "free 7-day pilot" in m for m in msgs))
    check("no message says 'inquiries', 'guaranteed' or a link", not any(re.search(r"inquir|guarantee|https?://", m, re.I) for m in msgs))
    check("message lengths are 380-700", all(380 <= len(m) <= 700 for m in msgs), f"{min(map(len, msgs))}-{max(map(len, msgs))}")
    sizes = []
    for x in fin:
        data = store.files.get(x["teaser_path"]) if x.get("teaser_path") else None
        if data:
            im = Image.open(io.BytesIO(data))
            sizes.append((im.size, len(data)))
    check("one 1080x1350 teaser per lead, each <= 350 KB", len(sizes) == 30 and all(s == (1080, 1350) and n <= 350 * 1024 for s, n in sizes),
          f"{len(sizes)} teasers, max {max(n for _, n in sizes) // 1024} KB")

    # ---- 2 · yes → generate
    land = next(x for x in fin if x["subcategory"] == "land_developers")
    agency = next(x for x in fin if x["subcategory"] == "property_agency")
    for x in (land, agency):
        x.update(status="demo_queued", demo_type="ads")
    store.tables["settings"]["outreach_whatsapp"] = {"key": "outreach_whatsapp", "value": "254114129809"}
    built: dict[str, Path] = {}
    import pipeline.generate as gen
    gen.build_store = lambda *a_, **k: store                      # the in-memory store stands in for Supabase
    pages_dir = PIPELINE / "out"
    for x in (land, agency):
        slug = x["slug"]
        t1 = time.time()
        if not a.skip_render:
            rc = generate(cfg, Env(), SimpleNamespace(lead_id=x["id"], track=None, limit=None, dry_run=True, final=False, offer=None))
            check(f"generate builds the pilot plan for {x['subcategory']}", rc == 0, f"{time.time() - t1:.0f}s")
        page = pages_dir / slug / "pilot"
        built[x["subcategory"]] = page
        check(f"{x['subcategory']} page exists with 3 videos", all((page / "ads" / str(i) / "video.mp4").exists() for i in (1, 2, 3)) and (page / "index.html").exists())
        tot = sum(f.stat().st_size for f in page.rglob("*") if f.is_file()) / 1e6
        first = (sum(f.stat().st_size for f in page.rglob("*") if f.is_file() and f.suffix != ".mp4")) / 1e6
        check(f"{x['subcategory']} page weight within budget", tot <= 12 and first <= 1.5, f"{tot:.1f} MB total, {first:.2f} MB before videos")

    # ---- 3 · open both pages like a client would
    from playwright.sync_api import sync_playwright
    for sub, page in built.items():
        srv = subprocess.Popen([sys.executable, "-m", "http.server", "8788", "--directory", str(page.parent), "--bind", "127.0.0.1"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.2)
        try:
            with sync_playwright() as p:
                b = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
                ctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
                pg = ctx.new_page()
                errs: list[str] = []
                pg.on("pageerror", lambda e: errs.append(str(e)))
                pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
                pg.goto("http://127.0.0.1:8788/pilot/", wait_until="networkidle")
                pg.wait_for_timeout(1200)
                H = pg.evaluate("document.documentElement.scrollHeight")
                reached = set()
                for f in [i / 60 for i in range(61)]:
                    pg.evaluate(f"window.scrollTo(0,{int((H - 844) * f)})")
                    pg.wait_for_timeout(300)
                    reached.add(pg.evaluate("document.getElementById('chNow').textContent"))
                panels = pg.evaluate("document.querySelectorAll('.ch').length")
                strip_moved = pg.evaluate("getComputedStyle(document.getElementById('strip')).transform")
                href = pg.evaluate("document.getElementById('startBtn').href")
                vids = pg.evaluate("Array.from(document.querySelectorAll('video')).map(v => v.currentSrc || v.src)")
                b.close()
            check(f"{sub} page: no console errors", not errs, "; ".join(errs[:3]))
            check(f"{sub} page: every chapter reached by scrolling", len(reached) >= panels, f"{len(reached)} of {panels} chapters seen")
            check(f"{sub} page: scrolling moves the story sideways", strip_moved not in ("none", ""), strip_moved[:40])
            check(f"{sub} page: Start button opens WhatsApp with the outreach number", href.startswith("https://wa.me/254114129809?text="), href[:60])
            check(f"{sub} page: the 3 ad videos are wired", sum(1 for v in vids if v.endswith(".mp4")) >= 1 and len(vids) == 3, f"{len(vids)} <video> elements")
        finally:
            srv.terminate()
    write_report()
    print("\nALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
