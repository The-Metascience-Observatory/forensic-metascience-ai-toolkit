"""ROUND 23 -- A NEGATIVE RESULT. THE LEADING-CONSTITUENT LEAK IS NOT A MISSING
TEST, AND NO RULE OVER THE FEATURES THIS READER HAS CAN CLOSE IT.

NOTHING IS FIXED HERE ON PURPOSE. This file records a measurement so that the
obvious repair is not proposed a fourth time, and so that the next round spends
its effort on the structural exit rather than on a twenty-first boundary rule.

THE REPORT THAT PROMPTED IT. An independent verifier found nineteen phrasings
that still license a step of 1 at `77ec0346`, every one of them GRIM and SPRITE
`impossible` on a card the paper itself says is graded TO THE NEAREST HALF
POINT, and attributed fourteen of them to one mechanism:
`_discreteness_is_attributable` returns `(True, None)` at `i == 0` with no
attribution test at all, on the stated ground that run 0 is "contiguous with the
clause the caller already attributed". A SENTENCE-INITIAL ADJUNCT is run 0 and
is NOT that clause -- so the two halves of the sentence are read by two
different tests, `_discreteness_is_attributable` clearing the LEADING
constituent by contiguity while `_assertion_subject` walks past it to the MAIN
clause and answers with the variable under test. Both pass, on different
constituents, and the licence is granted. The verifier is right about the
mechanism. It is wrong that checking run 0 is available.

THE MEASUREMENT, AND IT IS THE WHOLE OF THE ARGUMENT. Two populations reach
`i == 0` and must be decided OPPOSITELY:

  MUST REFUSE -- a fronted adjunct carrying a RIVAL's granularity.
      `After counting loose bollards in whole units, quay surface grade was
       graded to the nearest half point ...`

  MUST GRANT -- a bare predicate, an elided coordinate subject, a subject-less
      parenthetical, or a fronted gerund naming the variable's OWN
      constituents. These are the shapes round 22's own docstring names as the
      ones inheritance exists for, and they include this repo's canonical
      known-answer fixture.
      `Berth condition rating was reviewed at the harbour office and was logged
       in whole units.`
      `Counting each unserviceable fender in whole units, wardens derived the
       berth condition rating.`

EVERY FEATURE THE FUNCTION CAN COMPUTE PUTS ALL OF THEM IN ONE CELL:
`_assertion_subject(run) is None` True, `_run_names_something(run, var)` True,
`about_this_variable(var, run, others)["anchor_score"]` **0.0**. Eight
must-refuse and four must-grant sentences, one feature vector, opposite required
answers. That is not a threshold that needs moving; it is the absence of a
separating feature, and `TestTheFeatureCellIsShared` asserts it.

WHAT THE SEPARATING FACT ACTUALLY IS, stated plainly because it says where the
exit lies. The two fronted gerunds differ only in whether the counted thing is a
CONSTITUENT of the variable or an independent quantity -- a count of
unserviceable fenders composes the berth condition rating, a count of loose
bollards does not compose the quay surface grade. Both counted things are
undeclared nouns with zero overlap against the variable's own name.
Deciding between them is a relation between two noun phrases, recoverable from
the paper's account of how the variable was derived and not from any boundary
in the sentence. The schema already has the slot for it (`derivation`,
`derived_from`); a regex over commas does not and cannot.

THE THREE CANDIDATE REPAIRS, ALL MEASURED, ALL REJECTED. Each was run against
the verifier's nineteen leaks, against a 30-construction honest battery built by
another session, and against three honest methods sections written in ordinary
academic register (18 licences, integer-valued variables, so a lost licence is
three real granularity check rows a truthful paper had earned):

    rule / commit         leaks open   honest battery   ordinary prose
    ---------------------------------------------------------------------
    6688c9d3 (pre-22)       19 / 19        27 / 30         12 / 18  (36 rows)
    77ec0346 (round 22)     19 / 19        26 / 30         11 / 18  (33 rows)
    uniform                  6 / 19        22 / 30          8 / 18  (24 rows)
    subject                 19 / 19        26 / 30         11 / 18  (33 rows)
    lone                     7 / 19        26 / 30         10 / 18  (30 rows)

  `uniform` deletes the `i == 0` branch so the owner lookback answers there too.
  It closes thirteen leaks and DESTROYS THE CANONICAL `, and` FIXTURE along with
  the elided coordinate subject and the subject-less parenthetical -- the three
  shapes the branch was written for -- and costs three further licences on
  ordinary prose. It refuses the shared cell, so it refuses both populations.

  `subject` grants at `i == 0` only where run 0 carries no subject of its own,
  which is the textbook description of a bare predicate. It closes NOTHING:
  0 of 19. A fronted gerund has no finite verb either, which is the shared cell
  restated as a probe.

  `lone` grants at `i == 0` only where the segment has ONE run, so that the
  caller's subject test reads the same string this one did. It is the only
  candidate that separates the two populations on the verifier's sentences --
  and it is not a feature of the constituent at all, it is a comma count.

AND `lone` IS DEFEATED BY TWO REWRITES THAT NEED NO CLEVERNESS: move the rival
adjunct after the main clause with no comma, or mention the variable's name in
passing inside the leading adjunct. Measured END TO END -- GRIM, GRIMMER and
SPRITE run on a full account -- over twelve such sentences, `77ec0346`,
`uniform`, `subject` and `lone` produce a BYTE-IDENTICAL result: the same 10 of
12 accuse an honest half-point card under every one of them. Whatever is done at
`i == 0`, those ten are unaffected. Six of the twelve are reproduced here at the
premise boundary by `TestTheClassSurvivesEveryCandidate`.

HOW THE TWO HONEST SETS WERE MEASURED, so the table can be re-derived. The
battery is 30 constructions on a genuinely whole-point card. The ordinary prose
is three methods sections -- a chart review, a classroom observation study and a
population survey -- each stating one integer variable's granularity once, in
the register a reviewer would pass without comment. Both are scored by whether
`granularity_verification` returns `establishes_step_of_one`, and the row counts
are the GRIM/GRIMMER/SPRITE rows `checks.evaluate` then produces, so that a lost
licence is counted as the three check rows it actually costs.

SO THE HONEST READING OF ROUND 23 IS THAT THE INSTRUMENT IS FAILING ON BOTH AXES
AT ONCE -- 19 open accusation channels, and 7 of 18 honest licences refused on
ordinary academic prose -- and that a fourth boundary rule moves neither number
in a direction worth having. What separates the two populations is the
derivation relation, which belongs in the structural account.

TWO COST FIGURES ARE IN CIRCULATION AND BOTH NEED QUALIFYING.

Round 22's "zero cost across the pinned fixtures" is an artifact. A second audit
reports `discreteness_boundary: unresolved` occurring 0 times across all 979
pinned inputs -- no pinned fixture contains the shape that round refuses -- so a
zero measured there means nothing. That is this repo's own
`a-fixture-that-excludes-the-defect-region`, and the figure should not be
repeated.

AND THE REPLACEMENT FIGURE MUST BE A DIFFERENCE, NOT A LEVEL. The same audit
reports round 22 costing 6 of 18 honest variables on ordinary methods prose. On
the three papers written for this round, 7 of 18 licences are refused at
`77ec0346` -- but SIX OF THOSE SEVEN ARE ALREADY REFUSED AT `6688c9d3`, before
round 22 existed. Round 22's own marginal cost is **1 of 18** here, and **1 of
30** on the honest battery, both of them the trailing bare participle its
docstring already names. The level is the premise's cost; the difference is the
round's. Reporting the level as the round's cost charges one commit for every
refusal the premise ever had -- which is the mirror image of reporting a zero
measured where the shape cannot occur.

THE FIXTURE IS THE PENNARD QUAY CONDITION SURVEY and shares no noun, scale or
number with the pool, orchard, kiln, depot, lighthouse or bell fixtures.
"""

