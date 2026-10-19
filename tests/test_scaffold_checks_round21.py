"""ROUND 21 -- A DISCRETENESS PREDICATE BELONGING TO AN UNDECLARED QUANTITY,
SIX MORE WAYS, AND THE RULE CHANGES SHAPE INSTEAD OF GROWING.

THE DEFECT IS ROUND 19's D3, WHICH WAS CLOSED THREE INSTANCES AT A TIME. That
round added `number of`'s counted-noun test, a bare `while` to `_CLAUSE_BREAK`,
and a parenthesis rule keyed on `_FINITE_AUX`. Each closed one phrasing. SIX
more were measured against the UNCHANGED tree at `680b150a`, on the default
path, no flag, on an honest half-point card -- all six GRIM `impossible`:

    ..., and damaged packets were counted in whole units.
    ... and damaged packets were tallied in whole units.
    ..., and mainspring failures were recorded as integers.
    ..., and steward workload was rated on a 7-point scale.
    ... (the stewards counted damaged packets in whole units).
    ... (each inspector tallied damaged packets in whole units).

The first four are the vocabulary's PREDICATE members after `, and` or a bare
`and`, which round 19 left alone because it fixed the ONE noun-phrase member.
The last two are parentheticals whose finite verb is LEXICAL rather than one of
the nine auxiliaries `_FINITE_AUX` carries. The same facts after a SEMICOLON
refused at `680b150a` and refuse now; so did the same facts about a DECLARED
rival. The leak is exactly the gap between those two: a quantity the PAPER names
and the ACCOUNT does not declare, inside a clause the boundary list cannot cut.

SO THE FIX IS NOT A SEVENTH SEPARATOR OR A TENTH AUXILIARY. CLAUDE.md records
three times that one more member of a closed list buys one round, and the
licence is the polarity where being generous MANUFACTURES an accusation. The
question changed instead: not WHERE THE CLAUSE ENDS but WHICH ASSERTION INSIDE
IT the discreteness word belongs to. An assertion carrying a subject of its own
is about that subject, which must then be this variable; one carrying no subject
of its own is a predicate on its host clause and is attributed exactly as
before. An undeclared quantity in subject position now fails BY CONSTRUCTION,
because the test is `the subject IS this variable` and never `no OTHER DECLARED
variable intervenes`.

WHY THE CANONICAL `, and` FIXTURE SURVIVES, AND IT IS THE WHOLE COST ARGUMENT.
`, and` is still NOT a `_CLAUSE_BREAK` member -- that decision was measured and
rejected twice, because splitting there costs `<variable> was rated on a scale,
and each participant gave one whole-number rating on that scale`, whose
discreteness clause then names no variable. A SEGMENT boundary is a weaker
thing: it decides only where to look for a subject, and a segment with none
still inherits its clause. `each participant gave one whole-number rating`
asserts about nobody this reader can find and keeps its licence; `damaged
packets were counted in whole units` asserts about damaged packets and does not.
The boundary rule cannot tell those apart. The subject rule can.

THE COST WAS MEASURED AND IT IS ZERO. Eighteen honest phrasings of a real
whole-unit granularity statement: 16 licensed at `680b150a` and 16 licensed now,
the SAME sixteen. The two that refuse refused before this round as well and for
reasons that predate it. On the other side the accusing set goes from 8 of 10 to
1 of 10. Every check row the scaffold emits was dumped for 78 probes before and
after: 0 accusations manufactured, 0 licences newly granted, 0 averaging vetoes
lost, and `_clauses` splits identical on every one.

WHAT STILL DEFEATS IT, PINNED AS AN OPEN POSITION RATHER THAN PAPERED OVER. A
competing assertion whose finite verb is LEXICAL and is not one of the
vocabulary's own verbs -- `..., and stewards LOGGED mainspring failures as
integers.` -- carries a subject this reader cannot find, defers to its host
clause, and licenses. Closing it needs a verb lexicon, and both morphological
proxies for one refuse honest sentences: `each warden MARKED one whole-number
grade` is the shape this module must keep and it is `-ed`. That residue sits
where `_CLAUSE_BREAK` already leaves the `, and` case -- with the account's own
`derivation` field and with the model, whose `step` question is asked of exactly
that sentence. See `TestTheResidueIsNamed`.

THE FIXTURE PAPER IS A COMMUNITY ORCHARD PRUNING AUDIT and shares no sentence,
scale, noun or number with any earlier round.
"""

from __future__ import annotations

import statistics as st

import pytest

