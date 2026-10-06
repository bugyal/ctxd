"""Pre-flight gating: verdicts, exit codes, config handling."""
import json

import pytest

from ctxd.headroom import load_config, preflight
from ctxd.model import Ledger, Turn, UsageError, context_of


def mk_ledger(final):
    t = Turn(index=0, model="m", input_tokens=final, cache_read=0,
             cache_creation=0, output_tokens=0)
    return Ledger(session="s", turns=[t], peak_context_tokens=final,
                  peak_turn=0, final_context_tokens=final)


CFG = {"window_tokens": 10000, "warn_frac": 0.5, "block_frac": 0.9}


def test_low_usage_proceeds():
    r = preflight(mk_ledger(1000), 0, CFG, stale_blocks=False)
    assert r["verdict"] == "proceed" and r["exit"] == 0


def test_warning_band_warns_but_exits_zero():
    r = preflight(mk_ledger(6000), 0, CFG, stale_blocks=False)
    assert r["verdict"] == "warn" and r["exit"] == 0
    assert "60% of the window" in r["reasons"][0]


def test_blocked_band_blocks():
    r = preflight(mk_ledger(9500), 0, CFG, stale_blocks=False)
    assert r["verdict"] == "block" and r["exit"] == 1


def test_no_window_is_unknown_never_fabricated():
    r = preflight(mk_ledger(999999), 0, {"window_tokens": None,
                                         "warn_frac": 0.5, "block_frac": 0.9},
                  stale_blocks=False)
    assert r["headroom"]["state"] == "unknown"
    assert r["verdict"] == "proceed"
    assert any("no window configured" in x for x in r["reasons"])


def test_stale_views_warn_by_default_block_on_flag():
    r = preflight(mk_ledger(1000), 2, CFG, stale_blocks=False)
    assert r["verdict"] == "warn" and r["exit"] == 0
    r2 = preflight(mk_ledger(1000), 2, CFG, stale_blocks=True)
    assert r2["verdict"] == "block" and r2["exit"] == 1


def test_the_hallucinated_refusal_case():
    """Evidence 1wy840o: model refuses at 25% real usage. ctxd must say proceed."""
    # 25% of a 200k window with a model CLAIMING it is out of context
    r = preflight(mk_ledger(50_000), 0,
                  {"window_tokens": 200_000, "warn_frac": 0.5,
                   "block_frac": 0.9}, stale_blocks=False)
    assert r["verdict"] == "proceed" and r["exit"] == 0
    assert r["headroom"]["used_frac"] == 0.25


def test_config_file_and_cli_precedence(tmp_path):
    cfg_file = tmp_path / "ctxd.json"
    cfg_file.write_text(json.dumps(
        {"window_tokens": 5000, "warn_frac": 0.4, "block_frac": 0.8}))
    cfg = load_config(str(cfg_file), None, None, None)
    assert cfg["window_tokens"] == 5000 and cfg["warn_frac"] == 0.4
    # CLI flag wins over file
    cfg2 = load_config(str(cfg_file), 9000, None, None)
    assert cfg2["window_tokens"] == 9000


def test_bad_config_is_usage_error(tmp_path):
    bad = tmp_path / "c.json"
    bad.write_text("{nope")
    with pytest.raises(UsageError):
        load_config(str(bad), None, None, None)
    with pytest.raises(UsageError):
        load_config(None, -5, None, None)
    with pytest.raises(UsageError):
        load_config(None, None, 0.9, 0.5)  # warn > block


def test_context_helper_sums_components():
    t = Turn(index=0, model="m", input_tokens=10, cache_read=20,
             cache_creation=30, output_tokens=5)
    assert context_of(t) == 60   # output tokens are not context
