"""ROUND 26 -- WHOLE-NUMBERED PER OBSERVATION IS NOT WHOLE-NUMBERED PER SUBJECT.
NO EARLIER ROUND ASKED "PER WHAT?"

Round 4 asked which CLAUSE the whole-number words belong to, round 21 which
ASSERTION, round 22 which CONSTITUENT, round 24 which QUANTITY, round 25 whether
the sentence was AFFIRMING or DENYING. Every one of those asks WHOSE the claim
is. None asks PER WHAT it was made.

    Varnish finish was graded in whole points at each of three settings.
    Varnish finish was graded in whole points by each of two luthiers.
    Varnish finish was graded as a whole number of quarter points.

Each attributes perfectly -- it is about the variable under test, it is
affirmed, its boundaries are clean -- and each establishes the step for a
SETTING, a LUTHIER or a QUARTER POINT. The table prints one number per
INSTRUMENT. Round 24's veto asks the model whose quantity the words describe and
the model answers CORRECTLY: they describe the target. The question it asks
cannot be made to answer this one.

MEASURED AT `a2878afb`, on the DEFAULT path, no flag and no model, on a card the
paper itself grades to the nearest half point: 22 ordinary phrasings of the
shape, **20 licensed a per-subject step of 1, and GRIM, GRIMMER and SPRITE all
returned `impossible` on every one of the 20.**

# WHERE IT BELONGS, AND THE ANSWER WAS NOT OBVIOUS

Not in `AVERAGED`. That veto asserts a POSITIVE fact -- the reported quantity IS
the mean of several observations -- and it is strong enough to withdraw the
KIND's licence too, because the mean of k whole counts is not whole. These
sentences assert no such thing: `graded in whole points at each of three
settings` does not say the table reports a mean, and the table may report the
final setting's grade or the total, either of which IS whole. Moving these
phrasings into `AVERAGED` would make this layer assert an aggregation the paper
never stated, and take a `count`'s kind licence away on the strength of it --
supplying a premise rather than narrowing one (CLAUDE.md 8d, invariant 1).

What is true is weaker and is an ABSENCE: the sentence states its granularity
about individual OBSERVATIONS and says nothing about the per-subject value. So
it is a guard inside the SENTENCE LICENCE -- `discreteness_source` falls back to
`assumed` -- and the KIND licence is untouched, exactly as round 24 leaves it
untouched and for the same reason.

# THE MAIN FINDING IS A BRANCH THAT WAS BUILT, MEASURED AND NOT SHIPPED

The obvious rule is a DISTRIBUTIVE QUANTIFIER: `at each visit`, `by every
reader`, `per sheet` withdraws unless its restrictor names the subject, which
the account declares (`subjects.unit_of_analysis`, `subjects.population`,
`paper.species_or_population` -- three fields the schema specifies and no
judgement in `premises` or `checks` had ever read). It was written. It closed
eight more accusing phrasings. IT IS NOT SHIPPED, and the reason is not tuning:

    each participant gave one whole-number rating on that scale
    each luthier gave one whole-number grade on that card

are the same sentence. The first is honest and the second is not, and the only
thing separating them is that a participant is a subject and a luthier is a
rater -- which no feature of the sentence carries. The join is not reliable
enough to rest a licence on: the FIRST of those is this repo's own canonical
known-answer paper (`test_scaffold_checks.W7_TEXT`), which declares
`species_or_population: "people"` and leaves `unit_of_analysis` null, so
`participant` misses the join and GRIM stops running on
`test_known_impossible_mean_is_impossible`.

MEASURED with that branch on: **223 pinned tests fail across 17 files.** The
shape it fires on -- `at every service`, `on each plate`, `at every drill`, `for
every plot holder` -- is what the honest licensing control of nearly every
earlier round is written in. A guard that pre-empts those fixtures does not
merely cost coverage: it makes fifty pinned adjunct cases unable to fail, which
is [[a-fixture-that-excludes-the-defect-region]] arriving from the other side.

So the bare distributive is an ATTACHMENT-SHAPED problem and belongs where round
24 put one: a model asked a NEW question -- not `whose quantity do these words
describe` but `PER WHAT is the claim made`. `adjudication_attach`'s machinery
takes it unchanged. Specified, deliberately not built: round 24's own warning is
that a batch score is not a measurement of what a run will do.

# WHAT SHIPS: TWO BRANCHES, BOTH RESTING ON THE PAPER'S OWN WORDS

  A  a CARDINAL over a plural noun (`by each of two luthiers`, `on both
     settings`, `at all four benches`, `by two independent luthiers`) -- the
     paper has SAID there is more than one observation per subject. Read after
     the discreteness vocabulary is removed, so `seven response options` and `a
     7-point scale` cannot fire it.
  B  a SUB-UNIT of the reported measure (`a whole number of quarter points`, `in
     whole half points`) -- the claim is whole in a unit the table does not
     print, so the step is 1/k of the printed unit. Read FORWARD of the
     vocabulary only, and within 30 characters.

Neither needs to know what a subject IS. `subject_terms` and the variable's own
name are used only as ESCAPES -- `across five press runs` is not a repetition --
so an account that declares nothing loses coverage, never protection.

# WHAT IT COSTS, WITH DENOMINATORS, ON PROSE WRITTEN FOR THIS ROUND

A CORRECTION TO THE PREMISE THIS ROUND WAS HANDED, and it matters for the next
one. Rounds 24 and 25 both recorded that the pinned suite cannot see this
premise (`discreteness_boundary: unresolved` 0 times in 979 inputs;
`_denial_governing` firing 0 times in 6,161 calls), and this round was briefed
that a green suite would therefore be no evidence either way. **That is not true
here, in both directions.** The first version of this guard FAILED 223 PINNED
TESTS across 17 files, because nine fixture sentences in six files used a
per-observation sentence as their honest licensing control. Each of those nine
was changed to drop the incidental cardinal, with a comment at the site; NO
ASSERTION WAS CHANGED.

But the suite still cannot measure this guard, and the reason is worth stating
rather than leaving to be rediscovered. After those corrections it fires on **18
distinct pinned passages and changes no shipped verdict**: on every one the
paper's own averaging statement already refuses (rounds 4, 11, 12, 15, 21), or
the variable is a `count` whose KIND licence this guard does not touch (round
19). The suite exercises this guard's PLUMBING and not its VERDICT. So the cost
and the benefit are measured on prose written for the purpose, A/B against the
guard disabled -- which is `a2878afb` for this code path -- and every denominator
below is asserted in `TestWhatThisCostsAndWhatStillLeaks`, not quoted from here:

    honest sentences, the whole-number claim IS the per-subject value    44
      of which the free path licensed at a2878afb                       44
      that a shipping branch REACHES at all                              8
      rescued by the subject / variable-name escape                      2
      LICENCES LOST                                                      6

    per-observation sentences (the accusation arm)                      22
      of which the free path licensed at a2878afb                       20
      CLOSED by this round                                              12
      still licensed after it                                            8

    an adversarial probe, written to find leaks and not to confirm       11
      still licensed                                                    11

The six losses are the honest number and are named in `COSTS`: every one is a
spelled cardinal beside a plural noun that is not a repetition of the
measurement (`after two weeks of training`, `using two magnifying lenses`, `by
the clerk who had completed three training sessions`, `on bellies drawn from
three benches`, `over three months of repair work`, `on quarter-size bellies`).
Separating those from `by two independent luthiers` requires knowing that a week
is not an observation, which is the same semantic question the unshipped branch
foundered on. The price is a check; the price of the licence is an accusation.

# WHAT STILL LEAKS, IN ONE LIST

Eight of the twenty-two, all bare distributives with no cardinal (`at every
bench`, `on each occasion`, `at each setting`, `for every panel`, `by every
luthier`, `by each luthier in turn`, and two where a coordinator resets the
window before the cardinal). Eleven more from an adversarial probe written to
find leaks rather than confirm the rule: repetition adverbs (`weekly`,
`repeatedly`, `twice`, `in duplicate`, `in triplicate`), bare plural agents and
occasions (`by trained raters`, `at successive checks`, `by a panel`, `at the
luthier level`), coordinated occasion names (`at intake and at release`), and a
sub-unit written as a decimal (`units of 0.5 points`). All nineteen are PINNED
in `STILL_ACCUSING` and `PROBE_LEAKS`, so none can be read as closed and a later
round that closes one owns the update. None is closed by adding a word to a
list: the repetition adverbs would need the lexicon this premise has three times
been told not to grow, and the bare plurals need to know that a check is an
occasion and a rater is an agent, which is the unshipped branch's question.

AND THE PAID PATH IS DELIBERATELY UNTOUCHED, which is round 25's call taken
again. Under a model `verdict` this function replaces the SENTENCE TEST
wholesale, and this narrowing is part of that test: it is an absence-of-licence
argument, not the arithmetic fact `AVERAGED` carries, so it is not strong enough
to overrule a model that was shown the passage and asked. A model answering
`true` on `in whole points by each of two luthiers` is a model failure of round
24's class, and the veto for that class is a QUESTION put to a model, never a
regex overruling one.

THE FIXTURE PAPER IS A VIOLIN WORKSHOP VARNISH AUDIT and shares no sentence,
scale, noun or number with the pool, orchard, kiln, depot, seed-library, harbour,
lighthouse, printworks, allotment, keying-bureau or school-canteen fixtures of
earlier rounds.
"""

