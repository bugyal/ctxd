"""Rendering: human text and machine JSON for every ctxd command."""
from __future__ import annotations

import json

from .model import Ledger, ReadSnapshot


def _fmt_tokens(n: int) -> str:
    return f"{n:,}"


def render_ledger(ledger: Ledger, cfg: dict) -> str:
    out = [f"# ctxd ledger — {ledger.session}"]
    if not ledger.turns:
        out.append("")
        out.append("No usage records found in this transcript.")
        out.append("ctxd records nothing rather than estimating.")
        return "\n".join(out)
    last = ledger.turns[-1]
    out += [
        "",
        "| turn | model | input | cache_read | cache_new | context total |",
        "|---|---|---|---|---|---|",
    ]
    show = ledger.turns if len(ledger.turns) <= 12 else \
        ledger.turns[:6] + [None] + ledger.turns[-6:]
    for t in show:
        if t is None:
            out.append(f"| … {len(ledger.turns) - 12} more … | | | | | |")
            continue
        out.append(
            f"| {t.index} | {t.model or '-'} | {_fmt_tokens(t.input_tokens)} | "
            f"{_fmt_tokens(t.cache_read)} | {_fmt_tokens(t.cache_creation)} | "
            f"{_fmt_tokens(t.input_tokens + t.cache_read + t.cache_creation)} |")
    w = cfg.get("window_tokens")
    out += [
        "",
        f"peak context   : {_fmt_tokens(ledger.peak_context_tokens)} tokens "
        f"(turn {ledger.peak_turn})",
        f"final context  : {_fmt_tokens(ledger.final_context_tokens)} tokens "
        f"(last usage record, turn {last.index})",
    ]
    if w:
        frac = ledger.final_context_tokens / w
        out.append(f"window         : {_fmt_tokens(int(w))} tokens → "
                   f"{frac:.0%} used")
    else:
        out.append("window         : not configured; headroom not checkable "
                       "(pass --window or --config)")
    out.append("")
    out.append("All counts are provider-recorded usage, not model claims.")
    return "\n".join(out)


def render_snapshots(snaps: list[ReadSnapshot]) -> str:
    out = [f"# ctxd stale-view report — {len(snaps)} file view(s) recorded"]
    if not snaps:
        out.append("")
        out.append("No file reads with recorded content in this transcript.")
        return "\n".join(out)
    stale = [s for s in snaps if s.is_stale]
    out += ["", f"stale: {len(stale)} of {len(snaps)}", ""]
    if stale:
        out += ["| file | read window | why stale |", "|---|---|---|"]
        for s in stale:
            win = (f"L{s.start_line}–{s.start_line + s.num_lines - 1}"
                   if s.num_lines else "-")
            out.append(f"| `{s.file_path}` | {win} | {s.reason} |")
        out += ["", "Re-read these before relying on their contents."]
    else:
        out.append("Every recorded view matches the file as it stands now.")
    return "\n".join(out)


def render_preflight(result: dict) -> str:
    sym = {"proceed": "PROCEED", "warn": "WARN", "block": "BLOCK",
           "unknown": "PROCEED"}[result["verdict"]]
    h = result["headroom"]
    out = [f"ctxd preflight: {sym}"]
    if h["window_tokens"] is None:
        out.append(f"  context: {_fmt_tokens(h['used_tokens'])} tokens "
                       "(measured); window not configured, headroom unknown")
    else:
        out.append(f"  context: {_fmt_tokens(h['used_tokens'])} / "
                       f"{_fmt_tokens(h['window_tokens'])} tokens "
                       f"({h['used_frac']:.0%} used), "
                       f"{_fmt_tokens(h['free_tokens'])} free")
    if result["stale_views"]:
        out.append(f"  stale views: {result['stale_views']} — re-read before "
                       "relying on them")
    for r in result["reasons"]:
        out.append(f"  - {r}")
    return "\n".join(out)


def render_json(data) -> str:
    return json.dumps(data, indent=1)
