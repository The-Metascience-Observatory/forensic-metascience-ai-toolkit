"""ROUND 28 -- THE THREE SUB-QUESTIONS ARE ONE QUESTION, AND THE BOOLEAN IS
NAMED FOR THE PREMISE.

WHAT WAS TESTED. Round 24 gave the granularity licence a withdrawal-only model
veto and asked it the ATTACHMENT sub-question alone -- whose quantity do this
passage's whole-number words describe? Rounds 25, 26 and 27 then built two more
REGEX guards for the two sub-questions it does not reach: polarity (does the
passage deny it?) and unit of observation (whole-numbered per what?). The
hypothesis this round tested is that the three are one question wearing three
coats, and that asking it once of the same window by the same machinery closes
all three -- because the separation is what created three vocabularies to evade.

# THE HEAD-TO-HEAD, WITH BOTH ARMS AND EVERY DENOMINATOR

Sonnet, 2026-09-13, $2.082198 in total, on three fixture families -- a half-point
apiary card, a half-point bell card and a half-point pool-drill card, each with a
genuinely whole-numbered companion. The probes are the adversarial corpora these
guards were built against: the 45-phrasing denial battery and the ten remaining
negation particles, 42 per-observation phrasings, 8 where the two guards
interact, round 23's 19 surviving attachment leaks and sweep2's 25.

The ACCUSATION ARM is every probe on which a per-subject step of 1 must NOT be
licensed on an honest paper; a licence there makes GRIM, GRIMMER and SPRITE all
return `impossible` on a card the paper itself grades to the nearest half point.

    channel                       n     regex guards     one question
    -------------------------------------------------------------------
    polarity (denial)            54           46               53
    unit of observation          42           16               42
    attachment                   44           25               44
    the two interacting           8            8                8
    -------------------------------------------------------------------
    ACCUSATION ARM              148           95              147
    HONEST ARM, licences kept    62           38               59

**One question closes 147 of 148 where the three vocabularies close 95, and
keeps 59 of 62 honest licences where they keep 38. It dominates on both axes.**
It closes 53 accusation channels the guards leave open and misses exactly ONE
they close.

THE DISAGREEMENT IS ONE PROBE AND IT IS NOT A MODEL ERROR. `Comb uniformity could
not be recorded in anything other than whole units` is a DOUBLE NEGATIVE, and the
model reads it as English does -- "means it was necessarily recorded in whole
units" -- and declines to withdraw. The regex closes it by accident of its own
documented cost: round 25's guard is polarity-blind past the first negator and
its own test file already pins this sentence as a licence it wrongly destroys. So
on this probe the vocabulary is right for the wrong reason and the model is right
about the sentence; it counts as a miss because the fixture paper is a half-point
card, which makes the sentence a self-contradiction no honest paper would print.
THE SHIPPED PATH CLOSES IT ANYWAY, because the veto is a CONJUNCT on the free
path's licence and the free path already refuses it (`TestTheFreePathIsUnchanged`).

THE HONEST ARM, and it is the half that decides the architecture. 62 sentences
that genuinely DO establish a per-subject whole number, in ordinary academic
register, including the three hard shapes the brief names -- a per-subject claim
in a sentence that also mentions per-observation recording, a double negative,
and a claim about the CARD that IS a claim about the value:

    the free path refuses 24 of them before any model is asked   (21 to a GUARD,
                                                                  3 to the
                                                                  vocabulary)
    38 are licensed at HEAD; the question wrongly withdraws 1
    of the 24 the guards refuse, the question would KEEP 22

The one it withdraws among the 38 is the synthetic control `recorded not only as
integers but also as a grade`, which on a half-point card is a paper
contradicting itself; on the 37 genuine honest-register sentences licensed at
HEAD it withdraws NONE. Of the 24 the guards refuse it withdraws 2, both
subset-restricted (`counted in whole units in three of the eleven yards`,
`Colonies that were not requeened had their queen cells counted in whole units`)
and both defensible readings -- and both are sentences the guards refuse too.

AND THE DENIAL GUARD'S OWN CLOSURE IS HALF ACCIDENT, which is the measurement
that prompted the round. Of the 54 denial-channel probes, round 25's guard closes
**26**; another **20** are closed by OLDER guards by accident of clause shape (10
`unattributed`, 7 `boundary_unresolved`, 3 `belongs_to_other`) and 8 leak. A
channel closed at 48% by the instrument built for it is a coin flip, not a guard.

THE CAVEATS THAT TRAVEL WITH THESE NUMBERS. The two arms were bought in two
batches of 91 and 119, each one deterministic interleave, which is E1's validated
composition and still a composition (round 18's lesson: a refusal premise's
question must be measured at the size a real run asks it -- which is what the
end-to-end runs below are for). Three fixture families are not a corpus. And the
honest arm is prose written for this measurement, because the pinned suite cannot
adjudicate this premise at all: `discreteness_boundary: unresolved` occurs 0
times across 979 pinned inputs and round 25's guard fires 0 times in 6,161 calls
across the suite.

# THE RESULT THAT COST FOUR PAID RUNS AND IS THE REAL FINDING

**A WIDENED QUESTION CANNOT BE ASKED THROUGH A BOOLEAN CALLED `establishes`.**
Three wordings of the widened question were run END TO END through
`adjudication_attach.adjudicate` on one two-candidate paper, which is round 24's
own rule (a batch score is not a measurement of what a run will do):

    wording                                              $        result
    ---------------------------------------------------------------------------
    "does this passage FALL SHORT of showing ..."     0.246996  both INVERTED
    "could the reported figure be a fraction ..."     0.078343  both INVERTED
    "does it state at least one of four facts"        0.078527  both INVERTED
    the same, PREAMBLE's polarity rule neutralised    0.078241  both INVERTED
    CONTROL: round 24's own string, same paper        0.043788  correct
    the premise question, natural direction           0.056031  correct
    the same through the shipped wiring               0.035678  correct

Every one returned the CORRECT REASON. The third names fact (c) in as many words
-- "ties whole-unit counting to single occasions, not the per-colony Table 1
figure" -- and answered `false`. Round 24's own string, on the SAME paper, was
not inverted, which attributes the inversion to the widening rather than to the
fixture. And the neutralised-preamble run rules out the shared preamble, which
was the obvious suspect and is not the cause.

The model was never reading the passage wrong. It was filling a field called
`establishes` with whether the premise holds, which is what the field is called
-- and round 24 escaped only because ITS premise was a different proposition
("these words are about another quantity"), so the field could be borrowed. Once
the question IS the premise question, the field name wins over any wording. So
the question is asked in the direction the field is named for and the WITHDRAWING
answer is `false` (`premise_reading.WITHDRAWN_ON_FALSE`). The same paper is then
right on both candidates.

# WHAT DID NOT MOVE, AND IT IS THE ONLY THING THAT MATTERED

THE POLARITY OF THE POWER. A verdict may still only ever take a check away:
`eligible` asks only about a variable the free path has ALREADY licensed by a
sentence, so the keeping answer agrees with a licence that already stood and
restores nothing, and `granularity_verification` ANDs the withdrawal in and uses
it in no other expression. Round 24's cross-product test asserts that over both
answers and now reads the direction from `premise_reading.withdraws` instead of
writing it down a second time -- which is the only way a fabricated-verdict suite
can be a claim about the shipped rule.

AND THE NEW DIRECTION'S FAILURE MODE IS NAMED RATHER THAN HIDDEN. Under round
24's direction a confused model that answered `true` withdrew a check, which is
safe. Under this one a confused model that answers `true` leaves the check
RUNNING. That is the less safe default, and it is why the accusation arm above is
148 probes rather than an argument: an unmeasured question in this direction would
be a promise. Measured, the model answered the withdrawing way on 147 of 148 and
gave a located reason every time.

# THE REGEX GUARDS ARE NOT DELETED, AND THAT IS DELIBERATE

They are the FREE path; this is opt-in behind `--adjudicate-attachment`. Removing
them would take the default path from 95 of 148 accusation channels closed to
none, which is the wrong direction by any reading of the table above. What the
table DOES say is that the three-guard structure is not the exit: six rounds have
attacked it, round 23 proved no rule over the computable features separates the
two populations, and the guards now cost 21 honest licences of 62 to close 95
accusation channels of 148, where one question costs 3 to close 147. Whether the
paid path should become the default is a separate decision with a separate owner
-- the same line round 24 drew and for the same reason.

THE FIXTURE IS THE RAVENSMOOR LAMP ROOM and shares no noun, scale or number with
the pool, orchard, kiln, depot, Penhale, lighthouse, bell, quay, loom, apiary or
bakery fixtures.
"""

