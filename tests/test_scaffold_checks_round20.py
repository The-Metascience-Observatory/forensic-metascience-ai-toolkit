"""ROUND 20 -- THE VARYING-n QUESTION HAD TWO ANCHORS, AND A PAPER FILLS THE WRONG ONE.

THE DEFECT, IN ONE SENTENCE: round 18 named the denominator in the TARGET and
then asked whether the quantity was computed over "FEWER subjects than that whole
group", which is a SECOND anchor the target does not fix -- and a paper states
item-level missingness against its ENROLMENT, so on an account that has already
bound the ANALYSED n the honest sentence reads as a violation.

    account binds 44, the roll is 47, the paper says `44 of the 47`
      -> fewer than the whole group (47)?   yes
      -> is 44 the wrong denominator?       NO -- it is the right one

MEASURED BEFORE ANYTHING WAS CHANGED, at `7f0e3c9`, sonnet, 2026-09-12, with the
honest arm asked ALONE: **7 of 7 honest phrasings across two fixtures answered
`true`**, withdrew `group_n`'s denominator and left each paper with no check at
all. Six reasoned in as many words "fewer than whole group"; the seventh said
"matching target's smaller subgroup" and answered `true` anyway -- the "names a
number of subjects ... that differs from the number in the target" clause firing
on the enrolment AFTER the model had already seen the match. Reworded, 7 of 7
answer `false` and the check runs.

THE TRUE POSITIVES WERE RE-MEASURED IN THE SAME ROUND AND DID NOT MOVE: **22 of
22**, which is round 18's own ten defect windows plus the eight mirror windows
this round adds. That second number is what makes this a fix rather than a
silencing -- a rewording that bought the honest arm by making the question never
fire would be a regression, and `TestTheTruePositivesSurvive` is where it would
show.

THE MIRROR WINDOWS ARE THIS ROUND'S ATTACK ON ITS OWN FIX, and they are why the
dominance clause is worded the way it is. The obvious repair -- "answer FALSE
when the target's number is in the passage" -- INVERTS the defect: `Copy clarity
data were missing for 3 of the 47 operators` asked at a target of 47 prints the
target's own number, and a `false` there restores GRIM `impossible` on a paper
whose arithmetic is exact at 44. So the question asks for the CONTRIBUTING number
and says in terms that a larger total, and a count of who was missing from it,
are not that number. All eight mirror windows answer `true`.

WHY ROUND 18 COULD NOT SEE ANY OF THIS, which is the methodological half and the
part worth carrying to the next premise. Its batch held the enrolled-target and
analysed-target readings of one passage side by side, and the contrast did the
disambiguation the question should have done: asked in that mixed batch the
shipped string answers all seven honest phrasings correctly (36 of 36, measured
the same day). Asked alone -- the shape a real run on one paper has -- it fails
seven for seven. A refusal premise's question is measured on ONE paper's
candidates from here on.

THE VERDICTS ARE REPLAYED, NOT RE-BOUGHT, which is round 15's rule. `recorded`
is what two real sonnet batches answered about the exact candidate sets
`adjudication_n.candidates` builds from these fixtures ($1.44 over seven batches,
two of them the before/after pair these tests pin).

ONE FIXTURE PAIR IS NOT A CORPUS. This measures whether the question separates
two populations a real paper genuinely produces. It says nothing about a real
paper's false-refusal rate.
"""

from __future__ import annotations

import statistics as st

import pytest

from metascience_agent.scaffold import (adjudication_n, checks,
                                        premise_reading as PR, premises)

from tests.test_scaffold_checks_round18 import (ANALYSED, BAD, ENROLLED, EVASIONS,
                                                ROLL, accusations, account, paper,
                                                reading, verdicts_for)

# --------------------------------------------------------------------------
# THE SEVEN HONEST PHRASINGS -- fixture A is round 18's paper, bound CORRECTLY
# --------------------------------------------------------------------------

