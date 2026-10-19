"""The nine defects a third adversarial pass found in the checks bridge, pinned.

THE PAPER IS NEW AND SO ARE THE ATTACKS. "The Harborview study" shares nothing
with the Delta trial of `test_scaffold_checks_adversarial.py`: different
variables, different value shapes, and attacks aimed at ARITHMETICALLY HONEST
cases rather than at premise gates. Every number in every fixture below is
internally consistent with the paper that prints it, so any verdict worse than
`consistent` or `indeterminate` is a false accusation by construction.

The nine, and where each is fixed:

  A  a `stated` bound is never compared against the variable's OWN PRINTED
     VALUES (`premises.values_outside`, applied to the passed bound and not only
     to the kind's)
  G  the same, for a level scale read against a CHANGE score
  H  a tie in `premises.about_this_variable` passed as an attribution
  B  `check_count_percent` asked wherever any n resolves, with nothing testing
     that the n is THAT percentage's base (`premises.other_bases_that_fit`)
  C  a prose count and a prose percentage about one variable paired as a
     count/percent pair (`premises.NON_SUBJECT_PERCENTAGE_KINDS`)
  D  the denominator's UNIT never checked against the statistic's
     (`premises.population_sizes`)
  E  the n-corroboration test satisfied by the row's own quote
     (`premises.n_corroboration`, one witness withdrawn)
  F  `study_n_over_several_arms` counting DECLARED groups only
  I  the SPRITE runtime guard keyed on n, while the cost is on the SCALE
  L  an unhashable member of `location`/`coordinate`/`variable_id` raising out
     of the index, before the per-candidate try/except
"""

from __future__ import annotations

import time

import pytest

from metascience_agent.scaffold import checks, premises

# --------------------------------------------------------------------------
# The Harborview study. Everything in it is true and consistent.
# --------------------------------------------------------------------------

TEXT = """# The Harborview Study: sleep, stress and clinic attendance

## Methods

Forty adults enrolled at a single community clinic and were analysed as one
cohort; the enrolled sample was n = 40.
Thirty-two of the forty enrolled adults completed the twelve-week follow-up
questionnaire.
The Perceived Stress Scale items were each rated from 0 to 4, and the
Perceived Stress Scale was scored in whole points.
Nights with disturbed sleep were tallied as whole nights per participant over
the recording fortnight.
Body mass was measured in kilograms to one decimal place.

## Results

Among the thirty-two adults who completed follow-up, twenty-four (75.0%)
reported improved sleep.
The mean Perceived Stress Scale score was 18.5 (SD 6.2).
The mean number of disturbed nights was 4.90 (SD 2.10).
Body mass averaged 78.4 kg (SD 12.6).
"""

BAD = {"suspicious", "highly_suspicious", "impossible"}


def var(vid, name, kind, *, bsource="not_stated", lower=None, upper=None,
        bquote=None, step=None, gquote=None, label=None):
    return {"id": vid, "name": name, "label": label if label is not None else name,
            "printed_as": [], "kind": kind, "role": None,
            "bounds": {"source": bsource, "lower": lower, "upper": upper, "quote": bquote},
            "granularity": {"per_subject_step": step, "quote": gquote}}


def cell(vid, statistic, printed, *, table="table:1", row=1, col=1, col_label=None,
         variable_id=None, group="grp:cohort"):
    lit = premises.read_plain(printed) or {}
    return {"id": vid, "statistic": statistic, "printed": printed,
            "numeric": lit.get("value"), "decimals": lit.get("decimals", 0),
            "printed_form": "percent" if lit.get("is_percent") else "plain",
            "units": None, "variable_id": variable_id, "id_check": "agrees",
            "statistic_disputed": False, "source": "table", "quote": None,
            "quote_verified": "cell", "printed_in_quote": None,
            "location": {"kind": "table_cell", "table_id": table, "row": row, "col": col,
                         "col_label": col_label},
            "coordinate": {"study_id": "study:main", "group_id": group, "phase_id": None}}


