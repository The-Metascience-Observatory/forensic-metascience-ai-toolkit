"""The sixteen defects a seventh adversarial pass found in the checks bridge, pinned.

THE PAPER IS NEW AND SO ARE THE SURFACES. "The Brackenridge community-pharmacy
medication-review audit" -- twenty-eight patients whose medicines a community
pharmacist reviews -- shares nothing with the Delta trial of
`test_scaffold_checks_adversarial.py`, the Harborview study of
`test_scaffold_checks_round3.py`, the Ashcombe trial of
`test_scaffold_checks_round4.py`, the Kelmscott survey of
`test_scaffold_checks_round5.py` or the Ashgrove sleep audit of
`test_scaffold_checks_round6.py`. Every number below is recomputed IN THIS FILE
from real integer data, so "the paper printed nothing wrong" is a fact rather
than an assertion, and any verdict worse than `consistent` or `indeterminate` is
a false accusation by construction.

THE SHAPE OF THE ROUND, IN ONE SENTENCE: nearly every defect is a guard that
asks its question of the wrong half of the account -- the group's n rather than
the study's, the value's `units` rather than the column's, the sentence rather
than the account's own `derivation` field -- so the SAME PAPER with the SAME
SENTENCES was refused when the reading recorded one thing and accused when it
recorded another. Four of the fixtures below are literally the same paper twice.

The sixteen, and where each is fixed:

  S   BOTH WAVE GUARDS WATCHED THE GROUP'S DOOR ONLY. `phases_with_n` is keyed on
      (study, group), and a single-arm paper states its enrolled n once as a
      sentence about the STUDY (`applies_to_all_groups`, filed under
      (study, None)); and the retention join ran only on the group's phase-less
      fallback, while the study-level branch sets `from_study`. Identical paper:
      refused with the n at the group, GRIM `impossible` with it at the study
      (`checks._Index.group_n`)
  B   TWO VARIABLES MAY SHARE ONE ID. Both readers of the variable table were
      last-write-wins and `duplicate_ids` was only ever asked about VALUES, so
      Study B's honest continuous 41.37 mg mean was adjudicated under Study A's
      `count` kind and stated step (`premises.variables_by_id`,
      `duplicate_variable_id`)
  G   THE CLAUSE SPLIT WAS THE SEMICOLON AND NOTHING ELSE, so one sentence
      contrasting two variables lent the first one's discreteness to the second
      (`premises._CLAUSE_BREAK`)
  Q   A CHANGE SCORE INHERITED THE LEVEL SCALE, because a derived variable is
      named after what it is derived from and round 6's contradiction guard sees
      only the variable's PRINTED values -- and a change score prints a mean and
      an SD (`premises.derived_range_changes`,
      `bound_stated_for_the_source_quantity`)
  J   A NUMERAL IN A GROUP'S LABEL CORROBORATED A DENOMINATOR without anyone
      asking what it counts, and the commonest numeral in a group label is a
      duration (`premises.numeral_counts_subjects`)
  A   THE AVERAGING VETO WAS A CLOSED NOUN LIST: 21 of 28 nouns a paper actually
      averages over evaded it. What separates a within-subject mean from a group
      mean is not the constituents' noun but whose average it is
      (`premises.AVERAGED`), and the account's own `derivation` field said so
      outright and was read by nothing (`premises.DERIVED_AVERAGE`)
  H   `_TABLE_LABEL` WAS ANCHORED AT `^`, so PLOS (`S1 Table.`) and BMC
      (`Additional file 1: Table S1.`) captions joined to no prose at all
      (`premises.table_label_pattern`)
  C   THE ALTERNATIVE-BASE CEILING READ THE PAPER THROUGH A TWO-WORD BUDGET, so
      a cohort printed with three adjectives sat above the paper's own ceiling
      (`premises._SUBJECT_COUNT`)
  E   THE RETENTION JOIN NEEDED BOTH SENTENCES TO NAME A STAGE THE VOCABULARY
      KNEW, and `the second assessment`, `the exit interview` and `endline` were
      not in it (`premises._STAGE_PHRASE`)
  F   THE CORRECTION NOTICE WAS READ BY TWO SENTENCE TEMPLATES, and three
      ordinary corrigendum wordings named the old number as the verb's OBJECT
      (`premises._SUPERSEDED_VALUE`, `_CORRECTED_VALUE`)
  P   THE UNIT GUARD NEEDED THE UNIT RECORDED TWICE. One-sided shapes are
      ordinary truthful readings -- the unit printed once over the column -- and
      all of them accused (`premises.printed_unit`, `premises.recorded_unit`)
  I   A NUMBER THIS PAPER QUOTES FROM ANOTHER PAPER was indistinguishable from
      one it reports (`premises.attributed_to_another_study`)
  N3  A PERCENTAGE THAT ROUNDS TO ZERO PINS NO BASE, and returning "no
      alternative" for it said the opposite to the one caller there is
      (`premises.other_bases_that_fit`)
  Z1  A VARIABLE ID THAT IS NOT A SCALAR raised out of the index, before the
      per-candidate try/except -- the class round 3 fixed for values, never
      applied to the variable table (`premises.well_formed_variable`)
  Z2  A `document` THAT IS A LIST raised out of `_captions`, same place, same
      consequence (`premises._captions`)
  Y   GRIMMER WAS WIRED WITH NO n CEILING while SPRITE had two, and the
      per-candidate try/except catches exceptions, not seconds
      (`checks.GRIMMER_MAX_N`)

THE COST SIDE IS ASSERTED THROUGHOUT, because a guard that bought its safety by
refusing everything would pass every attack here and be worthless: the fully
recorded table still reaches five verdicts, the corrected value beside a
withdrawn one still runs, our own mean beside a cited one still runs, and the
audit's own scale still passes on a derived variable whose derivation is a MEAN
(which is what three of ajcp.70049's live checks rest on).
"""

from __future__ import annotations

import statistics as st

import pytest

from metascience_agent.scaffold import checks, premises, schema

BAD = {"suspicious", "highly_suspicious", "impossible"}

# --------------------------------------------------------------------------
# The Brackenridge audit's real per-patient data
# --------------------------------------------------------------------------

#: Prescribed medicines per patient, whole counts, 28 patients, 151 in total.
MEDS = [3, 9, 8, 2, 5, 9, 7, 9, 1, 9, 0, 7, 4, 8, 3, 3, 7, 8,
        8, 7, 6, 2, 3, 2, 8, 6, 0, 7]

#: Each patient's THREE monthly pill counts. The adherence index is the mean of
#: her three, so it moves in steps of 1/3 and the group mean is 454/84.
PILL_COUNTS = [[5, 2, 6], [10, 0, 1], [8, 1, 5], [9, 0, 8], [3, 0, 1],
               [6, 6, 1], [3, 1, 8], [6, 0, 9], [1, 3, 10], [10, 9, 0],
               [9, 9, 6], [0, 3, 0], [8, 2, 4], [6, 2, 8], [1, 9, 4],
               [8, 10, 2], [1, 9, 9], [10, 3, 5], [1, 8, 11], [1, 9, 0],
               [9, 3, 7], [10, 8, 6], [12, 5, 7], [9, 7, 5], [4, 3, 12],
               [2, 11, 12], [3, 1, 9], [4, 8, 7]]
INDEX = [sum(p) / 3 for p in PILL_COUNTS]

#: The 24 patients who came back: their medicine counts, 170 in total.
W12 = [7, 4, 3, 12, 7, 9, 9, 11, 8, 5, 6, 7, 10, 3, 6, 12, 10, 3, 4, 4,
       10, 9, 3, 8]

