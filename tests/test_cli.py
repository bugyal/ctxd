"""End-to-end CLI tests: real subprocess-free invocation of main()."""
import json

import pytest

from ctxd.cli import main


def test_ledger_text(session, capsys):
    rc = main(["ledger", session])
    out = capsys.readouterr().out
    assert rc == 0
    assert "peak context" in out
    assert "5,600 tokens" in out
    assert "provider-recorded usage, not model claims" in out


def test_ledger_json(session, capsys):
    rc = main(["--json", "ledger", session])
    out = capsys.readouterr().out
    assert rc == 0
    d = json.loads(out)
    assert d["peak_context_tokens"] == 5600
    assert d["final_context_tokens"] == 5600


def test_stale_text(session, capsys):
    rc = main(["stale", session])
    out = capsys.readouterr().out
    assert rc == 0
    assert "stale: 1 of 2" in out
    assert "edited later in this session" in out


def test_preflight_proceeds_low(session, capsys):
    rc = main(["--window", "100000", "preflight", session])
    out = capsys.readouterr().out
    assert rc == 0
    assert "WARN" in out          # stale view warns, headroom is fine
    assert "stale views: 1" in out


def test_preflight_blocks_on_stale_with_flag(session, capsys):
    rc = main(["--window", "100000", "preflight", session, "--stale-blocks"])
    assert rc == 1


def test_preflight_json_shape(session, capsys):
    rc = main(["--window", "100000", "--json", "preflight", session])
    out = capsys.readouterr().out
    d = json.loads(out)
    assert set(d) >= {"verdict", "exit", "reasons", "headroom", "stale_views"}
    assert d["stale_views"] == 1
    assert d["headroom"]["window_tokens"] == 100000


def test_status_line(session, capsys):
    rc = main(["--window", "100000", "status", session])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert "ctx 5,600 tok (6% of window)" in out
    assert "stale 1" in out


def test_missing_file_is_usage_error(tmp_path, capsys):
    rc = main(["ledger", str(tmp_path / "nope.jsonl")])
    err = capsys.readouterr().err
    assert rc == 2
    assert err.startswith("ctxd: no such transcript")


def test_non_jsonl_arg_is_usage_error(tmp_path, capsys):
    f = tmp_path / "x.txt"
    f.write_text("hi")
    rc = main(["ledger", str(f)])
    assert rc == 2
    assert "expected a .jsonl" in capsys.readouterr().err