def prose(vid, statistic, printed, quote, *, variable_id=None, group="grp:cohort",
          phase=None, id_check="agrees", offset=0, applies_to_all=False):
    lit = premises.read_plain(printed) or {}
    v = {"id": vid, "statistic": statistic, "printed": printed,
         "numeric": lit.get("value"), "decimals": lit.get("decimals", 0),
         "printed_form": "percent" if lit.get("is_percent") else "plain",
         "units": None, "variable_id": variable_id, "id_check": id_check,
         "statistic_disputed": False, "source": "prose", "quote": quote,
         "quote_verified": "verbatim", "printed_in_quote": True,
         "location": {"kind": "prose", "offset": offset, "col_label": None},
         "coordinate": {"study_id": "study:main", "group_id": group, "phase_id": phase}}
    if applies_to_all:
        v["applies_to_all_groups"] = True
    return v


def account(*, groups=None, variables=None, values=None, tables=None):
    return {"paper": {"doi": "10.0000/harborview", "title": "The Harborview Study"},
            "studies": [{"id": "study:main", "design": "prospective_cohort",
                         "groups": groups if groups is not None
                         else [{"id": "grp:cohort", "label": "Whole cohort",
                                "n": 40, "n_source": "text"}]}],
            "variables": variables or [], "values": values or [],
            "document": {"tables": tables or [
                {"id": "table:1", "caption": "Table 1. Characteristics of the cohort."}]}}


def accusations(got):
    return [(r["check_id"], r["severity"], r["result"].get("failure_mode"))
            for r in got["checks"] if r["severity"] in BAD]


def _ran(got, check_id):
    return next((r for r in got["checks"] if r["check_id"] == check_id), None)


def _ref(got, check_id):
    return next((r for r in got["refused"] if r["check_id"] == check_id), None)


N40 = prose("val:n", "n", "40",
            "Forty adults enrolled at a single community clinic and were analysed as "
            "one cohort; the enrolled sample was n = 40.", id_check=None)


# --------------------------------------------------------------------------
# The control. Without it every test below could pass by refusing everything.
# --------------------------------------------------------------------------


CONTROL_TEXT = TEXT + (
    "\nAmong the 32 adults who completed follow-up, 24 (75.0%) reported improved "
    "sleep.\n")


def control_account():
    """The same honest paper, READ CORRECTLY: no bound offered for a quantity
    the paper never bounded, the completers declared as their own group with
    their own n, and every denominator the n of the thing being counted."""
    return account(
        groups=[{"id": "grp:cohort", "label": "Whole cohort", "n": 40, "n_source": "text"},
                {"id": "grp:completers", "label": "Completed follow-up", "n": 32,
                 "n_source": "text"}],
        variables=[
            var("var:pss", "Perceived Stress Scale", "integer_score", step=1,
                gquote="the Perceived Stress Scale was scored in whole points"),
            var("var:nights", "disturbed nights", "count", step=1,
                gquote="Nights with disturbed sleep were tallied as whole nights per "
                       "participant over the recording fortnight."),
            var("var:improved_sleep", "improved sleep", "percentage_of_subjects"),
        ],
        values=[
            N40,
            prose("val:n32", "n", "32",
                  "Thirty-two of the forty enrolled adults completed the twelve-week "
                  "follow-up questionnaire.", group="grp:completers", id_check=None),
            prose("val:pss:mean", "mean", "18.5",
                  "The mean Perceived Stress Scale score was 18.5 (SD 6.2).",
                  variable_id="var:pss"),
            prose("val:pss:sd", "sd", "6.2",
                  "The mean Perceived Stress Scale score was 18.5 (SD 6.2).",
                  variable_id="var:pss"),
            prose("val:nights:mean", "mean", "4.90",
                  "The mean number of disturbed nights was 4.90 (SD 2.10).",
                  variable_id="var:nights"),
            prose("val:nights:sd", "sd", "2.10",
                  "The mean number of disturbed nights was 4.90 (SD 2.10).",
                  variable_id="var:nights"),
            cell("val:imp:cnt", "count", "24", row=3, col_label="n (%)",
                 variable_id="var:improved_sleep", group="grp:completers"),
            cell("val:imp:pct", "percentage", "75.0", row=3, col_label="n (%)",
                 variable_id="var:improved_sleep", group="grp:completers"),
        ])


