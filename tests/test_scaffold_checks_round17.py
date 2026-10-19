"""ROUND 17 -- BOUNDED ADJUDICATION FOR THE ESTIMATOR REFUSAL PREMISE.

THE DEFECT, MEASURED AT `ff4d5ae` AND NOT INFERRED. Four ordinary honest
phrasings of a survey-weighted mean, run through the real `checks.evaluate` on
round 10's own honest weighted fixture:

    accusations=3  estimator candidates=0   "Each swimmer's card counts toward
                     the reported mean according to her stratum share on the register."
    accusations=3  estimator candidates=0   "The reported averages give every
                     stratum the share it holds on the roll."
    accusations=3  estimator candidates=0   "Table 1 gives the means after the
                     register margins were applied."
    accusations=3  estimator candidates=0   "Reported means take account of the
                     differing selection chances of the swimmers."

GRIM, GRIMMER and SPRITE all return `impossible` on an honest paper AND
`premise_reading.candidates` offers the model ZERO estimator candidates, so
`--read-premises` cannot rescue any of them either. That is round 15's D1 shape
reproduced on a different premise: a RECALL failure, where no judgement however
good could have helped because nothing was ever asked.

AND THE VOCABULARY IS ALREADY LIVING ON THE JUDGE'S CREDIT. Three of round 10's
own eight pinned statements -- `reweighted`, `raked`, `in proportion to` --
already evade `premise_reading._ESTIMATOR_CANDIDATE`; they refuse today only
because `premises._ESTIMATOR_STATEMENT`, the JUDGE, happens to carry them. Pinned
below, because it is the reason the next phrasing takes both to zero.

WHAT CHANGED IS STAGE 1 AND ONLY STAGE 1 (`adjudication._estimator_candidates`,
free and deterministic). The estimator premise is keyed to a SET OF VALUES rather
than to a variable, so relevance is asked of three scopes: the VARIABLE
(`_is_about`, borrowed verbatim from the averaging net), WHAT THE PAPER REPORTS
(`_GOVERNS_REPORTED`, paper-wide, per statistic kind), and TABLE FURNITURE (the
band, caption and footnotes, with the `_ESTIMATOR_CANDIDATE` gate removed). Every
served-text passage is a WINDOW, which is what makes a statement split across two
sentences judgeable at all.

THE QUESTION WAS REWRITTEN, MEASURED, AND REVERTED, and that is the other result
of this round. The proposal was that `QUESTIONS["estimator"]` is a LIST OF
ADJECTIVES and therefore the same instrument as the vocabulary a model is brought
in to replace. Asked head to head on the real candidate path, the two wordings
agreed on 49 of 49 -- so the shipped string stays and `PROMPT_VERSION` does not
move, which is what keeps every premise's saved reply reusable. The reason it
generalises is worth keeping: it is not a bare list, it ends in the arithmetic
contrast ("rather than a plain total divided by the number of subjects in this
group"), and that clause is what the model answers from.

THE MODEL VERDICTS ARE REPLAYED FROM A RECORDED RUN, not called for at test time.
`RECORDED_TRUE` is what a real sonnet batch answered about the exact candidate
rows `adjudication.candidates_for` builds from these fixtures -- window, printed
context, target and all, which is the shape round 16 proved matters: asked as
bare sentences the defect does not appear.

THE MEASUREMENT, STATED SO IT CAN BE ARGUED WITH. 2026-09-12, sonnet, five
batches, $1.127 in total. EVERY ROW THIS FILE REPLAYS A VERDICT FOR WAS ASKED --
nothing here is extrapolated from a neighbouring window:

    this file's first 37 candidates, proposed wording     37 of 37   $0.3507
    the same 37, shipped wording                          37 of 37   $0.2165
    12 adversarial candidates, proposed wording           12 of 12   $0.1687
    the same 12, shipped wording                          12 of 12   $0.1585
    the adversarial set in full, 37 rows, shipped         37 of 37   $0.2328

So 74 rows judged under the shipped wording (72 distinct -- two windows occur in
both of its batches) and 49 under the proposed one, and the two wordings never
disagreed on a single row. The adversarial twelve are seven
estimators described with NONE of the shipped question's adjectives -- a
weighting stated as replication, a two-stage mean, an unnamed trim, an unnamed
imputation, a model fit, an unnamed post-stratification, a geometric mean -- and
five honest controls a stricter wording could have over-fired on, including two
members withdrawing (which changes WHO IS IN the mean and not HOW IT IS
COMPUTED). Every defect passage in this file answered `true`; every honest
control, the bare `Mean (SD)` column with its plain caption among them, answered
`false`; and so did a footnote saying only that sample sizes differ across
measures, which belongs to the premise next door.

One fixture is not a corpus and this file says nothing about a real paper's rate.
"""

from __future__ import annotations

import statistics as st

import pytest

from metascience_agent.scaffold import __main__ as _main
from metascience_agent.scaffold import (adjudication, checks,
                                        premise_reading as PR, premises)

BAD = {"suspicious", "highly_suspicious", "impossible"}


# --------------------------------------------------------------------------
# The Kilnsea lifeboat station drill audit -- round 17's own fixture paper
# (shares nothing with rounds 1-16)
# --------------------------------------------------------------------------

#: Launch readiness, scored 0-12 in WHOLE points, one card per crew member. The
#: figure the paper reports is the ROLL-WEIGHTED mean of those cards, which is an
#: honest estimator and is reachable from NO integer total over 12 -- so a paper
#: whose arithmetic is exact is convicted the moment the estimator premise is not
#: withdrawn.
READY = [4, 11, 7, 2, 12, 0, 6, 9, 3, 8, 5, 10, 1, 7,
         12, 2, 4, 8, 6, 3, 11, 5, 9, 0, 6, 8, 4, 7]
