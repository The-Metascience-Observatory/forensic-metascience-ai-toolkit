"""The five defects a fifth adversarial pass found in the checks bridge, and the
two half-implementations round 3's own re-derivation left open, pinned.

THE PAPER IS NEW AND SO IS THE SURFACE. "The Kelmscott district child nutrition
survey" shares nothing with the Delta trial of
`test_scaffold_checks_adversarial.py`, the Harborview study of
`test_scaffold_checks_round3.py` or the Ashcombe trial of
`test_scaffold_checks_round4.py`: a weighted school survey rather than a trial,
and attacks aimed at premises none of those rounds touched -- WHICH ESTIMATOR
produced a printed mean, WHICH PHASE a denominator belongs to, and whether an id
names one value.

Every number below is recomputed IN THIS FILE from a real 34-child integer
dataset by the estimator the paper's own sentence names, so "the paper printed
nothing wrong" is a fact rather than an assertion, and any verdict worse than
`consistent` or `indeterminate` is a false accusation by construction.

The five it found, and the two it reproduced, and where each is fixed:

  M   a reported mean that is not a sum over n -- survey-weighted, Rubin-pooled,
      ANCOVA-adjusted, trimmed, or a two-stage mean of school means -- reached
      GRIM, GRIMMER and SPRITE as `impossible` even where the paper NAMES its
      estimator. `premises.weighted_percentage_reason` already read the four
      places a paper says so and returned early unless the value was a
      PERCENTAGE (`premises.named_estimator`, now shared, and
      `premises.NOT_A_SIMPLE_MEAN`)
  P   `_Index.n_at` was keyed on (study, group) while `phase_id` is part of the
      coordinate everywhere else, so a two-wave study's baseline n was the
      denominator of every follow-up statistic of the same group
  Q   `premises.population_sizes` refused only a population LARGER than the
      bound n; a paper naming a SMALLER subgroup with its own printed size in
      the value's own sentence is the commonest case and the one direction that
      manufactures a granularity failure (`subgroup_stated_in_the_sentence`)
  B   the alternative-base ceiling was the largest n the ACCOUNT held under the
      STRICT grammar, so a total spelled out (`Thirty-four children`) or grouped
      by thousands (`1,204 patients`) put the paper's own denominator above its
      own ceiling and the guard stopped firing (`premises.paper_max_n`)
  D   `_Index.by_id` is last-write-wins and nothing asserted that an id names one
      value, so two values sharing one id produced a check translated from the
      wrong record while conservation still balanced
      (`premises.duplicate_ids`)
  G   an empty `structure.json` (`{}`) was recorded as `structure_present:
      "empty"` and `require` still keyed on `expected`, which is None for an
      absent file and for an empty one alike
  R   a refusal's docket named the reason and never the paper's own words behind
      it, so `mean_is_not_a_simple_average` read as an assertion about nothing in
      particular

THE COST SIDE IS ASSERTED TOO. A guard that bought its safety by refusing
everything would pass every attack here and be worthless, so the raw-estimator
control must keep reaching a verdict in all five families, and `Mean (SD)` over a
caption that names no estimator must stay checkable.
"""

from __future__ import annotations

import json
import shutil
import statistics as st

import pytest

from forensic_metascience_ai_toolkit.scaffold import checks, premises, structure

BAD = {"suspicious", "highly_suspicious", "impossible"}

# --------------------------------------------------------------------------
# The Kelmscott survey's real per-child data
# --------------------------------------------------------------------------

#: 34 children, HEI-SF scored 0-20 in whole points. n = 34 is where GRIM has real
#: discriminating power at two decimals.
HEI = [4, 5, 6, 6, 7, 7, 7, 8, 8, 8, 9, 9, 9, 9, 10, 10, 10, 10, 11, 11,
       11, 12, 12, 12, 13, 13, 14, 14, 15, 15, 16, 17, 18, 19]

#: Two schools sampled with unequal probability; the design weight is the inverse
#: selection probability, which is the ordinary complex-survey convention.
WEIGHT = [1.0] * 17 + [2.5] * 17

AGE = [7, 8, 9, 10, 11, 7, 8, 9, 10, 11, 7, 8, 9, 10, 11, 7, 8,
       9, 10, 11, 7, 8, 9, 10, 11, 7, 8, 9, 10, 11, 7, 8, 9, 10]
GIRLS = [i < 17 for i in range(34)]

BOUND_Q = ("The Healthy Eating Index short form is scored from 0 to 20 in whole "
           "points, and each child contributed one whole-point score.")
N_Q = ("Thirty-four children were sampled from two primary schools and all "
       "thirty-four were analysed; the analysed sample was n = 34.")

METHODS = f"""# The Kelmscott district child nutrition survey

## Methods

{N_Q}
{BOUND_Q}
Seventeen of the children were girls and seventeen were boys.
"""


def weighted_mean(xs, ws):
    return sum(x * w for x, w in zip(xs, ws)) / sum(ws)


def weighted_sd(xs, ws):
    mu = weighted_mean(xs, ws)
    return (sum(w * (x - mu) ** 2 for x, w in zip(xs, ws)) / (sum(ws) - 1)) ** 0.5


def trimmed_mean(xs, k):
    s = sorted(xs)
    return st.fmean(s[k:len(s) - k])


def ancova_adjusted(y, x, mask):
    """The least-squares mean of the masked subgroup: its own mean of y, moved to
    the grand mean of the covariate by the pooled slope."""
    gy = [yi for yi, m in zip(y, mask) if m]
    gx = [xi for xi, m in zip(x, mask) if m]
    b = st.covariance(x, y) / st.variance(x)
    return st.fmean(gy) + b * (st.fmean(x) - st.fmean(gx))


