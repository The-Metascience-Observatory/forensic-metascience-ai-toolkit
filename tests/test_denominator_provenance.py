"""The third premise: whose denominator is this?

GRIM rests on three things -- the scale bounds, the discreteness of the
observations, and the DENOMINATOR. The first two are gated (`bound_source`,
`discreteness_source`). The third is an `n` the model read off a column header,
and an earlier audit ranked it ABOVE the other two in risk: the n analysed for a
single outcome is routinely smaller than the column's enrolled total, and GRIM at
the wrong denominator manufactures an impossibility out of an honest table.

Two real artifacts motivated the work: 13.04% is impossible at n = 22 and exact
at n = 23; 35.3% is impossible at n = 52 and exact at n = 51.

THE OBVIOUS FIX IS WRONG AND THE MEASUREMENT SAYS SO. See
`TestTheRescueWeDidNotShip`. This file exists as much to stop a future
implementation as to test the present one.
"""
import random

import pytest

from forensic_metascience_ai_toolkit.tools.grim import (
    DENOMINATOR_WINDOW, grim_test, nearby_denominators,
    percentage_reading_disagrees,
)


class TestNearbyDenominators:
    def test_the_motivating_artifact(self):
        """13.04 at n = 22 is exact at 23. That is what an off-by-one
        denominator looks like, and it is a question worth asking."""
        assert 23 in nearby_denominators(13.04, 22, 2)

    def test_the_second_artifact(self):
        assert 51 in nearby_denominators(35.3, 52, 1)

    def test_the_supplied_n_is_never_in_its_own_answer(self):
        assert 30 not in nearby_denominators(4.91, 30, 2)

    def test_it_stays_inside_the_window(self):
        near = nearby_denominators(4.91, 30, 2, window=DENOMINATOR_WINDOW)
        assert all(abs(x - 30) <= DENOMINATOR_WINDOW for x in near)

    def test_it_never_proposes_a_denominator_below_two(self):
        assert all(x >= 2 for x in nearby_denominators(1.5, 3, 1))

    def test_garbage_in_returns_empty_rather_than_raising(self):
        assert nearby_denominators(None, 30, 2) == []
        assert nearby_denominators(4.91, None, 2) == []


class TestItIsAQuestionNotARescue:
    """The severity must not move. Everything else here follows from that."""

    def _granularity_case_with_a_neighbour(self):
        random.seed(1)
        for _ in range(3000):
            mean = round(random.uniform(1.0, 7.0), 2)
            n = random.choice([22, 30, 41, 52])
            r = grim_test(mean, n, decimals=2, data_type="likert",
                          discreteness_source="stated")
            if r.get("failure_mode") == "granularity" and r.get("denominator_question"):
                return mean, n, r
        pytest.skip("no case found in the search budget")

    def test_the_verdict_is_unchanged(self):
        mean, n, r = self._granularity_case_with_a_neighbour()
        assert r["severity"] == "impossible"
        assert r["failure_mode"] == "granularity"
        assert r["denominator_question"]["severity_unchanged"] is True

    def test_it_names_the_denominator_that_would_fit(self):
        mean, n, r = self._granularity_case_with_a_neighbour()
        dq = r["denominator_question"]
        assert dq["n_tested"] == n
        assert dq["n_that_would_fit"]
        assert all(nn != n for nn in dq["n_that_would_fit"])

    def test_it_is_phrased_as_a_question_to_the_authors(self):
        """Answerable, specific, presupposing no wrongdoing -- the same bar the
        author-questions schema sets."""
        _m, _n, r = self._granularity_case_with_a_neighbour()
        ask = r["denominator_question"]["ask"]
        assert "Ask which n" in ask
        for accusatory in ("fabricat", "wrong", "error", "false"):
            assert accusatory not in ask.lower()

    def test_it_carries_its_own_disclaimer(self):
        """A reader who sees 'this works at n = 32' will treat it as exculpatory
        unless told otherwise, and at these sample sizes it is not."""
        _m, _n, r = self._granularity_case_with_a_neighbour()
        not_ev = r["denominator_question"]["not_evidence"]
        assert "70-80%" in not_ev
        assert "not a reason to withdraw" in not_ev

    def test_a_robustly_impossible_value_gets_no_question_at_all(self):
        """5.51 at n = 30 fits at no denominator in the window, which is why it
        is this repo's canonical GRIM case. Offering an empty question would
        imply a doubt that does not exist."""
        r = grim_test(5.51, 30, decimals=2, data_type="likert",
                      discreteness_source="stated")
        assert r["failure_mode"] == "granularity"
        assert "denominator_question" not in r

    def test_a_consistent_value_gets_no_question(self):
        r = grim_test(5.0, 30, decimals=2, data_type="likert")
        assert "denominator_question" not in r


