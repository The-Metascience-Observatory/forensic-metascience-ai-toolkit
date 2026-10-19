"""ROUND 22 -- AN ASSERTION BOUNDARY THIS READER CANNOT RESOLVE MAY NOT SUPPLY
A PREMISE, AND THE RULE FAILS CLOSED INSTEAD OF GROWING A THIRD LIST.

THE DEFECT IS ROUND 19's AND ROUND 21's, ARRIVING THROUGH A THIRD DOOR. Round
19 closed three phrasings by name. Round 21 stopped asking WHERE THE CLAUSE ENDS
and asked WHICH ASSERTION INSIDE IT the discreteness word belongs to, which
closed the COORDINATORS and the PARENTHESES. Neither can see a SUBORDINATE
CLAUSE or an ADJUNCT: neither is a coordinator, neither is a bracket, so
`assertion_segments` returns the WHOLE SENTENCE as one segment,
`_assertion_subject` answers with the MAIN CLAUSE's subject -- which IS the
variable under test -- and a whole-unit word belonging to something else buys a
step of 1.

TWENTY ORDINARY PHRASINGS WERE MEASURED ACCUSING against the unchanged tree at
`6688c9d3`, on the default path, with no flag, on a card the paper itself says
is graded TO THE NEAREST HALF POINT. Eight adjuncts (`, together with a count of
X`, `, with X counted in whole units`, `, alongside`, `, as well as`, `, plus`),
eleven subordinators (`, because`, `, after`, `, since`, `, as`, `, when`,
`, where`, `, before`, `, once`, `, whereby`, and the bare forms of two of them
with no comma at all), and four absolutes and participials (`, X being counted`,
`, X counted in whole units`, `, the stewards having counted X`, an appositive).
GRIM AND SPRITE `impossible`, both, on every one. The same facts after a
SEMICOLON refused, and the same facts about a DECLARED rival refused.

AND THE RECORD WAS SILENT, which is what made it dangerous to audit:
`discreteness_source: stated`, `establishes_step_of_one: True`,
`discreteness_belongs_to: None`, `reasons: []`, and a `discreteness_assertion`
holding the entire sentence -- which DOES name the variable. An auditor reading
that premise saw a licence that looked correct.

SO THE RULE IS NOT A TWENTY-FIRST SUBORDINATOR. CLAUDE.md records three times
that one more member of a closed list buys exactly one round, and this premise
has now paid that twice. THE ACTUAL DEFECT IS A FAIL-OPEN: where the boundary
cannot be determined the code falls back on the host clause's attribution and
GRANTS, which inverts invariant 1 -- a derived boundary may NARROW a premise and
may never SUPPLY one. An unparsed boundary was supplying one.

THE RULE, IN ONE SENTENCE. A licence may rest only on an assertion this reader
has delimited, and two things defeat that without punctuation it already cuts
on: a COMMA opens a constituent whose head and attachment are unknown, and a
SECOND SUBJECT-PLUS-FINITE-VERB opens a predication whose boundary is unknown.
Where the whole-unit word sits in either, the licence is withheld and the record
says so by name. Neither mechanism is a vocabulary: one is a mark, the other is
the finite-verb probe and the content/generic split this module already has.

WHAT SURVIVES, AND WHY IT IS NOT A RULE THAT REFUSES EVERYTHING. Inheritance
still works for a bare predicate CONTIGUOUS with its clause (`(values were
recorded in whole units)`, `and was scored in whole points`, the canonical
`, and each keeper gave one whole-number grade`), and a constituent after a
comma may still earn a licence by NAMING THIS VARIABLE ITSELF, which keeps the
commonest shape in methods prose: `At each watch, lantern polish was recorded in
whole points.`

THE COST IS MEASURED AND IT IS NOT ZERO -- see `TestWhatThisCosts`. Two of
twenty-four honest phrasings now refuse, both genuinely indistinguishable from a
leak: a trailing adjunct that leaves a bare participle behind (`, recorded in
whole units` -- while `, in whole points`, which leaves nothing behind, keeps
its licence), and a granularity stated in a SECOND predication (`The cards were
archived once lantern polish was recorded in whole points`). Measured the same
way on two further fixtures built by other sessions: 1 of 18 and 1 of 22. Named
here rather than left out, because a cost table that quietly excludes its own
losses is the fixture defect this repo keeps finding -- and because the last fix
on this premise reported its cost as zero and a verifier then measured ten.

THE FIXTURE PAPER IS A LIGHTHOUSE WATCH AUDIT and shares no sentence, scale,
noun or number with the pool, orchard, kiln or depot fixtures of earlier rounds.
"""