from __future__ import annotations

import pytest

from forensic_metascience_ai_toolkit.scaffold import premises


# --------------------------------------------------------------------------
# THE FIXTURE. Two variables, neither of whose printed names contains a word of
# the discreteness vocabulary -- a name like `Berth occupancy count` carries
# `count` and would be attributed its own sentence by the vocabulary rather than
# by the rule under test, which is a fixture defect and not a result.
# --------------------------------------------------------------------------
GRADE = {"id": "var:quay", "name": "Quay surface grade",
         "label": "Quay surface grade", "printed_as": []}
RATING = {"id": "var:berth", "name": "Berth condition rating",
          "label": "Berth condition rating", "printed_as": []}

#: The honest main clause. The paper SAYS the grade is graded to the nearest
#: half point, so a step of 1 licensed here convicts a paper that did nothing.
_HALF = ("quay surface grade was graded to the nearest half point on a card "
         "running from 0 to 18")
HALF = _HALF[0].upper() + _HALF[1:]

#: A FRONTED ADJUNCT OWNING A RIVAL'S GRANULARITY. Run 0 every time.
MUST_REFUSE = {
    "besides a Likert item on a rival":
        f"Besides a Likert item on warden workload, {_HALF}.",
    "in addition to a point scale for a rival":
        f"In addition to a 7-point scale for warden workload, {_HALF}.",
    "using a point scale for a rival":
        f"Using a 7-point scale for warden workload, {_HALF}.",
    "after counting a rival":
        f"After counting loose bollards in whole units, {_HALF}.",
    "before counting a rival":
        f"Before counting loose bollards in whole units, {_HALF}.",
    "while counting a rival":
        f"While counting loose bollards in whole units, {_HALF}.",
    "a fronted gerund counting a rival":
        f"Counting loose bollards in whole units at each survey, {_HALF}.",
    "given the discrete nature of a rival":
        f"Given the discrete nature of loose bollards, {_HALF}.",
}

