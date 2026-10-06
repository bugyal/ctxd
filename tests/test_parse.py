"""Ledger tests — the ground-truth invariant: numbers come from usage records."""
import json

from ctxd.parse import parse_session


def test_peak_is_sum_of_all_input_components(session):
    ledger, snaps, edits, claims = parse_session(session)
    # largest usage record in the fixture: turn 3
    # 2500 + 3000 + 100 = 5600 (turn 2 is 2000+3000+400 = 5400)
    assert ledger.peak_context_tokens == 5600
    assert ledger.peak_turn == 3
    assert ledger.peak_breakdown == {"input": 2500, "cache_read": 3000,
                                     "cache_creation": 100}


def test_final_is_last_usage_record(session):
    ledger, *_ = parse_session(session)
    # last record: 2500 + 3000 + 100 = 5600
    assert ledger.final_context_tokens == 5600
    assert ledger.turns[-1].index == 3


def test_four_usage_turns_found(session):
    ledger, *_ = parse_session(session)
    assert len(ledger.turns) == 4


def test_malformed_and_unknown_lines_skipped(session, capsys):
    ledger, *_ = parse_session(session)
    # the fixture carries a broken line and an unknown record type; neither dies
    assert len(ledger.turns) == 4
    err = capsys.readouterr().err
    assert "1 malformed line(s)" in err


def test_model_claims_are_collected_but_not_used(session):
    ledger, _, _, claims = parse_session(session)
    assert any("almost out of context" in c for c in claims)
    # the claim is a lie: measured usage that turn is tiny
    turn = ledger.turns[1]
    assert turn.input_tokens + turn.cache_read + turn.cache_creation == 2050