#: Twenty-four whole-number CHANGES in prescribed medicines. Ten are negative --
#: those patients had medicines stopped -- so the quantity is not on the level
#: scale of 0 to 25 at all.
CHANGES = [-5, 0, 11, -5, 10, -10, -1, 4, 1, 5, 5, -4, 8, -1, 7, 5, 7, -4,
           -6, -8, 3, 7, 10, -8]

#: Study B's daily dose in MILLIGRAMS, a titrated continuous quantity.
DOSE_MG = [40.8, 44.6, 57.3, 41.3, 42.8, 45.6, 31.5, 42.9, 47.0, 52.8, 28.3,
           35.6, 28.2, 53.3, 49.3, 26.5, 59.4, 58.8, 47.9, 46.5, 30.5, 25.5,
           43.5, 27.1, 31.7, 33.5, 26.1, 60.1]

#: Total review time, RECORDED in whole minutes and REPORTED in hours.
REVIEW_MIN = 11369

N = len(MEDS)
MEDS_MEAN = f"{st.fmean(MEDS):.2f}"                 # 5.39
MEDS_SD = f"{st.stdev(MEDS):.2f}"                   # 2.96
INDEX_MEAN = f"{st.fmean(INDEX):.2f}"               # 5.40
INDEX_SD = f"{st.stdev(INDEX):.2f}"                 # 1.83
W12_MEAN = f"{sum(W12) / len(W12):.2f}"             # 7.08
CHANGE_MEAN = f"{st.fmean(CHANGES):.2f}"            # 1.29
CHANGE_SD = f"{st.stdev(CHANGES):.2f}"              # 6.40
DOSE_MEAN = f"{st.fmean(DOSE_MG):.2f}"              # 41.37
DOSE_SD = f"{st.stdev(DOSE_MG):.2f}"                # 11.17
TIME_H = f"{REVIEW_MIN / N / 60:.2f}"               # 6.77


def test_the_fixture_paper_is_honest():
    """Every printed number is the exact summary of real data, computed by the
    estimator the paper's own sentence names. Anything worse than `consistent`
    below is a false accusation as a matter of arithmetic."""
    assert (MEDS_MEAN, W12_MEAN, INDEX_MEAN) == ("5.39", "7.08", "5.40")
    assert (CHANGE_MEAN, CHANGE_SD) == ("1.29", "6.40")
    assert (DOSE_MEAN, TIME_H) == ("41.37", "6.77")
    assert sum(MEDS) == 151 and len(MEDS) == 28
    assert sum(W12) == 170 and len(W12) == 24
    # The index is a mean of THREE whole counts, so its own step is 1/3 and the
    # group mean is a total over 84 observations, not over 28.
    assert sum(sum(p) for p in PILL_COUNTS) == 454
    assert not any(round(k / N, 2) == float(INDEX_MEAN) for k in range(N * 13))
    # Ten of the 24 changes are negative, which is what makes the level scale
    # the wrong range rather than merely a generous one.
    assert sum(1 for x in CHANGES if x < 0) == 10 and sum(CHANGES) == 31
    # 7.08 is 170/24 exactly and unreachable over 28 whole counts.
    assert not any(round(k / N, 2) == 7.08 for k in range(N * 13))


# --------------------------------------------------------------------------
# The account shapes
# --------------------------------------------------------------------------

N_Q = ("Twenty-eight patients were enrolled in the Brackenridge "
       "medication-review audit (n = 28).")
MEDS_B = "Prescribed medicines ranged from 0 to 25 per patient."
MEDS_G = "Prescribed medicines were counted in whole units."


def var(vid, name, kind, *, bsource="not_stated", lower=None, upper=None,
        bquote=None, step=None, gquote=None, units=None, role=None,
        derivation=None, derived_from=(), printed_as=()):
    return {"id": vid, "name": name, "label": name,
            "printed_as": list(printed_as), "kind": kind, "role": role,
            "units": units, "units_source": "stated" if units else "not_stated",
            "derivation": derivation, "derived_from": list(derived_from),
            "bounds": {"source": bsource, "lower": lower, "upper": upper,
                       "quote": bquote},
            "granularity": {"per_subject_step": step, "quote": gquote}}


def meds_var(**kw):
    kw.setdefault("step", 1)
    kw.setdefault("gquote", MEDS_G)
    return var("var:medicines", "Prescribed medicines", "count", **kw)


def _lit(printed):
    return premises.read_plain(printed) or {}


def cell(vid, statistic, printed, *, table="table:1", row=1, col=1,
         col_label=None, variable_id=None, study="study:main", group="grp:all",
         phase=None, units=None):
    lit = _lit(printed)
    return {"id": vid, "statistic": statistic, "printed": printed,
            "numeric": lit.get("value"), "decimals": lit.get("decimals", 0),
            "printed_form": "percent" if lit.get("is_percent") else "plain",
            "units": units, "variable_id": variable_id, "id_check": "agrees",
            "statistic_disputed": False, "source": "table", "quote": None,
            "quote_verified": "cell", "printed_in_quote": None,
            "location": {"kind": "table_cell", "table_id": table, "row": row,
                         "col": col, "col_label": col_label},
            "coordinate": {"study_id": study, "group_id": group,
                           "phase_id": phase}}


def prose(vid, statistic, printed, quote, *, variable_id=None,
          study="study:main", group="grp:all", phase=None, id_check="agrees",
          offset=0, applies_to_all=False, units=None):
    lit = _lit(printed)
    out = {"id": vid, "statistic": statistic, "printed": printed,
           "numeric": lit.get("value"), "decimals": lit.get("decimals", 0),
           "printed_form": "percent" if lit.get("is_percent") else "plain",
           "units": units, "variable_id": variable_id, "id_check": id_check,
           "statistic_disputed": False, "source": "prose", "quote": quote,
           "quote_verified": "verbatim", "printed_in_quote": True,
           "location": {"kind": "prose", "offset": offset, "col_label": None},
           "coordinate": {"study_id": study, "group_id": group,
                          "phase_id": phase}}
    if applies_to_all:
        out["applies_to_all_groups"] = True
    return out


def n_row(printed="28", quote=N_Q, **kw):
    return prose("val:n", "n", printed, quote, **kw)


def one_group(n=28, gid="grp:all", sid="study:main", label="All patients"):
    return [{"id": sid, "design": "prospective_cohort",
             "groups": [{"id": gid, "label": label, "n": n,
                         "n_source": "text"}]}]


def account(*, variables=(), values=(), studies=None, tables=None):
    return {
        "paper": {"doi": "10.0000/brackenridge",
                  "title": "The Brackenridge community-pharmacy "
                           "medication-review audit"},
        "studies": list(studies) if studies is not None else one_group(),
        "variables": list(variables), "values": list(values),
        "document": {"tables": list(tables) if tables is not None else [
            {"id": "table:1", "caption": "Table 1. Medicines and adherence of "
                                         "the audited patients."}]},
    }


def accusations(got):
    return [r for r in got["checks"] if r["severity"] in BAD]


def refusals(got):
    return {r["check_id"]: r["reason"] for r in got["refused"]}


def every_reason(got):
    return {row["reason"] for r in got["refused"] for row in r["reasons"]}


def ran(got):
    return {r["check_id"] for r in got["checks"]}


# --------------------------------------------------------------------------
# S -- THE WAVE GUARDS WATCHED THE GROUP'S DOOR AND A STUDY-LEVEL n WALKED PAST
# --------------------------------------------------------------------------

S_MEAN_Q = ("At the twelve-week review visit the mean number of prescribed "
            f"medicines was {W12_MEAN}.")