from __future__ import annotations

import statistics as st

import pytest

from metascience_agent.scaffold import checks, premises

BAD = {"suspicious", "highly_suspicious", "impossible"}

# --------------------------------------------------------------------------
# The Penhale lighthouse watch audit
# --------------------------------------------------------------------------

#: Lantern polish, graded 0-16 in whole points by each of TWO keepers; a watch's
#: figure is the mean of the two cards, so it moves in HALF points, and the
#: paper says so. Honest by construction and unreachable from any integer total,
#: which is what makes a licence granted here a conviction of a paper that did
#: nothing wrong.
POLISH = [9.5, 4.0, 12.5, 7.0, 15.0, 3.5, 11.0, 6.5, 16.0, 8.0,
          5.5, 3.5, 10.5, 2.0, 14.5, 7.5, 4.5, 12.0, 9.0, 6.0,
          15.5, 3.0, 11.5, 8.5, 13.5, 5.0, 10.0, 2.5, 14.0, 7.0,
          12.5, 9.5, 4.0, 16.0, 6.5, 11.0, 8.0, 13.0, 5.5, 10.5,
          3.5, 15.0, 7.5, 12.0, 11.0, 4.5, 14.5, 6.0, 11.5]
N = len(POLISH)
P_MEAN = f"{st.fmean(POLISH):.2f}"
P_SD = f"{st.stdev(POLISH):.2f}"
assert N == 49
assert not any(round(k / N, 2) == float(P_MEAN) for k in range(N * 16 + 1)), P_MEAN
assert any(round(t / (2 * N), 2) == float(P_MEAN) for t in range(N * 32 + 1))

#: The honest WHOLE-number companion: an ordinary integer count, licensed by its
#: KIND and untouched by anything in this round. It is the control that says a
#: fix which bought safety by refusing everything would fail here.
SIGNALS = [3, 8, 1, 6, 11, 4, 9, 2, 7, 12, 5, 10, 3, 8, 1, 6, 11,
           4, 9, 2, 7, 12, 5, 10, 3, 8, 1, 6, 11, 4, 9, 2, 7, 12,
           5, 10, 3, 8, 1, 6, 11, 4, 9, 2, 7, 12, 5, 10, 3]
assert len(SIGNALS) == N
S_MEAN = f"{st.fmean(SIGNALS):.2f}"
S_SD = f"{st.stdev(SIGNALS):.2f}"

N_Q = "Forty-nine watches were observed in the Penhale lighthouse audit (n = 49)."
SCALE = "Lantern polish was graded on a card running from 0 to 16"
#: THE SHARPEST FORM OF THE CASE, and it needs no averaging anywhere. The paper
#: states its OWN granularity and it is NOT 1. The only whole-unit word in the
#: sentence belongs to something else.
HALF = ("Lantern polish was graded to the nearest half point on a card running "
        "from 0 to 16")
GRAN_S = "Fog signal tests were counted as whole tests, from 0 to 40 per watch."


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
            "coordinate": {"study_id": "study:penhale", "group_id": "grp:watches",
                           "phase_id": None}}


def account(variables, values):
    return {"paper": {"doi": "10.0000/penhale",
                      "title": "Lantern upkeep at a coastal light"},
            "studies": [{"id": "study:penhale", "design": "prospective_cohort",
                         "groups": [{"id": "grp:watches", "label": "All watches",
                                     "n": N, "n_source": "text"}]}],
            "variables": variables, "values": values,
            "document": {"tables": [
                {"id": "table:1", "caption": "Table 1. Watch-level upkeep measures.",
                 "footnotes": []}]}}


