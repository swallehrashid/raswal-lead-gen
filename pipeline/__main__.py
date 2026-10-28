"""CLI (brief §16.3).

  python -m pipeline nightly [--list-date YYYY-MM-DD] [--subcategory KEY] [--dry-run]
                             [--no-llm] [--no-render] [--max-places-calls N] [--limit N]
                             [--offline] [--no-db]
  python -m pipeline rerender --lead-id ID          (or --offline [--subcategory KEY])
  python -m pipeline redraft  --lead-id ID
  python -m pipeline generate [--lead-id ID] [--track web|content] [--limit N] [--dry-run]
  python -m pipeline cells    --subcategory KEY
  python -m pipeline usage
  python -m pipeline heartbeat
  python -m pipeline purge
  python -m pipeline gen-seed
  python -m pipeline export-mock
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from pipeline.settings import Env, MissingSecrets, install_secret_redaction, load_config


def _date(s: str) -> date:
    return date.fromisoformat(s)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m pipeline", description="Raswal lead generator")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("nightly", help="build the list for the next send day")
    n.add_argument("--list-date", type=_date)
    n.add_argument("--subcategory")
    n.add_argument("--dry-run", action="store_true", help="≤5 Places calls, no Supabase writes, CSV to out/")
    n.add_argument("--no-llm", action="store_true", help="skip Gemini; use deterministic fallback messages")
    n.add_argument("--no-render", action="store_true", help="skip teaser rendering")
    n.add_argument("--max-places-calls", type=int)
    n.add_argument("--limit", type=int, help="enrich at most N candidates (default enrich_limit)")
    n.add_argument("--offline", action="store_true", help="use tests/fixtures for every external call")
    n.add_argument("--no-db", action="store_true",
                   help="dry run without Supabase reads (no suppression/contacted checks!)")

    r = sub.add_parser("rerender", help="re-render a lead's teaser (or all fixture samples with --offline)")
    r.add_argument("--lead-id")
    r.add_argument("--offline", action="store_true")
    r.add_argument("--subcategory")

    d = sub.add_parser("redraft", help="re-draft a lead's message variants")
    d.add_argument("--lead-id", required=True)
    d.add_argument("--no-llm", action="store_true")

    g = sub.add_parser("generate", help="build + deploy demos for queued leads, write links back")
    g.add_argument("--lead-id", help="one lead (any status); default: all status=demo_queued")
    g.add_argument("--track", choices=["web", "content"], help="only this demo track")
    g.add_argument("--limit", type=int, help="process at most N queued leads")
    g.add_argument("--dry-run", action="store_true", help="build locally; no deploy, no DB writes")

    c = sub.add_parser("cells", help="show search-cell rotation state")
    c.add_argument("--subcategory", required=True)
    c.add_argument("--offline", action="store_true")

    sub.add_parser("usage", help="API usage this month")
    sub.add_parser("heartbeat", help="one trivial Supabase query (keeps the free project awake)")
    sub.add_parser("purge", help="retention purge (also runs at the end of every nightly)")
    sub.add_parser("gen-seed", help="regenerate supabase/seed.sql from config")
    m = sub.add_parser("export-mock", help="build the dashboard mock dataset from fixtures")
    m.add_argument("--no-render", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%H:%M:%S")
    env = Env.from_environ()
    install_secret_redaction(env)
    cfg = load_config()
    try:
        if args.cmd == "nightly":
            from pipeline.nightly import NightlyOptions, run_nightly
            result = run_nightly(cfg, env, NightlyOptions.from_args(args))
            return 0 if result.status in ("ok", "skipped") else 1
        if args.cmd == "rerender":
            from pipeline.commands import rerender
            return rerender(cfg, env, args)
        if args.cmd == "redraft":
            from pipeline.commands import redraft
            return redraft(cfg, env, args)
        if args.cmd == "generate":
            from pipeline.generate import generate
            return generate(cfg, env, args)
        if args.cmd == "cells":
            from pipeline.commands import show_cells
            return show_cells(cfg, env, args)
        if args.cmd == "usage":
            from pipeline.commands import show_usage
            return show_usage(cfg, env)
        if args.cmd == "heartbeat":
            from pipeline.commands import heartbeat
            return heartbeat(cfg, env)
        if args.cmd == "purge":
            from pipeline.commands import purge
            return purge(cfg, env)
        if args.cmd == "gen-seed":
            from pipeline.seed import write_seed
            print(f"wrote {write_seed(cfg)}")
            return 0
        if args.cmd == "export-mock":
            from pipeline.mock_export import export_mock
            return export_mock(cfg, env, args)
    except MissingSecrets as e:
        print(str(e), file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