S_ATTENDED = "Twenty-four patients attended the twelve-week review visit."
S_TEXT = f"{N_Q} {S_ATTENDED} {S_MEAN_Q}\n"

S_N24_Q = "Twenty-four patients were assessed at twelve weeks (n = 24)."
S_TEXT_2 = f"{N_Q} {S_N24_Q} {S_MEAN_Q}\n"


def _s_account(*, n_at_study):
    """The enrolled n as the STUDY's (a sentence about the study, applying to
    every group) or as the group's own phase-less row. Same paper either way."""
    kw = {"group": None, "applies_to_all": True} if n_at_study else {}
    return account(variables=[meds_var(gquote=None)],
                   values=[n_row(**kw),
                           prose("val:m12", "mean", W12_MEAN, S_MEAN_Q,
                                 variable_id="var:medicines",
                                 phase="phase:w12", offset=120)])


def _s_perwave_account(*, n_at_study):
    kw = {"group": None, "applies_to_all": True} if n_at_study else {}
    return account(
        variables=[meds_var(gquote=None)],
        values=[n_row(**kw),
                prose("val:n24", "n", "24", S_N24_Q, phase="phase:w12",
                      offset=90, **kw),
                # the ordinary shape of a results sentence: the wave is in the
                # words, not in the coordinate
                prose("val:m12", "mean", W12_MEAN, S_MEAN_Q,
                      variable_id="var:medicines", offset=150)])


class TestTheWaveGuardsWatchTheStudysDoorToo:
    @pytest.mark.parametrize("n_at_study", [True, False])
    def test_the_retention_join_fires_wherever_the_n_was_recorded(self, n_at_study):
        """`7.08` is 170/24 exactly. The paper states the twenty-four in prose
        with no `n = 24` notation to key on, so the only n in the account is the
        enrolled 28 -- and 7.08 x 28 = 198.24."""
        got = checks.evaluate(_s_account(n_at_study=n_at_study), S_TEXT)
        assert accusations(got) == []
        assert refusals(got)["chk:grim:val:m12"] == "analysed_n_stated_for_another_stage"

    @pytest.mark.parametrize("n_at_study", [True, False])
    def test_the_per_wave_guard_fires_wherever_the_n_was_recorded(self, n_at_study):
        """Here the account DOES hold the per-wave n, and the value names no
        phase: the account's own rows say the denominator varies by wave."""
        got = checks.evaluate(_s_perwave_account(n_at_study=n_at_study), S_TEXT_2)
        assert accusations(got) == []
        assert refusals(got)["chk:grim:val:m12"] == "phase_n_over_several_phases"

    def test_the_study_level_n_is_what_a_single_arm_paper_produces(self):
        """The premise the fix rests on, asserted rather than assumed: a
        sentence about the STUDY has no group in its coordinate, so its n row is
        filed under (study, None) and a guard keyed on (study, group) cannot see
        it."""
        idx = checks._Index(_s_perwave_account(n_at_study=True), S_TEXT_2)
        assert idx.phases_with_n.get(("study:main", "grp:all")) is None
        assert idx.phases_with_n[("study:main", None)] == {"phase:w12"}


# --------------------------------------------------------------------------
# B -- TWO VARIABLES SHARING ONE ID
# --------------------------------------------------------------------------

B_TEXT = ("Study A audited twenty-eight patients (n = 28) at the Brackenridge "
          "practice; the daily dose was counted in whole tablets dispensed per "
          "day. Study B audited a further twenty-eight patients (n = 28) whose "
          "daily dose is reported in milligrams of the active drug per day.\n")
B_GRAN_A = ("Study A audited twenty-eight patients (n = 28) at the Brackenridge "
            "practice; the daily dose was counted in whole tablets dispensed "
            "per day.")
B_N_Q = ("Study B audited a further twenty-eight patients (n = 28) whose daily "
         "dose is reported in milligrams of the active drug per day.")


def _b_account(*, collide):
    """A slug-from-name reading mints `var:daily_dose` for both studies: Study
    A's whole tablets per day and Study B's titrated milligrams per day."""
    id_b = "var:daily_dose" if collide else "var:daily_dose_mg"
    return account(
        variables=[var(id_b, "Daily dose", "continuous", units="mg"),
                   var("var:daily_dose", "Daily dose", "count", step=1,
                       gquote=B_GRAN_A, units="tablets")],
        studies=one_group(28, gid="grp:b", sid="study:b"),
        tables=[{"id": "table:2", "caption": "Table 2. Daily dose in Study B."}],
        values=[prose("val:n_b", "n", "28", B_N_Q, study="study:b",
                      group="grp:b"),
                cell("val:b_mean", "mean", DOSE_MEAN, table="table:2",
                     col_label="Mean (SD)", variable_id=id_b, study="study:b",
                     group="grp:b"),
                cell("val:b_sd", "sd", DOSE_SD, table="table:2",
                     col_label="Mean (SD)", variable_id=id_b, study="study:b",
                     group="grp:b")])


class TestTwoVariablesMayNotShareOneId:
    def test_the_collision_refuses_by_name_rather_than_borrowing_the_premises(self):
        """41.37 mg is an ordinary continuous mean; under the OTHER variable's
        `count` kind and stated step it was GRIM `impossible`, with `data_type:
        count` and `discreteness_source: stated` both borrowed."""
        got = checks.evaluate(_b_account(collide=True), B_TEXT)
        assert accusations(got) == []
        assert refusals(got)["chk:grim:val:b_mean"] == "duplicate_variable_id"

    def test_distinct_ids_reach_the_variable_they_name(self):
        """THE CONTROL, and it is what says the refusal is about the collision:
        the same account with two ids refuses on the KIND, which is the honest
        answer for a continuous quantity."""
        got = checks.evaluate(_b_account(collide=False), B_TEXT)
        assert accusations(got) == []
        assert refusals(got)["chk:grim:val:b_mean"] == "kind_not_integer"

    def test_a_duplicated_id_is_dropped_rather_than_resolved(self):
        variables = _b_account(collide=True)["variables"]
        assert premises.duplicate_ids(variables) == {"var:daily_dose"}
        assert premises.variables_by_id(variables) == {}

    def test_the_schema_names_it_too(self):
        """`schema.validate` reported a duplicate VALUE id while reading the
        variable table into a SET four lines earlier, so the one function whose
        job is to name a collision could not see this one."""
        acc = _b_account(collide=True)
        assert any("duplicate variable id `var:daily_dose`" in p
                   for p in schema.validate_account(acc))
        assert not any("duplicate variable id" in p
                       for p in schema.validate_account(_b_account(collide=False)))


# --------------------------------------------------------------------------
# G -- ONE SENTENCE, TWO VARIABLES, ONE CLAUSE
# --------------------------------------------------------------------------

G_SENTENCES = {
    "comma_whereas": ("Medicines were counted in whole units, whereas review "
                      "time was taken from the dispensing log in minutes and "
                      "seconds."),
    "comma_while": ("Medicines were counted in whole units, while review time "
                    "was taken from the dispensing log in minutes and "
                    "seconds."),
    "semicolon": ("Medicines were counted in whole units; review time was "
                  "taken from the dispensing log in minutes and seconds."),
}


def _g_account(sentence):
    return account(
        variables=[meds_var(gquote=None),
                   var("var:review_time", "Review time", "integer_score",
                       step=1, gquote=sentence)],
        values=[n_row(),
                cell("val:time_mean", "mean", "40.37", col_label="Mean (SD)",
                     variable_id="var:review_time")])