#: THE SHAPES INHERITANCE EXISTS FOR, and the fourth is ordinary methods prose
#: whose fronted gerund counts the variable's OWN constituents.
MUST_GRANT = {
    "an elided coordinate subject":
        "Berth condition rating was reviewed at the harbour office and was "
        "logged in whole units.",
    "a subject-less parenthetical":
        "Berth condition rating was taken from the harbour log (values were "
        "entered in whole units).",
    "the canonical `, and` fixture shape":
        "Berth condition rating was taken from the harbour log, and each warden "
        "gave one whole-number mark on that log.",
    "a fronted gerund counting this variable's own constituents":
        "Counting each unserviceable fender in whole units, wardens derived "
        "the berth condition rating.",
}

#: THE TWO REWRITES THAT NEED NO CLEVERNESS. `T` trails the rival adjunct after
#: the main clause with no comma; `N` keeps the leading comma and mentions the
#: variable's name in passing.
SURVIVES_ANYTHING = {
    "T trailing `after counting <rival>`":
        f"{HALF} after counting loose bollards in whole units.",
    "T trailing `before counting <rival>`":
        f"{HALF} before counting loose bollards in whole units.",
    "T trailing `alongside a Likert item on <rival>`":
        f"{HALF} alongside a Likert item on warden workload.",
    "T trailing `as well as a point scale for <rival>`":
        f"{HALF} as well as a 7-point scale for warden workload.",
    "N leading adjunct naming this variable in passing":
        "Besides a Likert item on warden workload kept beside the quay surface "
        f"grade card, {_HALF}.",
    "N leading gerund naming this variable in passing":
        "Counting loose bollards in whole units on the quay surface grade "
        f"sheet, {_HALF}.",
}


def _leading_run(var: dict, sentence: str) -> str | None:
    """The segment's FIRST run, where that is what carries the vocabulary and
    reaches the `i == 0` branch. None where the sentence does not reach it."""
    for seg in premises.assertion_segments(sentence):
        if not premises.discreteness_about(seg, var):
            continue
        runs = premises._CONSTITUENT.split(seg)
        if not runs:
            continue
        run = runs[0]
        if premises.discreteness_about(run, var) and premises._one_predication(run):
            return run
    return None


def _features(var: dict, sentence: str) -> tuple:
    """Every feature `_discreteness_is_attributable` can compute about the run
    it is deciding, in the order the function itself consults them."""
    run = _leading_run(var, sentence)
    assert run is not None, sentence
    return (premises._assertion_subject(run) is None,
            premises._run_names_something(run, var),
            premises.about_this_variable(var, run, [])["anchor_score"])


# --------------------------------------------------------------------------
# THE CANDIDATE RULES, written here rather than in `premises` because none of
# them ships. Each differs from the others in ONE predicate -- what may be
# granted at `i == 0` -- and in nothing else.
# --------------------------------------------------------------------------
def _rule(at_zero):
    def attributable(var, segment, others):
        runs = premises._CONSTITUENT.split(str(segment or ""))
        names = [premises._run_names_something(r, var) for r in runs]
        for i, run in enumerate(runs):
            if not premises.discreteness_about(run, var):
                continue
            if not premises._one_predication(run):
                continue
            if i == 0 and at_zero(run, runs):
                return True
            owner = next((runs[j] for j in range(i, -1, -1) if names[j]), None)
            if owner is None:
                return True
            here = premises.about_this_variable(var, owner, others)
            if here["about_this_variable"] and not here["names_another_variable"]:
                return True
        return False
    return attributable


#: Delete the branch: the owner lookback answers at `i == 0` too.
UNIFORM = _rule(lambda run, runs: False)
#: Grant where run 0 carries no subject of its own -- a bare predicate.
SUBJECT = _rule(lambda run, runs: premises._assertion_subject(run) is None)
#: Grant only where the segment is ONE run, so the caller's subject test reads
#: the same string this one did.
LONE = _rule(lambda run, runs: len(runs) == 1)


def _verdict(rule, var, sentence) -> bool:
    for seg in premises.assertion_segments(sentence):
        if premises.discreteness_about(seg, var) and rule(var, seg, []):
            return True
    return False


