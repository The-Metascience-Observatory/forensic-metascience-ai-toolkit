"""ROUND 25 -- A SENTENCE THAT DENIES WHOLE-NUMBER GRANULARITY MAY NOT
ESTABLISH IT. THE VOCABULARY HAD NO POLARITY.

EVERY ROUND SINCE THE FOURTH ASKED WHOSE THE CLAIM IS -- which clause (round 4),
which assertion (round 21), which constituent (round 22), which quantity (round
24). NONE OF THEM ASKED WHETHER THE SENTENCE WAS MAKING THE CLAIM OR DENYING IT.
`premises.DISCRETENESS` is a keyword test; `counted` matches inside `was not
counted`; and a paper that states in its own words that its measure is NOT
recorded in whole units was handed `discreteness_source: stated` and convicted.

MEASURED AT `ccc8c627`, on the DEFAULT path, with NO flag and no model, on a
card the paper itself says is graded to the nearest half point. Eleven ordinary
phrasings, GRIM, GRIMMER and SPRITE `impossible` on every one:

    ... and was not counted in whole units.
    ... and not counted in whole units.
    ... and was not recorded as integers.
    ... and is not discrete.
    ... and did not use a Likert item.
    ... and neither counted nor tallied in whole units.
    ... and was never a whole number.
    ... with no integers permitted.
    ... in half points instead of whole units.
    ... in half points rather than whole units.
    ... not in whole units but in half points.

THIS IS THE SHARPEST FORM THE FALSE ACCUSATION CAN TAKE, and it is worth saying
why rather than treating it as one more leak. In rounds 19, 21 and 22 the paper
said something TRUE that the reader mis-attributed -- damaged packets really were
counted in whole units, and the defect was that the claim was given to the wrong
quantity. Here the paper says the OPPOSITE of the premise the toolkit then
convicts it on, about the very variable under test, in the sentence the account
itself offered. The disclosure that should have refused the check is the thing
that bought it.

# THE RULE, AND IT IS A SCOPE RULE RATHER THAN A NOT-LIST

A NOT-LIST alone is the wrong instrument twice over. It would withdraw the
licence from `No sheets were missing; ink smears were counted in whole units`,
where the denial is about something else entirely; and it could not tell `ink
smears were counted in whole units, unlike ink density, which was not` -- which
DOES establish the step for ink smears -- from `ink smears were not counted in
whole units`. So the question is asked PER VOCABULARY MATCH, and the denial must
be shown to GOVERN that match:

  * BACKWARDS ONLY. English negation scopes forward from the negator, so a
    denial appearing AFTER the whole-unit words is not about them. That one
    asymmetry is the whole of what keeps `..., unlike Y, which was not`.
  * AND ONLY AS FAR AS THE NEAREST POLARITY RESET -- a mark that opens a
    constituent (`_CONSTITUENT`) or one of the six coordinating conjunctions
    (`_COORDINATOR`), plus the sentence-level marks. BOTH DEFINITIONS ARE
    IMPORTED FROM THE ONES THIS MODULE ALREADY OWNS rather than restated, which
    is the drift CLAUDE.md 8j names.
  * THE RESET IS INCLUDED IN THE WINDOW, because one of the six coordinators IS
    a negator: `neither counted nor tallied in whole units` would otherwise reset
    itself clean at `nor`.

# WHAT IT COSTS, WITH DENOMINATORS, ON PROSE WRITTEN FOR THIS ROUND

THE PINNED SUITE CANNOT POLICE THIS PREMISE AND A GREEN RUN IS NOT EVIDENCE.
MEASURED, by instrumenting `_denial_governing` and running the whole suite with
this file excluded: **6,161 calls across 11,466 pinned tests, and it fired 0
times.** Not one fixture in the repo contains a negated granularity sentence, in
either direction, so the suite would be green whatever this guard did. Round 24
recorded the same property from the other side (`discreteness_boundary:
unresolved`, 0 occurrences in 979 pinned inputs), and this repo has already had
to retire two "zero cost" figures measured where the shape cannot occur. So the
battery below is written here, for this, and every number in this docstring is
A/B against the guard removed (`monkeypatch` of `_denial_governing`, which IS
`ccc8c627`'s behaviour for this code path).

    honest sentences carrying a denial SOMEWHERE ELSE        24
      of which the free path licensed at ccc8c627            19
      licences lost to the guard                              0
      of those 19, ones where a negator sits physically
      BEFORE the whole-unit words, so the RESET rule is the
      only thing keeping the licence                          9   all kept

    honest sentences carrying no denial at all               22
      of which the free path licensed at ccc8c627            19
      licences lost to the guard                              0

    TOTAL 46 honest sentences, 38 licences at risk, 0 lost.

The nine are the number that matters. A guard whose zero came entirely from
denials sitting downstream of the vocabulary would be untested in the direction
that can cost coverage, and this one is not: on nine of them the denial is
upstream and only the reset rule stands between the sentence and a withdrawal.

# WHAT IT STILL GETS WRONG, IN BOTH DIRECTIONS

Named here and asserted in `TestWhatThisCostsAndWhatStillLeaks`, because a cost
table that quietly excludes its own losses is the fixture defect this repo keeps
finding.

FOUR HONEST SENTENCES LOSE A LICENCE THEY SHOULD KEEP, all one shape -- a DOUBLE
NEGATIVE, where a negator affirms integrality by denying its complement (`could
not be recorded in anything other than whole units`). The guard reads the `not`
and stops. The price is a check; the price of reading it the other way is an
accusation, and this module's standing rule decides that.

FIVE DENIALS STILL LICENSE. A denial reaching across a comma-delimited
parenthetical (`were not, in the end, counted in whole units`) or across a
bracketed one (`were not (after the 2019 revision) counted`); a denial
distributed over a coordinator (`were not averaged and counted in whole units`,
which English reads as `not [averaged and counted]` and this reader reads as
`not averaged` AND `counted`); and a denial carried by a LEXICAL VERB rather than
a particle (`readers avoided counting`, `refrained from counting`, `stopped
counting`). The last is round 21's own named residue arriving on the polarity
axis, and closing it needs a verb lexicon -- the closed list this premise has
three times been told not to grow.

AND THE PAID PATH IS DELIBERATELY UNTOUCHED. Under a model `verdict`,
`granularity_verification` replaces the SENTENCE TEST wholesale and `says_step`
is not consulted, so this guard does not constrain it. That is the design
(round 24): the model has been shown the passage and asked the real question,
and overriding its answer with a regex is what this module spent six rounds
moving away from. A model shown `was not counted in whole units` and answering
`establishes: true` is a model failure, and `adjudication_attach` is the veto
built for that class. Recorded, not changed.

# THE SIBLINGS WERE CHECKED AND ARE NOT THIS BUG

`AVERAGED`, `WEIGHTED_PERCENTAGE` and `_ESTIMATOR_STATEMENT` are polarity-blind
in exactly the same way -- each matches a sentence that DENIES what it looks for.
All three are REFUSAL premises: a blind match ADDS a refusal, which costs a check
and can never buy an accusation, so the blindness is on the safe side of
invariant 1 and is left alone. `_N_VARIES` (the varying-n vocabulary) turns out
to escape, but by an ACCIDENT rather than by design -- it requires its verb
immediately after its noun, so an inserted `do not` breaks the match -- and that
is recorded so the pass is not read as evidence it asks the question.

`SCALE_ASSERTING` is the one other LICENCE-side vocabulary and IS polarity-blind
in the dangerous direction: `the card did not run from 0 to 14` passes its gate.
It is NOT fixed here, and the reason is that the fix would not be
one-directional the way this one is -- a negated bound sentence very often still
states a bound (`no score exceeded 14` bounds at 14), so a guard there withdraws
correct bounds as readily as wrong ones and needs its own measurement.
`TestTheSiblingsAreNamedAndNotTouched` pins all of it.

THE FIXTURE PAPER IS A JOBBING PRINTWORKS PROOFING AUDIT and shares no sentence,
scale, noun or number with the pool, orchard, kiln, depot, seed-library, harbour
or lighthouse fixtures of earlier rounds.
"""