from metascience_agent.scaffold import checks, premises, premise_reading as PR

BAD = {"suspicious", "highly_suspicious", "impossible"}

# --------------------------------------------------------------------------
# The Marden orchard pruning audit
# --------------------------------------------------------------------------

#: Branch health, graded 0-12 in WHOLE points by each of TWO wardens; a tree's
#: figure is the mean of the two cards, so it moves in HALF points. Honest by
#: construction and unreachable from any integer total, which is what makes a
#: licence granted here a conviction of a paper that did nothing wrong.
HEALTH = [8.0, 9.0, 5.5, 11.0, 8.5, 3.0, 10.5, 6.0, 9.5, 4.5,
          12.0, 7.0, 10.0, 5.0, 8.0, 11.5, 6.5, 9.0, 2.5, 11.0,
          7.5, 4.0, 10.5, 8.5, 5.5, 9.5, 6.0, 12.0, 3.5, 10.0,
          7.0, 11.5, 8.0, 5.0, 9.5, 6.5, 4.5, 10.5, 8.5, 7.5, 11.0]
N = len(HEALTH)
H_MEAN = f"{st.fmean(HEALTH):.2f}"
H_SD = f"{st.stdev(HEALTH):.2f}"
assert N == 41
assert not any(round(k / N, 2) == float(H_MEAN) for k in range(N * 12 + 1)), H_MEAN
assert any(round(t / (2 * N), 2) == float(H_MEAN) for t in range(N * 24 + 1))

#: The honest WHOLE-number companion: pruning cuts per tree, an ordinary integer
#: count. It is the control for every licence this file narrows.
CUTS = [21, 34, 12, 40, 27, 55, 16, 31, 46, 19, 25, 39, 14, 30, 51,
        23, 36, 18, 44, 28, 37, 11, 49, 21, 33, 42, 16, 26, 53, 19,
        31, 23, 47, 39, 14, 28, 41, 22, 35, 17, 29]
assert len(CUTS) == N
C_MEAN = f"{st.fmean(CUTS):.2f}"
C_SD = f"{st.stdev(CUTS):.2f}"

N_Q = "Forty-one trees were surveyed in the Marden orchard audit (n = 41)."
SCALE = "Branch health was graded on a slip running from 0 to 12"
GRAN_C = "Pruning cuts were counted as whole cuts, from 0 to 300 per tree."


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
            "coordinate": {"study_id": "study:marden", "group_id": "grp:trees",
                           "phase_id": None}}


def account(variables, values):
    return {"paper": {"doi": "10.0000/marden",
                      "title": "Pruning quality in a community orchard"},
            "studies": [{"id": "study:marden", "design": "prospective_cohort",
                         "groups": [{"id": "grp:trees", "label": "All trees",
                                     "n": N, "n_source": "text"}]}],
            "variables": variables, "values": values,
            "document": {"tables": [
                {"id": "table:1",
                 "caption": "Table 1. Tree-level pruning measures.",
                 "footnotes": []}]}}


def health_paper(sentence, *, with_cuts=False):
    """The orchard paper whose granularity sentence for Branch health is
    `sentence`, and the account that reads it."""
    variables = [var("var:health", "Branch health", sentence, 0, 12)]
    values = [cell("val:hm", "mean", H_MEAN, "var:health", 1, "Mean (SD)"),
              cell("val:hs", "sd", H_SD, "var:health", 2, "Mean (SD)"),
              cell("val:hn", "n", str(N), "var:health", 3, "n")]
    sentences = [N_Q, sentence]
    if with_cuts:
        variables.append(var("var:cuts", "Pruning cuts", GRAN_C, 0, 300,
                             kind="count"))
        values += [cell("val:cm", "mean", C_MEAN, "var:cuts", 1, "Mean (SD)"),
                   cell("val:cs", "sd", C_SD, "var:cuts", 2, "Mean (SD)"),
                   cell("val:cn", "n", str(N), "var:cuts", 3, "n")]
        sentences.append(GRAN_C)
    text = "\n\n".join(["## Methods"] + sentences) + "\n"
    return account(variables, values), text


def accusations(acc, text):
    return sorted({(r["check_id"], r["severity"])
                   for r in checks.evaluate(acc, text)["checks"]
                   if r["severity"] in BAD})


def families(acc, text):
    return sorted((r["family"], r["variable_id"], r["severity"])
                  for r in checks.evaluate(acc, text)["checks"])


