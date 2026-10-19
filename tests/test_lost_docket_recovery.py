"""Pins for what happens when a producer files a highlights document.

MEASURED 2026-08-22 at v1.9.0 over ten papers on grok-4.6: THREE lost their
entire tool docket after 47, 70 and 78 forensic tool calls, and the bounded
retry was empty on all three. It is not truncation -- on
`10.1186--s13550-023-00956-9` the final assistant message is 3,726 characters
of complete, well-formed JSON with three findings and stub metadata
(`coverage: {stats_found: 0, tools_run: []}`, `anatomy: {studies: [],
variables: [], tests: []}`). The model did the work over 19 turns and then
filed a summary.

Also pinned here: the 16% of a run's spend that the stage table could not see,
and the token totals the usage table printed as zero.
"""

from __future__ import annotations

import pytest

from metascience_agent import agent as A
from metascience_agent.parallel import (_add_ledger_only_attempts,
                                        _coverage_with_ledger_fallback,
                                        _producer_retry_correction,
                                        _usage_totals)


def _ledger(*names, surface="forensic_mcp"):
    return [{"tool_short": n, "surface": surface} for n in names]


class TestCoverageIsRebuiltFromTheLedger:
    def test_a_lost_docket_recovers_the_tools_it_actually_ran(self):
        cov = _coverage_with_ledger_fallback(
            {"coverage": {"stats_found": 0, "tools_run": []}},
            _ledger("check_table", "grim_check", "check_table", "statcheck"))
        assert cov["tools_run"] == ["check_table", "grim_check", "statcheck"]
        assert cov["tools_run_source"] == "ledger"

    def test_the_producers_own_coverage_is_never_overwritten(self):
        """A recovered list is a fallback, not an improvement on a real one."""
        cov = _coverage_with_ledger_fallback(
            {"coverage": {"stats_found": 96, "tools_run": ["extract_xml"]}},
            _ledger("check_table", "grim_check"))
        assert cov["tools_run"] == ["extract_xml"]
        assert "tools_run_source" not in cov

    def test_harness_and_builtin_calls_are_not_forensic_coverage(self):
        """`search_tool` and `Read` are how the model got to the paper, not
        checks it ran on it. 271 of one run's calls were `search_tool`."""
        cov = _coverage_with_ledger_fallback(
            {"coverage": {"tools_run": []}},
            _ledger("search_tool", surface="harness")
            + _ledger("Read", surface="builtin_allowed")
            + _ledger("grim_check"))
        assert cov["tools_run"] == ["grim_check"]

    def test_stats_found_is_never_invented(self):
        """How many statistics a paper contains is not something a ledger
        knows; only the tool list is recoverable."""
        cov = _coverage_with_ledger_fallback(
            {"coverage": {"stats_found": 0, "tools_run": []}},
            _ledger("grim_check"))
        assert cov["stats_found"] == 0

    def test_an_empty_ledger_changes_nothing(self):
        cov = _coverage_with_ledger_fallback({"coverage": {"tools_run": []}}, [])
        assert cov == {"tools_run": []}


class TestTheRetryIsToldWhyItIsRetrying:
    """A retry that re-sends a byte-identical prompt is a coin flip, and it
    lost 3 of 3 on 2026-08-22. The adjudicator retry, given the rejection text
    in the same release, recovered 2 of 2."""

    def test_a_truncated_docket_is_told_what_was_missing_not_that_it_was_invalid(self):
        msg = _producer_retry_correction(
            {}, {"findings": [1, 2, 3]}, 70,
            schema_gate_error=False, truncated_docket=True)
        assert "70 forensic tool call(s)" in msg
        assert "3 finding(s)" in msg
        assert "It parsed, so nothing rejected it" in msg, (
            "telling the model its output was invalid would be false here")
        assert "including the ones that PASSED" in msg

    def test_a_schema_gate_error_is_quoted_verbatim(self):
        msg = _producer_retry_correction(
            {"schema_errors": ["model output was not valid JSON: EOF while "
                               "parsing a string at line 1 column 5700"]},
            None, 47, schema_gate_error=True, truncated_docket=False)
        assert "EOF while parsing a string at line 1 column 5700" in msg
        assert "It parsed" not in msg

    def test_a_schema_error_with_no_detail_still_retries_usefully(self):
        msg = _producer_retry_correction(
            {}, None, 47, schema_gate_error=True, truncated_docket=False)
        assert "RETRY" in msg and "LAST message" in msg