from __future__ import annotations

import statistics as st

import pytest

from metascience_agent.scaffold import checks, premises

BAD = {"suspicious", "highly_suspicious", "impossible"}

# --------------------------------------------------------------------------
# The Whitlock printworks proofing audit
# --------------------------------------------------------------------------

#: Proof legibility, graded 0-14 to the NEAREST HALF POINT. Honest by
#: construction and unreachable from any integer total, so a licence granted here
#: convicts a paper that did nothing wrong.
PROOF = [9.5, 4.0, 12.5, 7.0, 13.0, 3.5, 11.0, 6.5, 14.0, 8.0,
         5.5, 3.5, 10.5, 2.0, 12.0, 7.5, 4.5, 11.5, 9.0, 6.0,
         13.5, 3.0, 10.0, 8.5, 12.5, 5.0, 10.5, 2.5, 14.0, 7.0,
         12.0, 9.5, 4.0, 13.0, 6.5, 11.0, 8.0, 13.5, 5.5, 10.0,
         3.5, 12.5, 7.5, 11.5, 9.0]
N = len(PROOF)
P_MEAN = f"{st.fmean(PROOF):.2f}"
P_SD = f"{st.stdev(PROOF):.2f}"
assert N == 45
#: THE PROPERTY THE WHOLE FILE RESTS ON: no integer total over 45 observations
#: reproduces this mean, and a half-integer one does. A step of 1 therefore
#: makes GRIM say `impossible` about an honest measure.
assert not any(round(k / N, 2) == float(P_MEAN) for k in range(N * 14 + 1)), P_MEAN
assert any(round(t / (2 * N), 2) == float(P_MEAN) for t in range(N * 28 + 1))

