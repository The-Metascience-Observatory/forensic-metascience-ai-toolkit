"""The five defects a fourth adversarial pass found in the checks bridge, pinned.

THE PAPER IS NEW AND SO ARE THE ATTACKS. "The Ashcombe trial" shares nothing
with the Delta trial of `test_scaffold_checks_adversarial.py` or the Harborview
study of `test_scaffold_checks_round3.py`: a different design, different
variables, and attacks aimed at the two premises those rounds did not touch --
what the paper says its numbers ARE (a mean of whole-point ratings, a weighted
percentage, a model coefficient) and how many subjects each one is over.

Every number in every fixture below is arithmetically consistent with the paper
that prints it -- the three summarised means were computed from real per-subject
datasets and the missingness mean from 46 real whole-point scores -- so any
verdict worse than `consistent` or `indeterminate` is a false accusation by
construction.

The five, and where each is fixed:

  B  the discreteness gate is a KEYWORD TEST and ignores AGGREGATION vocabulary
     in the same span, so `the child's score is the mean of the two assessors'
     whole-point ratings` bought `discreteness_source: stated`
     (`premises.AVERAGED`, vetoing the clause and the kind's own licence)
  D  a survey-weighted or age-standardised percentage is not the printed count's
     own quotient, and nothing the paper could say stopped the check
     (`premises.WEIGHTED_PERCENTAGE`)
  F  the model-output guard misses the four commonest regression captions, and
     the headers a regression table carries when it prints no estimate symbol
     (`premises._MODEL_TABLE`, `premises._MODEL_HEADER`, `premises.table_notes`)
  I  item-level missingness: the analysis n the paper ANNOUNCES is ignored and
     the group n is bound instead (`premises.varying_n_statement`, refused as
     `per_row_n_not_captured` -- the gap the vocabulary already named)
  J  `evaluate(..., families=("no_such_family",))` raised `KeyError` outside
     every per-candidate try/except, so the run produced no checks and no docket

Plus the coverage regression the independent re-derivation found beside them:
one sentence may state ONE scale for TWO variables, and the attribution tie
refused both (`premises.bounds_verification._shared_scale`).
"""

from __future__ import annotations

import pytest

from forensic_metascience_ai_toolkit.scaffold import checks, premises

BAD = {"suspicious", "highly_suspicious", "impossible"}


# --------------------------------------------------------------------------
# builders
# --------------------------------------------------------------------------


def var(vid, name, kind, *, bsource="not_stated", lower=None, upper=None,
        bquote=None, step=None, gquote=None, label=None):
    return {"id": vid, "name": name, "label": label if label is not None else name,
            "printed_as": [], "kind": kind, "role": None,
            "bounds": {"source": bsource, "lower": lower, "upper": upper,
                       "quote": bquote},
            "granularity": {"per_subject_step": step, "quote": gquote}}


def cell(vid, statistic, printed, *, table="table:1", row=1, col=1, col_label=None,
         variable_id=None, group="grp:all"):
    lit = premises.read_plain(printed) or {}
    return {"id": vid, "statistic": statistic, "printed": printed,
            "numeric": lit.get("value"), "decimals": lit.get("decimals", 0),
            "printed_form": "percent" if lit.get("is_percent") else "plain",
            "units": None, "variable_id": variable_id, "id_check": "agrees",
            "statistic_disputed": False, "source": "table", "quote": None,
            "quote_verified": "cell", "printed_in_quote": None,
            "location": {"kind": "table_cell", "table_id": table, "row": row,
                         "col": col, "col_label": col_label},
            "coordinate": {"study_id": "study:main", "group_id": group,
                           "phase_id": None}}


def prose(vid, statistic, printed, quote, *, variable_id=None, group="grp:all",
          id_check="agrees"):
    lit = premises.read_plain(printed) or {}
    return {"id": vid, "statistic": statistic, "printed": printed,
            "numeric": lit.get("value"), "decimals": lit.get("decimals", 0),
            "printed_form": "percent" if lit.get("is_percent") else "plain",
            "units": None, "variable_id": variable_id, "id_check": id_check,
            "statistic_disputed": False, "source": "prose", "quote": quote,
            "quote_verified": "verbatim", "printed_in_quote": True,
            "location": {"kind": "prose", "offset": 0, "col_label": None},
            "coordinate": {"study_id": "study:main", "group_id": group,
                           "phase_id": None}}