#: The account binds the ANALYSED 44, which IS the denominator, and the paper
#: states its missingness against the roll of 47 -- the ordinary way a paper says
#: this. The premise does NOT hold and the check must run.
ASHGATE_HONEST = {
    # the shared case: round 18's own evasion, read at the analysed target
    "counts both": EVASIONS["44 of the 47"],
    # THE CASES ROUND 18's TARGET COULD NOT REACH: the analysed number is not
    # printed at all, so every number in the passage DIFFERS from the target and
    # the "names a number that differs" clause had nothing opposing it
    "missing 3 of 47":
        "Copy clarity data were missing for 3 of the 47 operators.",
    "three did not return":
        "Three of the 47 operators did not return a copy clarity card.",
    "all but three":
        "All but three of the 47 operators returned a usable copy clarity card.",
}

#: THE POLICY CONTROLS, AND THEY ARE EXPECTED `true`. A passage that says
#: subjects are missing without resolving how many leaves the denominator
#: genuinely unknown, and this premise's stated policy is that ambiguity resolves
#: toward the refusal. They are here so that a rewording cannot buy the honest
#: arm by making the question never fire.
ASHGATE_UNRESOLVED = {
    "missing three, no roll":
        "Copy clarity data were missing for three operators.",
    "only those who returned":
        "Copy clarity was scored only for those operators who returned a usable card.",
}

# --------------------------------------------------------------------------
# Fixture B -- a second paper, sharing no sentence, scale or number with the first
# --------------------------------------------------------------------------

#: Plot tidiness, scored 0-6 in WHOLE points, rated for 52 of the 58 plot
#: holders. HONEST BY CONSTRUCTION in the way round 18's paper is: 158 whole
#: points over 52 cards is exactly 3.04, and 3.04 is reachable from NO integer
#: total over 58 under either rounding convention -- so binding the enrolled 58
#: convicts a paper whose arithmetic is exact.
TIDY = [0] * 3 + [1] * 6 + [2] * 11 + [3] * 12 + [4] * 10 + [5] * 6 + [6] * 4
B_ANALYSED, B_ENROLLED = len(TIDY), 58
B_MEAN, B_SD = f"{st.fmean(TIDY):.2f}", f"{st.stdev(TIDY):.2f}"

assert (B_ANALYSED, sum(TIDY), B_MEAN) == (52, 158, "3.04")
assert any(round(k / B_ANALYSED, 2) == float(B_MEAN)
           for k in range(B_ANALYSED * 6 + 1))
assert not any(round(k / B_ENROLLED, 2) == float(B_MEAN)
               for k in range(B_ENROLLED * 6 + 1))

B_ROLL = "Cards were sent to 58 plot holders on the Brantwood allotment register."
B_GRANT = ("Plot tidiness was rated in whole points on a 0 to 6 card for every "
           "plot holder.")

BRANTWOOD_HONEST = {
    "rated for 52 of 58": "Plot tidiness was rated for 52 of the 58 plot holders.",
    "6 did not return":
        "Tidiness cards were not returned by 6 of the 58 plot holders.",
    "six of 58 did not":
        "Six of the 58 plot holders did not return a tidiness card.",
}

BRANTWOOD_UNRESOLVED = {
    "some did not": "Some plot holders did not return a tidiness card.",
}


def b_cell(vid, statistic, printed, *, col=1, col_label="Mean (SD)"):
    lit = premises.read_plain(printed) or {}
    return {"id": vid, "statistic": statistic, "printed": printed,
            "numeric": lit.get("value"), "decimals": lit.get("decimals", 0),
            "printed_form": "plain", "units": None, "variable_id": "var:tidiness",
            "id_check": "agrees", "statistic_disputed": False, "source": "table",
            "quote": None, "quote_verified": "cell", "printed_in_quote": None,
            "location": {"kind": "table_cell", "table_id": "table:1", "row": 1,
                         "col": col, "col_label": col_label},
            "coordinate": {"study_id": "study:brantwood",
                           "group_id": "grp:holders", "phase_id": None}}