def pooled_after_imputation(observed, imputed_sets):
    """Rubin's rules for a mean: the average of the per-dataset means."""
    return st.fmean([st.fmean(list(observed) + list(imp)) for imp in imputed_sets])


IMPUTED_SETS = [
    [9, 11, 13], [10, 12, 11], [8, 10, 14], [11, 9, 12], [12, 11, 10],
    [9, 13, 11], [10, 10, 12], [11, 12, 9], [8, 11, 13], [12, 9, 11],
    [10, 13, 10], [9, 10, 12], [11, 11, 11], [13, 9, 10], [8, 12, 12],
    [10, 11, 13], [12, 10, 9], [9, 12, 10], [11, 10, 12], [10, 11, 11],
]

W_MEAN = f"{weighted_mean(HEI, WEIGHT):.2f}"
W_SD = f"{weighted_sd(HEI, WEIGHT):.2f}"
RAW_MEAN = f"{st.fmean(HEI):.2f}"
RAW_SD = f"{st.stdev(HEI):.2f}"


def test_the_fixture_paper_is_honest():
    """EVERY PRINTED NUMBER, RECOMPUTED. A fixture whose paper is quietly wrong
    would make every assertion below meaningless, so the arithmetic is asserted
    before it is used."""
    assert W_MEAN == "12.01" and W_SD == "3.60"
    assert RAW_MEAN == "10.74" and RAW_SD == "3.74"
    assert f"{pooled_after_imputation(HEI[:31], IMPUTED_SETS):.2f}" == "10.10"
    assert f"{ancova_adjusted(HEI, AGE, GIRLS):.2f}" == "7.79"
    assert f"{trimmed_mean(HEI, 3):.2f}" == "10.57"


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


def hei_var():
    return var("var:hei", "Healthy Eating Index short form score", "integer_score",
               bsource="stated", lower=0, upper=20, bquote=BOUND_Q,
               step=1, gquote=BOUND_Q)


def cell(vid, statistic, printed, *, table="table:1", row=1, col=1, col_label=None,
         variable_id=None, group="grp:all", phase=None):
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
                           "phase_id": phase}}


def prose(vid, statistic, printed, quote, *, variable_id=None, group="grp:all",
          phase=None, id_check="agrees", applies_to_all=False):
    lit = premises.read_plain(printed) or {}
    v = {"id": vid, "statistic": statistic, "printed": printed,
         "numeric": lit.get("value"), "decimals": lit.get("decimals", 0),
         "printed_form": "percent" if lit.get("is_percent") else "plain",
         "units": None, "variable_id": variable_id, "id_check": id_check,
         "statistic_disputed": False, "source": "prose", "quote": quote,
         "quote_verified": "verbatim", "printed_in_quote": True,
         "location": {"kind": "prose", "offset": 0, "col_label": None},
         "coordinate": {"study_id": "study:main", "group_id": group,
                        "phase_id": phase}}
    if applies_to_all:
        v["applies_to_all_groups"] = True
    return v


def account(*, groups=None, variables=None, values=None, tables=None, studies=None):
    return {"paper": {"doi": "10.0000/kelmscott",
                      "title": "The Kelmscott district nutrition survey"},
            "studies": studies if studies is not None else
            [{"id": "study:main", "design": "cross_sectional_survey",
              "groups": groups if groups is not None
              else [{"id": "grp:all", "label": "All children", "n": 34,
                     "n_source": "text"}]}],
            "variables": variables or [], "values": values or [],
            "document": {"tables": tables or [
                {"id": "table:1",
                 "caption": "Table 1. Characteristics of the sampled children."}]}}


def n_row(printed="34", quote=N_Q, *, group="grp:all", phase=None, vid="val:n",
          applies_to_all=False):
    return prose(vid, "n", printed, quote, group=group, phase=phase,
                 id_check=None, applies_to_all=applies_to_all)


def accusations(got):
    return [(r["check_id"], r["severity"], r["result"].get("failure_mode"))
            for r in got["checks"] if r["severity"] in BAD]


def refusals(got):
    return {r["check_id"]: r["reason"] for r in got["refused"]}


def every_reason(got):
    return {row["reason"] for r in got["refused"] for row in r["reasons"]}


def ran(got):
    return {r["check_id"] for r in got["checks"]}


# --------------------------------------------------------------------------
# M -- THE REPORTED MEAN IS NOT A SUM OVER n, AND THE PAPER SAYS SO
# --------------------------------------------------------------------------

#: (name, the Methods sentence, the results sentence, the printed mean). Every
#: mean is what its own named estimator gives on the 34 real integer scores, and
#: every one of them is GRIM `impossible` at n = 34 -- which is the attack.
ESTIMATORS = [
    ("a survey-weighted mean",
     "Sampling weights were the inverse of each school's selection probability.",
     f"Weighted to the district population, the mean Healthy Eating Index short "
     f"form score was {W_MEAN}.", W_MEAN),
    ("a mean pooled by Rubin's rules after multiple imputation",
     "Missing items were multiply imputed, twenty datasets were created, and "
     "estimates were pooled using Rubin's rules.",
     "Pooled across the twenty imputed datasets using Rubin's rules, the mean "
     "Healthy Eating Index short form score was 10.10.", "10.10"),
    ("an ANCOVA least-squares mean",
     "Scores were compared between the sexes by analysis of covariance with age "
     "in whole years as the covariate.",
     "Adjusted for age, the mean Healthy Eating Index short form score was 7.79 "
     "among the girls.", "7.79"),
    ("a 10% trimmed mean",
     "Three children reported implausibly high intakes.",
     "We report the 10% trimmed mean Healthy Eating Index short form score, "
     "which was 10.57.", "10.57"),
    ("a two-stage mean of the two school means",
     "Fourteen children were sampled at Ashfield and twenty at Bardsey.",
     "Giving each school equal weight, the mean of the two school means was "
     "12.24.", "12.24"),
]


