"""Every tool call ends in exactly one recorded state, and they sum.

A CONSERVATION LAW, not a statistic. `coverage()` already asserts a GROUP is in
exactly one state; this asserts the same of a CALL. The difference matters: a
call is something WE did, so an unbalanced ledger is always our defect and never
a fact about the paper.

WHY IT EXISTS. Measured 2026-08-20 over the nine registers of the eleven-paper
run: `n_checks_attached` was ZERO on every paper while 27-53 calls each reported
no matchable value. The verdicts had been computed and saved, and were dropped
at a silent parse. Nothing failed. No test went red. It was found weeks later by
someone probing a register by hand.

Nearly every defect that session found is a violation of this law -- 826 prose
values with no number, 265 table cells discarded by XML precedence, 143 silent
groups, the zero attachments. Each was a thing produced that ended in no state
at all.

THE LAW DOES NOT BALANCE TODAY, and that is recorded rather than tuned away.
Over the nine registers: 723 calls, 262 joined, 346 unmatched, **115
unaccounted**, and three papers with NEGATIVE residuals -- proof that two
counters count the same call. A boolean I adjusted until it read True would
have taught its reader nothing.
"""

import pytest

from forensic_metascience_ai_toolkit.values import call_ledger_balance


def _calls(n, unreadable=0, name="mcp__x__grim_check"):
    out = [{"name": name} for _ in range(n - unreadable)]
    out += [{"name": name, "result_unreadable": "truncated"}
            for _ in range(unreadable)]
    return out


class TestTheLawItself:
    def test_a_balanced_ledger_is_reported_balanced(self):
        r = call_ledger_balance(
            {"n_per_cell_checks_joined": 6, "n_calls_with_no_matchable_value": 4},
            _calls(10))
        assert r["n_unaccounted"] == 0 and r["accounted"] is True

    def test_a_call_in_no_state_shows_as_a_positive_residual(self):
        r = call_ledger_balance(
            {"n_per_cell_checks_joined": 6, "n_calls_with_no_matchable_value": 1},
            _calls(10))
        assert r["n_unaccounted"] == 3 and r["accounted"] is False

    def test_double_counting_shows_as_a_NEGATIVE_residual(self):
        """Measured on three real registers. A negative number is the only
        honest way to say two counters describe the same call."""
        r = call_ledger_balance(
            {"n_per_cell_checks_joined": 8, "n_calls_with_no_matchable_value": 8},
            _calls(10))
        assert r["n_unaccounted"] == -6

    def test_unreadable_is_a_reason_not_a_third_bucket(self):
        """A call whose result could not be parsed cannot be joined either, so
        it is already inside `n_unmatched`. Counting it again over-counted every
        paper on this law's first run."""
        r = call_ledger_balance(
            {"n_per_cell_checks_joined": 4, "n_calls_with_no_matchable_value": 6},
            _calls(10, unreadable=6))
        assert r["n_unaccounted"] == 0
        assert r["n_unreadable"] == 6
        assert r["unreadable_because"] == {"truncated": 6}