from __future__ import annotations

import statistics as st
from decimal import ROUND_HALF_UP, Decimal

import pytest

from metascience_agent.scaffold import checks, premises

BAD = {"suspicious", "highly_suspicious", "impossible"}

# --------------------------------------------------------------------------
# The Halliwell violin workshop varnish audit
# --------------------------------------------------------------------------

#: Varnish finish, graded 0-16 to the NEAREST HALF POINT. Honest by construction
#: and unreachable from any integer total, so a licence granted here convicts a
#: paper that did nothing wrong.
VARNISH = [4.5, 2.5, 7.0, 3.5, 2.0, 7.0, 15.0, 13.0, 12.5, 4.5, 9.0, 5.0, 3.5,
           2.5, 4.0, 15.0, 13.5, 13.0, 13.0, 4.0, 5.5, 10.5, 12.0, 14.0, 14.0,
           2.5, 10.0, 11.0, 8.5, 3.5, 8.0, 2.5, 15.0, 14.0, 9.0, 5.5, 14.5, 9.5,
           14.0, 13.5, 8.5]
N = len(VARNISH)
V_MEAN = f"{st.fmean(VARNISH):.2f}"
V_SD = f"{st.stdev(VARNISH):.2f}"
assert N == 41


def _reaches(total, mean_s: str) -> bool:
    """Does an integer total reach this printed mean under EITHER convention?

    BOTH ARE ASKED, AND THE FIRST DRAFT OF THIS FILE ASKED ONLY ONE. `round()`
    alone said the fixture was unreachable; GRIM carries `642a6f1`'s truncation
    rescue, an integer total of 371 truncates to the mean, and every
    `impossible` this file was built on came back `consistent`. That is
    [[independence-in-process-is-not-independence]] reproduced inside the
    construction of a fixture whose whole job is to have a known answer.
    """
    q = Decimal(total) / Decimal(N)
    half = q.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return str(half) == mean_s or f"{Decimal(int(q * 100)) / Decimal(100):.2f}" == mean_s


#: THE PROPERTY THE WHOLE FILE RESTS ON: no integer total over 41 observations
#: reproduces this mean under rounding OR truncation, and a half-integer one
#: does. A step of 1 therefore makes GRIM say `impossible` about an honest
#: measure.
assert not any(_reaches(k, V_MEAN) for k in range(N * 16 + 1)), V_MEAN
assert any(_reaches(Decimal(t) / 2, V_MEAN) for t in range(N * 32 + 1))

#: The honest WHOLE-number companion on the same card. It is the control that
#: says a guard which bought safety by refusing everything would fail here: its
#: licence comes from the PAPER'S OWN SENTENCE, not from its kind, so this round
#: could take it away.
SCARS = [(i * 7 + 3) % 17 for i in range(N)]
assert len(SCARS) == N
S_MEAN = f"{st.fmean(SCARS):.2f}"
S_SD = f"{st.stdev(SCARS):.2f}"