#: The honest WHOLE-number companion, on the same card. It is the control that
#: says a guard which bought safety by refusing everything would fail here: its
#: licence comes from the PAPER'S OWN SENTENCE, not from its kind, so this round
#: can take it away.
SMEARS = [4, 9, 2, 7, 12, 5, 10, 3, 8, 1, 6, 11, 4, 9, 2, 7, 12, 5, 10, 3,
          8, 1, 6, 11, 4, 9, 2, 7, 12, 5, 10, 3, 8, 1, 6, 11, 4, 9, 2, 7,
          12, 5, 10, 3, 8]
assert len(SMEARS) == N
S_MEAN = f"{st.fmean(SMEARS):.2f}"
S_SD = f"{st.stdev(SMEARS):.2f}"

N_Q = "Forty-five press runs were proofed at the Whitlock works (n = 45)."
#: THE SHARPEST FORM OF THE CASE, and it needs no rival quantity anywhere. The
#: paper states its OWN granularity, in its own sentence, and it is NOT 1.
HALF = ("Proof legibility was graded to the nearest half point on a card "
        "running from 0 to 14")
#: The companion's own sentence, which must keep its licence throughout.
GRAN_S = "Ink smears were counted in whole units on a card running from 0 to 14."


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
            "coordinate": {"study_id": "study:whitlock", "group_id": "grp:runs",
                           "phase_id": None}}


def account(variables, values):
    return {"paper": {"doi": "10.0000/whitlock",
                      "title": "Proof quality in a jobbing printworks"},
            "studies": [{"id": "study:whitlock", "design": "prospective_cohort",
                         "groups": [{"id": "grp:runs", "label": "All runs",
                                     "n": N, "n_source": "text"}]}],
            "variables": variables, "values": values,
            "document": {"tables": [
                {"id": "table:1", "caption": "Table 1. Run-level proofing measures.",
                 "footnotes": []}]}}


def press_paper(sentence, *, with_smears=False):
    """The Whitlock paper whose granularity sentence for Proof legibility is
    `sentence`, and the account that reads it.

    THE MEAN AND THE SD SHARE A CELL, which is what lets GRIMMER and SPRITE run
    beside GRIM: `premises._partners` pairs on `(table, row, col)`, and a
    `Mean (SD)` column is one cell holding two values.
    """
    variables = [var("var:proof", "Proof legibility", sentence, 0, 14)]
    values = [cell("val:pm", "mean", P_MEAN, "var:proof", 1, "Mean (SD)"),
              cell("val:ps", "sd", P_SD, "var:proof", 1, "Mean (SD)"),
              cell("val:pn", "n", str(N), "var:proof", 2, "n")]
    sentences = [N_Q, sentence]
    if with_smears:
        variables.append(var("var:smears", "Ink smears", GRAN_S, 0, 14))
        values += [cell("val:sm", "mean", S_MEAN, "var:smears", 3, "Mean (SD)"),
                   cell("val:ss", "sd", S_SD, "var:smears", 3, "Mean (SD)"),
                   cell("val:sn", "n", str(N), "var:smears", 4, "n")]
        sentences.append(GRAN_S)
    text = "\n\n".join(["## Methods"] + sentences) + "\n"
    return account(variables, values), text


def smear_paper(sentence):
    """The same paper with `sentence` offered for the WHOLE-NUMBER companion.

    The coverage battery runs here rather than on the half-point card, because
    on an honest whole-unit measure a kept licence is a CHECK THAT RUNS and a
    withdrawn one is a check refused -- which is what a coverage cost is. The
    kind stays `ordinal` on purpose: a `count` would be licensed by
    `DISCRETENESS_NECESSARY_KINDS` whatever any sentence said, and nothing this
    round does could be measured on it.
    """
    variables = [var("var:smears", "Ink smears", sentence, 0, 14)]
    values = [cell("val:sm", "mean", S_MEAN, "var:smears", 1, "Mean (SD)"),
              cell("val:ss", "sd", S_SD, "var:smears", 1, "Mean (SD)"),
              cell("val:sn", "n", str(N), "var:smears", 2, "n")]
    text = "\n\n".join(["## Methods", N_Q, sentence]) + "\n"
    return account(variables, values), text