class TestTheControlStillRuns:
    def test_the_honest_paper_correctly_read_accuses_nobody(self):
        got = checks.evaluate(control_account(), CONTROL_TEXT)
        assert accusations(got) == []

    def test_and_it_still_runs_real_checks(self):
        """A round of fixes that bought its safety by refusing everything would
        pass every other test in this file."""
        got = checks.evaluate(control_account(), CONTROL_TEXT)
        assert got["n_run"] >= 3
        assert _ran(got, "chk:count_percent:val:imp:pct")["severity"] == "consistent"
        assert _ran(got, "chk:count_percent:val:imp:pct")["args"]["n"] == 32
        assert _ran(got, "chk:grim:val:nights:mean")["severity"] == "consistent"


# --------------------------------------------------------------------------
# A and G -- a `stated` bound is never compared against the printed values
# --------------------------------------------------------------------------


class TestAStatedBoundIsCheckedAgainstThePrintedValues:
    def test_an_item_range_read_against_a_total_score(self):
        """The paper states the ITEM range 0-4 and reports the TOTAL score. The
        quote is the paper's own, it locates, it is about this variable and it
        prints both numerals -- every existing test passes -- and 18.5 (SD 6.2)
        at n = 40 came back GRIM `impossible`, GRIMMER `suspicious`, SPRITE
        `suspicious` and `check_sd_or_se` `highly_suspicious`."""
        acc = account(
            variables=[var("var:pss", "Perceived Stress Scale", "integer_score",
                           bsource="stated", lower=0, upper=4,
                           bquote="The Perceived Stress Scale items were each rated "
                                  "from 0 to 4",
                           step=1,
                           gquote="the Perceived Stress Scale was scored in whole points")],
            values=[N40,
                    prose("val:pss:mean", "mean", "18.5",
                          "The mean Perceived Stress Scale score was 18.5 (SD 6.2).",
                          variable_id="var:pss"),
                    prose("val:pss:sd", "sd", "6.2",
                          "The mean Perceived Stress Scale score was 18.5 (SD 6.2).",
                          variable_id="var:pss")])
        got = checks.evaluate(acc, TEXT)
        assert accusations(got) == []
        for check_id in ("chk:grim:val:pss:mean", "chk:grimmer:val:pss:mean",
                         "chk:sprite:val:pss:mean", "chk:sd_or_se:val:pss:sd"):
            row = _ref(got, check_id)
            assert row is not None, check_id
            assert "bound_contradicted_by_printed_values" in {
                r["reason"] for r in row["reasons"]}, check_id

    def test_a_level_scale_read_against_a_change_score(self):
        """A change score runs on [-(max-min), +(max-min)] and the level scale is
        not its range. GRIM `impossible` plus two on an honest trial."""
        text = """# The Kestrel trial

## Methods

Forty adults were randomised and analysed; the analysed sample was n = 40.
Mood was rated on a 1 to 7 point scale and was scored in whole points.

## Results

Mood changed by a mean of -0.85 points (SD 1.42) between baseline and week 12.
"""
        acc = account(
            groups=[{"id": "grp:trial", "label": "Randomised sample", "n": 40,
                     "n_source": "text"}],
            variables=[var("var:mood", "mood", "integer_score", label="Mood rating",
                           bsource="stated", lower=1, upper=7,
                           bquote="Mood was rated on a 1 to 7 point scale", step=1,
                           gquote="Mood was rated on a 1 to 7 point scale and was "
                                  "scored in whole points")],
            values=[prose("val:n", "n", "40",
                          "Forty adults were randomised and analysed; the analysed "
                          "sample was n = 40.", group="grp:trial", id_check=None),
                    prose("val:chg:mean", "mean", "-0.85",
                          "Mood changed by a mean of -0.85 points (SD 1.42) between "
                          "baseline and week 12.", variable_id="var:mood",
                          group="grp:trial", phase="phase:change"),
                    prose("val:chg:sd", "sd", "1.42",
                          "Mood changed by a mean of -0.85 points (SD 1.42) between "
                          "baseline and week 12.", variable_id="var:mood",
                          group="grp:trial", phase="phase:change")])
        got = checks.evaluate(acc, text)
        assert accusations(got) == []

    def test_the_test_is_one_function_and_the_kind_path_still_uses_it(self):
        """`values_outside` has two callers on purpose: the kind's bound and the
        paper's own. A second copy of it is the defect this package keeps
        finding."""
        vals = [{"id": "a", "statistic": "mean", "printed": "18.5"},
                {"id": "b", "statistic": "sd", "printed": "99.0"},
                {"id": "c", "statistic": "count", "printed": "142"}]
        assert premises.values_outside(0, 4, vals) == ["a"]
        assert premises.values_outside(None, None, vals) == []
        assert premises.values_outside(0, 100, vals) == []

    def test_a_bound_the_printed_values_agree_with_is_untouched(self):
        """The other direction: an honest scale still reaches the tools."""
        got = checks.evaluate(control_account(), CONTROL_TEXT)
        acc = control_account()
        pss = next(v for v in acc["variables"] if v["id"] == "var:pss")
        pss["bounds"] = {"source": "stated", "lower": 0, "upper": 40,
                         "quote": "The Perceived Stress Scale items were each rated "
                                  "from 0 to 4"}
        del got
        stamped = premises.stamp(acc, TEXT)
        rec = next(v for v in stamped["variables"]
                   if v["id"] == "var:pss")["bounds"]["verification"]
        assert rec["bound_contradicted_by_printed_values"] == []


