"""The six defects a sixth adversarial pass found in the checks bridge, pinned.

THE PAPER IS NEW AND SO ARE THE SURFACES. "The Ashgrove night-shift sleep audit"
-- a two-wave occupational sleep audit of 28 hospital nurses -- shares nothing
with the Delta trial of `test_scaffold_checks_adversarial.py`, the Harborview
study of `test_scaffold_checks_round3.py`, the Ashcombe trial of
`test_scaffold_checks_round4.py` or the Kelmscott survey of
`test_scaffold_checks_round5.py`, and the attacks are aimed at premises none of
those rounds touched: WHICH UNIT a number is printed in, WHICH STAGE a
denominator belongs to, WHAT a table's printed name is, WHAT the paper's own
percentage base is, WHAT the analysis unit is, and whether the paper has
WITHDRAWN the number at all.

Every number below is recomputed IN THIS FILE from a real 28-nurse integer
dataset, so "the paper printed nothing wrong" is a fact rather than an
assertion, and any verdict worse than `consistent` or `indeterminate` is a false
accusation by construction.

The six it found, and where each is fixed:

  U   UNITS ARE NEVER READ. `variable.units` and `value.units` are both in the
      schema, both filled truthfully, and neither was read anywhere in
      `premises` or `checks` -- so a quantity RECORDED in whole units and
      REPORTED in a coarser one (11,369 whole minutes over 28 nurses printed as
      `6.77` h; 1,939,200 whole grams printed as `69.26` kg) returned GRIM,
      GRIMMER and SPRITE `impossible`, while the identical account in the
      recorded unit is `consistent` (`premises.units_of`,
      `printed_in_another_unit`)
  P   THE PHASE GUARD WAS ONE-SIDED. `phase_n_over_several_phases` fired only for
      a value AT a phase, so a value bound to NO phase inherited the phase-less
      enrolled n even where the account's own rows state an n per wave -- the
      guard protected the value that was honest at that n and let through the one
      that was not
  P2  AND IT FAILED OPEN ON THE LESS COMPLETE ACCOUNT. Where the paper states the
      follow-up number in prose the reading made no n row of (`Twenty-four nurses
      attended the twelve-week visit`, no `n =` notation to key on), the account
      held one n and the follow-up mean was adjudicated against it. The served
      text is now read for the fourth document-level statement it was never read
      for -- how many units were analysed here -- and joined to the value's own
      sentence by the STAGE both name (`premises.analysed_counts`,
      `premises.stage_phrases`)
  S   `premises._TABLE_LABEL` COULD NOT JOIN A SUPPLEMENT LABEL. `Table S1`,
      `eTable 2`, `Table A1`, `Supplementary Table 3` and `Appendix Table 1` all
      returned None, so the paper's own prose could not withdraw a supplement's
      regression table -- and a supplement is exactly where a clinical paper puts
      one (CLAUDE.md 8p). Fifteen false accusations from a regex
  D   `paper_max_n` UNDER-READ THE PAPER'S OWN PERCENTAGE BASE, by two routes: a
      cohort size spelled out above ninety-nine (`read_spelled` was bounded at
      99) and one printed only in a table and typed `count` rather than `n`.
      A base the ceiling excludes is not a base named -- it is a check that RUNS
      and accuses (`premises.spelled_value`, `premises.CEILING_STATISTICS`)
  K   THE n COUNTS SUBJECTS AND THE MEAN AVERAGES OBSERVATIONS whenever the
      observation count is stated in a sentence other than the value's own
      (`premises.analysis_unit_statement`)
  E   A VALUE QUOTED INSIDE THE PAPER'S OWN CORRECTION NOTICE was
      indistinguishable from a reported one, so the superseded number was
      adjudicated beside the corrected one that replaced it
      (`premises.withdrawn_by_a_correction`)

THE COST SIDE IS ASSERTED THROUGHOUT, because a guard that bought its safety by
refusing everything would pass every attack here and be worthless: the audit read
in its own recorded units must keep reaching a verdict in every family, a
supplement table with no prose note about it stays checkable, the corrected value
beside a withdrawn one still runs, and the baseline mean of a study that reports
dropout at a LATER stage is untouched.
"""

from __future__ import annotations

import statistics as st

import pytest

from forensic_metascience_ai_toolkit.scaffold import checks, premises

BAD = {"suspicious", "highly_suspicious", "impossible"}

# --------------------------------------------------------------------------
# The Ashgrove audit's real per-nurse data
# --------------------------------------------------------------------------

#: Total sleep on the study night, RECORDED IN WHOLE MINUTES (28 nurses).
SLEEP_MIN = [412, 355, 468, 401, 390, 425, 333, 456, 402, 380,
             441, 398, 367, 420, 455, 372, 409, 434, 388, 461,
             350, 418, 397, 443, 376, 429, 405, 384]

#: Pittsburgh Sleep Quality Index global score, 0-21 in whole points, wave 1.
PSQI_W1 = [9, 12, 5, 8, 11, 6, 14, 4, 9, 10,
           7, 8, 13, 6, 5, 11, 9, 7, 10, 4,
           12, 8, 9, 6, 11, 7, 8, 10]

#: The 24 nurses re-assessed twelve weeks later.
PSQI_W2 = [6, 9, 4, 7, 9, 5, 12, 4, 8, 8,
           6, 7, 11, 5, 4, 9, 8, 6, 9, 3,
           10, 7, 8, 5]

#: Night-time awakenings, whole events, per nurse on one night.
AWAK = [3, 5, 1, 2, 4, 2, 6, 1, 3, 4,
        2, 3, 5, 2, 1, 4, 3, 2, 4, 1,
        5, 3, 3, 2, 4, 2, 3, 4]