N_Q = "Forty-one instruments were assessed in the Halliwell workshop (n = 41)."
#: The half-point card's prefix, carrying NO discreteness vocabulary of its own,
#: so every case below licenses (or fails to) purely on what it appends.
HALF = "Varnish finish was graded on a card running from 0 to 16"
#: The companion's own sentence, which must keep its licence throughout.
GRAN_S = "Bench scars were counted in whole units on a card running from 0 to 16."


def var(vid, name, quote, lower, upper, *, kind="ordinal"):
    return {"id": vid, "name": name, "label": name, "printed_as": [],
            "kind": kind, "role": None, "units": None,
            "units_source": "not_stated", "derivation": None, "derived_from": [],
            "bounds": {"source": "stated", "lower": lower, "upper": upper,
                       "quote": quote},
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
            "coordinate": {"study_id": "study:halliwell", "group_id": "grp:fiddles",
                           "phase_id": None}}


def account(variables, values, *, declare_units=True):
    """The account, with the three fields the schema asks for about WHO A ROW IS.

    `declare_units=False` is the account that leaves them null, which is what
    `TestTheEscapesAreEscapesAndNeverTriggers` measures the guard against: the
    two shipping branches are asked either way, and lose only the ESCAPE.
    """
    acc = {"paper": {"doi": "10.0000/halliwell",
                     "title": "Varnish condition in a working violin shop",
                     "species_or_population": (
                         "instruments" if declare_units else "")},
           "studies": [{"id": "study:halliwell", "design": "prospective_cohort",
                        "groups": [{"id": "grp:fiddles", "label": "All instruments",
                                    "n": N, "n_source": "text"}]}],
           "variables": variables, "values": values,
           "document": {"tables": [
               {"id": "table:1", "caption": "Table 1. Instrument-level condition.",
                "footnotes": []}]}}
    if declare_units:
        acc["subjects"] = {"population": "instruments brought in for repair",
                           "unit_of_analysis": "an instrument"}
    return acc


def varnish_paper(sentence, *, with_scars=False, declare_units=True):
    """The Halliwell paper whose granularity sentence for Varnish finish is
    `sentence`, and the account that reads it.

    THE MEAN AND THE SD SHARE A CELL, which is what lets GRIMMER and SPRITE run
    beside GRIM: `premises._partners` pairs on `(table, row, col)`, and a
    `Mean (SD)` column is one cell holding two values.
    """
    variables = [var("var:varnish", "Varnish finish", sentence, 0, 16)]
    values = [cell("val:vm", "mean", V_MEAN, "var:varnish", 1, "Mean (SD)"),
              cell("val:vs", "sd", V_SD, "var:varnish", 1, "Mean (SD)"),
              cell("val:vn", "n", str(N), "var:varnish", 2, "n")]
    sentences = [N_Q, sentence]
    if with_scars:
        variables.append(var("var:scars", "Bench scars", GRAN_S, 0, 16))
        values += [cell("val:sm", "mean", S_MEAN, "var:scars", 3, "Mean (SD)"),
                   cell("val:ss", "sd", S_SD, "var:scars", 3, "Mean (SD)"),
                   cell("val:sn", "n", str(N), "var:scars", 4, "n")]
        sentences.append(GRAN_S)
    text = "\n\n".join(["## Methods"] + sentences) + "\n"
    return account(variables, values, declare_units=declare_units), text


def scars_paper(sentence, *, declare_units=True):
    """The same paper with `sentence` offered for the WHOLE-NUMBER companion.

    The coverage battery runs here rather than on the half-point card, because on
    an honest whole-unit measure a kept licence is a CHECK THAT RUNS and a
    withdrawn one is a check refused -- which is what a coverage cost is. The
    kind stays `ordinal` on purpose: a `count` would be licensed by
    `DISCRETENESS_NECESSARY_KINDS` whatever any sentence said, and nothing this
    round does could be measured on it.
    """
    variables = [var("var:scars", "Bench scars", sentence, 0, 16)]
    values = [cell("val:sm", "mean", S_MEAN, "var:scars", 1, "Mean (SD)"),
              cell("val:ss", "sd", S_SD, "var:scars", 1, "Mean (SD)"),
              cell("val:sn", "n", str(N), "var:scars", 2, "n")]
    text = "\n\n".join(["## Methods", N_Q, sentence]) + "\n"
    return account(variables, values, declare_units=declare_units), text


def accusations(acc, text):
    return sorted({(r["check_id"], r["severity"])
                   for r in checks.evaluate(acc, text)["checks"]
                   if r["severity"] in BAD})


def families(acc, text):
    return sorted((r["family"], r["variable_id"], r["severity"])
                  for r in checks.evaluate(acc, text)["checks"])


def verification(acc, text, vid="var:varnish", verdict=None):
    hay = premises.Haystack(text)
    variables = premises.readable_variables(acc)
    v = [x for x in variables if x["id"] == vid][0]
    mine = [x for x in acc["values"] if x.get("variable_id") == vid]
    return premises.granularity_verification(
        v, hay, variables, mine, verdict,
        passages=premises.table_passages(acc, mine),
        subjects=premises.subject_terms(acc))


def every_reason(acc, text):
    return {row["reason"] for r in checks.evaluate(acc, text)["refused"]
            for row in r["reasons"]}


def licensed(sentence, *, declare_units=True):
    """Did the WHOLE-NUMBER companion keep its step of 1 on this sentence?"""
    acc, text = scars_paper(sentence, declare_units=declare_units)
    return verification(acc, text, "var:scars")["establishes_step_of_one"]


def convicted(sentence):
    """Did the HALF-POINT card keep a licence, and so get convicted?"""
    acc, text = varnish_paper(sentence)
    return verification(acc, text)["establishes_step_of_one"]