WEIGHTS = [1.4, 0.8, 1.1, 0.9, 1.3, 0.7, 1.2, 1.0, 0.6, 1.5, 0.9, 1.1, 1.3, 0.8,
           1.2, 0.7, 1.4, 1.0, 0.9, 1.1, 0.6, 1.5, 1.2, 0.8, 1.3, 0.7, 1.0, 1.4]
N = len(READY)
W_MEAN = f"{sum(w * x for w, x in zip(WEIGHTS, READY)) / sum(WEIGHTS):.2f}"
W_SD = f"{st.stdev(READY):.2f}"

#: THE FIXTURE PAPER IS HONEST BY CONSTRUCTION, and the second assertion is what
#: makes it an experiment: the weighted mean is unreachable from any integer
#: total, so leaving the premise standing convicts a paper that did nothing wrong.
assert N == 28 == len(WEIGHTS) and all(0 <= x <= 12 for x in READY)
assert not any(round(k / N, 2) == float(W_MEAN) for k in range(N * 12 + 1))

#: THE SAME PAPER WITH NO WEIGHTING -- the plain mean of the same cards, which IS
#: reachable from an integer total. This is the honest descriptive control the
#: whole family exists for, and a wrong `true` here is the coverage collapse that
#: is this extension's top risk.
PLAIN_MEAN = f"{st.fmean(READY):.2f}"
assert any(round(k / N, 2) == float(PLAIN_MEAN) for k in range(N * 12 + 1))

N_Q = ("Twenty-eight crew took part in the Kilnsea lifeboat station drill audit "
       "(n = 28).")
BOUND = "Launch readiness was scored on a card running from 0 to 12."
GRAN = "Launch readiness was scored in whole points at every drill."


# --------------------------------------------------------------------------
# THE FOUR EVASIONS, MEASURED AT ff4d5ae -- 3 accusations AND 0 candidates
# --------------------------------------------------------------------------

EVASIONS = {
    "counts toward according to her share":
        "Each crew member's card counts toward the reported mean according to "
        "her watch's share of the station roll.",
    "gives every stratum its share":
        "The reported averages give every watch the share it holds on the roll.",
    "after the margins were applied":
        "Table 1 gives the means after the roll margins were applied.",
    "takes account of selection chances":
        "Reported means take account of the differing selection chances of the "
        "crew.",
}

#: ROUND 10'S OWN DOCUMENT-LEVEL STATEMENT, ported to this paper. It produced
#: zero candidates until round 10 widened the net, and it must reach stage 1
#: here WITHOUT depending on that widening.
GOVERNING_OUTSIDE = ("Each crew member's card was up-weighted by the reciprocal "
                     "of her selection probability before the reported values "
                     "were formed.")

#: THE SPLIT-STATEMENT CHANNEL, this premise's F9. Neither half establishes the
#: premise alone -- the first names no reported quantity, the second no weights --
#: so a per-sentence candidate is correctly judged `false` and the paper is
#: convicted anyway. Only the window makes it judgeable.
SPLIT_FIRST = "Weights were formed from the roll's age and watch margins."
SPLIT_SECOND = "Each crew member's card counts in proportion to hers."

#: ROUND 12'S F3 CHANNEL, with a statement the vocabulary does NOT carry. The
#: caught version (`Means are weighted to the guild roll.`) is already refused by
#: the free path through `premises.table_footnotes`, so it can prove nothing
#: about a recall net; this one is the case that needs one. On a JATS paper a
#: footnote is not in the served body at all.
FOOTNOTE = ("Each crew member's card counts toward the figures above according "
            "to her watch's share of the station roll.")

#: SEVEN ESTIMATORS DESCRIBED WITH NONE OF THE SHIPPED QUESTION'S ADJECTIVES, and
#: none of `premises.NOT_A_SIMPLE_MEAN`'s either. Written to defeat a list, which
#: is what the proposed rewrite assumed the question was; the measurement says the
#: question's closing ARITHMETIC CONTRAST carries all seven anyway. They stay
#: pinned because they are the hardest recall cases this file has -- every one is
#: invisible to the free path in both its judging and its candidate vocabulary.
ADVERSARIAL = {
    "a weighting stated as replication":
        "Each crew member's card enters the reported mean once for every three "
        "members of her watch on the roll.",
    "a two-stage mean":
        "The figures in Table 1 were obtained by first taking the mean within "
        "each watch and then combining those four numbers.",
    "a trim, unnamed":
        "Means were computed after the three lowest and three highest cards in "
        "each watch were set aside.",
    "an imputation, unnamed":
        "Where a card was missing, the member's most likely score given her watch "
        "and years of service was put in its place before the mean was taken.",
    "a model fit, unnamed":
        "The reported mean is the value that best fits the cards under the "
        "station's response model.",
    "a post-stratification, unnamed":
        "Each mean in Table 1 was rescaled so that the four watches contribute in "
        "the ratio of their roll sizes.",
    "a geometric mean, unnamed":
        "The reported figure is the exponential of the mean of the logged cards.",
}

#: AND THE CONTROLS THAT GO WITH THEM, which are the ones a STRICTER wording could
#: have over-fired on. "Two members withdrew" is the one worth naming: it changes
#: WHO IS IN the mean and not HOW IT IS COMPUTED, so the premise stands and the
#: check is owed. A `true` there is the shape that would quietly silence the tool
#: on every paper that reports an exclusion, which is most of them.
ADVERSARIAL_HONEST = {
    "a legibility check":
        "Cards were checked for legibility before the mean was taken.",
    "two members withdrew":
        "Two members withdrew before the final drill and their cards are not "
        "included.",
    "the tool used":
        "The mean was computed with the station's spreadsheet.",
    "rounding before printing":
        "Means were rounded to two decimal places before printing.",
    "a plain report":
        "The mean of the 28 cards is reported to two decimals alongside its "
        "standard deviation.",
}