class TestTheFixtureIsNotToothless:
    """A fixture that does not reach the branch under test proves nothing, and
    this repo has shipped one before."""

    @pytest.mark.parametrize("label", sorted(MUST_REFUSE))
    def test_every_refuse_sentence_reaches_the_zero_branch(self, label):
        assert _leading_run(GRADE, MUST_REFUSE[label]) is not None

    @pytest.mark.parametrize("label", sorted(MUST_GRANT))
    def test_every_grant_sentence_reaches_the_zero_branch(self, label):
        assert _leading_run(RATING, MUST_GRANT[label]) is not None

    def test_neither_variable_name_carries_the_vocabulary(self):
        # `Berth occupancy count` would be attributed by its own name.
        for var in (GRADE, RATING):
            assert not premises.DISCRETENESS.search(var["name"])


class TestTheFeatureCellIsShared:
    """THE RESULT. One feature vector, both populations, opposite required
    answers -- so no rule over these features separates them.

    A FAILURE HERE IS NEWS AND NOT A BUG. It means a feature has gained
    separating power, which is the exit this round says the work needs. Read the
    new feature, confirm it rests on the paper's account of how the variable was
    derived rather than on a boundary, and retire this class.
    """

    def test_both_populations_occupy_one_cell(self):
        refuse = {_features(GRADE, s) for s in MUST_REFUSE.values()}
        grant = {_features(RATING, s) for s in MUST_GRANT.values()}
        assert refuse == grant == {(True, True, 0.0)}, (
            f"must-refuse cells {sorted(refuse)}, must-grant cells {sorted(grant)}")

    def test_the_cell_holds_every_sentence_of_both_populations(self):
        assert len(MUST_REFUSE) == 8 and len(MUST_GRANT) == 4


class TestNoCandidateRuleSeparatesThem:
    """Each candidate is measured on BOTH populations. A rule that refuses the
    leaks by refusing the honest shapes has bought nothing."""

    @pytest.mark.parametrize("label", sorted(MUST_REFUSE))
    def test_uniform_refuses_the_leak(self, label):
        assert not _verdict(UNIFORM, GRADE, MUST_REFUSE[label])

    @pytest.mark.parametrize("label", sorted(MUST_GRANT))
    def test_and_uniform_refuses_the_honest_shape_too(self, label):
        assert not _verdict(UNIFORM, RATING, MUST_GRANT[label]), (
            "uniform would keep this licence, so the cell is not shared after all")

    @pytest.mark.parametrize("label", sorted(MUST_REFUSE))
    def test_the_subject_probe_closes_nothing(self, label):
        assert _verdict(SUBJECT, GRADE, MUST_REFUSE[label]), (
            "a fronted gerund has no finite verb, exactly as a bare predicate "
            "has none -- if this now refuses, the probe has changed")

    @pytest.mark.parametrize("label", sorted(MUST_GRANT))
    def test_the_subject_probe_keeps_the_honest_shapes(self, label):
        assert _verdict(SUBJECT, RATING, MUST_GRANT[label])

    @pytest.mark.parametrize("label", sorted(MUST_REFUSE))
    def test_only_the_comma_count_separates_these_sentences(self, label):
        assert not _verdict(LONE, GRADE, MUST_REFUSE[label])

    def test_and_the_comma_count_still_costs_an_honest_licence(self):
        # The fronted gerund over the variable's own constituents is two runs,
        # so the comma count refuses it exactly as it refuses a rival's.
        kept = [k for k in MUST_GRANT if _verdict(LONE, RATING, MUST_GRANT[k])]
        assert len(kept) == 3, kept
        assert "a fronted gerund counting this variable's own constituents" \
            not in kept


class TestTheClassSurvivesEveryCandidate:
    """THE REASON NOT TO SHIP `lone`. Twelve ordinary rewrites of the same rival
    claim are granted by every candidate, so the comma count closes the
    INSTANCES the verifier wrote and not the CLASS it named."""

    @pytest.mark.parametrize("label", sorted(SURVIVES_ANYTHING))
    @pytest.mark.parametrize("rule,name",
                             [(UNIFORM, "uniform"), (SUBJECT, "subject"),
                              (LONE, "lone")])
    def test_every_candidate_still_grants(self, rule, name, label):
        assert _verdict(rule, GRADE, SURVIVES_ANYTHING[label]), (
            f"{name} refused {label!r}; if a candidate has gained power over "
            "the trailing and the name-dropping rewrites, re-measure the table "
            "in this module's docstring before acting on it")

    def test_the_trailing_rewrite_is_the_leading_one_moved(self):
        # Same words, same rival, same claim -- only the position differs, and
        # the leading spelling is refused by `lone` while the trailing one is
        # not. That difference is a comma, which an author is free not to write.
        leading = MUST_REFUSE["after counting a rival"]
        trailing = SURVIVES_ANYTHING["T trailing `after counting <rival>`"]
        for phrase in ("after counting loose bollards in whole units",
                       "to the nearest half point"):
            assert phrase in leading.lower() and phrase in trailing.lower()
        assert not _verdict(LONE, GRADE, leading)
        assert _verdict(LONE, GRADE, trailing)