def test_the_fixture_is_not_toothless():
    """THE ASSERTION EVERY `accusations(...) == []` IN THIS FILE RESTS ON.
    [[a-fixture-that-excludes-the-defect-region]]: with the licence standing this
    honest paper is convicted by THREE tools, so a test showing no accusation has
    shown something. And the whole-unit companion is checked and PASSES, so a fix
    that bought safety by refusing everything fails here."""
    acc, text = varnish_paper(
        "Varnish finish was graded in whole points on a card running from 0 to "
        "16 by the bench luthier.", with_scars=True)
    got = families(acc, text)
    assert ("grim", "var:varnish", "impossible") in got
    assert ("grimmer", "var:varnish", "impossible") in got
    assert ("sprite", "var:varnish", "impossible") in got
    assert ("grim", "var:scars", "consistent") in got


# --------------------------------------------------------------------------
# THE TWELVE THAT THIS ROUND CLOSES
# --------------------------------------------------------------------------

#: Every one of these was GRIM, GRIMMER and SPRITE `impossible` at `a2878afb`,
#: on a card the paper itself says is graded to the nearest half point.
CLOSED = {
    # -- repeated OCCASIONS, counted -----------------------------------------
    "at each of three settings": f"{HALF} in whole points at each of three settings.",
    "at each of the three firings":
        f"{HALF} in whole points at each of the three firings.",
    "on both settings": f"{HALF} in whole points on both settings.",
    "at all four benches": f"{HALF} in whole points at all four benches.",
    "in each of the two sittings":
        f"{HALF} in whole points in each of the two sittings.",
    # -- repeated RATERS, counted --------------------------------------------
    "by each of two luthiers": f"{HALF} in whole points by each of two luthiers.",
    "by each of the three assessors":
        f"{HALF} in whole points by each of the three assessors.",
    "by both luthiers": f"{HALF} in whole points by both luthiers independently.",
    "by two independent luthiers":
        f"{HALF} in whole points by two independent luthiers.",
    # -- a whole number of SUB-UNITS -----------------------------------------
    "a whole number of quarter points":
        f"{HALF} as a whole number of quarter points.",
    "counted in whole half points": f"{HALF} and counted in whole half points.",
    "an integer number of quarter points":
        f"{HALF} as an integer number of quarter points.",
}

#: Refused at `a2878afb` too, because `DISCRETENESS` wants `whole` next to the
#: unit word and `quarter` gets in the way. Kept in the file so the sub-unit
#: family is complete and a future widening of the vocabulary cannot reopen them
#: quietly.
ALREADY_REFUSED = {
    "in whole quarter points": f"{HALF} in whole quarter points.",
    "to the nearest whole quarter point":
        f"{HALF} to the nearest whole quarter point.",
}


class TestTheTwelveLiveFalseAccusations:
    @pytest.mark.parametrize("label", sorted(CLOSED))
    def test_the_step_is_no_longer_established(self, label):
        assert not convicted(CLOSED[label])

    @pytest.mark.parametrize("label", sorted(CLOSED))
    def test_no_tool_accuses_the_paper(self, label):
        acc, text = varnish_paper(CLOSED[label])
        assert accusations(acc, text) == []

    @pytest.mark.parametrize("label", sorted(ALREADY_REFUSED))
    def test_the_family_is_complete(self, label):
        assert not convicted(ALREADY_REFUSED[label])

    def test_the_refusal_is_named_and_says_what_the_claim_was_per(self):
        """A refusal that names nothing is worth less than one naming the words
        it refused on -- round 22's argument for
        `discreteness_unresolved_constituent`, and round 25's for
        `discreteness_denied_by`."""
        acc, text = varnish_paper(CLOSED["by each of two luthiers"])
        rec = verification(acc, text)
        assert rec["discreteness_claim_is_per"] == "two luthiers"
        assert rec["discreteness_claim_is_per_in"] == "granularity_quote"
        assert rec["discreteness_source"] == premises.ASSUMED_DISCRETENESS
        assert "discreteness_claim_is_per_observation" in every_reason(acc, text)

    def test_the_quote_still_records_that_it_states_discreteness(self):
        """THE TWO FACTS ARE SEPARATE AND BOTH ARE TRUE. The sentence DOES state
        whole-number granularity -- it states it about a luthier's card -- so
        reporting `quote_states_discreteness: False` would be a false sentence
        about the paper. Only the LICENCE falls."""
        acc, text = varnish_paper(CLOSED["by each of two luthiers"])
        rec = verification(acc, text)
        assert rec["quote_states_discreteness"] is True
        assert rec["quote_about_this_variable"] is True
        assert rec["discreteness_denied_by"] is None
        assert rec["quote_reports_an_average"] is None

    def test_the_sub_unit_case_names_the_unit(self):
        acc, text = varnish_paper(CLOSED["a whole number of quarter points"])
        assert verification(acc, text)["discreteness_claim_is_per"] == "quarter points"


# --------------------------------------------------------------------------
# WHAT IT COSTS, AND WHAT IT STILL LETS THROUGH
# --------------------------------------------------------------------------