from __future__ import annotations

import statistics as st
from decimal import ROUND_HALF_UP, Decimal

import pytest

from metascience_agent.scaffold import adjudication_attach as AA
from metascience_agent.scaffold import checks, premises
from metascience_agent.scaffold import premise_reading as PR

# --------------------------------------------------------------------------
# THE FIXTURE
# --------------------------------------------------------------------------

#: The half-point card. `Lamp glass clarity` is graded TO THE NEAREST HALF POINT
#: on a 0-16 card and the paper says so, so a per-subject step of 1 is FALSE
#: about it and any licence hands GRIM, GRIMMER and SPRITE a mean no integer
#: total can reach.
CLARITY = [0.5, 0.5, 0.5, 0.5, 0.5, 1.0, 2.0, 3.5, 4.5, 5.0,
           5.5, 6.5, 6.5, 7.0, 7.0, 8.0, 8.0, 8.5, 9.5, 10.0,
           10.0, 10.5, 10.5, 10.5, 12.0, 12.0, 12.0, 12.5, 12.5, 13.0,
           13.0, 13.5, 13.5, 14.0, 14.0, 14.5, 14.5, 14.5, 15.0, 15.5]
NL = len(CLARITY)
C_MEAN = f"{st.fmean(CLARITY):.2f}"
C_SD = f"{st.stdev(CLARITY):.2f}"
assert NL == 40