def account(*, groups=None, variables=None, values=None, tables=None):
    return {"paper": {"doi": "10.0000/ashcombe", "title": "The Ashcombe trial"},
            "studies": [{"id": "study:main", "design": "parallel_rct",
                         "groups": groups if groups is not None
                         else [{"id": "grp:all", "label": "All participants",
                                "n": 48, "n_source": "text"}]}],
            "variables": variables or [], "values": values or [],
            "document": {"tables": tables or [
                {"id": "table:1", "caption": "Table 1. Baseline characteristics."}]}}


def accusations(got):
    return [(r["check_id"], r["severity"], r["result"].get("failure_mode"))
            for r in got["checks"] if r["severity"] in BAD]


def refusals(got):
    return {r["check_id"]: r["reason"] for r in got["refused"]}


def every_reason(got):
    return {row["reason"] for r in got["refused"] for row in r["reasons"]}


N_48 = prose("val:n", "n", "48",
             "Forty-eight children were analysed; the analysed sample was n = 48.",
             id_check=None)


# --------------------------------------------------------------------------
# B -- THE DISCRETENESS PREMISE AND THE AVERAGE
# --------------------------------------------------------------------------

#: (name, text, variable kwargs, mean, sd). Each mean/SD pair was computed from a
#: real per-subject dataset with the paper's own granularity, so the paper
#: printed nothing wrong; the step is 0.05, 0.5 and 1/3 respectively and GRIM's
#: premise of 1 is false in all three.
AVERAGES = [
    ("a mean item score, 20 items rated 1-5",
     "The Caregiver Burden Inventory comprises twenty items and each item is "
     "rated in whole points from 1 to 5, and a caregiver's score is the mean of "
     "that caregiver's twenty item ratings.",
     "Caregiver Burden Inventory score", 1, 5,
     "each item is rated in whole points from 1 to 5", "3.03", "0.34"),
    ("the mean of two whole-point raters",
     "Two independent assessors each rated inhaler technique in whole points "
     "from 0 to 10, and the child's score is the mean of the two assessors' "
     "whole-point ratings.",
     "inhaler technique score", 0, 10,
     "rated inhaler technique in whole points from 0 to 10", "4.86", "2.13"),
    ("the average of three whole-count trials",
     "On each of three attempts the number of correctly completed steps was "
     "counted in whole steps, from 0 to 12, and the child's score is the "
     "average of the three attempts.",
     "correctly completed steps", 0, 12,
     "counted in whole steps, from 0 to 12", "6.28", "1.95"),
]


def _averaged_account(sentence, name, lo, hi, bquote, mean, sd, gquote, *,
                      kind="integer_score"):
    text = ("# The Ashcombe trial\n\n## Methods\n\n"
            "Forty-eight children were analysed; the analysed sample was n = 48.\n"
            + sentence + "\n\n## Results\n\n"
            + f"The mean {name} was {mean} (SD {sd}).\n")
    v = var("var:x", name, kind, bsource="stated", lower=lo, upper=hi,
            bquote=bquote, step=1, gquote=gquote)
    said = f"The mean {name} was {mean} (SD {sd})."
    vals = [N_48,
            prose("val:mean", "mean", mean, said, variable_id="var:x"),
            prose("val:sd", "sd", sd, said, variable_id="var:x")]
    return account(variables=[v], values=vals), text