def verification(acc, text, vid="var:health"):
    hay = premises.Haystack(text)
    variables = premises.readable_variables(acc)
    v = [x for x in variables if x["id"] == vid][0]
    mine = [x for x in acc["values"] if x.get("variable_id") == vid]
    return premises.granularity_verification(v, hay, variables, mine)


def test_the_fixture_is_not_toothless():
    """THE ASSERTION EVERY `accusations(...) == []` IN THIS FILE RESTS ON.
    [[a-fixture-that-excludes-the-defect-region]]: with the licence standing this
    paper IS convicted, so a test that shows no accusation has shown something.
    And the honest whole-unit companion is checked and PASSES, so a fix that
    bought safety by refusing everything would fail here."""
    # ROUND 26: `by each of two wardens` no longer licenses a per-subject step
    # (it states the step for a WARDEN'S SLIP), so the device that makes this
    # honest half-point card look integer is now the plain whole-points sentence.
    acc, text = health_paper(
        "Branch health was graded in whole points on a slip running from 0 to "
        "12 by the duty warden.", with_cuts=True)
    got = families(acc, text)
    assert ("grim", "var:health", "impossible") in got
    assert ("grim", "var:cuts", "consistent") in got


# --------------------------------------------------------------------------
# THE SIX LIVE FALSE ACCUSATIONS
# --------------------------------------------------------------------------

LEAKS = {
    "a comma-and, and the predicate `counted`":
        f"{SCALE}, and damaged packets were counted in whole units.",
    "a bare and, and the predicate `tallied`":
        f"{SCALE} and damaged packets were tallied in whole units.",
    "a comma-and, and the noun `integers`":
        f"{SCALE}, and mainspring failures were recorded as integers.",
    "a comma-and, and a point scale":
        f"{SCALE}, and warden workload was rated on a 7-point scale.",
    "a parenthetical whose finite verb is lexical":
        f"{SCALE} (the wardens counted damaged packets in whole units).",
    "a parenthetical whose finite verb is lexical, second person":
        f"{SCALE} (each warden tallied damaged packets in whole units).",
}

#: WHOSE CLAIM IT REALLY WAS, for each leak above. The record has to be able to
#: say so: a reader of a refusal must be able to go and look at what took the
#: licence away, exactly as a reader of a licence looks at what bought it.
BELONGS_TO = {
    "a comma-and, and the predicate `counted`": "damaged packets",
    "a bare and, and the predicate `tallied`": "damaged packets",
    "a comma-and, and the noun `integers`": "mainspring failures",
    "a comma-and, and a point scale": "warden workload",
    "a parenthetical whose finite verb is lexical": "the wardens",
    "a parenthetical whose finite verb is lexical, second person": "each warden",
}

CONTROLS = {
    "the scale clause alone": f"{SCALE}.",
    "the same fact after a semicolon":
        f"{SCALE}; damaged packets were counted in whole units.",
    "the same fact after a bare while":
        f"{SCALE} while damaged packets were counted in whole units.",
    "a parenthetical with an auxiliary":
        f"{SCALE} (damaged packets were counted in whole units).",
}


class TestALicenceIsNotSuppliedByAnotherQuantitysPredicate:
    """ROUND 19's D3 CONTINUED, AND ITS OWN DOCSTRING SAID WHY IT WOULD BE:
    "this narrows one phrase, not the vocabulary". The other members were the
    ones left, and all six of these were reproduced as GRIM `impossible` on this
    honest half-point card against the UNCHANGED tree at `680b150a` before
    anything was written."""

    @pytest.mark.parametrize("label", sorted(LEAKS))
    def test_each_leak_no_longer_licenses_a_step(self, label):
        acc, text = health_paper(LEAKS[label])
        assert accusations(acc, text) == [], label
        assert verification(acc, text)["establishes_step_of_one"] is False, label

    @pytest.mark.parametrize("label", sorted(LEAKS))
    def test_the_record_names_whose_claim_it_was(self, label):
        rec = verification(*health_paper(LEAKS[label]))
        assert rec["discreteness_belongs_to"] == BELONGS_TO[label], label
        assert rec["discreteness_assertion"] is None
        assert any(BELONGS_TO[label] in r["detail"] for r in rec["reasons"]), \
            rec["reasons"]

    @pytest.mark.parametrize("label", sorted(CONTROLS))
    def test_the_controls_that_already_refused_still_refuse(self, label):
        """THE TELL THAT THE BOUNDARY LIST WAS THE WHOLE DIFFERENCE, and it must
        stay a tell: the identical facts punctuated the ways this repo already
        reads refused at `680b150a` and refuse now."""
        acc, text = health_paper(CONTROLS[label])
        assert accusations(acc, text) == [], label
        assert verification(acc, text)["establishes_step_of_one"] is False, label

    @pytest.mark.parametrize("label", sorted(LEAKS))
    def test_a_declared_rival_was_never_the_mechanism(self, label):
        """The account declaring the other quantity changes nothing, which is
        what says the fix is not `names_another_variable` reaching further. The
        test is that the subject IS this variable, so an undeclared quantity
        fails for the same reason a declared one does."""
        acc, text = health_paper(LEAKS[label], with_cuts=True)
        assert verification(acc, text)["establishes_step_of_one"] is False, label