class TestAContrastiveClauseIsAClause:
    @pytest.mark.parametrize("key", sorted(G_SENTENCES))
    def test_the_discreteness_words_stay_with_the_variable_they_describe(self, key):
        """1130.4 minutes over 28 patients is 40.3714 -> `40.37`, and the two
        whole-minute totals either side print 40.36 and 40.39 -- so a step of 1
        borrowed from MEDICINES makes an honest continuous mean `impossible`.
        The A/B is the punctuation and nothing else."""
        text = f"{N_Q} {G_SENTENCES[key]}\n"
        got = checks.evaluate(_g_account(G_SENTENCES[key]), text)
        assert accusations(got) == []
        assert refusals(got)["chk:grim:val:time_mean"] == "discreteness_assumed"

    def test_and_a_conjunction_inside_one_statement_still_does_not_split(self):
        """THE COST SIDE, and it is the reason `and` is not on the list: `Mood
        was rated on a 1 to 7 point scale and was scored in whole points` is ONE
        statement about one subject, and splitting it there would refuse the
        paper's own granularity sentence."""
        one = "Mood was rated on a 1 to 7 point scale and was scored in whole points"
        assert premises._clauses(one) == [one]
        assert premises._clauses("A was counted in whole units; B was timed") == [
            "A was counted in whole units", "B was timed"]


# --------------------------------------------------------------------------
# Q -- A CHANGE SCORE INHERITING THE LEVEL SCALE
# --------------------------------------------------------------------------

Q_TEXT = f"Twenty-four patients completed both reviews (n = 24). {MEDS_B} {MEDS_G}\n"


def _q_account(*, declare_level_variable):
    """The paper reports the CHANGE. Declaring the level variable too makes the
    attribution a tie, which already refused -- so the accusation appeared only
    where the reading had recorded LESS."""
    variables = [var("var:change", "Change in prescribed medicines",
                     "integer_score", role="derived_outcome", bsource="stated",
                     lower=0, upper=25, bquote=MEDS_B, step=1, gquote=MEDS_G,
                     derivation="twelve-week count minus baseline count",
                     derived_from=["var:medicines"])]
    if declare_level_variable:
        variables.append(meds_var())
    return account(
        variables=variables, studies=one_group(24),
        tables=[{"id": "table:1", "caption": "Table 1. Change in prescribed "
                                             "medicines over twelve weeks."}],
        values=[n_row("24", "Twenty-four patients completed both reviews (n = 24)."),
                cell("val:chg_mean", "mean", CHANGE_MEAN, col_label="Mean (SD)",
                     variable_id="var:change"),
                cell("val:chg_sd", "sd", CHANGE_SD, col_label="Mean (SD)",
                     variable_id="var:change")])


class TestADerivedQuantitysBoundIsItsOwn:
    @pytest.mark.parametrize("declared", [True, False])
    def test_the_level_scale_is_not_the_change_scores_range(self, declared):
        """A change runs on [-(max-min), +(max-min)]; ten of these 24 patients
        had medicines STOPPED. Round 6's `bound_contradicted_by_printed_values`
        cannot see it, because a change score prints a mean and an SD and
        `1.29 (6.40)` sits inside [0, 25]. SPRITE was asked to rebuild
        non-negative integers out of it."""
        got = checks.evaluate(_q_account(declare_level_variable=declared), Q_TEXT)
        assert accusations(got) == []

    def test_the_refusal_names_the_derivation(self):
        got = checks.evaluate(_q_account(declare_level_variable=False), Q_TEXT)
        assert refusals(got)["chk:grimmer:val:chg_mean"] == \
            "bound_stated_for_the_source_quantity"
        stamped = premises.stamp(_q_account(declare_level_variable=False), Q_TEXT)
        rec = stamped["variables"][0]["bounds"]["verification"]
        assert rec["derived_range_changes"] == "minus"
        assert rec["lower_passed"] is None and rec["upper_passed"] is None

    def test_a_mean_of_items_keeps_the_items_scale(self):
        """THE COST SIDE, AND IT IS A LIVE ONE. A rule keyed on derivedness
        alone would take three of ajcp.70049's own checks: a MEAN of k items on
        [a, b] is still on [a, b], and the account marks such a variable
        derived. Only a derivation that MOVES the range withdraws the scale."""
        mean_of_items = var(
            "var:engagement", "Engaging communication", "integer_score",
            role="derived_outcome", derived_from=["var:item"],
            derivation="the mean of member responses to four items")
        assert premises.derived_range_changes(mean_of_items) is None
        assert premises.derived_range_changes(
            var("var:total", "Total score", "integer_score")) is None


# --------------------------------------------------------------------------
# J -- A NUMERAL IN A GROUP'S LABEL THAT COUNTS MONTHS
# --------------------------------------------------------------------------

J_N_Q = "Twelve community pharmacies took part in the audit (n = 12)."
J_TEXT = (J_N_Q + " The twelve pharmacies enrolled thirty patients between "
          "them.\n")


def _j_account(label):
    return account(
        variables=[meds_var()],
        studies=[{"id": "study:main", "design": "prospective_cohort",
                  "groups": [{"id": "grp:all", "label": label, "n": None,
                              "n_source": None}]}],
        values=[n_row("12", J_N_Q),
                cell("val:mean", "mean", "5.03", col_label="Mean (SD)",
                     variable_id="var:medicines")])


class TestAGroupLabelsNumeralIsAskedWhatItCounts:
    @pytest.mark.parametrize("label", ["12-month cohort", "12 month cohort",
                                       "Community pharmacy cohort"])
    def test_a_duration_in_the_label_corroborates_nothing(self, label):
        """Twelve pharmacies enrolled thirty patients taking 151 medicines:
        151/30 = 5.03, and 5.03 x 12 = 60.36. The cluster design supplies the
        matching integer honestly, and `12-month cohort` supplied the
        corroboration that let it be divided by."""
        got = checks.evaluate(_j_account(label), J_TEXT)
        assert accusations(got) == []
        assert refusals(got)["chk:grim:val:mean"] == "n_not_corroborated"

    def test_a_count_in_the_label_still_corroborates(self):
        """THE COST SIDE: a label that prints the arm's own size is the witness
        this test exists for, and it is untouched."""
        assert premises.numeral_counts_subjects("Intervention (12 patients)", 12)
        assert premises.numeral_counts_subjects("Arm B, n = 12", 12)
        assert not premises.numeral_counts_subjects("12-month cohort", 12)
        assert not premises.numeral_counts_subjects("2019 cohort", 2019)


# --------------------------------------------------------------------------
# A -- THE AVERAGING VETO AS A CLOSED NOUN LIST
# --------------------------------------------------------------------------

A_GRAN = ("Tablets were counted in whole units, and each patient's adherence "
          "index is the mean of her three monthly pill counts.")
A_BOUND = "The adherence index runs from 0 to 30 tablets returned per month."
A_TEXT = (f"{N_Q} {A_GRAN} {A_BOUND} Across the audit 454 tablets were "
          "returned in total.\n")

#: Nouns a paper averages over. Seven were in the list; the other twenty-one
#: were not, and every one of them said exactly the same thing.
A_NOUNS = ["ratings", "assessments", "observations", "readings", "trials",
           "items", "measurements", "counts", "visits", "sessions", "nights",
           "days", "weeks", "months", "reviews", "encounters", "episodes",
           "samples", "records", "occasions", "waves", "appointments",
           "interviews", "consultations", "tallies", "totals", "scores",
           "results"]