def _reaches(total, mean_s: str) -> bool:
    """Does this total reach the printed mean under EITHER convention?

    Both are asked. GRIM in this repo carries the truncation rescue (`642a6f1`),
    so a fixture built on round-half-up alone is not a known answer at all
    ([[independence-in-process-is-not-independence]]).
    """
    q = Decimal(total) / Decimal(NL)
    half = q.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return (str(half) == mean_s
            or f"{Decimal(int(q * 100)) / Decimal(100):.2f}" == mean_s)


# UNREACHABLE from any integer total over 40 under either convention, and
# reachable from a half-point one -- so the accusation the free path makes on
# this card is demonstrably false rather than assumed false.
assert not any(_reaches(k, C_MEAN) for k in range(NL * 16 + 1)), C_MEAN
assert any(_reaches(Decimal(t) / 2, C_MEAN) for t in range(NL * 32 + 1)), C_MEAN

#: The honest whole-number companion on the same survey, where a licence buys
#: real `consistent` rows and so is where the COVERAGE cost is measured.
LENSES = [(i * 7 + 3) % 17 for i in range(NL)]
L_MEAN = f"{st.fmean(LENSES):.2f}"
L_SD = f"{st.stdev(LENSES):.2f}"

N_Q = "Forty-one lamps were withdrawn from the Ravensmoor lamp room (n = 41)."
#: The bounds sentence for each variable, carrying NO discreteness vocabulary of
#: its own, so every probe below licenses -- or fails to -- purely on what it
#: adds. Separating the two is what keeps a probe from refusing for
#: `bound_quote_does_not_state_it` and reading as safety
#: ([[a-fixture-that-excludes-the-defect-region]]).
BOUND_C = "Lamp glass clarity was graded on a card running from 0 to 16."
BOUND_L = "Cracked lenses were recorded on a card running from 0 to 16."
GRAN_L = "Cracked lenses were counted in whole units on a card running from 0 to 16."