class TestTheRescueWeDidNotShip:
    """MEASURED NEGATIVE. Do not turn this diagnostic into a de-escalation.

    De-escalating any granularity failure that fits at a nearby n would not be a
    diagnosis, it would be an off switch. This test re-runs the measurement, at
    reduced scale, so the number is in the suite rather than only in a commit
    message -- the argument for shipping the rescue is seductive and will be
    made again.
    """

    @pytest.mark.parametrize("n,floor", [(20, 0.5), (30, 0.6), (50, 0.5)])
    def test_most_genuine_failures_also_fit_at_a_nearby_n(self, n, floor):
        random.seed(0)
        fails = rescued = 0
        for _ in range(600):
            mean = round(random.uniform(1.0, 7.0), 2)
            r = grim_test(mean, n, decimals=2, data_type="likert",
                          discreteness_source="stated")
            if r.get("failure_mode") == "granularity":
                fails += 1
                if nearby_denominators(mean, n, 2):
                    rescued += 1
        assert fails > 50, "the sweep must actually produce failures to measure"
        share = rescued / fails
        assert share > floor, (
            f"at n={n}, {share:.0%} of genuine GRIM failures fit at a nearby n. "
            "If this ever drops far below the measured 70-80%, re-run the full "
            "sweep before concluding a rescue is now safe."
        )

    def test_grim_has_no_power_at_all_at_large_n_and_two_decimals(self):
        """The same sweep returned ZERO failures at n >= 80. Worth knowing
        before anyone quotes a clean GRIM result on a large table as evidence of
        anything."""
        random.seed(0)
        fails = sum(
            1 for _ in range(400)
            if grim_test(round(random.uniform(1.0, 7.0), 2), 120, decimals=2,
                         data_type="likert",
                         discreteness_source="stated").get("failure_mode") == "granularity"
        )
        assert fails == 0


class TestEveryCheckSaysWhereItsDenominatorCameFrom:
    def test_an_ordinary_supplied_n_is_recorded(self):
        from forensic_metascience_ai_toolkit.dispatch import check_table
        out = check_table(
            [{"raw": "5.51 (1.20)", "row_label": "Anxiety", "n": 30}],
            [{"id": "v1", "family": "likert_item", "lower_bound": 1,
              "upper_bound": 7}],
            {"Anxiety": "v1"})
        rec = (out.get("results") or [{}])[0]
        prov = rec.get("n_provenance") or {}
        assert prov.get("derived") is False
        assert prov.get("n") == 30
        assert "enrolled total" in prov.get("note", "")

    def test_an_n_printed_in_the_cell_label_says_so(self):
        """`n = 30` in a column header is weak evidence, but it is evidence, and
        it is different from an n we cannot see the source of at all."""
        from forensic_metascience_ai_toolkit.dispatch import check_table
        out = check_table(
            [{"raw": "5.51 (1.20)", "row_label": "Anxiety",
              "col_label": "Treatment (n = 30)", "n": 30}],
            [{"id": "v1", "family": "likert_item"}], {"Anxiety": "v1"})
        rec = (out.get("results") or [{}])[0]
        prov = rec.get("n_provenance") or {}
        assert prov.get("how") == "printed_in_a_label"
        assert 30 in (prov.get("in_cell_labels") or [])

    def test_the_derived_case_still_caps_and_still_says_so(self):
        """The reconstructed denominator was already documented and capped. This
        change must not have quietly replaced that with the weaker stamp."""
        from forensic_metascience_ai_toolkit.dispatch import _stamp_derived_n
        rec = {"severity": "impossible"}
        _stamp_derived_n(rec, {"n": 100, "n_source": "sum", "section": "S",
                               "column": "C"})
        assert rec["n_provenance"]["derived"] is True
        assert rec["severity"] != "impossible"
        assert rec["severity_uncapped"] == "impossible"