#: The same audit run over three nights each: 84 nurse-nights, 257 awakenings.
AWAK_NIGHTS = 84
AWAK_TOTAL = 257

#: Body mass, RECORDED IN WHOLE GRAMS.
MASS_G = [68400, 72150, 59800, 81300, 64950, 77200, 55600, 70050,
          66300, 74800, 61200, 83900, 58450, 69700, 75300, 62800,
          71600, 65100, 79400, 57900, 73250, 67450, 60700, 76800,
          63350, 80200, 68950, 72600]

N = len(SLEEP_MIN)
SLEEP_MEAN_MIN = f"{st.fmean(SLEEP_MIN):.2f}"          # 406.04 minutes
SLEEP_SD_MIN = f"{st.stdev(SLEEP_MIN):.2f}"            # 34.96 minutes
SLEEP_MEAN_H = f"{st.fmean(SLEEP_MIN) / 60:.2f}"       # 6.77 hours
SLEEP_SD_H = f"{st.stdev(SLEEP_MIN) / 60:.2f}"         # 0.58 hours
MASS_MEAN_KG = f"{st.fmean(MASS_G) / 1000:.2f}"        # 69.26 kg
MASS_SD_KG = f"{st.stdev(MASS_G) / 1000:.2f}"          # 7.69 kg
W1_MEAN = f"{st.fmean(PSQI_W1):.2f}"                   # 8.54
W1_SD = f"{st.stdev(PSQI_W1):.2f}"                     # 2.67
W2_MEAN = f"{st.fmean(PSQI_W2):.2f}"                   # 7.08
W2_SD = f"{st.stdev(PSQI_W2):.2f}"                     # 2.36
AWAK_MEAN = f"{AWAK_TOTAL / AWAK_NIGHTS:.2f}"          # 3.06 per nurse-night


def test_the_fixture_paper_is_honest():
    """Every printed number is the exact summary of real whole-unit data, in the
    unit its own sentence names. Anything worse than `consistent` below is a
    false accusation as a matter of arithmetic, not of judgement."""
    assert (SLEEP_MEAN_MIN, SLEEP_MEAN_H) == ("406.04", "6.77")
    assert (MASS_MEAN_KG, W1_MEAN, W2_MEAN) == ("69.26", "8.54", "7.08")
    assert sum(SLEEP_MIN) == 11369 and all(float(x).is_integer() for x in SLEEP_MIN)
    assert st.fmean(PSQI_W2) * len(PSQI_W2) == sum(PSQI_W2) == 170
    # 3.06 is exactly 257/84 and is unreachable over 28 whole counts: 85/28 =
    # 3.036 and 86/28 = 3.071, which is what makes the wrong denominator
    # `impossible` rather than merely wrong.
    assert AWAK_MEAN == "3.06"
    assert not any(round(k / N, 2) == 3.06 for k in range(N * 10))


# --------------------------------------------------------------------------
# The account shapes
# --------------------------------------------------------------------------

PSQI_B = ("The Pittsburgh Sleep Quality Index global score runs from 0 to 21 "
          "and each nurse contributed one whole-point score.")
N_Q = "Twenty-eight nurses working the night rotation were enrolled (n = 28)."


def var(vid, name, kind, *, bsource="not_stated", lower=None, upper=None,
        bquote=None, step=None, gquote=None, units=None, printed_as=()):
    return {"id": vid, "name": name, "label": name,
            "printed_as": list(printed_as), "kind": kind, "role": None,
            "units": units, "units_source": "stated" if units else "not_stated",
            "bounds": {"source": bsource, "lower": lower, "upper": upper,
                       "quote": bquote},
            "granularity": {"per_subject_step": step, "quote": gquote}}


def psqi_var():
    return var("var:psqi", "Pittsburgh Sleep Quality Index global score",
               "integer_score", printed_as=["PSQI", "index score"],
               bsource="stated", lower=0, upper=21, bquote=PSQI_B,
               step=1, gquote=PSQI_B)


def _lit(printed):
    return premises.read_plain(printed) or {}


def cell(vid, statistic, printed, *, table="table:1", row=1, col=1,
         col_label=None, variable_id=None, group="grp:all", phase=None,
         units=None):
    lit = _lit(printed)
    return {"id": vid, "statistic": statistic, "printed": printed,
            "numeric": lit.get("value"), "decimals": lit.get("decimals", 0),
            "printed_form": "percent" if lit.get("is_percent") else "plain",
            "units": units, "variable_id": variable_id, "id_check": "agrees",
            "statistic_disputed": False, "source": "table", "quote": None,
            "quote_verified": "cell", "printed_in_quote": None,
            "location": {"kind": "table_cell", "table_id": table, "row": row,
                         "col": col, "col_label": col_label},
            "coordinate": {"study_id": "study:main", "group_id": group,
                           "phase_id": phase}}


def prose(vid, statistic, printed, quote, *, variable_id=None, group="grp:all",
          phase=None, id_check="agrees", units=None):
    lit = _lit(printed)
    return {"id": vid, "statistic": statistic, "printed": printed,
            "numeric": lit.get("value"), "decimals": lit.get("decimals", 0),
            "printed_form": "percent" if lit.get("is_percent") else "plain",
            "units": units, "variable_id": variable_id, "id_check": id_check,
            "statistic_disputed": False, "source": "prose", "quote": quote,
            "quote_verified": "verbatim", "printed_in_quote": True,
            "location": {"kind": "prose", "offset": 0, "col_label": None},
            "coordinate": {"study_id": "study:main", "group_id": group,
                           "phase_id": phase}}