def watch_paper(sentence, *, with_signals=False):
    """The Penhale paper whose granularity sentence for Lantern polish is
    `sentence`, and the account that reads it."""
    variables = [var("var:polish", "Lantern polish", sentence, 0, 16)]
    values = [cell("val:pm", "mean", P_MEAN, "var:polish", 1, "Mean (SD)"),
              cell("val:ps", "sd", P_SD, "var:polish", 2, "Mean (SD)"),
              cell("val:pn", "n", str(N), "var:polish", 3, "n")]
    sentences = [N_Q, sentence]
    if with_signals:
        variables.append(var("var:signals", "Fog signal tests", GRAN_S, 0, 40,
                             kind="count"))
        values += [cell("val:sm", "mean", S_MEAN, "var:signals", 1, "Mean (SD)"),
                   cell("val:ss", "sd", S_SD, "var:signals", 2, "Mean (SD)"),
                   cell("val:sn", "n", str(N), "var:signals", 3, "n")]
        sentences.append(GRAN_S)
    text = "\n\n".join(["## Methods"] + sentences) + "\n"
    return account(variables, values), text


def accusations(acc, text):
    return sorted({(r["check_id"], r["severity"])
                   for r in checks.evaluate(acc, text)["checks"]
                   if r["severity"] in BAD})


def families(acc, text):
    return sorted((r["family"], r["variable_id"], r["severity"])
                  for r in checks.evaluate(acc, text)["checks"])


def verification(acc, text, vid="var:polish"):
    hay = premises.Haystack(text)
    variables = premises.readable_variables(acc)
    v = [x for x in variables if x["id"] == vid][0]
    mine = [x for x in acc["values"] if x.get("variable_id") == vid]
    return premises.granularity_verification(v, hay, variables, mine)


def every_reason(acc, text):
    got = checks.evaluate(acc, text)
    return {row["reason"] for r in got["refused"] for row in r["reasons"]}


def test_the_fixture_is_not_toothless():
    """THE ASSERTION EVERY `accusations(...) == []` IN THIS FILE RESTS ON.
    [[a-fixture-that-excludes-the-defect-region]]: with the licence standing
    this paper IS convicted, so a test showing no accusation has shown
    something. And the honest whole-unit companion is checked and PASSES, so a
    fix that bought safety by refusing everything fails here."""
    # ROUND 26: `by each of two keepers` no longer licenses a per-subject step.
    # WORTH READING RATHER THAN SKIMMING -- this fixture was the evidence FOR
    # round 26: it used a two-keeper sentence as the device that makes an honest
    # HALF-POINT card look integer, while `TestTheHonestPapersKeepTheirStep`
    # listed the same sentence as an honest licence. Both at once, and the device
    # works precisely because the sentence does not establish a per-subject step.
    acc, text = watch_paper(
        "Lantern polish was graded in whole points on a card running from 0 to "
        "16 by the duty keeper.", with_signals=True)
    got = families(acc, text)
    assert ("grim", "var:polish", "impossible") in got
    assert ("grim", "var:signals", "consistent") in got


# --------------------------------------------------------------------------
# THE TWENTY LIVE FALSE ACCUSATIONS
# --------------------------------------------------------------------------

#: Every one of these was GRIM AND SPRITE `impossible` at `6688c9d3` on the
#: half-point card below, and every one is ordinary methods prose. `chipped
#: prisms` and `keeper workload` are quantities the PAPER names and the ACCOUNT
#: does not declare -- the gap round 19 and round 21 each closed one door of.
LEAKS = {
    "adjunct `, together with a count of X`":
        f"{HALF}, together with a count of chipped prisms.",
    "adjunct `, with X counted in whole units`":
        f"{HALF}, with chipped prisms counted in whole units.",
    "adjunct `, alongside a Likert item on X`":
        f"{HALF}, alongside a Likert item on keeper workload.",
    "adjunct `, as well as a 7-point scale for X`":
        f"{HALF}, as well as a 7-point scale for keeper workload.",
    "adjunct `, plus a 7-point scale for X`":
        f"{HALF}, plus a 7-point scale for keeper workload.",
    "subord `, because X were counted`":
        f"{HALF}, because chipped prisms were counted in whole units.",
    "subord `, after X were counted`":
        f"{HALF}, after chipped prisms were counted in whole units.",
    "subord `, since X were counted`":
        f"{HALF}, since chipped prisms were counted in whole units.",
    "subord `, as X were counted`":
        f"{HALF}, as chipped prisms were counted in whole units.",
    "subord `, when X were counted`":
        f"{HALF}, when chipped prisms were counted in whole units.",
    "subord `, where X were counted`":
        f"{HALF}, where chipped prisms were counted in whole units.",
    "subord `, before X were counted`":
        f"{HALF}, before chipped prisms were counted in whole units.",
    "subord `, once X were counted`":
        f"{HALF}, once chipped prisms were counted in whole units.",
    "subord `, whereby X were recorded as integers`":
        f"{HALF}, whereby chipped prisms were recorded as integers.",
    "subord bare `because`, no comma at all":
        f"{HALF} because chipped prisms were counted in whole units.",
    "subord bare `after`, no comma at all":
        f"{HALF} after chipped prisms were counted in whole units.",
    "absolute `, X being counted`":
        f"{HALF}, chipped prisms being counted in whole units.",
    "participial `, X counted in whole units`":
        f"{HALF}, chipped prisms counted in whole units.",
    "absolute `, the keepers having counted X`":
        f"{HALF}, the keepers having counted chipped prisms in whole units.",
    "appositive `, a measure separate from X, counted ...`":
        f"{HALF}, a measure quite separate from chipped prisms, counted in "
        f"whole units.",
}

