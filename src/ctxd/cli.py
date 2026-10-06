"""ctxd CLI.

Subcommands:
  ledger <session.jsonl>      ground-truth context ledger from usage records
  stale <session.jsonl>       stale file-view report (hash vs disk + session edits)
  preflight <session.jsonl>   harness gate: exit 0 proceed / exit 1 block
  status <session.jsonl>      one-line summary for a status line

Global flags: --window, --config, --json, and for stale/preflight:
--no-disk (transcript-only mode), --root (relocate checked paths),
--stale-blocks (stale views block, not just warn).
"""
from __future__ import annotations

import argparse
import sys

from . import __version__
from .headroom import load_config, preflight
from .model import UsageError
from .parse import parse_session
from .report import (render_json, render_ledger, render_preflight,
                     render_snapshots)
from .stale import analyse_snapshots


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ctxd",
        description="Agent stale-context detection: ground-truth ledger, "
                    "stale file-view detection, pre-flight gating.")
    p.add_argument("--version", action="version",
                   version=f"ctxd {__version__}")
    p.add_argument("--window", type=int, default=None, metavar="N",
                   help="context window size in tokens (required for "
                        "headroom math; never guessed)")
    p.add_argument("--config", default=None, metavar="FILE",
                   help="JSON config: {window_tokens, warn_frac, block_frac}")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_session(sp):
        sp.add_argument("session", help="Claude Code session .jsonl path")
        sp.add_argument("--no-disk", action="store_true",
                        help="skip on-disk checks (transcript-only)")
        sp.add_argument("--root", default=None,
                        help="relocate recorded absolute paths under this root")
        return sp

    add_session(sub.add_parser("ledger", help="context ledger from usage records"))

    sp = add_session(sub.add_parser("stale", help="stale file-view report"))
    sp.add_argument("--stale-blocks", action="store_true",
                    help="(with preflight) stale views block instead of warn")

    sp = add_session(sub.add_parser("preflight", help="harness gate"))
    sp.add_argument("--stale-blocks", action="store_true",
                    help="stale views block instead of warn")

    add_session(sub.add_parser("status", help="one-line summary"))
    return p


def _load(session: str, args):
    if not session.endswith(".jsonl"):
        raise UsageError(f"expected a .jsonl session transcript, got: {session}")
    import os

    if not os.path.isfile(session):
        raise UsageError(f"no such transcript: {session}")
    ledger, snaps, edits, _claims = parse_session(session)
    analyse_snapshots(snaps, edits, check_disk=not args.no_disk,
                      root=args.root)
    return ledger, snaps


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        cfg = load_config(args.config, args.window, None, None)
        ledger, snaps = _load(args.session, args)
    except UsageError as exc:
        print(f"ctxd: {exc}", file=sys.stderr)
        return 2

    stale_n = len([s for s in snaps if s.is_stale])

    if args.cmd == "ledger":
        if args.json:
            d = ledger.as_dict()
            d["window_tokens"] = cfg.get("window_tokens")
            print(render_json(d))
        else:
            print(render_ledger(ledger, cfg))
        return 0

    if args.cmd == "stale":
        if args.json:
            print(render_json({
                "session": ledger.session,
                "views": len(snaps),
                "stale": stale_n,
                "items": [{
                    "file_path": s.file_path,
                    "start_line": s.start_line,
                    "num_lines": s.num_lines,
                    "sha256": s.sha256,
                    "stale": s.is_stale,
                    "edited_later_in_session": s.edited_later_in_session,
                    "changed_on_disk": s.changed_on_disk,
                    "file_missing": s.file_missing,
                    "reason": s.reason,
                } for s in snaps],
            }))
        else:
            print(render_snapshots(snaps))
        return 0

    if args.cmd == "preflight":
        result = preflight(ledger, stale_n, cfg,
                           stale_blocks=args.stale_blocks)
        if args.json:
            print(render_json(result))
        else:
            print(render_preflight(result))
        return result["exit"]

    if args.cmd == "status":
        h_state = "n/a"
        used = f"{ledger.final_context_tokens:,}"
        if cfg.get("window_tokens"):
            frac = ledger.final_context_tokens / cfg["window_tokens"]
            h_state = f"{frac:.0%}"
        line = (f"ctx {used} tok "
                f"({h_state} of window) | views {len(snaps)} | "
                f"stale {stale_n}")
        print(line)
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
