"""Parse Claude Code session transcripts (.jsonl) into ledger + snapshots.

Format grounded on this machine's real transcripts (~/.claude/projects), not
invented:

- assistant records: ``message.role == "assistant"``, ``message.model``,
  ``message.usage`` with ``input_tokens``, ``cache_read_input_tokens``,
  ``cache_creation_input_tokens``, ``output_tokens``.
- read snapshots: user-side ``toolUseResult`` of shape
  ``{"type":"text","file":{filePath,content,numLines,startLine,totalLines}}``,
  linked to the triggering assistant call via ``sourceToolAssistantUUID``.
- edits: assistant ``tool_use`` records with name Write/Edit and a
  ``file_path`` in the input.

Several schema shapes are tolerated because transcripts on this machine carry
more than one (tool_use ids ``call_*`` vs ``toolu_*``, content as list or
string). Unrecognised records are skipped, never guessed.
"""
from __future__ import annotations

from .model import (EditRecord, Ledger, ReadSnapshot, Turn, context_of,
                    iter_jsonl, sha256_text)

_READ_TOOLS = {"Read", "View", "view", "read"}
_EDIT_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


def _assistant_texts(rec) -> list[str]:
    msg = rec.get("message") or {}
    content = msg.get("content")
    texts = []
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                t = part.get("text")
                if isinstance(t, str):
                    texts.append(t)
    elif isinstance(content, str):
        texts.append(content)
    return texts


def parse_usage(rec) -> Turn | None:
    """Extract a Turn from an assistant record carrying provider usage."""
    msg = rec.get("message") or {}
    usage = msg.get("usage")
    if not isinstance(usage, dict):
        return None

    def num(key):
        v = usage.get(key)
        return v if isinstance(v, (int, float)) and v >= 0 else 0

    return Turn(
        index=0,  # renumbered by caller
        model=msg.get("model") if isinstance(msg.get("model"), str) else None,
        input_tokens=int(num("input_tokens")),
        cache_read=int(num("cache_read_input_tokens")),
        cache_creation=int(num("cache_creation_input_tokens")),
        output_tokens=int(num("output_tokens")),
        timestamp=rec.get("timestamp") if isinstance(rec.get("timestamp"), str) else None,
    )


def _tool_uses(rec) -> list[tuple[str, dict, str | None]]:
    """Yield (tool_name, input, tool_use_id) from an assistant record."""
    msg = rec.get("message") or {}
    content = msg.get("content")
    out = []
    if isinstance(content, list):
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "tool_use":
                continue
            name = part.get("name")
            inp = part.get("input")
            tid = part.get("id")
            if isinstance(name, str) and isinstance(inp, dict):
                out.append((name, inp, tid if isinstance(tid, str) else None))
    return out


def _read_snapshot_from_tool_result(rec) -> ReadSnapshot | None:
    """Extract a Read snapshot from a user-side toolUseResult record."""
    if rec.get("type") != "user":
        return None
    tur = rec.get("toolUseResult")
    if not isinstance(tur, dict) or tur.get("type") != "text":
        return None
    fi = tur.get("file")
    if not isinstance(fi, dict):
        return None
    path = fi.get("filePath")
    content = fi.get("content")
    if not isinstance(path, str) or not isinstance(content, str):
        return None

    def int_or(key, default=0):
        v = fi.get(key)
        return v if isinstance(v, int) and v >= 0 else default

    return ReadSnapshot(
        file_path=path,
        content=content,
        start_line=int_or("startLine"),
        num_lines=int_or("numLines"),
        total_lines=int_or("totalLines"),
        record_uuid=rec.get("uuid") if isinstance(rec.get("uuid"), str) else None,
        timestamp=rec.get("timestamp") if isinstance(rec.get("timestamp"), str) else None,
    )


def parse_session(path: str) -> tuple[Ledger, list[ReadSnapshot], list[EditRecord],
                                     list[str]]:
    """Parse one transcript. Returns (ledger, snapshots, edits, model_claims).

    ``model_claims`` collects assistant *text* that asserts something about the
    context window (matches /context|token|window|context left/i). These are
    never used for numbers — they are surfaced so the report can contrast what
    the model claimed with what the provider recorded.
    """
    ledger = Ledger(session=path)
    snapshots: list[ReadSnapshot] = []
    edits: list[EditRecord] = []
    model_claims: list[str] = []
    turn_no = 0
    import re

    claim_re = re.compile(r"\b(context|token|window)\b", re.IGNORECASE)

    for rec in iter_jsonl(path):
        if not isinstance(rec, dict):
            continue

        if rec.get("type") == "assistant":
            turn = parse_usage(rec)
            if turn is not None:
                turn.index = turn_no
                turn_no += 1
                ledger.turns.append(turn)
            for text in _assistant_texts(rec):
                if claim_re.search(text):
                    model_claims.append(text)

            for name, inp, _tid in _tool_uses(rec):
                fp = inp.get("file_path")
                if name in _EDIT_TOOLS and isinstance(fp, str):
                    edits.append(EditRecord(
                        file_path=fp,
                        tool=name,
                        timestamp=rec.get("timestamp")
                        if isinstance(rec.get("timestamp"), str) else None,
                    ))

        snap = _read_snapshot_from_tool_result(rec)
        if snap is not None:
            snapshots.append(snap)

    # ledger aggregates — from usage records only
    for i, t in enumerate(ledger.turns):
        t.index = i
    if ledger.turns:
        for t in ledger.turns:
            c = context_of(t)
            if c > ledger.peak_context_tokens:
                ledger.peak_context_tokens = c
                ledger.peak_turn = t.index
                ledger.peak_breakdown = {
                    "input": t.input_tokens,
                    "cache_read": t.cache_read,
                    "cache_creation": t.cache_creation,
                }
        ledger.final_context_tokens = context_of(ledger.turns[-1])

    for s in snapshots:
        s.sha256 = sha256_text(s.content)
    return ledger, snapshots, edits, model_claims