def n_row(printed="28", quote=N_Q, *, phase=None, vid="val:n", group="grp:all"):
    return prose(vid, "n", printed, quote, id_check=None, phase=phase,
                 group=group)


def account(*, variables=None, values=None, tables=None, groups=None):
    return {
        "paper": {"doi": "10.0000/ashgrove",
                  "title": "The Ashgrove night-shift sleep audit"},
        "studies": [{"id": "study:main", "design": "prospective_cohort",
                     "groups": groups if groups is not None else
                     [{"id": "grp:all", "label": "All nurses", "n": 28,
                       "n_source": "text"}]}],
        "variables": variables or [], "values": values or [],
        "document": {"tables": tables or [
            {"id": "table:1", "caption": "Table 1. Sleep characteristics of the "
                                         "audited nurses."}]},
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
# U -- A WHOLE-UNIT VARIABLE REPORTED IN A COARSER UNIT
# --------------------------------------------------------------------------

SLEEP_G = ("Total sleep time on the study night was counted in whole minutes "
           "from the actigraph record.")
MASS_GQ = ("Body mass was recorded as a whole number of grams on a calibrated "
           "platform scale.")
U_TEXT = ("# The Ashgrove night-shift sleep audit\n\n## Methods\n\n"
          + N_Q + "\n" + SLEEP_G + "\n" + MASS_GQ + "\n\n## Results\n\n"
          + f"Nurses slept for a mean of {SLEEP_MEAN_H} h (SD {SLEEP_SD_H}) on "
            "the study night.\n"
          + f"Mean body mass was {MASS_MEAN_KG} kg (SD {MASS_SD_KG}).\n")

SLEEP_H_S = (f"Nurses slept for a mean of {SLEEP_MEAN_H} h (SD {SLEEP_SD_H}) on "
             "the study night.")
MASS_S = f"Mean body mass was {MASS_MEAN_KG} kg (SD {MASS_SD_KG})."


def _unit_account(value_units, variable_units):
    """The same audit, twice: the variable's unit is the one it was RECORDED in,
    and `value_units` is the one the paper PRINTED."""
    return account(
        variables=[var("var:sleep", "total sleep time", "integer_score",
                       units=variable_units, step=1, gquote=SLEEP_G)],
        values=[n_row(),
                prose("val:mean", "mean", SLEEP_MEAN_H, SLEEP_H_S,
                      variable_id="var:sleep", units=value_units),
                prose("val:sd", "sd", SLEEP_SD_H, SLEEP_H_S,
                      variable_id="var:sleep", units=value_units)])


class TestAStepIsAStepInTHATUnit:
    def test_whole_minutes_printed_as_hours_are_not_convicted(self):
        """11,369 whole minutes over 28 nurses is 406.0357 min = 6.7673 h ->
        `6.77`, and `6.77 * 28` is not an integer number of hours because the
        integers are minutes."""
        got = checks.evaluate(_unit_account("h", "minutes"), U_TEXT)
        assert accusations(got) == []
        assert refusals(got)["chk:grim:val:mean"] == "printed_in_another_unit"
        for family in ("grimmer", "sprite"):
            assert refusals(got)[f"chk:{family}:val:mean"] == "printed_in_another_unit"

    def test_whole_grams_printed_as_kilograms_are_not_convicted(self):
        acc = account(
            variables=[var("var:mass", "body mass", "integer_score",
                           units="grams", step=1, gquote=MASS_GQ)],
            values=[n_row(),
                    prose("val:mean", "mean", MASS_MEAN_KG, MASS_S,
                          variable_id="var:mass", units="kg")])
        got = checks.evaluate(acc, U_TEXT, ("grim",))
        assert accusations(got) == []
        assert refusals(got)["chk:grim:val:mean"] == "printed_in_another_unit"

    def test_the_same_account_in_the_recorded_unit_still_runs(self):
        """THE COST SIDE. The audit read in minutes -- the unit its own
        granularity sentence is about -- reaches a verdict and clears it."""
        text = ("# The Ashgrove night-shift sleep audit\n\n## Methods\n\n"
                + N_Q + "\n" + SLEEP_G + "\n\n## Results\n\n"
                + f"Nurses slept for a mean of {SLEEP_MEAN_MIN} minutes "
                  f"(SD {SLEEP_SD_MIN}) on the study night.\n")
        s = (f"Nurses slept for a mean of {SLEEP_MEAN_MIN} minutes "
             f"(SD {SLEEP_SD_MIN}) on the study night.")
        acc = account(
            variables=[var("var:sleep", "total sleep time", "integer_score",
                           units="minutes", step=1, gquote=SLEEP_G)],
            values=[n_row(),
                    prose("val:mean", "mean", SLEEP_MEAN_MIN, s,
                          variable_id="var:sleep", units="minutes"),
                    prose("val:sd", "sd", SLEEP_SD_MIN, s,
                          variable_id="var:sleep", units="minutes")])
        got = checks.evaluate(acc, text, ("grim",))
        assert "chk:grim:val:mean" in ran(got)
        assert accusations(got) == []

    @pytest.mark.parametrize("value_units,variable_units", [
        ("min", "minutes"), ("minutes", "min"), ("h", "hours"), ("kg", "kilograms"),
        ("Minutes", "minute"), ("minutes", None), (None, "minutes"), (None, None),
    ])
    def test_one_unit_spelled_two_ways_costs_nothing(self, value_units,
                                                     variable_units):
        """A SYNONYM IS NOT A MISMATCH, and an absence is not one either. The map
        exists so that the guard fires on `hours` against `minutes` and never on
        `min` against `minutes`."""
        got = checks.evaluate(_unit_account(value_units, variable_units), U_TEXT,
                              ("grim",))
        assert "printed_in_another_unit" not in every_reason(got)

    def test_the_premise_is_stamped_on_every_value_either_way(self):
        stamped = premises.stamp(_unit_account("h", "minutes"), U_TEXT)
        units = {v["id"]: v["premise"]["units"] for v in stamped["values"]}
        assert units["val:mean"]["agree"] is False
        assert units["val:mean"]["value_unit_normalised"] == "hour"
        assert units["val:mean"]["variable_unit_normalised"] == "minute"
        assert units["val:n"]["agree"] is None


# --------------------------------------------------------------------------
# P -- A VALUE AT NO PHASE, IN A STUDY WHOSE n THE PAPER STATES PER WAVE
# --------------------------------------------------------------------------

W1_S = (f"At wave 1 the mean Pittsburgh Sleep Quality Index global score was "
        f"{W1_MEAN} (SD {W1_SD}).")
FU_S = f"At follow-up the mean index score was {W2_MEAN} (SD {W2_SD})."
W2_N_S = "Twenty-four nurses were re-assessed twelve weeks later (n = 24)."
P_TEXT = ("# The Ashgrove night-shift sleep audit\n\n## Methods\n\n"
          + N_Q + "\n" + PSQI_B + "\n" + W2_N_S + "\n\n## Results\n\n"
          + W1_S + "\n" + FU_S + "\n")


class TestThePhaseGuardIsTwoSided:
    def test_a_value_at_no_phase_does_not_inherit_the_phase_less_n(self):
        """`7.08` is 170/24 exactly -- the wave-2 mean of the 24 nurses
        re-assessed -- and the sentence it sits in names no wave the reading
        could bind to. At the enrolled 28 it was GRIM, GRIMMER and SPRITE
        `impossible`, while the wave-1 mean BESIDE IT, honest at 28, was
        correctly refused by the one-sided guard: the guard protected the right
        value and let the wrong one through."""
        acc = account(variables=[psqi_var()],
                      values=[n_row(vid="val:n:enrolled"),
                              n_row("24", W2_N_S, phase="phase:w2", vid="val:n:w2"),
                              prose("val:w1:mean", "mean", W1_MEAN, W1_S,
                                    variable_id="var:psqi", phase="phase:w1"),
                              prose("val:fu:mean", "mean", W2_MEAN, FU_S,
                                    variable_id="var:psqi"),
                              prose("val:fu:sd", "sd", W2_SD, FU_S,
                                    variable_id="var:psqi")])
        got = checks.evaluate(acc, P_TEXT)
        assert accusations(got) == []
        assert refusals(got)["chk:grim:val:fu:mean"] == "phase_n_over_several_phases"
        assert refusals(got)["chk:grim:val:w1:mean"] == "phase_n_over_several_phases"

    def test_the_docket_says_the_value_carried_no_phase(self):
        """A refusal a reader cannot act on is half a refusal: the record has to
        distinguish `this wave has no n` from `this value names no wave`."""
        acc = account(variables=[psqi_var()],
                      values=[n_row(vid="val:n:enrolled"),
                              n_row("24", W2_N_S, phase="phase:w2", vid="val:n:w2"),
                              prose("val:fu:mean", "mean", W2_MEAN, FU_S,
                                    variable_id="var:psqi")])
        got = checks.evaluate(acc, P_TEXT, ("grim",))
        row = [r for r in got["refused"] if r["check_id"] == "chk:grim:val:fu:mean"][0]
        detail = row["reasons"][0]["detail"]
        assert "phase:w2" in detail
        assert "names no phase at all" in detail

    def test_a_phase_less_account_with_no_per_wave_n_is_untouched(self):
        """THE COST SIDE. Where no n carries a phase, nothing says the
        denominator varies and a phase-less value keeps its check."""
        text = ("# The Ashgrove night-shift sleep audit\n\n## Methods\n\n"
                + N_Q + "\n" + PSQI_B + "\n\n## Results\n\n" + W1_S + "\n")
        acc = account(variables=[psqi_var()],
                      values=[n_row(),
                              prose("val:w1:mean", "mean", W1_MEAN, W1_S,
                                    variable_id="var:psqi"),
                              prose("val:w1:sd", "sd", W1_SD, W1_S,
                                    variable_id="var:psqi")])
        got = checks.evaluate(acc, text)
        assert accusations(got) == []
        assert {"chk:grim:val:w1:mean", "chk:grimmer:val:w1:mean"} <= ran(got)


# --------------------------------------------------------------------------
# P2 -- THE PAPER STATES THE FOLLOW-UP NUMBER AND THE READING RECORDED NO n ROW
# --------------------------------------------------------------------------

FU_VISIT_S = f"At the twelve-week visit the mean index score was {W2_MEAN} (SD {W2_SD})."
ATTENDED_S = "Twenty-four nurses attended the twelve-week visit."
P2_TEXT = ("# The Ashgrove night-shift sleep audit\n\n## Methods\n\n"
           + N_Q + "\n" + PSQI_B + "\n" + ATTENDED_S + "\n\n## Results\n\n"
           + FU_VISIT_S + "\n")


def _p2_account(extra=None):
    values = [n_row(), prose("val:m", "mean", W2_MEAN, FU_VISIT_S,
                             variable_id="var:psqi", phase="phase:w2"),
              prose("val:s", "sd", W2_SD, FU_VISIT_S, variable_id="var:psqi",
                    phase="phase:w2")]
    if extra is not None:
        values.insert(1, extra)
    return account(variables=[psqi_var()], values=values)


class TestAStageTheReadingDidNotRecord:
    def test_the_paper_s_own_sentence_withdraws_the_phase_less_n(self):
        """`Twenty-four nurses attended the twelve-week visit` carries no `n =`
        notation for the reading to key on, so the account holds exactly one n --
        the enrolled 28, at no phase -- and the twelve-week mean was adjudicated
        against it. Both controls, where the SAME sentence WAS recorded as an n
        row, already refused: the less the reading recorded, the more the bridge
        accused."""
        got = checks.evaluate(_p2_account(), P2_TEXT)
        assert accusations(got) == []
        for family in ("grim", "grimmer", "sprite"):
            assert (refusals(got)[f"chk:{family}:val:m"]
                    == "analysed_n_stated_for_another_stage")

    def test_the_docket_carries_the_paper_s_own_sentence(self):
        """Round 5's finding R, applied to a new refusal: the docket names the
        sentence the refusal rests on, and the stage it was joined by."""
        got = checks.evaluate(_p2_account(), P2_TEXT, ("grim",))
        row = [r for r in got["refused"] if r["check_id"] == "chk:grim:val:m"][0]
        detail = row["reasons"][0]["detail"]
        assert ATTENDED_S in detail
        assert "twelve week" in detail

    def test_a_retention_count_at_another_stage_costs_nothing(self):
        """THE COST SIDE, AND THE REASON THE JOIN EXISTS. Every study that
        reports dropout states a retention count somewhere; what withdraws the
        phase-less n is that the retention sentence and the value's own name THE
        SAME STAGE. A baseline mean beside `Twenty-four nurses attended the
        twelve-week visit` keeps its check."""
        base_s = f"At baseline the mean index score was {W1_MEAN} (SD {W1_SD})."
        text = ("# The Ashgrove night-shift sleep audit\n\n## Methods\n\n"
                + N_Q + "\n" + PSQI_B + "\n" + ATTENDED_S + "\n\n## Results\n\n"
                + base_s + "\n")
        acc = account(variables=[psqi_var()],
                      values=[n_row(),
                              prose("val:b", "mean", W1_MEAN, base_s,
                                    variable_id="var:psqi", phase="phase:w1"),
                              prose("val:bs", "sd", W1_SD, base_s,
                                    variable_id="var:psqi", phase="phase:w1")])
        got = checks.evaluate(acc, text)
        assert accusations(got) == []
        assert "chk:grim:val:b" in ran(got)

    def test_enrolment_is_not_a_retention_statement(self):
        """`enrolled`, `randomised` and `screened` name the total the group's n
        already is; reading them would refuse a paper for stating its own sample
        size."""
        assert premises.analysed_counts(N_Q) == []
        assert premises.analysed_counts("Forty patients were randomised.") == []
        got = premises.analysed_counts(ATTENDED_S)
        assert got and got[0]["n"] == 24 and got[0]["stages"] == ["twelve week"]

    def test_a_percentage_in_the_sentence_does_not_defeat_it(self):
        """A DECIMAL POINT IS NOT A SENTENCE BOUNDARY. The filler was `[^.;\\n]`,
        so `Twenty-nine children (85.3%) were re-interviewed` -- the commonest
        way there is of printing a retention count -- did not match at all."""
        got = premises.analysed_counts(
            "Twenty-four nurses (85.7%) attended the twelve-week visit.")
        assert got and got[0]["n"] == 24


# --------------------------------------------------------------------------
# S -- A SUPPLEMENT TABLE HAS A PRINTED NAME TOO
# --------------------------------------------------------------------------

#: 240/28 = 8.5714 and 241/28 = 8.6071, so no integer sum over 28 whole-point
#: scores rounds OR truncates to 8.58 -- which is what makes the mislabelled
#: coefficient reach `impossible` when the prose note cannot withdraw it.
COEF, COEF_SE = "8.58", "3.03"

S_LABELS = [
    ("table:4", "Table 4.", "Table 4"),
    ("table:s1", "Table S1.", "Table S1"),
    ("table:e2", "eTable 2.", "eTable 2"),
    ("table:a1", "Table A1.", "Table A1"),
    ("table:st3", "Supplementary Table 3.", "Supplementary Table 3"),
    ("table:app1", "Appendix Table 1.", "Appendix Table 1"),
]


def _supplement_account(table_id, caption, printed_name):
    sentence = (f"{printed_name} gives the multivariable model for the sleep "
                "quality index score.")
    text = ("# The Ashgrove night-shift sleep audit\n\n## Methods\n\n"
            + N_Q + "\n" + PSQI_B + "\n\n## Results\n\n" + sentence + "\n")
    acc = account(variables=[psqi_var()],
                  values=[n_row(),
                          cell("val:b", "mean", COEF, table=table_id, row=3,
                               col=2, variable_id="var:psqi"),
                          cell("val:se", "sd", COEF_SE, table=table_id, row=3,
                               col=2, variable_id="var:psqi")],
                  tables=[{"id": table_id, "caption": caption}])
    return acc, text


class TestTheNoteChannelReachesASupplement:
    @pytest.mark.parametrize("table_id,caption,printed_name", S_LABELS)
    def test_the_paper_s_prose_withdraws_the_table_whatever_it_is_called(
            self, table_id, caption, printed_name):
        """The caption is bare, the column carries no label, and the only thing
        that says these cells are a fitted model is the paper's own sentence
        about that table -- which is round 4's sharpest column of the guard
        matrix. It worked for `Table 4` and for no label a supplement uses."""
        acc, text = _supplement_account(table_id, caption, printed_name)
        got = checks.evaluate(acc, text)
        assert accusations(got) == []
        assert refusals(got)["chk:grim:val:b"] == "reports_model_output"
        assert refusals(got)["chk:sd_or_se:val:se"] == "reports_model_output"

    @pytest.mark.parametrize("table_id,caption,printed_name", S_LABELS)
    def test_the_note_is_found_for_each_printed_name(self, table_id, caption,
                                                     printed_name):
        acc, text = _supplement_account(table_id, caption, printed_name)
        notes = premises.table_notes({table_id: caption}, text)
        assert printed_name.lower() in notes[table_id].lower()

    def test_one_table_s_note_is_not_another_table_s(self):
        """THE COST SIDE, AND THE HAZARD OF A LOOSER PATTERN. A note about
        `Table S1` may not withdraw `Table 1`, and one about `Table 1` may not
        withdraw `eTable 1`: the join is built from the caption's own words."""
        text = "Table S1 gives the multivariable model for the index score."
        notes = premises.table_notes(
            {"a": "Table 1.", "b": "Table S1.", "c": "eTable 1."}, text)
        assert set(notes) == {"b"}

    def test_a_supplement_table_with_no_note_stays_checkable(self):
        """THE OTHER COST SIDE. Reading the label is not by itself a reason to
        refuse: a supplement table the paper says nothing about is a descriptive
        table until something says otherwise."""
        s = f"Table S1 reports the wave-1 characteristics of the sample."
        text = ("# The Ashgrove night-shift sleep audit\n\n## Methods\n\n"
                + N_Q + "\n" + PSQI_B + "\n\n## Results\n\n" + s + "\n")
        acc = account(variables=[psqi_var()],
                      values=[n_row(),
                              cell("val:m", "mean", W1_MEAN, table="table:s1",
                                   col_label="Mean (SD)", variable_id="var:psqi"),
                              cell("val:s", "sd", W1_SD, table="table:s1",
                                   col_label="Mean (SD)", variable_id="var:psqi")],
                      tables=[{"id": "table:s1", "caption": "Table S1."}])
        got = checks.evaluate(acc, text)
        assert accusations(got) == []
        assert {"chk:grim:val:m", "chk:grimmer:val:m"} <= ran(got)


# --------------------------------------------------------------------------
# D -- THE ALTERNATIVE-BASE CEILING IS THE PAPER'S OWN
# --------------------------------------------------------------------------

DEC_Q = "Nine of the eligible nurses (8.0%) declined for shift reasons."


def _base_account(cohort_sentence, *, cohort_value=None):
    text = ("# The Ashgrove night-shift sleep audit\n\n## Methods\n\n"
            + cohort_sentence + "\n" + N_Q + "\n\n## Results\n\n" + DEC_Q + "\n")
    values = [n_row(),
              prose("val:cnt", "count", "9", DEC_Q, variable_id="var:decline"),
              prose("val:pct", "percentage", "8.0%", DEC_Q,
                    variable_id="var:decline")]
    if cohort_value is not None:
        values.append(cohort_value)
    acc = account(
        variables=[var("var:decline", "declined for shift reasons",
                       "percentage_of_subjects"),
                   var("var:eligible", "eligible nurses", "count",
                       bsource="definitional", lower=0)],
        values=values)
    return acc, text


class TestTheCeilingIsThePapersOwnBase:
    def test_a_cohort_spelled_out_above_ninety_nine_is_read(self):
        """9/112 = 8.0357% -> `8.0%`, and the n bound at the coordinate is the
        ANALYSED 28. `read_spelled` stopped at ninety-nine, so the paper's own
        base sat above its own ceiling, `other_bases_that_fit` returned nothing,
        and `to_count_percent_kwargs` read that as `no reading of the base
        rescues the arithmetic` -- the branch the family exists to accuse on."""
        acc, text = _base_account(
            "One hundred and twelve nurses were eligible for the audit.")
        got = checks.evaluate(acc, text, ("count_percent",))
        assert accusations(got) == []
        assert refusals(got)["chk:count_percent:val:pct"] == "another_denominator_fits"

    def test_a_cohort_printed_only_in_a_table_is_read(self):
        """A flow table's `Eligible cohort | 112` is typed `count`, and the
        ceiling read `statistic: n` rows and the served text only."""
        acc, text = _base_account(
            "All eligible nurses were listed in Table 1.",
            cohort_value=cell("val:cohort", "count", "112",
                              col_label="Eligible cohort",
                              variable_id="var:eligible"))
        got = checks.evaluate(acc, text, ("count_percent",))
        assert accusations(got) == []
        assert refusals(got)["chk:count_percent:val:pct"] == "another_denominator_fits"

    def test_the_grammar_reads_the_hundreds_and_the_thousands(self):
        assert premises.read_spelled("One hundred and twelve") == 112
        assert premises.read_spelled("two thousand and four") == 2004
        assert premises.read_spelled("Thirty-four") == 34
        assert premises.read_spelled("nineteen") == 19
        assert premises.read_spelled("one hundred") == 100
        assert premises.read_spelled("a hundred") is None
        assert premises.printed_subject_counts(
            "One hundred and twelve nurses were eligible.") == [112]
        assert premises.paper_max_n(
            [{"statistic": "count", "printed": "112"}], "") == 112

    def test_a_percentage_its_own_n_reproduces_still_runs(self):
        """THE COST SIDE. A higher ceiling only ever NAMES an alternative, and an
        alternative is only ever consulted where the bound n does not reproduce
        the printed percentage. Fourteen of 28 is 50.0% and the check runs."""
        s = "Fourteen of the twenty-eight nurses (50.0%) scored 9 or more."
        text = ("# The Ashgrove night-shift sleep audit\n\n## Methods\n\n"
                + "One hundred and twelve nurses were eligible for the audit.\n"
                + N_Q + "\n\n## Results\n\n" + s + "\n")
        acc = account(
            variables=[var("var:poor", "scored 9 or more",
                           "percentage_of_subjects")],
            values=[n_row(),
                    prose("val:c", "count", "14", s, variable_id="var:poor"),
                    prose("val:p", "percentage", "50.0%", s,
                          variable_id="var:poor")])
        got = checks.evaluate(acc, text, ("count_percent",))
        assert "chk:count_percent:val:p" in ran(got)
        assert accusations(got) == []


# --------------------------------------------------------------------------
# K -- THE n COUNTS SUBJECTS AND THE MEAN AVERAGES OBSERVATIONS
# --------------------------------------------------------------------------

AWAK_G = "Night-time awakenings were tallied as whole events."
AWAK_S = f"The mean number of awakenings per night was {AWAK_MEAN}."
NIGHTS_S = (f"Each nurse was recorded on three consecutive nights, giving "
            f"{AWAK_NIGHTS} nurse-nights of actigraphy.")


def _awak_account(methods):
    text = ("# The Ashgrove night-shift sleep audit\n\n## Methods\n\n"
            + N_Q + "\n" + methods + "\n" + AWAK_G + "\n\n## Results\n\n"
            + AWAK_S + "\n")
    acc = account(
        variables=[var("var:awak", "night-time awakenings", "count", step=1,
                       gquote=AWAK_G, bsource="definitional", lower=0)],
        values=[n_row(), prose("val:m", "mean", AWAK_MEAN, AWAK_S,
                               variable_id="var:awak")])
    return acc, text


class TestTheUnitOfAnalysisIsNotAlwaysTheSubject:
    def test_an_observation_count_stated_in_methods_withdraws_the_n(self):
        """257 whole awakenings over 84 nurse-nights is 3.0595 -> `3.06`, which
        no integer sum over 28 can produce. `group_n`'s own docstring concedes it
        never asks whether an n counts the same THING, and it closed only the
        case where the VALUE'S OWN sentence says so -- moving the clause one
        sentence up into Methods defeated it."""
        acc, text = _awak_account(NIGHTS_S)
        got = checks.evaluate(acc, text, ("grim",))
        assert accusations(got) == []
        assert (refusals(got)["chk:grim:val:m"]
                == "analysis_unit_is_not_the_subject_count")

    def test_the_same_clause_in_the_value_s_own_sentence_still_refuses(self):
        """The control the existing guard already handled, kept so that the two
        readings of one paper cannot diverge."""
        s = (f"The mean number of awakenings per night was {AWAK_MEAN} across "
             f"the {AWAK_NIGHTS} nurse-nights.")
        text = ("# The Ashgrove night-shift sleep audit\n\n## Methods\n\n"
                + N_Q + "\nEach nurse was recorded on three consecutive nights.\n"
                + AWAK_G + "\n\n## Results\n\n" + s + "\n")
        acc = account(
            variables=[var("var:awak", "night-time awakenings", "count", step=1,
                           gquote=AWAK_G, bsource="definitional", lower=0)],
            values=[n_row(), prose("val:m", "mean", AWAK_MEAN, s,
                                   variable_id="var:awak")])
        got = checks.evaluate(acc, text, ("grim",))
        assert accusations(got) == []
        assert (refusals(got)["chk:grim:val:m"]
                == "denominator_contradicted_by_the_sentence")

    def test_a_yield_of_subjects_says_nothing_and_withdraws_nothing(self):
        """THE COST SIDE, AND THE NARROW PART OF THE RULE. `a total of 28 nurses`
        counts people; only a unit that is NOT a person -- a hyphenated compound,
        or one of the nouns a repeated-measures design counts observations in --
        says the analysis unit is not the subject."""
        assert premises.analysis_unit_statement(
            "A total of 28 nurses were enrolled.") is None
        assert premises.analysis_unit_statement(
            "Each nurse was recorded on three consecutive nights.") is None
        got = premises.analysis_unit_statement(NIGHTS_S)
        assert got["n"] == 84 and got["unit"] == "nurse-nights"

    def test_a_paper_with_no_such_statement_keeps_its_check(self):
        """THE COST SIDE. One night per nurse makes the nurse the unit, and the
        per-nurse mean of the same real data -- 84 whole awakenings over 28
        nurses -- is checked and clears."""
        per_nurse = f"{st.fmean(AWAK):.2f}"
        s = f"Nurses woke a mean of {per_nurse} times in the night."
        text = ("# The Ashgrove night-shift sleep audit\n\n## Methods\n\n"
                + N_Q + "\nEach nurse was recorded on one night of the rotation.\n"
                + AWAK_G + "\n\n## Results\n\n" + s + "\n")
        acc = account(
            variables=[var("var:awak", "night-time awakenings", "count", step=1,
                           gquote=AWAK_G, bsource="definitional", lower=0)],
            values=[n_row(), prose("val:m", "mean", per_nurse, s,
                                   variable_id="var:awak")])
        got = checks.evaluate(acc, text, ("grim",))
        assert "chk:grim:val:m" in ran(got)
        assert accusations(got) == []


# --------------------------------------------------------------------------
# E -- A NUMBER THE PAPER HAS ALREADY WITHDRAWN
# --------------------------------------------------------------------------

CORRECTION = ("Correction. In the originally published article the mean index "
              f"score at wave 1 was given as 8.58; the correct value is "
              f"{W1_MEAN}.")


class TestANumberThePaperHasWithdrawn:
    def test_the_superseded_value_is_not_adjudicated(self):
        """`8.58` is printed in the paper, its quote verifies verbatim, and its
        provenance is `printed_text` -- so nothing distinguished it from a
        reported number, and GRIM returned `impossible` on a paper that had
        already published a correction for that exact figure."""
        text = ("# The Ashgrove night-shift sleep audit\n\n## Methods\n\n"
                + N_Q + "\n" + PSQI_B + "\n\n## Results\n\n" + CORRECTION + "\n")
        acc = account(variables=[psqi_var()],
                      values=[n_row(),
                              prose("val:old", "mean", "8.58", CORRECTION,
                                    variable_id="var:psqi"),
                              prose("val:new", "mean", W1_MEAN, CORRECTION,
                                    variable_id="var:psqi")])
        got = checks.evaluate(acc, text, ("grim",))
        assert accusations(got) == []
        assert (refusals(got)["chk:grim:val:old"]
                == "value_withdrawn_by_a_correction")
        # THE COST SIDE, IN THE SAME SENTENCE: the corrected value is the paper's
        # claim and is checked, and it clears.
        assert "chk:grim:val:new" in ran(got)

    def test_an_erratum_that_revises_an_n_withdraws_the_old_n_only(self):
        notice = ("Corrigendum. The sample size was misstated as 28 in the "
                  "original article; twenty-six nurses were assessed (n = 26).")
        assert premises.withdrawn_by_a_correction(
            prose("v", "n", "28", notice)) is not None
        assert premises.withdrawn_by_a_correction(
            prose("v", "n", "26", notice)) is None

    def test_a_sentence_that_is_not_a_correction_withdraws_nothing(self):
        """THE COST SIDE. The rule reads the VALUE'S OWN quote and not the
        document, because a correction notice somewhere in a paper does not
        withdraw every number in it."""
        assert premises.withdrawn_by_a_correction(
            prose("v", "mean", W1_MEAN, W1_S)) is None
        assert premises.withdrawn_by_a_correction(
            prose("v", "mean", W1_MEAN,
                  "The mean was 8.54, correctly reported as 8.54.")) is None


# --------------------------------------------------------------------------
# THE CONTROL -- the audit read correctly, in the units it recorded
# --------------------------------------------------------------------------

CONTROL_TEXT = f"""# The Ashgrove night-shift sleep audit

## Methods

{N_Q}
{SLEEP_G}
{PSQI_B}
{AWAK_G}

## Results

Nurses slept for a mean of {SLEEP_MEAN_MIN} minutes (SD {SLEEP_SD_MIN}) on the study night.
The mean Pittsburgh Sleep Quality Index global score at wave 1 was {W1_MEAN} (SD {W1_SD}).
Fourteen of the twenty-eight nurses (50.0%) scored 9 or more on the index.
"""

_SLEEP_S = (f"Nurses slept for a mean of {SLEEP_MEAN_MIN} minutes "
            f"(SD {SLEEP_SD_MIN}) on the study night.")
_PSQI_S = (f"The mean Pittsburgh Sleep Quality Index global score at wave 1 was "
           f"{W1_MEAN} (SD {W1_SD}).")
_POOR_S = ("Fourteen of the twenty-eight nurses (50.0%) scored 9 or more on the "
           "index.")


def _control():
    return account(
        variables=[var("var:sleep", "total sleep time", "integer_score",
                       units="minutes", step=1, gquote=SLEEP_G),
                   psqi_var(),
                   var("var:poor", "scored 9 or more on the index",
                       "percentage_of_subjects")],
        values=[n_row(),
                prose("val:sleep:mean", "mean", SLEEP_MEAN_MIN, _SLEEP_S,
                      variable_id="var:sleep", units="minutes"),
                prose("val:sleep:sd", "sd", SLEEP_SD_MIN, _SLEEP_S,
                      variable_id="var:sleep", units="minutes"),
                prose("val:psqi:mean", "mean", W1_MEAN, _PSQI_S,
                      variable_id="var:psqi"),
                prose("val:psqi:sd", "sd", W1_SD, _PSQI_S,
                      variable_id="var:psqi"),
                prose("val:poor:cnt", "count", "14", _POOR_S,
                      variable_id="var:poor"),
                prose("val:poor:pct", "percentage", "50.0%", _POOR_S,
                      variable_id="var:poor")])


class TestTheAuditReadCorrectlyStillRuns:
    def test_every_family_reaches_a_verdict_and_clears_it(self):
        """A guard that bought its safety by refusing everything would pass every
        attack in this file. The audit read in its own recorded units must keep
        reaching a verdict in all five families."""
        got = checks.evaluate(_control(), CONTROL_TEXT)
        assert accusations(got) == []
        families = {cid.split(":")[1] for cid in ran(got)}
        assert families == {"grim", "grimmer", "sprite", "sd_or_se", "count_percent"}

    def test_no_round_six_reason_fires_on_it(self):
        got = checks.evaluate(_control(), CONTROL_TEXT)
        new = {"printed_in_another_unit", "value_withdrawn_by_a_correction",
               "analysed_n_stated_for_another_stage",
               "analysis_unit_is_not_the_subject_count",
               "phase_n_over_several_phases"}
        assert not (every_reason(got) & new)


class TestTheVocabularyStaysClosed:
    def test_the_new_reasons_are_declared_once_each(self):
        """The premise-shaped codes belong to `premises`, the n-shaped ones to
        the bridge, and the two halves may not overlap."""
        assert {"printed_in_another_unit",
                "value_withdrawn_by_a_correction"} <= set(premises.REASONS)
        assert {"analysed_n_stated_for_another_stage",
                "analysis_unit_is_not_the_subject_count"} <= set(checks.BRIDGE_REASONS)
        assert not (set(premises.REASONS) & set(checks.BRIDGE_REASONS))