def brantwood(group_n=B_ANALYSED):
    return {"paper": {"doi": "10.0000/brantwood",
                      "title": "The Brantwood allotment tidiness survey"},
            "studies": [{"id": "study:brantwood", "design": "prospective_cohort",
                         "groups": [{"id": "grp:holders", "label": "All plot holders",
                                     "n": group_n, "n_source": "text"}]}],
            "variables": [{"id": "var:tidiness", "name": "Plot tidiness",
                           "label": "Plot tidiness", "printed_as": [],
                           "kind": "ordinal", "role": None, "units": None,
                           "units_source": "not_stated", "derivation": None,
                           "derived_from": [],
                           "bounds": {"source": "stated", "lower": 0, "upper": 6,
                                      "quote": B_GRANT},
                           "granularity": {"per_subject_step": 1, "quote": B_GRANT}}],
            "values": [b_cell("val:bmean", "mean", B_MEAN),
                       b_cell("val:bsd", "sd", B_SD, col=2),
                       b_cell("val:bn", "n", str(group_n), col=3, col_label="n")],
            "document": {"tables": [
                {"id": "table:1",
                 "caption": "Table 1. Plot tidiness, Brantwood allotment register.",
                 "footnotes": []}]}}


def b_paper(*sentences):
    return " ".join(("## Methods", B_ROLL, B_GRANT) + sentences)


# --------------------------------------------------------------------------
# The arms, and the recorded replies
# --------------------------------------------------------------------------


def honest_arms():
    """`(label, sentence, account binding the ANALYSED n, served text, variable)`."""
    out = []
    for label, s in sorted(ASHGATE_HONEST.items()):
        out.append((f"A/{label}", s, account(group_n=ANALYSED), paper(s), "var:clarity"))
    for label, s in sorted(BRANTWOOD_HONEST.items()):
        out.append((f"B/{label}", s, brantwood(), b_paper(s), "var:tidiness"))
    return out


def mirror_arms():
    """THE MIRROR OF EVERY HONEST PHRASING, on the account that binds the ENROLLED
    n. The same sentence in the same served text, a different declared
    denominator -- and now the premise DOES hold, because the quantity really is
    over fewer subjects than the account divides by."""
    out = []
    for label, s in sorted(ASHGATE_HONEST.items()):
        out.append((f"A/{label}@{ENROLLED}", s, account(), paper(s), "var:clarity"))
    for label, s in sorted(BRANTWOOD_HONEST.items()):
        out.append((f"B/{label}@{B_ENROLLED}", s, brantwood(group_n=B_ENROLLED),
                    b_paper(s), "var:tidiness"))
    return out


def unresolved_arms():
    out = []
    for label, s in sorted(ASHGATE_UNRESOLVED.items()):
        out.append((f"A/{label}", s, account(group_n=ANALYSED), paper(s), "var:clarity"))
    for label, s in sorted(BRANTWOOD_UNRESOLVED.items()):
        out.append((f"B/{label}", s, brantwood(), b_paper(s), "var:tidiness"))
    return out


def target_n(c: dict) -> int:
    """The number the TARGET names, read off the candidate rather than passed in:
    `_target` is what the model was shown, so the replay addresses what the batch
    addressed."""
    return int(str(c["target"]).split("over the ")[-1].split()[0])


def recorded(c: dict) -> bool:
    """What the 2026-09-12 sonnet batches answered about this candidate.

    THE ADDRESS IS (what the window carries, what the target names), which is
    this round's own result rather than bookkeeping: every sentence below was
    asked at BOTH denominators and answered differently, so a replay keyed on the
    passage alone would be addressing a question that was never put.

    `missing three, no roll` IS THE ONE SPLIT, recorded rather than smoothed
    because it is the clearest evidence the model reads the WINDOW and not the
    sentence. The window that also carries the roll ("... from 47 operators ...
    missing for three operators") resolves to 44, which is the target, and came
    back `false`; the window without it came back `true`, reason "No total pool
    stated here, so missing-three count can't confirm". Both are right, and the
    arm is refused either way, because one `true` is enough.
    """
    n, q = target_n(c), c["quote"]
    for s in list(ASHGATE_HONEST.values()) + list(BRANTWOOD_HONEST.values()):
        if s in q:
            return n in (ENROLLED, B_ENROLLED)
    for s in list(ASHGATE_UNRESOLVED.values()) + list(BRANTWOOD_UNRESOLVED.values()):
        if s in q:
            return ROLL not in q and B_ROLL not in q
    for s in EVASIONS.values():
        if s in q:
            return n == ENROLLED
    return False