def _estimator_account(methods, said, mean):
    text = METHODS + methods + "\n\n## Results\n\n" + said + "\n"
    acc = account(variables=[hei_var()],
                  values=[n_row(),
                          prose("val:mean", "mean", mean, said, variable_id="var:hei")])
    return acc, text


class TestAnEstimatorIsNotASumOverN:
    @pytest.mark.parametrize("tag,methods,said,mean", ESTIMATORS)
    def test_a_named_estimator_accuses_nobody(self, tag, methods, said, mean):
        """The sharpest defect of round 5, in its five shapes. Each printed mean
        is exactly what the paper's own named estimator gives on real integer
        data, and each was `impossible` on GRIM, GRIMMER and SPRITE."""
        acc, text = _estimator_account(methods, said, mean)
        got = checks.evaluate(acc, text)
        assert accusations(got) == []
        assert "mean_is_not_a_simple_average" in every_reason(got)

    @pytest.mark.parametrize("tag,methods,said,mean", ESTIMATORS)
    def test_the_refusal_names_the_words_the_paper_used(self, tag, methods, said, mean):
        """A refusal that cannot be traced to the sentence it rests on is not a
        statement a reader can check."""
        acc, text = _estimator_account(methods, said, mean)
        rows = [row for r in checks.evaluate(acc, text)["refused"]
                for row in r["reasons"]
                if row["reason"] == "mean_is_not_a_simple_average"]
        assert rows
        assert all("sentence" in row["detail"] or "paper" in row["detail"]
                   for row in rows)

    def test_the_sd_beside_it_is_left_alone(self):
        """THE GATE IS THE MEAN'S, NOT THE VALUE'S NEIGHBOURS'. `check_sd_or_se`
        asks whether a dispersion is plausible on a stated range, which a
        weighted dispersion still is; refusing it would take a value out of a
        family for a reason that is not about that family."""
        said = (f"Weighted to the district population, the mean Healthy Eating "
                f"Index short form score was {W_MEAN} (SD {W_SD}).")
        text = METHODS + "\n## Results\n\n" + said + "\n"
        acc = account(variables=[hei_var()], values=[
            n_row(),
            prose("val:mean", "mean", W_MEAN, said, variable_id="var:hei"),
            prose("val:sd", "sd", W_SD, said, variable_id="var:hei")])
        got = checks.evaluate(acc, text)
        assert accusations(got) == []
        assert "chk:sd_or_se:val:sd" in ran(got)


#: The ways a paper names its estimator IN PROSE. One payload throughout -- the
#: survey-weighted 12.01, which GRIM calls `impossible` at n = 34 -- so the only
#: thing that varies is the naming.
NAMINGS_IN_PROSE = [
    "Weighted to the district population, the mean score was {v}.",
    "The survey-weighted mean score was {v}.",
    "The age- and sex-standardized mean score was {v}.",
    "Pooled across the twenty imputed datasets, the mean score was {v}.",
    "The least-squares mean score was {v}.",
    "The estimated marginal mean score was {v}.",
    "Adjusted for age and sex, the mean score was {v}.",
    "The 10% trimmed mean score was {v}.",
    "The winsorized mean score was {v}.",
    "The bootstrap mean score was {v}.",
    "The mean of the two school means was {v}.",
    "The inverse-probability-weighted mean score was {v}.",
]

#: The ways a paper names it in a COLUMN BAND, and in a CAPTION. `Mean (SD)` and
#: `Table 2. Characteristics of the sampled children.` are the controls: they
#: name no estimator, so they stay checkable.
NAMINGS_IN_A_BAND = [
    "Weighted mean (SD)", "Survey-weighted mean", "Adjusted mean (SE)",
    "LS mean (SE)", "EMM (95% CI)", "Trimmed mean", "Pooled mean (SD)",
    "Standardized mean", "Marginal mean (SE)", "Estimated marginal mean (SE)",
    "Adjusted",
]
NAMINGS_IN_A_CAPTION = [
    "Table 2. Estimates weighted to the district population.",
    "Table 2. Estimates pooled across twenty imputed datasets (Rubin's rules).",
    "Table 2. Estimated marginal means from the ANCOVA.",
    "Table 2. Least-squares means, adjusted for age.",
    "Table 2. Trimmed means (10% each tail).",
    "Table 2. Age- and sex-standardized means.",
    "Table 2. Inverse-probability-weighted estimates.",
]

PLAIN_CAPTION = "Table 2. Characteristics of the sampled children."


def _table_account(band, caption):
    text = METHODS + "\n## Results\n\nTable 2 gives the district estimates.\n"
    acc = account(variables=[hei_var()],
                  tables=[{"id": "table:2", "caption": caption}],
                  values=[n_row(),
                          cell("val:mean", "mean", W_MEAN, table="table:2",
                               col_label=band, variable_id="var:hei")])
    return acc, text