def _a_account(gran_quote, *, derivation="mean of the three monthly pill counts"):
    return account(
        variables=[var("var:adherence_index", "Adherence index", "count",
                       bsource="stated", lower=0, upper=30, bquote=A_BOUND,
                       step=1, gquote=gran_quote, derivation=derivation,
                       derived_from=["var:pill_count"]),
                   var("var:quiz", "Knowledge quiz score", "integer_score")],
        values=[n_row(),
                cell("val:index_mean", "mean", INDEX_MEAN,
                     col_label="Mean (SD)", variable_id="var:adherence_index"),
                cell("val:index_sd", "sd", INDEX_SD, col_label="Mean (SD)",
                     variable_id="var:adherence_index")])


class TestTheAveragingVetoIsNotANounList:
    def test_a_mean_of_three_whole_counts_keeps_no_step_of_one(self):
        """The group mean is 454/84, not an integer over 28: GRIM, GRIMMER and
        SPRITE all returned `impossible` because the constituents were called
        `pill counts` rather than `pill assessments`."""
        got = checks.evaluate(_a_account(A_GRAN), A_TEXT)
        assert accusations(got) == []
        for family in ("grim", "grimmer", "sprite"):
            assert refusals(got)[f"chk:{family}:val:index_mean"] in {
                "discreteness_quote_reports_an_average",
                "derivation_reports_an_average"}

    @pytest.mark.parametrize("noun", A_NOUNS)
    def test_every_noun_a_paper_averages_over_is_vetoed(self, noun):
        """The veto reads WHOSE average it is, not what was averaged."""
        s = ("Events were counted in whole units, and each patient's index is "
             f"the mean of her three monthly {noun}.")
        assert premises.AVERAGED.search(s), noun

    def test_a_group_mean_is_not_vetoed(self):
        """THE COST SIDE, and it is the whole reason the noun list was narrow:
        `a mean of 3.4 visits` is what every results sentence looks like, and a
        group mean IS an integer total over n."""
        for honest in ("Patients took a mean of 5.39 medicines.",
                       "The mean of the 28 patients was 5.39.",
                       "The mean of the children's scores was 11.90.",
                       "Attendance averaged 82.5% of scheduled sessions.",
                       "Body mass averaged 78.4 kg."):
            assert not premises.AVERAGED.search(honest), honest

    def test_the_accounts_own_derivation_is_read(self):
        """It said `mean of the three monthly pill counts` in a field the schema
        asks for, and no line of `premises` or `checks` read `derivation` or
        `derived_from`."""
        got = checks.evaluate(_a_account("Tablets were counted in whole units."),
                              A_TEXT)
        assert accusations(got) == []
        assert "derivation_reports_an_average" in every_reason(got)

    def test_the_papers_own_sentence_is_read_wherever_it_sits(self):
        """ROUND 9. The account offers a granularity quote saying only the
        whole-unit half, and the averaging half is a DIFFERENT sentence of the
        same paper -- which the veto never read, because it read the clauses of
        the offered quote's sentence only. The served-text witness fires here
        with `derivation` NULL, which is the honest omission the round-9 fixture
        was built on."""
        acc = _a_account("Tablets were counted in whole units.", derivation=None)
        got = checks.evaluate(acc, A_TEXT)
        assert accusations(got) == []
        assert refusals(got)["chk:grim:val:index_mean"] == \
            "discreteness_quote_reports_an_average"
        rec = [v for v in premises.stamp(acc, A_TEXT)["variables"]
               if v["id"] == "var:adherence_index"][0]["granularity"]["verification"]
        assert rec["reports_an_average_in"] == "served_text"
        assert rec["paper_reports_an_average"]

    def test_a_derivation_that_is_not_an_average_keeps_the_step(self):
        """THE COST SIDE for the derivation reader: a difference of whole counts
        is a whole count, and only an AVERAGE withdraws the step.

        THE PAPER MUST NOT SAY IT EITHER, which is what the round-9 served-text
        witness added: `A_TEXT` itself says the index IS the mean of her three
        monthly pill counts, so on that text the step is withdrawn whatever the
        derivation says -- correctly, and by the paper rather than by the
        account. The text here isolates the derivation reader, which is what
        this case was written to test."""
        text = (f"{N_Q} Tablets were counted in whole units. {A_BOUND} Across "
                "the audit 454 tablets were returned in total.\n")
        got = checks.evaluate(
            _a_account("Tablets were counted in whole units.",
                       derivation="the twelve-week count minus the baseline count"),
            text)
        assert "chk:grim:val:index_mean" in ran(got)
        assert "derivation_reports_an_average" not in every_reason(got)


# --------------------------------------------------------------------------
# H -- A TABLE WHOSE CAPTION DOES NOT START WITH ITS NAME
# --------------------------------------------------------------------------

H_BOUND = ("The Brackenridge adherence score is scored from 0 to 21, in whole "
           "points.")
H_CAPTIONS = {
    "Table 4. Twelve-week adherence.": "Table 4",
    "S1 Table. Twelve-week adherence.": "S1 Table",
    "Additional file 1: Table S1. Twelve-week adherence.":
        "Additional file 1: Table S1",
    "Table S1. Twelve-week adherence.": "Table S1",
    "eTable 2. Twelve-week adherence.": "eTable 2",
    "Appendix Table 1. Twelve-week adherence.": "Appendix Table 1",
}


def _h_account(caption):
    return account(
        variables=[var("var:adherence_score", "Brackenridge adherence score",
                       "integer_score", bsource="stated", lower=0, upper=21,
                       bquote=H_BOUND, step=1, gquote=H_BOUND)],
        tables=[{"id": "table:x", "caption": caption}],
        values=[n_row(),
                cell("val:b", "mean", "8.58", table="table:x",
                     col_label="Twelve weeks", variable_id="var:adherence_score"),
                cell("val:se", "sd", "3.03", table="table:x",
                     col_label="Twelve weeks",
                     variable_id="var:adherence_score")])


class TestATablesNameNeedNotComeFirst:
    @pytest.mark.parametrize("caption,label", sorted(H_CAPTIONS.items()))
    def test_the_papers_own_prose_reaches_a_supplement_table(self, caption, label):
        """A mixed-effects coefficient 8.58 and its standard error 3.03, printed
        in the supplement and named as a model in the paper's own words. With no
        joinable label the note channel is severed and the pair is adjudicated
        as a mean and an SD of a 0-21 whole-point score."""
        text = (f"{N_Q} {H_BOUND} "
                f"{label} gives the mixed-effects model for twelve-week "
                "adherence.\n")
        got = checks.evaluate(_h_account(caption), text)
        assert accusations(got) == []
        assert refusals(got)["chk:grim:val:b"] == "reports_model_output"

    @pytest.mark.parametrize("caption,expected", [
        ("Table 4. Twelve-week adherence.", "Table 4"),
        ("S1 Table. Mixed-effects model.", "S1 Table"),
        ("Additional file 1: Table S1. Mixed-effects model.", "Table S1"),
        ("Supplementary Table 3. Mixed-effects model.", "Supplementary Table 3"),
    ])
    def test_the_prose_pattern_is_built_in_the_order_the_caption_printed(
            self, caption, expected):
        rx = premises.table_label_pattern(caption)
        assert rx is not None and rx.search(f"{expected} gives the model.")

    def test_a_caption_that_names_no_table_still_joins_to_nothing(self):
        """THE COST SIDE. Guessing a printed label from the internal handle
        would invent the join, and a cross-reference deep in a caption is not
        this table's own name."""
        assert premises.table_label_pattern("S2 Fig. The trial profile.") is None
        assert premises.table_label_pattern("Characteristics of the sample.") is None
        assert premises.table_label_pattern(
            "Baseline characteristics of the audited patients, by practice "
            "(see Table 2 for the model).") is None