#: ONE PROBE PER CHANNEL, each of which licenses a step of 1 at HEAD on the
#: half-point card -- so each is a live accusation the free path makes and the
#: veto has to remove. Verified by `TestTheFixtureReachesEachChannel`.
CHANNELS = {
    # POLARITY: the paper denies whole-number granularity with an ordinary
    # lexical verb rather than a negation particle.
    "polarity": "Lamp glass clarity ceased to be counted in whole units after "
                "the first shift.",
    # UNIT OF OBSERVATION: what is whole is one inspection's grade, and the
    # table prints one figure per lamp.
    "per_observation": "Lamp glass clarity was counted in whole units at each "
                       "inspection.",
    # ATTACHMENT: the only whole-number words in the sentence belong to an
    # undeclared rival quantity.
    "attachment": "Besides a Likert item on lampman workload, lamp glass "
                  "clarity was graded to the nearest half point.",
}


def _var(vid, name, quote, bound_quote, *, kind="ordinal"):
    return {"id": vid, "name": name, "label": name, "printed_as": [],
            "kind": kind, "role": None, "units": None,
            "units_source": "not_stated", "derivation": None, "derived_from": [],
            "bounds": {"source": "stated", "lower": 0, "upper": 16,
                       "quote": bound_quote},
            "granularity": {"per_subject_step": 1, "quote": quote}}


def _cell(vid, statistic, printed, variable_id, col, col_label):
    lit = premises.read_plain(printed) or {}
    return {"id": vid, "statistic": statistic, "printed": printed,
            "numeric": lit.get("value"), "decimals": lit.get("decimals", 0),
            "printed_form": "plain", "units": None, "variable_id": variable_id,
            "id_check": "agrees", "statistic_disputed": False, "source": "table",
            "quote": None, "quote_verified": "cell", "printed_in_quote": None,
            "location": {"kind": "table_cell", "table_id": "table:1", "row": 1,
                         "col": col, "col_label": col_label},
            "coordinate": {"study_id": "study:ravensmoor",
                           "group_id": "grp:lamps", "phase_id": None}}


def lamp_room(clarity_sentence: str, lens_sentence: str = GRAN_L):
    """The paper, with a granularity sentence for each of the two variables."""
    variables = [_var("var:clarity", "Lamp glass clarity", clarity_sentence,
                      BOUND_C),
                 _var("var:lenses", "Cracked lenses", lens_sentence, BOUND_L)]
    values = [_cell("val:cm", "mean", C_MEAN, "var:clarity", 1, "Mean (SD)"),
              _cell("val:cs", "sd", C_SD, "var:clarity", 1, "Mean (SD)"),
              _cell("val:cn", "n", str(NL), "var:clarity", 2, "n"),
              _cell("val:lm", "mean", L_MEAN, "var:lenses", 3, "Mean (SD)"),
              _cell("val:ls", "sd", L_SD, "var:lenses", 3, "Mean (SD)"),
              _cell("val:ln", "n", str(NL), "var:lenses", 4, "n")]
    account = {"paper": {"doi": "10.0000/ravensmoor",
                         "title": "Lamp condition at the Ravensmoor colliery",
                         "species_or_population": "safety lamps"},
               "subjects": {"population": "safety lamps in service",
                            "unit_of_analysis": "a lamp"},
               "studies": [{"id": "study:ravensmoor",
                            "design": "prospective_cohort",
                            "groups": [{"id": "grp:lamps", "label": "All lamps",
                                        "n": NL, "n_source": "text"}]}],
               "variables": variables, "values": values,
               "document": {"tables": [
                   {"id": "table:1", "caption": "Table 1. Lamp-level condition.",
                    "footnotes": []}]}}
    text = "\n\n".join(["## Methods", N_Q, BOUND_C, clarity_sentence, BOUND_L,
                        lens_sentence]) + "\n"
    return account, text


BAD = {"suspicious", "highly_suspicious", "impossible"}


def _reading(cands, answers):
    """A `premise_reading` block answering the candidates the module built.

    THE VERDICTS ARE FABRICATED, for round 24's reason: what rots is the WIRING
    and the POLARITY, and that is the half a paid call cannot re-run cheaply.
    The paid measurement is in this module's docstring, dated, with its arms.
    """
    return {"schema": PR.SCHEMA_VERSION, "prompt_version": "round28-fabricated",
            "model": "round28-fabricated", "candidates": cands,
            "verdicts": [{"candidate_id": c["id"], "premise": c["premise"],
                          "establishes": bool(answers[c["id"]]),
                          "reason": "fabricated for the wiring test",
                          "model": "round28-fabricated",
                          "prompt_version": "round28-fabricated"}
                         for c in cands if c["id"] in answers]}