def cands(acc, text, variable_id):
    return [c for c in adjudication_n.candidates(acc, text)
            if c["variable_id"] == variable_id]


def read_back(acc, text, cs, establishes=recorded):
    return checks.evaluate(
        dict(acc, premise_reading=reading(*verdicts_for(cs, establishes, "recorded"),
                                          candidates=cs)), text)


# --------------------------------------------------------------------------
# THE FIXTURES MUST BE WHAT THEY CLAIM TO BE
# --------------------------------------------------------------------------


@pytest.mark.parametrize("label,sentence,acc,text,vid", honest_arms())
def test_the_honest_paper_is_checkable_and_clean_before_any_reading(
        label, sentence, acc, text, vid):
    """THE HONEST ARM'S WHOLE POINT IS THE CHECK THAT RUNS. At the analysed n the
    arithmetic is exact, so the free path already checks the mean and clears it.
    What round 18's question did was take that check away."""
    got = checks.evaluate(acc, text)
    assert got["n_run"] >= 1, label
    assert accusations(got) == [], label


@pytest.mark.parametrize("label,sentence,acc,text,vid", mirror_arms())
def test_the_mirror_paper_really_is_accused_before_any_reading(
        label, sentence, acc, text, vid):
    """AND THE MIRROR ARM'S WHOLE POINT IS THE ACCUSATION THAT STANDS. Same
    sentence, same text, the enrolled n bound instead -- GRIM returns
    `impossible` on a paper whose arithmetic is exact. A `false` here is a live
    false accusation, which is why the dominance clause may not be read as "the
    target's number appears in the passage"."""
    got = checks.evaluate(acc, text)
    assert {s for _, s in accusations(got)} == {"impossible"}, label


def test_every_honest_phrasing_evades_the_vocabulary_too():
    """THE FREE PATH CANNOT RESCUE ANY OF THESE EITHER, which is what makes the
    model reading the thing under test rather than a fallback."""
    for label, sentence, acc, text, vid in honest_arms() + mirror_arms():
        assert not premises._N_VARIES.search(sentence), label
        assert premises.varying_n_statement(text) is None, label


# --------------------------------------------------------------------------
# THE DEFECT, AND THE FIX -- the honest arm
# --------------------------------------------------------------------------


@pytest.mark.parametrize("label,sentence,acc,text,vid", honest_arms())
def test_no_honest_phrasing_withdraws_the_denominator(label, sentence, acc, text, vid):
    """THE SEVEN. Every window the net builds for an honest paper came back
    `false` under the reworded question, so the check the paper is entitled to
    still runs and the run is exactly what it was with no reading at all.

    Under round 18's string all seven answered `true` here and `n_run` fell to
    zero."""
    cs = cands(acc, text, vid)
    assert cs, label
    assert any(sentence in c["quote"] for c in cs), label
    assert not any(recorded(c) for c in cs), label
    got = read_back(acc, text, cs)
    assert got == checks.evaluate(acc, text), label
    assert got["n_run"] >= 1, label


def test_the_seven_are_seven_distinct_phrasings_over_two_fixtures():
    """The count in the docstrings is a claim about the fixture, so it is
    asserted rather than written down: seven phrasings, two papers, and the
    analysed number is ABSENT from the passage in five of them -- which is the
    case round 18's target-naming could not reach."""
    arms = honest_arms()
    assert len(arms) == 7
    assert len({vid for *_, vid in arms}) == 2
    absent = [s for _, s, _, _, _ in arms
              if str(ANALYSED) not in s and str(B_ANALYSED) not in s]
    assert len(absent) == 5, absent


