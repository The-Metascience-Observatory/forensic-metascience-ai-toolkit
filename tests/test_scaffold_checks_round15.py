"""ROUND 15 -- WAVE 7E'S BOUNDED-ADJUDICATION PROTOTYPE, pinned against the
defect classes that motivated it.

THE SPEC'S HYPOTHESIS, WHICH THIS FILE IS THE TEST OF: every averaging defect
that reached a false accusation in rounds 4, 9, 10, 11, 13 and 14 was a RECALL
failure, not a JUDGEMENT failure. Round 14's D2 measured the other half -- where
recall DID reach the sentence, a real paid reading withdrew the premise cleanly.
So `scaffold/adjudication.py` narrows the vocabulary's job to RELEVANCE (is this
passage about how this variable's value was arrived at?) and hands the
establish/withdraw question to the model for everything relevance surfaced.

WHAT IS PINNED HERE, and every case is a BEFORE/AFTER pair rather than a claim
about the new path alone:

  * D1 (round 14) -- six honest, ordinary ways of saying a reported figure is
    the mean of three judges' cards that match NEITHER `premises.AVERAGED` nor
    `premise_reading._AVERAGING_CANDIDATE`. The log preserved the specification
    and not the sentences (the probe's own fixtures were wiped with /tmp), so
    these six are regenerated to it and each is asserted to evade both regexes
    -- the assertion is what makes them the same experiment.
  * F9 (round 3) / F2 (round 4) -- the granting and withdrawing facts SPLIT
    ACROSS TWO SENTENCES, which defeated the paid path too: no single sentence
    establishes the premise, so a per-sentence candidate is judged `false`
    correctly and the paper is convicted anyway.
  * F3 (round 4) -- the statement sitting in a TABLE FOOTNOTE.
  * E1's no-regression half: the honest controls the old path correctly leaves
    alone stay untouched, and the new path manufactures NO new accusation.
  * E4: the LICENCE side (`bound`, `step`) is byte-identical before and after,
    because `adjudication.candidates` emits `averaging` rows and nothing else.

THE MODEL VERDICTS ARE REPLAYED FROM A RECORDED RUN, not called for at test
time. `RECORDED` is what a real sonnet batch answered about the exact candidate
set `adjudication.candidates` builds from these fixtures -- 28 candidates in one
call at $0.473429 plus 4 in a second at $0.337954, 2026-09-11, sonnet,
`premise_reading.PROMPT_VERSION` unchanged. A test may not spend money; what it
can do is pin that the WIRING carries a recorded verdict to the place it has to
reach, and pin stage 1 -- which is free, deterministic, and the half the spec's
hypothesis is actually about.

THE MEASUREMENT, STATED SO IT CAN BE ARGUED WITH: 32 of 32 adjudications were
correct. Every one of the eight defect passages was judged `true`; every one of
the twelve honest passages -- including three whose WINDOW carries a NEIGHBOUR
sentence that really does describe an average, of another variable or of the
group -- was judged `false`. Across this fixture the spec's hypothesis holds:
the failures were recall, and where recall reached the model, judgement was not
the bottleneck. One fixture is not a corpus, and this file says nothing about
what a real paper's rate is.
"""

from __future__ import annotations

import statistics as st

import pytest

from forensic_metascience_ai_toolkit.scaffold import (adjudication, checks,
                                        premise_reading as PR, premises)

BAD = {"suspicious", "highly_suspicious", "impossible"}


# --------------------------------------------------------------------------
# The Marchfield brass-band adjudication survey -- round 15's own fixture paper
# (shares nothing with rounds 1-14)
# --------------------------------------------------------------------------

#: Tone, scored 0-30 in WHOLE points by EACH of THREE judges. The figure the
#: paper reports is the mean of the three cards, so an entrant's own value moves
#: in THIRDS of a point: this is the quantity the averaging veto must withdraw a
#: step of 1 from. THREE cards rather than two deliberately -- a half-point index
#: is round 10-12's shape, and a third-point one is not reachable by any of the
#: pair-specific branches `AVERAGED` has accumulated.
CARD_A = [4, 18, 27, 25, 24, 2, 8, 3, 15, 24, 14, 15, 20, 12, 25,
          6, 3, 15, 0, 28, 26, 12, 13, 19, 24, 24, 0, 22, 14, 8]