def _answer(withdraw: bool) -> bool:
    """The model answer that MEANS `withdraw`, read from the shipped rule.

    Written once here rather than as a literal in thirty assertions, so that a
    future round which moves the direction again moves these tests with it
    instead of leaving them green on a rule nothing obeys.
    """
    for said in (True, False):
        if PR.withdraws(AA.PREMISE, said) is withdraw:
            return said
    raise AssertionError("neither answer withdraws")


WITHDRAW, KEEP = _answer(True), _answer(False)


def evaluate(account, text, answers=None):
    acc = {k: (list(v) if isinstance(v, list) else v) for k, v in account.items()}
    acc["variables"] = [dict(v) for v in account["variables"]]
    if answers is not None:
        cands = AA.candidates(acc, text)
        acc["premise_reading"] = _reading(
            cands, answers(cands) if callable(answers) else answers)
    acc = premises.stamp(acc, text)
    got = checks.evaluate(acc, text)
    return {"account": acc,
            "accusations": sorted({(r["family"], r["variable_id"], r["severity"])
                                   for r in got["checks"]
                                   if r["severity"] in BAD}),
            "granularity_rows": sorted((r["family"], r["variable_id"])
                                       for r in got["checks"]
                                       if r["family"] in {"grim", "grimmer",
                                                          "sprite"})}


def verification(account, vid):
    for var in account["variables"]:
        if var["id"] == vid:
            return (var.get("granularity") or {}).get("verification") or {}
    raise AssertionError(vid)


ALL_WITHDRAW = (lambda cs: {c["id"]: WITHDRAW for c in cs})
ALL_KEEP = (lambda cs: {c["id"]: KEEP for c in cs})


# --------------------------------------------------------------------------
# 0. THE FIXTURE PROVES ITS OWN TEETH ON ALL THREE CHANNELS
# --------------------------------------------------------------------------


class TestTheFixtureReachesEachChannel:
    """Each probe must LICENSE at HEAD and ACCUSE, or the veto is being measured
    where the defect cannot occur -- this repo's own
    [[a-fixture-that-excludes-the-defect-region]], which has bitten this premise
    four times."""

    @pytest.mark.parametrize("channel", sorted(CHANNELS))
    def test_the_free_path_licenses_a_step_it_should_not(self, channel):
        acc, text = lamp_room(CHANNELS[channel])
        rec = verification(evaluate(acc, text)["account"], "var:clarity")
        assert rec["establishes_step_of_one"] is True
        assert rec["discreteness_source"] == premises.STATED_DISCRETENESS

    @pytest.mark.parametrize("channel", sorted(CHANNELS))
    def test_and_three_tools_accuse_the_honest_paper(self, channel):
        acc, text = lamp_room(CHANNELS[channel])
        got = evaluate(acc, text)
        assert {f for f, v, _ in got["accusations"] if v == "var:clarity"} == \
            {"grim", "grimmer", "sprite"}

    def test_the_honest_companion_is_licensed_and_checked(self):
        """The coverage side: a licence here buys real rows, so a veto that
        destroys them is a cost and not a saving."""
        acc, text = lamp_room(CHANNELS["per_observation"])
        got = evaluate(acc, text)
        assert verification(got["account"], "var:lenses")["establishes_step_of_one"]
        assert {f for f, v in got["granularity_rows"] if v == "var:lenses"} == \
            {"grim", "grimmer", "sprite"}
        assert not [a for a in got["accusations"] if a[1] == "var:lenses"]


# --------------------------------------------------------------------------
# 1. ONE QUESTION REACHES ALL THREE CHANNELS
# --------------------------------------------------------------------------


