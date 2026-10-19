"""`design` was accepted, echoed into the result, and consulted nowhere.

`check_effect_plausibility` recomputes a BETWEEN-GROUPS d -- the mean difference
over a pooled SD -- and compares it to the paper's reported d with a
rounding-only tolerance. A within-subjects study reports `d_z`, the mean change
over the SD of the DIFFERENCES. They are related by

    d_rm = d_z * sqrt(2 * (1 - r))                     [Lakens 2013 eq. 8]

so they coincide only at r = 0.5 and diverge without limit as the pre-post
correlation rises. r is not among this function's arguments and cannot be
inferred from pre/post means and SDs, so a paired d is not checkable here at
all -- and an honest one was being called wrong.
"""

from __future__ import annotations

import pytest

from metascience_agent.tools.effect_size import check_effect_plausibility as check

# An honest within-subjects study: pre 50.0 (10.0), post 44.5 (10.0), n = 30,
# correctly reporting d_z = 0.87. The between-groups recomputation gives 0.55.
HONEST_PAIRED = dict(mean1=50.0, sd1=10.0, n1=30, mean2=44.5, sd2=10.0, n2=30,
                     reported_d=0.87)


class TestAPairedDesignIsRefusedNotAccused:
    @pytest.mark.parametrize("design", [
        "within_subjects_pre_post", "repeated measures", "within-subjects",
        "pre-post", "crossover", "matched pairs", "longitudinal",
    ])
    def test_it_does_not_accuse(self, design):
        r = check(**HONEST_PAIRED, design=design)
        assert r["severity"] == "indeterminate"
        assert r["applicable"] is False

    def test_it_says_why_and_names_the_right_tool(self):
        r = check(**HONEST_PAIRED, design="repeated measures")
        why = r["why_not_checked"]
        assert "d_z" in why
        assert "correlation" in why
        assert "paired_d_interval" in why

    def test_it_reuses_the_shared_design_vocabulary(self):
        """A second design list here would drift from the one
        `check_variance_dispersion` refuses on -- this codebase has found the
        same constant hand-copied eleven times with the copies disagreeing."""
        from metascience_agent.tools.csf import _resolve_design
        from metascience_agent.tools.effect_size import _design_is_paired
        assert _design_is_paired("repeated measures")
        assert _resolve_design("repeated measures") == "repeated_measures"
        assert not _design_is_paired("parallel-group RCT")


class TestBetweenGroupsCheckingIsUnchanged:
    """The refusal must not become "stop checking"."""

    def test_a_genuinely_wrong_between_groups_d_is_still_suspicious(self):
        r = check(**HONEST_PAIRED, design="parallel-group RCT")
        assert r["severity"] == "suspicious"

    def test_an_undeclared_design_is_unchanged(self):
        """We cannot tell a paired study from its six numbers, so nothing is
        assumed -- the conservative direction preserves the existing check."""
        r = check(**HONEST_PAIRED)
        assert r["severity"] == "suspicious"

    def test_a_correct_between_groups_d_is_consistent(self):
        r = check(mean1=50.0, sd1=10.0, n1=30, mean2=44.5, sd2=10.0, n2=30,
                  reported_d=0.55, design="parallel-group RCT")
        assert r["severity"] == "consistent"

    def test_an_unknown_design_string_does_not_silently_excuse(self):
        r = check(**HONEST_PAIRED, design="some novel allocation scheme")
        assert r["severity"] == "suspicious"
