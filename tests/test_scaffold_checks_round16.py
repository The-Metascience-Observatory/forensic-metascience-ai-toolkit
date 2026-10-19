"""ROUND 16 -- THE AVERAGING QUESTION ASKED ABOUT THE WRONG THING.

THE DEFECT, IN ONE SENTENCE: the premise `QUESTIONS["averaging"]` gates is a
per-subject STEP OF 1, and the question asked instead whether ANY combination of
two or more observations had happened. Those are not the same set. The maximum of
two whole-point cards is a combination and is always a whole number; so is the
minimum, the first, the last, the mode, a plain total and a plain count. Every one
of them satisfied the old question and every one of them withdrew a check from a
paper entitled to it.

MEASURED BEFORE ANYTHING WAS CHANGED, on the real candidate path -- a window plus
the printed context, which is what `adjudication.candidates` builds, and NOT a
bare sentence. That distinction is the whole reproduction: asked as bare
sentences with no window and no table context, sonnet answered all nine probe
cases correctly under the OLD wording, and the defect did not appear at all. It
appears when the candidate is the one the pipeline actually sends.

    2026-09-12, sonnet, one batch of nine, $0.234236, OLD wording:

      the higher of two whole-point cards, with "the hull score is itself
        always a whole number" in the SAME sentence  ....  true   (wrong)
      the higher of two whole-point cards, no such clause  ....  true   (wrong)
      the lower of two whole-point cards               ....  true   (wrong)
      the arithmetic middle of the two cards           ....  true   (right)
      set midway between them, splitting the difference ...  true   (right)
      the three cards totalled and divided by three    ....  true   (right)
      agreed between the two inspectors at the bench   ....  false
      reflects both inspectors' cards                  ....  false
      recorded by the one inspector at the single visit ...  false  (right)

    the same nine, NEW wording, $0.153031:

      the higher (twice) and the lower                 ....  false  (fixed)
      the arithmetic middle / midway / totalled-and-divided  true   (kept)
      agreed between; reflects both                    ....  true   (see below)
      the one inspector at the single visit            ....  false  (kept)

AND THE VETO POWER WAS RE-MEASURED RATHER THAN ASSUMED. All eight of round 15's
pinned defect passages -- the six round-14 evasions, the split sentence, the
footnote -- were re-asked under the new wording and all eight still answer `true`
($0.176487). An intermediate wording did NOT: it offered "a median of an even
number of values" as the averaging case, from which sonnet correctly inferred
that a median of an ODD number is integer-preserving, and read "the central
value of the three judges' cards" as a median of three. That is good arithmetic
and a lost veto, and it is why the shipped wording names no median at all and
sends every ambiguous wording to `true` instead.

THE TWO CASES THAT MOVED THE OTHER WAY, stated plainly rather than tidied away.
"The gasket score was agreed between the two inspectors" and "Each barrel's seal
score reflects both inspectors' cards" answered `false` under the old wording and
answer `true` under the new one. Neither sentence establishes that the result is
a whole number: an agreed score MAY be one of the two cards and may equally be a
figure they settled on between them. This is a lost check on a vaguely written
paper, not a lost accusation, and it is the direction this premise is required to
fail in -- a refusal premise may only ever remove a check (`index` applies an
averaging verdict on `true` alone). Recorded here because it is a real cost of
the fix and a later reader should not have to rediscover it.

A TEST MAY NOT SPEND MONEY. What is pinned below is the instrument (the question
says what it was measured saying) and the WIRING (a recorded verdict reaches
`granularity_verification` and does the thing the measurement says it does),
replayed from the verdicts above exactly as round 15 replays its own batch.
"""

from __future__ import annotations

import pytest

from metascience_agent.scaffold import (adjudication, checks,
                                        premise_reading as PR, premises)

BAD = {"suspicious", "highly_suspicious", "impossible"}

N = 30

#: THE SHIPYARD INSPECTION SURVEY -- round 16's own fixture, sharing nothing with
#: round 15's brass band. Every barrel's score is the HIGHER of two whole-point
#: cards, so every subject's value really is a whole number and the paper is
#: entitled to its step of 1. The mean printed below is reachable from an integer
#: total over 30, so an honest reading convicts nobody.
HULL = [4, 9, 7, 2, 10, 0, 6, 6, 3, 8, 5, 5, 9, 1, 7,
        10, 2, 4, 8, 6, 3, 7, 5, 9, 0, 6, 8, 4, 7, 5]