#: AND THE PREMISE NEXT DOOR, which is the risk this design carries by
#: construction: table furniture is admitted with NO aboutness test, so a
#: footnote about how many people were analysed IS asked the estimator question.
#: A `true` here would be a true fact filed under the wrong premise and would
#: print the wrong reason in a docket. It is excluded in the QUESTION's wording,
#: because `adjudication` may not name that premise at all (D71's grep rail).
WRONG_PREMISE_FOOTNOTE = ("Sample sizes vary across measures owing to missing "
                          "responses.")


# --------------------------------------------------------------------------
# The account
# --------------------------------------------------------------------------


def var(vid, name, *, lower=0, upper=12, bquote=BOUND, step=1, gquote=GRAN):
    return {"id": vid, "name": name, "label": name, "printed_as": [],
            "kind": "ordinal", "role": None, "units": None,
            "units_source": "not_stated", "derivation": None, "derived_from": [],
            "bounds": {"source": "stated", "lower": lower, "upper": upper,
                       "quote": bquote},
            "granularity": {"per_subject_step": step, "quote": gquote}}


def _lit(printed):
    return premises.read_plain(printed) or {}


def cell(vid, statistic, printed, *, variable_id=None, col_label="Mean (SD)",
         row=1, col=1):
    lit = _lit(printed)
    return {"id": vid, "statistic": statistic, "printed": printed,
            "numeric": lit.get("value"), "decimals": lit.get("decimals", 0),
            "printed_form": "percent" if lit.get("is_percent") else "plain",
            "units": None, "variable_id": variable_id, "id_check": "agrees",
            "statistic_disputed": False, "source": "table", "quote": None,
            "quote_verified": "cell", "printed_in_quote": None,
            "location": {"kind": "table_cell", "table_id": "table:1", "row": row,
                         "col": col, "col_label": col_label},
            "coordinate": {"study_id": "study:kilnsea", "group_id": "grp:crew",
                           "phase_id": None}}


def prose(vid, statistic, printed, quote, *, variable_id=None):
    lit = _lit(printed)
    return {"id": vid, "statistic": statistic, "printed": printed,
            "numeric": lit.get("value"), "decimals": lit.get("decimals", 0),
            "printed_form": "plain", "units": None, "variable_id": variable_id,
            "id_check": "agrees", "statistic_disputed": False, "source": "prose",
            "quote": quote, "quote_verified": "verbatim", "printed_in_quote": True,
            "location": {"kind": "prose", "offset": 0, "col_label": None},
            "coordinate": {"study_id": "study:kilnsea", "group_id": "grp:crew",
                           "phase_id": None}}


def account(*, values=(), footnotes=()):
    return {"paper": {"doi": "10.0000/kilnsea",
                      "title": "The Kilnsea lifeboat station drill audit"},
            "studies": [{"id": "study:kilnsea", "design": "prospective_cohort",
                         "groups": [{"id": "grp:crew", "label": "All crew",
                                     "n": N, "n_source": "text"}]}],
            "variables": [var("var:ready", "Launch readiness")],
            "values": list(values),
            "document": {"tables": [
                {"id": "table:1",
                 "caption": "Table 1. Crew-level drill scores, Kilnsea station.",
                 "footnotes": [str(f) for f in footnotes]}]}}


def drill_account(mean=None, *, footnotes=()):
    return account(values=[prose("val:n", "n", str(N), N_Q),
                           cell("val:m", "mean", mean or W_MEAN,
                                variable_id="var:ready"),
                           cell("val:s", "sd", W_SD, variable_id="var:ready",
                                col=2)],
                   footnotes=footnotes)


def paper(*sentences):
    """The served text: the sentences that grant the premises, then the case."""
    return "\n\n".join(("## Methods", N_Q, BOUND, GRAN) + sentences) + "\n"


def accusations(got):
    return sorted({(r["check_id"], r["severity"]) for r in got["checks"]
                   if r["severity"] in BAD})


def estimator_candidates(acc, text):
    return adjudication.candidates_for(acc, text, ("estimator",))


def old_path_candidates(acc, text):
    return [c for c in PR.candidates(acc, text) if c["premise"] == "estimator"]


def reading(*verdicts, candidates=()):
    cands = list(candidates)
    return {"schema": PR.SCHEMA_VERSION, "prompt_version": PR.PROMPT_VERSION,
            "model": "sonnet", "n_candidates": len(cands), "n_asked": len(cands),
            "n_dropped": 0, "candidates": cands, "verdicts": list(verdicts),
            "problems": [], "cost_usd": 0.0, "n_calls": 1}


#: WHAT THE PAID BATCH ANSWERED `true` ON, exhaustively: the defect passages and
#: nothing else. Every other candidate of the run -- the granting sentences, the
#: plain `Mean (SD)` column with its plain caption, each honest control, and the
#: footnote about differing sample sizes -- came back `false`. Written as the
#: passages rather than as candidate ids because a candidate id is an artefact of
#: the ordering and the passage is the thing that was judged.
RECORDED_TRUE = (tuple(EVASIONS.values()) + tuple(ADVERSARIAL.values())
                 + (GOVERNING_OUTSIDE, SPLIT_SECOND, FOOTNOTE))


def recorded(c):
    """The 2026-09-12 sonnet batch's answer about this candidate."""
    return any(s in c["quote"] for s in RECORDED_TRUE)


def verdicts_for(cands, establishes):
    """A recorded reply, replayed: one verdict per candidate."""
    return [{"candidate_id": c["id"], "premise": c["premise"],
             "establishes": bool(establishes(c)), "reason": "recorded",
             "model": "sonnet", "prompt_version": PR.PROMPT_VERSION}
            for c in cands]


# --------------------------------------------------------------------------
# THE DEFECT: EACH CASE CONVICTS AT HEAD AND CANNOT EVEN BE ASKED ABOUT
# --------------------------------------------------------------------------


