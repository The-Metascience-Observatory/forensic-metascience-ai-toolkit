"""The corner the Monte Carlo sampler never visits.

`rivets_anova` derives the achievable p-range by sampling uniformly from the
interior of the rounding box. The extreme of F lies on a VERTEX of that box,
which a finite uniform sample reaches with probability zero -- so the reported
interval is too NARROW, and a too-narrow interval is exactly what turns a
reachable p into "UNREACHABLE".

REPRODUCED before the fix, and independently re-derived rather than taken from
the report that raised it:

    rivets_anova(means=[1.60]*3, sds=[0.07]*3, ns=[150]*3, reported_p=0.35)
      -> highly_suspicious
         "Reported p value = 0.35 is UNREACHABLE given the achievable interval
          [0.366, 1] implied by the printed precision of the group means/SDs."

An independent corner enumeration gives a smallest achievable p of 0.3072, so
0.35 IS achievable and the accusation was our sampling shortfall reported in
the grammar of a claim about the paper -- at the second-highest severity the
system has.

Why a vertex: between-group SS is a positive semidefinite quadratic form in the
means, hence convex, and a convex function over a box attains its maximum at a
corner; within-group SS depends only on the SDs and is minimal at their floors.
"""

import itertools

import pytest
from scipy import stats

from forensic_metascience_ai_toolkit.tools.rivets import rivets_anova

TIGHT = dict(means=[1.60] * 3, sds=[0.07] * 3, ns=[150] * 3)


def corner_p_min(means, sds, ns, half_m=0.005, half_s=0.005):
    """The smallest achievable p, derived here rather than from the module."""
    k, N = len(means), sum(ns)
    best = 1.0
    for signs in itertools.product((-1, 1), repeat=k):
        mm = [m + s * half_m for m, s in zip(means, signs)]
        ss = [s - half_s for s in sds]
        gm = sum(m * n for m, n in zip(mm, ns)) / N
        ssb = sum(n * (m - gm) ** 2 for m, n in zip(mm, ns))
        ssw = sum((n - 1) * s * s for n, s in zip(ns, ss))
        best = min(best, float(stats.f.sf((ssb / (k - 1)) / (ssw / (N - k)), k - 1, N - k)))
    return best


class TestTheAchievableRangeReachesTheCorner:
    def test_a_corner_reachable_p_is_not_called_unreachable(self):
        got = rivets_anova(reported_p=0.35, **TIGHT)
        assert got["severity"] == "consistent", got.get("explanation")

    def test_the_reported_minimum_matches_an_independent_derivation(self):
        got = rivets_anova(reported_p=0.35, **TIGHT)
        assert got["p_min"] == pytest.approx(corner_p_min(**TIGHT), abs=1e-4)

    def test_the_range_only_ever_widened(self):
        """The corner is unioned with the sampled range, so it can only remove
        accusations, never add one."""
        got = rivets_anova(reported_p=0.35, **TIGHT)
        assert got["p_min"] <= 0.3662 and got["p_max"] >= 1.0 - 1e-9


class TestGenuineDetectionsSurvive:
    def test_a_p_below_every_corner_still_fires(self):
        got = rivets_anova(reported_p=0.001, **TIGHT)
        assert got["severity"] == "highly_suspicious"

    def test_a_real_separation_still_reconciles(self):
        got = rivets_anova(means=[1.0, 2.0, 3.0], sds=[0.5] * 3, ns=[20] * 3,
                           reported_p="<.001")
        assert got["severity"] == "consistent"


class TestTheThresholdDeclarationIsReachable:
    """`_reported_p_outside` calls reading a bound as exact "a large
    false-accusation class rather than a detection" -- and the only way to say
    "this is a bound" was a STRING, while the registry types `reported_p` as a
    float. The guard existed and could not be reached on any real call."""

    BIG = dict(means=[1.0, 2.0, 3.0], sds=[0.5] * 3, ns=[20] * 3)

    def test_the_registry_exposes_it(self):
        from forensic_metascience_ai_toolkit import registry as R
        for name in ("rivets_anova", "rivets_independent_t"):
            assert "p_is_threshold" in R.BY_NAME[name].schema(), name

    def test_declaring_a_bound_over_mcp_reaches_the_threshold_rule(self):
        from forensic_metascience_ai_toolkit import registry as R
        got = R.BY_NAME["rivets_anova"].call(
            {**self.BIG, "reported_p": 0.001, "p_is_threshold": True})
        assert got["severity"] == "consistent"

    def test_an_explicit_declaration_beats_the_literal(self):
        assert rivets_anova(reported_p=0.001, p_is_threshold=True,
                            **self.BIG)["severity"] == "consistent"
        assert rivets_anova(reported_p=0.001, p_is_threshold=False,
                            **self.BIG)["severity"] == "highly_suspicious"

    def test_unset_still_reads_the_string_form(self):
        """The old channel keeps working for direct/CLI callers."""
        assert rivets_anova(reported_p="<.001", **self.BIG)["severity"] == "consistent"