def accusations(acc, text):
    return sorted({(r["check_id"], r["severity"])
                   for r in checks.evaluate(acc, text)["checks"]
                   if r["severity"] in BAD})


def families(acc, text):
    return sorted((r["family"], r["variable_id"], r["severity"])
                  for r in checks.evaluate(acc, text)["checks"])


def verification(acc, text, vid="var:proof"):
    hay = premises.Haystack(text)
    variables = premises.readable_variables(acc)
    v = [x for x in variables if x["id"] == vid][0]
    mine = [x for x in acc["values"] if x.get("variable_id") == vid]
    return premises.granularity_verification(v, hay, variables, mine)


def every_reason(acc, text):
    return {row["reason"] for r in checks.evaluate(acc, text)["refused"]
            for row in r["reasons"]}


def licensed(sentence):
    """Did the WHOLE-NUMBER companion keep its step of 1 on this sentence?"""
    acc, text = smear_paper(sentence)
    return verification(acc, text, "var:smears")["establishes_step_of_one"]


def test_the_fixture_is_not_toothless():
    """THE ASSERTION EVERY `accusations(...) == []` IN THIS FILE RESTS ON.
    [[a-fixture-that-excludes-the-defect-region]]: with the licence standing this
    honest paper is convicted by THREE tools, so a test showing no accusation has
    shown something. And the whole-unit companion is checked and PASSES, so a fix
    that bought safety by refusing everything fails here."""
    # ROUND 26: `by each of two readers` no longer licenses a per-subject step
    # -- it states the step for a READER'S CARD -- so the plain whole-points
    # sentence is now what gives this fixture its teeth.
    acc, text = press_paper(
        "Proof legibility was graded in whole points on a card running from 0 "
        "to 14 by the duty reader.", with_smears=True)
    got = families(acc, text)
    assert ("grim", "var:proof", "impossible") in got
    assert ("grimmer", "var:proof", "impossible") in got
    assert ("sprite", "var:proof", "impossible") in got
    assert ("grim", "var:smears", "consistent") in got


# --------------------------------------------------------------------------
# THE ELEVEN LIVE FALSE ACCUSATIONS
# --------------------------------------------------------------------------

#: Every one of these was GRIM, GRIMMER and SPRITE `impossible` at `ccc8c627`,
#: and every one is a paper disclosing, in its own words, that the premise the
#: toolkit convicts it on does not hold.
DENIALS = {
    "`was not counted in whole units`":
        f"{HALF} and was not counted in whole units.",
    "`and not counted in whole units`":
        f"{HALF} and not counted in whole units.",
    "`was not recorded as integers`":
        f"{HALF} and was not recorded as integers.",
    "`is not discrete`":
        f"{HALF} and is not discrete.",
    "`did not use a Likert item`":
        f"{HALF} and did not use a Likert item.",
    "`neither counted nor tallied`":
        f"{HALF} and neither counted nor tallied in whole units.",
    "`was never a whole number`":
        f"{HALF} and was never a whole number.",
    "`with no integers permitted`":
        f"{HALF} with no integers permitted.",
    "contrast `instead of whole units`":
        "Proof legibility was graded on a card running from 0 to 14 in half "
        "points instead of whole units.",
    "contrast `rather than whole units`":
        "Proof legibility was graded on a card running from 0 to 14 in half "
        "points rather than whole units.",
    "contrast `not in whole units but in half points`":
        "Proof legibility was graded on a card running from 0 to 14 not in "
        "whole units but in half points.",
}


class TestADenialDoesNotEstablish:

    @pytest.mark.parametrize("label", sorted(DENIALS))
    def test_each_denial_no_longer_licenses_a_step(self, label):
        acc, text = press_paper(DENIALS[label])
        assert accusations(acc, text) == [], label
        assert verification(acc, text)["establishes_step_of_one"] is False, label

    @pytest.mark.parametrize("label", sorted(DENIALS))
    def test_the_record_names_the_words_that_denied_it(self, label):
        """A refusal that names nothing is worth less than one that names the
        words it refused on -- round 22's argument for
        `discreteness_unresolved_constituent`, on this axis."""
        rec = verification(*press_paper(DENIALS[label]))
        assert rec["quote_states_discreteness"] is False, label
        assert rec["discreteness_denied_by"], label
        assert rec["discreteness_denied_by"].lower() in DENIALS[label].lower(), label

    @pytest.mark.parametrize("label", sorted(DENIALS))
    def test_the_refusal_reaches_the_docket_by_name(self, label):
        """NOT folded into `discreteness_assumed`, whose sentence -- "no located
        quote shows the PAPER establishes it" -- is a false statement about a
        paper whose quote says the opposite in so many words. A silence and a
        disclosure are different facts ([[absence-must-be-representable]])."""
        acc, text = press_paper(DENIALS[label])
        got = every_reason(acc, text)
        assert "discreteness_claim_is_denied" in got, label
        assert "discreteness_assumed" not in got, label
        assert "discreteness_claim_is_denied" in checks.REASONS

    @pytest.mark.parametrize("label", sorted(DENIALS))
    def test_the_companion_is_untouched(self, label):
        """The honest whole-unit measure beside it keeps its licence and its
        check, which says the guard withdraws a licence rather than the file."""
        acc, text = press_paper(DENIALS[label], with_smears=True)
        assert verification(acc, text, "var:smears")[
            "establishes_step_of_one"] is True, label
        assert ("grim", "var:smears", "consistent") in families(acc, text), label