@pytest.mark.parametrize("label,sentence,acc,text,vid", unresolved_arms())
def test_unresolved_missingness_still_refuses(label, sentence, acc, text, vid):
    """AMBIGUITY STILL RESOLVES TOWARD THE REFUSAL, and this is the half that
    stops the fix being a silencing of the question. A passage that says subjects
    are missing without resolving how many leaves the denominator unknown, so at
    least one window answers `true` and the check is withdrawn."""
    cs = cands(acc, text, vid)
    assert cs, label
    assert any(recorded(c) for c in cs), label
    assert read_back(acc, text, cs)["n_run"] == 0, label


def test_the_one_window_split_is_recorded_rather_than_smoothed():
    """`Copy clarity data were missing for three operators` was answered BOTH
    ways in one batch, by window: `false` where the window also carries the roll
    (47 less three is the target's 44), `true` where it does not. That is the
    model reading the window it was given, and the arm is refused either way."""
    sentence = ASHGATE_UNRESOLVED["missing three, no roll"]
    acc, text = account(group_n=ANALYSED), paper(sentence)
    cs = [c for c in cands(acc, text, "var:clarity") if sentence in c["quote"]]
    assert len(cs) == 2
    assert {recorded(c) for c in cs} == {True, False}
    assert not recorded(next(c for c in cs if ROLL in c["quote"]))


# --------------------------------------------------------------------------
# THE HALF THAT DECIDES WHETHER THE FIX IS A FIX -- the true positives
# --------------------------------------------------------------------------


class TestTheTruePositivesSurvive:
    """A REWORDING THAT BOUGHT THE HONEST ARM BY MAKING THE QUESTION NEVER FIRE
    WOULD BE A REGRESSION, NOT A FIX. 22 of 22 true positives held under the new
    string, and these are they."""

    @pytest.mark.parametrize("label", sorted(EVASIONS))
    def test_round_18s_defect_windows_still_withdraw_the_denominator(self, label):
        """ROUND 18's TEN, RE-MEASURED UNDER THE NEW QUESTION AND UNMOVED. Its
        own `RECORDED_TRUE` therefore still describes what a model answers, so
        nothing in `test_scaffold_checks_round18.py` is now a replay of a reply
        the shipped prompt would no longer get."""
        text, acc = paper(EVASIONS[label]), account()
        cs = cands(acc, text, "var:clarity")
        assert accusations(checks.evaluate(acc, text)), "the fixture must convict"
        assert any(recorded(c) and EVASIONS[label] in c["quote"] for c in cs)
        assert accusations(read_back(acc, text, cs)) == []

    @pytest.mark.parametrize("label,sentence,acc,text,vid", mirror_arms())
    def test_every_mirror_window_still_withdraws_the_denominator(
            self, label, sentence, acc, text, vid):
        """THE EIGHT THIS ROUND ADDS, and the attack on its own fix. The target's
        number is PRINTED in the passage -- `missing for 3 of the 47` asked at 47
        -- so a dominance clause read as "the target's number appears" would
        answer `false` here and leave the accusation standing."""
        cs = cands(acc, text, vid)
        assert any(recorded(c) and sentence in c["quote"] for c in cs), label
        assert accusations(read_back(acc, text, cs)) == [], label

    def test_the_same_passage_answers_both_ways_at_the_two_denominators(self):
        """THE PAIRED DESIGN, AS ONE ASSERTION. Every honest phrasing and its
        mirror are the SAME sentence in the SAME served text and produce the SAME
        candidate quotes; only the account's declared n differs, and the recorded
        verdicts differ with it. If any passage answered the same way at both,
        this round would have measured nothing."""
        for (hl, hs, ha, ht, hv), (ml, ms, ma, mt, mv) in zip(honest_arms(),
                                                              mirror_arms()):
            assert (hs, ht) == (ms, mt)
            assert {c["quote"] for c in cands(ha, ht, hv)} == {
                c["quote"] for c in cands(ma, mt, mv)}, hl
            assert not any(recorded(c) for c in cands(ha, ht, hv)), hl
            assert any(recorded(c) for c in cands(ma, mt, mv)), ml