CARD_B = [23, 25, 7, 18, 30, 3, 28, 10, 0, 0, 0, 20, 17, 0, 30,
          28, 12, 21, 6, 13, 23, 0, 16, 7, 24, 14, 30, 15, 17, 7]
CARD_C = [11, 7, 21, 7, 24, 14, 30, 9, 29, 0, 13, 26, 29, 17, 29,
          20, 3, 5, 20, 23, 27, 9, 3, 23, 10, 28, 23, 22, 16, 29]
TONE = [(a + b + c) / 3 for a, b, c in zip(CARD_A, CARD_B, CARD_C)]
N = len(TONE)
TONE_MEAN = f"{st.fmean(TONE):.2f}"
TONE_SD = f"{st.stdev(TONE):.2f}"

#: THE FIXTURE PAPER IS HONEST BY CONSTRUCTION. Entrants' own values fall on
#: thirds, and the mean they produce is reachable from NO integer total over 30
#: under either rounding convention -- so a wrongly granted step of 1 convicts a
#: paper whose arithmetic is exact.
assert sorted({round(x % 1, 4) for x in TONE}) == [0.0, 0.3333, 0.6667]
assert not any(round(k / N, 2) == float(TONE_MEAN) for k in range(N * 30 + 1))


# --------------------------------------------------------------------------
# D1 -- SIX EVASIONS OF THE CLOSED VOCABULARY (round 14, regenerated to spec)
# --------------------------------------------------------------------------

#: The sentence that GRANTS the step. Ordinary, honest, and true: each judge's
#: card really is a whole number.
#: ROUND 26 REMOVED `by each of three judges` FROM THE GRANTING SENTENCE, and
#: the fixture is better for it: the paper still says three judges in every
#: EVASION below, which is where round 15 wants the withdrawal to live. With the
#: cardinal in the granting sentence this fixture had TWO independent reasons to
#: refuse and only one of them was ever under test.
GRANT = "Tone was scored in whole points on a 0 to 30 card."

#: The sentence that WITHDRAWS it, six ways, none of which contains a word
#: either vocabulary carries. Two name the variable outright and four are
#: anaphoric, which is the mix an ordinary Methods paragraph produces.
EVASIONS = {
    "the central value":
        "Each entrant's tone score is the central value of the three judges' cards.",
    "reconciled into a single rating":
        "The three judges' cards for each entrant were reconciled into a single rating.",
    "what they come to on balance":
        "Each entrant's tone score is what the three judges' cards come to on balance.",
    "the arithmetic middle":
        "The reported tone score is the arithmetic middle of the three cards.",
    "levelled out":
        "The three cards recorded for an entrant were levelled out to give the "
        "reported tone score.",
    "the consensus":
        "The reported tone score is the consensus of the three judges' cards.",
}


@pytest.mark.parametrize("label", sorted(EVASIONS))
def test_every_round_14_evasion_really_does_evade_both_vocabularies(label):
    """THE ASSERTION THAT MAKES THESE THE SAME EXPERIMENT. The log preserved
    D1's specification and not its sentences; a regenerated sentence that the
    vocabulary happens to catch would be testing nothing, and the failure would
    look exactly like a pass."""
    sentence = EVASIONS[label]
    assert not premises.AVERAGED.search(sentence)
    assert not PR._AVERAGING_CANDIDATE.search(sentence)


# --------------------------------------------------------------------------
# F9 / F2 -- THE FACT SPLIT ACROSS TWO SENTENCES
# --------------------------------------------------------------------------

#: NEITHER SENTENCE ESTABLISHES THE PREMISE ON ITS OWN, which is why a paid
#: reading judged per-sentence answers `false` to both and is right to. The
#: first says three judges sat; the second says what was done with their cards
#: and names no quantity at all. Read together they are unambiguous.
SPLIT_FIRST = "Three judges sat at every heat and each returned a card."
SPLIT_SECOND = "The tone score printed below rests on all three of them equally."

#: F3's channel: the same fact, in the table's own footnote.
FOOTNOTE = "Tone scores rest equally on all three judges' cards."