class TestASentenceThatSaysMeanEstablishesNoStep:
    @pytest.mark.parametrize("tag,sentence,name,lo,hi,bquote,mean,sd", AVERAGES)
    @pytest.mark.parametrize("form", ["the paper's whole sentence", "the narrow clause"])
    def test_the_three_summarisation_conventions_accuse_nobody(
            self, tag, sentence, name, lo, hi, bquote, mean, sd, form):
        """The sharpest false accusation of round 4, in its three shapes.

        The paper's sentence is TRUE -- the ratings ARE whole points -- and the
        thing it summarises is not. Offered whole, and offered as the narrow
        clause a reading might lift out of it, both must refuse."""
        gquote = sentence if form == "the paper's whole sentence" else bquote
        acc, text = _averaged_account(sentence, name, lo, hi, bquote, mean, sd, gquote)
        got = checks.evaluate(acc, text)
        assert accusations(got) == []
        assert "discreteness_quote_reports_an_average" in every_reason(got)

    @pytest.mark.parametrize("tag,sentence,name,lo,hi,bquote,mean,sd", AVERAGES)
    def test_the_step_is_never_stamped_stated(self, tag, sentence, name, lo, hi,
                                              bquote, mean, sd):
        acc, text = _averaged_account(sentence, name, lo, hi, bquote, mean, sd, sentence)
        rec = premises.stamp(acc, text)["variables"][0]["granularity"]["verification"]
        assert rec["discreteness_source"] == premises.ASSUMED_DISCRETENESS
        assert rec["establishes_step_of_one"] is False
        assert rec["quote_reports_an_average"]

    def test_the_kinds_own_licence_is_withdrawn_by_the_same_sentence(self):
        """A `count` needs no sentence at all -- and a sentence saying the
        reported quantity is the MEAN of three counts contradicts the kind as
        surely as a printed 2.40 on a `binary` does."""
        sentence = ("On each of three attempts the number of correctly completed "
                    "steps was counted in whole steps, and the child's score is "
                    "the average of the three attempts.")
        acc, text = _averaged_account(
            sentence, "correctly completed steps", 0, 12,
            "counted in whole steps", "6.28", "1.95", sentence, kind="count")
        rec = premises.stamp(acc, text)["variables"][0]["granularity"]["verification"]
        assert rec["kind"] == "count"
        assert rec["kind_makes_it_necessary"] is False
        assert accusations(checks.evaluate(acc, text)) == []

    def test_an_ordinary_whole_point_sentence_still_establishes_the_step(self):
        """THE COST SIDE, ASSERTED. A guard that bought its safety by refusing
        every paper would pass every test above and be worthless."""
        text = ("# The Ashcombe trial\n\n## Methods\n\n"
                "Forty-eight children were analysed; the analysed sample was n = 48.\n"
                "The Asthma Control Test is scored from 5 to 25 in whole points, "
                "and each child contributed one whole-point score.\n\n"
                "## Results\n\nThe mean Asthma Control Test score was 18.50 (SD 3.40).\n")
        q = ("The Asthma Control Test is scored from 5 to 25 in whole points, "
             "and each child contributed one whole-point score.")
        v = var("var:act", "Asthma Control Test score", "integer_score",
                bsource="stated", lower=5, upper=25,
                bquote="The Asthma Control Test is scored from 5 to 25 in whole points",
                step=1, gquote=q)
        said = "The mean Asthma Control Test score was 18.50 (SD 3.40)."
        acc = account(variables=[v], values=[
            N_48, prose("val:m", "mean", "18.50", said, variable_id="var:act"),
            prose("val:s", "sd", "3.40", said, variable_id="var:act")])
        got = checks.evaluate(acc, text)
        assert accusations(got) == []
        ran = {r["check_id"]: r["args"].get("discreteness_source") for r in got["checks"]}
        assert ran.get("chk:grim:val:m") == premises.STATED_DISCRETENESS

    def test_a_sum_of_whole_points_is_still_a_whole_number(self):
        """A SUM IS NOT AN AVERAGE, and the veto must not swallow the commonest
        honest composite there is: a total score built from whole-point items."""
        assert not premises.AVERAGED.search(
            "the total score is the sum of the nine item scores, each rated 0 to 3 "
            "in whole points")

    @pytest.mark.parametrize("sentence", [
        "Participants attended a mean of 3.4 visits.",
        "Body mass averaged 78.4 kg.",
        "attendance averaged 82.5% of scheduled sessions",
        "The mean number of disturbed nights was 4.90.",
    ])
    def test_a_reported_summary_is_not_a_definition(self, sentence):
        """`a mean of 3.4 visits` is what EVERY results sentence looks like.
        Vetoing on it would cost the honest papers this gate exists to keep."""
        assert not premises.AVERAGED.search(sentence)

    def test_the_veto_is_clause_scoped(self):
        """An averaging clause about ANOTHER variable does not withdraw this
        variable's step -- the same rule the establishing clause is held to."""
        text = ("# The Ashcombe trial\n\n## Methods\n\n"
                "Forty-eight children were analysed; the analysed sample was n = 48.\n"
                "Mood was rated on a 1 to 7 point scale and was scored in whole "
                "points; the fidelity index is the mean of four item ratings.\n\n"
                "## Results\n\nThe mean mood score was 4.10 (SD 1.20).\n")
        v = var("var:mood", "Mood", "integer_score", bsource="stated", lower=1,
                upper=7, bquote="Mood was rated on a 1 to 7 point scale", step=1,
                gquote="Mood was rated on a 1 to 7 point scale and was scored in "
                       "whole points")
        rec = premises.stamp(account(variables=[v]), text)[
            "variables"][0]["granularity"]["verification"]
        assert rec["quote_reports_an_average"] is None
        assert rec["discreteness_source"] == premises.STATED_DISCRETENESS