# --------------------------------------------------------------------------
# C -- THE PAPER'S OWN COHORT, ABOVE THE PAPER'S OWN CEILING
# --------------------------------------------------------------------------

C_COHORTS = [
    "One hundred and twelve eligible pharmacists were screened.",
    "One hundred and twelve eligible registered community pharmacists were "
    "screened.",
    "One hundred and twelve eligible, registered pharmacists were screened.",
    "In all 112 eligible pharmacists were screened.",
    "In all 112 eligible registered community pharmacists were screened.",
]


def _c_account():
    return account(
        variables=[var("var:declined", "Declined to take part",
                       "percentage_of_subjects")],
        values=[n_row("28", "Twenty-eight pharmacists took part in the audit "
                            "(n = 28)."),
                cell("val:declined_count", "count", "9", row=3,
                     col_label="n (%)", variable_id="var:declined"),
                cell("val:declined_pct", "percentage", "8.0", row=3,
                     col_label="n (%)", variable_id="var:declined")])


class TestTheCeilingReadsThePapersOwnCohort:
    @pytest.mark.parametrize("cohort", C_COHORTS)
    def test_the_base_the_paper_prints_is_named_however_it_prints_it(self, cohort):
        """9 of the 112 screened declined: 9/112 = 8.036% -> `8.0`, and the
        coordinate's n is the 28 who took part. A base the ceiling excludes is
        not a base named -- it is a check that RUNS and accuses."""
        text = f"{cohort} Twenty-eight pharmacists took part in the audit (n = 28).\n"
        got = checks.evaluate(_c_account(), text)
        assert accusations(got) == []
        assert refusals(got)["chk:count_percent:val:declined_pct"] == \
            "another_denominator_fits"
        assert 112 in premises.printed_subject_counts(text)


# --------------------------------------------------------------------------
# E -- A WAVE THE STAGE VOCABULARY HAD NEVER HEARD OF
# --------------------------------------------------------------------------

E_WORDINGS = {
    "twelve_week_visit": ("Twenty-four patients attended the twelve-week visit.",
                          "At the twelve-week visit the mean number of "
                          f"prescribed medicines was {W12_MEAN}."),
    "second_assessment": ("Twenty-four patients completed the second assessment.",
                          "At the second assessment the mean number of "
                          f"prescribed medicines was {W12_MEAN}."),
    "exit_interview": ("Twenty-four patients completed the exit interview.",
                       "At the exit interview the mean number of prescribed "
                       f"medicines was {W12_MEAN}."),
    "endline": ("Twenty-four patients were assessed at endline.",
                f"At endline the mean number of prescribed medicines was "
                f"{W12_MEAN}."),
    "final_review": ("Twenty-four patients completed the final review.",
                     "At the final review the mean number of prescribed "
                     f"medicines was {W12_MEAN}."),
}


class TestAStageIsWhateverThePaperCallsIt:
    @pytest.mark.parametrize("key", sorted(E_WORDINGS))
    def test_the_retention_join_works_in_the_papers_own_words(self, key):
        retained, mean_quote = E_WORDINGS[key]
        acc = account(variables=[meds_var(gquote=None)],
                      values=[n_row(),
                              prose("val:m12", "mean", W12_MEAN, mean_quote,
                                    variable_id="var:medicines",
                                    phase="phase:w2", offset=140)])
        got = checks.evaluate(acc, f"{N_Q} {retained} {mean_quote}\n")
        assert accusations(got) == []
        assert refusals(got)["chk:grim:val:m12"] == \
            "analysed_n_stated_for_another_stage"

    def test_a_sentence_that_names_no_stage_still_joins_to_nothing(self):
        """THE LIMIT IS STATED RATHER THAN HIDDEN, and it is what keeps the rule
        a guard rather than a veto: a results sentence naming no wave joins to
        nothing, and that shape keeps its check."""
        assert premises.stage_phrases("The mean number of medicines was 7.08.") == []
        assert premises.stage_phrases("At the second assessment") == ["second assessment"]
        assert premises.stage_phrases("at endline") == ["endline"]


# --------------------------------------------------------------------------
# F -- A CORRECTION NOTICE WRITTEN IN PROSE
# --------------------------------------------------------------------------

F_NOTICES = {
    "given_as": ("Correction. In the originally published article the mean "
                 "adherence score was given as 8.58; the correct value is 8.54."),
    "reported_a_mean_of": ("Correction. In the original article, Table 2 "
                           "reported a mean of 8.58; this has been corrected "
                           "to 8.54."),
    "is_wrong_should_be": ("Correction. The value 8.58 in Table 2 is wrong; it "
                           "should be 8.54."),
    "rather_than": ("Correction. In the originally published article the mean "
                    "adherence score was 8.58 rather than 8.54."),
}


def _f_account(notice):
    return account(
        variables=[var("var:adherence_score", "Brackenridge adherence score",
                       "integer_score", bsource="stated", lower=0, upper=21,
                       bquote=H_BOUND, step=1, gquote=H_BOUND)],
        values=[n_row(),
                prose("val:old", "mean", "8.58", notice,
                      variable_id="var:adherence_score", offset=200),
                prose("val:new", "mean", "8.54", notice,
                      variable_id="var:adherence_score", offset=201)])


class TestACorrectionIsWrittenInProse:
    @pytest.mark.parametrize("key", sorted(F_NOTICES))
    def test_the_withdrawn_number_is_withdrawn_and_the_corrected_one_is_not(self, key):
        """239 whole adherence points over 28 patients is 8.5357 -> `8.54`,
        which is `consistent`. `8.58` is the number the notice withdraws, and it
        was adjudicated `impossible` beside its own replacement."""
        notice = F_NOTICES[key]
        got = checks.evaluate(_f_account(notice), f"{N_Q} {H_BOUND} {notice}\n")
        assert accusations(got) == []
        assert refusals(got)["chk:grim:val:old"] == "value_withdrawn_by_a_correction"
        # THE COST SIDE, AND IT IS THE THIRD CONDITION OF THE GUARD: the
        # replacement is still checked.
        assert "chk:grim:val:new" in ran(got)

    def test_a_number_outside_a_notice_is_untouched(self):
        assert premises.withdrawn_by_a_correction(
            {"printed": "8.58", "quote": "The mean adherence score was 8.58."}) is None


# --------------------------------------------------------------------------
# P -- THE UNIT RECORDED ON ONE SIDE ONLY
# --------------------------------------------------------------------------

P_GRAN = ("Review time was recorded in whole minutes from the dispensing "
          "system log.")
P_TEXT = f"{N_Q} {P_GRAN} Total review time is reported in hours.\n"


def _p_account(variable_units, value_units):
    return account(
        variables=[var("var:review_time", "Total review time", "count",
                       units=variable_units, step=1, gquote=P_GRAN)],
        values=[n_row(),
                cell("val:time_mean", "mean", TIME_H,
                     col_label="Total review time, h",
                     variable_id="var:review_time", units=value_units)])