# --------------------------------------------------------------------------
# The account
# --------------------------------------------------------------------------


def var(vid, name, kind, *, bsource="not_stated", lower=None, upper=None,
        bquote=None, step=None, gquote=None, derivation=None):
    return {"id": vid, "name": name, "label": name, "printed_as": [],
            "kind": kind, "role": None, "units": None,
            "units_source": "not_stated", "derivation": derivation,
            "derived_from": [],
            "bounds": {"source": bsource, "lower": lower, "upper": upper,
                       "quote": bquote},
            "granularity": {"per_subject_step": step, "quote": gquote}}


def _lit(printed):
    return premises.read_plain(printed) or {}


def cell(vid, statistic, printed, *, variable_id=None, col_label="Mean (SD)",
         row=1, col=1, table="table:1"):
    lit = _lit(printed)
    return {"id": vid, "statistic": statistic, "printed": printed,
            "numeric": lit.get("value"), "decimals": lit.get("decimals", 0),
            "printed_form": "percent" if lit.get("is_percent") else "plain",
            "units": None, "variable_id": variable_id, "id_check": "agrees",
            "statistic_disputed": False, "source": "table", "quote": None,
            "quote_verified": "cell", "printed_in_quote": None,
            "location": {"kind": "table_cell", "table_id": table, "row": row,
                         "col": col, "col_label": col_label},
            "coordinate": {"study_id": "study:march", "group_id": "grp:entrants",
                           "phase_id": None}}


def account(*, variables=(), values=(), footnotes=()):
    tables = [{"id": "table:1",
               "caption": "Table 1. Entrant-level scores, Marchfield brass-band survey.",
               "footnotes": [str(f) for f in footnotes]}]
    return {"paper": {"doi": "10.0000/marchfield",
                      "title": "The Marchfield brass-band adjudication survey"},
            "studies": [{"id": "study:march", "design": "prospective_cohort",
                         "groups": [{"id": "grp:entrants", "label": "All entrants",
                                     "n": N, "n_source": "text"}]}],
            "variables": list(variables), "values": list(values),
            "document": {"tables": tables}}


def tone_account(*, footnotes=()):
    return account(
        variables=[var("var:tone", "Tone score", "ordinal", bsource="stated",
                       lower=0, upper=30, bquote=GRANT, step=1, gquote=GRANT),
                   var("var:tempo", "Tempo accuracy", "ordinal",
                       bsource="not_stated", step=1,
                       gquote="Tempo accuracy was logged in whole points.")],
        values=[cell("val:mean", "mean", TONE_MEAN, variable_id="var:tone"),
                cell("val:sd", "sd", TONE_SD, variable_id="var:tone", col=2),
                cell("val:n", "n", str(N), variable_id="var:tone", col=3,
                     col_label="n")],
        footnotes=footnotes)


def paper(*sentences):
    """The served text: the granting sentence, then whatever the case adds."""
    return " ".join(("## Methods", GRANT) + sentences)


def accusations(got):
    return sorted({(r["check_id"], r["severity"]) for r in got["checks"]
                   if r["severity"] in BAD})


def averaging_candidates(acc, text, variable_id="var:tone"):
    return [c for c in adjudication.candidates(acc, text)
            if c["variable_id"] == variable_id]


def old_path_candidates(acc, text, variable_id="var:tone"):
    return [c for c in PR.candidates(acc, text)
            if c["premise"] == "averaging" and c["variable_id"] == variable_id]


def reading(*verdicts, candidates=()):
    cands = list(candidates)
    return {"schema": PR.SCHEMA_VERSION, "prompt_version": PR.PROMPT_VERSION,
            "model": "sonnet", "n_candidates": len(cands), "n_asked": len(cands),
            "n_dropped": 0, "candidates": cands, "verdicts": list(verdicts),
            "problems": [], "cost_usd": 0.0, "n_calls": 1}


#: WHAT THE PAID BATCH ANSWERED `true` ON, exhaustively: the eight defect
#: passages and nothing else. Every other candidate of the run -- the granting
#: sentence alone, the table caption, each honest control, and each window
#: carrying a contaminating neighbour -- came back `false`. Written as the
#: passages rather than as candidate ids because a candidate id is an artefact
#: of the ordering and the passage is the thing that was judged.
RECORDED_TRUE = tuple(EVASIONS.values()) + (SPLIT_SECOND, FOOTNOTE)