#: The same facts punctuated or worded the ways this repo ALREADY reads. Each
#: refused at `6688c9d3` and must refuse now: that they did is the tell that the
#: boundary was the whole difference, and it must stay a tell.
CONTROLS = {
    "the half-point sentence alone": f"{HALF}.",
    "the same fact after a semicolon":
        f"{HALF}; chipped prisms were counted in whole units.",
    "the same fact after `, and`":
        f"{HALF}, and chipped prisms were counted in whole units.",
    "the same fact after a bare `while`":
        f"{HALF} while chipped prisms were counted in whole units.",
    "a parenthetical with an auxiliary":
        f"{HALF} (chipped prisms were counted in whole units).",
}


class TestAnUnresolvedBoundaryDoesNotLicense:

    @pytest.mark.parametrize("label", sorted(LEAKS))
    def test_each_leak_no_longer_licenses_a_step(self, label):
        acc, text = watch_paper(LEAKS[label])
        assert accusations(acc, text) == [], label
        assert verification(acc, text)["establishes_step_of_one"] is False, label

    @pytest.mark.parametrize("label", sorted(LEAKS))
    def test_the_record_says_the_boundary_could_not_be_resolved(self, label):
        """THE HALF OF THIS ROUND THAT IS NOT THE VERDICT. A leaked licence used
        to read `discreteness_belongs_to: None` and `reasons: []`, so the defect
        was invisible to an auditor reading the account. A refusal that names
        nothing is worth less than one that names the words it refused on."""
        rec = verification(*watch_paper(LEAKS[label]))
        assert rec["discreteness_boundary"] == "unresolved", label
        assert rec["discreteness_assertion"] is None, label
        assert rec["discreteness_unresolved_constituent"], label
        assert rec["discreteness_unresolved_constituent"] in LEAKS[label], label

    @pytest.mark.parametrize("label", sorted(LEAKS))
    def test_the_refusal_reaches_the_docket_by_name(self, label):
        """Not folded into `discreteness_assumed`, whose sentence -- "no located
        quote shows the PAPER establishes it" -- is the wrong one here: a quote
        DID state discreteness, in words this reader could not attribute."""
        acc, text = watch_paper(LEAKS[label])
        got = every_reason(acc, text)
        assert "discreteness_assertion_boundary_unresolved" in got, label
        assert "discreteness_assertion_boundary_unresolved" in checks.REASONS

    @pytest.mark.parametrize("label", sorted(LEAKS))
    def test_a_declared_rival_was_never_the_mechanism(self, label):
        """Declaring the other quantity changes nothing, which is what says the
        fix is not `names_another_variable` reaching further."""
        acc, text = watch_paper(LEAKS[label], with_signals=True)
        assert verification(acc, text)["establishes_step_of_one"] is False, label

    @pytest.mark.parametrize("label", sorted(CONTROLS))
    def test_the_controls_that_already_refused_still_refuse(self, label):
        acc, text = watch_paper(CONTROLS[label])
        assert accusations(acc, text) == [], label
        assert verification(acc, text)["establishes_step_of_one"] is False, label

    def test_the_whole_unit_companion_is_untouched(self):
        """A count is a count whatever this rule decides: `var:signals` is
        licensed by its KIND, which this round does not touch."""
        acc, text = watch_paper(LEAKS["subord `, because X were counted`"],
                                with_signals=True)
        rec = verification(acc, text, "var:signals")
        assert rec["kind_makes_it_necessary"] is True
        assert ("grim", "var:signals", "consistent") in families(acc, text)