class TestTheUnitIsReadFromWhereverThePaperPrintsIt:
    @pytest.mark.parametrize("variable_units,value_units", [
        ("minutes", "h"), ("minutes", None), (None, "h"), (None, None)])
    def test_whole_minutes_printed_as_hours_are_not_convicted(
            self, variable_units, value_units):
        """11,369 whole minutes over 28 patients is 406.04 min = 6.7673 h ->
        `6.77`. The schema tells a reading to record `units` "as printed", so a
        table whose unit is printed once over the column truthfully leaves the
        cell's own `units` null -- and the guard needed it recorded twice."""
        got = checks.evaluate(_p_account(variable_units, value_units), P_TEXT)
        assert accusations(got) == []
        assert refusals(got)["chk:grim:val:time_mean"] == "printed_in_another_unit"

    def test_the_recorded_unit_still_reaches_a_verdict(self):
        """THE COST SIDE. The same audit read in MINUTES -- the unit its own
        granularity sentence is about -- runs and clears."""
        text = f"{N_Q} {P_GRAN}\n"
        acc = account(
            variables=[var("var:review_time", "Total review time", "count",
                           units="minutes", step=1, gquote=P_GRAN)],
            values=[n_row(),
                    cell("val:time_mean", "mean", f"{REVIEW_MIN / N:.2f}",
                         col_label="Total review time, min",
                         variable_id="var:review_time", units="minutes")])
        got = checks.evaluate(acc, text)
        assert "chk:grim:val:time_mean" in ran(got)
        assert accusations(got) == []

    def test_a_band_that_names_no_unit_says_nothing_either_way(self):
        """AN UNRECOGNISED TOKEN IS AN ABSENCE, NOT A MISMATCH -- otherwise
        `Mean (SD)` would make `sd` a unit and manufacture a mismatch against a
        real one, and `n (%)` would do it on every clinical table."""
        assert premises.printed_unit(
            {"location": {"col_label": "Mean (SD)"}}) == (None, "")
        assert premises.printed_unit(
            {"location": {"col_label": "n (%)"}}) == (None, "")
        assert premises.printed_unit(
            {"location": {"col_label": "Age, y"}})[0] == "year"
        assert premises.recorded_unit(
            {"granularity": {"quote": P_GRAN}})[0] == "minute"
        assert premises.recorded_unit(
            {"granularity": {"quote": MEDS_G}})[0] is None


# --------------------------------------------------------------------------
# I -- A NUMBER THIS PAPER QUOTES FROM ANOTHER PAPER
# --------------------------------------------------------------------------

I_SENTENCES = {
    "prior_n_printed": ("Our patients took a mean of 5.39 medicines, more than "
                        "the 4.70 reported by Chen and colleagues in 96 "
                        "patients."),
    "prior_n_absent": ("Our patients took a mean of 5.39 medicines, more than "
                       "the 4.70 reported by Chen and colleagues."),
    "et_al": ("Our patients took a mean of 5.39 medicines, more than the 4.70 "
              "of Chen et al. (2021)."),
}


def _i_account(sentence):
    return account(
        variables=[meds_var()],
        values=[n_row(),
                prose("val:ours", "mean", "5.39", sentence,
                      variable_id="var:medicines", offset=120),
                prose("val:chen", "mean", "4.70", sentence,
                      variable_id="var:medicines", offset=121)])


class TestANumberQuotedFromAnotherPaper:
    @pytest.mark.parametrize("key", sorted(I_SENTENCES))
    def test_the_other_papers_number_is_not_adjudicated_at_our_n(self, key):
        """151 medicines over 28 patients is 5.3929 -> `5.39`, ours and
        `consistent`. 4.70 is Chen's, and 4.70 x 28 = 131.6."""
        sentence = I_SENTENCES[key]
        got = checks.evaluate(_i_account(sentence), f"{N_Q} {sentence}\n")
        assert accusations(got) == []
        assert "chk:grim:val:chen" not in ran(got)

    def test_our_own_number_in_the_same_sentence_still_runs(self):
        """THE COST SIDE, and it is why the phrase has to follow THIS number:
        refusing every value in a sentence that cites somebody would take our
        number with theirs."""
        sentence = I_SENTENCES["prior_n_absent"]
        got = checks.evaluate(_i_account(sentence), f"{N_Q} {sentence}\n")
        assert "chk:grim:val:ours" in ran(got)
        assert premises.attributed_to_another_study(
            {"printed": "5.39", "quote": sentence}) is None
        assert premises.attributed_to_another_study(
            {"printed": "4.70", "quote": sentence})


# --------------------------------------------------------------------------
# N3 -- A PERCENTAGE THAT ROUNDS TO ZERO
# --------------------------------------------------------------------------

class TestAPercentageThatRoundsToZeroPinsNoBase:
    def test_an_unbounded_base_is_not_the_same_as_no_base(self):
        """`1 (0.0)` -- one event among the 4,000 patients on the register,
        printed at a coordinate carrying the 28 audited. The window's lower edge
        is below zero, so every denominator from 1,000 upward reproduces the
        pair; returning [] for that said the opposite to the one caller there
        is, which reads an empty list as `no reading of the base rescues the
        arithmetic` and RUNS the check."""
        acc = account(
            variables=[var("var:sae", "Serious adverse event",
                           "percentage_of_subjects")],
            values=[n_row(),
                    cell("val:sae_n", "count", "1", row=4, col_label="n (%)",
                         variable_id="var:sae"),
                    cell("val:sae_pct", "percentage", "0.0", row=4,
                         col_label="n (%)", variable_id="var:sae")])
        text = (f"{N_Q} One serious adverse event was recorded among the 4000 "
                "patients on the practice register.\n")
        got = checks.evaluate(acc, text)
        assert accusations(got) == []
        assert refusals(got)["chk:count_percent:val:sae_pct"] == \
            "another_denominator_fits"

    def test_an_arithmetic_disagreement_no_base_explains_still_runs(self):
        """THE COST SIDE, and it is the case the family exists for: where the
        interval holds no integer the paper could have used, the disagreement is
        about the arithmetic and the check runs."""
        assert premises.other_bases_that_fit(142, 73.0, 1, 200, 200) == []
        assert premises.other_bases_that_fit(26, 0.867, 3, 30, 30) == []
        assert premises.other_bases_that_fit(1, 0.0, 1, 28, 4000)[:1] == [1000]


# --------------------------------------------------------------------------
# Z -- THE SHAPES THAT TOOK THE WHOLE SIDECAR
# --------------------------------------------------------------------------

def _z_values():
    return [n_row(),
            cell("val:mean", "mean", "5.39", col_label="Mean (SD)",
                 variable_id="var:medicines")]