class TestThePercentageAsMeanFalseClear:
    """A false clear, found by replaying the archive.

    The model sent the SAME statistic to the same tool in both forms:

        mean = 0.183, n = 12, 3 dp  ->  not consistent
        mean = 18.3,  n = 12, 1 dp  ->  CONSISTENT

    Both describe 18.3% of 12. A mean of 12 integers moves in steps of
    1/12 = 0.083, so 18.3 is reachable (220/12 = 18.333). A PERCENTAGE of 12
    units moves in steps of 100/12 = 8.3 POINTS -- attainable values are 0, 8.3,
    16.7, 25.0, and 18.3 is not among them. Feeding a percentage to a mean-GRIM
    divides the granularity by 100 and clears almost anything.
    """

    def test_the_two_readings_genuinely_disagree(self):
        from forensic_metascience_ai_toolkit.tools.grim import _mean_passes_grim
        assert _mean_passes_grim(18.3, 12, 1)[0] is True      # as a mean
        assert percentage_reading_disagrees(18.3, 12, 1) is not None               # not as a percentage

    def test_the_caveat_survives_the_no_power_exit(self):
        """The mean reading at n = 12 and 1 dp has NO discriminating power, so
        this no longer returns `consistent` -- calling it that was a second
        false clear on top of the one this class was written for.

        The caveat must survive that exit anyway, because it is a DIFFERENT
        check with its own power: it asks whether 0.183 is attainable at 3 dp,
        where 98.8% of the grid is rejected. An early return that dropped it
        would have deleted the fix that found the original false clear.
        """
        r = grim_test(18.3, 12, decimals=1, data_type="count", scale_min=0,
                    scale_max=200, discreteness_source="stated")
        assert r["severity"] == "indeterminate"
        assert r["failure_mode"] == "no_discriminating_power"
        assert r["percentage_reading"]["reading"] == "percentage"
        assert "8.33 percentage points" in r["percentage_reading"]["note"]

    def test_it_names_the_tool_that_asks_the_right_question(self):
        r = grim_test(9.6, 93, decimals=1, data_type="count", scale_min=0,
                    scale_max=200, discreteness_source="stated")
        assert "grim_percentage" in r["percentage_reading"]["note"]

    def test_a_stated_scale_containing_the_value_settles_it(self):
        """5.0 on the PAPER'S OWN 1-7 scale is a mean, full stop. Firing there
        would put this caveat on every ordinary Likert mean -- 5.0% of 30 is not
        attainable either, and saying so is noise."""
        r = grim_test(5.0, 30, decimals=2, data_type="likert", scale_min=1,
                    scale_max=7, bound_source="stated", discreteness_source="stated")
        assert r["severity"] == "consistent"
        assert "percentage_reading" not in r

    def test_a_scale_WE_assumed_cannot_settle_it(self):
        """A bound we invented rules nothing out, so the caveat stands -- the
        safe direction."""
        r = grim_test(5.0, 30, decimals=2, data_type="likert", scale_min=1,
                    scale_max=7, bound_source="assumed", discreteness_source="stated")
        assert r.get("percentage_reading") is not None

    def test_a_value_above_100_cannot_be_a_percentage(self):
        assert percentage_reading_disagrees(120.0, 30, 1) is None

    def test_a_value_at_or_below_1_is_already_a_proportion(self):
        assert percentage_reading_disagrees(0.183, 12, 3) is None

    def test_no_caveat_when_both_readings_agree(self):
        """16.7% IS attainable at n = 12 (2/12), so there is no disagreement to
        report and the caveat would be pure noise."""
        assert percentage_reading_disagrees(16.7, 12, 1) is None

    def test_it_never_ACCUSES(self):
        """18.3 is a perfectly ordinary mean -- a FIM score, a count of days. We
        cannot tell from the number which it is, and refusing every mean above 1
        would disable the tool on most clinical data. So the caveat may inform
        and must never convict.

        `consistent` is what the mean reading returns; here the verdict is
        `indeterminate` for the unrelated reason that GRIM has no power at
        n = 12 and 1 dp. Either way the caveat has not produced an accusation,
        which is the property under test."""
        r = grim_test(18.3, 12, decimals=1, data_type="count", scale_min=0,
                    scale_max=200, discreteness_source="stated")
        assert r["consistent"] is True
        assert r["severity"] not in ("impossible", "highly_suspicious", "suspicious")

    def test_garbage_in_returns_none(self):
        assert percentage_reading_disagrees(None, 12, 1) is None
        assert percentage_reading_disagrees(18.3, 0, 1) is None
        assert percentage_reading_disagrees(18.3, 12, None) is None