# --------------------------------------------------------------------------
# THE COST SIDE -- EIGHTEEN HONEST PHRASINGS, AND THE SAME SIXTEEN SURVIVE
# --------------------------------------------------------------------------

HONEST = {
    "passive, its own subject":
        "Branch health was graded in whole points on a slip running from 0 to 12.",
    "passive, `as an integer`":
        "Branch health was recorded as an integer from 0 to 12.",
    "a plural head noun":
        "Branch health scores were counted in whole units.",
    "a per-subject possessive":
        "Each tree's branch health was tallied in whole points.",
    "a point scale":
        "Branch health was rated on a 7-point scale.",
    "a Likert item":
        "Branch health was assessed with a Likert item.",
    "a coordinated verb phrase with an elided subject":
        "Branch health was rated on a slip and was scored in whole points.",
    "THE CANONICAL `, and` SHAPE, where a person gives the rating":
        (f"{SCALE}, and each warden gave one whole-number grade on that slip."),
    "a parenthetical with no subject of its own":
        f"{SCALE} (values were recorded in whole units).",
    "a nominalised subject":
        "Ratings of branch health were recorded in whole points.",
    "a subject carrying a prepositional phrase":
        "The branch health of each tree was counted in whole units.",
    "a COORDINATED SUBJECT under one predicate":
        "Branch health and cut counts were both recorded in whole units.",
    "the discreteness word in the FIRST coordinate":
        "Branch health was graded in whole points, and the slips were collected "
        "at each visit.",
    "an active clause with a lexical verb and an agent subject":
        "Wardens graded branch health in whole points.",
    # ROUND 26 MADE THIS SINGULAR. What round 21 tests here is the BY-PHRASE;
    # `two wardens` was incidental and is not honest -- a paper that says the
    # grading happened twice per tree has not said the tree's own figure is a
    # whole number.
    "the whole-points sentence with a by-phrase":
        "Branch health was graded in whole points on a slip running from 0 to "
        "12 by the duty warden.",
    "`number of` counting THIS variable":
        "The number of branch health points was recorded in whole units.",
}

#: THE TWO THAT REFUSE, AND BOTH REFUSED BEFORE THIS ROUND. Named rather than
#: dropped, because a cost table that quietly excludes its own losses is the
#: fixture defect this repo keeps finding.
HONEST_ALREADY_REFUSED = {
    "a parenthetical with a CONTENTFUL subject":
        f"{SCALE} (grades were recorded in whole units).",
    "a semicolon, with the granularity in the second clause":
        f"{SCALE}; the grade was always a whole number.",
}


class TestTheHonestPapersKeepTheirStep:
    """WHAT THE FIX COSTS, MEASURED RATHER THAN ASSERTED. A licence rule
    narrowed until it stops firing is not a fix, so every honest phrasing of a
    real whole-unit statement is replayed: sixteen licensed at `680b150a` and
    the same sixteen license now."""

    @pytest.mark.parametrize("label", sorted(HONEST))
    def test_an_honest_granularity_statement_still_licenses(self, label):
        acc, text = health_paper(HONEST[label])
        rec = verification(acc, text)
        assert rec["establishes_step_of_one"] is True, (label, rec["reasons"])
        assert rec["discreteness_source"] == premises.STATED_DISCRETENESS, label

    @pytest.mark.parametrize("label", sorted(HONEST))
    def test_the_licence_names_the_assertion_that_bought_it(self, label):
        rec = verification(*health_paper(HONEST[label]))
        assert rec["discreteness_assertion"], label
        assert rec["discreteness_assertion"] in HONEST[label], label

    @pytest.mark.parametrize("label", sorted(HONEST_ALREADY_REFUSED))
    def test_the_two_pre_existing_refusals_are_named_not_hidden(self, label):
        """NOT A COST OF THIS ROUND, and the distinction is the point of
        recording them. Both refuse at `680b150a` for reasons older than this
        change -- `_clauses` cuts an auxiliary-headed parenthetical out, and a
        semicolon has always been a clause break -- so they belong in the cost
        table as a zero rather than outside it."""
        acc, text = health_paper(HONEST_ALREADY_REFUSED[label])
        assert verification(acc, text)["establishes_step_of_one"] is False, label

    def test_the_whole_unit_companion_is_untouched(self):
        """A count is a count whatever this rule decides: `var:cuts` is licensed
        by its KIND, which this round does not touch in either direction."""
        acc, text = health_paper(LEAKS["a comma-and, and the predicate `counted`"],
                                 with_cuts=True)
        rec = verification(acc, text, "var:cuts")
        assert rec["kind_makes_it_necessary"] is True
        assert ("grim", "var:cuts", "consistent") in families(acc, text)