class TestTheNewTestIsTheOnlyThingStandingThere:
    """MONOTONICITY, RUN RATHER THAN ASSERTED. The change is exactly ONE
    CONJUNCT added to the conditions round 21 already applies, so it can only
    ever REMOVE a licence -- and the way to show that is to take the conjunct
    away and watch the twenty accusations come back. A fix that had also moved
    an attribution would not reproduce them."""

    @pytest.mark.parametrize("label", sorted(LEAKS))
    def test_disabling_the_boundary_test_restores_the_old_accusation(
            self, label, monkeypatch):
        monkeypatch.setattr(premises, "_discreteness_is_attributable",
                            lambda var, segment, others: (True, None))
        acc, text = watch_paper(LEAKS[label])
        assert verification(acc, text)["establishes_step_of_one"] is True, label
        assert accusations(acc, text), label

    @pytest.mark.parametrize("label", sorted(CONTROLS))
    def test_disabling_it_does_not_restore_anything_on_the_controls(
            self, label, monkeypatch):
        """The controls refuse for reasons that predate this round, so removing
        this round's conjunct must not change them. That is what says the twenty
        above are this conjunct's doing and not a second edit's."""
        monkeypatch.setattr(premises, "_discreteness_is_attributable",
                            lambda var, segment, others: (True, None))
        acc, text = watch_paper(CONTROLS[label])
        assert verification(acc, text)["establishes_step_of_one"] is False, label


# --------------------------------------------------------------------------
# THE COST SIDE -- TWENTY-TWO HONEST PHRASINGS, AND TWENTY KEEP THEIR STEP
# --------------------------------------------------------------------------

HONEST = {
    "passive, its own subject":
        "Lantern polish was graded in whole points on a card running from 0 to 16.",
    "passive, `as an integer`":
        "Lantern polish was recorded as an integer from 0 to 16.",
    "a plural head noun":
        "Lantern polish scores were counted in whole units.",
    "a per-subject possessive":
        "Each watch's lantern polish was tallied in whole points.",
    "a point scale":
        "Lantern polish was rated on a 9-point scale.",
    "a Likert item":
        "Lantern polish was assessed with a Likert item.",
    "a coordinated verb phrase with an elided subject":
        "Lantern polish was rated on a card and was scored in whole points.",
    "THE CANONICAL `, and` SHAPE, where a person gives the rating":
        f"{SCALE}, and each keeper gave one whole-number grade on that card.",
    "a parenthetical with no subject of its own":
        f"{SCALE} (values were recorded in whole units).",
    "a nominalised subject":
        "Ratings of lantern polish were recorded in whole points.",
    "a subject carrying a prepositional phrase":
        "The lantern polish of each light was counted in whole units.",
    "a COORDINATED SUBJECT under one predicate":
        "Lantern polish and prism counts were both recorded in whole units.",
    "the discreteness word in the FIRST coordinate":
        "Lantern polish was graded in whole points, and the cards were "
        "collected at each relief.",
    "an active clause with a lexical verb and an agent subject":
        "Keepers graded lantern polish in whole points.",
    # ROUND 26 MADE THE THREE CARDINAL CASES SINGULAR. Each still carries the
    # GRAMMAR round 22 is about -- a by-phrase, a long leading adverbial, a
    # second predication -- and none now says the measurement was made twice per
    # subject, which is a different premise and not an honest licence.
    "the whole-points sentence with a by-phrase":
        "Lantern polish was graded in whole points on a card running from 0 to "
        "16 by the duty keeper.",
    "`number of` counting THIS variable":
        "The number of lantern polish points was recorded in whole units.",
    "A LEADING ADVERBIAL before the assertion":
        "At each watch, lantern polish was recorded in whole points.",
    "A LONGER LEADING ADVERBIAL":
        "In the independent assessment carried out that season, lantern polish "
        "was recorded in whole points.",
    "A TRAILING ADJUNCT THAT NAMES THIS VARIABLE":
        f"{SCALE}, with lantern polish recorded in whole units.",
    "a trailing adjunct naming this variable, participial":
        f"{SCALE}, lantern polish being recorded in whole units.",
    "A TRAILING MODIFIER THAT NAMES NOTHING AT ALL":
        "Lantern polish is scored from 0 to 16, in whole points.",
    "A SECOND PREDICATION ARRIVING AFTER THE WHOLE-UNIT WORDS":
        "Lantern polish was counted in whole units by the keeper who was "
        "trained that season.",
}