class TestTheGuardIsTheOnlyThingStandingThere:
    """MONOTONICITY, RUN RATHER THAN ASSERTED. The change is ONE CONJUNCT added
    to `discreteness_about`, so removing it must bring all eleven accusations
    back -- and must change nothing that refused for an older reason. A fix that
    had also moved an attribution would not reproduce that pair."""

    @pytest.mark.parametrize("label", sorted(DENIALS))
    def test_disabling_the_polarity_test_restores_the_old_accusation(
            self, label, monkeypatch):
        monkeypatch.setattr(premises, "_denial_governing",
                            lambda text, start: None)
        acc, text = press_paper(DENIALS[label])
        assert verification(acc, text)["establishes_step_of_one"] is True, label
        assert accusations(acc, text), label

    @pytest.mark.parametrize("label", sorted(DENIALS))
    def test_all_three_tools_convicted_the_honest_paper(self, label, monkeypatch):
        """THE REPRODUCTION, AT FULL WIDTH. GRIM is not the only tool resting on
        the step: GRIMMER and SPRITE take it too, and a leak here is three
        `impossible` verdicts on one honest measure."""
        monkeypatch.setattr(premises, "_denial_governing",
                            lambda text, start: None)
        acc, text = press_paper(DENIALS[label])
        got = families(acc, text)
        for family in ("grim", "grimmer", "sprite"):
            assert (family, "var:proof", "impossible") in got, (label, family)


# --------------------------------------------------------------------------
# THE COST SIDE -- HONEST PROSE, WRITTEN HERE, WITH DENOMINATORS
# --------------------------------------------------------------------------

#: (A) A DENIAL SOMEWHERE ELSE IN THE SENTENCE. Every one of these must keep its
#: licence, and the nine marked `[upstream]` are the ones that make the zero
#: worth quoting: the negator sits physically BEFORE the whole-unit words, so the
#: RESET half of the scope rule is the only thing standing between the sentence
#: and a withdrawal.
DENIAL_ELSEWHERE = {
    "[upstream] `No sheets were missing;` then the claim":
        "No sheets were missing; ink smears were counted in whole units.",
    "[upstream] `No sheets were missing, and` the claim":
        "No sheets were missing, and ink smears were counted in whole units.",
    "[upstream] `No sheets were missing and` the claim, no comma":
        "No sheets were missing and ink smears were counted in whole units.",
    "[upstream] `not averaged and were counted`":
        "Ink smears were not averaged and were counted in whole units.",
    "[upstream] `not estimated but counted`":
        "Ink smears were not estimated but counted in whole units.",
    "[upstream] `Neither reader was replaced;` then the claim":
        "Neither reader was replaced; ink smears were counted in whole units.",
    "[upstream] `cannot` in the clause before":
        "Spoiled sheets cannot be re-proofed; ink smears were counted in whole "
        "units.",
    "[upstream] `The readers did not confer;` then the claim":
        "The readers did not confer; ink smears were counted in whole units.",
    "[upstream] a fronted `With no missing values to impute,`":
        "With no missing values to impute, ink smears were counted in whole "
        "units.",
    "the denial comes after, semicolon":
        "Ink smears were counted in whole units; no sheets were missing.",
    "the denial comes after, `unlike Y, which was not`":
        "Ink smears were counted in whole units, unlike ink density, which was "
        "not.",
    "the denial comes after, `and were not averaged`":
        "Ink smears were counted in whole units and were not averaged.",
    "the denial comes after, `by readers who never conferred`":
        "Ink smears were counted in whole units by readers who never conferred.",
    "the denial comes after, `with no imputation`":
        "Ink smears were counted in whole units, with no imputation of missing "
        "sheets.",
    "the denial comes after, `though Y was not`":
        "Ink smears were counted in whole units, though ink density was not.",
    "the denial comes after, `and no partial marks were allowed`":
        "Ink smears were graded on a 15-point scale and no partial marks were "
        "allowed.",
    "the denial comes after, `without imputation`":
        "Ink smears were counted in whole units without imputation.",
    "the denial comes after, `, and no sheet was excluded`":
        "Ink smears were recorded in whole units, and no sheet was excluded.",
    "`not only ... but also` is a focus construction, not a denial":
        "Ink smears were not only counted in whole units but also checked twice.",
    "`No.` is the numero abbreviation, not a denial":
        "No. of ink smears was counted in whole units.",
    "a fronted `Although no reader was replaced,`":
        "Although no reader was replaced, ink smears were counted in whole "
        "units.",
    "two sentences, the denial in the first":
        "No imputation was performed. Ink smears were counted in whole units.",
    "a fronted `Where no sheet was spoiled,`":
        "Where no sheet was spoiled, ink smears were counted in whole units.",
    "`not a derived index; they were counted`":
        "Ink smears were not a derived index; they were counted in whole units.",
}

