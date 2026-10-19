"""Upstream statcheck flags p-values that are correct at their printed precision.

Found on a real paper in `high_value_pdfs_to_run_on/`: statcheck flagged 33 of
58 statistics, and 11 of those 33 (33%) reported a p that is the correct
rendering of the computed p at the number of decimals actually printed. For
example `r(51) = -0.167, p = 0.232` against a computed 0.232008.

A p printed as `.232` asserts the interval [.2315, .2325). This is the same
rounding-interval principle the GRIM family uses, applied to statcheck: a
printed number asserts an interval, not a point.

Counting those as errors matters because a raw flag count is what a reader
sees. "33 of 58 statistics are wrong" reads as an indictment; the honest figure
was 22, none of which changed a conclusion.
"""
import pytest

from metascience_agent.tools.r_wrappers import _within_printed_precision


class TestWithinPrintedPrecision:
    @pytest.mark.parametrize("raw,reported,computed", [
        ("r(51)=-0.167, p=0.232", 0.232, 0.232008),
        ("r(51)=-0.249, p=0.072", 0.072, 0.072184),
        ("r(53)=-0.198, p=0.147", 0.147, 0.147318),
        ("r(51)=-0.151, p=0.280", 0.280, 0.280460),
    ])
    def test_correct_at_printed_precision(self, raw, reported, computed):
        assert _within_printed_precision(raw, reported, computed) is True

    @pytest.mark.parametrize("raw,reported,computed", [
        ("F(1,45)=4.82, p=0.030", 0.030, 0.033330),   # rounds to .033, not .030
        ("F(1,33)=7.86, p=0.009", 0.009, 0.008400),   # rounds to .008
        ("r(41)=-0.241, p=0.102", 0.102, 0.119513),   # genuinely different
    ])
    def test_genuine_inconsistency_still_flagged(self, raw, reported, computed):
        assert _within_printed_precision(raw, reported, computed) is False

    def test_precision_comes_from_the_literal_not_the_float(self):
        """`p=.05` asserts 2 dp -- the interval [.045, .055), not a point.

        Reading it as 6 dp would shrink that interval 10,000-fold and
        manufacture a discrepancy out of correct reporting. Both .0499 and
        .0533 render as `.05` at 2 dp; .0567 does not. The SAME computed value
        printed to 3 dp as `.050` is genuinely inconsistent -- the precision the
        author chose is what sets the interval.
        """
        assert _within_printed_precision("t(28)=2.34, p=.05", 0.05, 0.0499) is True
        assert _within_printed_precision("t(28)=2.34, p=.05", 0.05, 0.0533) is True
        assert _within_printed_precision("t(28)=2.34, p=.05", 0.05, 0.0567) is False
        assert _within_printed_precision("t(28)=2.34, p=.050", 0.050, 0.0533) is False

    def test_unparseable_input_is_not_excused(self):
        """No p literal to read precision from -> do NOT silently forgive."""
        assert _within_printed_precision("t(28)=2.34", 0.05, 0.05) is False
        assert _within_printed_precision("p=0.10", None, 0.10) is False
        assert _within_printed_precision("p=0.10", 0.10, "n/a") is False