class TestTheFourPlacesAPaperNamesItsEstimator:
    @pytest.mark.parametrize("said", NAMINGS_IN_PROSE)
    def test_the_value_s_own_sentence(self, said):
        s = said.format(v=W_MEAN)
        text = METHODS + "\n## Results\n\n" + s + "\n"
        acc = account(variables=[hei_var()],
                      values=[n_row(), prose("val:mean", "mean", W_MEAN, s,
                                             variable_id="var:hei")])
        assert accusations(checks.evaluate(acc, text, ("grim",))) == []

    @pytest.mark.parametrize("band", NAMINGS_IN_A_BAND)
    def test_the_column_band(self, band):
        acc, text = _table_account(band, PLAIN_CAPTION)
        assert accusations(checks.evaluate(acc, text, ("grim",))) == []

    @pytest.mark.parametrize("caption", NAMINGS_IN_A_CAPTION)
    def test_the_table_s_caption(self, caption):
        acc, text = _table_account("Mean (SD)", caption)
        assert accusations(checks.evaluate(acc, text, ("grim",))) == []

    def test_a_governing_sentence_of_the_paper_s(self):
        """The fourth place: the paper says it once, of all its means. The band
        and the caption here name nothing, so this sentence is the only evidence
        there is -- and without it the same cell is checked (the test below)."""
        acc, bare = _table_account("Mean (SD)", PLAIN_CAPTION)
        governed = (METHODS + "All means in Table 2 are weighted to the "
                              "school-district population.\n\n## Results\n\n"
                              "Table 2 gives the estimates.\n")
        got = checks.evaluate(acc, governed, ("grim",))
        assert accusations(got) == []
        assert refusals(got)["chk:grim:val:mean"] == "mean_is_not_a_simple_average"
        assert premises.estimator_statement(governed)
        assert premises.estimator_statement(bare) is None

    def test_a_band_and_a_caption_that_name_no_estimator_stay_checkable(self):
        """THE COST SIDE. `Mean (SD)` under an ordinary caption is the honest
        descriptive column this whole family exists for, and a guard that refused
        it would pass every test above and be worthless. The paper here says
        nothing about an estimator anywhere, so nothing is available to read --
        and the check runs, on the raw mean, and clears."""
        text = METHODS + "\n## Results\n\nTable 2 gives the characteristics.\n"
        acc = account(variables=[hei_var()],
                      tables=[{"id": "table:2", "caption": PLAIN_CAPTION}],
                      values=[n_row(),
                              cell("val:mean", "mean", RAW_MEAN, table="table:2",
                                   col_label="Mean (SD)", variable_id="var:hei")])
        got = checks.evaluate(acc, text, ("grim",))
        assert accusations(got) == []
        assert ran(got) == {"chk:grim:val:mean"}


class TestTheGuardIsNotWiredToOneStatistic:
    """M8: one weighted table, one caption, one band. The percentage in it was
    refused and the MEAN beside it -- weighted by the same weights, named in the
    same caption -- was checked and convicted. The four places are read for both
    now; only the vocabulary differs."""

    CAPTION = ("Table 2. District estimates, weighted to the district population "
               "of children. Counts are unweighted; percentages and means are "
               "weighted.")

    def _account(self):
        return account(
            variables=[hei_var(),
                       var("var:target", "met the five-a-day target",
                           "percentage_of_subjects")],
            tables=[{"id": "table:2", "caption": self.CAPTION}],
            values=[n_row(),
                    cell("val:cnt", "count", "12", table="table:2",
                         col_label="No. (weighted %)", variable_id="var:target"),
                    cell("val:pct", "percentage", "41.8", table="table:2",
                         col_label="No. (weighted %)", variable_id="var:target"),
                    cell("val:mean", "mean", W_MEAN, table="table:2", row=2,
                         col_label="Weighted mean (SD)", variable_id="var:hei"),
                    cell("val:sd", "sd", W_SD, table="table:2", row=2,
                         col_label="Weighted mean (SD)", variable_id="var:hei")])

    def test_the_percentage_and_the_mean_are_both_refused(self):
        text = (METHODS + "All percentages and means in Table 2 are weighted to the "
                          "school-district population; counts are unweighted.\n\n"
                          "## Results\n\nTable 2 gives the district estimates.\n")
        got = checks.evaluate(self._account(), text)
        assert accusations(got) == []
        reasons = every_reason(got)
        assert "percentage_is_weighted" in reasons
        assert "mean_is_not_a_simple_average" in reasons

    def test_both_guards_read_the_same_four_places(self):
        """One detector, two vocabularies -- asserted directly so a future change
        cannot give one statistic a place the other does not have."""
        v = self._account()["values"][3]
        caps = {"table:2": self.CAPTION}
        assert premises.named_estimator(premises.NOT_A_SIMPLE_MEAN, v, caps)
        assert premises.named_estimator(premises.WEIGHTED_PERCENTAGE, v, caps)


# --------------------------------------------------------------------------
# P -- THE DENOMINATOR IS RESOLVED BY (study, group) AND THE COORDINATE ALSO
#      CARRIES A PHASE
# --------------------------------------------------------------------------

LOST = [0, 1, 2, 3, 21]
FOLLOWED = [x for i, x in enumerate(HEI) if i not in LOST]
FU_MEAN_S = f"{st.fmean(FOLLOWED):.2f}"
FOLLOW_S = (f"Twenty-nine children (85.3%) were re-interviewed at twelve weeks, "
            f"and their mean Healthy Eating Index short form score was {FU_MEAN_S}.")
BASE_S = f"The mean Healthy Eating Index short form score at baseline was {RAW_MEAN}."

TWO_WAVE_TEXT = (METHODS + "\n## Results\n\n" + BASE_S + "\n" + FOLLOW_S + "\n")


def _two_wave(values):
    return account(variables=[hei_var()], values=values), TWO_WAVE_TEXT


BASE_N = n_row("34", N_Q, vid="val:n:base")
BASE_MEAN = prose("val:base:mean", "mean", RAW_MEAN, BASE_S, variable_id="var:hei",
                  phase="phase:baseline")
FU_MEAN = prose("val:fu:mean", "mean", FU_MEAN_S, FOLLOW_S, variable_id="var:hei",
                phase="phase:week12")