#: Honest sentences for the WHOLE-NUMBER companion, whose claim really is about
#: the value printed for one instrument. Every one licensed at `a2878afb`.
HONEST = {
    # -- no construction at all: the guard must be inert ---------------------
    "plain": "Bench scars were counted in whole units on a card running from 0 to 16.",
    "integers": "Bench scars were recorded as integers between 0 and 16.",
    "discrete": "Bench scars are discrete and were recorded on a 0 to 16 card.",
    "whole events": "Bench scars were counted in whole events on a 0 to 16 card.",
    "tallied": "Bench scars were tallied in whole units throughout the audit.",
    "number of scars": "The number of bench scars on the instrument was recorded.",
    "at the final inspection":
        "Bench scars were counted in whole units at the final inspection.",
    "by the foreman": "Bench scars were counted in whole units by the foreman.",
    "by a single luthier":
        "Bench scars were counted in whole units by a single luthier.",
    "trailing comma adjunct":
        "Bench scars were recorded on a card running from 0 to 16, in whole units.",
    # -- a DISTRIBUTIVE over the subject, which the unshipped branch would have
    #    had to get right and this one never looks at ------------------------
    "for each instrument":
        "Bench scars were counted in whole units for each instrument.",
    "for every instrument in the series":
        "Bench scars were counted in whole units for every instrument in the series.",
    "each instrument's own value":
        "Each instrument's bench scars were counted in whole units.",
    "per instrument": "Bench scars were counted in whole units per instrument.",
    "in each instrument":
        "Bench scars were counted in whole units in each instrument.",
    "once for each instrument":
        "Bench scars were counted in whole units once for each instrument.",
    "in each of the 41 instruments":
        "Bench scars were counted in whole units in each of the 41 instruments.",
    "at each instrument's final check":
        "Bench scars were counted in whole units at each instrument's final check.",
    # -- a DISTRIBUTIVE over the measured thing itself -----------------------
    "every scar": "Every bench scar on the belly was counted in whole units.",
    "each scar": "Each bench scar was counted in whole units by the proof luthier.",
    # -- a CARDINAL that must not fire: it is INSIDE the vocabulary ----------
    "seven response options":
        "Bench scars were recorded using seven response options from 0 to 16.",
    "a 7-point scale": "Bench scars were rated on a 7-point scale in whole units.",
    "three response options":
        "Bench scars were scored in whole units with three response options.",
    # -- a CARDINAL over the SUBJECT: the escape is the only thing keeping it -
    "across five instruments":
        "Bench scars were counted in whole units across five instruments.",
    "following two pilot instruments":
        "Bench scars were counted in whole units following two pilot instruments.",
    # -- a construction on the OTHER SIDE of a reset -------------------------
    "coordinator: and three auditors":
        "Bench scars were counted in whole units, and three auditors verified the "
        "ledger.",
    "semicolon: four instruments excluded":
        "Bench scars were counted in whole units; four instruments were excluded.",
    "full stop: each luthier signed":
        "Bench scars were counted in whole units. Each luthier signed the ledger.",
    "parenthesis: two clerks":
        "Bench scars were counted in whole units (two clerks kept the ledger).",
    # -- a FRACTION WORD that is not a sub-unit of measure -------------------
    "half of the bellies":
        "Bench scars were counted in whole units on half of the bellies.",
    "a quarter of an hour":
        "Bench scars were counted in whole units within a quarter of an hour.",
    "half the instruments":
        "Bench scars were counted in whole units in half the instruments seen that "
        "week.",
    "and half were re-checked":
        "Bench scars were counted in whole units and half were re-checked.",
    "half of them by the trainee":
        "Bench scars were counted in whole units, half of them by the trainee.",
    # -- ORDINALS, which branch B refuses to read as fractions ---------------
    "the third inspection":
        "Bench scars were counted in whole units at the third inspection.",
    "the fifth belly":
        "Bench scars were counted in whole units from the fifth belly onwards.",
    # -- an honest AGGREGATION that keeps its step: a SUM of whole numbers ---
    "sum over bellies":
        "Bench scars on each belly were counted in whole units, and the instrument "
        "total is reported.",
    "total across checks":
        "Bench scars were counted in whole units at each check and the total for "
        "the instrument is reported.",
}

#: THE SIX THE GUARD COSTS. Every one is a spelled cardinal beside a plural noun
#: that is NOT a repetition of the measurement. Separating them from `by two
#: independent luthiers` needs to know that a week is not an observation, which
#: is the same semantic question the unshipped branch foundered on.
COSTS = {
    "after two weeks of training":
        "Bench scars were counted in whole units after two weeks of training.",
    "using two magnifying lenses":
        "Bench scars were counted in whole units using two magnifying lenses.",
    "clerk with three training sessions":
        "Bench scars were counted in whole units by the clerk who had completed "
        "three training sessions.",
    "drawn from three benches":
        "Bench scars were counted in whole units on bellies drawn from three "
        "benches.",
    "over three months":
        "Bench scars were counted in whole units over three months of repair work.",
    "on quarter-size bellies":
        "Bench scars were counted in whole units on quarter-size bellies.",
}

#: THE EIGHT OF THE TWENTY-TWO THAT STILL ACCUSE. All bare distributives with no
#: cardinal, which is the branch that was measured and not shipped, plus two
#: where a coordinator resets the window before the cardinal.
STILL_ACCUSING = {
    "at every bench": f"{HALF} in whole points at every bench.",
    "on each occasion": f"{HALF} in whole points on each occasion.",
    "at each setting": f"{HALF} in whole points at each setting.",
    "for every panel": f"{HALF} in whole points for every panel of the belly.",
    "by every luthier": f"{HALF} in whole points by every luthier on the bench.",
    "by each luthier in turn": f"{HALF} in whole points by each luthier in turn.",
    "coordinator hides the cardinal, occasions":
        f"{HALF} in whole points per sitting, and three sittings were given to "
        f"each instrument.",
    "coordinator hides the cardinal, raters":
        f"{HALF} in whole points per luthier, and two luthiers graded every "
        f"instrument.",
}

#: AND ELEVEN MORE FROM AN ADVERSARIAL PROBE WRITTEN TO FIND LEAKS. None is
#: closed by adding a word to a list: the repetition adverbs need the lexicon
#: this premise has three times been told not to grow, and the bare plurals need
#: to know that a visit is an occasion and a rater is an agent.
PROBE_LEAKS = {
    "by trained raters": f"{HALF} in whole points by trained raters.",
    "at successive checks": f"{HALF} in whole points at successive checks.",
    "at intake and at release":
        f"{HALF} in whole points at intake and at release.",
    "weekly": f"{HALF} in whole points weekly over the repair period.",
    "repeatedly": f"{HALF} in whole points repeatedly during the repair.",
    "in duplicate": f"{HALF} in whole points in duplicate.",
    "in triplicate": f"{HALF} in whole points in triplicate.",
    "twice": f"{HALF} in whole points twice for each instrument.",
    "by a panel": f"{HALF} in whole points by a panel of luthiers.",
    "luthier-level": f"{HALF} in whole points at the luthier level.",
    "units of 0.5": f"{HALF} as a whole number of units of 0.5 points.",
}


