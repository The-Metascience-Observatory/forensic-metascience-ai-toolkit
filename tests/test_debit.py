"""Tests for DEBIT (binary mean/SD consistency)."""

import math

import pytest

from metascience_agent.tools.debit import (
    debit_test,
    debit_test_batch,
    _expected_sample_sd,
)


class TestExpectedSampleSD:
    """Verify the closed-form sample SD against an explicit construction."""

    def test_against_explicit_data(self):
        # 5 ones and 5 zeros (n=10), Bessel-corrected sample SD.
        data = [1] * 5 + [0] * 5
        n = len(data)
        mean = sum(data) / n
        var = sum((x - mean) ** 2 for x in data) / (n - 1)
        expected = math.sqrt(var)
        assert _expected_sample_sd(5, 10) == pytest.approx(expected, rel=1e-12)

    def test_extremes_zero(self):
        # All ones or all zeros → SD = 0.
        assert _expected_sample_sd(0, 100) == 0.0
        assert _expected_sample_sd(100, 100) == 0.0

    def test_n_lt_2(self):
        # Degenerate; we return 0 rather than divide by zero.
        assert _expected_sample_sd(1, 1) == 0.0


class TestDEBITConsistent:
    """Cases that should pass DEBIT."""

    def test_balanced_binary(self):
        # 50/50 split with n=100 → SD ≈ 0.5025...
        result = debit_test(mean=0.50, sd=0.50, n=100)
        assert result["consistent"] is True
        assert result["severity"] == "consistent"
        assert 50 in result["matching_k_values"]

    def test_low_proportion(self):
        # k=5 of 100 → mean=0.05, expected SD = sqrt(5*95/(100*99)) ≈ 0.2190
        # Reported 0.22 (2dp) should match (0.2190 rounds to 0.22).
        result = debit_test(mean=0.05, sd=0.22, n=100)
        assert result["consistent"] is True

    def test_three_dp_precision(self):
        # k=10 of 100, mean=0.100, SD ≈ 0.3015 → matches at 3dp too.
        result = debit_test(mean=0.100, sd=0.302, n=100, decimals_mean=3, decimals_sd=3)
        assert result["consistent"] is True


class TestDEBITImpossible:
    """Cases that should fail DEBIT."""

    def test_regnerus_2012_example(self):
        """Heathers' Regnerus 2012 example: mean=0.01, SD=0.75 is impossible.

        Maximum binary SD is 0.5 (at p=0.5); SD=0.75 is impossible for ANY
        binary variable, let alone one with mean 0.01.
        """
        result = debit_test(mean=0.01, sd=0.75, n=1000)
        assert result["consistent"] is False
        assert result["severity"] == "impossible"

    def test_sd_above_max(self):
        # Maximum sample SD for binary data approaches 0.5 (with Bessel ~0.5025
        # at n=100). SD=0.6 with any mean is impossible.
        result = debit_test(mean=0.5, sd=0.6, n=100)
        assert result["consistent"] is False

    def test_mean_outside_unit_interval(self):
        result = debit_test(mean=1.5, sd=0.3, n=100)
        assert result["consistent"] is False
        assert "outside [0, 1]" in result["explanation"]

    def test_grim_failure_subsumed(self):
        # n=30 cannot produce a mean of 0.501 (granularity 1/30 ≈ 0.0333).
        # The candidate k for mean=0.50 is only 15; 15/30 = 0.500 exactly,
        # which rounds to 0.50 not 0.501. So with reported 0.501 to 3dp:
        result = debit_test(mean=0.501, sd=0.5, n=30, decimals_mean=3)
        assert result["consistent"] is False
        assert "GRIM" in result["explanation"] or "k" in result["explanation"]


class TestDEBITBatch:
    def test_mixed_batch(self):
        rows = [
            {"label": "var_a", "mean": 0.50, "sd": 0.50, "n": 100, "decimals_mean": 2, "decimals_sd": 2},  # OK
            {"label": "var_b", "mean": 0.01, "sd": 0.75, "n": 1000, "decimals_mean": 2, "decimals_sd": 2},  # impossible
            {"label": "var_c", "mean": 0.05, "sd": 0.22, "n": 100, "decimals_mean": 2, "decimals_sd": 2},  # OK
        ]
        result = debit_test_batch(rows)
        assert result["n_rows"] == 3
        assert result["n_impossible"] == 1
        assert result["n_consistent"] == 2
        # 1/3 impossible meets the highly_suspicious threshold (>= len/3).
        assert result["severity"] in ("suspicious", "highly_suspicious")

    def test_all_consistent_batch(self):
        rows = [
            {"label": "a", "mean": 0.50, "sd": 0.50, "n": 100, "decimals_mean": 2, "decimals_sd": 2},
            {"label": "b", "mean": 0.20, "sd": 0.40, "n": 100, "decimals_mean": 2, "decimals_sd": 2},
        ]
        result = debit_test_batch(rows)
        assert result["severity"] == "consistent"