class TestOneQuestionClosesAllThree:
    @pytest.mark.parametrize("channel", sorted(CHANNELS))
    def test_a_withdrawing_verdict_removes_the_accusation(self, channel):
        acc, text = lamp_room(CHANNELS[channel])
        got = evaluate(acc, text, answers=ALL_WITHDRAW)
        assert not [a for a in got["accusations"] if a[1] == "var:clarity"]
        assert verification(got["account"],
                            "var:clarity")["establishes_step_of_one"] is False

    def test_the_docket_reason_does_not_name_a_cause_it_was_not_given(self):
        """Renamed in round 28, because the old key asserted ATTACHMENT on every
        withdrawal and the widened question withdraws for a denial and for a
        per-observation claim too. A docket that names the wrong cause is the
        [[a-fix-can-repair-its-own-symptom]] shape at a reader-facing boundary.
        """
        assert "discreteness_licence_withdrawn_by_a_model" in premises.REASONS
        assert "discreteness_claim_belongs_to_another_quantity" not in premises.REASONS

    @pytest.mark.parametrize("channel", sorted(CHANNELS))
    def test_and_the_record_says_a_licence_fell(self, channel):
        """[[absence-must-be-representable]]: a docket has to say the licence
        WAS withdrawn, not merely that none was found."""
        acc, text = lamp_room(CHANNELS[channel])
        got = evaluate(acc, text, answers=ALL_WITHDRAW)
        rec = verification(got["account"], "var:clarity")
        assert rec["discreteness_licence_withdrawn_by_model"] is True
        assert rec["model_reading_attachment"]["withdraws"] is True
        assert [r for r in rec["reasons"]
                if r["reason"] == "discreteness_licence_withdrawn_by_a_model"]

    @pytest.mark.parametrize("channel", sorted(CHANNELS))
    def test_one_question_is_asked_and_not_three(self, channel):
        """The hypothesis in one assertion: the candidate set carries a single
        premise, asked once of the window the licence rests on."""
        acc, text = lamp_room(CHANNELS[channel])
        cands = [c for c in AA.candidates(acc, text)
                 if c["variable_id"] == "var:clarity"]
        assert len(cands) == 1
        assert {c["premise"] for c in cands} == {AA.PREMISE}

    def test_the_honest_companion_beside_it_keeps_every_row(self):
        """A withdrawal is per variable. The whole-unit measure in the same
        paper, answered the keeping way, keeps all three of its rows."""
        acc, text = lamp_room(CHANNELS["polarity"])
        cands = AA.candidates(acc, text)
        answers = {c["id"]: (WITHDRAW if c["variable_id"] == "var:clarity"
                             else KEEP) for c in cands}
        got = evaluate(acc, text, answers=answers)
        assert {f for f, v in got["granularity_rows"] if v == "var:lenses"} == \
            {"grim", "grimmer", "sprite"}
        assert not got["accusations"]


# --------------------------------------------------------------------------
# 2. THE DIRECTION MOVED; THE POWER DID NOT
# --------------------------------------------------------------------------