# --------------------------------------------------------------------------
# D -- THE WEIGHTED PERCENTAGE
# --------------------------------------------------------------------------

WEIGHTED_METHODS = """# The Ashcombe trial: district prevalence substudy

## Methods

Forty-eight children were analysed; the analysed sample was n = 48.
{methods}

## Results

Twelve children had a physician diagnosis of atopy; {result}
"""


def _weighted(col_label, caption, *, methods="Counts and percentages are reported.",
              result="the prevalence was 31.4%.", printed="31.4"):
    text = WEIGHTED_METHODS.format(methods=methods, result=result)
    v = var("var:atopy", "atopy", "percentage_of_subjects")
    vals = [N_48,
            cell("val:cnt", "count", "12", table="table:3", row=2, col=1,
                 col_label=col_label, variable_id="var:atopy"),
            cell("val:pct", "percentage", printed, table="table:3", row=2, col=1,
                 col_label=col_label, variable_id="var:atopy")]
    acc = account(variables=[v], values=vals,
                  tables=[{"id": "table:3", "caption": caption}])
    return checks.evaluate(acc, text)


class TestAWeightedPercentageIsNotTheCountsOwnQuotient:
    """12 of 48 children have atopy (25.0% unweighted); weighted to the district
    the prevalence is 31.4%. Both numbers are right and `12/48` is not 31.4%."""

    @pytest.mark.parametrize("tag,col_label,caption,extra", [
        ("column band and caption", "No. (weighted %)",
         "Table 3. Characteristics, No. (weighted %). Percentages are weighted to "
         "the school-district population; counts are unweighted.", {}),
        ("caption only", "No. (%)",
         "Table 3. Characteristics. Percentages are weighted to the "
         "school-district population; counts are unweighted.", {}),
        ("Methods only", "n (%)", "Table 3. Characteristics of the children.",
         {"methods": "Percentages are weighted to the school-district population "
                     "using the survey design weights; counts are unweighted."}),
        ("age-standardized", "No. (age-standardized %)",
         "Table 3. Characteristics, No. (age-standardized %).", {}),
        ("design-adjusted", "No. (adjusted %)",
         "Table 3. Characteristics, No. (adjusted %).", {}),
    ])
    def test_nothing_the_paper_says_is_ignored(self, tag, col_label, caption, extra):
        got = _weighted(col_label, caption, **extra)
        assert accusations(got) == []
        assert refusals(got).get("chk:count_percent:val:pct") == "percentage_is_weighted"

    def test_the_papers_own_sentence_says_it_in_prose(self):
        text = WEIGHTED_METHODS.format(
            methods="Counts and percentages are reported.",
            result="the weighted prevalence was 31.4%.")
        said = ("Twelve children had a physician diagnosis of atopy; the weighted "
                "prevalence was 31.4%.")
        v = var("var:atopy", "atopy", "percentage_of_subjects")
        acc = account(variables=[v], values=[
            N_48, prose("val:cnt", "count", "12", said, variable_id="var:atopy"),
            prose("val:pct", "percentage", "31.4%", said, variable_id="var:atopy")])
        got = checks.evaluate(acc, text)
        assert accusations(got) == []
        assert refusals(got).get("chk:count_percent:val:pct") == "percentage_is_weighted"

    def test_an_ordinary_unweighted_table_still_runs(self):
        """THE COST SIDE. 12 of 48 is 25.0%, and it must still be checked."""
        got = _weighted("No. (%)", "Table 3. Characteristics of the children.",
                        printed="25.0")
        assert accusations(got) == []
        ran = {r["check_id"] for r in got["checks"]}
        assert "chk:count_percent:val:pct" in ran

    def test_the_count_itself_is_not_withdrawn(self):
        """The weighting is a fact about the ESTIMATOR, and the count is not it.
        Refusing the count too would remove it from every other family for a
        reason that is not about it."""
        got = _weighted("No. (weighted %)", "Table 3. Characteristics.")
        acc_used = None
        for row in got["refused"]:
            if row["check_id"] == "chk:count_percent:val:pct":
                acc_used = {r["where"] for r in row["reasons"]
                            if r["reason"] == "percentage_is_weighted"}
        assert acc_used == {"val:pct"}