#: WHAT THIS ROUND COSTS, NAMED RATHER THAN LEFT OUT OF THE TABLE. Both are
#: honest sentences a paper may print, and both are the shape this reader cannot
#: tell from a leak: strike the quantity's name out of `, with chipped prisms
#: counted in whole units` and you have the first; strike it out of `once
#: chipped prisms were counted in whole units` and you have the second. The
#: price of the refusal is a check; the price of the licence is an accusation.
#:
#: THE FIRST IS THE NEAR MISS, and it is the reason `_run_names_something`
#: exists. `, in whole points` names nothing once the vocabulary is removed and
#: keeps its licence; `, recorded in whole units` leaves the participle
#: `recorded` behind, this reader cannot tell a participle from a noun, and the
#: direction it must be wrong in is the one that costs a check.
HONEST_NOW_REFUSED = {
    "a trailing adjunct leaving a participle behind":
        f"{SCALE}, recorded in whole units.",
    "the granularity stated in a SECOND predication":
        "The cards were archived once lantern polish was recorded in whole "
        "points.",
}

#: AND THE TWO THAT ALREADY REFUSED BEFORE THIS ROUND, so the table's zeros are
#: honest zeros. Both refuse at `6688c9d3` for reasons older than this change.
HONEST_ALREADY_REFUSED = {
    "a parenthetical with a CONTENTFUL subject":
        f"{SCALE} (grades were recorded in whole units).",
    "a semicolon, with the granularity in the second clause":
        f"{SCALE}; the grade was always a whole number.",
}


class TestTheHonestPapersKeepTheirStep:

    @pytest.mark.parametrize("label", sorted(HONEST))
    def test_an_honest_granularity_statement_still_licenses(self, label):
        acc, text = watch_paper(HONEST[label])
        rec = verification(acc, text)
        assert rec["establishes_step_of_one"] is True, (label, rec["reasons"])
        assert rec["discreteness_source"] == premises.STATED_DISCRETENESS, label

    @pytest.mark.parametrize("label", sorted(HONEST))
    def test_the_record_says_how_the_licence_was_attributed(self, label):
        """The other half of the auditability ask: a reader has to be able to
        tell a licence resting on an assertion that NAMES this variable from one
        resting on INHERITANCE, which is the weaker of the two and the one the
        remaining residue rides in on."""
        rec = verification(*watch_paper(HONEST[label]))
        assert rec["discreteness_boundary"] in {"subject", "inherited"}, label
        assert rec["discreteness_unresolved_constituent"] is None, label
        assert rec["discreteness_assertion"] in HONEST[label], label


class TestWhatThisCosts:
    """MEASURED RATHER THAN ASSERTED, because the last fix on this premise
    reported its cost as zero and an independent verifier then measured ten."""

    @pytest.mark.parametrize("label", sorted(HONEST_NOW_REFUSED))
    def test_the_two_honest_shapes_this_round_refuses(self, label):
        acc, text = watch_paper(HONEST_NOW_REFUSED[label])
        rec = verification(acc, text)
        assert rec["establishes_step_of_one"] is False, label
        assert rec["discreteness_boundary"] == "unresolved", label

    @pytest.mark.parametrize("label", sorted(HONEST_ALREADY_REFUSED))
    def test_the_two_pre_existing_refusals_are_named_not_hidden(self, label):
        acc, text = watch_paper(HONEST_ALREADY_REFUSED[label])
        assert verification(acc, text)["establishes_step_of_one"] is False, label

    def test_the_cost_is_two_of_twenty_four_and_the_table_is_complete(self):
        """The whole honest battery in one number, so a later change that pays
        more cannot pay it quietly. Twenty-two of twenty-four license; the two
        that do not are enumerated above with the leak each is
        indistinguishable from."""
        assert len(HONEST) == 22
        assert len(HONEST_NOW_REFUSED) == 2
        kept = sum(verification(*watch_paper(s))["establishes_step_of_one"]
                   for s in HONEST.values())
        assert kept == 22