@pytest.mark.parametrize("label", sorted(EVASIONS))
def test_the_old_path_convicts_and_cannot_even_ask(label):
    """BEFORE, and both halves matter. The vocabulary does not read the
    statement, so three checks convict an honest paper; and the paid path never
    offers the model the withdrawing sentence, so no verdict could have rescued
    it."""
    text = paper(EVASIONS[label])
    acc = drill_account()
    assert accusations(checks.evaluate(acc, text)), "the fixture must convict"
    assert not [c for c in old_path_candidates(acc, text)
                if EVASIONS[label] in c["quote"]]


@pytest.mark.parametrize("label", sorted(EVASIONS))
def test_stage_one_surfaces_the_withdrawing_sentence(label):
    """AFTER, STAGE 1. Free, deterministic, and the half the hypothesis is
    actually about: the sentence reaches a model at all."""
    got = estimator_candidates(drill_account(), paper(EVASIONS[label]))
    assert any(EVASIONS[label] in c["quote"] for c in got), \
        [c["quote"] for c in got]


@pytest.mark.parametrize("label", sorted(EVASIONS))
def test_a_true_verdict_removes_every_accusation(label):
    """AFTER, STAGE 2 REPLAYED. The recorded reply said `true` on the withdrawing
    passage; the wiring has to carry that through `premise_reading.index` --
    which keys an estimator verdict by VALUE id -- to `premises.value_premise`,
    where the refusal lives."""
    text = paper(EVASIONS[label])
    acc = drill_account()
    cands = estimator_candidates(acc, text)
    assert any(recorded(c) for c in cands)
    rec = reading(*verdicts_for(cands, recorded), candidates=cands)
    assert accusations(checks.evaluate(dict(acc, premise_reading=rec), text)) == []


def test_the_document_level_statement_reaches_stage_one_without_the_widening():
    """Round 10's own governing sentence, which produced zero candidates until
    the vocabulary was widened for it. Relevance must reach it on the aboutness
    of the passage alone."""
    text = paper(GOVERNING_OUTSIDE)
    acc = drill_account()
    assert premises.estimator_statement(text) is None, "must stay outside the judge"
    assert accusations(checks.evaluate(acc, text))
    got = estimator_candidates(acc, text)
    assert any(GOVERNING_OUTSIDE in c["quote"] for c in got), [c["quote"] for c in got]
    rec = reading(*verdicts_for(got, recorded), candidates=got)
    assert accusations(checks.evaluate(dict(acc, premise_reading=rec), text)) == []


def test_the_split_statement_is_offered_as_one_passage():
    """THE F9 SHAPE FOR THIS PREMISE. Neither half establishes the premise alone,
    so the old path convicts and a per-sentence candidate could not have helped;
    the window is what makes the pair judgeable."""
    text = paper(SPLIT_FIRST, SPLIT_SECOND)
    acc = drill_account()
    assert accusations(checks.evaluate(acc, text))
    assert not [c for c in old_path_candidates(acc, text)
                if SPLIT_SECOND in c["quote"]]
    got = estimator_candidates(acc, text)
    assert any(SPLIT_FIRST in c["quote"] and SPLIT_SECOND in c["quote"]
               for c in got), [c["quote"] for c in got]
    rec = reading(*verdicts_for(got, recorded), candidates=got)
    assert accusations(checks.evaluate(dict(acc, premise_reading=rec), text)) == []


def test_the_footnote_channel_reaches_stage_one():
    """A statement the vocabulary does not carry, sitting only in the table's own
    footnote -- which on a JATS paper is not in the served body at all. Admitted
    with no aboutness test, the same rule a caption gets: furniture governs its
    own table and has no sentence to be about."""
    text = paper()
    acc = drill_account(footnotes=[FOOTNOTE])
    assert FOOTNOTE not in text
    assert accusations(checks.evaluate(acc, text))
    got = estimator_candidates(acc, text)
    assert any(FOOTNOTE in c["quote"] and c["source"] == "printed_context"
               for c in got), [(c["source"], c["quote"]) for c in got]
    rec = reading(*verdicts_for(got, recorded), candidates=got)
    assert accusations(checks.evaluate(dict(acc, premise_reading=rec), text)) == []


# --------------------------------------------------------------------------
# THE TOP RISK: COVERAGE COLLAPSE ON THE HONEST DESCRIPTIVE COLUMN
# --------------------------------------------------------------------------

#: HONEST PAPERS THAT SAY NOTHING ABOUT AN ESTIMATOR. A `true` on any of these
#: withdraws GRIM, GRIMMER and SPRITE from the plain `Mean (SD)` column this
#: whole family exists for. The recorded batch answered `false` to every one.
HONEST = {
    "nothing further said": (),
    "an unrelated methods sentence":
        ("Cards were collected by the coxswain at the end of each drill.",),
    "round 11's own plain descriptive sentence":
        ("Means and standard deviations are reported for every crew-level "
         "rating.",),
    "the paper's own group mean":
        ("The mean of the 28 crew is reported beside its standard deviation.",),
    "a difference described as marginal":
        ("The differences in means were marginal.",),
    "an adjustment made somewhere else in the paper":
        ("A logistic regression of call-out success adjusted for wind force.",),
}


@pytest.mark.parametrize("label", sorted(HONEST))
def test_an_honest_paper_keeps_its_checks_under_the_recorded_verdicts(label):
    """RISK 1, THE MEASUREMENT. The honest paper here is the one whose mean the
    checks CAN reach, so `before` is empty and `after` must be empty too -- but
    the test that matters is the next one, which pins that the checks still RAN."""
    text = paper(*HONEST[label])
    acc = drill_account(PLAIN_MEAN)
    before = accusations(checks.evaluate(acc, text))
    assert before == []
    cands = estimator_candidates(acc, text)
    rec = reading(*verdicts_for(cands, recorded), candidates=cands)
    assert accusations(checks.evaluate(dict(acc, premise_reading=rec), text)) == []


