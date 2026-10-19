"""A tool pointed at the wrong kind of data must REFUSE, not accuse.

Every case below previously returned `severity: impossible` -- a
fabrication-grade claim produced purely by misapplication. The guards used to
live only in the rulebook prompt; `CLAUDE.md` conceded this explicitly. Prompts
are advisory, so these are now enforced in code and pinned here.
"""
import pytest

from forensic_metascience_ai_toolkit.tools import debit_test, grim_test
from forensic_metascience_ai_toolkit.tools.grim import grim_test_percentage
from forensic_metascience_ai_toolkit.tools.grimu import grimu_check, grimu_coexistence

NON_ACCUSATORY = {"indeterminate", "consistent", "suspicious"}


class TestGrimApplicability:
    @pytest.mark.parametrize(
        "mean,n,data_type",
        [
            (79.05, 30, "continuous"),   # a weight in kg
            (0.85, 100, "proportion"),   # a proportion
            (12.4, 50, "continuous"),    # continuous above the Likert default
            (5.2, 40, "unknown"),        # provenance unknown -> refuse
        ],
    )
    def test_non_integer_data_is_refused(self, mean, n, data_type):
        r = grim_test(mean, n, data_type=data_type)
        assert r["severity"] == "indeterminate"
        assert r["applicable"] is False

    @pytest.mark.parametrize("data_type", ["integer", "likert", "count"])
    def test_integer_data_is_still_evaluated(self, data_type):
        assert grim_test(5.51, 30, data_type=data_type,
                         discreteness_source="stated")["severity"] == "impossible"
        assert grim_test(3.53, 30, data_type=data_type)["severity"] == "consistent"


class TestGrimBoundSource:
    """Rulebook rule 4 -- a finding resting on a bound WE invented is weaker."""

    def test_assumed_bound_violation_is_capped_at_suspicious(self):
        r = grim_test(12.4, 50, data_type="count")  # default 1-7 scale is ours
        assert r["failure_mode"] == "out_of_range"
        assert r["severity"] == "suspicious"
        assert r["bound_source"] == "assumed"

    def test_stated_bound_violation_may_be_impossible(self):
        r = grim_test(12.4, 50, data_type="count", bound_source="stated")
        assert r["failure_mode"] == "out_of_range"
        assert r["severity"] == "impossible"

    def test_granularity_failure_is_labelled_distinctly(self):
        r = grim_test(5.51, 30, data_type="likert")
        assert r["failure_mode"] == "granularity"
        assert r["grim_consistent"] is False


class TestDebitApplicability:
    def test_non_binary_data_type_is_refused(self):
        r = debit_test(0.5, 0.5, 30, data_type="continuous")
        assert r["severity"] == "indeterminate"
        assert r["applicable"] is False

    def test_mean_outside_unit_interval_is_misapplication_not_finding(self):
        """debit_test(5.51, 1.2, 30) is a Likert mean -- refuse, don't accuse."""
        r = debit_test(5.51, 1.2, 30)
        assert r["severity"] == "indeterminate"
        assert r["applicable"] is False

    def test_n_below_two_is_a_guard_not_a_finding(self):
        assert debit_test(0.5, 0.5, 1)["severity"] == "indeterminate"

    def test_genuine_binary_impossibility_still_detected(self):
        assert debit_test(0.30, 0.30, 50)["severity"] == "impossible"


class TestGrimuApplicability:
    @pytest.mark.parametrize("test_type", ["t", "t-test", "f", "anova",
                                           "chi2", "chi-squared", "regression"])
    def test_a_non_rank_sum_p_is_refused(self, test_type):
        r = grimu_check(8, 8, "0.171", test_type=test_type)
        assert r["severity"] == "indeterminate"
        assert r["applicable"] is False

    def test_mann_whitney_is_still_evaluated(self):
        r = grimu_check(8, 8, "0.172", test_type="mann_whitney")
        assert r.get("applicable") is not False
        assert "error" not in r or r["severity"] != "indeterminate" or r.get("consistent") is not None

    def test_coexistence_refuses_the_wrong_test(self):
        r = grimu_coexistence(8, 8, ["0.171", "0.172"], test_type="t-test")
        assert r["severity"] == "indeterminate"
        assert r["applicable"] is False


