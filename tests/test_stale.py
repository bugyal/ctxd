"""Stale-view tests: both signals, independently and together."""
import os

from ctxd.parse import parse_session
from ctxd.stale import analyse_snapshots


def _load(session, check_disk=True):
    ledger, snaps, edits, _ = parse_session(session)
    analyse_snapshots(snaps, edits, check_disk=check_disk)
    return snaps


def test_edited_later_in_session_is_stale(session, tree):
    snaps = _load(session)
    app = [s for s in snaps if s.file_path.endswith("app.py")][0]
    assert app.edited_later_in_session is True
    assert app.is_stale is True
    assert "edited later in this session" in app.reason


def test_fresh_view_not_flagged(session, tree):
    snaps = _load(session)
    util = [s for s in snaps if s.file_path.endswith("util.py")][0]
    assert util.is_stale is False
    assert util.reason == ""


def test_disk_change_stales_without_session_edit(session, tree):
    # util.py matches the disk now; change the disk and re-check
    snaps = _load(session)
    util = [s for s in snaps if s.file_path.endswith("util.py")][0]
    assert util.changed_on_disk is False
    with open(tree["util"], "w") as fh:
        fh.write("a\nb\nHELPER()\nd\ne\n")
    try:
        snaps2 = _load(session)
        util2 = [s for s in snaps2 if s.file_path.endswith("util.py")][0]
        assert util2.changed_on_disk is True
        assert util2.edited_later_in_session is False
        assert util2.is_stale is True
        assert "differs from the file on disk" in util2.reason
    finally:
        with open(tree["util"], "w") as fh:
            fh.write("a\nb\nhelper()\nd\ne\n")


def test_partial_read_compares_its_own_window(session, tree):
    # util.py snapshot is lines 3..3 of a 5-line file; changing line 1 must NOT
    # stale it, changing line 3 must
    snaps = _load(session)
    util = [s for s in snaps if s.file_path.endswith("util.py")][0]
    assert (util.start_line, util.num_lines) == (3, 1)
    with open(tree["util"], "w") as fh:
        fh.write("CHANGED\nb\nhelper()\nd\ne\n")
    try:
        snaps2 = _load(session)
        util2 = [s for s in snaps2 if s.file_path.endswith("util.py")][0]
        assert util2.changed_on_disk is False   # window still matches
    finally:
        with open(tree["util"], "w") as fh:
            fh.write("a\nb\nhelper()\nd\ne\n")


def test_missing_file_is_stale(session, tree):
    with open(tree["util"], "w") as fh:
        fh.write("a\nb\nhelper()\nd\ne\n")
    os.unlink(tree["util"])
    try:
        snaps = _load(session)
        util = [s for s in snaps if s.file_path.endswith("util.py")][0]
        assert util.file_missing is True
        assert util.is_stale is True
        assert "no longer exists" in util.reason
    finally:
        with open(tree["util"], "w") as fh:
            fh.write("a\nb\nhelper()\nd\ne\n")


def test_no_disk_mode_uses_session_signal_only(session):
    snaps = _load(session, check_disk=False)
    app = [s for s in snaps if s.file_path.endswith("app.py")][0]
    assert app.is_stale is True            # session edit signal still fires
    util = [s for s in snaps if s.file_path.endswith("util.py")][0]
    assert util.is_stale is False
    assert util.changed_on_disk is False   # never checked
