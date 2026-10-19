"""Convention rescues must not stop at the bounds WE assumed.

Three false-accusation paths, each verified by execution before the fix
(2026-08-09), each an instance of the same house failure pattern: OUR
assumption -- an assumed scale bound, an undisclosed rounding convention, a
search confined to a region we chose -- reported in the grammar of a claim
about the PAPER.

  * SPRITE's population-SD rescue searched only INSIDE the assumed scale, so
    a population-SD report whose reconstruction needs values beyond that
    scale returned `no_solution_proven` at `impossible` with the error "No
    integer sample can produce this mean/SD pair" -- a sentence that is
    simply false (the real sample below produces it).
  * GRIMMER's population-SD rescue had the identical defect, and its failure
    reason claimed impossibility "under either the sample (n-1) or population
    (n) convention" when the population convention was never tried outside
    the assumed bounds.
  * DEBIT assumed the round-half convention without trying or disclosing
    truncation, so an honest truncating reporter (SPSS's default, one of
    scrutiny::grim's rounding options) was convicted at `impossible`.

The witness for the first two is REAL data on a 1-10 scale reported with the
population SD (numpy's std default, Excel's STDEVP):

    [2,2,2,3,4,4,5,5,5,6,6,7,8,8,8,9,9,10,10,10]
    n=20, exact mean 6.15, population SD 2.7069 -> printed 2.71

Handed to either tool with the 1-7 default (bound_source="assumed"), both
returned `impossible` before the fix. A verdict that rests on an assumed
bound is capped below `impossible` (house rule: only bound-free arithmetic
may reach `impossible`), and the honest verdict here is "consistent if the SD
is a population SD and the scale is wider than assumed".
"""

import numpy as np
import pytest

from forensic_metascience_ai_toolkit.tools.debit import debit_test, debit_test_batch
from forensic_metascience_ai_toolkit.tools.sd_checks import grimmer_test
from forensic_metascience_ai_toolkit.tools.sprite import sprite_reconstruct

# Real integers on a 1-10 scale whose POPULATION SD rounds to 2.71.
WITNESS = [2, 2, 2, 3, 4, 4, 5, 5, 5, 6, 6, 7, 8, 8, 8, 9, 9, 10, 10, 10]
CELL = dict(mean=6.15, sd=2.71, n=20)


def test_the_witness_is_what_the_docstring_says():
    assert len(WITNESS) == CELL["n"]
    assert np.mean(WITNESS) == pytest.approx(6.15)
    assert round(float(np.std(WITNESS, ddof=0)), 2) == 2.71



# `discreteness_source="stated"` from 2026-08-10: the bound-free branches
# (`grim_fail`, `no_solution_proven`) now cap at `suspicious` unless someone
# establishes that the observations are integers -- Greg's "guilty until proven
# innocent" rule for the GRIM family, see tools/grim.HARD_DISCRETENESS_SOURCES.
# These fixtures stipulate Likert data, so they say so. Assertions unchanged.
#
# SEPARATELY, on the same day: the POPULATION-SD convention moved from
# `suspicious` to `consistent` (Greg -- "it would be inconsistent to do the
# truncation check but not this"). Each class's thesis is unchanged -- the
# verdict must not be `impossible`, because a reporting convention is not
# fabrication -- and the convention is still named in `outcome` /
# `failure_mode` / `sd_convention`, which is what the per-paper rate is built
# from. Only the word moved.

class TestSpritePopulationSdOutsideAssumedBounds:
    def test_the_reported_false_accusation(self):
        """Assumed 1-7: the pop-SD solution lives on 1-10, and the verdict
        must say so instead of proving a falsehood."""
        r = sprite_reconstruct(**CELL, scale_min=1, scale_max=7)
        assert r["severity"] != "impossible"
        assert r["severity"] == "consistent"
        assert r["outcome"] == "sd_convention"
        assert r["sd_convention"] == "population"
        assert r["requires_bounds_beyond_assumed"] is True

    def test_the_error_names_both_of_our_assumptions(self):
        r = sprite_reconstruct(**CELL, scale_min=1, scale_max=7)
        assert "POPULATION" in r["error"]
        assert "wider than" in r["error"].lower()

    def test_stated_bounds_still_license_impossible(self):
        """If the paper really says 1-7, values beyond it are unavailable and
        the old verdict was correct."""
        r = sprite_reconstruct(**CELL, scale_min=1, scale_max=7,
                               bound_source="stated", discreteness_source="stated")
        assert r["severity"] == "impossible"
        assert r["outcome"] == "no_solution_proven"

    def test_the_truthful_stated_scale_is_the_in_bounds_pop_case(self):
        r = sprite_reconstruct(**CELL, scale_min=1, scale_max=10,
                               bound_source="stated")
        assert r["severity"] == "consistent"
        assert r["outcome"] == "sd_convention"

    def test_a_both_convention_impossibility_is_not_rescued(self):
        """mean 4.00, SD 1.40, n=10: no integer Q fits either convention's
        window even with the bounds removed (pop window [179.46, 179.74]
        contains no integer). The genuine detection keeps its weight."""
        r = sprite_reconstruct(4.0, 1.4, n=10, data_type="likert",
                               decimals_mean=2, decimals_sd=2,
                               discreteness_source="stated")
        assert r["outcome"] == "no_solution_proven"
        assert r["severity"] == "impossible"