# --------------------------------------------------------------------------
# H -- a tie in the attribution test
# --------------------------------------------------------------------------


class TestATieIsNotAnAttribution:
    H_TEXT = """# The Fenwick cohort

## Methods

Forty adults were enrolled and analysed; the analysed sample was n = 40.

## Results

Table 1. Baseline characteristics of the 40 adults

Abbreviations: BMI, body mass index in kg per m2
PSS, Perceived Stress Scale, items rated 0 to 4

Body mass index averaged 27.4 kg per m2 (SD 4.6).
The mean Perceived Stress Scale score was 18.5 (SD 6.2).
"""

    def _account(self):
        return account(
            variables=[var("var:bmi", "body mass index", "continuous",
                           bsource="stated", lower=0, upper=4,
                           bquote="items rated 0 to 4"),
                       var("var:pss", "Perceived Stress Scale", "integer_score")],
            values=[prose("val:n", "n", "40",
                          "Forty adults were enrolled and analysed; the analysed "
                          "sample was n = 40.", id_check=None),
                    prose("val:bmi:mean", "mean", "27.4",
                          "Body mass index averaged 27.4 kg per m2 (SD 4.6).",
                          variable_id="var:bmi"),
                    prose("val:bmi:sd", "sd", "4.6",
                          "Body mass index averaged 27.4 kg per m2 (SD 4.6).",
                          variable_id="var:bmi")])

    def test_an_abbreviations_block_is_one_sentence_and_names_two_variables(self):
        """`Haystack.sentence` is right to read the whole sentence rather than
        the fragment, and an abbreviations block has no terminal punctuation, so
        one line expands into the block. Both variables scored 1.0, the tie
        passed because the comparison was STRICTLY greater, and an ordinary BMI
        of 27.4 (SD 4.6) was adjudicated against a 0-4 scale."""
        got = checks.evaluate(self._account(), self.H_TEXT)
        assert accusations(got) == []
        rec = next(v for v in premises.stamp(self._account(), self.H_TEXT)["variables"]
                   if v["id"] == "var:bmi")["bounds"]["verification"]
        assert rec["quote_names_another_variable"] == "var:pss"
        assert rec["lower_passed"] is None and rec["upper_passed"] is None

    def test_the_tie_rule_is_in_about_this_variable_and_needs_a_real_rival(self):
        mine = {"id": "var:a", "name": "Perceived Stress Scale", "printed_as": []}
        rival = {"id": "var:b", "name": "body mass index", "printed_as": []}
        both = "BMI, body mass index PSS, Perceived Stress Scale, items rated 0 to 4"
        assert premises.about_this_variable(mine, both, [rival])[
            "names_another_variable"] == "var:b"
        only_mine = "The Perceived Stress Scale was scored in whole points"
        assert premises.about_this_variable(mine, only_mine, [rival])[
            "names_another_variable"] is None


# --------------------------------------------------------------------------
# B and C -- the percentage's base
# --------------------------------------------------------------------------


B_TEXT = TEXT + """
Among the 32 adults who completed follow-up, 24 (75.0%) reported improved sleep.
Of the 24 adults who reported improved sleep, 14 (58.3%) were women.
Attendance was recorded for all 40 participants: 31 attended at least ten of the
twelve scheduled sessions, and attendance averaged 82.5% of scheduled sessions.
"""

GROUPS = [{"id": "grp:cohort", "label": "Whole cohort", "n": 40, "n_source": "text"}]


