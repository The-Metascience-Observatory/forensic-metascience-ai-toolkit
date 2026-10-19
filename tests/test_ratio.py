"""Nothing in the toolkit verified a division, and a cost-utility paper is one.

MEASURED: a secondary cost-effectiveness analysis printed all three columns of
its central table -- incremental cost, incremental QALYs, and the resulting
ICER -- and the sweep filed "Table 2 Deterministic ICER column (ICER = cost
increment / QALY increment) -- no tool performs ratio/division verification"
under `not_checked`. Worked by hand, the three rows implied three different
incremental costs where there can only be one, and none of them matched the
figure the paper stated in its own methods. That was the paper's headline
result and the pipeline skipped it for want of an operator.
"""
import pytest

from metascience_agent.tools.ratio import check_ratio


# The published table: incremental cost EUR 408 (Methods 2.2), and three ICERs
# whose QALY increments are printed in the same rows.
CARS = [
    ("Bayesian posterior", 0.010, 26981),
    ("Ordinal",            0.014, 18788),
    ("Standard gamble",    0.015, 20618),
]
DECS = dict(decimals_numerator=0, decimals_denominator=3, decimals_ratio=0)


class TestTheCaseThatMotivatedIt:
    @pytest.mark.parametrize("label,qaly,icer", CARS)
    def test_no_row_reproduces_its_own_icer(self, label, qaly, icer):
        r = check_ratio(numerator=408, denominator=qaly, reported_ratio=icer,
                        description=f"ICER ({label})", **DECS)
        assert r["consistent"] is False
        assert r["severity"] == "suspicious"
        assert r["failure_mode"] == "ratio_not_reproducible"

    def test_each_row_implies_a_different_denominator(self):
        """The load-bearing output. An incremental cost cannot depend on which
        utility model you chose, so three rows implying three different ones is
        the contradiction -- far more legible than three separate failures."""
        implied = [
            check_ratio(numerator=408, denominator=q, reported_ratio=i, **DECS)
            ["implied_denominator"]
            for _, q, i in CARS
        ]
        assert len({round(x, 4) for x in implied}) == 3
        for got, (_, printed, _) in zip(implied, CARS):
            assert abs(got - printed) > 1e-4

    def test_a_ratio_that_reconciles_passes(self):
        r = check_ratio(numerator=408, denominator=0.015, reported_ratio=27200,
                        **DECS)
        assert r["consistent"] is True
        assert r["severity"] == "consistent"


class TestPrecisionIsRequiredNotGuessed:
    """A quotient's slack depends on the denominator's MAGNITUDE as well as
    both precisions, so there is no safe default: guessing either clears every
    ratio or accuses on rounding alone."""

    @pytest.mark.parametrize("omit", ["decimals_numerator",
                                      "decimals_denominator",
                                      "decimals_ratio"])
    def test_missing_precision_refuses(self, omit):
        kw = dict(DECS)
        kw.pop(omit)
        r = check_ratio(numerator=408, denominator=0.014,
                        reported_ratio=18788, **kw)
        assert r["severity"] == "indeterminate"
        assert r["consistent"] is None
        assert omit.replace("decimals_", "") in r["error"]

    def test_negative_precision_refuses(self):
        kw = dict(DECS, decimals_ratio=-1)
        r = check_ratio(numerator=408, denominator=0.014,
                        reported_ratio=18788, **kw)
        assert r["severity"] == "indeterminate"

    def test_the_window_widens_with_a_small_denominator(self):
        """Same precisions, smaller denominator, wider attainable interval --
        the reason a fixed tolerance cannot work here."""
        big = check_ratio(numerator=2.0, denominator=0.5, reported_ratio=4.0,
                          decimals_numerator=1, decimals_denominator=1,
                          decimals_ratio=1)
        small = check_ratio(numerator=2.0, denominator=0.05, reported_ratio=40.0,
                            decimals_numerator=1, decimals_denominator=2,
                            decimals_ratio=1)
        wb = big["attainable_ratio_interval"]
        ws = small["attainable_ratio_interval"]
        assert (ws[1] - ws[0]) > (wb[1] - wb[0])


class TestItRefusesRatherThanJudges:
    def test_zero_denominator(self):
        r = check_ratio(numerator=1.0, denominator=0.0, reported_ratio=5.0,
                        **DECS)
        assert r["severity"] == "indeterminate"
        assert "undefined" in r["error"]

    def test_a_denominator_whose_interval_spans_zero(self):
        """0.0 at 1 dp could be anything in [-0.05, 0.05], so the quotient is
        unbounded. A refusal, never a pass."""
        r = check_ratio(numerator=5.0, denominator=0.02, reported_ratio=250.0,
                        decimals_numerator=1, decimals_denominator=1,
                        decimals_ratio=0)
        assert r["severity"] == "indeterminate"
        assert "unbounded" in r["error"]

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), None,
                                     "408", True])
    def test_non_finite_or_non_numeric_input(self, bad):
        r = check_ratio(numerator=bad, denominator=0.014,
                        reported_ratio=18788, **DECS)
        assert r["severity"] == "indeterminate"
        assert "not a finite number" in r["error"]


class TestSeverityIsCapped:
    def test_never_reaches_impossible(self):
        """Ratios are routinely computed from unrounded intermediates a paper
        never shows, so an irreproducible one is a question, not fabrication."""
        r = check_ratio(numerator=1.0, denominator=1.0, reported_ratio=999.0,
                        decimals_numerator=1, decimals_denominator=1,
                        decimals_ratio=1)
        assert r["severity"] == "suspicious"
        assert r["severity"] != "impossible"

    def test_the_explanation_names_the_implied_value(self):
        r = check_ratio(numerator=408, denominator=0.014,
                        reported_ratio=18788, **DECS)
        assert "0.0217" in r["explanation"] or "0.021716" in r["methodology"]
