"""The midpoint test assumes a Wald interval, and there was no way to say otherwise.

`check_estimate_ci` compares a point estimate against the arithmetic (or, for a
ratio measure, geometric) midpoint of its interval. That is exact only for a
Wald interval, `estimate +/- z*SE`. Bootstrap, exact, profile-likelihood,
bias-corrected, Fieller, Wilson and Bayesian intervals are all asymmetric BY
CONSTRUCTION -- and the function had no `interval_method` parameter, so the
premise could not be declared away.

Non-parametric bootstrap intervals are mandatory practice for skewed cost data
in health economics; exact and profile-likelihood intervals are routine in
epidemiology. The registry's integrity card already disclosed this in prose,
which is honest disclosure and not a guard.
"""

from __future__ import annotations

import pytest

from metascience_agent.tools.estimates import check_estimate_ci as check

# An honest incremental cost with a non-parametric bootstrap CI.
COST = dict(estimate=420.0, ci_low=95.0, ci_high=910.0, measure="mean_difference")
# An honest profile-likelihood risk difference.
RD = dict(estimate=3.1, ci_low=0.4, ci_high=8.9, measure="risk_difference")


class TestADeclaredAsymmetricMethodIsNotAnInconsistency:
    @pytest.mark.parametrize("method", [
        "bootstrap", "BCa bootstrap", "bias-corrected bootstrap",
        "percentile bootstrap", "exact", "Clopper-Pearson",
        "profile likelihood", "Fieller", "Wilson score", "Bayesian credible",
    ])
    def test_the_midpoint_test_does_not_fire(self, method):
        assert check(**COST, interval_method=method)["severity"] == "consistent"

    def test_it_says_the_test_was_skipped_rather_than_going_silent(self):
        r = check(**RD, interval_method="profile likelihood")
        assert any("midpoint test was not run" in n for n in r["notes"])

    def test_a_declared_wald_interval_still_fires(self):
        """Declaring the method truthfully must not become a way to switch the
        check off."""
        assert check(**COST, interval_method="wald")["severity"] == "suspicious"

    def test_an_unrecognised_method_does_not_silently_excuse(self):
        assert check(**COST, interval_method="some novel method")["severity"] \
            == "suspicious"


class TestUndeclaredKeepsTheCheckAndChangesTheWording:
    """Most papers do not name their CI method, and dropping the test then
    would lose a real transcription-error detector. What changes is that the
    problem names the innocent reading instead of asserting an inconsistency."""

    def test_the_severity_is_unchanged(self):
        assert check(**COST)["severity"] == "suspicious"

    def test_the_problem_names_the_innocent_reading(self):
        problems = " ".join(check(**COST)["problems"])
        assert "bootstrap" in problems
        assert "does not say which method" in problems
        assert "confirm the method" in problems

    def test_a_declared_method_does_not_carry_that_caveat(self):
        r = check(**COST, interval_method="wald")
        assert "does not say which method" not in " ".join(r["problems"])


class TestSymmetricIntervalsAreUntouched:
    def test_a_correct_wald_interval_is_consistent(self):
        assert check(estimate=5.0, ci_low=1.0, ci_high=9.0,
                     measure="mean_difference",
                     interval_method="wald")["severity"] == "consistent"

    def test_the_parameter_is_declared_so_the_model_can_pass_it(self):
        """A parameter the model cannot supply is dead weight."""
        from metascience_agent.registry import SPECS
        spec = next(s for s in SPECS if s.name == "check_estimate_ci")
        assert "interval_method" in [p.name for p in spec.params]


class TestTheRecoveredPCheckMakesTheSameWaldAssumption:
    """Found by REPLAY, not by reading: replaying 934 archived tool calls at
    HEAD showed 4 distinct `check_estimate_ci` calls going consistent ->
    suspicious, and the branch that fired was not the midpoint test.

    `se = (ln hi - ln lo) / (2z)` reconstructs the standard error by assuming
    the bounds sit z errors either side of the estimate -- true of a Wald
    interval and of no other kind. Against a bootstrap, exact,
    profile-likelihood or Fieller interval the recovered p is a quantity the
    paper never computed.

    I had guarded the branch the audit pointed at and left its neighbour, which
    rests on exactly the same assumption.
    """

    # A real archived call from 10.1001--jamanetworkopen.2023.51752.
    CALL = dict(estimate=0.793, ci_low=0.674, ci_high=0.934, measure="RR",
                reported_p=0.003)

    @pytest.mark.parametrize("method", [
        "bootstrap", "profile likelihood", "exact", "BCa bootstrap"])
    def test_a_declared_asymmetric_method_is_not_accused(self, method):
        assert check(**self.CALL, interval_method=method)["severity"] == "consistent"

    def test_it_says_the_check_was_skipped(self):
        r = check(**self.CALL, interval_method="bootstrap")
        assert any("recovered-p check was not run" in n for n in r["notes"])

    def test_a_declared_wald_interval_still_fires(self):
        assert check(**self.CALL, interval_method="wald")["severity"] == "suspicious"

    def test_undeclared_keeps_its_severity_and_names_the_reading(self):
        r = check(**self.CALL)
        assert r["severity"] == "suspicious"
        problems = " ".join(r["problems"])
        assert "inverts a WALD interval" in problems
        assert "confirm the method" in problems

    def test_the_midpoint_and_recovered_p_branches_agree(self):
        """Both rest on the same assumption, so both must respect the same
        declaration -- the omission this class exists for."""
        asym = check(**self.CALL, interval_method="bootstrap")
        assert asym["severity"] == "consistent"
        assert not asym["problems"]