class TestTheRunCanAccountForItself:
    def test_token_and_wall_totals_come_back_summed(self):
        """`output tokens: 0` was printed for a run that produced ~1.3M."""
        got = _usage_totals({
            "tool_agent": {"input_tokens": 100, "output_tokens": 40843,
                           "wall_seconds": 640.0,
                           "cache_read_input_tokens": 2038656},
            "adjudicator": {"output_tokens": 20391, "wall_seconds": 311.6},
        })
        assert got["output_tokens"] == 61234
        assert got["cache_read_input_tokens"] == 2038656
        assert got["total_wall_seconds"] == 951.6

    def test_a_discarded_retry_is_counted_because_it_was_billed(self):
        got = _usage_totals({
            "tool_agent": {"output_tokens": 100, "wall_seconds": 1.0},
            "tool_agent_retry": {"output_tokens": 900, "wall_seconds": 2.0},
        })
        assert got["output_tokens"] == 1000, "the retry was paid for"

    def test_no_stages_reports_no_runtime_rather_than_zero(self):
        """`None` suppresses the row; `0.0` would print a false measurement."""
        assert _usage_totals({})["total_wall_seconds"] is None

    def test_junk_reports_unknown_rather_than_a_short_sum(self):
        """This runs inside the return statement of a finished paper, so it
        must not crash -- but a partial total would look like a measurement.
        Unreachable in practice; every field is an int we wrote."""
        got = _usage_totals({"a": None, "b": {"output_tokens": "?"},
                             "c": {"output_tokens": 5}})
        assert got["output_tokens"] is None
        assert got["total_wall_seconds"] is None
        assert "usage_totals_error" in got


@pytest.fixture
def fresh_ledger():
    """A private spend ledger for this test, per `reset_spend`'s contract."""
    A.reset_spend()
    yield
    A.reset_spend()


class TestEveryBilledAttemptReachesTheStageTable:
    """16% OF A RUN'S SPEND WAS INVISIBLE: $1.82 of $11.57 over ten papers,
    $0.85 on one, because a retry returns one attempt and the other is dropped
    -- money included. The total was right and the decomposition was not.

    Read off `record_spend`'s ledger rather than plumbed through the retry
    paths. That deleted six assignment sites AND covers two retries `parallel`
    never sees: the legacy `stage2_editorial` and the tool agent's internal one.
    """

    @staticmethod
    def _stage(cost, out_tokens=0, wall=1.0):
        return {"cost_usd": cost, "output_tokens": out_tokens,
                "wall_seconds": wall, "input_tokens": 0,
                "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}

    def test_a_discarded_retry_becomes_its_own_row(self, fresh_ledger):
        A.record_spend("tool_agent", self._stage(0.31, 100))
        A.record_spend("tool_agent_retry", self._stage(0.85, 900))
        meta = {"tool_agent": {"cost_usd": 0.31, "output_tokens": 100}}
        _add_ledger_only_attempts(meta)
        assert set(meta) == {"tool_agent", "tool_agent_retry"}
        assert meta["tool_agent_retry"]["cost_usd"] == 0.85
        assert meta["tool_agent_retry"]["source"] == "spend_ledger"

    def test_a_stage_already_in_the_table_is_never_overwritten(self, fresh_ledger):
        """The real stage meta carries messages, coverage and a parse path; the
        ledger row carries money. The richer record wins."""
        A.record_spend("tool_agent", self._stage(0.31))
        meta = {"tool_agent": {"cost_usd": 0.31, "output_parse_path": "json_schema"}}
        _add_ledger_only_attempts(meta)
        assert meta["tool_agent"]["output_parse_path"] == "json_schema"
        assert "source" not in meta["tool_agent"]

    def test_two_attempts_under_one_label_are_SUMMED_not_overwritten(self, fresh_ledger):
        """`tool_agent_retry` is emitted by BOTH
        `_run_stage_requiring_forensic_tools` and `_retry_if_empty`. Keying by
        name would let one silently overwrite the other -- an undercount
        presented as a decomposition."""
        A.record_spend("tool_agent_retry", self._stage(0.40, 400, wall=10.0))
        A.record_spend("tool_agent_retry", self._stage(0.25, 250, wall=5.0))
        meta = {}
        _add_ledger_only_attempts(meta)
        row = meta["tool_agent_retry"]
        assert row["cost_usd"] == pytest.approx(0.65)
        assert row["output_tokens"] == 650
        assert row["wall_seconds"] == pytest.approx(15.0)
        assert row["n_attempts"] == 2

    def test_the_discarded_attempt_reaches_the_token_totals(self, fresh_ledger):
        """The whole chain: ledger -> stages_meta -> the cost row."""
        A.record_spend("tool_agent", self._stage(0.31, 100))
        A.record_spend("tool_agent_retry", self._stage(0.85, 900))
        meta = {"tool_agent": self._stage(0.31, 100)}
        _add_ledger_only_attempts(meta)
        assert _usage_totals(meta)["output_tokens"] == 1000

    def test_record_spend_carries_the_token_fields_at_all(self, fresh_ledger):
        """The field that made the ledger sufficient. Without it this whole
        substitution would silently undercount tokens."""
        A.record_spend("adjudicator", self._stage(0.11, 20391))
        row, = A.spend_so_far()["stages"]
        for f in A._SPEND_USAGE_FIELDS:
            assert f in row, f
        assert row["output_tokens"] == 20391