class TestThePercentagesBaseIsAPremise:
    def test_a_subgroup_percentage_over_the_cohort_n(self):
        """`24 (75.0)` is arithmetically perfect over the 32 completers; the
        cohort n of 40 is the only n at the coordinate. `check_count_percent`'s
        own escape hatch is one-sided -- `count >= n` returns `indeterminate`,
        and the commonest case is a base that is SMALLER."""
        acc = account(groups=GROUPS,
                      variables=[var("var:improved_sleep", "improved sleep",
                                     "percentage_of_subjects")],
                      values=[N40,
                              cell("val:t1:cnt", "count", "24", row=3, col_label="n (%)",
                                   variable_id="var:improved_sleep"),
                              cell("val:t1:pct", "percentage", "75.0", row=3,
                                   col_label="n (%)",
                                   variable_id="var:improved_sleep")])
        got = checks.evaluate(acc, B_TEXT)
        assert accusations(got) == []
        row = _ref(got, "chk:count_percent:val:t1:pct")
        assert row["reason"] == "another_denominator_fits"
        assert "32" in row["reasons"][0]["detail"]

    def test_a_row_percentage_in_a_crosstab(self):
        acc = account(groups=GROUPS,
                      variables=[var("var:women_improved", "women among improved "
                                     "sleepers", "percentage_of_subjects")],
                      values=[N40,
                              cell("val:t2:cnt", "count", "14", table="table:2", col=2,
                                   col_label="Women, n (%)",
                                   variable_id="var:women_improved"),
                              cell("val:t2:pct", "percentage", "58.3", table="table:2",
                                   col=2, col_label="Women, n (%)",
                                   variable_id="var:women_improved")],
                      tables=[{"id": "table:2", "caption": "Table 2. Sex distribution "
                                                           "by sleep outcome (row "
                                                           "percentages)."}])
        got = checks.evaluate(acc, B_TEXT)
        assert accusations(got) == []
        assert _ref(got, "chk:count_percent:val:t2:pct")["reason"] == \
            "another_denominator_fits"

    def test_the_family_keeps_its_power_where_no_other_base_fits(self):
        """THE CONTROL FOR THE TWO ABOVE, and the case the family exists for.
        `142 (73.0)` implies a denominator of 194.5 and NO integer denominator
        produces 73.0 from 142, so the disagreement is about the arithmetic and
        the check runs."""
        assert premises.other_bases_that_fit(142, 73.0, 1, 200, 200) == []
        assert premises.base_fits(146, 73.0, 1, 200) is True
        assert premises.other_bases_that_fit(24, 75.0, 1, 40, 40) == [32]
        # A base above every n the paper prints is arithmetic, not a base.
        assert premises.other_bases_that_fit(26, 0.867, 3, 30, 30) == []

    def test_a_prose_count_and_a_prose_percentage_of_something_else(self):
        """Two honest, unrelated quantities about one variable in one group,
        paired because the prose key is (study, group, phase, variable). The
        reading's own kind says the percentage is of SESSIONS, and the only
        denominator the account carries is a count of subjects."""
        acc = account(groups=GROUPS,
                      variables=[var("var:attendance", "clinic attendance",
                                     "percentage_of_observations")],
                      values=[N40,
                              prose("val:att:cnt", "count", "31",
                                    "Attendance was recorded for all 40 participants: 31 "
                                    "attended at least ten of the twelve scheduled "
                                    "sessions, and attendance averaged 82.5% of "
                                    "scheduled sessions.",
                                    variable_id="var:attendance", offset=100),
                              prose("val:att:pct", "percentage", "82.5",
                                    "Attendance was recorded for all 40 participants: 31 "
                                    "attended at least ten of the twelve scheduled "
                                    "sessions, and attendance averaged 82.5% of "
                                    "scheduled sessions.",
                                    variable_id="var:attendance", offset=200)])
        got = checks.evaluate(acc, B_TEXT)
        assert accusations(got) == []
        assert _ref(got, "chk:count_percent:val:att:pct")["reason"] == \
            "percentage_base_is_not_subjects"

    def test_the_denylist_names_only_kinds_that_contradict_a_subject_base(self):
        """`percentage_of_subjects` is NOT in it, and neither is any
        non-percentage kind: demanding a percentage kind would refuse 109 honest
        cells on jamanetworkopen.37679 alone."""
        assert "percentage_of_subjects" not in premises.NON_SUBJECT_PERCENTAGE_KINDS
        assert premises.NON_SUBJECT_PERCENTAGE_KINDS < premises.PERCENTAGE_KINDS