class TestTheEqualsSignAsThePDFEncodedIt:
    """Older Springer PDFs render `=` as `¼` -- a Type-1 font-encoding
    artifact, not an OCR guess -- so `n = 68` reaches us as `n ¼ 68`. MEASURED
    over the 305-paper cerebrolysin corpus: 16 papers (5.2%) contain
    `n ¼ <digit>`, 107 occurrences.

    On 10.1007--s00702-004-0248-2 the column header reads `Placebo (n ¼ 68)`,
    so the denominator printed directly above the cells was unreadable and
    every percentage refusal on that paper said only "this cell carries none".
    """

    def test_the_corrupted_form_is_read_as_a_denominator(self):
        from forensic_metascience_ai_toolkit.dispatch import _N_IN_LABEL, _HEADER_N
        from forensic_metascience_ai_toolkit.composite import _HEADER_N as COMPOSITE_N
        for pattern in (_N_IN_LABEL, _HEADER_N, COMPOSITE_N):
            assert pattern.findall("Placebo (n ¼ 68)") == ["68"], pattern.pattern
            assert pattern.findall("Placebo (n = 68)") == ["68"], pattern.pattern

    def test_one_quarter_is_still_one_quarter(self):
        """`¼` is not a character this codebase may rewrite on sight --
        `celltypes._UNICODE_REPAIRS` is deliberately not the place for it.
        Between an `n` and a digit it can mean nothing else; anywhere else it
        means a quarter."""
        from forensic_metascience_ai_toolkit.dispatch import _N_IN_LABEL
        assert _N_IN_LABEL.findall("improvement in ¼ of patients") == []
        assert _N_IN_LABEL.findall("¼ 68") == []

    def test_it_does_not_make_a_refused_check_run(self):
        """The repair improves the REFUSAL, it does not supply the n.
        `_refusal_reason`'s own docstring: "a candidate is help; using it
        unasked is the false accusation this module exists to prevent." An
        enrolled total is not the n behind a given row, and these checks accuse
        when n is too large."""
        from forensic_metascience_ai_toolkit.dispatch import check_table
        cells = [{"raw": "47 (60.3)", "row": 4, "row_label": "Female",
                  "col_label": "Placebo (n ¼ 68)"}]
        variables = [{"id": "v1", "name": "Female", "family": "binary",
                      "lower_bound": 0, "upper_bound": 1}]
        out = check_table(cells=cells, variables=variables,
                          bindings={"Female": "v1"})
        assert out["n_checks_run"] == 0
        reasons = " ".join(x.get("reason", "") for x in out["not_run"])
        # ...but the refusal now names the number and says how to use it.
        assert "n = 68" in reasons and "Pass n=68" in reasons