assert len(HULL) == N and all(float(x).is_integer() for x in HULL)
HULL_MEAN = f"{sum(HULL) / N:.2f}"
assert any(round(k / N, 2) == float(HULL_MEAN) for k in range(N * 10 + 1))
HULL_SD = "2.88"


def var(vid, name, quote):
    return {"id": vid, "name": name, "label": name, "printed_as": [],
            "kind": "ordinal", "role": None, "units": None,
            "units_source": "not_stated", "derivation": None, "derived_from": [],
            "bounds": {"source": "stated", "lower": 0, "upper": 10, "quote": quote},
            "granularity": {"per_subject_step": 1, "quote": quote}}


def cell(vid, statistic, printed, variable_id, col, col_label):
    lit = premises.read_plain(printed) or {}
    return {"id": vid, "statistic": statistic, "printed": printed,
            "numeric": lit.get("value"), "decimals": lit.get("decimals", 0),
            "printed_form": "plain", "units": None, "variable_id": variable_id,
            "id_check": "agrees", "statistic_disputed": False, "source": "table",
            "quote": None, "quote_verified": "cell", "printed_in_quote": None,
            "location": {"kind": "table_cell", "table_id": "table:1", "row": 1,
                         "col": col, "col_label": col_label},
            "coordinate": {"study_id": "study:yard", "group_id": "grp:barrels",
                           "phase_id": None}}


GRANT = "Hull score was recorded in whole points on a 0 to 10 card."


def hull_account():
    return {"paper": {"doi": "10.0000/shipyard",
                      "title": "The shipyard inspection survey"},
            "studies": [{"id": "study:yard", "design": "prospective_cohort",
                         "groups": [{"id": "grp:barrels", "label": "All barrels",
                                     "n": N, "n_source": "text"}]}],
            "variables": [var("var:hull", "Hull score", GRANT)],
            "values": [cell("val:mean", "mean", HULL_MEAN, "var:hull", 1, "Mean (SD)"),
                       cell("val:sd", "sd", HULL_SD, "var:hull", 2, "Mean (SD)"),
                       cell("val:n", "n", str(N), "var:hull", 3, "n")],
            "document": {"tables": [
                {"id": "table:1",
                 "caption": "Table 1. Barrel-level inspection scores.",
                 "footnotes": []}]}}


def paper(*sentences):
    return " ".join(("## Methods", GRANT) + sentences)


def accusations(got):
    return sorted({(r["check_id"], r["severity"]) for r in got["checks"]
                   if r["severity"] in BAD})


def candidates(acc, text):
    return [c for c in adjudication.candidates(acc, text)
            if c["variable_id"] == "var:hull"]


def reading(cands, establishes):
    return {"schema": PR.SCHEMA_VERSION, "prompt_version": PR.PROMPT_VERSION,
            "model": "sonnet", "n_candidates": len(cands), "n_asked": len(cands),
            "n_dropped": 0, "candidates": list(cands),
            "verdicts": [{"candidate_id": c["id"], "premise": "averaging",
                          "establishes": bool(establishes), "reason": "recorded",
                          "model": "sonnet", "prompt_version": PR.PROMPT_VERSION}
                         for c in cands],
            "problems": [], "cost_usd": 0.0, "n_calls": 1}


# --------------------------------------------------------------------------
# THE FOUR MEASURED FALSE VETOES, AND WHAT EACH OF THEM COSTS
# --------------------------------------------------------------------------

#: EVERY ONE OF THESE IS AN INTEGER-PRESERVING OPERATION OVER WHOLE-POINT CARDS,
#: so every one of them leaves a per-subject step of 1 exactly where it was. The
#: first states its own integrality in the same sentence and was vetoed anyway;
#: the others do not need to, because the arithmetic is a property of the
#: operation and not of the prose.
INTEGER_PRESERVING = {
    "the higher, said to be whole in the same sentence":
        "The hull score is the higher of the two inspectors' whole-point cards; "
        "because both cards are whole numbers, the hull score is itself always a "
        "whole number.",
    "the higher, with nothing said about wholeness":
        "Each hull score takes the higher of the two surveyors' whole-point cards.",
    "the lower":
        "The hull score is the lower of the two inspectors' whole-point cards.",
    "the most frequent of three":
        "The hull score is whichever of the three inspectors' cards was returned "
        "most often.",
    "a plain total":
        "The hull score is the two inspectors' whole-point cards added together.",
}