class TestTheWithdrawingAnswerIsFalse:
    def test_the_premise_is_declared_in_one_place(self):
        assert AA.PREMISE in PR.WITHDRAWN_ON_FALSE
        assert AA.PREMISE in PR.REFUSAL_PREMISES

    def test_and_the_rule_is_a_function_rather_than_a_literal(self):
        assert PR.withdraws(AA.PREMISE, False) is True
        assert PR.withdraws(AA.PREMISE, True) is False

    @pytest.mark.parametrize("premise", sorted(PR.REFUSAL_PREMISES
                                               - PR.WITHDRAWN_ON_FALSE))
    def test_every_other_refusal_premise_is_unmoved(self, premise):
        """Four questions are asked about a fact BESIDE the premise, so `true`
        still means "add the refusal" for all of them. A change that moved them
        too would be a silent change to `averaging`, `estimator`, `correction`
        and `varying_n`."""
        assert PR.withdraws(premise, True) is True
        assert PR.withdraws(premise, False) is False

    def test_a_filed_row_carries_the_answer_and_the_decision(self):
        """Both, because a reader of a docket needs the model's answer AND what
        this layer did with it -- and because the fail-open property below only
        holds while the literal answer is still there to be read."""
        acc, text = lamp_room(CHANNELS["attachment"])
        cands = AA.candidates(acc, text)
        reading = _reading(cands, ALL_WITHDRAW(cands))
        idx = PR.index(reading, premises.Haystack(text),
                       {v["id"]: v for v in acc["variables"]})
        row = idx[AA.PREMISE]["var:clarity"]
        assert row["establishes"] is False
        assert row["withdraws"] is True

    def test_a_consumer_reading_the_wrong_field_fails_open(self):
        """THE TRAP THIS DIRECTION SETS, and the reason it is survivable. Four
        other refusal premises are read as `verdict.get("establishes")`, so a
        copy-paste consumer of THIS one reads False on a row that withdraws --
        declines to withdraw, loses a check, and cannot buy an accusation."""
        acc, text = lamp_room(CHANNELS["per_observation"])
        cands = AA.candidates(acc, text)
        reading = _reading(cands, ALL_WITHDRAW(cands))
        idx = PR.index(reading, premises.Haystack(text),
                       {v["id"]: v for v in acc["variables"]})
        row = idx[AA.PREMISE]["var:clarity"]
        assert not row["establishes"], "the wrong field reads as 'do not withdraw'"

    @pytest.mark.parametrize("channel", sorted(CHANNELS))
    def test_the_keeping_answer_changes_nothing(self, channel):
        acc, text = lamp_room(CHANNELS[channel])
        free = verification(evaluate(acc, text)["account"], "var:clarity")
        kept = verification(evaluate(acc, text, answers=ALL_KEEP)["account"],
                            "var:clarity")
        for field in ("establishes_step_of_one", "discreteness_source",
                      "kind_makes_it_necessary"):
            assert kept[field] == free[field], field
        assert kept["discreteness_licence_withdrawn_by_model"] is False

    @pytest.mark.parametrize("channel", sorted(CHANNELS))
    def test_no_answer_of_either_sign_adds_a_check(self, channel):
        """The cardinal property, over the cross-product rather than in one
        direction: a verdict may only ever take a check away."""
        acc, text = lamp_room(CHANNELS[channel])
        free = evaluate(acc, text)
        for answers in (ALL_KEEP, ALL_WITHDRAW):
            got = evaluate(acc, text, answers=answers)
            assert set(got["granularity_rows"]) <= set(free["granularity_rows"])
            assert set(got["accusations"]) <= set(free["accusations"])

    def test_no_answer_restores_a_licence_the_free_path_withheld(self):
        """The named inversion, on a sentence the free path already refuses: the
        keeping answer must not mean `grant`."""
        denied = "Lamp glass clarity was not counted in whole units."
        acc, text = lamp_room(denied)
        assert verification(evaluate(acc, text)["account"],
                            "var:clarity")["establishes_step_of_one"] is False
        for answers in (ALL_KEEP, ALL_WITHDRAW):
            rec = verification(evaluate(acc, text, answers=answers)["account"],
                               "var:clarity")
            assert rec["establishes_step_of_one"] is False
            assert rec["discreteness_source"] == premises.ASSUMED_DISCRETENESS

    def test_an_unlicensed_variable_is_never_asked(self):
        """`eligible`'s first exclusion is what makes the keeping answer
        harmless: there is no licence to agree with unless one already stood."""
        denied = "Lamp glass clarity was not counted in whole units."
        acc, text = lamp_room(denied)
        assert "var:clarity" not in {c["variable_id"]
                                     for c in AA.candidates(acc, text)}


# --------------------------------------------------------------------------
# 3. THE FREE PATH IS UNTOUCHED, AND THE REGEX GUARDS ARE STILL THERE
# --------------------------------------------------------------------------


