"""PyPI statcheck 0.0.7 accuses every honest negative-statistic report.

Found by the independent validation sweep of 2026-08-27 and reproduced here
minimally. `statcheck.error_test.error_test` builds the test statistic's
rounding box on the SIGNED value and then assigns the two computed p-values by
position:

    low_stat = test_stat - .5/10**test_dec
    up_stat  = test_stat + .5/10**test_dec
    up_p  = compute_p(test_stat=low_stat, ...)
    low_p = compute_p(test_stat=up_stat, ...)

Correct for a positive t, because p falls as |t| rises. Backwards for a negative
one: `low_stat` carries the LARGER magnitude and therefore the SMALLER p, so the
two bounds arrive swapped and every later comparison is made against an inverted
interval.

This is the largest false-accusation channel measured anywhere in the toolkit,
and it is not our arithmetic.
"""
from __future__ import annotations

import random

import pytest

statcheck = pytest.importorskip("statcheck", reason="statcheck is optional")

from forensic_metascience_ai_toolkit.tools.r_wrappers import (  # noqa: E402
    _patch_statcheck_sign_bug,
)


@pytest.fixture(autouse=True)
def _patched():
    assert _patch_statcheck_sign_bug(), "the shim must install for these tests"


def _error(p, t, df, dec=1):
    from statcheck.error_test import error_test
    return bool(error_test(p, "t", t, None, df, "=", "=", 3, dec, True, .05, True))


def _true_p(t, df):
    from statcheck.compute_p import compute_p
    return compute_p("t", t, None, df, True)


class TestTheMinimalReproduction:
    """The same statistic, reported with each sign, must get the same verdict."""

    def test_a_negative_t_is_not_an_error_when_its_positive_twin_is_not(self):
        assert _error(0.059, -2.0, 20) == _error(0.059, 2.0, 20)

    def test_and_specifically_neither_is_an_error(self):
        """.059 sits inside the true interval [0.0537, 0.0653] either way."""
        assert not _error(0.059, -2.0, 20)
        assert not _error(0.059, 2.0, 20)

    @pytest.mark.parametrize("t,df", [(-2.0, 20), (-3.1, 45), (-1.4, 8),
                                      (-2.5, 100), (-4.2, 12)])
    def test_an_exactly_honest_negative_report_is_never_an_error(self, t, df):
        p = round(_true_p(t, df), 3)
        assert not _error(p, t, df), (
            f"t({df})={t}, p={p} is the correctly computed p and must not flag")


class TestSymmetryIsTheProperty:
    """Sign carries no information about whether a report is correct, so the
    verdict must not depend on it. This is the invariant, not the point cases."""

    def test_verdicts_match_across_sign_over_a_sweep(self):
        random.seed(11)
        mismatched = 0
        checked = 0
        for _ in range(400):
            df = random.randint(5, 120)
            t = round(random.uniform(0.5, 4.5), 1)
            lo, up = _true_p(t + .05, df), _true_p(t - .05, df)
            if (up - lo) < 0.001:
                continue      # interval narrower than the reported p's step
            p = round(_true_p(t, df), 3)
            checked += 1
            if _error(p, t, df) != _error(p, -t, df):
                mismatched += 1
        assert checked > 100, "the sweep must actually exercise decidable cases"
        assert mismatched == 0, f"{mismatched} of {checked} verdicts flipped with sign"


class TestRecallIsNotTradedAway:
    """A fix that silences the false accusations by refusing everything would
    pass every test above."""

    @pytest.mark.parametrize("sign", [1, -1])
    def test_a_genuinely_wrong_p_is_still_caught(self, sign):
        caught = 0
        random.seed(5)
        for _ in range(150):
            df = random.randint(10, 90)
            t = sign * round(random.uniform(1.0, 4.0), 1)
            wrong = round(min(0.98, _true_p(t, df) * 4 + 0.05), 3)
            if _error(wrong, t, df):
                caught += 1
        assert caught >= 145, f"only {caught}/150 genuine errors caught"


class TestTheShimItself:
    def test_it_is_idempotent(self):
        assert _patch_statcheck_sign_bug()
        assert _patch_statcheck_sign_bug()

    def test_it_marks_the_function_so_a_double_wrap_is_impossible(self):
        from statcheck.error_test import error_test
        assert getattr(error_test, "_fmt_sign_patched", False)

    def test_the_module_that_actually_calls_it_sees_the_patch(self):
        """`process_stats.py` does `from statcheck.error_test import
        error_test`, copying the function object into its own namespace at
        import time. Rebinding only the defining module would leave the real
        pipeline (st.statcheck -> process_stats) calling the broken original
        while a test on the defining module reported the patch as installed.

        This assertion is the reason the shim walks sys.modules; it failed on
        the first version.
        """
        import statcheck.process_stats as ps
        assert getattr(ps.error_test, "_fmt_sign_patched", False)

    def test_end_to_end_through_the_real_entry_point(self):
        """The control, unpatched, on the real pipeline:

            Value  Reported_P_Value  Computed_P_Value  Error
             -2.0             0.059          0.059266   True
              2.0             0.059          0.059266  False

        Identical computed p, identical reported p, opposite verdicts.
        """
        from statcheck.st import statcheck as run
        df, _ = run("An effect, t(20) = -2.00, p = .059. Another, "
                    "t(20) = 2.00, p = .059.")
        errors = list(df["Error"])
        assert len(errors) == 2
        assert errors[0] == errors[1] == False, (      # noqa: E712
            "the same statistic reported with each sign must get the same verdict")

    def test_a_non_numeric_statistic_falls_through_rather_than_crashing(self):
        from statcheck.error_test import error_test
        try:
            error_test(0.05, "t", "not-a-number", None, 20, "=", "=", 3, 1,
                       True, .05, True)
        except (TypeError, ValueError):
            pass          # the original's own behaviour; the shim must not add
                          # a new failure mode, and must not swallow this one
