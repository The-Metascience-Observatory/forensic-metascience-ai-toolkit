"""The shared rounding module, and the properties the nine old helpers agreed on.

Nine ad-hoc half-width helpers had accumulated across the tools. They agreed,
but nothing checked that they agreed, so a fix to one never reached the others.
This pins the shared definition and the two behaviours that were repeatedly got
wrong: precision read from a parsed float instead of the printed literal, and a
sum compared against a single cell's tolerance.
"""
import pytest

from forensic_metascience_ai_toolkit.tools import rounding as R


class TestHalfWidth:
    @pytest.mark.parametrize("decimals,expected", [
        (0, 0.5), (1, 0.05), (2, 0.005), (3, 0.0005),
    ])
    def test_matches_the_definition(self, decimals, expected):
        assert R.half_width(decimals) == pytest.approx(expected)

    def test_tolerance_is_half_width_plus_float_slack(self):
        assert R.tolerance(2) > R.half_width(2)
        assert R.tolerance(2) - R.half_width(2) < 1e-9

    def test_interval_brackets_the_printed_value(self):
        lo, hi = R.interval(71.0, 1)
        assert lo == pytest.approx(70.95)
        assert hi == pytest.approx(71.05)


class TestMatchesAtPrecision:
    def test_accepts_a_value_inside_the_printed_interval(self):
        # 0.232008 prints as .232, so a check comparing it against a reported
        # .232 must not call that a discrepancy.
        assert R.matches_at_precision(0.232008, 0.232, 3)

    def test_rejects_a_value_outside_it(self):
        assert not R.matches_at_precision(0.238, 0.232, 3)

    def test_a_boundary_value_still_matches(self):
        """Exactly one half-width away must not flip on the last bit."""
        assert R.matches_at_precision(71.05, 71.0, 1)

    @pytest.mark.parametrize("computed,reported", [(None, 1.0), (1.0, None), (None, None)])
    def test_a_missing_side_is_never_a_match(self, computed, reported):
        """An absent value is not agreement; reporting `consistent` on data the
        check never saw is the worst available failure mode."""
        assert not R.matches_at_precision(computed, reported, 2)


class TestDecimalsOfText:
    @pytest.mark.parametrize("text,expected", [
        ("71", 0), ("71.0", 1), ("71.13", 2), ("1,234.567", 3),
        ("-4.50", 2), ("0", 0), (".05", 2),
    ])
    def test_reads_the_literal(self, text, expected):
        assert R.decimals_of_text(text) == expected

    def test_unparseable_is_unknown_not_zero(self):
        assert R.decimals_of_text("n/a") is None
        assert R.decimals_of_text(None) is None

    def test_the_float_repr_trap(self):
        """This is the defect the module exists to prevent.

        A mean printed `71` is known to zero decimals, so its interval is
        +/-0.5. Reading precision from the parsed float gives `str(71.0)` ->
        one decimal and an interval ten times too tight, which manufactures
        impossibilities out of correctly-reported data.
        """
        assert R.decimals_of_text("71") == 0
        assert R.decimals_of_text(str(float("71"))) == 1  # what NOT to do


class TestDecimalsOfTextRefusesWhatItCannotRead:
    """E-notation and non-finite text have no printed decimal count.

    Counting characters after the dot in `"2.5e3"` returned 3, an interval of
    +/-0.0005 for a value whose true printed half-width is 50 -- five orders of
    magnitude TOO TIGHT, the direction that accuses. Verified before the fix:
    `matches_at_precision(2480, 2500, decimals_of_text("2.5e3"))` was False,
    although 2480 is perfectly consistent with a printed 2.5e3. And
    `float("nan")` parses, so `"nan"` returned 0 -- "printed to zero decimals"
    -- licensing a granularity verdict on a value that is not a number.
    """

    @pytest.mark.parametrize("text", ["2.5e3", "1.2e-4", "1e-5", "1.5E6"])
    def test_scientific_notation_is_unknown_precision(self, text):
        assert R.decimals_of_text(text) is None

    @pytest.mark.parametrize("text", ["nan", "NaN", "inf", "-inf", "Infinity"])
    def test_non_finite_text_is_unknown_not_zero(self, text):
        assert R.decimals_of_text(text) is None


