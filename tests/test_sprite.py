"""SPRITE may not say `impossible` against a scale it invented.

`sprite_reconstruct` defaults to scale_min=1, scale_max=7 -- a Likert scale
applied to whatever it is handed -- and had no `bound_source` cap, so a value
that merely fell outside OUR default came back as the strongest verdict the
system can produce.

Measured on a real paper: "Number of coalition members", mean 35.78, SD 33.74,
n=64, declared `count` with NO stated bounds. SPRITE assumed [1, 7], computed
that the implied total 2290 exceeded its imagined maximum of 448, and returned:

    "The implied total 2290 lies outside the attainable range [64, 448] for
     n=64 on scale [1, 7]."

There is no 1-7 scale anywhere in that paper, and 2290/64 = 35.78125 rounds to
35.78. `grim_check` got the same cell right (`suspicious`) because it caps
out-of-range findings under an assumed bound (tools/grim.py:161-170).

The cap is on the FAILURE MODE, not on the tool: a granularity failure is
bound-free and stays `impossible`.
"""
import pytest

from metascience_agent.tools.sprite import _sd_window_feasible, sprite_reconstruct

COALITION = dict(mean=35.78, sd=33.74, n=64, data_type="count",
                 decimals_mean=2, decimals_sd=2)



# `discreteness_source="stated"` from 2026-08-10: the bound-free branches
# (`grim_fail`, `no_solution_proven`) now cap at `suspicious` unless someone
# establishes that the observations are integers -- Greg's "guilty until proven
# innocent" rule for the GRIM family, see tools/grim.HARD_DISCRETENESS_SOURCES.
# These fixtures stipulate Likert data, so they say so. Assertions unchanged.

class TestInventedBoundsAreCapped:
    def test_the_reported_false_accusation(self):
        r = sprite_reconstruct(**COALITION)
        assert r["severity"] == "suspicious"
        assert r["outcome"] == "out_of_range"

    def test_the_explanation_names_the_bound_as_ours(self):
        r = sprite_reconstruct(**COALITION)
        assert "assumed" in r["explanation"]
        assert r["bound_source"] == "assumed"

    def test_a_stated_bound_still_licenses_impossible(self):
        r = sprite_reconstruct(**COALITION, bound_source="stated")
        assert r["severity"] == "impossible"
        assert r["outcome"] == "out_of_range"

    def test_a_logically_necessary_bound_also_licenses_impossible(self):
        r = sprite_reconstruct(**COALITION, bound_source="logically_necessary")
        assert r["severity"] == "impossible"

    def test_the_truthful_scale_makes_it_consistent(self):
        r = sprite_reconstruct(**COALITION, scale_min=0, scale_max=500,
                               bound_source="stated")
        assert r["severity"] == "consistent" and r["outcome"] == "found"


class TestBoundFreeFailuresKeepTheirWeight:
    """A cap that swallowed real granularity failures would be worse than none."""

    def test_a_grim_failure_is_still_impossible(self):
        """5.51 x 30 = 165.3: no integer total rounds to it, on ANY scale."""
        r = sprite_reconstruct(5.51, 1.2, n=30, data_type="likert",
                               discreteness_source="stated")
        assert r["outcome"] == "grim_fail"
        assert r["severity"] == "impossible"

    def test_a_grim_failure_is_not_relabelled_out_of_range(self):
        """Both lists must exist separately: `grim_sums` is bound-free, and
        `admissible_sums` is that list intersected with the scale. Reading
        `grim_fail` off the FILTERED list made every range failure look like a
        granularity failure."""
        r = sprite_reconstruct(35.78, 33.74, n=64, data_type="count",
                               decimals_mean=2, decimals_sd=2)
        assert r["outcome"] != "grim_fail"
        assert r["grim_sums"] == [2290]

    def test_an_arithmetic_sd_impossibility_is_still_impossible(self):
        """mean 4.00, SD 1.40, n=10: unreachable under BOTH the sample and the
        population SD convention (exhaustively enumerated), so the population
        fallback does not rescue it and it stays impossible.

        The old case here was SD=1.00, which IS reachable under the population
        convention ([2,3,3,4,4,4,5,5,5,5], population SD exactly 1.00) -- calling
        it impossible was a false accusation against numpy's std default. That
        case is now TestSpritePopulationSdConvention in
        test_false_positive_guards.py."""
        r = sprite_reconstruct(4.0, 1.4, n=10, data_type="likert",
                               decimals_mean=2, decimals_sd=2,
                               discreteness_source="stated")
        assert r["outcome"] == "no_solution_proven"
        assert r["severity"] == "impossible"
        assert r["feasible_ignoring_bounds"] is False

    def test_a_reconstructable_pair_is_untouched(self):
        r = sprite_reconstruct(4.0, 0.82, n=10, data_type="likert")
        assert r["severity"] == "consistent" and r["outcome"] == "found"


class TestBoundFreeFeasibilityScreen:
    """`apply_bounds=False` keeps only what holds for ANY integers."""

    def test_dropping_bounds_can_only_help(self):
        for s in (2290, 40, 165):
            bounded, _ = _sd_window_feasible(s, 64, 33.74, 2, 1, 7, apply_bounds=True)
            free, _ = _sd_window_feasible(s, 64, 33.74, 2, 1, 7, apply_bounds=False)
            assert free or not bounded

    def test_parity_still_bites_without_bounds(self):
        """The integrality/parity proof does not depend on the scale at all."""
        ok, reason = _sd_window_feasible(40, 10, 1.0, 2, 1, 7, apply_bounds=False)
        assert ok is False and "parity" in reason