#: AND THESE CAN RETURN A NON-WHOLE NUMBER FROM WHOLE CARDS, so the veto is owed.
#: `3` and `4` average to `3.5` and split the difference at `3.5`; the point of
#: naming both is that the midpoint case is the one an "is it an average?" reading
#: of the question can talk itself out of.
BREAKS_INTEGRALITY = {
    "the arithmetic middle":
        "Each hull score is the arithmetic middle of the two inspectors' cards.",
    "midway, splitting the difference":
        "Each hull score is set midway between the two inspectors' cards, "
        "splitting the difference.",
    "totalled and divided":
        "Each hull score is the three raters' cards totalled and divided by three.",
}


@pytest.mark.parametrize("label", sorted(INTEGER_PRESERVING))
def test_an_integer_preserving_operation_still_reaches_a_model(label):
    """STAGE 1 IS UNCHANGED AND MUST STAY UNCHANGED. The fix is to the QUESTION,
    not to the recall net: relevance still surfaces the sentence, and it is the
    model that now answers it correctly. A fix that worked by hiding the passage
    would be the closed-vocabulary failure this module exists to stop."""
    text = paper(INTEGER_PRESERVING[label])
    got = candidates(hull_account(), text)
    assert any(INTEGER_PRESERVING[label].split(";")[0] in c["quote"] for c in got), \
        [c["quote"] for c in got]


@pytest.mark.parametrize("label", sorted(INTEGER_PRESERVING))
def test_the_measured_false_on_an_integer_preserving_operation_keeps_the_check(label):
    """WHAT THE FIX BUYS, REPLAYED. The new wording answered `false` on the two
    maximum forms and the minimum; carried through the wiring, a `false` leaves
    the step of 1 standing and the honest paper keeps its checks -- and, because
    a refusal premise moves on `true` alone, it is also exactly what the
    vocabulary would have done unasked."""
    text = paper(INTEGER_PRESERVING[label])
    acc = hull_account()
    cands = candidates(acc, text)
    rec = reading(cands, False)
    got = checks.evaluate(dict(acc, premise_reading=rec), text)
    assert accusations(got) == []
    assert [r for r in got["checks"] if r.get("check_id")], \
        "the fixture must run checks at all"
    ver = _hull_verification(acc, text, rec)
    assert ver["establishes_step_of_one"] is True, ver["reasons"]
    assert ver["reports_an_average_in"] is None


@pytest.mark.parametrize("label", sorted(BREAKS_INTEGRALITY))
def test_the_measured_true_on_a_real_average_still_withdraws_the_step(label):
    """THE CONTROL THAT MATTERS MORE THAN THE FIX. A question narrowed until it
    stops firing is not a fix, so the three genuine cases are replayed through
    the same wiring: a `true` reaches `granularity_verification` and the step of
    1 is gone."""
    text = paper(BREAKS_INTEGRALITY[label])
    acc = hull_account()
    cands = candidates(acc, text)
    assert cands
    ver = _hull_verification(acc, text, reading(cands, True))
    assert ver["establishes_step_of_one"] is False, ver
    assert ver["reports_an_average_in"] == "model_reading"


def _hull_verification(acc, text, rec):
    """`granularity_verification` for the hull score, under this reading."""
    hay = premises.Haystack(text)
    variables = premises.readable_variables(acc)
    v = [x for x in variables if x["id"] == "var:hull"][0]
    idx = PR.index(rec, hay, premises.variables_by_id(variables))
    values = [x for x in acc["values"] if x["variable_id"] == "var:hull"]
    return premises.granularity_verification(
        v, hay, variables, values,
        averaging_verdict=idx["averaging"].get("var:hull"))


def test_a_true_verdict_on_a_real_average_is_indexed_onto_the_variable():
    """The join `granularity_verification` reads is by VARIABLE id, and the
    measurement above is worth nothing if the verdict lands anywhere else."""
    text = paper(BREAKS_INTEGRALITY["the arithmetic middle"])
    acc = hull_account()
    cands = candidates(acc, text)
    hay = premises.Haystack(text)
    variables = premises.readable_variables(acc)
    idx = PR.index(reading(cands, True), hay, premises.variables_by_id(variables))
    assert "var:hull" in idx["averaging"]
    assert idx["averaging"]["var:hull"]["establishes"] is True


# --------------------------------------------------------------------------
# THE INSTRUMENT ITSELF
# --------------------------------------------------------------------------


