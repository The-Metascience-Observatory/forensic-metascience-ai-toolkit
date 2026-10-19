"""`extraction_verified` verifies the VALUE. The bound comes from the LABEL.

`check_statistic_bounds` reaches `impossible` when `extraction_verified` is set,
explaining that "the extraction was verified against the paper's own text, so
this is not a misreading on our side". That is true of the value and says
nothing about the label -- and only the label supplies the bound. Where a label
is genuinely used for a less-bounded quantity, an honest paper was accused at
the toolkit's highest severity.
"""

from __future__ import annotations

import pytest

from metascience_agent.tools.bounds import check_statistic_bounds as check


def _sev(value, measure, verified=True):
    return check(value=value, measure=measure,
                 extraction_verified=verified)["severity"]


class TestHonestValuesAreNoLongerImpossible:
    @pytest.mark.parametrize("value, measure, what", [
        (-35.2, "percentage", "a percent DECREASE from baseline"),
        (-8.0, "percent", "a percent decrease"),
        (248.0, "percent", "a percent INCREASE"),
        (150.0, "percentage", "a percent increase over 100"),
    ])
    def test_a_percent_change_is_not_an_impossible_share(self, value, measure, what):
        assert _sev(value, measure) == "suspicious", what

    def test_a_negative_r_squared_may_be_an_adjusted_one(self):
        assert _sev(-0.021, "r_squared") == "suspicious"

    def test_adjusted_r_squared_is_its_own_measure_and_passes_clean(self):
        """It subtracts a penalty for parameters and is negative whenever a
        model fits worse than the mean -- ordinary, and printed as-is by every
        major package. It used to alias onto `r_squared`."""
        for alias in ("adjusted_r_squared", "adj_r2", "adjusted_r2", "r2_adj"):
            assert _sev(-0.021, alias) == "consistent", alias

    def test_the_cap_reports_rather_than_going_silent(self):
        r = check(value=248.0, measure="percent", extraction_verified=True)
        assert r["consistent"] is False
        assert r["label_is_ambiguous"] is True
        assert "percent CHANGE" in r["innocent_reading"]
        assert "confirm which quantity" in r["explanation"]


class TestGenuineViolationsKeepTheirVerdict:
    """The cap must not become "stop checking"."""

    @pytest.mark.parametrize("value, measure", [
        (-1.4, "pearson_r"), (1.4, "pearson_r"),
        (1.3, "p_value"), (-0.2, "p_value"),
        (1.2, "kappa"), (1.5, "auc"), (1.9, "cronbach_alpha"),
        (-3.0, "variance"), (-1.0, "sd"),
    ])
    def test_an_unambiguous_label_still_reaches_impossible(self, value, measure):
        assert _sev(value, measure) == "impossible"

    def test_direction_matters_for_r_squared(self):
        """Below 0 is ambiguous (adjusted R-squared); above 1 is impossible for
        adjusted and unadjusted alike."""
        assert _sev(-0.021, "r_squared") == "suspicious"
        assert _sev(1.4, "r_squared") == "impossible"
        assert _sev(1.4, "adjusted_r_squared") == "impossible"

    def test_an_in_bounds_value_is_still_consistent(self):
        assert _sev(0.42, "percentage") == "consistent"
        assert _sev(0.8, "r_squared") == "consistent"

    def test_without_extraction_verified_nothing_reaches_impossible(self):
        """Unchanged behaviour: the pre-existing guard still governs."""
        assert _sev(-1.4, "pearson_r", verified=False) != "impossible"
