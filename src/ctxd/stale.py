"""Stale file-view detection.

A snapshot is **stale** when the file the agent saw is not the file that exists
now. Two independent signals, both tested:

1. **edited-later-in-session** — the same transcript contains a Write/Edit to
   that path after the read. Detectable from the transcript alone; this is the
   77.8% class from the OpenHands study (agent edits a file it has an open view
   of, keeps reasoning over the old view).
2. **changed-on-disk** — the current file content hashes differently from the
   recorded snapshot. Grounded against the filesystem at check time, so a file
   changed by a tool, another process, or a later session is caught too.

Content comparison is on the snapshot's own line window, so a partial read
(offset/limit) is compared against the same lines of the current file. A file
that no longer exists is reported as missing, not silently "not stale" — a
deleted file invalidates every view of it.
"""
from __future__ import annotations

import os

from .model import EditRecord, ReadSnapshot, sha256_text


def _ordering_key(ts: str | None, fallback: int) -> tuple:
    # timestamps are ISO strings from the same harness, comparable as strings;
    # records without one order by transcript position (fallback index).
    if ts:
        return (1, ts, fallback)
    return (0, "", fallback)


def analyse_snapshots(snapshots: list[ReadSnapshot],
                      edits: list[EditRecord],
                      check_disk: bool = True,
                      root: str | None = None) -> None:
    """Fill staleness fields on each snapshot, in place."""
    edit_times: dict[str, list[tuple]] = {}
    for i, e in enumerate(edits):
        edit_times.setdefault(e.file_path, []).append(
            _ordering_key(e.timestamp, i))

    for i, snap in enumerate(snapshots):
        edited = False
        for key in edit_times.get(snap.file_path, []):
            if key > _ordering_key(snap.timestamp, i):
                edited = True
                break
        snap.edited_later_in_session = edited

        if check_disk:
            path = os.path.join(root, snap.file_path) if root else snap.file_path
            if not os.path.isfile(path):
                snap.file_missing = True
            else:
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as fh:
                        lines = fh.readlines()
                except OSError:
                    snap.file_missing = True
                else:
                    current = "".join(lines[snap.start_line - 1:
                                            snap.start_line - 1 + snap.num_lines])
                    snap.changed_on_disk = sha256_text(current) != snap.sha256

        snap.is_stale = snap.edited_later_in_session or snap.changed_on_disk \
            or snap.file_missing
        if snap.file_missing:
            snap.reason = "file no longer exists on disk"
        elif snap.edited_later_in_session and snap.changed_on_disk:
            snap.reason = "edited later in this session and differs on disk now"
        elif snap.edited_later_in_session:
            snap.reason = "edited later in this session"
        elif snap.changed_on_disk:
            snap.reason = "differs from the file on disk now"


def stale_of(snapshots: list[ReadSnapshot]) -> list[ReadSnapshot]:
    return [s for s in snapshots if s.is_stale]