class TestWhatCounts:
    def test_extractors_are_not_checks(self):
        """`extract_pdf` and `get_table` fetch inputs; they produce no verdict
        and must not be expected to join to a value."""
        calls = _calls(4) + [{"name": "mcp__x__extract_pdf"},
                             {"name": "mcp__x__get_table"},
                             {"name": "StructuredOutput"}]
        r = call_ledger_balance(
            {"n_per_cell_checks_joined": 4, "n_calls_with_no_matchable_value": 0},
            calls)
        assert r["n_calls"] == 4 and r["n_unaccounted"] == 0

    def test_check_table_CALLS_count_as_joined(self):
        r = call_ledger_balance(
            {"n_check_table_calls_joined": 3, "n_per_cell_checks_joined": 2,
             "n_calls_with_no_matchable_value": 5}, _calls(10))
        assert r["n_joined"] == 5 and r["n_unaccounted"] == 0

    def test_attached_ROWS_are_not_counted_as_calls(self):
        """This test used to assert the opposite, and the assertion was wrong.

        `n_checks_attached` counts attached RESULT ROWS. One `check_table` call
        carries many, so adding it to a law about CALLS counted one call up to a
        dozen times -- which is where this law's three NEGATIVE residuals came
        from on its first real measurement. The fixture agreed with the code
        because I wrote both, and only the corpus disagreed.
        """
        r = call_ledger_balance(
            {"n_checks_attached": 12, "n_refusals_attached": 4,
             "n_check_table_calls_joined": 1,
             "n_calls_with_no_matchable_value": 9}, _calls(10))
        assert r["n_joined"] == 1 and r["n_unaccounted"] == 0

    def test_every_recorded_state_is_in_the_sum(self):
        """A call that was recorded as unmatched or ambiguous did not vanish."""
        r = call_ledger_balance(
            {"n_per_cell_checks_joined": 2, "n_per_cell_checks_unmatched": 5,
             "n_per_cell_checks_ambiguous": 3}, _calls(10))
        assert r["n_unaccounted"] == 0 and r["n_unmatched"] == 8

    def test_a_fetch_is_not_a_check(self):
        """`Read` and `extract_pdf` never computed a verdict, so they are not in
        the denominator -- and both ends of the law read the same predicate off
        the same key, which is the defect that made this law unbalanced."""
        calls = _calls(4) + [{"tool": "mcp__x__extract_pdf"}, {"tool": "Read"}]
        r = call_ledger_balance({"n_calls_with_no_matchable_value": 4}, calls)
        assert r["n_calls"] == 4 and r["n_unaccounted"] == 0

    def test_the_note_says_whose_defect_it_is(self):
        r = call_ledger_balance({}, _calls(3))
        assert "never a fact about the paper" in r["note"]


class TestTheRatchet:
    """Pinned so the residual cannot grow unnoticed. Lower it when the join is
    fixed; never raise it to make a red suite green."""

    #: MEASURED 2026-08-20: **0 of 700 calls**, on all nine registers, with no
    #: paper negative. It was 145 of 723 (20.1% absolute, 115 signed) hours
    #: earlier, and the gap was never about the paper: the law summed two of the
    #: four states the register actually recorded, counted attached ROWS as
    #: though they were calls, and read its own filter off a key (`name`) that
    #: none of the 819 real calls carries.
    #:
    #: PINNED AT ZERO ON PURPOSE. This is a conservation law, so any residual is
    #: our bookkeeping defect and there is no honest value above zero to allow.
    #: A new tool whose calls end in no state SHOULD turn this red the day it
    #: lands. Never raise it to make a red suite green -- find the state that
    #: went unrecorded, and record it.
    MAX_UNACCOUNTED_SHARE = 0.0

    def test_the_corpus_residual_has_not_grown(self):
        import json
        import pathlib

        P = pathlib.Path("/mnt/c/Users/gregs/Dropbox/agent_for_forensic_metascience_papers"
                         "/cerebrolysin_papers/prioritized_cerebrolysin_papers")
        regs = list(P.glob("*/forensic_review/value_register.json")) if P.is_dir() else []
        if len(regs) < 5:
            pytest.skip("the eleven-paper corpus is not on this machine")
        calls = unacct = 0
        for f in regs:
            c = (json.loads(f.read_text(encoding="utf-8")).get("calls") or {})
            calls += c.get("n_calls") or 0
            unacct += abs(c.get("n_unaccounted") or 0)
        assert calls, "no calls recorded across the corpus"
        share = unacct / calls
        assert share <= self.MAX_UNACCOUNTED_SHARE, (
            f"{unacct} of {calls} calls ({share:.1%}) end in no recorded state, "
            f"above the pinned {self.MAX_UNACCOUNTED_SHARE:.0%}. Every one is a "
            "verdict computed and then lost.")