@pytest.mark.parametrize("label", sorted(HONEST))
def test_the_honest_paper_is_still_being_checked_and_not_merely_unaccused(label):
    """THE TEST RISK 1 ACTUALLY NEEDS, and it is round 11's
    `test_a_plain_descriptive_paper_is_still_checked` moved onto the new path.
    An empty accusation list is what a SILENCED tool and a satisfied tool both
    produce; the paper here is accused at HEAD, so a `true` would remove a real
    finding and the recorded `false` has to keep it."""
    text = paper(*HONEST[label])
    acc = drill_account()
    assert accusations(checks.evaluate(acc, text)) != []
    cands = estimator_candidates(acc, text)
    rec = reading(*verdicts_for(cands, recorded), candidates=cands)
    assert accusations(checks.evaluate(dict(acc, premise_reading=rec), text)) != []


@pytest.mark.parametrize("label", sorted(HONEST))
def test_no_answer_the_model_can_give_adds_an_accusation(label):
    """THE POLARITY, PINNED AS A PROPERTY RATHER THAN AS A DOCSTRING. Whatever
    the model says, in EITHER direction, the new path never adds an accusation
    the old one did not make."""
    text = paper(*HONEST[label])
    for acc in (drill_account(), drill_account(PLAIN_MEAN)):
        before = accusations(checks.evaluate(acc, text))
        cands = estimator_candidates(acc, text)
        for answer in (True, False):
            rec = reading(*verdicts_for(cands, lambda c: answer), candidates=cands)
            after = accusations(checks.evaluate(dict(acc, premise_reading=rec), text))
            assert set(after) <= set(before), (answer, before, after)


def test_the_plain_descriptive_column_is_offered_and_refused():
    """THE FURNITURE CHANNEL'S OWN RISK, AND IT IS THE POINT OF MEASURING IT.
    Removing the `_ESTIMATOR_CANDIDATE` gate means the bare `Mean (SD)` band over
    a plain caption becomes a candidate -- there is no vocabulary left to stop
    it. Stage 1 really does put it in front of the model; the recorded batch
    answered `false`."""
    acc = drill_account()
    got = estimator_candidates(acc, paper())
    furniture = [c for c in got if c["source"] == "printed_context"]
    assert furniture and any("Mean (SD)" in c["quote"] for c in furniture)
    assert not any(recorded(c) for c in furniture)


def test_a_statement_about_who_was_analysed_is_not_an_estimator_statement():
    """RISK 7 -- THE WRONG PREMISE, ROUND 12'S F3 IN REVERSE. Furniture is
    admitted with no aboutness test, so a footnote belonging to the premise next
    door IS asked this question. A `true` would be coverage-only harm but would
    put a false reason in a docket, which is the defect class a false docket
    sentence belongs to. It could not be guarded in `adjudication` -- D71's grep
    rail forbids that module from naming the other premise -- so it was MEASURED
    instead, and the recorded batch answered `false`."""
    acc = drill_account(footnotes=[WRONG_PREMISE_FOOTNOTE])
    got = estimator_candidates(acc, paper())
    offered = [c for c in got if WRONG_PREMISE_FOOTNOTE in c["quote"]]
    assert offered, [c["quote"] for c in got]
    assert not any(recorded(c) for c in offered)


# --------------------------------------------------------------------------
# THE ADVERSARIAL SET: ESTIMATORS NO VOCABULARY IN THIS REPO CAN SEE
# --------------------------------------------------------------------------


@pytest.mark.parametrize("label", sorted(ADVERSARIAL))
def test_an_adversarial_estimator_is_invisible_to_every_vocabulary(label):
    """WHAT MAKES THESE THE HARD CASES. None of the three regexes that judge this
    premise, and neither of the two that decide what a model may SEE about it,
    matches any of them -- so at HEAD the paper is convicted and nothing can be
    asked. `_GOVERNS_REPORTED` is the only thing that reaches them, and it
    enumerates names for a REPORTED STATISTIC rather than ways of describing an
    estimator, which is the distinction the whole design rests on."""
    s = ADVERSARIAL[label]
    assert not premises.NOT_A_SIMPLE_MEAN.search(s)
    assert not premises._ESTIMATOR_STATEMENT.search(s)
    assert not premises.WEIGHTED_PERCENTAGE.search(s)
    assert not PR._ESTIMATOR_CANDIDATE.search(s)
    assert PR._GOVERNS_REPORTED.search(s)


@pytest.mark.parametrize("label", sorted(ADVERSARIAL))
def test_an_adversarial_estimator_convicts_at_head_and_is_rescued(label):
    text = paper(ADVERSARIAL[label])
    acc = drill_account()
    assert accusations(checks.evaluate(acc, text)), "the fixture must convict"
    assert not [c for c in old_path_candidates(acc, text)
                if ADVERSARIAL[label] in c["quote"]]
    cands = estimator_candidates(acc, text)
    assert any(ADVERSARIAL[label] in c["quote"] for c in cands), \
        [c["quote"] for c in cands]
    rec = reading(*verdicts_for(cands, recorded), candidates=cands)
    assert accusations(checks.evaluate(dict(acc, premise_reading=rec), text)) == []


@pytest.mark.parametrize("label", sorted(ADVERSARIAL_HONEST))
def test_an_adversarial_control_keeps_its_checks(label):
    """THE OTHER HALF OF THE SAME BATCH, and the reason it was asked. A wording
    generous enough to catch the seven above could easily have caught an
    exclusion, a rounding step or the name of a spreadsheet -- each of which
    would silence the tool on an honest paper. The recorded batch answered
    `false` to all five."""
    text = paper(ADVERSARIAL_HONEST[label])
    acc = drill_account()
    assert accusations(checks.evaluate(acc, text)) != []
    cands = estimator_candidates(acc, text)
    assert any(ADVERSARIAL_HONEST[label] in c["quote"] for c in cands)
    rec = reading(*verdicts_for(cands, recorded), candidates=cands)
    assert accusations(checks.evaluate(dict(acc, premise_reading=rec), text)) != []