class TestTheFreePathIsUnchanged:
    """The three guards are the FREE path and this round does not remove them.
    Deleting them would make the default worse by every number in the module
    docstring, and whether the default should change is a separate decision."""

    def test_the_denial_guard_still_refuses(self):
        acc, text = lamp_room("Lamp glass clarity was not counted in whole "
                              "units.")
        rec = verification(evaluate(acc, text)["account"], "var:clarity")
        assert rec["establishes_step_of_one"] is False
        assert rec["discreteness_denied_by"]

    def test_the_per_observation_guard_still_refuses(self):
        acc, text = lamp_room("Lamp glass clarity was counted in whole units "
                              "at each of three inspections.")
        rec = verification(evaluate(acc, text)["account"], "var:clarity")
        assert rec["establishes_step_of_one"] is False
        assert rec["discreteness_claim_is_per"]

    def test_the_attachment_guard_still_refuses(self):
        acc, text = lamp_room("Lamp glass clarity was graded to the nearest "
                              "half point, with cracked prisms counted in "
                              "whole units.")
        rec = verification(evaluate(acc, text)["account"], "var:clarity")
        assert rec["establishes_step_of_one"] is False

    @pytest.mark.parametrize("channel", sorted(CHANNELS))
    def test_a_run_with_no_reading_behaves_exactly_as_before(self, channel):
        """No `premise_reading` block at all: every channel still licenses and
        still accuses. The veto is off unless it is asked for, which is what
        makes the round measurable against the old behaviour rather than a
        replacement for it."""
        acc, text = lamp_room(CHANNELS[channel])
        got = evaluate(acc, text)
        assert verification(got["account"],
                            "var:clarity")["establishes_step_of_one"]
        assert [a for a in got["accusations"] if a[1] == "var:clarity"]

    def test_the_free_net_never_offers_this_premise(self):
        acc, text = lamp_room(CHANNELS["attachment"])
        got = PR.candidates(acc, text)
        assert got, "the fixture must produce candidates at all"
        assert AA.PREMISE not in {c["premise"] for c in got}


# --------------------------------------------------------------------------
# 4. THE RESIDUE, NAMED RATHER THAN COUNTED
# --------------------------------------------------------------------------


class TestWhatTheOneQuestionDoesNotClose:
    """The one probe of 148 the question misses, and the two honest licences of
    62 it costs, pinned so the round cannot be read as "closes everything".

    Each is a claim about `PROMPT_VERSION`'s bytes on 2026-09-13
    ([[measured-claims-have-a-shelf-life]]). What is EXECUTED here is the part a
    test can hold: that the shipped path closes the miss by another route, and
    that the two honest losses were already losses before this round.
    """

    #: `could not be recorded in anything other than whole units` -- a double
    #: negative, which affirms integrality by denying its complement. The model
    #: reads it as English does and declines to withdraw; the free path refuses
    #: it for round 25's own documented reason, so the CONJUNCT closes it.
    DOUBLE_NEGATIVE = ("Lamp glass clarity could not be recorded in anything "
                       "other than whole units.")

    #: Both subset-restricted, both honest, both refused by the free path
    #: already -- so the question costs nothing here that was not already spent.
    SUBSET_RESTRICTED = (
        "Cracked lenses were counted in whole units in three of the eleven "
        "lamp rooms.",
        "Lamps that were not recalled had their cracked lenses counted in "
        "whole units.")

    def test_the_conjunct_closes_the_one_the_question_misses(self):
        """The veto is ANDed onto the free path's licence, so a probe the
        question would keep is still refused if the vocabulary refuses it. That
        is why the shipped path closes 148 of 148 and the question alone 147."""
        acc, text = lamp_room(self.DOUBLE_NEGATIVE)
        for answers in (None, ALL_KEEP, ALL_WITHDRAW):
            rec = verification(evaluate(acc, text, answers=answers)["account"],
                               "var:clarity")
            assert rec["establishes_step_of_one"] is False

    @pytest.mark.parametrize("sentence", SUBSET_RESTRICTED)
    def test_the_two_honest_losses_were_already_losses(self, sentence):
        """Measured on the whole-number companion, where a licence buys real
        rows: the free path refuses these before any model is asked, so the
        question's withdrawal costs nothing the guards had not already cost."""
        acc, text = lamp_room(CHANNELS["attachment"], lens_sentence=sentence)
        rec = verification(evaluate(acc, text)["account"], "var:lenses")
        assert rec["establishes_step_of_one"] is False
