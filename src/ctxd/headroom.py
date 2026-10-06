"""Headroom and pre-flight verdicts.

The window budget must come from configuration — models differ and ctxd does
not guess one. It is provided per invocation (--window) or read from a
``--config`` JSON file ({"window_tokens": N, "warn_frac": 0.5,
"block_frac": 0.9}). Without a window, headroom is reported as ``unknown`` and
never fabricated: absence of data is stated, not filled.

Verdicts, from measured usage only:
  ok       — headroom >= warn_frac
  warning  — headroom < warn_frac (proceed; plan compaction)
  blocked  — headroom < block_frac, or stale views exist with --stale-blocks
"""
from __future__ import annotations

import json

from .model import Ledger, UsageError

DEFAULT_WARN_FRAC = 0.5
DEFAULT_BLOCK_FRAC = 0.9


def load_config(path: str | None, window: int | None,
                warn_frac: float | None, block_frac: float | None) -> dict:
    cfg: dict = {"window_tokens": None, "warn_frac": None, "block_frac": None}
    if path:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise UsageError(f"config is not valid JSON: {path} ({exc})") from exc
        if not isinstance(data, dict):
            raise UsageError(f"config must be a JSON object: {path}")
        # explicit CLI args (non-None) win over file values
        for key in ("window_tokens", "warn_frac", "block_frac"):
            if key in data:
                cfg[key] = data[key]
    # CLI flags override everything
    if window is not None:
        cfg["window_tokens"] = window
    if warn_frac is not None:
        cfg["warn_frac"] = warn_frac
    if block_frac is not None:
        cfg["block_frac"] = block_frac
    # built-in defaults last
    if cfg["warn_frac"] is None:
        cfg["warn_frac"] = DEFAULT_WARN_FRAC
    if cfg["block_frac"] is None:
        cfg["block_frac"] = DEFAULT_BLOCK_FRAC
    w = cfg.get("window_tokens")
    if w is not None and (not isinstance(w, (int, float)) or w <= 0):
        raise UsageError(f"window_tokens must be a positive number, got {w!r}")
    if not 0 < cfg["warn_frac"] <= 1 or not 0 < cfg["block_frac"] <= 1:
        raise UsageError("warn_frac/block_frac must be in (0, 1]")
    if cfg["warn_frac"] > cfg["block_frac"]:
        raise UsageError("warn_frac must not exceed block_frac")
    cfg["window_tokens"] = int(w) if w is not None else None
    return cfg


def headroom(ledger: Ledger, cfg: dict) -> dict:
    """Headroom verdict for the session's final recorded context."""
    w = cfg.get("window_tokens")
    used = ledger.final_context_tokens
    if w is None:
        return {"state": "unknown", "used_tokens": used, "window_tokens": None,
                "free_tokens": None, "used_frac": None}
    used_frac = used / w
    free = max(0, w - used)
    if used_frac >= cfg["block_frac"]:
        state = "blocked"
    elif used_frac >= cfg["warn_frac"]:
        state = "warning"
    else:
        state = "ok"
    return {"state": state, "used_tokens": used, "window_tokens": int(w),
            "free_tokens": free, "used_frac": round(used_frac, 4)}


def preflight(ledger: Ledger, stale_count: int, cfg: dict,
              stale_blocks: bool) -> dict:
    """One gate a harness calls before the next tool call.

    Returns a dict; the CLI maps it to exit 0/1. Every field names its
    provenance — tokens are provider-recorded, never model claims.
    """
    h = headroom(ledger, cfg)
    reasons: list[str] = []
    verdict = "proceed"

    if h["state"] == "blocked":
        verdict = "block"
        reasons.append(
            f"measured context {h['used_tokens']} tokens is "
            f"{h['used_frac']:.0%} of the configured "
            f"{h['window_tokens']}-token window")
    elif h["state"] == "warning":
        verdict = "warn"
        reasons.append(
            f"measured context {h['used_tokens']} tokens is "
            f"{h['used_frac']:.0%} of the window; plan a compaction")

    if stale_count > 0:
        msg = (f"{stale_count} file view(s) are stale; "
               "re-read before relying on them")
        if stale_blocks:
            verdict = "block"
            reasons.append(msg + " (blocking mode)")
        else:
            if verdict == "proceed":
                verdict = "warn"
            reasons.append(msg)

    if h["state"] == "unknown" and verdict == "proceed":
        reasons.append("no window configured; headroom not checkable")

    return {
        "verdict": verdict,
        "exit": 1 if verdict == "block" else 0,
        "reasons": reasons,
        "headroom": h,
        "stale_views": stale_count,
    }