def recorded(c):
    """The 2026-09-11 sonnet batch's answer about this candidate."""
    return any(s in c["quote"] for s in RECORDED_TRUE)


def verdicts_for(cands, establishes):
    """A recorded reply, replayed: one verdict per candidate."""
    return [{"candidate_id": c["id"], "premise": "averaging",
             "establishes": bool(establishes(c)), "reason": "recorded",
             "model": "sonnet", "prompt_version": PR.PROMPT_VERSION}
            for c in cands]


# --------------------------------------------------------------------------
# E2 -- EACH DEFECT FAILS UNDER THE OLD PATH AND RESOLVES UNDER THE NEW ONE
# --------------------------------------------------------------------------


@pytest.mark.parametrize("label", sorted(EVASIONS))
def test_d1_the_old_path_convicts_and_cannot_even_ask(label):
    """BEFORE. The vocabulary grants the step, the checks convict an honest
    paper, and the paid path never offers the model the WITHDRAWING SENTENCE --
    which is D1's own measurement, verbatim: "the model correctly says the
    caption states nothing about averaging, because the caption is the only
    candidate it was ever shown." No verdict could have rescued this."""
    text = paper(EVASIONS[label])
    acc = tone_account()
    assert accusations(checks.evaluate(acc, text)), "the fixture must convict"
    assert not [c for c in old_path_candidates(acc, text)
                if EVASIONS[label] in c["quote"]]


@pytest.mark.parametrize("label", sorted(EVASIONS))
def test_d1_stage_one_surfaces_the_withdrawing_sentence(label):
    """AFTER, STAGE 1. Relevance is free and deterministic, and this is the half
    the spec's hypothesis is about: the sentence reaches a model at all."""
    text = paper(EVASIONS[label])
    acc = tone_account()
    got = averaging_candidates(acc, text)
    assert any(EVASIONS[label] in c["quote"] for c in got), \
        [c["quote"] for c in got]


@pytest.mark.parametrize("label", sorted(EVASIONS))
def test_d1_a_true_verdict_removes_every_accusation(label):
    """AFTER, STAGE 2 REPLAYED. The recorded reply said `true` on the
    withdrawing passage; the wiring has to carry that to
    `granularity_verification`, which is where the step of 1 lives."""
    text = paper(EVASIONS[label])
    acc = tone_account()
    cands = averaging_candidates(acc, text)
    assert any(recorded(c) for c in cands)
    rec = reading(*verdicts_for(cands, recorded), candidates=cands)
    assert accusations(checks.evaluate(dict(acc, premise_reading=rec), text)) == []


def test_f9_the_split_sentence_defeats_the_old_path_in_both_channels():
    """BEFORE. Neither half carries a combination word, so the free path grants
    the step; and even a per-sentence paid candidate cannot be judged `true`,
    because neither sentence establishes the premise alone."""
    text = paper(SPLIT_FIRST, SPLIT_SECOND)
    acc = tone_account()
    assert accusations(checks.evaluate(acc, text))
    assert not [c for c in old_path_candidates(acc, text)
                if SPLIT_SECOND in c["quote"]]


def test_f9_stage_one_offers_the_two_sentences_as_one_passage():
    """AFTER. The passage is a WINDOW inside the section, so the fact that is
    split across two sentences arrives whole -- which is the only form in which
    it is judgeable at all."""
    text = paper(SPLIT_FIRST, SPLIT_SECOND)
    got = averaging_candidates(tone_account(), text)
    assert any(SPLIT_FIRST in c["quote"] and SPLIT_SECOND in c["quote"]
               for c in got), [c["quote"] for c in got]


def test_f3_the_footnote_channel_reaches_stage_one():
    """The table's own footnote is admitted without an aboutness test, the same
    rule `premises.averaging_statements` applies to a caption: it governs its
    own table and has no sentence to be about."""
    text = paper()
    acc = tone_account(footnotes=[FOOTNOTE])
    got = averaging_candidates(acc, text)
    assert any(FOOTNOTE in c["quote"] and c["source"] == "printed_context"
               for c in got), [(c["source"], c["quote"]) for c in got]