class TestGrimmerPopulationSdOutsideAssumedBounds:
    def test_the_reported_false_accusation(self):
        r = grimmer_test(**CELL, scale_min=1, scale_max=7)
        assert r["severity"] != "impossible"
        assert r["severity"] == "consistent"
        assert r["failure_mode"] == "sd_convention"
        assert r["population_feasible_ignoring_bounds"] is True

    def test_the_reason_names_both_of_our_assumptions(self):
        r = grimmer_test(**CELL, scale_min=1, scale_max=7)
        assert "POPULATION" in r["failure_reason"]
        assert "ASSUMED" in r["failure_reason"]

    def test_stated_bounds_still_license_impossible_with_an_honest_reason(self):
        """`impossible` survives, but the reason may no longer claim that no
        convention admits the SD -- the population convention does, outside
        the stated scale, and the sentence must say where."""
        r = grimmer_test(**CELL, scale_min=1, scale_max=7,
                         bound_source="stated", discreteness_source="stated")
        assert r["severity"] == "impossible"
        assert r["failure_mode"] == "sd_granularity"
        assert "STATED" in r["failure_reason"]
        assert "either" not in r["failure_reason"]

    def test_it_agrees_with_sprite_on_the_same_cell(self):
        """Two tools corroborating a false `impossible` on one cell is what
        makes it persuasive; they must de-escalate together."""
        s = sprite_reconstruct(**CELL, scale_min=1, scale_max=7)
        g = grimmer_test(**CELL, scale_min=1, scale_max=7)
        assert s["severity"] == g["severity"] == "consistent"
        assert s["outcome"] == g["failure_mode"] == "sd_convention"

    def test_a_both_convention_impossibility_is_not_rescued(self):
        r = grimmer_test(mean=4.0, sd=1.4, n=10, scale_min=1, scale_max=7,
                         decimals=2, decimals_sd=2, discreteness_source="stated")
        assert r["severity"] == "impossible"
        assert r["failure_mode"] == "sd_granularity"
        assert r["population_feasible_ignoring_bounds"] is False


class TestDebitTruncationConvention:
    """An honest truncating reporter must not be convicted.

    Witnesses (verified by execution before the fix; both returned
    `impossible`):

      * 2 ones + 1 zero, n=3: exact mean 0.6667, sample SD 0.5774. A
        truncating reporter prints 0.66 / 0.57; round-half admits no k at
        all, so the MEAN step convicted -- "The mean alone is impossible".
      * 2 ones + 2 zeros, n=4: exact mean 0.50, sample SD 0.5774, printed
        0.50 / 0.57 by a truncating reporter; the SD step convicted
        (`sd_convention: neither`).
    """

    def test_truncated_mean_and_sd_are_not_impossible(self):
        assert round(2 / 3, 4) == 0.6667  # truncates to 0.66, rounds to 0.67
        r = debit_test(mean=0.66, sd=0.57, n=3)
        # RECALIBRATED 2026-08-10 (Greg): a value rescued purely by the
        # TRUNCATION convention is `consistent`, so it can never enter the
        # findings as an accusation. The fact is carried by the convention
        # field and by the per-paper rate. See `grim.grim_test`.
        assert r["severity"] == "consistent"
        assert r.get("truncation_only") or r.get("rounding_convention")
        assert r["rounding_convention"] == "truncation"
        assert 2 in r["matching_k_values_truncation"]

    def test_truncated_sd_alone_is_not_impossible(self):
        r = debit_test(mean=0.5, sd=0.57, n=4)
        # RECALIBRATED 2026-08-10 (Greg): a value rescued purely by the
        # TRUNCATION convention is `consistent`, so it can never enter the
        # findings as an accusation. The fact is carried by the convention
        # field and by the per-paper rate. See `grim.grim_test`.
        assert r["severity"] == "consistent"
        assert r["rounding_convention"] == "truncation"

    def test_the_explanation_names_the_convention(self):
        r = debit_test(mean=0.5, sd=0.57, n=4)
        assert "TRUNCATED" in r["explanation"]
        assert "not evidence of fabrication" in r["explanation"].lower()

    def test_a_round_half_consistent_triple_is_untouched(self):
        r = debit_test(mean=0.50, sd=0.50, n=100)
        assert r["severity"] == "consistent"
        assert r["rounding_convention"] == "round_half"

    def test_regnerus_2012_stays_impossible(self):
        """The canonical true positive: SD 0.75 at mean 0.01 fits no k under
        any convention, rounded or truncated."""
        r = debit_test(mean=0.01, sd=0.75, n=1000)
        assert r["severity"] == "impossible"
        assert r["rounding_convention"] == "neither"

    def test_a_mean_impossible_under_both_conventions_stays_impossible(self):
        """n=30 admits 0.500 and 0.5333...; 0.501 at 3 dp is reachable by
        neither rounding nor truncation."""
        r = debit_test(mean=0.501, sd=0.5, n=30, decimals_mean=3)
        assert r["severity"] == "impossible"
        assert "both" in r["explanation"].lower()

    def test_the_batch_still_counts_a_truncation_row_even_though_it_passes(self):
        """RENAMED 2026-08-10. It used to assert the batch does not "launder" a
        truncation row into `consistent` -- but that IS now the severity, by
        Greg's decision. The intent survives intact: the row must still be
        COUNTED, because the per-paper rate is where the signal lives."""
        rows = [
            {"label": "fine", "mean": 0.50, "sd": 0.50, "n": 100, "decimals_mean": 2, "decimals_sd": 2},
            {"label": "truncated", "mean": 0.5, "sd": 0.57, "n": 4, "decimals_mean": 2, "decimals_sd": 2},
        ]
        result = debit_test_batch(rows)
        assert result["n_truncation_convention"] == 1
        # RECALIBRATED 2026-08-10 (Greg): a value rescued purely by the
        # TRUNCATION convention is `consistent`, so it can never enter the
        # findings as an accusation. The fact is carried by the convention
        # field and by the per-paper rate. See `grim.grim_test`.
        assert result["severity"] == "consistent"