# --------------------------------------------------------------------------
# THE SELF-ATTACK -- the cases the FIX itself could have broken
# --------------------------------------------------------------------------

#: THE THREE CLAUSES THIS ROUND ADDED THAT PUSH TOWARD `false`, AND THE CASE
#: THAT EXPOSES EACH. A `false` where `true` is right is the only direction this
#: premise can buy an accusation, so each clause was asked the question that
#: would catch it, under BOTH wordings, in one batch each.
#:
#:   X1/X2  "FALSE where the passage plainly says the measure was taken for ...
#:          every subject and names no smaller contributing number" -- asked of
#:          a paper that says EVERYONE was measured on an account that has bound
#:          a SMALLER n. The target is wrong in the other direction and the
#:          honest answer is `true`.
#:   X3     "it stays FALSE when the passage also names a larger total" -- asked
#:          of a passage naming THREE numbers, with the target equal to none.
#:   X4     a target equal to no number in the passage at all.
#:   X5     the honest control for X3: the same passage, target equal to the
#:          contributing count.
#:
#: MEASURED both ways, sonnet, 2026-09-12, one batch each ($0.305 old, $0.116
#: new): **round 18's wording scores 4 of 7 arms and this one scores 7 of 7.**
#: Every attack case is better or equal and none is worse.
#:
#: AND X1/X2 ARE A SECOND, INHERITED FALSE-ACCUSATION CHANNEL, found while
#: attacking this fix rather than while looking for it. Under round 18's string
#: BOTH windows of each answered `false` -- "plainly states full participation"
#: -- so a paper saying every subject was measured could not withdraw a
#: denominator smaller than its own roll. The clause shape that does it is round
#: 18's ("the whole group contributed"), so this is not a defect this round
#: introduced; it is one the rewording happens to close, and it is recorded so
#: nobody re-measures it.
ATTACK_EVERY_47 = "Copy clarity was scored for every one of the 47 operators."
ATTACK_EVERY = "Every operator on the roll was scored for copy clarity."
ATTACK_APPROACHED = ("Of the 50 operators approached, 44 returned a usable copy "
                     "clarity card.")


def recorded_attack(c: dict) -> bool:
    """What the 2026-09-12 attack batch answered, under the shipped wording.

    `X2` SPLITS BY WINDOW exactly as `missing three, no roll` does, and for the
    same reason: `Every operator on the roll was scored` names no number, so the
    window that also carries the roll resolves it to 47 and answers `true`, and
    the window without it cannot and answers `false` ("no specific number given
    to contradict"). One `true` is enough, so the arm is refused either way --
    which under round 18's wording it was not, because both windows were `false`.
    """
    n, q = target_n(c), c["quote"]
    if ATTACK_EVERY_47 in q:
        return True
    if ATTACK_EVERY in q:
        return ROLL in q
    if ATTACK_APPROACHED in q:
        return n != ANALYSED
    if EVASIONS["44 of the 47"] in q:
        return n != ANALYSED
    return False