class TestWhatThisCostsAndWhatStillLeaks:
    """THE COST TABLE, ASSERTED RATHER THAN CLAIMED IN A DOCSTRING, and the
    losses named beside the wins -- a cost table that quietly excludes its own
    losses is the fixture defect this repo keeps finding."""

    @pytest.mark.parametrize("label", sorted(HONEST))
    def test_an_honest_sentence_keeps_its_licence(self, label):
        assert licensed(HONEST[label])

    @pytest.mark.parametrize("label", sorted(HONEST))
    def test_an_honest_sentence_accuses_nobody(self, label):
        acc, text = scars_paper(HONEST[label])
        assert accusations(acc, text) == []

    @pytest.mark.parametrize("label", sorted(COSTS))
    def test_the_named_cost_is_a_refusal_and_never_an_accusation(self, label):
        """A LOST LICENCE IS A CHECK THAT DOES NOT RUN. It is not an accusation,
        which is the whole of why this direction is the safe one."""
        assert not licensed(COSTS[label])
        acc, text = scars_paper(COSTS[label])
        assert accusations(acc, text) == []

    @pytest.mark.parametrize("label", sorted(STILL_ACCUSING))
    def test_the_bare_distributive_still_licenses(self, label):
        """PINNED SO IT CANNOT BE READ AS CLOSED. These are live false
        accusations at HEAD and they are the specification for the model
        question described in this module's docstring. If a later round closes
        one, this test fails and that round owns the update."""
        assert convicted(STILL_ACCUSING[label])

    @pytest.mark.parametrize("label", sorted(PROBE_LEAKS))
    def test_the_probe_leak_still_licenses(self, label):
        assert convicted(PROBE_LEAKS[label])

    def test_the_denominators_are_what_the_docstring_says(self):
        assert (len(HONEST), len(COSTS)) == (38, 6)
        assert len(HONEST) + len(COSTS) == 44
        assert (len(CLOSED), len(ALREADY_REFUSED), len(STILL_ACCUSING)) == (12, 2, 8)
        assert len(CLOSED) + len(ALREADY_REFUSED) + len(STILL_ACCUSING) == 22
        assert len(PROBE_LEAKS) == 11

    def test_how_many_honest_sentences_reach_a_branch_at_all(self):
        """THE NUMBER THAT SAYS THE COST WAS MEASURED WHERE IT CAN OCCUR. A `0
        of 44` drawn over prose no branch can see would be
        [[a-fixture-that-excludes-the-defect-region]] a third time, which this
        project has already had to retire twice. Eight reach; the escape rescues
        two; six are lost."""
        reached = set()
        for label, sentence in {**HONEST, **COSTS}.items():
            acc, _ = scars_paper(sentence)
            v = [x for x in premises.readable_variables(acc)
                 if x["id"] == "var:scars"][0]
            if premises.discreteness_is_per(sentence, v, frozenset()) is not None:
                reached.add(label)
        assert len(reached) == 8, sorted(reached)
        assert reached >= set(COSTS)
        assert reached - set(COSTS) == {"across five instruments",
                                        "following two pilot instruments"}

    def test_every_honest_sentence_licensed_before_this_round(self):
        """THE DENOMINATOR IS CHECKED, NOT ASSUMED. A cost of `0 of 38` measured
        over sentences the free path never licensed would be measuring nothing --
        the shape retired twice in this project already. A/B is the guard
        disabled, which is `a2878afb` for this code path."""
        real = premises.discreteness_is_per
        premises.discreteness_is_per = lambda passage, var, subjects: None
        try:
            before = {lab for lab in HONEST if licensed(HONEST[lab])}
            before_cost = {lab for lab in COSTS if licensed(COSTS[lab])}
            accused = {lab for lab in CLOSED if convicted(CLOSED[lab])}
        finally:
            premises.discreteness_is_per = real
        assert before == set(HONEST), sorted(set(HONEST) - before)
        assert before_cost == set(COSTS), sorted(set(COSTS) - before_cost)
        assert accused == set(CLOSED), sorted(set(CLOSED) - accused)

    def test_the_twelve_were_convicted_by_three_tools_before_this_round(self):
        """AND THE ACCUSATION ARM'S DENOMINATOR TOO: it is not enough that the
        step was licensed; the tools have to have fired."""
        real = premises.discreteness_is_per
        premises.discreteness_is_per = lambda passage, var, subjects: None
        try:
            for label, sentence in sorted(CLOSED.items()):
                acc, text = varnish_paper(sentence)
                got = {(f, s) for f, _, s in families(acc, text)}
                assert ("grim", "impossible") in got, label
                assert ("grimmer", "impossible") in got, label
                assert ("sprite", "impossible") in got, label
        finally:
            premises.discreteness_is_per = real


class TestTheEscapesAreEscapesAndNeverTriggers:
    """`subject_terms` AND THE VARIABLE'S OWN NAME MAY ONLY KEEP A LICENCE.

    An account that declares nothing about who a row is therefore loses COVERAGE
    and never PROTECTION -- which is what keeps a nullable schema field off the
    critical path, and is the opposite of the unshipped branch, whose whole
    verdict turned on that same field."""

    def test_the_fields_the_schema_asks_for_are_read_at_last(self):
        acc, _ = scars_paper(HONEST["plain"])
        assert premises.subject_terms(acc) >= {"instrument"}
        bare, _ = scars_paper(HONEST["plain"], declare_units=False)
        assert premises.subject_terms(bare) == frozenset()

    def test_a_cardinal_over_the_subject_is_not_a_repetition(self):
        assert licensed(HONEST["across five instruments"])
        assert not licensed(HONEST["across five instruments"], declare_units=False)

    def test_an_undeclared_account_loses_coverage_and_not_protection(self):
        for label in sorted(CLOSED):
            assert not convicted(CLOSED[label])
        bare_losses = {lab for lab in HONEST
                       if not licensed(HONEST[lab], declare_units=False)}
        assert bare_losses == {"across five instruments",
                               "following two pilot instruments"}

    def test_a_cardinal_over_the_measured_thing_is_not_a_repetition(self):
        """`by each of two varnish luthiers` shares `varnish` with the variable
        and is still a repetition; its HEAD is `luthier`. The escape reads the
        noun the cardinal counts, not any word the phrase happens to contain."""
        assert not convicted(f"{HALF} in whole points by each of two varnish "
                             f"luthiers.")


