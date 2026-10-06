"""Shared types and small helpers."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field


class UsageError(Exception):
    """A user-facing CLI misuse. `main` renders it as `ctxd: <msg>`, exit 2."""


@dataclass
class Turn:
    """One assistant turn with provider-reported usage."""

    index: int                 # 0-based order among usage-bearing turns
    model: str | None
    input_tokens: int
    cache_read: int
    cache_creation: int
    output_tokens: int
    timestamp: str | None = None


@dataclass
class ReadSnapshot:
    """A file view the harness recorded the agent taking."""

    file_path: str
    content: str
    start_line: int
    num_lines: int
    total_lines: int
    record_uuid: str | None = None
    timestamp: str | None = None
    # filled by analysis:
    sha256: str = ""
    file_missing: bool = False
    changed_on_disk: bool = False
    edited_later_in_session: bool = False
    is_stale: bool = False
    reason: str = ""


@dataclass
class EditRecord:
    """A Write/Edit the session performed on a file."""

    file_path: str
    tool: str                  # "Write" | "Edit" | other
    record_uuid: str | None = None
    timestamp: str | None = None


@dataclass
class Ledger:
    """Ground-truth context ledger for one session."""

    session: str
    turns: list[Turn] = field(default_factory=list)
    peak_context_tokens: int = 0
    peak_turn: int = -1
    final_context_tokens: int = 0
    # classification of where the peak came from — provenance, not a blend:
    peak_breakdown: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "session": self.session,
            "turns": len(self.turns),
            "peak_context_tokens": self.peak_context_tokens,
            "peak_turn": self.peak_turn,
            "final_context_tokens": self.final_context_tokens,
            "peak_breakdown": self.peak_breakdown,
        }


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def iter_jsonl(path: str):
    """Yield parsed records from a .jsonl file; skip bad lines, count them."""
    bad = 0
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                bad += 1
    if bad:
        # surfaced via warnings channel in report, not an exception:
        import sys

        print(f"ctxd: warning: {bad} malformed line(s) skipped in {path}",
              file=sys.stderr)


def context_of(turn: Turn) -> int:
    """Context footprint of a turn = everything the provider counted as input.

    input_tokens already includes uncached input; cache_read/creation are parts
    of the prompt billed separately, so real prompt size is the sum. This is the
    number that fills the context window — provenance: provider usage record.
    """
    return turn.input_tokens + turn.cache_read + turn.cache_creation