#: (B) NO DENIAL ANYWHERE. The guard must be exactly inert on ordinary
#: granularity prose, which is the population every earlier round's honest
#: battery lives in.
NO_DENIAL = {
    "a scale and the claim, coordinated":
        "Ink smears were graded on a card running from 0 to 14 and was counted "
        "in whole units.",
    "`, in whole points` trailing a scale":
        "Ink smears are scored from 0 to 14, in whole points.",
    "THE CANONICAL `, and` SHAPE, where a person gives the rating":
        "Ink smears were graded on a card running from 0 to 14, and each reader "
        "gave one whole-number rating on that card.",
    "a Likert item":
        "Ink smears were rated on a Likert item running from 0 to 14.",
    "an n-point scale":
        "Ink smears were rated on a 15-point scale.",
    "`recorded as integers`":
        "Ink smears were recorded as integers from 0 to 14.",
    "`tallied in whole units`":
        "Ink smears were tallied in whole units on a card from 0 to 14.",
    "`a discrete measure`":
        "Ink smears are a discrete measure running from 0 to 14.",
    "the noun-phrase head `the number of`":
        "The number of ink smears per run was recorded, from 0 to 14.",
    "a fronted adverbial before the claim":
        "At each run, ink smears were recorded in whole points, from 0 to 14.",
    "a parenthetical with no subject of its own":
        "Ink smears ran from 0 to 14 (values were recorded in whole units).",
    "`response options`":
        "Ink smears used fifteen response options, from 0 to 14.",
    "a fronted gerund":
        "Counting ink smears in whole units, readers scored 0 to 14.",
    "`whole events`":
        "Ink smears were logged as whole events, from 0 to 14.",
    "`and recorded in whole units`, elided subject":
        "Ink smears were graded on a card running from 0 to 14 and recorded in "
        "whole units.",
    "a passive with a by-phrase":
        "Ink smears were counted in whole units by each reader, from 0 to 14.",
    "`whole numbers between 0 and 14`":
        "Ink smears were whole numbers between 0 and 14.",
    "a counting rule in Methods":
        "Ink smears from 0 to 14 were counted in whole units at each inspection.",
    "a fronted `Tallying ...`":
        "Tallying ink smears in whole units, readers worked from 0 to 14.",
    "a per-reader subject":
        "Each reader counted ink smears in whole units on a 0 to 14 card.",
    "the scale as an appositive":
        "Ink smears, from 0 to 14, were graded in whole points.",
    "the scale, then the claim, after a semicolon":
        "Ink smears ran from 0 to 14; each was counted in whole units.",
}