class TestTheDirectionIsAConjunctOnALicence:
    """THE SAFETY ARGUMENT, EXECUTED RATHER THAN DOCUMENTED. Round 24 asserts its
    polarity over the cross-product rather than resting on a sentence, and this
    is the same rail for a free-path guard: it appears in ONE expression, ANDed,
    so it can only ever turn a True into a False."""

    ALL = {**CLOSED, **ALREADY_REFUSED, **STILL_ACCUSING, **PROBE_LEAKS,
           **HONEST, **COSTS}

    def test_it_never_turns_a_refusal_into_a_licence(self):
        real = premises.discreteness_is_per
        premises.discreteness_is_per = lambda passage, var, subjects: None
        try:
            before = {lab for lab, s in self.ALL.items() if convicted(s)}
        finally:
            premises.discreteness_is_per = real
        after = {lab for lab, s in self.ALL.items() if convicted(s)}
        assert after <= before, sorted(after - before)

    def test_it_never_turns_a_clean_paper_into_an_accused_one(self):
        real = premises.discreteness_is_per
        premises.discreteness_is_per = lambda passage, var, subjects: None
        try:
            before = {lab: accusations(*scars_paper(s))
                      for lab, s in self.ALL.items()}
        finally:
            premises.discreteness_is_per = real
        for lab, s in self.ALL.items():
            assert accusations(*scars_paper(s)) <= before[lab], lab

    def test_the_kind_licence_is_untouched(self):
        """A COUNT OF THINGS IS A WHOLE NUMBER OF THINGS whatever adjunct the
        sentence carries, and the sentence does not say the reported value is a
        mean -- it may be the final setting's count, or the total. Withdrawing
        the KIND licence here would assert the aggregation, which is supplying a
        premise rather than narrowing one. `AVERAGED` withdraws it because the
        mean of k whole counts is not whole; this does not."""
        sentence = CLOSED["by each of two luthiers"]
        variables = [var("var:varnish", "Varnish finish", sentence, 0, 16,
                         kind="count")]
        values = [cell("val:vm", "mean", V_MEAN, "var:varnish", 1, "Mean (SD)"),
                  cell("val:vn", "n", str(N), "var:varnish", 2, "n")]
        acc = account(variables, values)
        text = "\n\n".join(["## Methods", N_Q, sentence]) + "\n"
        rec = verification(acc, text)
        assert rec["kind_makes_it_necessary"] is True
        assert rec["discreteness_source"] == premises.NECESSARY_DISCRETENESS
        assert rec["establishes_step_of_one"] is True
        assert rec["discreteness_claim_is_per"] == "two luthiers"

    def test_an_average_still_withdraws_the_kind_licence(self):
        """THE CONTRAST THAT MAKES THE TEST ABOVE MEAN SOMETHING. The same
        variable, the same kind, a sentence that says the reported figure IS the
        mean -- and the kind licence falls, as it always has."""
        sentence = ("Varnish finish was counted in whole points by each of two "
                    "luthiers, and the two cards were averaged.")
        variables = [var("var:varnish", "Varnish finish", sentence, 0, 16,
                         kind="count")]
        values = [cell("val:vm", "mean", V_MEAN, "var:varnish", 1, "Mean (SD)"),
                  cell("val:vn", "n", str(N), "var:varnish", 2, "n")]
        acc = account(variables, values)
        text = "\n\n".join(["## Methods", N_Q, sentence]) + "\n"
        rec = verification(acc, text)
        assert rec["kind_makes_it_necessary"] is False
        assert rec["establishes_step_of_one"] is False


class TestOneUndistributedMatchNoLongerLicenses:
    """WHAT ROUND 26 BELIEVED HERE, AND WHAT ROUND 27 MEASURED. This class
    pinned the `all` in `discreteness_is_per` -- a refusal had to be the
    passage's LAST WORD on granularity, so a sentence scoping one whole-number
    claim to a rater and making another about the reported figure kept its step.

    THE RESCUE COULD NOT BE HAD SAFELY. `SENTENCE` below and the round-27 probe
    `... at each of three inspections, and the card was printed in whole units.`
    are the same sentence: a per-observation main clause coordinating a second
    assertion whose subject names something the account never declared. One
    means the REPORTED VALUE is whole and the other means the INSTRUMENT is, and
    no feature of the words separates them -- the same shape as round 26's own
    unshipped distributive branch (`each participant` / `each luthier`). Five of
    seven such sentences licensed a step of 1 on a half-point card and returned
    GRIM, GRIMMER and SPRITE `impossible`.

    So the licence is gone and this class now pins the COST, which is what
    changed rather than the assertion: `tests/test_scaffold_checks_round27.py`
    carries the measurement and the honest prose it was measured on."""

    SENTENCE = ("Bench scars were counted in whole units by each of two luthiers, "
                "and the figure entered in the ledger for the instrument is itself "
                "recorded in whole units.")

    def test_the_second_assertion_no_longer_keeps_the_licence(self):
        assert not licensed(self.SENTENCE)

    def test_and_the_first_one_alone_would_not_either(self):
        assert not licensed("Bench scars were counted in whole units by each of "
                            "two luthiers.")

    def test_the_cost_is_a_check_and_never_an_accusation(self):
        """THE PRICE OF THE REFUSAL, STATED WHERE IT IS PAID. The variable is
        honestly whole-numbered, so what is lost is the four checks its step
        of 1 buys -- and nothing is accused either way."""
        acc, text = varnish_paper(self.SENTENCE)
        assert accusations(acc, text) == []
        acc, text = scars_paper(self.SENTENCE)
        assert accusations(acc, text) == []