class TestGrimUNormalApproximationZ:
    """MEASURED 2026-08-22 on 10.1016--j.compedu.2013.12.004, which prints
    `Z = 1.219, p = .223` and `Z = 1.259, p = .208` for Mann-Whitney tests on
    n1=21, n2=22. GRIM-U scored both as granularity misses and both were
    published at severity 2 against an honest paper -- while the findings' own
    notes recorded that statcheck reproduces each p exactly from the printed Z.

    A p rendered from a Z rounded to 3 dp lives on the image of THAT grid under
    2*Phi(-|z|), not on the U lattice. This is the grim_test/debit_test rule:
    a tool pointed at data it cannot speak about must REFUSE."""

    MEASURED = [(21, 22, "0.223", 1.219), (21, 22, "0.208", 1.259)]

    @pytest.mark.parametrize("n1,n2,p,z", MEASURED)
    def test_the_published_false_positives_now_refuse(self, n1, n2, p, z):
        r = grimu_check(n1, n2, p, decimals=3, reported_z=z)
        assert r["severity"] == "indeterminate"
        assert r["applicable"] is False
        assert r["failure_mode"] == "p_derived_from_normal_z"

    @pytest.mark.parametrize("n1,n2,p,z", MEASURED)
    def test_without_the_z_the_old_verdict_is_unchanged(self, n1, n2, p, z):
        """Pinning what the guard is FOR. Nothing about the lattice changed;
        the refusal is triggered by evidence the caller supplies."""
        assert grimu_check(n1, n2, p, decimals=3)["severity"] == "suspicious"

    def test_a_z_that_does_not_explain_the_p_does_not_excuse_it(self):
        """The guard checks its own precondition instead of trusting the label.
        A Z pasted beside an unrelated p must not buy an acquittal."""
        r = grimu_check(21, 22, "0.223", decimals=3, reported_z=3.9)
        assert r["severity"] == "suspicious"

    def test_p_source_refuses_without_the_z_itself(self):
        r = grimu_check(21, 22, "0.223", decimals=3, p_source="normal_z")
        assert r["severity"] == "indeterminate"
        assert r["applicable"] is False

    def test_the_matching_p_in_the_same_paper_refuses_too(self):
        """The third Mann-Whitney (`Z = 2.319, p = .020`) happened to land on
        the lattice. If the refusal did not cover it, the tool would be
        reporting Z-rounding luck as signal."""
        r = grimu_check(21, 22, "0.020", decimals=3, reported_z=2.319)
        assert r["severity"] == "indeterminate"


class TestGrimUTies:
    """The tie-corrected sdU is strictly smaller than the untied
    sqrt(n1*n2*(n1+n2+1)/12), so every achievable p moves. A rank test is
    usually reaching for a small-integer or ordinal outcome, where ties are
    near-certain."""

    def test_ties_refuse_the_granularity_branch(self):
        r = grimu_check(21, 22, "0.223", decimals=3, ties_possible=True)
        assert r["severity"] == "indeterminate"
        assert r["failure_mode"] == "ties_break_the_lattice"

    def test_ties_do_not_rescue_a_below_floor_p(self):
        """Ties cannot push U below 0, so the floor still binds. A guard that
        swallowed this would trade a false positive for a false negative."""
        r = grimu_check(4, 4, "0.0001", decimals=4, ties_possible=True)
        assert r["severity"] == "impossible"
        assert r["below_floor"] is True

    def test_coexistence_refuses_on_both_new_preconditions(self):
        for kw in ({"ties_possible": True}, {"p_source": "normal_z"}):
            r = grimu_coexistence(8, 8, ["0.171", "0.172"], **kw)
            assert r["severity"] == "indeterminate", kw
            assert r["applicable"] is False, kw


