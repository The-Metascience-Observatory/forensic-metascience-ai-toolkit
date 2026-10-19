"""A forensic tool must never accuse the paper on non-finite input.

A NaN or +/-inf statistic is never a reported value -- it comes from OUR
failures (a cell that would not parse, a division by a zero SD, an overflow).
The MCP/registry surface is protected by the measured-value gate in
`ToolSpec.call`; these tests pin the SAME guarantee on the RAW functions, which
are reachable directly (CLI commands, tool-to-tool calls, tests). Before the
guard, `grim_test_percentage`/`check_sd_range`/`debit_test` returned `impossible`
(a false accusation) on a NaN, and `grim_test`/`grimmer_test`/`recalc_chi_squared`
raised on the int() conversion (a crash a batch loop could swallow into a false
all-clear).
"""

import math

import pytest

from metascience_agent.tools.severity import refuse_if_nonfinite
from metascience_agent.tools.grim import grim_test, grim_test_percentage
from metascience_agent.tools.sd_checks import check_sd_range, grimmer_test
from metascience_agent.tools.debit import debit_test
from metascience_agent.tools.chi_squared import recalc_chi_squared
from metascience_agent.tools.rivets import rivets_anova
from metascience_agent.tools.heuristics import flag_uninformative_stat

NAN = float("nan")
INF = float("inf")


class TestRefuseIfNonfinite:
    def test_finite_scalars_pass(self):
        assert refuse_if_nonfinite(mean=5.5, n=30, sd=1.2) is None

    def test_none_and_bool_are_not_nonfinite(self):
        # Optional params arrive as None; a bool is not a statistic.
        assert refuse_if_nonfinite(n=None, flag=True) is None

    def test_nan_scalar_refuses(self):
        r = refuse_if_nonfinite(mean=NAN, n=30)
        assert r is not None and r["severity"] == "indeterminate"
        assert r["applicable"] is False
        assert "mean" in r["error"]

    def test_inf_scalar_refuses(self):
        assert refuse_if_nonfinite(sd=INF)["severity"] == "indeterminate"

    def test_nonfinite_inside_a_list_refuses(self):
        r = refuse_if_nonfinite(means=[1.0, NAN, 2.0])
        assert r is not None and r["severity"] == "indeterminate"

    def test_names_every_bad_input(self):
        r = refuse_if_nonfinite(mean=NAN, sd=INF, n=30)
        assert "mean" in r["error"] and "sd" in r["error"]


class TestRawFunctionsRefuseNonfinite:
    """Each of these returned `impossible` or crashed before the guard."""

    @pytest.mark.parametrize("call", [
        lambda: grim_test(NAN, 30, 1, 7, 2, "likert"),
        lambda: grim_test(INF, 30, 1, 7, 2, "likert"),
        lambda: grim_test_percentage(NAN, 40, 1, "proportion"),
        lambda: grimmer_test(NAN, 1.0, 30, 1, 7, data_type="likert"),
        lambda: grimmer_test(5.0, INF, 30, 1, 7, data_type="likert"),
        lambda: check_sd_range(NAN, 0, 10, 30),
        lambda: check_sd_range(INF, 0, 10, 30),
        lambda: check_sd_range(5.0, 0, NAN, 30),
        lambda: debit_test(0.5, NAN, 50, data_type="binary"),
        lambda: recalc_chi_squared([[NAN, 5], [5, 5]]),
        lambda: rivets_anova([1.6, NAN, 1.6], [0.07, 0.07, 0.07], [30, 30, 30]),
    ])
    def test_returns_indeterminate_never_a_claim(self, call):
        r = call()
        assert r["severity"] == "indeterminate", (
            f"a non-finite input produced {r['severity']!r} -- a claim about the "
            "paper from our own garbage"
        )

    def test_internal_caller_no_longer_false_accuses(self):
        # THE house-failure repro: a single NaN mean (a failed extraction of one
        # cell) drove flag_uninformative_stat -> rivets_anova to
        # `highly_suspicious` ("the test cannot have produced that p"). It must
        # now decline.
        r = flag_uninformative_stat(
            means=[1.6, NAN, 1.6], sds=[0.07, 0.07, 0.07], ns=[30, 30, 30],
            reported_p=0.5,
        )
        assert r["severity"] == "indeterminate"


class TestFiniteInputsUnaffected:
    """The guard must not blunt a genuine detection on real numbers."""

    def test_real_grim_impossibility_still_flags(self):
        # 5.51 * 30 = 165.3 is not an integer sum.
        assert grim_test(5.51, 30, 1, 7, 2, "likert",
                         discreteness_source="stated")["severity"] == "impossible"

    def test_real_sd_impossibility_still_flags(self):
        # SD 9 exceeds the max ~5.09 attainable on a 0-10 range at n=30.
        # `highly_suspicious` at the default (assumed) bounds -- that is the
        # bound_source cap (test_sd_range_bounds.py), not the nonfinite guard;
        # stating the bounds restores `impossible`.
        assert check_sd_range(9.0, 0, 10, 30)["severity"] == "highly_suspicious"
        assert check_sd_range(9.0, 0, 10, 30,
                              bound_source="stated")["severity"] == "impossible"

    def test_consistent_case_still_consistent(self):
        """2 dp, not 1. At n = 30 and 1 dp GRIM has NO discriminating power, so
        the old form of this assertion was pinning a check that could not fail
        as though it had passed -- the guard under test is unaffected either
        way, but the fixture should not be a dead check."""
        assert grim_test(5.0, 30, 1, 7, 2, "likert")["severity"] == "consistent"