def test_the_question_asks_about_the_arithmetic_and_not_about_combination():
    """THE PIN ON THE WORDING, and it is a pin on the LOGIC rather than on the
    four sentences that were measured. What makes the question right is that it
    names the integer-preserving operations as the FALSE case and the
    non-integer-capable ones as the TRUE case; a later edit that drops either
    list reopens the defect, and a later edit that merely rephrases around it
    will still pass -- which is the honest limit of a test like this."""
    q = PR.QUESTIONS["averaging"]
    assert "whole number" in q
    for preserving in ("the higher", "the lower", "the most frequent",
                       "a plain total", "a plain count"):
        assert preserving in q, preserving
    for breaking in ("average", "mean", "divided by", "weighted blend",
                     "midpoint", "splitting the difference"):
        assert breaking in q, breaking


def test_the_unclear_case_resolves_toward_the_refusal():
    """THE CLAUSE THAT COST A PINNED DEFECT WHEN IT WAS ABSENT. Without it
    sonnet read "the central value of the three judges' cards" as a median of
    three -- correct arithmetic, lost veto. A wording that could name either
    kind of operation does not establish integrality, and this premise may only
    remove a check, so the unclear case answers `true`."""
    q = PR.QUESTIONS["averaging"]
    assert "leaves unclear" in q
    assert "could equally name an averaging one" in q
    # AND NO MEDIAN IS OFFERED AS AN EXCEPTION. Naming the even/odd rule is what
    # taught the model to resolve "the central value" rather than refuse it.
    assert "median" not in q


def test_the_question_still_plugs_into_the_same_boolean_slot():
    """The rewording is a change to one string of `QUESTIONS` and to nothing
    else: the schema, the addressing and the refusal polarity are the ones E1
    measured, and `averaging` is still the premise whose verdict may only ADD a
    refusal."""
    assert "averaging" in PR.REFUSAL_PREMISES
    assert "averaging" not in PR.LICENCE_PREMISES
    assert PR.SCHEMA["properties"]["verdicts"]["items"]["required"] == [
        "candidate", "establishes", "reason"]
    cands = candidates(hull_account(),
                       paper(BREAKS_INTEGRALITY["totalled and divided"]))
    assert cands and all(c["question"] == PR.QUESTIONS["averaging"] for c in cands)
    assert PR.QUESTIONS["averaging"] in PR.build_prompt(cands)


def test_the_prompt_version_moved_with_the_question():
    """A run read back against a different question set is a run of a different
    instrument, and `PROMPT_VERSION` is the field that says so.

    IT MOVED AGAIN IN ROUND 18, which added a SIXTH question (`varying_n`) and
    reworded none of the five. So what this pins is the conscious decision: the
    constant is not the one it carried before this round's own measurement, and
    round 16's measured `averaging` string is untouched -- which is the half that
    could invalidate anything, and `test_no_other_question_moved` checks it in
    full.

    AND AGAIN IN ROUND 20, which REWORDED `varying_n` after measuring that round
    18's string withdrew the only check seven honest papers had. The same
    argument applies unchanged: `averaging` is untouched, so round 16's own
    measurement still describes the bytes it was taken on.

    AND AGAIN IN ROUND 24, which added a SEVENTH question
    (`discreteness_attachment`, the withdrawal-only licence veto) and reworded
    none of the six. The argument holds a third time, for the third time by
    `test_no_other_question_moved` rather than by this sentence.

    AND AGAIN IN ROUND 28, which WIDENED that seventh question from the
    attachment sub-question to the premise question itself and moved which
    boolean withdraws. It reworded none of the six others, so round 16's own
    `averaging` measurement still describes the bytes it was taken on -- the
    fourth time that argument has had to hold, and the fourth time
    `test_no_other_question_moved` is what holds it."""
    assert PR.PROMPT_VERSION != "e1-target-bounds/2026-09-09"
    assert PR.PROMPT_VERSION != "e1-varying-n/2026-09-12"
    assert PR.PROMPT_VERSION != "e1-varying-n-target-anchored/2026-09-12"
    assert PR.PROMPT_VERSION != "e1-discreteness-attachment/2026-09-12"
    assert PR.PROMPT_VERSION == "e1-discreteness-premise/2026-09-13"


def test_no_other_question_moved():
    """The four other premises are E1's own strings and were not part of this
    measurement; a rewording that quietly touched one of them would invalidate
    E1's 37/37 without anything failing."""
    assert PR.QUESTIONS["bound"].startswith("Does this sentence state the numeric range")
    assert PR.QUESTIONS["step"].startswith("Does this sentence establish that each subject's")
    assert PR.QUESTIONS["correction"].startswith("Does this correction notice say")
    assert PR.QUESTIONS["estimator"].startswith("Does this sentence, caption or column heading")