# --------------------------------------------------------------------------
# D, E, F -- three honest ways to bind the wrong denominator
# --------------------------------------------------------------------------


class TestTheDenominatorsOwnPremises:
    def test_a_cluster_trials_unit(self):
        """`group_n` resolves an n by (study, group) and asks four corroboration
        questions, none of which is 'does this n count the same THING'. Six
        clinics (n = 6) in the arm, 240 patients of those clinics, a mean of 3.4
        visits: GRIM `impossible` / `granularity` on a paper that printed both
        numbers correctly."""
        text = """# The Bayside cluster trial

## Methods

Twelve community clinics took part; six clinics (n = 6) were assigned to the
intervention arm and six to usual care.
Visits were counted as whole attendances per patient over the trial year.

## Results

The 240 patients of the intervention clinics attended a mean of 3.4 visits.
"""
        acc = account(
            groups=[{"id": "grp:intervention", "label": "Intervention arm", "n": 6,
                     "n_source": "text"}],
            variables=[var("var:visits", "visits", "count", step=1,
                           gquote="Visits were counted as whole attendances per patient")],
            values=[prose("val:d:n", "n", "6",
                          "Twelve community clinics took part; six clinics (n = 6) were "
                          "assigned to the intervention arm and six to usual care.",
                          group="grp:intervention", id_check=None),
                    prose("val:d:mean", "mean", "3.4",
                          "The 240 patients of the intervention clinics attended a mean "
                          "of 3.4 visits.", variable_id="var:visits",
                          group="grp:intervention")])
        got = checks.evaluate(acc, text)
        assert accusations(got) == []
        row = _ref(got, "chk:grim:val:d:mean")
        assert row["reason"] == "denominator_contradicted_by_the_sentence"

    def test_the_population_reader_needs_a_determiner_and_a_plural(self):
        """LARGER ONLY, and a decimal is not an integer: `of 8000.5 steps` is
        not a population, and a smaller integer in the same sentence may be
        anything a paper counts."""
        assert premises.population_sizes(
            "The 240 patients of the intervention clinics attended a mean of 3.4 "
            "visits.") == [240]
        assert premises.population_sizes(
            "Among the 32 adults who completed follow-up") == [32]
        assert premises.population_sizes(
            "Participants took a mean of 8000.5 steps per day (SD 3000.0).") == []
        assert premises.population_sizes(
            "The mean number of disturbed nights was 4.90 (SD 2.10).") == []

    def test_an_event_count_in_the_papers_own_n_notation(self):
        """`states_n` searched the row's own quote for `n = <that integer>`, so
        `Adverse events were recorded during the trial (n = 18).` corroborated
        itself and became the denominator of `9 (30.0%)` of thirty
        participants."""
        text = """# The Northgate trial

## Methods

Thirty participants were assigned to the intervention arm.

## Results

Adverse events were recorded during the trial (n = 18).
Nine of the thirty intervention participants experienced at least one adverse
event.
"""
        acc = account(
            groups=[{"id": "grp:intervention", "label": "Intervention arm"}],
            variables=[var("var:any_ae", "any adverse event", "percentage_of_subjects")],
            values=[prose("val:e:n", "n", "18",
                          "Adverse events were recorded during the trial (n = 18).",
                          group="grp:intervention", id_check=None),
                    cell("val:e:cnt", "count", "9", table="table:3", col_label="n (%)",
                         variable_id="var:any_ae", group="grp:intervention"),
                    cell("val:e:pct", "percentage", "30.0", table="table:3",
                         col_label="n (%)", variable_id="var:any_ae",
                         group="grp:intervention")],
            tables=[{"id": "table:3", "caption": "Table 3. Adverse events by arm."}])
        got = checks.evaluate(acc, text)
        assert accusations(got) == []
        assert _ref(got, "chk:count_percent:val:e:pct")["reason"] == "n_not_corroborated"

    def test_the_row_is_not_one_of_its_own_witnesses(self):
        rows = [{"id": "v", "n_premise": {"states_n": True}, "quote": "(n = 18)."}]
        assert premises.n_corroboration(rows, 18, {}) == []
        assert [w["by"] for w in premises.n_corroboration(
            rows, 18, {"n": 18, "n_source": "text"})] == ["declared_group_n"]

    def test_an_undeclared_subgroup_inherits_the_whole_studys_n(self):
        """The guard counted DECLARED groups, so a value whose coordinate names
        a group the structure never declared fell through to the study-level n
        and the guard saw ONE arm. The completers (32 of the 40 enrolled) then
        produced `check_count_percent` `suspicious` and GRIM `impossible`."""
        text = TEXT + (
            "\nAmong the 32 adults who completed follow-up, 24 (75.0%) reported "
            "improved sleep, and the mean number of disturbed nights among them was "
            "4.91.\n")
        n2 = dict(cell("val:f:n2", "n", "40", row=0, col_label="Whole cohort (n = 40)",
                       group=None), applies_to_all_groups=True)
        acc = account(
            groups=[{"id": "grp:cohort", "label": "Whole cohort", "n": 40,
                     "n_source": "text"}],
            variables=[var("var:improved_sleep", "improved sleep",
                           "percentage_of_subjects"),
                       var("var:nights", "disturbed nights", "count", step=1,
                           gquote="Nights with disturbed sleep were tallied as whole "
                                  "nights per participant over the recording "
                                  "fortnight.")],
            values=[prose("val:f:n", "n", "40",
                          "Forty adults enrolled at a single community clinic and were "
                          "analysed as one cohort; the enrolled sample was n = 40.",
                          group=None, id_check=None, applies_to_all=True),
                    n2,
                    cell("val:f:cnt", "count", "24", row=3, col_label="n (%)",
                         variable_id="var:improved_sleep", group="grp:completers"),
                    cell("val:f:pct", "percentage", "75.0", row=3, col_label="n (%)",
                         variable_id="var:improved_sleep", group="grp:completers"),
                    prose("val:f:mean", "mean", "4.91",
                          "Among the 32 adults who completed follow-up, 24 (75.0%) "
                          "reported improved sleep, and the mean number of disturbed "
                          "nights among them was 4.91.", variable_id="var:nights",
                          group="grp:completers")])
        got = checks.evaluate(acc, text)
        assert accusations(got) == []
        for check_id in ("chk:count_percent:val:f:pct", "chk:grim:val:f:mean"):
            assert _ref(got, check_id)["reason"] == "study_n_over_several_arms", check_id