class TestTheSelfAttack:
    """Each clause of the new wording that can push toward `false`, asked the
    question that would expose it."""

    @pytest.mark.parametrize("label,sentence,group_n", [
        ("X1 every-47", ATTACK_EVERY_47, ANALYSED),
        ("X2 every", ATTACK_EVERY, ANALYSED),
    ])
    def test_a_paper_saying_everyone_still_withdraws_a_smaller_bound_n(
            self, label, sentence, group_n):
        """THE `every subject` CLAUSE DOES NOT SWALLOW THE OTHER DIRECTION. The
        account has bound 44 and the paper says all 47 were measured, so 44 is
        the wrong denominator and at least one window has to say so. Under round
        18's string every window of both arms answered `false`."""
        acc, text = account(group_n=group_n), paper(sentence)
        cs = cands(acc, text, "var:clarity")
        assert cs, label
        assert any(recorded_attack(c) and sentence in c["quote"] for c in cs), label
        assert read_back(acc, text, cs, recorded_attack)["n_run"] == 0, label

    def test_three_numbers_with_the_target_equal_to_none_still_withdraws(self):
        """THE DOMINANCE CLAUSE IS NOT OVER-APPLIED. `Of the 50 operators
        approached, 44 returned a usable card` at a target of 47 names a larger
        total AND a contributing count, and the target is neither -- so the
        contributing number is not the target's and the accusation must go."""
        acc, text = account(), paper(ATTACK_APPROACHED)
        cs = cands(acc, text, "var:clarity")
        assert accusations(checks.evaluate(acc, text)), "the fixture must convict"
        assert any(recorded_attack(c) for c in cs)
        assert accusations(read_back(acc, text, cs, recorded_attack)) == []

    def test_the_same_three_number_passage_is_honest_at_its_own_count(self):
        """AND THE CONTROL FOR IT. The same passage at a target of 44 -- the
        count it actually names for this quantity -- withdraws nothing, even
        though it also prints a larger total of 50. Round 18's string answered
        `true` here."""
        acc, text = account(group_n=ANALYSED), paper(ATTACK_APPROACHED)
        cs = cands(acc, text, "var:clarity")
        assert cs
        assert not any(recorded_attack(c) for c in cs)
        got = read_back(acc, text, cs, recorded_attack)
        assert got == checks.evaluate(acc, text)
        assert got["n_run"] >= 1

    def test_a_target_matching_no_number_in_the_passage_still_withdraws(self):
        """A denominator the paper never mentions is not the contributing number
        either, and `44 of the 47` at a target of 40 says so."""
        acc, text = account(group_n=40), paper(EVASIONS["44 of the 47"])
        cs = cands(acc, text, "var:clarity")
        assert cs
        assert any(recorded_attack(c) for c in cs)
        assert read_back(acc, text, cs, recorded_attack)["n_run"] == 0


# --------------------------------------------------------------------------
# THE QUESTION ITSELF
# --------------------------------------------------------------------------


def test_the_question_has_one_anchor_and_it_is_the_target():
    """THE DEFECT WAS A SECOND ANCHOR, so what is pinned is its absence. "that
    whole group" is gone, and so is the clause that answered `true` on any number
    in the passage differing from the target -- the one caught firing after the
    model had already seen the match."""
    q = PR.QUESTIONS["varying_n"]
    assert "that whole group" not in q
    assert "names a number of subjects for this quantity that differs" not in q
    assert "the number of subjects stated in the target above" in q


def test_the_question_decides_the_two_number_case_and_does_not_invert_it():
    """BOTH HALVES OF THE DOMINANCE, because only one of them is safe alone. The
    FALSE clause has to survive a larger total being printed beside the
    contributing number; and it has to be scoped to the CONTRIBUTING number, or
    it fires on the mirror windows where the target's own number is the roll."""
    q = PR.QUESTIONS["varying_n"]
    assert "it stays FALSE when the passage also names a larger total" in q
    assert "never the larger total and never the count of who was missing" in q


def test_ambiguity_still_resolves_toward_the_refusal():
    """The clause that keeps an unresolved missingness statement a `true`. It
    lives in the question because `PREAMBLE` is shared with the licence premises,
    whose instinct is the opposite."""
    assert "leaves the contributing number unclear" in PR.QUESTIONS["varying_n"]


def test_no_number_may_be_reported_out_of_this_path():
    """RULE 3 of `adjudication_n`, still stated in the question. What changed is
    that it is now about what the model may REPORT: round 18's "do not supply,
    infer or calculate a number" also forbade the plain reading that three
    missing from forty-seven leaves the target's forty-four, which is the reading
    the honest case needs."""
    assert "Do not propose or report a denominator" in PR.QUESTIONS["varying_n"]