class TestBatchNeverLaundersARefusalIntoAClearVerdict:
    """`consistent` must mean "checked and fine", never "nothing was checked".

    The batch aggregate used to report `severity: consistent` whenever no row
    came back `impossible` -- including the case where EVERY row was refused and
    nothing was evaluated at all. The registry declares `data_type` with default
    None while the function default was "binary", so an ordinary
    `debit_check_batch(rows=...)` call hit exactly that path: six rows in, six
    `indeterminate` rows out, and a green verdict on a table DEBIT never looked
    at. The single-cell tool returned a visible `indeterminate` on the same
    input, so the batch form was the dangerous one.
    """

    ROWS = [
        {"label": "a", "mean": 0.50, "sd": 0.50, "n": 100, "decimals_mean": 2, "decimals_sd": 2},
        {"label": "b", "mean": 0.30, "sd": 0.46, "n": 100, "decimals_mean": 2, "decimals_sd": 2},
        {"label": "c", "mean": 0.20, "sd": 0.40, "n": 100, "decimals_mean": 2, "decimals_sd": 2},
    ]

    def test_batch_with_no_declared_data_type_does_not_report_consistent(self):
        """The exact MCP path: `data_type` unset, so the registry passes None."""
        from metascience_agent import registry as R

        spec = {s.name: s for s in R.SPECS}["debit_check_batch"]
        result = spec.call({"rows": [dict(r) for r in self.ROWS]})

        assert all(r["severity"] == "indeterminate" for r in result["results"])
        assert result["severity"] == "indeterminate"
        assert result["applicable"] is False

    def test_batch_agrees_with_the_single_cell_tool_on_the_same_input(self):
        from metascience_agent import registry as R

        specs = {s.name: s for s in R.SPECS}
        row = self.ROWS[0]
        single = specs["debit_check"].call(
            {"mean": row["mean"], "sd": row["sd"], "n": row["n"]}
        )
        batch = specs["debit_check_batch"].call({"rows": [dict(row)]})
        assert single["severity"] == batch["severity"] == "indeterminate"

    def test_all_rows_refused_is_indeterminate(self):
        result = debit_test_batch([dict(r) for r in self.ROWS], data_type="continuous")
        assert result["severity"] == "indeterminate"

    def test_empty_batch_is_indeterminate(self):
        """Zero rows evaluated is zero rows evaluated."""
        assert debit_test_batch([])["severity"] == "indeterminate"

    def test_unevaluated_rows_are_counted_not_implied(self):
        """The count must be visible, not inferable from sums that fail to add up."""
        rows = [
            {"label": "ok", "mean": 0.50, "sd": 0.50, "n": 100, "decimals_mean": 2, "decimals_sd": 2},
            {"label": "too_small", "mean": 0.50, "sd": 0.50, "n": 1, "decimals_mean": 2, "decimals_sd": 2},   # n < 2 guard
            {"label": "not_binary", "mean": 5.51, "sd": 1.20, "n": 30, "decimals_mean": 2, "decimals_sd": 2},  # mean outside [0,1]
        ]
        result = debit_test_batch(rows)
        assert result["n_rows"] == 3
        assert result["n_indeterminate"] == 2
        assert result["n_evaluated"] == 1
        assert result["n_consistent"] == 1
        # One row was checked and it was fine, so the aggregate may clear -- but
        # the two rows that were never checked are stated, not hidden.
        assert result["severity"] == "consistent"

    def test_escalation_fraction_is_taken_over_evaluated_rows(self):
        """6 impossible out of 6 evaluated is a pattern, whatever the table's size.

        Dividing by all 30 submitted rows gives a threshold of 10 and hides it.
        """
        rows = (
            [{"mean": 0.30, "sd": 0.30, "n": 50, "decimals_mean": 2, "decimals_sd": 2}] * 6          # impossible
            + [{"mean": 0.30, "sd": 0.46, "n": 1, "decimals_mean": 2, "decimals_sd": 2}] * 24        # n < 2 -> refused
        )
        result = debit_test_batch(rows)
        assert result["n_evaluated"] == 6
        assert result["n_impossible"] == 6
        assert result["severity"] == "highly_suspicious"

    def test_a_lone_impossible_row_still_does_not_escalate(self):
        """The evaluated-row denominator must not re-introduce small-table noise."""
        rows = [
            {"mean": 0.30, "sd": 0.30, "n": 50, "decimals_mean": 2, "decimals_sd": 2},   # impossible
            {"mean": 0.30, "sd": 0.46, "n": 50, "decimals_mean": 2, "decimals_sd": 2},   # consistent
            {"mean": 0.50, "sd": 0.51, "n": 40, "decimals_mean": 2, "decimals_sd": 2},   # consistent
        ]
        assert debit_test_batch(rows)["severity"] == "suspicious"