class TestThePaidPathIsUntouched:
    """ROUND 25'S CALL, TAKEN AGAIN. Under a verdict this function replaces the
    SENTENCE TEST wholesale, and this narrowing is part of that test. It is an
    absence-of-licence argument rather than the arithmetic fact `AVERAGED`
    carries, so it may not overrule a model that was shown the passage. Recorded
    here as residue: a model answering `true` on one of these is a model failure
    of round 24's class."""

    def test_a_model_true_still_grants_the_step(self):
        acc, text = varnish_paper(CLOSED["by each of two luthiers"])
        verdict = {"establishes": True, "quote": CLOSED["by each of two luthiers"],
                   "reason": "recorded", "model": "sonnet"}
        rec = verification(acc, text, verdict=verdict)
        assert rec["establishes_step_of_one"] is True

    def test_and_the_averaging_veto_still_beats_a_model_true(self):
        sentence = (f"{HALF} in whole points by each of two luthiers, and each "
                    f"instrument's figure is the mean of the two cards.")
        acc, text = varnish_paper(sentence)
        verdict = {"establishes": True, "quote": sentence, "reason": "recorded",
                   "model": "sonnet"}
        rec = verification(acc, text, verdict=verdict)
        assert rec["establishes_step_of_one"] is False


class TestTheBareDistributiveIsNotShipped:
    """THE DECISION, PINNED WITH THE EVIDENCE THAT MADE IT. Anyone reading this
    file will reach for the distributive rule; these are the two sentences that
    say why it cannot be a rule, and the canonical paper that says why the join
    cannot rescue it."""

    HONEST_SHAPE = ("Bench scars were graded on a card running from 0 to 16, and "
                    "each luthier gave one whole-number grade on that card.")
    ACCUSING_SHAPE = (f"{HALF}, and each luthier gave one whole-number grade on "
                      f"that card.")

    def test_the_two_sentences_are_the_same_sentence(self):
        """One licenses honestly and one manufactures an `impossible`, and the
        only difference is what the noun DENOTES. Both are licensed, which is the
        state this round leaves them in, deliberately."""
        assert licensed(self.HONEST_SHAPE)
        assert convicted(self.ACCUSING_SHAPE)

    def test_the_repos_own_canonical_paper_is_this_shape(self):
        """`test_scaffold_checks.W7_TEXT` -- `each participant gave one
        whole-number rating on that scale`, with `species_or_population:
        "people"` and `unit_of_analysis` null. The join that the distributive
        branch needed MISSES here, which is what took GRIM off
        `test_known_impossible_mean_is_impossible`."""
        from tests import test_scaffold_checks as canonical
        assert "each participant gave one whole-number" in canonical.W7_TEXT
        assert canonical.W7_P1["paper"]["species_or_population"] == "people"
        assert canonical.W7_P1["subjects"]["unit_of_analysis"] is None

    def test_no_distributive_quantifier_is_read_as_a_restrictor(self):
        """THE GREP RAIL. If a later round reintroduces the branch it must do so
        deliberately, with its own measurement, and this test is where it says
        so."""
        import inspect
        src = inspect.getsource(premises._per_governing)
        assert "_DISTRIBUTIVE" not in src
        assert not hasattr(premises, "_DISTRIBUTIVE")


class TestTheWindowAndTheDirection:
    """THE TWO SCOPE RULES, EACH WITH THE MEASURED CASE THAT SET IT."""

    def test_a_coordinator_resets_the_window(self):
        """`counted in whole units, and three auditors verified the ledger` is
        two assertions and the second one's cardinal is not about the first."""
        assert licensed(HONEST["coordinator: and three auditors"])

    def test_a_comma_does_not_reset_the_window(self):
        """An adjunct routinely sits behind a comma, which is the one place this
        window is wider than `_POLARITY_RESET`'s."""
        assert not convicted(f"{HALF} in whole points, by each of two luthiers.")

    def test_the_sub_unit_is_read_forward_only(self):
        """MEASURED: without the direction and the reach, round 22's own
        canonical honest sentence -- where the half point belongs to the variable
        and the whole units to a rival -- fired on its `half point`, which would
        have made fifty pinned adjunct cases unable to fail.

        THE ASSERTION IS ON THIS ROUND'S FIELD AND NOT ON THE LICENCE, which is
        the only honest way to test it: that sentence is refused anyway, by round
        19's rule that a rival's discreteness may not be read as this variable's
        (`discreteness_belongs_to: Varnish finish`). Asserting the licence would
        have been an assertion about a rule this round did not write, and it
        would pass or fail for reasons that have nothing to do with sub-units."""
        acc, text = scars_paper(
            "Varnish finish was graded to the nearest half point on a card "
            "running from 0 to 16, with bench scars counted in whole units.")
        rec = verification(acc, text, "var:scars")
        assert rec["discreteness_claim_is_per"] is None
        assert rec["discreteness_belongs_to"] == "Varnish finish"

    def test_a_sub_unit_behind_the_vocabulary_within_reach_is_still_not_read(self):
        """The same rule with the rival removed, so the licence IS the test."""
        assert licensed("Bench scars were recorded to the nearest half point on "
                        "the trial card and were counted in whole units.")

    def test_the_window_is_bounded_so_a_folded_row_is_not_quadratic(self):
        """`_DENIAL_LOOKBACK`'s reason in both directions: a converter's folded
        table row is one sentence of many thousands of characters."""
        assert premises._PER_REACH == 400
        filler = "instrument condition was logged " * 40
        assert licensed(f"Bench scars were counted in whole units. {filler} "
                        f"Two luthiers were on the bench that season.")


class TestTheVocabularyIsRemovedBeforeTheCardinalIsRead:
    """THE ONE TRICK THAT KEEPS THE COMMONEST HONEST GRANULARITY SENTENCE. A
    Likert item's own number is PART of the whole-number claim, not a count of
    how many times it was made -- `_run_names_something`'s move, reused."""

    @pytest.mark.parametrize("label", ["seven response options", "a 7-point scale",
                                       "three response options"])
    def test_a_scale_size_is_not_a_repetition_count(self, label):
        assert licensed(HONEST[label])

    def test_a_digit_that_is_part_of_a_longer_number_is_not_a_cardinal(self):
        assert licensed("Bench scars were counted in whole units to within 0.5 "
                        "of the ledger total.")

    def test_a_large_digit_is_the_papers_own_n(self):
        """`a paper writes its own n in digits` -- `AVERAGED`'s measured
        asymmetry, from the other side."""
        assert licensed(HONEST["in each of the 41 instruments"])