# --------------------------------------------------------------------------
# F -- THE MODEL-OUTPUT GUARD
# --------------------------------------------------------------------------

F_TEXT = """# The Ashcombe trial: predictors of asthma control

## Methods

Forty-eight children were analysed; the analysed sample was n = 48.
The Asthma Control Test is scored from 5 to 25 in whole points, and each child
contributed one whole-point score.

## Results

The model is given in the table.
"""

F_VAR = var("var:act", "Asthma Control Test score", "integer_score",
            bsource="stated", lower=5, upper=25,
            bquote="The Asthma Control Test is scored from 5 to 25 in whole points",
            step=1,
            gquote="The Asthma Control Test is scored from 5 to 25 in whole "
                   "points, and each child contributed one whole-point score.")


def _coefficient_table(col_label, caption, text=F_TEXT):
    """8.57 really is the coefficient and 3.03 really is its standard error.
    Read as a mean and an SD of a 5-25 whole-point outcome, 8.57 x 48 = 411.36
    and GRIM returns `impossible`."""
    vals = [N_48,
            cell("val:b", "mean", "8.57", table="table:4", row=2, col=1,
                 col_label=col_label, variable_id="var:act"),
            cell("val:se", "sd", "3.03", table="table:4", row=2, col=1,
                 col_label=col_label, variable_id="var:act")]
    acc = account(variables=[F_VAR], values=vals,
                  tables=[{"id": "table:4", "caption": caption}])
    return checks.evaluate(acc, text)


class TestTheGuardReadsTheCaptionsAPaperActuallyPrints:
    @pytest.mark.parametrize("caption", [
        "Table 4. Mixed-effects model for week-12 Asthma Control Test score.",
        "Table 4. Multivariable model, week-12 Asthma Control Test score.",
        "Table 4. Adjusted mean difference in week-12 Asthma Control Test score.",
        "Table 4. ANCOVA for week-12 Asthma Control Test score, adjusted for baseline.",
        "Table 4. Generalized estimating equations for week-12 asthma control.",
        "Table 4. Cox proportional hazards model for time to first exacerbation.",
    ])
    @pytest.mark.parametrize("label", [None, "Adjusted", "Model 2", "Difference"])
    def test_an_explicit_model_caption_guards_every_ordinary_header(self, caption, label):
        got = _coefficient_table(label, caption)
        assert accusations(got) == []
        assert every_reason(got) >= {"reports_model_output"}

    @pytest.mark.parametrize("label", ["(1)", "Adjusted", "Crude", "Model 2",
                                       "Difference", "Mean difference",
                                       "Intervention vs control", "Model"])
    def test_a_model_or_contrast_header_needs_no_caption_at_all(self, label):
        got = _coefficient_table(label, "Table 4.", text=F_TEXT.replace(
            "The model is given in the table.", "The results are in the table."))
        assert accusations(got) == []
        assert every_reason(got) >= {"reports_model_output"}

    def test_the_papers_own_sentence_about_the_table_is_read(self):
        """A bare caption and no column label at all -- and the Results section
        saying, in the paper's own words, what Table 4 is."""
        text = F_TEXT.replace(
            "The model is given in the table.",
            "Table 4 gives the multivariable model for week-12 Asthma Control "
            "Test score.")
        got = _coefficient_table(None, "Table 4.", text=text)
        assert accusations(got) == []
        assert every_reason(got) >= {"reports_model_output"}

    def test_one_segment_and_not_the_whole_sentence(self):
        """`Table 4 shows the characteristics; the models are in Table 5` must
        not lend Table 5's word to Table 4."""
        notes = premises.table_notes(
            {"table:4": "Table 4. Characteristics.", "table:5": "Table 5. Estimates."},
            "Table 4 shows the characteristics; the models are in Table 5.")
        assert "table:4" not in notes
        assert "table:5" in notes

    @pytest.mark.parametrize("caption,label", [
        ("Table 1. Baseline characteristics of the analysed children.", "Mean (SD)"),
        ("Table 1. Characteristics by school.", "n (%)"),
        ("Table 2. Asthma Control Test score at each visit.", "M (SD)"),
    ])
    def test_a_descriptive_table_is_untouched(self, caption, label):
        """THE COST SIDE. A guard that answered yes to every table would pass
        every test above and remove all descriptive coverage."""
        said = "The mean Asthma Control Test score was 18.50 (SD 3.40)."
        text = F_TEXT.replace("The model is given in the table.", said)
        vals = [N_48,
                cell("val:m", "mean", "18.50", table="table:4", row=2, col=1,
                     col_label=label, variable_id="var:act"),
                cell("val:s", "sd", "3.40", table="table:4", row=2, col=1,
                     col_label=label, variable_id="var:act")]
        acc = account(variables=[F_VAR], values=vals,
                      tables=[{"id": "table:4", "caption": caption}])
        got = checks.evaluate(acc, text)
        assert accusations(got) == []
        assert "reports_model_output" not in every_reason(got)
        assert {r["check_id"] for r in got["checks"]} >= {"chk:grim:val:m"}