class TestCategoricalShares:
    """The n (%) of a category is a share of the sample, so GRIM on the
    percentage applies; a MEAN of a nominal category is still refused.

    Before 2026-10-18 anatomy declared such variables `nominal` (or `integer`
    for an ordinal category), `dispatch.DISPATCH` routed their n (%) cells to
    grim_percentage, and the tool refused every one as indeterminate.
    14 of 30 is 46.7%; 46.8% is attainable at no count of 30.
    """

    SEX = {"id": "sex", "name": "Sex", "family": "nominal_category",
           "measurement_level": "nominal", "discreteness": "discrete"}
    NYHA = {"id": "nyha", "name": "NYHA class", "family": "ordinal_category",
            "measurement_level": "ordinal", "discreteness": "discrete"}

    @staticmethod
    def _table(var, label, raw):
        from forensic_metascience_ai_toolkit import declared
        from forensic_metascience_ai_toolkit.dispatch import check_table
        try:
            return check_table([{"raw": raw, "row_label": label,
                                 "col_label": "All", "n": 30}],
                               [var], {label: var["id"]})
        finally:
            declared.clear()

    @pytest.mark.parametrize("data_type", ["nominal", "categorical",
                                           "nominal_category"])
    def test_a_category_share_is_evaluated(self, data_type):
        r = grim_test_percentage(46.8, 30, 1, data_type=data_type)
        assert r["severity"] == "impossible"
        assert r["failure_mode"] == "granularity"
        assert grim_test_percentage(46.7, 30, 1,
                                    data_type=data_type)["severity"] == "consistent"

    @pytest.mark.parametrize("data_type", ["nominal", "categorical"])
    def test_a_mean_of_a_category_is_still_refused(self, data_type):
        r = grim_test(5.51, 30, data_type=data_type, discreteness_source="stated")
        assert r["severity"] == "indeterminate"
        assert r["applicable"] is False

    def test_the_variable_record_still_describes_the_variable(self):
        """Only the percentage reading changes; a mean of ordinal codes is
        still integer data, and DISPATCH is keyed on the family's own type."""
        from forensic_metascience_ai_toolkit.dispatch import _as_variable
        for var, plain in ((self.SEX, "nominal"), (self.NYHA, "integer")):
            v = _as_variable(var)
            assert v.forensic_kwargs()["data_type"] == plain
            assert v.forensic_kwargs(share=True)["data_type"] == "proportion"
        cont = _as_variable({"id": "c", "name": "% change", "family": "continuous"})
        assert cont.forensic_kwargs(share=True)["data_type"] == "continuous"

    @pytest.mark.parametrize("var_key,label,raw", [
        ("SEX", "Male", "14 (46.8)"),
        ("NYHA", "Class III", "14 (46.8%)"),
        ("NYHA", "Class III", "14/30 (46.8)"),
    ])
    def test_the_table_path_reaches_grim_percentage(self, var_key, label, raw):
        r = self._table(getattr(self, var_key), label, raw)
        grim = [x for x in r["results"] if x["tool"] == "grim_percentage"]
        assert len(grim) == 1, r["not_run"]
        assert grim[0]["inputs"]["data_type"] == "proportion"
        assert grim[0]["severity"] == "impossible"
        assert grim[0]["result"]["failure_mode"] == "granularity"
        # The record agrees with the call, so nothing is downgraded to the
        # "least-licensing" unknown type.
        assert grim[0]["result"]["variable"]["status"] == "reconciled"

    def test_a_consistent_category_share_stays_consistent(self):
        r = self._table(self.SEX, "Male", "14 (46.7)")
        assert not [x for x in r["results"] if x["tool"] == "grim_percentage"
                    and x["severity"] != "consistent"]
        assert not r["not_run"]


def test_no_guard_path_ever_returns_impossible():
    """Sweep every misapplication in the agenda's table."""
    calls = [
        lambda: grim_test(79.05, 30, data_type="continuous"),
        lambda: grim_test(0.85, 100, data_type="proportion"),
        lambda: debit_test(5.51, 1.2, 30),
        lambda: debit_test(0.5, 0.5, 1),
        lambda: debit_test(0.5, 0.5, 30, data_type="continuous"),
        lambda: grimu_check(8, 8, "0.171", test_type="t-test"),
        lambda: grimu_coexistence(8, 8, ["0.171", "0.172"], test_type="anova"),
    ]
    offenders = [i for i, c in enumerate(calls) if c()["severity"] == "impossible"]
    assert offenders == [], f"misapplication still returns impossible: {offenders}"