# --------------------------------------------------------------------------
# NO REFUSAL POWER IS LOST -- THE PINNED FIXTURES OF ROUNDS 10 AND 11
# --------------------------------------------------------------------------


def _round10():
    from . import test_scaffold_checks_round10 as R10
    return R10


def _round11():
    from . import test_scaffold_checks_round11 as R11
    return R11


@pytest.mark.parametrize("i", range(8))
def test_round_10s_pinned_estimator_statements_still_refuse(i):
    """THE OTHER DIRECTION, AND IT IS THE ONE A RECALL EXTENSION CAN QUIETLY
    BREAK. Every statement the free path already reads must still refuse with no
    model in the room -- and must gain nothing from any answer one could give."""
    R10 = _round10()
    statement = R10.ESTIMATOR_STATEMENTS[i]
    acc, text, _, _ = R10._weighted(statement)
    assert R10.accusations(checks.evaluate(acc, text)) == [], statement
    cands = adjudication.candidates_for(acc, text, ("estimator",))
    for answer in (True, False):
        rec = reading(*verdicts_for(cands, lambda c: answer), candidates=cands)
        after = R10.accusations(checks.evaluate(dict(acc, premise_reading=rec), text))
        assert after == [], (statement, answer, after)


@pytest.mark.parametrize("i", range(7))
def test_round_11s_pinned_estimator_statements_still_refuse(i):
    R11 = _round11()
    statement = R11.ESTIMATOR_STATEMENTS[i]
    acc, text = R11._weighted(statement)
    assert R11.accusations(checks.evaluate(acc, text)) == [], statement
    cands = adjudication.candidates_for(acc, text, ("estimator",))
    for answer in (True, False):
        rec = reading(*verdicts_for(cands, lambda c: answer), candidates=cands)
        after = R11.accusations(checks.evaluate(dict(acc, premise_reading=rec), text))
        assert after == [], (statement, answer, after)


def test_a_value_the_vocabulary_already_refused_is_never_offered():
    """THE EARLY-OUT, AND IT IS NOT AN OPTIMISATION. A refusal can only be ADDED,
    so a value a rule has already refused cannot be moved by any verdict: asking
    costs a paid line and buys nothing. It is also what keeps the vocabulary
    LOAD-BEARING -- see the next test."""
    R10 = _round10()
    acc, text, _, _ = R10._weighted(R10.ESTIMATOR_STATEMENTS[0])
    assert premises.estimator_statement(text)
    got = adjudication.candidates_for(acc, text, ("estimator",))
    assert not any("val:m" in (c.get("value_ids") or []) for c in got), \
        [(c["source"], c["value_ids"]) for c in got]


def test_the_vocabulary_stays_load_bearing():
    """RISK 4, PINNED. Nobody may "simplify" the two judges away once the model
    path exists: every run WITHOUT the paid pass -- which is every ordinary run,
    and every call that truncates -- would lose the refusal and accuse honest
    weighted means again. The survivor filter reads them, so this is a live
    dependency and not a comment."""
    R10 = _round10()
    acc, text, _, _ = R10._weighted(R10.ESTIMATOR_STATEMENTS[0])
    values = [v for v in acc["values"] if premises.well_formed(v) is None]
    _, survivors = PR._estimator_groups(
        values, premises._captions(acc), premises.estimator_statement(text),
        premises.weighting_statement(text), premises.table_footnotes(acc),
        gate=False)
    assert "val:m" not in survivors["mean"]
    # and with the judges silenced it IS a survivor, which is what makes the
    # line above a measurement of them rather than of something else
    _, without = PR._estimator_groups(
        values, premises._captions(acc), None, None, {}, gate=False)
    assert "val:m" in without["mean"]


def test_three_of_round_10s_own_statements_already_evade_the_recall_vocabulary():
    """WHY THE RECALL NET HAD TO CHANGE AND NOT ONLY THE JUDGE. Three pinned
    statements refuse today only because `premises._ESTIMATOR_STATEMENT` happens
    to carry them; `premise_reading._ESTIMATOR_CANDIDATE`, which decides what a
    model may SEE, does not. The next phrasing takes both to zero, which is
    exactly what the four evasions above do."""
    R10 = _round10()
    evading = [s for s in R10.ESTIMATOR_STATEMENTS
               if not PR._ESTIMATOR_CANDIDATE.search(s)]
    assert len(evading) == 3, evading
    for s in evading:
        assert premises._ESTIMATOR_STATEMENT.search(s), s
        assert PR._GOVERNS_REPORTED.search(s), s


@pytest.mark.parametrize("label", sorted(EVASIONS))
def test_every_evasion_really_does_evade_both_estimator_vocabularies(label):
    """THE ASSERTION THAT MAKES THESE AN EXPERIMENT. A regenerated sentence the
    vocabulary happens to catch would be testing nothing, and the failure would
    look exactly like a pass."""
    s = EVASIONS[label]
    assert not PR._ESTIMATOR_CANDIDATE.search(s)
    assert not premises._ESTIMATOR_STATEMENT.search(s)
    assert not premises.NOT_A_SIMPLE_MEAN.search(s)
    assert PR._GOVERNS_REPORTED.search(s)


# --------------------------------------------------------------------------
# THE BOUNDARIES THE EXTENSION MAY NOT CROSS
# --------------------------------------------------------------------------


def test_the_default_is_still_averaging_alone():
    """THE ONE THING AN OPT-IN PROTOTYPE MAY NOT DO IS CHANGE WHAT AN EXISTING
    FLAG DOES. `--adjudicate-averaging` and every existing caller of
    `adjudication.candidates` get the same rows they got before."""
    assert adjudication.DEFAULT_PREMISES == ("averaging",)
    text = paper(*EVASIONS.values())
    acc = drill_account()
    assert {c["premise"] for c in adjudication.candidates(acc, text)} <= {"averaging"}
    assert (adjudication.candidates(acc, text)
            == adjudication.candidates_for(acc, text, ("averaging",)))


