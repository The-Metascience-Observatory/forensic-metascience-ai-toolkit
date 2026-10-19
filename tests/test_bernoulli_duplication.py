"""A proportion beside its own SD is one number, not two.

VERIFIED FALSE ACCUSATION, 2026-08-12. `prepass.sweep_duplication` returned
`highly_suspicious` with a coincidence probability of 4.8e-09 on
`10.1001/jamanetworkopen.2023.51752` -- an honest JAMA Network Open cohort
paper, and one on our own demonstration shortlist. It was found by an
adversarial review of a proposal to run MORE harness-aimed sweeps, which is the
only reason it was found at all: the sweep runs on every paper today and nobody
had read its output on a paper we believed was clean.

Every flagged pair was a binary variable printed as `proportion (SD)`, where
sd = sqrt(m(1-m)) is a DETERMINISTIC function of the mean:

    mean 0.26 -> 0.4386 (printed 0.44)     mean 0.10 -> 0.3000 (printed 0.30)
    mean 0.06 -> 0.2375 (printed 0.24)     mean 0.14 -> 0.3470 (printed 0.35)

Two compounding defects. The chance model multiplied p_mean by p_sd as two
independent draws when the pair carries ONE free parameter, understating the
probability by about four orders of magnitude. And the severity ladder counted
a nonzero SD as "high precision" when for these cells the SD restates the mean.

The fix must not cost discriminating power: the duplicated affect rows in the
Kouchaki & Gino PNAS supplement are the archetypal true positive this tool
exists to find, and they are NOT Bernoulli (their means exceed 1).
"""
import math
import pathlib

import pytest

from metascience_agent.tools.duplication import (
    _SAMPLE_SD_ALLOWANCE, _is_bernoulli_pair, detect_duplication,
)

REPO = pathlib.Path(__file__).resolve().parent.parent
JAMA = REPO / "tests/fixtures/papers/high_value_pdfs_to_run_on" / "10.1001--jamanetworkopen.2023.51752"

#: The exact pairs the tool flagged on the JAMA paper, read from its output.
FLAGGED = [(0.26, 0.44), (0.30, 0.46), (0.31, 0.47), (0.32, 0.47),
           (0.06, 0.24), (0.07, 0.25), (0.09, 0.29), (0.10, 0.30),
           (0.11, 0.31), (0.11, 0.32), (0.12, 0.32), (0.12, 0.33), (0.14, 0.35)]

#: Kouchaki & Gino, PNAS 2016, Tables S1/S2 -- identical across two studies the
#: paper describes as separate MTurk samples. The true positive.
GINO = [("Positive affect", 2.37, 0.92), ("Negative affect", 1.73, 0.82),
        ("PA post", 3.06, 0.97), ("NA post", 1.25, 0.37)]


class TestTheDetector:
    def test_it_recognises_every_pair_that_produced_the_false_accusation(self):
        missed = [(m, s) for m, s in FLAGGED if not _is_bernoulli_pair(m, s, 2, 2)]
        assert not missed, (
            f"{len(missed)} of {len(FLAGGED)} flagged pairs still read as two "
            f"independent numbers: {missed}. Each one keeps the group accusatory.")

    def test_the_band_allows_for_the_MEANS_own_rounding(self):
        """`0.07 (0.25)`: sqrt(.07 x .93) = 0.2551, which rounds to 0.26, not the
        printed 0.25. Judged against the printed mean alone this pair is refused
        -- but the true proportion is only known to lie in [0.065, 0.075], and
        that admits 0.25. Ignoring the mean's rounding leaves the accusation."""
        assert _is_bernoulli_pair(0.07, 0.25, 2, 2)
        assert abs(math.sqrt(0.07 * 0.93) - 0.2551) < 1e-3   # the naive value

    def test_the_band_allows_for_the_SAMPLE_sd_convention(self):
        """`0.31 (0.47)` misses the population band by 0.0005. Papers divide by
        n-1 as often as by n, and one rejected pair out of four kept the whole
        group at `highly_suspicious`."""
        assert _is_bernoulli_pair(0.31, 0.47, 2, 2)
        assert _SAMPLE_SD_ALLOWANCE >= math.sqrt(25 / 24), "must cover n >= 25"

    def test_a_continuous_pair_is_NOT_bernoulli(self):
        """The guard that preserves the Gino catch: a mean above 1 cannot be a
        proportion, so no affect scale can be discounted by this rule."""
        for _, m, s in GINO:
            assert not _is_bernoulli_pair(m, s, 2, 2), (m, s)

    def test_a_proportion_with_an_UNRELATED_sd_is_not_bernoulli(self):
        """The discount is earned by the arithmetic, not by being in [0, 1]."""
        assert not _is_bernoulli_pair(0.26, 0.10, 2, 2)
        assert not _is_bernoulli_pair(0.26, 0.90, 2, 2)

    def test_missing_values_are_refused_rather_than_assumed(self):
        assert not _is_bernoulli_pair(None, 0.44, 2, 2)
        assert not _is_bernoulli_pair(0.26, None, 2, 2)