# --------------------------------------------------------------------------
# THE RULE ITSELF, AND THE DIRECTION THAT MAKES IT SAFE
# --------------------------------------------------------------------------


class TestTheSegmentRule:
    def test_a_coordinator_is_a_boundary_only_between_two_finite_things(self):
        """WHAT KEEPS A COORDINATED SUBJECT WHOLE. `Branch health and cut counts
        were both recorded` coordinates two NOUNS -- there is no finite verb
        before the `and` -- so it stays one segment and both variables keep
        their licence."""
        assert premises.assertion_segments(
            "Branch health and cut counts were both recorded in whole units."
        ) == ["Branch health and cut counts were both recorded in whole units."]
        assert premises.assertion_segments(
            f"{SCALE} and damaged packets were tallied in whole units."
        ) == [SCALE, "damaged packets were tallied in whole units."]

    def test_every_parenthetical_is_its_own_segment(self):
        """Segmenting is NOT cutting. `_clauses` cuts only an auxiliary-headed
        parenthetical, because cutting is shared with the averaging veto and may
        not remove a refusal; a segment boundary decides only where to look for
        a subject, and a subject-less parenthetical still inherits its clause."""
        got = premises.assertion_segments(
            "Branch health was graded (values were recorded in whole units).")
        assert "values were recorded in whole units" in got

    def test_a_segment_with_no_subject_of_its_own_defers_to_its_clause(self):
        assert premises._assertion_subject("was scored in whole points") is None
        assert premises._assertion_subject("values were recorded in whole units") \
            is None
        assert premises._assertion_subject("each warden gave one whole-number "
                                           "grade on that slip") is None
        assert premises._assertion_subject(
            "damaged packets were counted in whole units") == "damaged packets"
        assert premises._assertion_subject(
            "the wardens counted damaged packets") == "the wardens"

    def test_the_vocabularys_own_verbs_are_the_only_lexical_ones(self):
        """`_FINITE_AUX` finds the subject of `X were counted`; it finds nothing
        in `the wardens counted X`, where the vocabulary's own word IS the verb.
        No other member can be one -- `integers`, `whole points`, `Likert` and
        `7-point scale` are nouns and modifiers."""
        for verb in ("count", "counts", "counted", "tally", "tallies", "tallied"):
            assert premises._LICENCE_FINITE.search(f"the wardens {verb} slips"), verb
        for noun in ("integers", "whole points", "Likert", "7-point scale"):
            assert premises._assertion_subject(f"the wardens use {noun}") is None, noun

    def test_the_licence_probe_is_wider_than_the_clause_probe(self):
        """AND THAT ASYMMETRY IS THE SAFETY ARGUMENT. A wider probe finds MORE
        subjects, a found subject must be this variable, so widening here can
        only ever REMOVE a licence. Widening `_FINITE_AUX` would also change
        `_clauses`, which the averaging VETO walks, and there the same edit would
        remove a refusal."""
        lexical = "the wardens counted damaged packets in whole units"
        assert premises._is_own_assertion(lexical) is False
        assert premises._assertion_subject(lexical) == "the wardens"

    def test_comma_and_is_still_not_a_clause_break(self):
        """THE DECISION THIS ROUND DELIBERATELY DOES NOT RE-OPEN. It was measured
        and rejected twice with a stated reason, and the segment rule is what
        makes re-opening it unnecessary."""
        assert len(premises._clauses(
            f"{SCALE}, and each warden gave one whole-number grade on that slip."
        )) == 1