# --------------------------------------------------------------------------
# E1 -- NO NEW ACCUSATION, AND NO REGRESSION ON WHAT ALREADY WORKS
# --------------------------------------------------------------------------


#: HONEST CONTROLS. A paper that says none of these things is entitled to its
#: step of 1, and nothing the new path does may take that entitlement away OR
#: manufacture a conviction the old path did not make.
HONEST = {
    "nothing further said": (),
    "an unrelated methods sentence":
        ("Cards were collected by the stewards at the end of each heat.",),
    "a sentence about the OTHER declared variable":
        ("Tempo accuracy was logged in whole points at the same heat.",),
    "the paper's own group mean, which is not a per-subject average":
        ("The mean of the 30 entrants is reported beside its standard deviation.",),
}


@pytest.mark.parametrize("label", sorted(HONEST))
def test_the_new_path_manufactures_no_accusation_the_old_one_did_not_make(label):
    """E1'S OWN WORDING: the claim is about which SHAPE of defect remains
    possible, so what is pinned is that the new path's verdicts -- in EITHER
    direction -- never add an accusation. A refusal can only remove a check, and
    this is the test that says so rather than the docstring."""
    text = paper(*HONEST[label])
    acc = tone_account()
    before = accusations(checks.evaluate(acc, text))
    cands = averaging_candidates(acc, text)
    for answer in (True, False):
        rec = reading(*verdicts_for(cands, lambda c: answer), candidates=cands)
        after = accusations(checks.evaluate(dict(acc, premise_reading=rec), text))
        assert set(after) <= set(before), (answer, before, after)


def test_a_false_verdict_leaves_the_vocabularys_own_refusal_standing():
    """THE POLARITY, PINNED. A paper that DOES say it in the vocabulary's own
    words is refused by the free path, and a model `false` may not lift that --
    `adjudication.already_refused` never offers the variable, and `index`
    applies a refusal only on `true`."""
    text = paper("Each entrant's tone score is the mean of the three judges' cards.")
    acc = tone_account()
    assert averaging_candidates(acc, text) == []
    assert accusations(checks.evaluate(acc, text)) == []


def test_stage_one_is_skipped_entirely_where_the_vocabulary_already_refused():
    """The early-out is not an optimisation: a premise already withdrawn cannot
    be moved, so asking about it costs a paid line and buys nothing."""
    hay = premises.Haystack(paper(
        "Each entrant's tone score is the mean of the three judges' cards."))
    variables = premises.readable_variables(tone_account())
    v = [x for x in variables if x["id"] == "var:tone"][0]
    assert adjudication.already_refused(v, hay, variables)


# --------------------------------------------------------------------------
# E4 -- THE LICENCE SIDE IS UNTOUCHED
# --------------------------------------------------------------------------


def test_the_new_path_emits_refusal_candidates_and_nothing_else():
    """E4, directly: `bound` and `step` are LICENCE premises, and a licence
    being generous is the direction this project has never let a model control.
    The prototype may not widen one."""
    text = paper(*[s for s in EVASIONS.values()])
    got = adjudication.candidates(tone_account(), text)
    assert got, "the fixture must produce candidates at all"
    assert {c["premise"] for c in got} == {"averaging"}
    assert all(c["premise"] in PR.REFUSAL_PREMISES for c in got)


def test_the_licence_path_is_byte_identical_before_and_after():
    """The two premise types side by side on one shared fixture: the bound and
    step candidates `premise_reading` builds are the same rows whether or not
    this module is imported or called."""
    text = paper(*[s for s in EVASIONS.values()])
    acc = tone_account()
    before = [c for c in PR.candidates(acc, text)
              if c["premise"] in PR.LICENCE_PREMISES]
    adjudication.candidates(acc, text)
    after = [c for c in PR.candidates(acc, text)
             if c["premise"] in PR.LICENCE_PREMISES]
    assert before == after