class TestTheCostIsZeroOnHonestProse:
    """AND THE MEASUREMENT IS A/B, NEVER AN ABSOLUTE. Several of these sentences
    are refused at `ccc8c627` for reasons that predate this round -- a bound the
    sentence does not print, an attribution the reader cannot make. Counting
    those as this round's cost would be false, and counting this round's cost as
    "how many license today" would be false the other way. So every assertion
    below compares the SAME sentence with the guard on and off."""

    @pytest.mark.parametrize("label", sorted(DENIAL_ELSEWHERE))
    def test_a_denial_elsewhere_costs_no_licence(self, label, monkeypatch):
        sentence = DENIAL_ELSEWHERE[label]
        now = licensed(sentence)
        monkeypatch.setattr(premises, "_denial_governing",
                            lambda text, start: None)
        was = licensed(sentence)
        assert now == was, label

    @pytest.mark.parametrize("label", sorted(NO_DENIAL))
    def test_the_guard_is_inert_where_nothing_is_denied(self, label, monkeypatch):
        sentence = NO_DENIAL[label]
        now = licensed(sentence)
        monkeypatch.setattr(premises, "_denial_governing",
                            lambda text, start: None)
        was = licensed(sentence)
        assert now == was, label

    def test_the_denominators_are_what_the_docstring_says(self):
        """THE NUMBERS IN THE DOCSTRING, RECOMPUTED. A measured claim in a
        docstring has a shelf life and nothing fails when it expires
        ([[measured-claims-have-a-shelf-life]]); this makes it fail."""
        assert len(DENIAL_ELSEWHERE) == 24
        assert len(NO_DENIAL) == 22
        at_risk = sum(licensed(s) for s in
                      list(DENIAL_ELSEWHERE.values()) + list(NO_DENIAL.values()))
        assert at_risk == 38

    def test_the_zero_is_not_trivially_true(self):
        """THE NINE THAT MAKE IT WORTH QUOTING. A guard whose zero came entirely
        from denials sitting DOWNSTREAM of the vocabulary would never have been
        asked the question that can cost coverage. On nine of these the negator
        is upstream of a whole-unit word, so only the RESET rule keeps the
        licence -- and all nine keep it."""
        v = {"id": "var:smears", "name": "Ink smears", "label": "Ink smears",
             "printed_as": [], "kind": "ordinal"}
        upstream = [s for s in DENIAL_ELSEWHERE.values()
                    if any(premises._NEGATOR.search(s[:m.start()])
                           for m, _ in premises._discreteness_hits(s, v))]
        assert len(upstream) == 13
        kept = [s for s in upstream if licensed(s)]
        assert len(kept) == 9
        assert all(licensed(s) for s in kept)


class TestWhatThisCostsAndWhatStillLeaks:
    """NAMED RATHER THAN LEFT OUT. Round 22 reported its cost as zero and a
    verifier then measured ten; the lesson taken was that a cost table which
    excludes its own losses is worthless. These are this round's, in both
    directions, pinned so that a later change which fixes one has to come here
    and say so."""

    #: THE SENTENCE AFFIRMS INTEGRALITY BY DENYING ITS COMPLEMENT, and the guard
    #: reads the negator and stops. Four shapes, all one construction. The price
    #: is a check; reading it the other way would price it in accusations.
    DOUBLE_NEGATIVES = {
        "`could not be recorded in anything other than whole units`":
            "Ink smears could not be recorded in anything other than whole "
            "units.",
        "`were never recorded in anything other than whole units`":
            "Ink smears were never recorded in anything other than whole units.",
        "`No count was recorded outside whole units`":
            "No ink-smear count was recorded outside whole units.",
        "`could not deviate from whole units`":
            "Readers could not deviate from whole units when counting ink "
            "smears.",
    }

    #: THE SENTENCE DENIES INTEGRALITY AND THE LICENCE SURVIVES. Two are the
    #: window's own boundary (a denial reaching across a parenthetical, bracketed
    #: or comma-delimited); one is a genuine English ambiguity that this reader
    #: resolves the permissive way; two are round 21's named residue -- a denial
    #: carried by a LEXICAL VERB -- arriving on the polarity axis.
    SURVIVING_LEAKS = {
        "denial across a bracketed parenthetical":
            "Ink smears were not (after the 2019 revision) counted in whole "
            "units.",
        "denial distributed over a coordinator":
            "Ink smears were not averaged and counted in whole units.",
        "denial by the lexical verb `avoided`":
            "Readers avoided counting ink smears in whole units.",
        "denial by the lexical verb `refrained from`":
            "Readers refrained from counting ink smears in whole units.",
        "denial by the lexical verb `stopped`":
            "Readers stopped counting ink smears in whole units in 2019.",
    }

    @pytest.mark.parametrize("label", sorted(DOUBLE_NEGATIVES))
    def test_a_double_negative_loses_a_licence_it_should_keep(self, label):
        assert licensed(self.DOUBLE_NEGATIVES[label]) is False, label

    @pytest.mark.parametrize("label", sorted(DOUBLE_NEGATIVES))
    def test_and_the_price_of_that_is_a_check_and_never_an_accusation(self, label):
        """The whole argument for taking this side of the ambiguity: the
        withdrawn licence turns a check into a refusal, and a refusal accuses
        nobody."""
        acc, text = smear_paper(self.DOUBLE_NEGATIVES[label])
        assert accusations(acc, text) == [], label
        assert "discreteness_claim_is_denied" in every_reason(acc, text), label

    @pytest.mark.parametrize("label", sorted(SURVIVING_LEAKS))
    def test_these_denials_still_license_and_that_is_recorded(self, label):
        assert licensed(self.SURVIVING_LEAKS[label]) is True, label