# --------------------------------------------------------------------------
# WHAT THE ROUND-21 FIX COST, RE-MEASURED -- AND WHY SEVEN OF IT STAYS SPENT
# --------------------------------------------------------------------------

#: An independent verifier measured that round 21 (`6688c9d3`) withdrew TEN
#: honest licences that stood at `680b150a`. Three of them are shapes THIS round
#: refuses independently and for its own reason, so they were never recoverable.
#: The other seven turn on a rule that reads the SUBJECT of an assertion while
#: the variable is its OBJECT.
ROUND_21_COST_SUBSUMED = {
    "a noun `counts` with a content word before it":
        "Prism counts were reconciled before lantern polish was recorded in "
        "whole points.",
    "a noun `count` with a content word before it":
        "The relief count was checked before lantern polish was recorded in "
        "whole points.",
    "a noun `tallies` with a content word before it":
        "Keeper tallies were archived after lantern polish was recorded in "
        "whole points.",
}

ROUND_21_COST_STILL_SPENT = {
    "active, `counted`, object is this variable":
        "The keeper counted lantern polish in whole units.",
    "active, `Each keeper counted`":
        "Each keeper counted lantern polish in whole units.",
    "active, `Keepers tallied`":
        "Keepers tallied lantern polish in whole points.",
    "active, with the scale in the same sentence":
        "Trained keepers counted lantern polish in whole units on a card from "
        "0 to 16.",
    "active, `The principal keeper tallied`":
        "The principal keeper tallied lantern polish in whole points.",
    "parenthetical, lexical subject":
        "Lantern polish was graded on a card (the keepers counted lantern "
        "polish in whole units).",
    "comma-and, lexical subject":
        f"{SCALE}, and the keepers counted lantern polish in whole units.",
}


class TestTheRoundTwentyOneCost:

    @pytest.mark.parametrize("label", sorted(ROUND_21_COST_SUBSUMED))
    def test_three_of_the_ten_this_round_would_refuse_anyway(self, label):
        """NOT RECOVERABLE, and the reason is the round's own: each of these is
        TWO predications, and the whole-unit words are in the second. Strike the
        variable's name out and you have the bare-`before` leak exactly. So
        round 22 refuses them on its own account, which is the honest reason --
        round 21 refused them because the noun `counts` was read as a finite
        verb, which was not."""
        assert premises._one_predication(ROUND_21_COST_SUBSUMED[label]) is False
        acc, text = watch_paper(ROUND_21_COST_SUBSUMED[label])
        assert verification(acc, text)["establishes_step_of_one"] is False, label

    @pytest.mark.parametrize("label", sorted(ROUND_21_COST_STILL_SPENT))
    def test_seven_of_the_ten_are_a_subject_rule_cost_this_round_does_not_pay(
            self, label):
        """Their boundary IS resolved -- round 22 has no quarrel with them, and
        the record proves which rule refused: `discreteness_belongs_to` NAMES
        the agent, so `_assertion_subject` found a subject and it was not this
        variable. The variable is the verb's OBJECT, which is round 21's stated
        open position and not this round's business."""
        acc, text = watch_paper(ROUND_21_COST_STILL_SPENT[label])
        rec = verification(acc, text)
        assert rec["establishes_step_of_one"] is False, label
        assert rec["discreteness_boundary"] != "unresolved", label
        assert rec["discreteness_unresolved_constituent"] is None, label
        assert rec["discreteness_belongs_to"], label

    def test_why_reading_the_object_was_not_attempted(self):
        """THE MEASUREMENT THAT MUST TRAVEL WITH ANY FUTURE ATTEMPT, pinned so
        the next round does not have to rediscover it. Recovering the seven
        means asking whether the OBJECT of the vocabulary verb is this variable,
        and the cheapest form of that question -- everything after the finite
        verb -- returns True on a sentence whose whole-unit claim belongs
        squarely to something else, because this variable is named in a trailing
        prepositional phrase. That is a manufactured licence, which is the
        dangerous polarity, so the seven stay spent until the direct object can
        be found rather than guessed at."""
        acc, text = watch_paper(f"{SCALE}.")
        variables = premises.readable_variables(acc)
        v = variables[0]
        rival = ("Chipped prisms were counted in whole units on the lantern "
                 "polish card.")
        tail = rival[premises._LICENCE_FINITE.search(rival).end():]
        assert premises.about_this_variable(v, tail, variables)[
            "about_this_variable"] is True
        # And the rule as it stands refuses it, which is the behaviour to keep.
        assert verification(*watch_paper(rival))[
            "establishes_step_of_one"] is False