# --------------------------------------------------------------------------
# I -- THE ANALYSIS n THE PAPER ANNOUNCES
# --------------------------------------------------------------------------

I_TEXT = """# The Ashcombe trial: asthma control

## Methods

Forty-eight children were enrolled and analysed; the analysed sample was n = 48.
The Asthma Control Test is scored from 5 to 25 in whole points, and each child
contributed one whole-point score.
{extra}

## Results

The mean Asthma Control Test score was 14.80 (SD 5.95).
"""

I_SAID = "The mean Asthma Control Test score was 14.80 (SD 5.95)."
I_N48 = prose("val:n48", "n", "48",
              "Forty-eight children were enrolled and analysed; the analysed "
              "sample was n = 48.", id_check=None)


class TestThePaperMaySayThisRowsNIsNotTheGroups:
    """14.80 (SD 5.95) was computed from 46 real whole-point scores in 5-25. It
    is GRIM- and GRIMMER-consistent at n = 46 and `impossible` at n = 48."""

    def test_the_tables_own_footnote_withdraws_the_group_n(self):
        caption = ("Table 1. Outcomes, mean (SD). Sample sizes vary from 44 to 48 "
                   "across measures owing to missing responses.")
        acc = account(variables=[F_VAR], values=[
            I_N48,
            cell("val:m", "mean", "14.80", col_label="Mean (SD)", variable_id="var:act"),
            cell("val:s", "sd", "5.95", col_label="Mean (SD)", variable_id="var:act")],
            tables=[{"id": "table:1", "caption": caption}])
        got = checks.evaluate(acc, I_TEXT.format(extra=""))
        assert accusations(got) == []
        assert set(refusals(got).values()) == {"per_row_n_not_captured"}

    def test_methods_says_it_for_a_value_reported_in_prose(self):
        text = I_TEXT.format(
            extra="Sample sizes vary from 44 to 48 across measures because some "
                  "children did not complete every questionnaire.")
        acc = account(variables=[F_VAR], values=[
            I_N48, prose("val:m", "mean", "14.80", I_SAID, variable_id="var:act"),
            prose("val:s", "sd", "5.95", I_SAID, variable_id="var:act")])
        got = checks.evaluate(acc, text)
        assert accusations(got) == []
        assert set(refusals(got).values()) == {"per_row_n_not_captured"}

    def test_the_refusal_hands_the_reader_the_sentence(self):
        text = I_TEXT.format(
            extra="Sample sizes vary from 44 to 48 across measures because some "
                  "children did not complete every questionnaire.")
        acc = account(variables=[F_VAR], values=[
            I_N48, prose("val:m", "mean", "14.80", I_SAID, variable_id="var:act")])
        got = checks.evaluate(acc, text)
        detail = [r["detail"] for row in got["refused"] for r in row["reasons"]
                  if r["reason"] == "per_row_n_not_captured"]
        assert detail and "Sample sizes vary from 44 to 48" in detail[0]

    def test_the_correct_reading_still_runs(self):
        """THE COST SIDE. Where the completers are declared as their own group
        the denominator is known, and the check must run and clear."""
        text = I_TEXT.format(
            extra="The Asthma Control Test was completed by 46 of the 48 children.")
        groups = [{"id": "grp:all", "label": "All analysed", "n": 48, "n_source": "text"},
                  {"id": "grp:act", "label": "Completed the Asthma Control Test",
                   "n": 46, "n_source": "text"}]
        acc = account(groups=groups, variables=[F_VAR], values=[
            I_N48,
            prose("val:n46", "n", "46",
                  "The Asthma Control Test was completed by 46 of the 48 children.",
                  group="grp:act", id_check=None),
            prose("val:m", "mean", "14.80", I_SAID, variable_id="var:act",
                  group="grp:act"),
            prose("val:s", "sd", "5.95", I_SAID, variable_id="var:act",
                  group="grp:act")])
        got = checks.evaluate(acc, text)
        assert accusations(got) == []
        assert {r["check_id"] for r in got["checks"]} >= {"chk:grim:val:m"}

    def test_a_paper_that_says_nothing_is_untouched(self):
        acc = account(variables=[F_VAR], values=[
            I_N48, prose("val:m", "mean", "18.50",
                         "The mean Asthma Control Test score was 18.50 (SD 3.40).",
                         variable_id="var:act")])
        text = I_TEXT.format(extra="").replace("14.80 (SD 5.95)", "18.50 (SD 3.40)")
        got = checks.evaluate(acc, text)
        assert "per_row_n_not_captured" not in every_reason(got)
        assert {r["check_id"] for r in got["checks"]} >= {"chk:grim:val:m"}