class TestTheFalseAccusationIsGone:
    @pytest.mark.skipif(not JAMA.exists(), reason="corpus paper not present")
    def test_the_jama_cohort_paper_is_not_accused(self):
        """THE REGRESSION TEST. This paper is honest, it is on the demo
        shortlist, and the tool called it highly_suspicious."""
        from metascience_agent import prepass
        result = prepass.sweep_duplication(prepass.paper_tables(JAMA))
        assert result["severity"] not in ("suspicious", "highly_suspicious",
                                          "impossible"), result["severity"]

    @pytest.mark.skipif(not JAMA.exists(), reason="corpus paper not present")
    def test_and_its_chance_probability_is_now_honest(self):
        """4.8e-09 said a coincidence was essentially impossible. With the pair
        priced as one number, a chance match is essentially CERTAIN -- which is
        the true state of affairs for proportions repeated across the tables of
        one cohort."""
        from metascience_agent import prepass
        res = prepass.sweep_duplication(prepass.paper_tables(JAMA))["result"]
        assert res["chance_probability"] > 0.5, res["chance_probability"]

    def test_a_bernoulli_group_cannot_reach_an_accusatory_tier_on_its_own(self):
        blocks = [
            {"label": f"Table {i}", "cells": [
                {"label": f"var{j}", "value": m, "sd": s}
                for j, (m, s) in enumerate(FLAGGED)]}
            for i in (1, 2)
        ]
        out = detect_duplication(blocks)
        assert out["severity"] not in ("suspicious", "highly_suspicious")
        grp = next(g for g in out["duplicate_groups"]
                   if g["kind"] == "cross_source_pair")
        assert grp["is_bernoulli_pair"] is True


class TestDiscriminatingPowerSurvives:
    """The fix is worthless if it also silences the case the tool exists for."""

    def _gino_blocks(self):
        return [{"label": lbl, "cells": [
                    {"label": n, "value": m, "sd": s} for n, m, s in GINO]}
                for lbl in ("Table S1 (study 1a)", "Table S2 (study 1b)")]

    def test_the_gino_duplication_is_still_highly_suspicious(self):
        out = detect_duplication(self._gino_blocks())
        assert out["severity"] == "highly_suspicious", out["severity"]

    def test_and_its_group_is_not_discounted_as_bernoulli(self):
        out = detect_duplication(self._gino_blocks())
        grp = next(g for g in out["duplicate_groups"]
                   if g["kind"] == "cross_source_pair")
        assert grp["is_bernoulli_pair"] is False
        assert grp["k_pairs"] == 4

    def test_its_chance_probability_stays_vanishingly_small(self):
        out = detect_duplication(self._gino_blocks())
        assert out["chance_probability"] < 1e-6, out["chance_probability"]


class TestThePriceOfAPair:
    """The probability half of the defect, tested separately from the severity
    half: either one alone still publishes a wrong number."""

    def test_a_bernoulli_group_is_priced_on_the_mean_ALONE(self):
        """Two runs over the same means, one with Bernoulli SDs and one with
        SDs of the same spread that are NOT determined by the mean. The
        Bernoulli run must come out LESS surprising -- it has one free
        parameter where the other has two."""
        means = [m for m, _ in FLAGGED]
        bern = [{"label": f"T{i}", "cells": [
                    {"label": f"v{j}", "value": m, "sd": s}
                    for j, (m, s) in enumerate(FLAGGED)]} for i in (1, 2)]
        # Same means, SDs spanning the same range but unrelated to them.
        sds = sorted(s for _, s in FLAGGED)[::-1]
        free = [{"label": f"T{i}", "cells": [
                    {"label": f"v{j}", "value": m, "sd": sds[j]}
                    for j, m in enumerate(means)]} for i in (1, 2)]
        p_bern = detect_duplication(bern)["chance_probability"]
        p_free = detect_duplication(free)["chance_probability"]
        assert p_bern > p_free, (
            f"Bernoulli pairs priced at {p_bern:.3g}, free pairs at {p_free:.3g}. "
            "A pair carrying one number must not be scored as rarer than a pair "
            "carrying two.")