def test_the_alternative_base_ceiling_is_not_reachable_from_this_module():
    """D71, kept literal. The ceiling must never be model-vetoable, and the
    cheapest way to keep that true is that the module which builds model
    candidates does not name it."""
    src = (adjudication.__file__ or "")
    assert src.endswith("adjudication.py")
    with open(src, encoding="utf-8") as fh:
        body = fh.read()
    for forbidden in ("paper_max_n", "_SUBJECT_COUNT", "alternative_base",
                      "_N_VARIES", "varying_n"):
        assert forbidden not in body.split('"""')[-1], forbidden


# --------------------------------------------------------------------------
# The shape of what stage 1 hands a model
# --------------------------------------------------------------------------


def test_every_candidate_is_askable_and_carries_its_question():
    """A window spanning two sentences is exactly the passage that will not
    locate as one contiguous span, and dropping it would reintroduce the recall
    gap. `askable` is therefore unconditional here, which is `premise_reading`'s
    own rule for a refusal premise, made explicit."""
    text = paper(SPLIT_FIRST, SPLIT_SECOND)
    for c in adjudication.candidates(tone_account(), text):
        assert c["askable"] is True
        assert c["question"] == PR.QUESTIONS["averaging"]
        assert c["relevance_version"] == adjudication.RELEVANCE_VERSION


def test_the_prompt_builds_from_these_candidates_unchanged():
    """The candidate shape is `premise_reading`'s own, so its prompt builder
    takes these rows with no change to it -- this is a different recall net, not
    a different pipeline."""
    text = paper(*[s for s in EVASIONS.values()])
    cands = adjudication.candidates(tone_account(), text)
    prompt = PR.build_prompt(cands)
    assert PR.PREAMBLE in prompt
    assert prompt.count("--- CANDIDATE ") == len(cands)


# --------------------------------------------------------------------------
# E1, THE OTHER HALF -- A PAPER THAT IS ENTITLED TO ITS STEP KEEPS IT, AND THE
# WINDOW'S OWN RISK, MEASURED
# --------------------------------------------------------------------------

#: THE SAME SURVEY WITH ONE ADJUDICATOR. Every entrant's tone score is a whole
#: number, the step of 1 is true, and the mean it produces IS reachable from an
#: integer total -- so this paper is not accused before the prototype exists and
#: must not be accused after it.
SINGLE = ("Tone was scored in whole points on a 0 to 30 card by the single "
          "adjudicator.")
CLEAN = CARD_A
CLEAN_MEAN = f"{st.fmean(CLEAN):.2f}"
CLEAN_SD = f"{st.stdev(CLEAN):.2f}"
assert all(float(x).is_integer() for x in CLEAN)
assert any(round(k / N, 2) == float(CLEAN_MEAN) for k in range(N * 30 + 1))

#: THE PROTOTYPE'S OWN RISK, NAMED IN `relevant_passages` AND THEN MEASURED. A
#: window is three sentences, so a neighbour that really does describe an
#: average -- of ANOTHER variable, or of the GROUP -- is shown to the model
#: beside a variable that is entitled to its step. If the model took the bait it
#: would withdraw a step wrongly, which costs a CHECK (never an accusation). It
#: did not: both came back `false`, with reasons naming the distinction.
NEIGHBOURS = {
    "an average of the OTHER declared variable":
        "Tempo accuracy is the mean of the two timekeepers' readings.",
    "the paper's own group mean":
        "The mean of the 30 entrants is reported beside its standard deviation.",
}


def clean_account():
    acc = account(
        variables=[var("var:tone", "Tone score", "ordinal", bsource="stated",
                       lower=0, upper=30, bquote=SINGLE, step=1, gquote=SINGLE),
                   var("var:tempo", "Tempo accuracy", "ordinal",
                       bsource="not_stated", step=1,
                       gquote="Tempo accuracy was logged in whole points.")],
        values=[cell("val:mean", "mean", CLEAN_MEAN, variable_id="var:tone"),
                cell("val:sd", "sd", CLEAN_SD, variable_id="var:tone", col=2),
                cell("val:n", "n", str(N), variable_id="var:tone", col=3,
                     col_label="n")])
    return acc