# --------------------------------------------------------------------------
# J -- A FAMILY NAME THE BRIDGE DOES NOT DEFINE
# --------------------------------------------------------------------------


class TestAnUnknownFamilyIsARefusalAndNotAnException:
    def _account(self):
        return account(variables=[F_VAR], values=[
            I_N48, prose("val:m", "mean", "18.50",
                         "The mean Asthma Control Test score was 18.50 (SD 3.40).",
                         variable_id="var:act")])

    def test_it_does_not_raise(self):
        got = checks.evaluate(self._account(), "", families=("no_such_family",))
        assert got["n_run"] == 0
        assert refusals(got) == {"chk:family:no_such_family": "unknown_family"}

    def test_conservation_still_holds(self):
        got = checks.evaluate(self._account(), "",
                              families=("grim", "no_such_family"))
        assert got["n_run"] + got["n_refused"] == got["n_candidates"]
        assert "unknown_family" in {r["reason"] for r in got["refused"]}
        assert set(got["by_family"]) == {"grim"}

    def test_an_empty_selection_means_none_and_not_all(self):
        got = checks.evaluate(self._account(), "", families=())
        assert got["n_candidates"] == 0
        assert got["n_run"] == 0

    def test_none_still_means_every_family(self):
        got = checks.evaluate(self._account(), "")
        assert set(got["by_family"]) == set(checks.FAMILY_NAMES)


# --------------------------------------------------------------------------
# THE COVERAGE REGRESSION: ONE SENTENCE, TWO VARIABLES, ONE SCALE
# --------------------------------------------------------------------------

SHARED_TEXT = """# The Ashcombe trial: coalition scales

## Methods

Forty-eight coalitions were analysed; the analysed sample was n = 48.

## Results

The means for inclusive decision making and inclusion of community residents were 4.06 and 4.01 on a 1-5 scale.
"""

SHARED_QUOTE = ("The means for inclusive decision making and inclusion of community "
                "residents were 4.06 and 4.01 on a 1-5 scale")