# --------------------------------------------------------------------------
# THE RULE ITSELF
# --------------------------------------------------------------------------


class TestTheBoundaryRule:

    def test_a_comma_free_segment_is_unchanged(self):
        """The rule is inert where there is nothing to be uncertain about: one
        run, index zero, attributable by contiguity exactly as before."""
        acc, text = watch_paper(f"{SCALE}.")
        variables = premises.readable_variables(acc)
        got = premises._discreteness_is_attributable(
            variables[0], "Lantern polish was recorded in whole points", variables)
        assert got == (True, None)

    def test_a_later_run_may_still_earn_a_licence_by_naming_the_variable(self):
        """A POSITIVE ATTRIBUTION, NEVER AN INHERITANCE -- and it is what keeps
        the leading-adverbial shape, which is ordinary methods prose."""
        acc, text = watch_paper(f"{SCALE}.")
        variables = premises.readable_variables(acc)
        ok, where = premises._discreteness_is_attributable(
            variables[0],
            "At each watch, lantern polish was recorded in whole points",
            variables)
        assert (ok, where) == (True, None)

    def test_a_later_run_naming_a_rival_is_refused_and_named(self):
        """And the refusal carries the words it refused on, which is what an
        auditor reads instead of `reasons: []`."""
        acc, text = watch_paper(f"{SCALE}.")
        variables = premises.readable_variables(acc)
        ok, where = premises._discreteness_is_attributable(
            variables[0], f"{SCALE}, chipped prisms counted in whole units",
            variables)
        assert ok is False
        assert where == "chipped prisms counted in whole units"

    def test_a_comma_is_not_a_clause_break_and_must_not_become_one(self):
        """WHY THE MARK IS USED FOR A REFUSAL AND NOT FOR AN ATTRIBUTION.
        Cutting there would hand the far side its own attribution test, and a
        trailing adjunct with no finite verb of its own would pass it by
        inheriting the clause exactly as it does today -- so the leak would
        survive the cut. The mark says INHERITANCE IS UNAVAILABLE, which is a
        weaker and safer thing."""
        assert premises._CLAUSE_BREAK.search("a, b") is None
        assert premises.assertion_segments(
            f"{HALF}, alongside a Likert item on keeper workload.") == [
                f"{HALF}, alongside a Likert item on keeper workload."]

    def test_a_run_that_names_nothing_modifies_what_was_last_named(self):
        """THE THIRD CONDITION, AND THE ONE THE ROUND WOULD BE WRONG WITHOUT.
        Both of these end in a constituent that names nothing once the
        vocabulary is removed. The first modifies the variable named in the run
        before it and keeps its licence -- it is this repo's own canonical
        bound-and-granularity sentence. The second modifies an APPOSITIVE naming
        a rival, and does not."""
        acc, text = watch_paper(f"{SCALE}.")
        variables = premises.readable_variables(acc)
        v = variables[0]
        assert premises._run_names_something(" in whole points.", v) is False
        assert premises._run_names_something(" counted in whole units.", v) is False
        assert premises._run_names_something(
            " a measure quite separate from chipped prisms", v) is True
        assert premises._discreteness_is_attributable(
            v, "Lantern polish is scored from 0 to 16, in whole points.",
            variables) == (True, None)
        ok, where = premises._discreteness_is_attributable(
            v, f"{SCALE}, a measure quite separate from chipped prisms, "
               f"counted in whole units.", variables)
        assert (ok, where) == (False, "counted in whole units.")

    def test_one_predication_reads_subjects_and_not_a_subordinator_list(self):
        """The second mechanism, and the argument that it is not a twenty-first
        list entry: what it looks for is a SUBJECT standing between two finite
        verbs, which is what a second predication is however it is introduced."""
        assert premises._one_predication(
            "Lantern polish scores were counted in whole units.") is True
        assert premises._one_predication(
            "Lantern polish was counted in whole units by the keepers.") is True
        assert premises._one_predication(
            "Lantern polish was graded on a card because chipped prisms were "
            "counted in whole units.") is False
        assert premises._one_predication(
            "Lantern polish was graded on a card after chipped prisms were "
            "counted in whole units.") is False