# --------------------------------------------------------------------------
# I -- the SPRITE runtime guard measures the wrong axis
# --------------------------------------------------------------------------


class TestTheSpriteSearchCeiling:
    def _account(self, lower, upper):
        return account(
            groups=[{"id": "grp:cohort", "label": "Whole cohort", "n": 200,
                     "n_source": "text"}],
            variables=[var("var:steps", "daily step counts", "count",
                           bsource="stated", lower=lower, upper=upper,
                           bquote="Daily step counts were recorded as whole steps and "
                                  "ranged from 0 to 30000 steps per day",
                           step=1,
                           gquote="Daily step counts were recorded as whole steps")],
            values=[prose("val:n", "n", "200",
                          "Two hundred adults wore an accelerometer for fourteen days; "
                          "the analysed sample was n = 200.", id_check=None),
                    prose("val:steps:mean", "mean", "8000.5",
                          "Participants took a mean of 8000.5 steps per day (SD 3000.0).",
                          variable_id="var:steps"),
                    prose("val:steps:sd", "sd", "3000.0",
                          "Participants took a mean of 8000.5 steps per day (SD 3000.0).",
                          variable_id="var:steps")])

    STEP_TEXT = """# The Larkhill accelerometer study

## Methods

Two hundred adults wore an accelerometer for fourteen days; the analysed sample
was n = 200.
Daily step counts were recorded as whole steps and ranged from 0 to 30000 steps
per day.

## Results

Participants took a mean of 8000.5 steps per day (SD 3000.0).
"""

    def test_a_wide_stated_scale_refuses_by_name(self):
        """`SPRITE_MAX_N` was justified as "the search is linear in n", and it is
        not: it walks the SCALE. An honest step-count paper at n = 200 passes the
        n ceiling and cost 11 s of `evaluate` for ONE value. The per-candidate
        try/except catches exceptions, not seconds."""
        t0 = time.time()
        got = checks.evaluate(self._account(0, 30000), self.STEP_TEXT)
        elapsed = time.time() - t0
        row = _ref(got, "chk:sprite:val:steps:mean")
        assert row["reason"] == "sprite_search_too_large"
        assert str(checks.SPRITE_MAX_SEARCH) in row["reasons"][0]["detail"]
        assert elapsed < 8, f"{elapsed:.1f}s"

    def test_the_other_families_are_untouched(self):
        """It is a fact about this tool, not about the paper."""
        got = checks.evaluate(self._account(0, 30000), self.STEP_TEXT)
        assert _ran(got, "chk:grimmer:val:steps:mean") is not None
        assert _ran(got, "chk:sd_or_se:val:steps:sd") is not None

    def test_a_likert_width_scale_is_admitted_at_any_n_below_the_n_ceiling(self):
        """MEASURED: n = 5,000 on a span of 10 costs 4.2 s, and n = 4,999 on a
        span of 20 costs 24.5 s. The narrow-span clause is what keeps the common
        large-n Likert case."""
        assert 4999 * 6 > checks.SPRITE_MAX_SEARCH        # the product alone would refuse
        acc = self._account(0, 6)
        got = checks.evaluate(acc, self.STEP_TEXT)
        assert _ref(got, "chk:sprite:val:steps:mean") is None or \
            _ref(got, "chk:sprite:val:steps:mean")["reason"] != "sprite_search_too_large"