def test_no_licence_premise_can_be_asked_for():
    """THE COMPOSER TAKES A PREMISE NAME BY ARGUMENT, which is exactly where a
    licence could be handed to a model by accident. It refuses instead."""
    acc, text = drill_account(), paper()
    for bad in sorted(PR.LICENCE_PREMISES):
        with pytest.raises(ValueError):
            adjudication.candidates_for(acc, text, (bad,))
    with pytest.raises(ValueError):
        adjudication.candidates_for(acc, text, ("correction",))


def test_the_licence_path_is_byte_identical_before_and_after():
    """E4, for the wider net: the bound and step candidates `premise_reading`
    builds are the same rows whether or not this module is called."""
    text = paper(*EVASIONS.values())
    acc = drill_account()
    before = [c for c in PR.candidates(acc, text) if c["premise"] in PR.LICENCE_PREMISES]
    adjudication.candidates_for(acc, text, ("averaging", "estimator"))
    after = [c for c in PR.candidates(acc, text) if c["premise"] in PR.LICENCE_PREMISES]
    assert before == after


def test_the_free_estimator_generator_is_unchanged_by_the_extraction():
    """`_estimator_groups` was extracted from `_estimator_candidates` so the two
    nets share ONE definition of what a group is. The gated caller must behave
    exactly as it did: `gate=True` is the vocabulary path, unchanged, so the two
    nets stay comparable."""
    R10 = _round10()
    for statement in R10.ESTIMATOR_STATEMENTS + [R10.GOVERNING_OUTSIDE]:
        acc, text, _, _ = R10._weighted(statement)
        values = [v for v in acc["values"] if premises.well_formed(v) is None]
        gated, _ = PR._estimator_groups(
            values, premises._captions(acc), premises.estimator_statement(text),
            premises.weighting_statement(text), premises.table_footnotes(acc))
        assert all(PR._ESTIMATOR_CANDIDATE.search(c["quote"]) for c in gated)


def test_the_alternative_base_ceiling_is_not_reachable_from_this_module():
    """D71, kept literal AND WIDENED. Round 15 checked only the text after the
    LAST docstring in the file; the extension adds functions after that point, so
    the rail is now the whole module minus its own module docstring -- which no
    longer names the ceiling either."""
    src = (adjudication.__file__ or "")
    assert src.endswith("adjudication.py")
    with open(src, encoding="utf-8") as fh:
        body = fh.read()
    after_module_docstring = body.split('"""', 2)[-1]
    for forbidden in ("paper_max_n", "_SUBJECT_COUNT", "alternative_base",
                      "_N_VARIES", "varying_n"):
        assert forbidden not in after_module_docstring, forbidden


def test_no_number_leaves_this_path():
    """RISK 5. An estimator statement routinely names an external population with
    a count, and reading that number is the ceiling's job. A candidate carries a
    passage and a target; a verdict carries a boolean and a reason. There is no
    channel by which a number of the PAPER's can leave.

    THE KEY SET WAS STANDING IN FOR THE PROMPT, and round 18 made the difference
    matter. Recording how much of a passage was carried and how many passages
    were cut (`premise_reading._segments`, `adjudication._stratified`) puts OUR
    OWN counts on the row, because a budget that binds in silence is the defect
    those two exist to remove. So the row's shape is still pinned, AND the
    guarantee it was standing in for is now asserted where it lives: the item
    template renders four fields, and no bookkeeping field reaches a model."""
    text = paper("Means were weighted to the station roll of 240 members.")
    cands = adjudication.candidates_for(drill_account(), text,
                                        ("averaging", "estimator"))
    for c in cands:
        assert set(c) == {"premise", "variable_id", "value_ids", "source", "quote",
                          "target", "context", "relevance_version", "id", "question",
                          "asked_bounds", "quote_located", "quote_not_located_because",
                          "askable", "quote_segment", "quote_chars_not_carried",
                          } | ({"band", "caption", "kind"}
                               if c["premise"] == "estimator"
                               else {"passages_considered", "passages_cut"})
        assert c["asked_bounds"] is None
    # AND THE BOOKKEEPING IS OURS AND STAYS OURS.
    prompt = PR.build_prompt(cands)
    for field in ("passages_considered", "passages_cut", "quote_segment",
                  "quote_chars_not_carried"):
        assert field not in prompt


# --------------------------------------------------------------------------
# THE SHAPE OF WHAT STAGE 1 HANDS A MODEL
# --------------------------------------------------------------------------


def test_every_candidate_is_askable_and_carries_its_own_question_and_version():
    text = paper(SPLIT_FIRST, SPLIT_SECOND)
    got = adjudication.candidates_for(drill_account(), text,
                                      ("averaging", "estimator"))
    assert {c["premise"] for c in got} == {"averaging", "estimator"}
    for c in got:
        assert c["askable"] is True
        assert c["question"] == PR.QUESTIONS[c["premise"]]
        assert c["relevance_version"] == adjudication.RELEVANCE_VERSIONS[c["premise"]]
    assert adjudication.RELEVANCE_VERSION == \
        adjudication.RELEVANCE_VERSIONS["averaging"]


def test_the_target_names_the_scope_a_true_would_move():
    """RISK 2. A paper-scoped `true` withdraws a check from EVERY mean in the
    paper, which is the largest single lever in the premise layer. It is
    inherited rather than new -- one `premises.estimator_statement` regex match
    does exactly that today -- but a model answering it is told how much it is
    moving, and so is a reader of `premise_reading.json`."""
    got = estimator_candidates(drill_account(), paper(GOVERNING_OUTSIDE))
    wide = [c for c in got if c["variable_id"] is None
            and c["source"] == "served_text"]
    assert wide
    for c in wide:
        assert c["target"] == f"the {len(c['value_ids'])} mean value(s) this paper reports"
        assert c["value_ids"] == ["val:m"]