class TestAPhaseIsPartOfTheCoordinate:
    def test_the_follow_up_mean_is_not_adjudicated_at_the_baseline_n(self):
        """29 of the 34 were re-interviewed; the paper says so in the sentence the
        follow-up mean sits in, and its mean over those 29 real scores was
        `impossible` at 34."""
        acc, text = _two_wave([BASE_N, BASE_MEAN, FU_MEAN,
                               prose("val:fu:cnt", "count", "29", FOLLOW_S,
                                     variable_id="var:hei", phase="phase:week12")])
        got = checks.evaluate(acc, text)
        assert accusations(got) == []
        assert refusals(got)["chk:grim:val:fu:mean"] == "subgroup_stated_in_the_sentence"

    def test_the_baseline_mean_still_runs(self):
        """THE COST SIDE. The baseline sentence names no other population, so the
        one n the paper prints is its denominator and the check runs."""
        acc, text = _two_wave([BASE_N, BASE_MEAN, FU_MEAN])
        got = checks.evaluate(acc, text, ("grim",))
        assert "chk:grim:val:base:mean" in ran(got)
        assert accusations(got) == []

    def test_an_n_stated_per_wave_refuses_the_wave_that_has_none(self):
        """Where the paper states an n PER WAVE, an n carrying no wave cannot be
        attributed to one -- the argument `study_n_over_several_arms` makes
        across arms, made across phases. And the docket names the waves that DO
        carry one, because a reader can only act on the refusal knowing them."""
        acc, text = _two_wave([BASE_N, BASE_MEAN, FU_MEAN,
                               n_row("29", FOLLOW_S, phase="phase:week12",
                                     vid="val:fu:n")])
        got = checks.evaluate(acc, text, ("grim",))
        assert accusations(got) == []
        assert refusals(got)["chk:grim:val:base:mean"] == "phase_n_over_several_phases"
        detail = [row["detail"] for r in got["refused"] for row in r["reasons"]
                  if row["reason"] == "phase_n_over_several_phases"]
        assert any("phase:week12" in d and "phase:baseline" in d for d in detail)

    def test_a_single_wave_n_still_serves_every_phase(self):
        """THE COST SIDE, AND IT IS THE ORDINARY SHAPE. A single-arm study states
        `n = 34` once and reports the outcome at two visits; nothing in the
        account says the denominator varies, so both checks run.

        THE TEXT WAS `TWO_WAVE_TEXT` AND IS NOW A SINGLE-WAVE ONE (round 6). The
        fixture reused the two-wave document, which SAYS `Twenty-nine children
        (85.3%) were re-interviewed at twelve weeks` -- so the served paper did
        say the denominator varies, and only the ACCOUNT did not. Round 6 gave
        the bridge a reader for that sentence
        (`premises.analysed_counts`), and the twelve-week check now
        refuses against the very text that names a different twelve-week n. The
        claim this test makes is about an account with one n and no such
        statement, so the text is made to agree with it; the other reading is
        pinned beside it below and in
        `test_scaffold_checks_round6.py::TestAStageTheReadingDidNotRecord`.
        """
        w12 = prose("val:w12:mean", "mean", RAW_MEAN,
                    BASE_S.replace("at baseline", "at twelve weeks"),
                    variable_id="var:hei", phase="phase:week12")
        acc, _ = _two_wave([BASE_N, BASE_MEAN, w12])
        single_wave = (METHODS + "\n## Results\n\n" + BASE_S + "\n"
                       + BASE_S.replace("at baseline", "at twelve weeks") + "\n")
        got = checks.evaluate(acc, single_wave, ("grim",))
        assert ran(got) == {"chk:grim:val:base:mean", "chk:grim:val:w12:mean"}
        assert accusations(got) == []

    def test_the_same_account_refuses_where_the_paper_states_the_follow_up_n(self):
        """AND THE OTHER HALF OF IT, which is round 6's finding: the identical
        account against the two-wave text refuses AT THE WAVE THE PAPER'S OWN
        SENTENCE IS ABOUT, and keeps the baseline check the same sentence says
        nothing about."""
        acc, text = _two_wave([BASE_N, BASE_MEAN,
                               prose("val:w12:mean", "mean", RAW_MEAN,
                                     BASE_S.replace("at baseline", "at twelve weeks"),
                                     variable_id="var:hei", phase="phase:week12")])
        got = checks.evaluate(acc, text, ("grim",))
        assert accusations(got) == []
        assert ran(got) == {"chk:grim:val:base:mean"}
        assert (refusals(got)["chk:grim:val:w12:mean"]
                == "analysed_n_stated_for_another_stage")

    def test_the_wave_declared_as_its_own_group_is_the_reading_that_works(self):
        groups = [{"id": "grp:all", "label": "All children", "n": 34,
                   "n_source": "text"},
                  {"id": "grp:fu", "label": "Re-interviewed at twelve weeks",
                   "n": 29, "n_source": "text"}]
        fu = dict(FU_MEAN)
        fu["coordinate"] = {**fu["coordinate"], "group_id": "grp:fu"}
        acc = account(groups=groups, variables=[hei_var()],
                      values=[BASE_N, BASE_MEAN, fu,
                              n_row("29", FOLLOW_S, group="grp:fu",
                                    phase="phase:week12", vid="val:fu:n")])
        got = checks.evaluate(acc, TWO_WAVE_TEXT, ("grim",))
        assert accusations(got) == []
        assert ran(got) == {"chk:grim:val:base:mean", "chk:grim:val:fu:mean"}


# --------------------------------------------------------------------------
# Q -- A STATISTIC OVER A SUBSET OF THE GROUP, NAMED IN THE PAPER'S SENTENCE
# --------------------------------------------------------------------------

LUNCH = [HEI[i] for i in range(13, 34)]
LUNCH_MEAN = f"{st.fmean(LUNCH):.2f}"
LUNCH_S = (f"The {len(LUNCH)} children who ate a school lunch had a mean Healthy "
           f"Eating Index short form score of {LUNCH_MEAN}.")