# --------------------------------------------------------------------------
# L -- an unhashable member is one skip, never the run
# --------------------------------------------------------------------------


UNHASHABLE = [
    ("location", "table_id", ["table:1"]),
    ("location", "table_id", {"id": "table:1"}),
    ("location", "row", [1, 2]),
    ("location", "col", [1]),
    ("location", "col_label", ["Mean", "(SD)"]),
    ("coordinate", "study_id", ["study:1", "study:2"]),
    ("coordinate", "group_id", {"id": "grp:cohort"}),
    ("coordinate", "phase_id", ["p1"]),
]


class TestAMalformedMemberIsOneSkip:
    def _account(self):
        return account(
            variables=[var("var:nights", "disturbed nights", "count", step=1,
                           gquote="Nights with disturbed sleep were tallied as whole "
                                  "nights per participant over the recording "
                                  "fortnight.")],
            values=[N40,
                    cell("val:m", "mean", "4.90", row=1, variable_id="var:nights"),
                    cell("val:s", "sd", "2.10", row=1, variable_id="var:nights")])

    @pytest.mark.parametrize("field,key,bad", UNHASHABLE)
    def test_an_unhashable_member_does_not_take_the_run(self, field, key, bad):
        """`well_formed` type-checked that `location`/`coordinate` ARE objects
        and never what was inside them, while `_cell_index`, `stamp` and the
        bridge's `_Index` build DICTIONARY KEYS out of their members. Seven
        shapes raised `TypeError: unhashable type` BEFORE the per-candidate
        try/except, so no `checks.json` and no `checks.md` were written."""
        acc = self._account()
        next(v for v in acc["values"] if v["id"] == "val:m")[field][key] = bad
        got = checks.evaluate(acc, TEXT)
        assert got["n_values_malformed"] == 1
        assert _ref(got, "chk:value:val:m")["reason"] == "value_malformed"
        assert got["n_run"] + got["n_refused"] == got["n_candidates"]

    def test_an_unhashable_variable_id_does_not_take_the_run(self):
        acc = self._account()
        next(v for v in acc["values"] if v["id"] == "val:m")["variable_id"] = ["var:nights"]
        got = checks.evaluate(acc, TEXT)
        assert got["n_values_malformed"] == 1

    def test_an_unhashable_group_id_in_the_structure_does_not_take_the_run(self):
        acc = self._account()
        acc["studies"][0]["groups"][0]["id"] = ["grp:cohort"]
        got = checks.evaluate(acc, TEXT)
        assert got["n_run"] + got["n_refused"] == got["n_candidates"]

    def test_the_test_is_on_the_type_and_not_on_a_list_of_field_names(self):
        """A field added later cannot reopen the hole."""
        assert premises.well_formed(
            {"id": "v", "location": {"a_field_nobody_has_added_yet": [1]}}) is not None
        assert premises.well_formed({"id": "v", "location": {"row": 1}}) is None
