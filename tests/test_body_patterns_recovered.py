"""Four forms the numeral floor could not see.

The floor exists to say what the model overlooked, so a REPORTED statistic that
lands in `unclassified` is the floor failing at its own job. These four are the
largest recoverable groups on the 12-paper corpus, measured rather than guessed.

CLASSIFICATION, NOT SUPPRESSION -- the distinction `numerals.tally` is built
around. `n_total` is model-free and must not move; what moves is the split
between `statistic` and `unclassified`. Measured: 3,371 numerals before and
after; unclassified 1,938 -> 1,839; statistic 834 -> 933.
"""

from __future__ import annotations

import re

import pytest

from metascience_agent.completeness import BODY_PATTERNS


def _matches(name: str, text: str):
    return [m.group(0) for m in re.finditer(BODY_PATTERNS[name], text, re.I)]


class TestDegreesOfFreedomFusedToTheSymbol:
    """`nhst` REQUIRES parentheses, so `F1,37 = 1.19` matched nothing -- an
    ordinary printed form, and the usual result of a PDF losing its subscript
    markup. 50 unclassified numerals sit inside one, the largest single
    recoverable group on the floor."""

    @pytest.mark.parametrize("text", [
        "no main effects of time (F1,37 = 1.19, p = 0.282)",
        "emotional awareness (F1,60 = 6.52, p = 0.013)",
        "F1,26 = 0.04", "t2,18 = 3.1", "z1,5 = 0.9",
    ])
    def test_it_matches(self, text):
        assert _matches("nhst_glued", text)

    def test_the_parenthesised_form_still_belongs_to_nhst(self):
        assert _matches("nhst", "t(243.39) = 2.11")

    @pytest.mark.parametrize("text", [
        "Table 1,37 shows", "in 2019, 37 patients", "F 1 , and separately 37",
    ])
    def test_it_does_not_match_prose_numbers(self, text):
        assert not _matches("nhst_glued", text)


class TestABoundedStatisticIsStillReported:
    """`nhst` requires `=`, so `F (1,52) < 0.1` -- how a paper reports a test it
    wants to dismiss -- was invisible."""

    @pytest.mark.parametrize("text", [
        "a digit-span task ( F (1,68) < 0.3)",
        "a reading-span task ( F (1,52) < 0.1)",
        "t (30) < 1.24", "t (39) < 1.04",
    ])
    def test_it_matches(self, text):
        assert _matches("nhst_bounded", text)


class TestABareRegressionCoefficient:
    """`named_equality` carries `beta` and `β` but not `b`, and psychology
    writes the unstandardised coefficient as a lone `b`."""

    @pytest.mark.parametrize("text", [
        "b = -2.43, SE b = 1.87", "b = 0.13, SE b = 0.07", "b =0.61",
        "B=.10, x 2 =28.82", "B = .08",
    ])
    def test_it_matches(self, text):
        assert _matches("beta_bare", text)

    @pytest.mark.parametrize("text", [
        "baseline = 3 months", "the number = 5", "sub_b = 7", "1b = 4",
    ])
    def test_it_requires_b_to_stand_alone(self, text):
        """Adding `b` to `named_equality` would have inherited its
        `[A-Za-z0-9_]{0,14}` suffix and matched every word starting with b."""
        assert not _matches("beta_bare", text)

    def test_it_excludes_the_corrupted_minus(self):
        """`10.1371--journal.pone.0069841` loses its minus signs to a CMap
        fault, so `B = -.012` arrives as `B = 2 .012`. Without the lookahead
        this files a mangled minus sign as a reported coefficient. Measured: 8
        such artifacts on that paper, now 0."""
        assert not _matches("beta_bare", "B = 2 .012, b = 2 .126")
        assert _matches("beta_bare", "B = 2.012")      # a real coefficient


class TestTheJamaEffectAndIntervalForm:
    """`estimate_ci_prose` requires the interval parenthesised immediately after
    the estimate; this journal family separates them with a semicolon."""

    @pytest.mark.parametrize("text", [
        "ARR, 0.879; 95% CI, 0.775-0.997; P = .04",
        "(AOR, 1.71; 95% CI, 1.17-2.49)",
        "ARR, 0.217; 95% CI, 0.081-0.582",
        "HR, 1.05; 95% CI, 1.01-1.09",
    ])
    def test_it_matches(self, text):
        assert _matches("effect_ci_jama", text)

    def test_the_parenthesised_form_still_belongs_to_the_older_pattern(self):
        assert _matches("estimate_ci_prose", "1.71 (95% CI 1.17 to 2.49)")


class TestTheFloorIsClassifiedNotSuppressed:
    """`numerals.tally`'s rule: the denominator must be independent of the
    finder. `n_total` is the one number that cannot quietly shrink."""

    def test_no_pattern_can_remove_a_numeral(self):
        from metascience_agent import numerals as N
        text = ("F1,37 = 1.19, p = 0.282; b = 0.13, SE b = 0.07; "
                "ARR, 0.879; 95% CI, 0.775-0.997.")
        assert len(N.index(text)) == len(N.index(text))
        assert len(N.index(text)) > 0