class TestDecimalsOfValueOnTinyFloats:
    """A float whose repr is e-notation still needs a finite fallback.

    `decimals_of_text` now refuses e-notation, so `decimals_of_value` derives
    the decimal-equivalent precision from the exponent instead: 1.5e-05 is
    `0.000015`, six decimals, half-width 5e-7 -- exactly the interval either
    plausible printed form (`0.000015` or `1.5x10^-5`) asserts. Returning None
    here would crash the callers that wrap the result in `half_width` (ttest
    line 119 does exactly that with a parsed p-value).
    """

    def test_e_notation_floats_get_their_decimal_equivalent(self):
        assert R.decimals_of_value(1.5e-05) == 6
        assert R.decimals_of_value(1e-05) == 5

    def test_ordinary_floats_are_unchanged(self):
        assert R.decimals_of_value(5.0) == 0
        assert R.decimals_of_value(0.001) == 3
        assert R.decimals_of_value(0.1 + 0.2) == 1

    def test_non_finite_still_refuses(self):
        assert R.decimals_of_value(float("nan")) is None
        assert R.decimals_of_value(float("inf")) is None


class TestCoarsestDecimals:
    def test_takes_the_binding_constraint(self):
        assert R.coarsest_decimals("1.40", "1.1", "2.001") == 1

    def test_one_unknown_makes_the_comparison_unknown(self):
        """Skipping the unreadable value would report a precision the
        comparison does not actually have."""
        assert R.coarsest_decimals("1.40", "n/a") is None

    def test_no_values_is_unknown(self):
        assert R.coarsest_decimals() is None


class TestAccumulatedHalfWidth:
    def test_a_sum_inherits_every_addends_slack(self):
        """Twenty values printed to 1 dp permit the total to be off by +/-1.0.

        A fixed tolerance of 0.5 -- the constant `check_summation` used to be
        called with -- is simultaneously too loose for a short 2 dp column and
        too tight for this one, so it is wrong in both directions.
        """
        assert R.accumulated_half_width([1] * 20) == pytest.approx(1.0)
        assert R.accumulated_half_width([2, 2]) == pytest.approx(0.01)

    def test_mixed_precisions_are_summed_not_minimised(self):
        # 0.5 + 0.05, not 2 * 0.5: each addend contributes its own.
        assert R.accumulated_half_width([0, 1]) == pytest.approx(0.55)

    def test_nothing_to_add_has_no_slack(self):
        assert R.accumulated_half_width([]) == 0.0


class TestTheOldHelpersStillWork:
    """The nine call sites kept their local names; they must still resolve."""

    def test_debit(self):
        from forensic_metascience_ai_toolkit.tools.debit import _rounding_half_width
        assert _rounding_half_width(2) == R.half_width(2)

    def test_rivets(self):
        from forensic_metascience_ai_toolkit.tools.rivets import _half_width, _matches_at_precision
        assert _half_width(2) == R.half_width(2)
        assert _matches_at_precision(1.001, 1.0, 2)

    def test_grimu_imports_from_rivets(self):
        """The one pre-existing cross-module import must survive the move."""
        from forensic_metascience_ai_toolkit.tools.grimu import _half_width as gu
        assert gu(3) == R.half_width(3)

    def test_estimates(self):
        from forensic_metascience_ai_toolkit.tools.estimates import _half_width
        assert _half_width(1.40, 1.1) == R.half_width(1)

    def test_celltypes(self):
        from forensic_metascience_ai_toolkit.tools.celltypes import _dp
        assert _dp("71.0") == 1
        assert _dp("n/a") is None
