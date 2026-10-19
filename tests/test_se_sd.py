"""Tests for SD/SE confusion check."""

import math

import pytest

from metascience_agent.tools.se_sd import check_sd_or_se, _max_sd_from_range


class TestMaxSDFromRange:
    """Verify the SD-ceiling formula matches sd_checks behaviour."""

    def test_no_n_uses_range_over_2(self):
        assert _max_sd_from_range(0, 100, None) == pytest.approx(50.0)

    def test_with_n_uses_the_attainable_ceiling(self):
        """(range/2)·sqrt(n/(n-1)) -- half the points at each extreme.

        This previously asserted `range·sqrt((n-1)/(4n))`, the RECIPROCAL
        correction, which sits BELOW a genuinely attainable SD: for n=20 on
        [0,100] the arrangement (10 at 0, 10 at 100) has SD 51.2989 while the
        old formula claimed a 48.7340 ceiling. Being a tautological test of the
        implementation, it locked the bug in -- the same failure mode as the
        GRIMMER expectation recorded in CLAUDE.md.
        """
        import statistics

        n = 20
        expected = 100 / 2 * math.sqrt(n / (n - 1))
        assert _max_sd_from_range(0, 100, n) == pytest.approx(expected)
        # the ceiling must be genuinely attainable, not merely self-consistent
        attainable = statistics.stdev([0.0] * 10 + [100.0] * 10)
        assert _max_sd_from_range(0, 100, n) == pytest.approx(attainable)


class TestHeydendaelExample:
    """Heathers §"Confusing SD and SE": SE=13, n=43 for ages → impossible if SE."""

    def test_se_label_implies_impossible_sd(self):
        result = check_sd_or_se(
            reported_value=13, n=43, reported_as="SE", variable_range=(18, 70)
        )
        # Implied SD = sqrt(43)*13 ≈ 85, range/2 ≈ 26 → impossible.
        assert result["as_se"]["implied_sd"] == pytest.approx(85.25, rel=1e-3)
        assert result["as_se"]["sd_plausible"] is False
        assert result["as_sd"]["sd_plausible"] is True
        assert result["likely_interpretation"] == "SD"
        assert result["severity"] == "suspicious"

    def test_sd_label_consistent(self):
        # If they had labeled it SD = 13, that's plausible.
        result = check_sd_or_se(
            reported_value=13, n=43, reported_as="SD", variable_range=(18, 70)
        )
        assert result["severity"] == "consistent"


class TestEdgeCases:
    def test_negative_value(self):
        # A negative dispersion is OUR parse artefact (an en dash or a range
        # separator read as a minus), never something an analysis prints, so
        # it is a REFUSAL rather than an accusation -- matching the sibling
        # `recalc_independent_t`, which had it right all along. It was also a
        # ceiling violation: this tool is declared `probabilistic`.
        result = check_sd_or_se(reported_value=-1, n=10)
        assert result["severity"] == "indeterminate"

    def test_n_too_small(self):
        result = check_sd_or_se(reported_value=5, n=1)
        assert result["severity"] == "indeterminate"

    def test_no_ceiling_returns_indeterminate(self):
        result = check_sd_or_se(reported_value=10, n=20)
        assert result["likely_interpretation"] == "indeterminate"
        assert result["severity"] == "indeterminate"

    def test_both_implausible_stated_bound(self):
        # Value 80 from a 0..10 variable, n=4 — both interpretations exceed
        # range/2 = 5. The paper STATES the 0-10 range, so the ceiling is a
        # hard bound and a "neither reading fits" verdict may escalate.
        result = check_sd_or_se(
            reported_value=80, n=4, reported_as="SD", variable_range=(0, 10),
            bound_source="stated",
        )
        assert result["likely_interpretation"] == "neither"
        assert result["severity"] == "highly_suspicious"

    def test_both_implausible_assumed_bound_caps_at_suspicious(self):
        # Same numbers, but the 0-10 range is OURS, not the paper's. A "neither
        # reading fits" verdict rests entirely on a ceiling we invented, so it
        # caps at `suspicious` (rulebook rule 4). `assumed` is the default, so
        # this is what the tool says when the caller does not vouch for the bound.
        result = check_sd_or_se(
            reported_value=80, n=4, reported_as="SD", variable_range=(0, 10)
        )
        assert result["likely_interpretation"] == "neither"
        assert result["severity"] == "suspicious"
        # The nested range check must not carry a bare `impossible` inside the
        # capped result.
        assert result["as_sd"]["sd_range_check"]["severity"] != "impossible"

    def test_vas_instrument_false_accusation_is_capped(self):
        # A real VAS 0-100mm instrument legitimately has SD 12.0 at n=50, but if
        # WE assume a 0-10 scale the value looks impossible. Against an assumed
        # bound the tool must cap at `suspicious`, not brand it highly_suspicious.
        result = check_sd_or_se(
            12.0, 50, reported_as="SD", variable_range=(0, 10)
        )
        assert result["severity"] == "suspicious"
        # With the paper's real stated range, it is consistent.
        real = check_sd_or_se(
            12.0, 50, reported_as="SD", variable_range=(0, 100), bound_source="stated"
        )
        assert real["severity"] == "consistent"

    def test_explicit_ceiling_overrides_range(self):
        result = check_sd_or_se(
            reported_value=20, n=10, plausible_sd_max=5
        )
        assert result["plausibility_ceiling"] == 5
        assert result["as_sd"]["sd_plausible"] is False


class TestSdCeilingConsistency:
    """The two SD-ceiling formulas must agree.

    `se_sd._max_sd_from_range` claimed in its docstring to mirror
    `sd_checks.check_sd_range`, but returned the reciprocal correction factor
    (0.90x the true ceiling at n=10). Attainable SDs therefore exceeded it and
    `check_sd_or_se` began arguing the paper had mislabelled an SE.
    """

    @pytest.mark.parametrize("n", [2, 3, 10, 30, 100, 1000])
    def test_ceilings_agree(self, n):
        import math
        from metascience_agent.tools.se_sd import _max_sd_from_range

        data_range = 10.0
        expected = data_range / 2 * math.sqrt(n / (n - 1))  # sd_checks' bound
        assert _max_sd_from_range(0.0, 10.0, n) == pytest.approx(expected, rel=1e-12)

    @pytest.mark.parametrize("n", [2, 10, 30, 100])
    def test_ceiling_is_actually_attainable(self, n):
        """Half the points at each extreme must NOT exceed the ceiling."""
        import statistics

        from metascience_agent.tools.se_sd import _max_sd_from_range

        half = n // 2
        sample = [0.0] * half + [10.0] * (n - half)
        assert statistics.stdev(sample) <= _max_sd_from_range(0.0, 10.0, n) + 1e-9