LUNCH_TEXT = (METHODS + "\n## Results\n\nThe mean Healthy Eating Index short form "
                        f"score was {RAW_MEAN}.\n{LUNCH_S}\n")


class TestASubgroupNamedInTheSentence:
    def test_the_subgroup_mean_is_not_adjudicated_at_the_group_n(self):
        """The 21 scores are real and their mean is exact; at the group's 34 it is
        `impossible`. The guard read a stated population only where it was LARGER
        than the bound n, and smaller is both the commoner case and the one
        direction that manufactures a granularity failure."""
        acc = account(variables=[hei_var()],
                      values=[n_row(),
                              prose("val:sub:mean", "mean", LUNCH_MEAN, LUNCH_S,
                                    variable_id="var:hei")])
        got = checks.evaluate(acc, LUNCH_TEXT, ("grim",))
        assert accusations(got) == []
        assert refusals(got)["chk:grim:val:sub:mean"] == "subgroup_stated_in_the_sentence"

    def test_the_subgroup_size_is_not_taken_as_the_denominator(self):
        """READING ONE OUT OF A SENTENCE WOULD SUPPLY A PREMISE, and a derived
        boundary may only narrow one. So no check runs on 21 either."""
        acc = account(variables=[hei_var()],
                      values=[n_row(),
                              prose("val:sub:mean", "mean", LUNCH_MEAN, LUNCH_S,
                                    variable_id="var:hei")])
        got = checks.evaluate(acc, LUNCH_TEXT)
        assert got["n_run"] == 0

    def test_the_subgroup_declared_as_a_group_is_the_reading_that_works(self):
        groups = [{"id": "grp:all", "label": "All children", "n": 34,
                   "n_source": "text"},
                  {"id": "grp:lunch", "label": "Ate a school lunch",
                   "n": len(LUNCH), "n_source": "text"}]
        acc = account(groups=groups, variables=[hei_var()], values=[
            n_row(),
            n_row(str(len(LUNCH)), LUNCH_S, group="grp:lunch", vid="val:sub:n"),
            prose("val:sub:mean", "mean", LUNCH_MEAN, LUNCH_S,
                  variable_id="var:hei", group="grp:lunch")])
        got = checks.evaluate(acc, LUNCH_TEXT, ("grim",))
        assert accusations(got) == []
        assert "chk:grim:val:sub:mean" in ran(got)

    def test_a_population_spelled_out_is_read_too(self):
        """`Twenty-nine children` states a denominator as plainly as `The 21
        children` does, and only one of the two was being read."""
        assert premises.population_sizes(FOLLOW_S) == [29]
        assert premises.population_sizes(LUNCH_S) == [21]

    def test_a_duration_is_not_a_population(self):
        """`at twelve weeks` counts time, not subjects, and a number in the docket
        that is not a denominator at all is a wrong sentence to a reader."""
        assert 12 not in premises.population_sizes(FOLLOW_S)


# --------------------------------------------------------------------------
# B -- THE ALTERNATIVE-BASE CEILING WAS THE ACCOUNT'S, NOT THE PAPER'S
# --------------------------------------------------------------------------

BY_SCHOOL_CAPTION = ("Table 2. Children meeting the five-a-day target, by school. "
                     "No. (% of all children surveyed).")
SCHOOL_Q = ("Thirty-four children were sampled from two primary schools; seventeen "
            "were interviewed at Ashfield Primary (n = 17) and seventeen at "
            "Bardsey Primary (n = 17).")
BY_SCHOOL_TEXT = f"""# The Kelmscott district child nutrition survey

## Methods

{SCHOOL_Q}

## Results

Table 2 gives the number meeting the five-a-day target at each school, with the
percentage of all children surveyed.
"""


def _by_school(total_row=None):
    groups = [{"id": "grp:ash", "label": "Ashfield Primary", "n": 17,
               "n_source": "text"},
              {"id": "grp:bar", "label": "Bardsey Primary", "n": 17,
               "n_source": "text"}]
    vals = [n_row("17", SCHOOL_Q, group="grp:ash", vid="val:n:ash"),
            n_row("17", SCHOOL_Q, group="grp:bar", vid="val:n:bar"),
            cell("val:ash:cnt", "count", "5", table="table:2", col_label="No. (%)",
                 variable_id="var:target", group="grp:ash"),
            cell("val:ash:pct", "percentage", "14.7", table="table:2",
                 col_label="No. (%)", variable_id="var:target", group="grp:ash"),
            cell("val:bar:cnt", "count", "7", table="table:2", row=2,
                 col_label="No. (%)", variable_id="var:target", group="grp:bar"),
            cell("val:bar:pct", "percentage", "20.6", table="table:2", row=2,
                 col_label="No. (%)", variable_id="var:target", group="grp:bar")]
    if total_row is not None:
        vals.insert(0, total_row)
    return account(groups=groups,
                   variables=[var("var:target", "met the five-a-day target",
                                  "percentage_of_subjects")],
                   tables=[{"id": "table:2", "caption": BY_SCHOOL_CAPTION}],
                   values=vals)