class TestTheAveragingVetoIsUntouched:
    """THE REFUSAL SIDE, ASSERTED DIRECTLY RATHER THAN INFERRED FROM THE SUITE
    STAYING GREEN. This round narrows a LICENCE; a change that also narrowed the
    averaging REFUSAL would restore `impossible` on every honest half-point
    paper the veto currently rescues, which is the [[a-fix-can-carry-its-own-
    false-accusation]] shape."""

    VETOED = {
        "a comma-and": "Branch health was graded in whole points by each of two "
                       "wardens, and the two slips were averaged.",
        "a semicolon": "Branch health was graded in whole points; the two slips "
                       "were averaged.",
        "a parenthetical": "Branch health was graded in whole points (the two "
                           "slips were averaged).",
        "a definition": "Each tree's branch health is the mean of the two "
                        "wardens' whole-point slips.",
        "a bare and": "Branch health was graded in whole points and the two "
                      "slips were averaged.",
        "a dash": "Branch health was graded in whole points -- the two slips "
                  "were averaged.",
        "arithmetic in words": "Branch health was graded in whole points, and "
                               "the pair was added together and halved.",
    }

    #: The one of the seven whose step is withdrawn by the CLAUSE-LEVEL
    #: averaging guard rather than by the attributed veto: `_averaging_here`
    #: resolves no subject for `the pair was added together and halved`, so
    #: `quote_reports_an_average` is None and `AVERAGED.search(clause)` is what
    #: stops the licence. MEASURED AT `680b150a` AND UNCHANGED -- named here
    #: rather than dropped from the table, because the two mechanisms are
    #: different guards and a test that conflated them would go quiet if either
    #: one died.
    BY_THE_CLAUSE_GUARD = {"arithmetic in words"}

    @pytest.mark.parametrize("label", sorted(VETOED))
    def test_the_step_is_still_withdrawn(self, label):
        acc, text = health_paper(self.VETOED[label])
        rec = verification(acc, text)
        assert rec["establishes_step_of_one"] is False, label
        assert accusations(acc, text) == [], label
        if label in self.BY_THE_CLAUSE_GUARD:
            assert rec["quote_reports_an_average"] is None, label
            assert premises.AVERAGED.search(self.VETOED[label]), label
        else:
            assert rec["quote_reports_an_average"], label


class TestTheResidueIsNamed:
    """WHAT STILL DEFEATS THE RULE, PINNED RATHER THAN PAPERED OVER, in the same
    shape `TestTheCoordinatedClauseIsLeftToTheModel` used for the case this
    round closed.

    A competing assertion whose finite verb is LEXICAL and is not one of the
    vocabulary's own verbs carries a subject this reader cannot find, so it
    defers to its host clause and licenses. Closing it needs a verb lexicon:
    both morphological proxies for one (`-ed`, `-s`) refuse honest sentences,
    and `each warden MARKED one whole-number grade` -- the canonical shape this
    module must keep -- is `-ed`.

    SO IT IS LEFT WHERE THE `, and` CASE WAS LEFT, and the same two readers
    close it: the account's own `derivation` field, and the model, whose `step`
    question is asked of exactly this sentence."""

    RESIDUE = (f"{SCALE}, and wardens logged mainspring failures as integers.")

    def test_the_vocabulary_path_still_licenses_and_this_is_the_open_cost(self):
        acc, text = health_paper(self.RESIDUE)
        assert verification(acc, text)["establishes_step_of_one"] is True

    def test_the_sentence_reaches_the_model_as_a_step_candidate(self):
        """A FIX THAT WORKED BY HIDING THE PASSAGE WOULD BE THE CLOSED-VOCABULARY
        FAILURE THIS MODULE EXISTS TO STOP. Stage 1 still surfaces it."""
        acc, text = health_paper(self.RESIDUE)
        cands = [c for c in PR.candidates(acc, text) if c["premise"] == "step"]
        assert any("mainspring" in c["quote"] for c in cands), \
            [c["quote"] for c in cands]

    def test_the_morphological_proxy_would_refuse_an_honest_paper(self):
        """THE MEASUREMENT THAT SAYS WHY THE RESIDUE IS LEFT RATHER THAN CLOSED
        WITH A PATTERN. `-ed` catches `logged` and it also catches `marked`, and
        the second is an honest paper's own sentence about its own variable."""
        honest = (f"{SCALE}, and each warden marked one whole-number grade on "
                  "that slip.")
        acc, text = health_paper(honest)
        assert verification(acc, text)["establishes_step_of_one"] is True
        assert premises._assertion_subject(
            "each warden marked one whole-number grade on that slip") is None