def test_one_question_is_not_asked_five_times():
    """RISK 9. The same footnote is carried by several tables and one window is
    reached from two anchors, so without deduplication the model is asked one
    question repeatedly and paid for each time."""
    text = paper(*EVASIONS.values(), GOVERNING_OUTSIDE)
    got = adjudication.candidates_for(drill_account(footnotes=[FOOTNOTE]), text,
                                      ("averaging", "estimator"))
    keys = [(c["premise"], c["quote"], c["target"]) for c in got]
    assert len(keys) == len(set(keys))


def test_the_candidate_set_is_deterministic():
    text = paper(*EVASIONS.values(), GOVERNING_OUTSIDE, SPLIT_FIRST, SPLIT_SECOND)
    acc = drill_account(footnotes=[FOOTNOTE])
    first = adjudication.candidates_for(acc, text, ("averaging", "estimator"))
    second = adjudication.candidates_for(acc, text, ("averaging", "estimator"))
    assert first == second


def test_the_cap_is_applied_per_scope_and_after_ranking():
    """RISK 8. `MAX_REFUSAL_CANDIDATES` is a cap and not a filter only if the
    strongest evidence is ranked first, and only if one crowded scope cannot
    starve another -- a table-heavy paper must not cut the paper-level statement
    the model most needs to see."""
    decoys = tuple(f"Rates of turnout in watch {i} were reported for the season."
                   for i in range(PR.MAX_REFUSAL_CANDIDATES + 12))
    text = paper(*decoys, GOVERNING_OUTSIDE)
    got = estimator_candidates(drill_account(), text)
    wide = [c for c in got if c["variable_id"] is None and c["source"] == "served_text"]
    assert len(wide) <= PR.MAX_REFUSAL_CANDIDATES
    assert any(GOVERNING_OUTSIDE in c["quote"] for c in got), \
        "the evidence-bearing passage must survive a crowded scope"


def test_the_prompt_builds_from_these_candidates_unchanged():
    text = paper(*EVASIONS.values())
    cands = adjudication.candidates_for(drill_account(), text,
                                        ("averaging", "estimator"))
    prompt = PR.build_prompt(cands)
    assert PR.PREAMBLE in prompt
    assert prompt.count("--- CANDIDATE ") == len(cands)
    assert PR.QUESTIONS["estimator"] in prompt


# --------------------------------------------------------------------------
# THE INSTRUMENT
# --------------------------------------------------------------------------


def test_the_estimator_question_did_not_move():
    """A RESULT, NOT AN OMISSION -- and the RESULT IS ABOUT THE STRING, not about
    the constant. The proposed rewrite measured at parity with the shipped string
    (49 of 49 either way), so `QUESTIONS['estimator']` stays exactly where E1
    left it. That is what this round measured and it is what is pinned here.

    THIS USED TO PIN `PROMPT_VERSION` INSTEAD, AND ON A REASON THAT IS NOT TRUE.
    It said bumping the constant would cost "every premise's saved reply"; it
    does not. `premise_reading._reuse` compares the PROMPT'S OWN BYTES
    (`<name>.prompt.md`), the constant is not in the prompt, it is not in
    `passes`' cache key, and it is not `reconstruct.PROMPT_VERSION` -- the one
    CLAUDE.md 8p warns discards every paid reading. Round 18 added a SIXTH
    question and moved the constant with it, which reworded none of the five
    strings and discarded no reply; the pin on the constant now lives in round
    16, where the decision about it is recorded."""
    assert PR.QUESTIONS["estimator"] == (
        "Does this sentence, caption or column heading say that the target "
        "number is a weighted, standardized, adjusted, pooled, imputed, trimmed "
        "or otherwise model-estimated quantity, rather than a plain total "
        "divided by the number of subjects in this group?")


def test_no_question_moved_at_all():
    """All five are E1's own strings, or round 16's for `averaging`. A rewording
    that quietly touched one would invalidate E1's 37/37, and round 16's own
    measurement, without anything failing."""
    assert PR.QUESTIONS["bound"].startswith("Does this sentence state the numeric range")
    assert PR.QUESTIONS["step"].startswith("Does this sentence establish that each subject's")
    assert PR.QUESTIONS["correction"].startswith("Does this correction notice say")
    assert PR.QUESTIONS["averaging"].startswith(
        "The check this premise gates can only run if each subject's own value")
    assert PR.QUESTIONS["estimator"] == (
        "Does this sentence, caption or column heading say that the target "
        "number is a weighted, standardized, adjusted, pooled, imputed, trimmed "
        "or otherwise model-estimated quantity, rather than a plain total "
        "divided by the number of subjects in this group?")


def test_the_estimator_question_is_not_a_bare_list_of_adjectives():
    """WHY THE REWRITE WAS NOT NEEDED, pinned as the property that does the work.
    The string reads as a list until its last clause, which states the ARITHMETIC
    the premise actually needs -- and measured head to head, that clause is enough
    to carry seven estimators described with none of the adjectives named. Anyone
    re-proposing the rewrite needs a phrasing that defeats THIS, not an argument
    that a list is a list."""
    assert PR.QUESTIONS["estimator"].rstrip("?").endswith(
        "rather than a plain total divided by the number of subjects in this group")


def test_the_flag_is_opt_in_and_offers_exactly_the_refusal_nets():
    """The prototype stays behind its own flag exactly as the averaging one did;
    the old spelling still works, so rounds 15 and 16's instrument is unchanged;
    and the choices the flag offers come from `_NETS` rather than from a second
    hand-typed list that can drift from it."""
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), pytest.raises(SystemExit):
        _main.main(["--help"])
    help_text = buf.getvalue()
    assert "--adjudicate" in help_text
    assert "--adjudicate-averaging" in help_text
    for name in adjudication._NETS:
        assert name in help_text
        assert name in PR.REFUSAL_PREMISES