class TestTheCeilingIsThePapersNotTheAccounts:
    def test_a_total_spelled_out_still_names_the_base(self):
        """5/34 and 7/34 are the caption's own base and the arithmetic is exact.
        The account holds no readable 34, so the ceiling was 17 and the guard
        could not see the base that explains the cell."""
        got = checks.evaluate(_by_school(), BY_SCHOOL_TEXT)
        assert accusations(got) == []
        assert set(refusals(got).values()) == {"another_denominator_fits"}

    def test_the_same_table_with_the_total_printed_as_a_numeral(self):
        """The control the attack was measured against."""
        total = n_row("34", SCHOOL_Q.replace("Thirty-four children were sampled",
                                             "In total n = 34 children were sampled"),
                      group=None, vid="val:n:all", applies_to_all=True)
        got = checks.evaluate(_by_school(total), BY_SCHOOL_TEXT)
        assert accusations(got) == []

    def test_the_forms_the_strict_grammar_refuses(self):
        assert premises.printed_integer("1,204") == 1204
        assert premises.printed_integer("Thirty-four") == 34
        assert premises.printed_integer("34.5") is None
        assert premises.paper_max_n([], "Thirty-four children were sampled.") == 34
        assert premises.paper_max_n([], "We screened 1,204 patients.") == 1204

    def test_the_ceiling_still_refuses_an_absurd_base(self):
        """WHY THE CEILING EXISTS AT ALL. `26 (0.867%)` is a hundredfold error, not
        a different base, and without a bound it was 'explained' by the
        denominators 2,996 to 3,000 in a paper of thirty people."""
        assert premises.other_bases_that_fit(26, 0.867, 3, 30, 34) == []


# --------------------------------------------------------------------------
# D -- TWO VALUES, ONE id
# --------------------------------------------------------------------------

TWO_STUDY_TEXT = f"""# The Kelmscott district child nutrition survey: two studies

## Methods

{BOUND_Q}

## Results

In Study 1 (n = 13) the mean Healthy Eating Index short form score was
{st.fmean(HEI[:13]):.2f}.
In Study 2 (n = 21) the mean Healthy Eating Index short form score was
{st.fmean(HEI[13:]):.2f}.
"""


def _two_studies(shared_id):
    s1 = (f"In Study 1 (n = 13) the mean Healthy Eating Index short form score "
          f"was {st.fmean(HEI[:13]):.2f}.")
    s2 = (f"In Study 2 (n = 21) the mean Healthy Eating Index short form score "
          f"was {st.fmean(HEI[13:]):.2f}.")
    studies = [{"id": "study:1", "design": "cross_sectional_survey",
                "groups": [{"id": "grp:all", "label": "All children", "n": 13,
                            "n_source": "text"}]},
               {"id": "study:2", "design": "cross_sectional_survey",
                "groups": [{"id": "grp:all", "label": "All children", "n": 21,
                            "n_source": "text"}]}]
    values = [prose("val:n:1", "n", "13", s1, id_check=None),
              prose("val:n:2", "n", "21", s2, id_check=None),
              prose("val:m" if shared_id else "val:m:1", "mean",
                    f"{st.fmean(HEI[:13]):.2f}", s1, variable_id="var:hei"),
              prose("val:m" if shared_id else "val:m:2", "mean",
                    f"{st.fmean(HEI[13:]):.2f}", s2, variable_id="var:hei")]
    for v, sid in zip(values, ("study:1", "study:2", "study:1", "study:2")):
        v["coordinate"] = {**v["coordinate"], "study_id": sid}
    return account(studies=studies, variables=[hei_var()], values=values)


class TestAnIdNamesOneValue:
    def test_two_studies_whose_mean_ids_collide(self):
        """One instrument reported for two studies collides on any id scheme keyed
        on (variable, statistic) -- the natural one. Both numbers, both ns and
        both coordinates are honest."""
        got = checks.evaluate(_two_studies(True), TWO_STUDY_TEXT)
        assert accusations(got) == []
        assert set(refusals(got).values()) == {"duplicate_value_id"}

    def test_the_same_account_with_distinct_ids_runs(self):
        got = checks.evaluate(_two_studies(False), TWO_STUDY_TEXT, ("grim",))
        assert accusations(got) == []
        assert len(ran(got)) == 2

    def test_an_abstract_mean_and_a_table_sd_sharing_an_id(self):
        """THE MEASURED CASE. `by_id` is last-write-wins, so GRIM was handed the
        3-decimal SD as its mean and returned `impossible` on an honest paper --
        while `n_candidates == n_run + n_refused` balanced exactly."""
        sd = f"{st.stdev(HEI):.3f}"
        said = f"The mean Healthy Eating Index short form score was 10.7 (SD {sd})."
        text = METHODS + "\n## Results\n\n" + said + "\n"
        acc = account(variables=[hei_var()], values=[
            n_row(),
            prose("val:hei", "mean", "10.7", said, variable_id="var:hei"),
            prose("val:hei", "sd", sd, said, variable_id="var:hei")])
        got = checks.evaluate(acc, text)
        assert accusations(got) == []
        assert got["n_run"] == 0
        assert set(refusals(got).values()) == {"duplicate_value_id"}

    def test_conservation_still_balances(self):
        got = checks.evaluate(_two_studies(True), TWO_STUDY_TEXT)
        assert got["n_candidates"] == got["n_run"] + got["n_refused"]

    def test_a_duplicated_n_row_is_refused_too(self):
        """The n rows come from `n_at` rather than from `by_id`, so nothing is
        silently substituted -- but the row a reader is sent to look at would be
        one of two, which is the same defect one step further down."""
        said = f"The mean Healthy Eating Index short form score was {RAW_MEAN}."
        text = METHODS + "\n## Results\n\n" + said + "\n"
        acc = account(variables=[hei_var()], values=[
            n_row(), n_row(),
            prose("val:mean", "mean", RAW_MEAN, said, variable_id="var:hei")])
        got = checks.evaluate(acc, text, ("grim",))
        assert refusals(got)["chk:grim:val:mean"] == "duplicate_value_id"
        detail = [row["detail"] for r in got["refused"] for row in r["reasons"]]
        assert any("val:n" in d for d in detail)


# --------------------------------------------------------------------------
# G -- AN EMPTY `structure.json` IS NOT "NO STRUCTURE"
# --------------------------------------------------------------------------