class TestTheVariableTableCannotTakeTheSidecar:
    @pytest.mark.parametrize("bad_id", [["var:medicines"], {"id": "var:medicines"},
                                        None, ""])
    def test_a_variable_id_that_cannot_be_a_key_is_one_skip(self, bad_id):
        """Round 3 fixed this class for values -- a list or a dict raised
        `TypeError: unhashable type` out of the index, BEFORE the per-candidate
        try/except, so no `checks.json` and no docket were written at all -- and
        the variable table was never given the same treatment."""
        v = meds_var()
        v["id"] = bad_id
        got = checks.evaluate(account(variables=[v], values=_z_values()), N_Q)
        assert accusations(got) == []
        assert refusals(got)["chk:grim:val:mean"] == "no_variable"

    @pytest.mark.parametrize("document", [
        [{"id": "table:1", "caption": "Table 1."}],
        {"tables": {"table:1": "Table 1."}},
        "Table 1.",
        None,
    ])
    def test_a_document_that_is_not_an_object_is_a_paper_with_no_captions(
            self, document):
        acc = account(variables=[meds_var()], values=_z_values())
        acc["document"] = document
        got = checks.evaluate(acc, N_Q)
        assert accusations(got) == []
        assert got["n_run"] + got["n_refused"] == got["n_candidates"]

    @pytest.mark.parametrize("variables", [
        {"var:medicines": {"id": "var:medicines"}},
        ["var:medicines"],
        None,
    ])
    def test_a_variable_table_that_is_not_a_list_of_objects_is_no_variables(
            self, variables):
        acc = account(variables=[meds_var()], values=_z_values())
        acc["variables"] = variables
        got = checks.evaluate(acc, N_Q)
        assert accusations(got) == []
        assert refusals(got)["chk:grim:val:mean"] == "no_variable"

    def test_the_malformed_variables_are_named_rather_than_dropped_silently(self):
        v = meds_var()
        v["id"] = ["var:medicines"]
        idx = checks._Index(account(variables=[v], values=_z_values()), N_Q)
        assert idx.malformed_variables and "index key" in \
            idx.malformed_variables[0]["why"]
        assert premises.well_formed_variable({"id": "var:x"}) is None

    # ROUND 12 -- `id` WAS THE ONLY FIELD THIS GATE ASKED ABOUT, AND IT IS NOT
    # THE ONLY ONE READ OUTSIDE THE ISOLATION. `printed_as` is ITERATED by
    # `premises._name_forms`, reached from `anchor_score` ->
    # `about_this_variable` -> `bounds_verification` -> `premises.stamp`, which
    # is the FIRST statement of `checks.evaluate`. A scalar there raised
    # `TypeError: 'int' object is not iterable` and the paper got no
    # `checks.json`, no `checks.md` and no docket at all.
    @pytest.mark.parametrize("bad", [5, True, 0.5, "Prescribed medicines",
                                     {"a": 1}])
    def test_a_printed_as_that_is_not_a_list_is_one_skip(self, bad):
        v = meds_var()
        v["printed_as"] = bad
        got = checks.evaluate(account(variables=[v], values=_z_values()), N_Q)
        assert accusations(got) == []
        assert refusals(got)["chk:grim:val:mean"] == "no_variable"
        assert got["n_run"] + got["n_refused"] == got["n_candidates"]

    @pytest.mark.parametrize("bad", [5, True, "Prescribed medicines", {"a": 1}])
    def test_the_bad_printed_as_is_named_rather_than_dropped_silently(self, bad):
        v = meds_var()
        v["printed_as"] = bad
        idx = checks._Index(account(variables=[v], values=_z_values()), N_Q)
        assert idx.malformed_variables
        assert "printed_as" in idx.malformed_variables[0]["why"]

    @pytest.mark.parametrize("good", [[], ["PSQI"], None])
    def test_a_printed_as_the_schema_allows_still_reaches_the_variable(self, good):
        """The gate may only ever REMOVE a variable that cannot be read. An
        absent `printed_as` is the commonest honest shape and must not refuse."""
        v = meds_var()
        v["printed_as"] = good
        assert premises.well_formed_variable(v) is None
        got = checks.evaluate(account(variables=[v], values=_z_values()), N_Q)
        assert accusations(got) == []
        assert "chk:grim:val:mean" in ran(got)

    def test_a_bare_string_is_one_label_and_never_one_label_per_letter(self):
        """THE HALF OF THIS DEFECT THAT DOES NOT CRASH. `list("Age")` raises
        nothing at all -- it yields `['A', 'g', 'e']`, one printed label per
        LETTER, which is silently wrong rather than loud, and a one-character
        label is a label that can join to a one-character row banner."""
        assert premises.printed_labels({"printed_as": "Age"}) == ["Age"]
        forms = premises._name_forms({"name": "Prescribed medicines",
                                      "printed_as": "Age"})
        assert ["age"] in forms
        assert not any(len(f) == 1 and len(f[0]) == 1 for f in forms)

    @pytest.mark.parametrize("bad, want", [
        (5, ["5"]), (True, ["true"]), ({"a": 1}, []), (None, []), ("", []),
        (0, []), ([], []), (["PSQI"], ["psqi"])])
    def test_printed_labels_coerces_a_scalar_and_reads_nothing_else(self, bad, want):
        """A scalar in a field the schema declares as an array of strings is one
        label written without its wrapper; a dict is not a list of labels in any
        reading. Neither may raise: this is the guard for every caller that did
        not come through `readable_variables`."""
        got = premises._name_forms({"name": None, "printed_as": bad})
        assert [w for form in got for w in form] == want


# --------------------------------------------------------------------------
# Y -- THE FAMILY WIRED WITH NO CEILING
# --------------------------------------------------------------------------

class TestGrimmerHasACeilingToo:
    def test_a_huge_n_refuses_by_name_rather_than_stalling_the_run(self):
        """MEASURED: `grimmer_check` costs 0.81 s at n = 100,000, 3.2 s at
        200,000, and does not return within 20 s at 1,000,000 -- and the
        per-candidate try/except catches exceptions, not seconds. The working
        corpus contains a 315,661-patient paper."""
        n = checks.GRIMMER_MAX_N * 2
        q = f"The cohort comprised {n} patients (n = {n}). {MEDS_B}"
        acc = account(
            variables=[meds_var(bsource="stated", lower=0, upper=25,
                                bquote=MEDS_B)],
            studies=one_group(n),
            values=[n_row(str(n), q),
                    cell("val:m", "mean", "5.39", col_label="Mean (SD)",
                         variable_id="var:medicines"),
                    cell("val:s", "sd", "1.83", col_label="Mean (SD)",
                         variable_id="var:medicines")])
        got = checks.evaluate(acc, q + "\n")
        assert refusals(got)["chk:grimmer:val:m"] == "n_too_large_for_grimmer"
        assert refusals(got)["chk:sprite:val:m"] == "n_too_large_for_sprite"
        # GRIM is arithmetic rather than a search and needs no ceiling: it costs
        # 0.00 s at n = 10,000,000.
        assert "chk:grim:val:m" in ran(got)
        assert accusations(got) == []

    def test_an_ordinary_n_is_untouched(self):
        assert checks.GRIMMER_MAX_N >= 100_000


# --------------------------------------------------------------------------
# THE COST SIDE, WHOLE
# --------------------------------------------------------------------------

K_TEXT = (f"{N_Q} {MEDS_B} Seven patients (25.0%) were taking ten or more "
          "medicines.\n")


class TestTheFullyRecordedTableStillReachesVerdicts:
    def test_five_checks_run_and_every_one_of_them_clears(self):
        """A bridge that refused everything would pass every attack in this file
        and be worthless. One ordinary table of the same audit, recorded the way
        the schema asks: the unit on both sides, one id per variable, the n at
        the group, the wave in the vocabulary, no correction notice."""
        acc = account(
            variables=[meds_var(bsource="stated", lower=0, upper=25,
                                bquote=MEDS_B),
                       var("var:polypharmacy", "Ten or more medicines",
                           "percentage_of_subjects")],
            values=[n_row(),
                    cell("val:mean", "mean", MEDS_MEAN, col_label="Mean (SD)",
                         variable_id="var:medicines"),
                    cell("val:sd", "sd", MEDS_SD, col_label="Mean (SD)",
                         variable_id="var:medicines"),
                    cell("val:poly_n", "count", "7", row=2, col_label="n (%)",
                         variable_id="var:polypharmacy"),
                    cell("val:poly_pct", "percentage", "25.0", row=2,
                         col_label="n (%)", variable_id="var:polypharmacy")])
        got = checks.evaluate(acc, K_TEXT)
        assert got["n_run"] == 5 and got["n_refused"] == 0
        assert accusations(got) == []
        assert {r["severity"] for r in got["checks"]} == {"consistent"}

    def test_every_reason_this_round_adds_is_in_the_closed_vocabulary(self):
        for code in ("duplicate_variable_id", "n_too_large_for_grimmer",
                     "value_attributed_to_another_study",
                     "derivation_reports_an_average",
                     "bound_stated_for_the_source_quantity"):
            assert code in checks.REASONS, code