def test_no_other_question_moved():
    """The five other premises carry measurements of their own -- E1's 37/37,
    round 16's averaging re-measurement, round 17's 74-of-74 parity -- and a
    rewording that quietly touched one would invalidate them with nothing
    failing."""
    assert PR.QUESTIONS["bound"].startswith("Does this sentence state the numeric range")
    assert PR.QUESTIONS["step"].startswith("Does this sentence establish that each subject's")
    assert PR.QUESTIONS["correction"].startswith("Does this correction notice say")
    assert PR.QUESTIONS["estimator"].startswith("Does this sentence, caption or column heading")
    assert PR.QUESTIONS["averaging"].startswith(
        "The check this premise gates can only run if")


def test_the_prompt_version_moved_with_the_question():
    """A run read back against a different question set is a run of a different
    instrument, and this one is not round 18's.

    WHAT IS PINNED IS THE PROPERTY, NOT THE LITERAL. This assertion was the THIRD
    hand-written copy of `PROMPT_VERSION`'s exact value, so round 24 -- which
    added a seventh question and touched none of the six -- had to edit three
    files to say one thing. That is the duplicate-constant shape this repo keeps
    paying for, one level up. Round 20's actual claim is that the constant is no
    longer the one its own measurement falsified, and that `varying_n`'s string
    is the reworded one; the exact value belongs in ONE place, which is
    `test_scaffold_checks_round16`."""
    assert PR.PROMPT_VERSION not in ("e1-target-bounds/2026-09-09",
                                     "e1-varying-n/2026-09-12")
    assert "the one left contributing to this quantity" in PR.QUESTIONS["varying_n"]


# --------------------------------------------------------------------------
# THE POLARITY IS UNCHANGED -- asserted on this round's own fixtures
# --------------------------------------------------------------------------


def test_forced_false_is_byte_identical_to_no_reading_at_all():
    """A REFUSAL PREMISE'S `false` MAY NEVER REMOVE A REFUSAL THE VOCABULARY
    MADE. Round 18 pins this on its own fixtures; a new fixture is new surface,
    and this round's whole argument is that `false` is the RIGHT answer on an
    honest paper -- so what a `false` may do has to be pinned here too."""
    for label, sentence, acc, text, vid in honest_arms() + mirror_arms():
        cs = adjudication_n.candidates(acc, text)
        assert read_back(acc, text, cs, lambda c: False) == checks.evaluate(acc, text), \
            label


def test_forced_true_may_only_lower_the_run_and_never_change_a_denominator():
    """MUTATION CONTROL, THE OTHER DIRECTION. Every verdict forced `true`: the
    number of checks that run may only FALL, no check may gain a worse severity,
    and every check still running must carry the `n` it carried with no reading
    at all."""
    for label, sentence, acc, text, vid in honest_arms() + mirror_arms():
        base = checks.evaluate(acc, text)
        cs = adjudication_n.candidates(acc, text)
        got = read_back(acc, text, cs, lambda c: True)
        assert got["n_run"] <= base["n_run"], label
        assert not (set(got["by_severity"]) & BAD) - (set(base["by_severity"]) & BAD)
        ns = {r["check_id"]: r["args"].get("n") for r in base["checks"]}
        for r in got["checks"]:
            assert r["args"].get("n") == ns[r["check_id"]], (label, r["check_id"])


def test_the_refusal_still_names_the_papers_own_words():
    """What reaches a docket is the CANDIDATE'S QUOTE, a span this pipeline
    supplied, and never the model's prose -- unchanged by the rewording, and
    asserted here because this round's fixtures are new."""
    label, sentence, acc, text, vid = mirror_arms()[0]
    cs = cands(acc, text, vid)
    moved = premises.stamp(
        dict(acc, premise_reading=reading(*verdicts_for(cs, recorded, "recorded"),
                                          candidates=cs)), text)
    supplied = {c["quote"] for c in cs}
    varies = [str((v.get("premise") or {}).get("analysis_n_varies") or "")
              for v in moved["values"]]
    assert any(varies)
    for got in varies:
        if got:
            assert got in supplied