def _run_dir(tmp_path, name, *, struct_text=None, stamp="deadbeef" * 8):
    out = tmp_path / name
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    said = f"The mean Healthy Eating Index short form score was {RAW_MEAN}."
    acc = account(variables=[hei_var()], values=[
        n_row(), prose("val:mean", "mean", RAW_MEAN, said, variable_id="var:hei")])
    if stamp is not None:
        acc["provenance"] = {"structure_sha256": stamp, "structure_version": 2}
        acc["structure"] = {"version": 2, "sha256": stamp}
    (out / "account.json").write_text(json.dumps(acc), encoding="utf-8")
    (out / "body.repaired.md").write_text(METHODS + "\n## Results\n\n" + said + "\n",
                                          encoding="utf-8")
    if struct_text is not None:
        (out / "structure.json").write_text(struct_text, encoding="utf-8")
    return out


class TestAnEmptyStructureIsNotAnAbsentOne:
    def test_an_empty_structure_json_refuses(self, tmp_path):
        """`structure.presence` was added to tell "no file" from "a file with
        nothing in it", and `require` still keyed on `expected`, which is None for
        both -- so the run went ahead against a structure nothing on disk hashes
        to, and the only correction was that `checks.json` stopped REPRINTING the
        fabricated sha256."""
        out = _run_dir(tmp_path, "G-empty", struct_text="{}")
        with pytest.raises(structure.StructureMismatch, match="holds no structure"):
            checks.run(out)
        assert not (out / "checks.json").exists()

    def test_an_unparseable_structure_json_refuses(self, tmp_path):
        out = _run_dir(tmp_path, "G-broken", struct_text="{oops")
        assert structure.presence(out) == "empty"
        with pytest.raises(structure.StructureMismatch, match="holds no structure"):
            checks.run(out)

    def test_an_account_that_names_no_structure_at_all_still_runs(self, tmp_path):
        """The third fact, unchanged: an account with no structure names none, so
        there is none to have mixed."""
        out = _run_dir(tmp_path, "G-none", struct_text=None, stamp=None)
        got = checks.run(out)
        assert got["n_run"] >= 1 and got["structure_sha256"] is None


# --------------------------------------------------------------------------
# R -- WHAT A READER IS HANDED
# --------------------------------------------------------------------------


class TestTheDocketNamesThePapersOwnWords:
    def test_a_refusal_reason_carries_a_worked_example(self):
        """The docket printed the closed vocabulary's sentence -- identical on
        every paper -- and never what THIS paper said to earn it, so a reason read
        as an assertion about nothing in particular."""
        acc, text = _estimator_account(*ESTIMATORS[0][1:])
        md = checks.render_markdown(checks.evaluate(acc, text))
        assert "for example" in md
        assert "mean_is_not_a_simple_average" in md
        assert "Weighted to" in md

    def test_the_example_is_capped_at_one_per_reason(self):
        """A run refusing a hundred candidates prints a hundred rows nobody
        reads. Three candidates refuse for this reason here; the docket carries
        one row for it."""
        acc, text = _estimator_account(*ESTIMATORS[0][1:])
        got = checks.evaluate(acc, text)
        assert got["n_refused"] == 3
        docket = checks.render_markdown(got).split("### The docket")[1] \
            .split("### Census")[0]
        assert docket.count("mean_is_not_a_simple_average") == 1
        assert "Weighted to" in docket


# --------------------------------------------------------------------------
# THE NEGATIVE CONTROL -- the same survey read correctly
# --------------------------------------------------------------------------

CONTROL_TEXT = f"""# The Kelmscott district child nutrition survey

## Methods

{N_Q}
{BOUND_Q}

## Results

The mean Healthy Eating Index short form score was {RAW_MEAN} (SD {RAW_SD}).
Twelve of the thirty-four children (35.3%) met the district's five-a-day target.
"""

CONTROL_MEAN_S = (f"The mean Healthy Eating Index short form score was {RAW_MEAN} "
                  f"(SD {RAW_SD}).")
CONTROL_PCT_S = ("Twelve of the thirty-four children (35.3%) met the district's "
                 "five-a-day target.")


def _control():
    return account(variables=[hei_var(),
                              var("var:target", "met the five-a-day target",
                                  "percentage_of_subjects")],
                   values=[n_row(),
                           prose("val:hei:mean", "mean", RAW_MEAN, CONTROL_MEAN_S,
                                 variable_id="var:hei"),
                           prose("val:hei:sd", "sd", RAW_SD, CONTROL_MEAN_S,
                                 variable_id="var:hei"),
                           prose("val:t:cnt", "count", "12", CONTROL_PCT_S,
                                 variable_id="var:target"),
                           prose("val:t:pct", "percentage", "35.3%", CONTROL_PCT_S,
                                 variable_id="var:target")])


class TestTheRawEstimatorsStillRun:
    """A CONTROL THAT REFUSES EVERYTHING PROVES NOTHING ABOUT THE ATTACKS. The raw
    arithmetic means are what GRIM is defined for, every premise here is the
    paper's own, and all five families must still reach a verdict."""

    def test_every_family_runs_and_clears(self):
        got = checks.evaluate(_control(), CONTROL_TEXT)
        assert accusations(got) == []
        assert ran(got) == {"chk:count_percent:val:t:pct", "chk:grim:val:hei:mean",
                            "chk:grimmer:val:hei:mean", "chk:sd_or_se:val:hei:sd",
                            "chk:sprite:val:hei:mean"}
        assert set(r["severity"] for r in got["checks"]) == {"consistent"}

    def test_the_control_sentences_name_no_estimator_and_no_subgroup(self):
        assert premises.estimator_statement(CONTROL_TEXT) is None
        assert premises.population_sizes(CONTROL_MEAN_S) == []