class TestTheSiblingsAreNamedAndNotTouched:
    """THE OTHER VOCABULARIES IN THIS MODULE WERE CHECKED FOR THE SAME HOLE.
    Four have it on the safe side and one has it on the dangerous side; none is
    changed here, and this test is what stops the audit having to be redone from
    scratch to find that out."""

    def test_three_refusal_vocabularies_are_polarity_blind_on_the_safe_side(self):
        """A REFUSAL premise that matches a negated sentence ADDS a refusal,
        which costs a check and can never buy an accusation -- the safe side of
        invariant 1. Blind, and left blind, deliberately."""
        assert premises.AVERAGED.search(
            "Scores were not the mean of the two raters' ratings.")
        assert premises.WEIGHTED_PERCENTAGE.search(
            "Percentages were not weighted.")
        assert premises.estimator_statement(
            "Means were not survey-weighted.") is not None

    def test_the_fourth_escapes_by_an_accident_and_not_by_design(self):
        """`_N_VARIES` requires its verb IMMEDIATELY after its noun
        (`sample\\s+sizes?\\b\\s*var(?:y|ies|ied)`), so an inserted `do not`
        breaks the match and the negated sentence does not fire the refusal.
        That is adjacency, not polarity: recorded here so nobody reads the pass
        as evidence the pattern asks the question."""
        assert premises.varying_n_statement(
            "Sample sizes do not vary across measures.") is None
        assert premises.varying_n_statement(
            "Sample sizes vary across measures.") is not None

    def test_the_one_licence_side_sibling_is_named_and_is_not_one_directional(self):
        """`SCALE_ASSERTING` gates the BOUNDS licence and is polarity-blind in
        the dangerous direction. It is NOT fixed here, and the reason is that the
        fix would not be one-directional the way this one is: a negated bound
        sentence very often still states a bound, so a polarity guard there
        withdraws correct bounds as readily as wrong ones and needs its own
        measurement."""
        assert premises.SCALE_ASSERTING.search(
            "the card did not run from 0 to 14")
        assert premises.SCALE_ASSERTING.search(
            "no score exceeded 14")

    def test_the_paid_path_is_deliberately_not_constrained(self):
        """Under a model `verdict` the SENTENCE TEST is replaced wholesale and
        `says_step` is not consulted, so this guard does not reach it. That is
        round 24's design and not an oversight: the model was shown the passage
        and asked the real question, and `adjudication_attach` is the veto built
        for a model that answers it wrongly."""
        acc, text = press_paper(DENIALS["`was not counted in whole units`"])
        hay = premises.Haystack(text)
        variables = premises.readable_variables(acc)
        v = variables[0]
        rec = premises.granularity_verification(
            v, hay, variables, acc["values"],
            verdict={"establishes": True, "quote": DENIALS[
                "`was not counted in whole units`"], "reason": "a model said so",
                "candidate_id": "c1", "model": "test"})
        assert rec["establishes_step_of_one"] is True
        assert rec["quote_states_discreteness"] is False
        assert rec["discreteness_denied_by"]


class TestTheScopeRuleImportsRatherThanRestates:
    """CLAUDE.md 8j: this repo's recurring defect is two spellings of one rule
    written at different times with only one of them moved. The polarity window
    is built from `_CONSTITUENT` and `_COORDINATOR`, the two boundary
    definitions this module already owns, and this test fails if a third copy of
    either appears inside it."""

    def test_the_reset_is_built_from_the_modules_own_boundaries(self):
        assert premises._CONSTITUENT.pattern in premises._POLARITY_RESET.pattern
        assert premises._COORDINATOR.pattern in premises._POLARITY_RESET.pattern

    def test_the_reset_is_included_in_the_window_so_nor_is_seen(self):
        """One of the six coordinators IS a negator. If the window began AFTER
        the reset, `neither counted nor tallied in whole units` would reset
        itself clean at `nor` and license the step."""
        assert premises._denial_governing(
            "grades were neither counted nor tallied in whole units", 45)

    def test_backwards_only(self):
        """The asymmetry that keeps `..., unlike Y, which was not`."""
        s = "grades were counted in whole units, unlike density, which was not"
        assert premises._denial_governing(s, s.index("counted")) is None

    def test_the_lookback_is_bounded_and_does_not_cut_a_word_in_half(self):
        """A truncated window must not begin inside a word: `piano` cut at `no`
        would read as a denial. The first token of a truncated window is
        dropped."""
        pad = "the piano" + " x" * (premises._DENIAL_LOOKBACK // 2)
        text = pad + " counted in whole units"
        assert premises._denial_governing(text, text.index("counted")) is None