def test_a_paper_entitled_to_its_step_is_untouched_in_both_directions():
    """E1, non-trivially: the old path leaves this paper alone, and neither
    answer the model can give adds anything to that."""
    text = " ".join(["## Methods", SINGLE])
    acc = clean_account()
    assert accusations(checks.evaluate(acc, text)) == []
    cands = averaging_candidates(acc, text)
    for answer in (True, False):
        rec = reading(*verdicts_for(cands, lambda c: answer), candidates=cands)
        assert accusations(checks.evaluate(dict(acc, premise_reading=rec), text)) == []


@pytest.mark.parametrize("label", sorted(NEIGHBOURS))
def test_a_contaminating_neighbour_reaches_the_model_and_is_refused(label):
    """BOTH HALVES, and the second is the one that could have gone the other
    way. Stage 1 really does put the neighbour in front of the model -- that is
    the cost of a window -- and the recorded batch answered `false` to both."""
    text = " ".join(["## Methods", SINGLE, NEIGHBOURS[label]])
    acc = clean_account()
    got = averaging_candidates(acc, text)
    assert any(NEIGHBOURS[label] in c["quote"] for c in got), \
        [c["quote"] for c in got]
    assert not any(recorded(c) for c in got)
    rec = reading(*verdicts_for(got, recorded), candidates=got)
    assert accusations(checks.evaluate(dict(acc, premise_reading=rec), text)) == []


# --------------------------------------------------------------------------
# E1 -- AGAINST THE EXISTING PINNED FIXTURES, NOT ONLY THIS ROUND'S OWN
# --------------------------------------------------------------------------

#: E1's claim is about a corpus of fixtures already built, so it is asked of
#: them rather than only of a paper written to be rescued. Round 10's seven
#: wordings of an average are the pinned set the old path ALREADY handles, on
#: both the vocabulary path and under a model `true` on the step: the property
#: to keep is that adding this prototype changes nothing there, in either
#: direction of verdict.
#:
#: THE IMPORT IS THE POINT. Re-typing round 10's fixture here would test a copy
#: of it, and a copy that drifts is how a regression test stops being one.


def _round10():
    from . import test_scaffold_checks_round10 as R10
    return R10


@pytest.mark.parametrize("i", range(7))
def test_round_10s_pinned_averages_gain_no_accusation_from_the_new_path(i):
    """The strongest form of E1 available for free: for a fixture the old path
    already handles, no answer the model could give adds anything."""
    R10 = _round10()
    sentence = R10.AVERAGES[i]
    acc, text, _, _ = R10._index(sentence)
    before = sorted(R10.accusations(checks.evaluate(acc, text)))
    assert before == [], sentence
    cands = adjudication.candidates(acc, text)
    for answer in (True, False):
        rec = reading(*verdicts_for(cands, lambda c: answer), candidates=cands)
        after = sorted(R10.accusations(
            checks.evaluate(dict(acc, premise_reading=rec), text)))
        assert after == [], (sentence, answer, after)


def test_round_12s_honest_half_point_index_is_still_not_accused():
    """Round 12's own fixture paper, through the new path: the decoy sentence
    between an anaphor and its antecedent, which is F2's shape and the one this
    prototype's stage 1 inherits its window rule from."""
    from . import test_scaffold_checks_round12 as R12
    for label, between in sorted(R12.DECOYS.items()):
        text = "\n\n".join([s for s in (R12.INTRO, between, R12.ANAPHOR) if s])
        acc = R12.account(variables=R12._peal_variables(),
                          values=[R12.cell("val:m", "mean", R12.PEAL_MEAN,
                                           variable_id="var:peal"),
                                  R12.cell("val:s", "sd", R12.PEAL_SD,
                                           variable_id="var:peal", col=2),
                                  R12.cell("val:n", "n", str(R12.N),
                                           variable_id="var:peal", col=3,
                                           col_label="n")])
        before = sorted(R12.accusations(checks.evaluate(acc, text)))
        assert before == [], label
        cands = adjudication.candidates(acc, text)
        for answer in (True, False):
            rec = reading(*verdicts_for(cands, lambda c: answer), candidates=cands)
            after = sorted(R12.accusations(
                checks.evaluate(dict(acc, premise_reading=rec), text)))
            assert after == [], (label, answer, after)