def _shared(other_bounds):
    a = var("var:idm", "inclusive decision making", "continuous",
            bsource="stated", lower=1, upper=5, bquote=SHARED_QUOTE)
    b = var("var:icr", "inclusion of community residents", "continuous", **other_bounds)
    said = ("The means for inclusive decision making and inclusion of community "
            "residents were 4.06 and 4.01 on a 1-5 scale.")
    vals = [prose("val:n", "n", "48",
                  "Forty-eight coalitions were analysed; the analysed sample was "
                  "n = 48.", id_check=None),
            prose("val:idm:mean", "mean", "4.06", said, variable_id="var:idm"),
            prose("val:idm:sd", "sd", "0.50", said, variable_id="var:idm")]
    acc = account(variables=[a, b], values=vals)
    return acc, premises.stamp(acc, SHARED_TEXT)


def _verification(stamped, vid):
    return [v for v in stamped["variables"] if v["id"] == vid][0]["bounds"]["verification"]


class TestOneSentenceMayStateOneScaleForTwoVariables:
    """The attribution tie refuses whenever the sentence names another declared
    variable at least as strongly. That is right when one of the two is wrong --
    round 3's abbreviations block put a PSS item range on a BMI of 27.4 -- and
    wrong when the sentence states ONE scale for BOTH, which cost two real
    `check_sd_or_se` calls on ajcp.70049."""

    SAME = {"bsource": "stated", "lower": 1, "upper": 5, "bquote": SHARED_QUOTE}

    def test_the_shared_scale_is_admitted_for_both(self):
        acc, stamped = _shared(self.SAME)
        for vid in ("var:idm", "var:icr"):
            rec = _verification(stamped, vid)
            assert (rec["lower_passed"], rec["upper_passed"]) == (1, 5), vid
            assert rec["bound_source"] == "stated", vid
            assert rec["quote_states_a_shared_scale_with"], vid

    def test_and_the_check_it_was_costing_actually_runs(self):
        acc, _ = _shared(self.SAME)
        got = checks.evaluate(acc, SHARED_TEXT)
        assert accusations(got) == []
        ran = {r["check_id"]: r["args"] for r in got["checks"]}
        assert "chk:sd_or_se:val:idm:sd" in ran
        assert ran["chk:sd_or_se:val:idm:sd"]["variable_range_max"] == 5

    def test_a_variable_that_declares_no_bound_shares_nothing(self):
        """The round-3 shape: the OTHER variable named in the sentence claims no
        such scale, so the tie is a real ambiguity and both sides refuse."""
        _, stamped = _shared({})
        rec = _verification(stamped, "var:idm")
        assert rec["lower_passed"] is None and rec["upper_passed"] is None
        assert rec["bound_source"] == premises.ASSUMED_BOUND_SOURCE

    def test_a_different_bound_on_the_other_variable_still_refuses(self):
        _, stamped = _shared({"bsource": "stated", "lower": 0, "upper": 4,
                              "bquote": SHARED_QUOTE})
        rec = _verification(stamped, "var:idm")
        assert rec["lower_passed"] is None and rec["upper_passed"] is None

    def test_the_abbreviations_block_still_refuses(self):
        """Round 3's own case, re-asserted from this side: the two variables
        score 1.0 apiece on a footnote block, and the `0 to 4` belongs to one of
        them. `premises.values_outside` is the second line and this is the first."""
        text = ("# The Fenwick cohort\n\n## Methods\n\n"
                "Forty adults were enrolled and analysed; the analysed sample was "
                "n = 40.\n\n## Results\n\n"
                "Table 1. Baseline characteristics of the 40 adults\n\n"
                "Abbreviations: BMI, body mass index in kg per m2\n"
                "PSS, Perceived Stress Scale, items rated 0 to 4\n\n"
                "Body mass index averaged 27.4 kg per m2 (SD 4.6).\n")
        acc = account(variables=[
            var("var:bmi", "body mass index", "continuous", bsource="stated",
                lower=0, upper=4, bquote="items rated 0 to 4"),
            var("var:pss", "Perceived Stress Scale", "integer_score")], values=[])
        rec = _verification(premises.stamp(acc, text), "var:bmi")
        assert rec["lower_passed"] is None and rec["upper_passed"] is None
        assert rec["quote_states_a_shared_scale_with"] is None
