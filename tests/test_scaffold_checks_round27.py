"""ROUND 27 -- AN ORDINARY SECOND MENTION DISARMED THE PER-WHAT GUARD.

Round 26 shipped the question no earlier round asked -- PER WHAT was the
whole-number claim made? -- and it works: `graded in whole points at each of
three inspections` establishes the step for an INSPECTION, the table prints one
number per COLONY, and the sentence licence falls back to `assumed`.

It was disarmed by one more whole-number word.

    `discreteness_is_per` withdrew on `if said and all(said)`: EVERY surviving
    vocabulary match in the located sentence had to be made per something else.
    So a second mention -- about the CARD, the FORM, the RESPONSE OPTIONS, or a
    rival quantity -- restored the licence and with it a per-subject step of 1.

MEASURED at `ec8cc12c`, on the DEFAULT path, no flag and no model, on a card the
paper itself grades to the nearest half point: seven probe sentences of the
shape, **five licensed a step of 1 and GRIM, GRIMMER and SPRITE all returned
`impossible` on every one of the five**. The other two were refused for reasons
that have nothing to do with unanimity and are pinned below so nobody reads them
as the guard working.

AND FIVE SENTENCES ARE A DEFECT REPORT, NOT A CLASS. A second battery of twenty
was written after the fix and against it -- the rescuing mention before the
distributed claim, inside a parenthesis, in a relative clause, behind a
semicolon, behind a dash, as an apposition, three mentions deep, naming the
variable, possessive, and both branches. **Sixteen of the twenty licensed a step
of 1 under the old rule, three `impossible` verdicts each; all sixteen are
closed, and the four that never licensed are named rather than counted.**

# THE RULE THAT SHIPS, AND WHY IT IS NOT A BARE `any`

    A whole-number claim THIS VARIABLE'S OWN ASSERTION makes, and makes per
    something that is not the subject, withdraws the sentence licence --
    whatever else the sentence says about granularity.

Two halves, and each has a polarity that must be stated:

  * ONE IS ENOUGH (`any`, not `all`). That is the averaging family's policy and
    not this premise's own -- `granularity_verification` states it at the call
    site: "a veto anywhere in the sentence beats an establishment anywhere in
    it -- the paper has said both, and refusing is the only reading that cannot
    accuse an honest paper". Round 26 made this the one member of the family a
    second mention could disarm.
  * AND IT MUST BE THIS VARIABLE'S. `..., and damaged frames were counted in
    whole units at each of three inspections` is a per-observation claim about
    something else and says nothing about the target, so it does not withdraw.
    Without that restriction the rule is a bare `any` and costs honest checks
    for a rival's adjunct; `TestTheRuleIsAboutTheTargetAndNotTheSentence`
    measures the difference rather than asserting it.

# THE UNANIMITY RULE RESTED ON A DISTINCTION THIS READER DOES NOT HAVE

That is the finding, and it is why the fix is a rule change and not a patch.
Round 26 pinned a rescuer; the probe supplied a disarmer; they are the same
sentence:

    ... by each of two luthiers, and the figure entered in the ledger for the
        instrument is itself recorded in whole units.          (round 26, kept)
    ... at each of three inspections, and the card was printed in whole units.
                                                              (round 27, probe)

Both coordinate a second assertion whose subject names something the account
never declared. One means the REPORTED VALUE is whole and the other means the
INSTRUMENT is. No feature of the words separates them -- the same shape as round
26's own built-measured-and-removed distributive branch, where `each participant
gave one whole-number rating` and `each keeper gave one whole-number grade` are
the same sentence. A rule that keeps the first keeps the second, and the second
manufactures an accusation on a paper that disclosed its own granularity.

A REPORTED-VALUE LEXICON WOULD SEPARATE THEM AND IS NOT SHIPPED: `the figure
entered`, `the value recorded`, `the final score` against `the card`, `the
form`, `the sheet`. It would GRANT a licence off a closed list of nouns, which
is the polarity that must fail closed and the shape every round since the sixth
has defeated. The honest answer is that the sentence is ambiguous and the
ambiguity costs a check.

# WHAT IT COSTS, MEASURED ON PROSE WRITTEN FOR IT

The pinned suite cannot adjudicate this premise -- every granularity call it
makes comes from the two files the rounds that wrote these rules also wrote --
so the cost is measured here, A/B against the guard disabled, on an honest
whole-numbered companion where a kept licence is a CHECK THAT RUNS:

    honest sentences carrying a second whole-numbered thing        21
      of which the free path licensed before this round            21
      LICENCES LOST                                                 5
      lost to the target's own per-observation claim (all 5)         5
      lost to a RIVAL's per-observation claim                        0

The five are in `COSTS` and every one of them states the step for an OCCASION
and then states it again in a second assertion -- which is exactly the
ambiguity above, paid for on the honest side. `KEEPS` holds the sixteen that
survive, twelve of them carrying a second whole-number mention and four
carrying another quantity's per-observation claim; a bare `any` loses those four
as well, which is the measurement that justifies the second half of the rule.

THE ACCUSATION ARM IS FREE OF CHARGE: all seven probes are refused, and the
tools accuse nobody on any sentence in this file.

# THE FIXTURE TRAP, WHICH HAS NOW BITTEN THIS PREMISE FOUR TIMES

The first probe of this defect was TOOTHLESS and read as perfect safety: its
bounds quote and its granularity quote were the same sentence, so a probe
sentence that did not itself print `0 to 18` failed the BOUNDS premise and GRIM,
GRIMMER and SPRITE refused for `bound_quote_does_not_state_it`
([[a-fixture-that-excludes-the-defect-region]]). Two rails here, both executed:

  * THE BOUNDS HAVE THEIR OWN SENTENCE (`BOUND_C`), and the granularity quote is
    never the bounds quote -- asserted, not assumed.
  * THE TEETH ARE SHOWN. `TestTheFixtureHasTeeth` disables the guard under test
    and the five accusations come back, three tools each. A file whose probes
    pass because nothing could ever fire is not evidence.

AND THE ACCUSATION IS DEMONSTRABLY FALSE, not assumed false. `COMB` is a real
37-value half-point sample inside the card's own bounds whose printed mean and
SD ARE the ones the table prints, under rounding and under truncation both. The
data exists; no integer total over 37 reaches that mean; the step is 0.5. Every
`impossible` in this file is manufactured by us.

THE FIXTURE PAPER IS AN UPLAND APIARY COMB SURVEY and shares no sentence, scale,
noun or number with the violin-workshop, pool, orchard, kiln, depot,
seed-library, harbour, lighthouse, printworks, allotment, keying-bureau or
school-canteen fixtures of earlier rounds.
"""

from __future__ import annotations

import statistics as st
from decimal import ROUND_HALF_UP, Decimal

import pytest

from forensic_metascience_ai_toolkit.scaffold import checks, premises

BAD = {"suspicious", "highly_suspicious", "impossible"}

# --------------------------------------------------------------------------
# The Kirkhollow apiary comb survey
# --------------------------------------------------------------------------

#: Comb uniformity, graded 0-18 to the NEAREST HALF POINT, one row per COLONY.
#: A REAL SAMPLE AND NOT A CONSTRUCTED PAIR: these 37 values are what the paper
#: measured, they all sit on the half point and inside the card, and the mean
#: and SD the table prints are theirs. So a step of 1 granted here convicts a
#: paper whose own data is on the page.
COMB = [3.0, 4.5, 4.5, 5.0, 5.0, 5.0, 5.5, 5.5, 6.5, 7.0, 7.5, 8.0, 8.5, 8.5,
        8.5, 8.5, 9.0, 9.0, 9.0, 9.5, 10.0, 10.0, 10.0, 10.0, 10.0, 11.0, 11.5,
        11.5, 11.5, 11.5, 12.5, 12.5, 12.5, 13.0, 14.5, 17.5, 17.5]
N = len(COMB)
V_MEAN = f"{st.fmean(COMB):.2f}"
V_SD = f"{st.stdev(COMB):.2f}"
assert N == 37
assert (V_MEAN, V_SD) == ("9.31", "3.42")
assert all(0 <= x <= 18 and (x * 2) % 1 == 0 for x in COMB)


def _reaches(total, mean_s: str) -> bool:
    """Does this total reach the printed mean under EITHER convention?

    BOTH ARE ASKED. GRIM in this repo carries the truncation rescue (`642a6f1`),
    so a fixture built on round-half-up alone is not a known answer at all
    ([[independence-in-process-is-not-independence]]).
    """
    q = Decimal(total) / Decimal(N)
    half = q.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return str(half) == mean_s or f"{Decimal(int(q * 100)) / Decimal(100):.2f}" == mean_s


#: THE PROPERTY THE WHOLE FILE RESTS ON: no integer total over 37 observations
#: reproduces this mean under rounding OR truncation, and the sample's own
#: half-integer total does. A step of 1 therefore makes GRIM say `impossible`
#: about a measure whose data is sitting in `COMB`.
assert not any(_reaches(k, V_MEAN) for k in range(N * 18 + 1)), V_MEAN
assert _reaches(Decimal(str(sum(COMB))), V_MEAN)

#: The honest WHOLE-number companion on the same card. It is the control that
#: says a guard which bought safety by refusing everything would fail here: its
#: licence comes from the PAPER'S OWN SENTENCE and not from its kind, so this
#: round can take it away -- which is what a coverage cost is.
CELLS = [(i * 5 + 2) % 19 for i in range(N)]
assert len(CELLS) == N
C_MEAN = f"{st.fmean(CELLS):.2f}"
C_SD = f"{st.stdev(CELLS):.2f}"

N_Q = "Thirty-seven colonies were surveyed across the Kirkhollow apiaries (n = 37)."
#: THE BOUNDS SENTENCES, WHICH ARE NEVER THE GRANULARITY SENTENCE. They carry no
#: discreteness vocabulary, so they license nothing on their own, and they keep
#: the bounds premise satisfied while a probe sentence says whatever it likes.
#: Without them every probe below refuses for `bound_quote_does_not_state_it`
#: and the file reads as perfect safety.
BOUND_C = "Comb uniformity was graded on a card running from 0 to 18."
BOUND_Q = "Queen cells were recorded on a card running from 0 to 18."
#: What the paper actually says about the half-point card, in full.
HONEST = "Comb uniformity was graded to the nearest half point."
#: The companion's own plain sentence, which must keep its licence throughout.
GRAN_C = "Queen cells were counted in whole units."


def var(vid, name, quote, lower, upper, *, kind="ordinal", bound_quote=None):
    return {"id": vid, "name": name, "label": name, "printed_as": [],
            "kind": kind, "role": None, "units": None,
            "units_source": "not_stated", "derivation": None, "derived_from": [],
            "bounds": {"source": "stated", "lower": lower, "upper": upper,
                       "quote": bound_quote or quote},
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
            "coordinate": {"study_id": "study:kirkhollow",
                           "group_id": "grp:colonies", "phase_id": None}}


def account(variables, values):
    return {"paper": {"doi": "10.0000/kirkhollow",
                      "title": "Comb condition in eleven upland apiaries",
                      "species_or_population": "honey bee colonies"},
            "subjects": {"population": "managed colonies in upland apiaries",
                         "unit_of_analysis": "a colony"},
            "studies": [{"id": "study:kirkhollow", "design": "prospective_cohort",
                         "groups": [{"id": "grp:colonies",
                                     "label": "All colonies", "n": N,
                                     "n_source": "text"}]}],
            "variables": variables, "values": values,
            "document": {"tables": [
                {"id": "table:1", "caption": "Table 1. Colony-level condition.",
                 "footnotes": []}]}}


def comb_paper(sentence):
    """The apiary paper whose granularity sentence for Comb uniformity -- the
    HALF-POINT card -- is `sentence`.

    THE MEAN AND THE SD SHARE A CELL, which is what lets GRIMMER and SPRITE run
    beside GRIM: `premises._partners` pairs on `(table, row, col)`, and a
    `Mean (SD)` column is one cell holding two values.
    """
    variables = [var("var:comb", "Comb uniformity", sentence, 0, 18,
                     bound_quote=BOUND_C)]
    values = [cell("val:cm", "mean", V_MEAN, "var:comb", 1, "Mean (SD)"),
              cell("val:cs", "sd", V_SD, "var:comb", 1, "Mean (SD)"),
              cell("val:cn", "n", str(N), "var:comb", 2, "n")]
    text = "\n\n".join(["## Methods", N_Q, BOUND_C, sentence]) + "\n"
    return account(variables, values), text


def cells_paper(sentence):
    """The same paper with `sentence` offered for the WHOLE-NUMBER companion.

    The coverage battery runs here rather than on the half-point card, because
    on an honest whole-unit measure a kept licence is a CHECK THAT RUNS and a
    withdrawn one is a check refused. The kind stays `ordinal` on purpose: a
    `count` is licensed by `DISCRETENESS_NECESSARY_KINDS` whatever any sentence
    says, and nothing this round does could be measured on it.
    """
    variables = [var("var:cells", "Queen cells", sentence, 0, 18,
                     bound_quote=BOUND_Q)]
    values = [cell("val:qm", "mean", C_MEAN, "var:cells", 1, "Mean (SD)"),
              cell("val:qs", "sd", C_SD, "var:cells", 1, "Mean (SD)"),
              cell("val:qn", "n", str(N), "var:cells", 2, "n")]
    text = "\n\n".join(["## Methods", N_Q, BOUND_Q, sentence]) + "\n"
    return account(variables, values), text


def accusations(acc, text):
    return sorted({(r["check_id"], r["severity"])
                   for r in checks.evaluate(acc, text)["checks"]
                   if r["severity"] in BAD})


def families(acc, text):
    return sorted((r["family"], r["variable_id"], r["severity"])
                  for r in checks.evaluate(acc, text)["checks"])


def verification(acc, text, vid="var:comb", verdict=None):
    hay = premises.Haystack(text)
    variables = premises.readable_variables(acc)
    v = [x for x in variables if x["id"] == vid][0]
    mine = [x for x in acc["values"] if x.get("variable_id") == vid]
    return premises.granularity_verification(
        v, hay, variables, mine, verdict,
        passages=premises.table_passages(acc, mine),
        subjects=premises.subject_terms(acc))


def convicted(sentence):
    """Did the HALF-POINT card keep a licence it must not have?"""
    acc, text = comb_paper(sentence)
    return verification(acc, text)["establishes_step_of_one"]


def licensed(sentence):
    """Did the honest WHOLE-NUMBER companion keep its step of 1?"""
    acc, text = cells_paper(sentence)
    return verification(acc, text, "var:cells")["establishes_step_of_one"]


def without_the_guard(fn):
    """Run `fn` with the mention test disabled, which is `ec8cc12c`'s rule.

    THE A/B ARM, AND IT IS EXACT RATHER THAN APPROXIMATE. `_mention_speaks_for_
    this` returning False is not a weakening of the shipped rule -- it deletes
    the branch, leaving `if said and all(said)`, which is round 26's function
    character for character. So every `before` in this file is what the previous
    commit did, measured rather than remembered.
    """
    real = premises._mention_speaks_for_this
    premises._mention_speaks_for_this = lambda text, spans, pos, var: False
    try:
        return fn()
    finally:
        premises._mention_speaks_for_this = real


def as_a_bare_any(fn):
    """Run `fn` with the mention test answering YES to everything, which is the
    rule this round considered and did not ship: withdraw on ANY distributed
    match, whoever it is about."""
    real = premises._mention_speaks_for_this
    premises._mention_speaks_for_this = lambda text, spans, pos, var: True
    try:
        return fn()
    finally:
        premises._mention_speaks_for_this = real


# --------------------------------------------------------------------------
# The probe that found it
# --------------------------------------------------------------------------

#: THE CONTROL. Round 26's guard, working: the claim is made per INSPECTION and
#: the table prints one number per colony.
CONTROL = "Comb uniformity was graded in whole points at each of three inspections."

#: THE FIVE THAT DISARMED IT at `ec8cc12c`. Each is the control plus one
#: ordinary second mention -- about the card, the form, the response options, or
#: a rival quantity -- and each licensed a step of 1 on the half-point card.
DISARMED = {
    "plus a card printed in whole units":
        "Comb uniformity was graded in whole points at each of three inspections, "
        "and the card was printed in whole units.",
    "plus a form accepting integers":
        "Comb uniformity was graded in whole points at each of three inspections, "
        "and the form accepted integers only.",
    "plus nineteen response options":
        "Comb uniformity was graded in whole points at each of three inspections "
        "and offered nineteen response options.",
    "plus a rival counted in whole units":
        "Comb uniformity was graded in whole points at each of three inspections, "
        "and damaged frames were counted in whole units.",
    "the sub-unit branch, plus a card":
        "Comb uniformity was recorded as a whole number of quarter points, "
        "and the card was printed in whole units.",
}

#: AND THE TWO THAT DID NOT, WHICH ARE PINNED SO NOBODY READS THEM AS THE GUARD
#: WORKING. `a Likert card` sits inside the same window as the cardinal, so the
#: second mention is distributed too and unanimity survived; `the number of
#: frames` never became a mention at all, because `_NUMBER_OF` asks a
#: noun-phrase head WHAT IT COUNTS and the answer is not this variable. Both
#: were refused for a reason unrelated to the defect.
REFUSED_ANYWAY = {
    "plus a Likert card":
        "Comb uniformity was graded in whole points at each of three inspections "
        "using a Likert card.",
    "plus the number of frames":
        "Comb uniformity was graded in whole points at each of three inspections, "
        "alongside the number of frames present.",
}

#: A SECOND BATTERY, WRITTEN AFTER THE FIX AND AGAINST IT. Five sentences are a
#: defect report, not a class, so the same disarm was written twenty more ways:
#: the rescuing mention BEFORE the distributed claim, inside a parenthesis, in a
#: relative clause, behind a semicolon, behind a dash, as an apposition, three
#: mentions deep, naming the variable, possessive, and both branches. SIXTEEN of
#: the twenty licensed a step of 1 under the old rule -- three `impossible`
#: verdicts each -- and all sixteen are closed. The four marked in
#: `FRESH_WITHOUT_TEETH` never licensed either way and are kept so nobody reads
#: them as this guard working.
FRESH = {
    "the card first":
        "The card was printed in whole units, and comb uniformity was graded in "
        "whole points at each of three inspections.",
    "the form first, behind a semicolon":
        "The form accepted integers only; comb uniformity was graded in whole "
        "points at each of three inspections.",
    "the rescuer in a parenthesis":
        "Comb uniformity was graded in whole points at each of three inspections "
        "(the card was printed in whole units).",
    "a subject-less parenthesis":
        "Comb uniformity was graded in whole points at each of three inspections "
        "(recorded in whole units).",
    "a relative clause on the occasions":
        "Comb uniformity was graded in whole points at each of three inspections, "
        "which were logged in whole units.",
    "a relative clause on the card":
        "Comb uniformity was graded in whole points at each of three inspections "
        "on a card that carries whole units.",
    "an apposition naming the figure":
        "Comb uniformity was graded in whole points at each of three inspections, "
        "the colony figure being an integer.",
    "round 26's own pinned rescuer":
        "Comb uniformity was graded in whole points at each of three inspections, "
        "and the figure entered in the ledger is itself recorded in whole units.",
    "three mentions, one distributed":
        "Comb uniformity was graded in whole points at each of three inspections, "
        "the card was printed in whole units, and the form accepted integers only.",
    "the rescuer behind a semicolon":
        "Comb uniformity was graded in whole points at each of three inspections; "
        "the card was printed in whole units.",
    "the rescuer repeats the variable":
        "Comb uniformity was graded in whole points at each of three inspections; "
        "comb uniformity is recorded in whole units.",
    "the rescuer behind a dash":
        "Comb uniformity was graded in whole points at each of three inspections "
        "-- the card was printed in whole units.",
    "sub-unit, rescuer in a parenthesis":
        "Comb uniformity was recorded as a whole number of quarter points (the "
        "card was printed in whole units).",
    "sub-unit, rescuer behind a semicolon":
        "Comb uniformity was recorded as a whole number of quarter points; the "
        "form accepted integers only.",
    "sub-unit, on a Likert card":
        "Comb uniformity was recorded as a whole number of quarter points on a "
        "Likert card.",
    "sub-unit, three mentions":
        "Comb uniformity was recorded as a whole number of quarter points, the "
        "card was printed in whole units, and nineteen response options were "
        "offered.",
    "rescued inside one assertion":
        "Comb uniformity was graded in whole points at each of three inspections "
        "and recorded in whole units.",
    "the distribution fronted":
        "Graded in whole points at each of three inspections, comb uniformity was "
        "entered in whole units.",
    "the rescuer names the variable":
        "Comb uniformity was graded in whole points at each of three inspections, "
        "and comb uniformity is stored as an integer.",
    "the rescuer is a possessive":
        "Comb uniformity was graded in whole points at each of three inspections, "
        "and each colony's comb uniformity is an integer.",
}

#: THE FOUR OF THE TWENTY THAT NEVER LICENSED, under the old rule or the new
#: one. Each is refused by machinery that predates this round -- a relative
#: clause and an apposition are constituents round 22 refuses to attribute, and
#: the fronted participle has no subject its assertion can be read against -- so
#: counting them as closures would inflate the result.
FRESH_WITHOUT_TEETH = {"a relative clause on the occasions",
                       "a relative clause on the card",
                       "an apposition naming the figure",
                       "the distribution fronted"}

ALL_PROBES = {"the control": CONTROL, **DISARMED, **REFUSED_ANYWAY, **FRESH}


class TestTheProbeIsClosed:
    """THE DEFECT, AND THE STATE IT IS LEFT IN."""

    @pytest.mark.parametrize("label", sorted(ALL_PROBES))
    def test_no_probe_licenses_a_step_of_one(self, label):
        assert not convicted(ALL_PROBES[label])

    @pytest.mark.parametrize("label", sorted(ALL_PROBES))
    def test_and_no_tool_accuses_the_paper(self, label):
        acc, text = comb_paper(ALL_PROBES[label])
        assert accusations(acc, text) == []

    def test_the_honest_sentence_is_still_read_honestly(self):
        """THE PAPER'S OWN WORDS. It says half point, it is not licensed, and
        nothing accuses it -- which is the state every probe above now joins."""
        assert not convicted(HONEST)
        acc, text = comb_paper(HONEST)
        assert accusations(acc, text) == []

    def test_the_refusal_names_the_words_it_refused_on(self):
        """A REFUSAL THAT NAMES NOTHING IS WORTH LESS THAN ONE THAT NAMES THE
        WORDS. `discreteness_claim_is_per` is what an auditor goes and looks
        at."""
        acc, text = comb_paper(DISARMED["plus a card printed in whole units"])
        rec = verification(acc, text)
        assert rec["discreteness_claim_is_per"] == "three inspections"
        assert rec["discreteness_claim_is_per_in"] == "granularity_quote"
        assert rec["discreteness_source"] == premises.ASSUMED_DISCRETENESS

    def test_the_sub_unit_refusal_names_its_own_words(self):
        acc, text = comb_paper(DISARMED["the sub-unit branch, plus a card"])
        assert verification(acc, text)["discreteness_claim_is_per"] == "quarter points"


class TestTheFixtureHasTeeth:
    """A PROBE THAT CANNOT FIRE IS NOT EVIDENCE, AND THIS FILE'S FIRST ANCESTOR
    COULD NOT FIRE. Every `not convicted` above is worth exactly as much as this
    class: with the guard under test removed, the five come back as three
    `impossible` verdicts each on a paper whose data is in `COMB`."""

    @pytest.mark.parametrize("label", sorted(DISARMED))
    def test_without_the_guard_the_step_is_licensed(self, label):
        assert without_the_guard(lambda: convicted(DISARMED[label]))

    @pytest.mark.parametrize("label", sorted(DISARMED))
    def test_without_the_guard_three_tools_accuse(self, label):
        def measure():
            acc, text = comb_paper(DISARMED[label])
            return {(f, s) for f, _, s in families(acc, text)}
        got = without_the_guard(measure)
        assert ("grim", "impossible") in got, label
        assert ("grimmer", "impossible") in got, label
        assert ("sprite", "impossible") in got, label

    @pytest.mark.parametrize(
        "label", sorted(set(FRESH) - FRESH_WITHOUT_TEETH))
    def test_the_second_battery_leaked_too_and_three_tools_accused(self, label):
        """SIXTEEN MORE, WRITTEN AFTER THE FIX AND AGAINST IT. A defect report
        of five sentences is not a class; these say the class is the RULE and
        not the phrasing, and every one of them accused."""
        def measure():
            acc, text = comb_paper(FRESH[label])
            return (verification(acc, text)["establishes_step_of_one"],
                    {(f, s) for f, _, s in families(acc, text)})
        step, got = without_the_guard(measure)
        assert step, label
        assert ("grim", "impossible") in got, label
        assert ("grimmer", "impossible") in got, label
        assert ("sprite", "impossible") in got, label

    @pytest.mark.parametrize("label", sorted(FRESH_WITHOUT_TEETH))
    def test_the_four_without_teeth_are_named_as_such(self, label):
        """THE HONEST DENOMINATOR IS SIXTEEN OF TWENTY. These four are refused
        by machinery older than this round, and reporting them as closures would
        inflate the result -- the shape this project has retired twice."""
        assert not without_the_guard(lambda: convicted(FRESH[label]))

    def test_the_two_that_were_refused_anyway_stay_refused_without_it(self):
        """THE OTHER HALF OF THE TEETH. If these fired under the A/B arm they
        would belong in `DISARMED`; they do not, and that is why the headline is
        five of seven and not seven of seven."""
        for label, sentence in sorted(REFUSED_ANYWAY.items()):
            assert not without_the_guard(lambda s=sentence: convicted(s)), label

    def test_the_bounds_are_their_own_sentence(self):
        """THE TRAP THAT MADE THE FIRST PROBE OF THIS DEFECT TOOTHLESS. A probe
        sentence does not state the card's range, so if the bounds premise read
        the GRANULARITY quote every tool would refuse for
        `bound_quote_does_not_state_it` and the file would read as perfect
        safety ([[a-fixture-that-excludes-the-defect-region]])."""
        acc, _ = comb_paper(CONTROL)
        v = acc["variables"][0]
        assert v["bounds"]["quote"] == BOUND_C
        assert v["granularity"]["quote"] == CONTROL
        assert v["bounds"]["quote"] != v["granularity"]["quote"]
        assert "0 to 18" not in v["granularity"]["quote"]

    def test_the_accusation_is_false_and_the_data_says_so(self):
        """NOT ASSUMED FALSE. The sample exists, sits on the half point, sits
        inside the card, and prints this mean and this SD under rounding and
        truncation both -- while no integer total over 37 reaches the mean."""
        assert f"{st.fmean(COMB):.2f}" == V_MEAN
        assert f"{st.stdev(COMB):.2f}" == V_SD
        assert _reaches(Decimal(str(sum(COMB))), V_MEAN)
        assert not any(_reaches(k, V_MEAN) for k in range(N * 18 + 1))
        assert sum(COMB) * 2 % 1 == 0 and sum(COMB) % 1 == 0.5


# --------------------------------------------------------------------------
# What it costs, on honest prose written for it
# --------------------------------------------------------------------------

#: HONEST SENTENCES ABOUT THE WHOLE-NUMBER COMPANION THAT KEEP THEIR LICENCE.
#: Every one states the step for the reported value and then mentions a SECOND
#: whole-numbered thing -- the instrument, a rival measure, the paperwork --
#: which is the shape the disarming probes have and which must not, on its own,
#: cost a check.
KEEPS = {
    # --- a second whole-number mention, nothing distributed ------------------
    "and the card was printed in whole units":
        "Queen cells were counted in whole units, and the card was printed in "
        "whole units.",
    "and the form accepted integers":
        "Queen cells were counted in whole units, and the form accepted "
        "integers only.",
    "and nineteen response options":
        "Queen cells were counted in whole units and the card offered nineteen "
        "response options.",
    "and a rival counted in whole units":
        "Queen cells were counted in whole units, and damaged frames were "
        "counted in whole units.",
    "and brood frames tallied too":
        "Queen cells were counted in whole units; brood frames were tallied in "
        "whole units as well.",
    "on an integer-only tablet":
        "Queen cells were counted in whole units on a tablet that accepted "
        "integers only.",
    "beside a Likert item":
        "Queen cells were counted in whole units, alongside a Likert item on "
        "keeper workload.",
    "and the ledger column holds integers":
        "Queen cells were counted in whole units, and the ledger column holds "
        "integers.",
    "and the number of frames was recorded":
        "Queen cells were counted in whole units, and the number of frames "
        "present was recorded.",
    "and mite drop counted in whole units":
        "Queen cells were counted in whole units; mite drop was counted in "
        "whole units on the same visit.",
    "with a whole-number checklist":
        "Queen cells were counted in whole units using a checklist scored in "
        "whole points.",
    "and the audit sheet is integers":
        "Queen cells were counted in whole units, and the audit sheet records "
        "integers throughout.",

    # --- a SECOND quantity's claim that IS distributed ----------------------
    # These four are what the `speaks for this` half of the rule buys. A bare
    # `any` loses every one of them for an adjunct that is not about the target.
    "a rival graded at each inspection":
        "Queen cells were counted in whole units, and damaged frames were "
        "counted in whole units at each of three inspections.",
    "a rival graded by each of two inspectors":
        "Queen cells were counted in whole units; comb uniformity was graded in "
        "whole points by each of two inspectors.",
    "a rival tallied on each of two boards":
        "Queen cells were counted in whole units, and mite drop was counted in "
        "whole units on each of two boards.",
    "a rival scored at each of three visits":
        "Queen cells were counted in whole units, and the entrance activity "
        "score was graded in whole points at each of three visits.",
}

#: AND THE HONEST SENTENCES THIS ROUND COSTS. Every one states the step for an
#: OCCASION or a SUB-UNIT and then says something whole-numbered again -- which
#: is the ambiguity the file's docstring argues cannot be resolved from the
#: words. On the half-point card the same shape buys three `impossible`
#: verdicts; here it costs four checks.
COSTS = {
    "per inspection, then the season total":
        "Queen cells were counted in whole units at each of three inspections, "
        "and the season total entered in the ledger is itself a whole number.",
    "per inspector, then the colony figure":
        "Queen cells were counted in whole units by each of two inspectors, "
        "and the figure recorded for the colony is an integer.",
    "per inspection, then the card":
        "Queen cells were counted in whole units at each of three inspections, "
        "and the card was printed in whole units.",
    "per inspection, then response options":
        "Queen cells were counted in whole units at each of three inspections "
        "and the card offered nineteen response options.",
    "a whole number of half units, then the card":
        "Queen cells were recorded as a whole number of half units, and the "
        "card was printed in whole units.",
}

HONEST_PROSE = {**KEEPS, **COSTS}


class TestWhatThisCosts:
    """THE COVERAGE ARM, WITH ITS DENOMINATOR CHECKED RATHER THAN QUOTED."""

    def test_every_honest_sentence_licensed_before_this_round(self):
        """THE DENOMINATOR IS MEASURED, NOT ASSUMED. A cost of `5 of 21` drawn
        over sentences the free path never licensed would be measuring nothing
        -- the shape this project has had to retire twice."""
        before = without_the_guard(
            lambda: {lab for lab, s in HONEST_PROSE.items() if licensed(s)})
        assert before == set(HONEST_PROSE), sorted(set(HONEST_PROSE) - before)

    @pytest.mark.parametrize("label", sorted(KEEPS))
    def test_the_sixteen_keep_their_licence(self, label):
        assert licensed(KEEPS[label])

    @pytest.mark.parametrize("label", sorted(COSTS))
    def test_the_five_are_the_price(self, label):
        assert not licensed(COSTS[label])

    def test_the_denominators_are_what_the_docstring_says(self):
        assert (len(KEEPS), len(COSTS)) == (16, 5)
        assert len(HONEST_PROSE) == 21
        assert (len(DISARMED), len(REFUSED_ANYWAY)) == (5, 2)
        assert (len(FRESH), len(FRESH_WITHOUT_TEETH)) == (20, 4)
        assert len(FRESH) - len(FRESH_WITHOUT_TEETH) == 16

    def test_the_price_is_a_check_and_never_an_accusation(self):
        """WHAT A WITHDRAWN LICENCE COSTS, STATED WHERE IT IS PAID: the checks
        the step of 1 would have bought. Nothing is accused either way, on the
        honest companion or on the half-point card."""
        for label, sentence in sorted(COSTS.items()):
            acc, text = cells_paper(sentence)
            assert accusations(acc, text) == [], label
            ran = len(families(acc, text))
            kept = without_the_guard(
                lambda s=sentence: len(families(*cells_paper(s))))
            assert ran < kept, label

    def test_no_honest_sentence_is_accused_either_way(self):
        for label, sentence in sorted(HONEST_PROSE.items()):
            acc, text = cells_paper(sentence)
            assert accusations(acc, text) == [], label


class TestTheRuleIsAboutTheTargetAndNotTheSentence:
    """THE SECOND HALF OF THE RULE, MEASURED RATHER THAN ARGUED. Withdrawing on
    ANY distributed match -- the obvious `any` -- closes the same five probes
    and ALSO takes the licence away for an adjunct attached to a quantity that
    is not the target. Four honest sentences say what that would cost."""

    RIVALS = ["a rival graded at each inspection",
              "a rival graded by each of two inspectors",
              "a rival tallied on each of two boards",
              "a rival scored at each of three visits"]

    def test_a_bare_any_would_lose_all_four(self):
        lost = as_a_bare_any(
            lambda: {lab for lab in self.RIVALS if not licensed(KEEPS[lab])})
        assert lost == set(self.RIVALS)

    def test_and_the_shipped_rule_keeps_all_four(self):
        assert all(licensed(KEEPS[lab]) for lab in self.RIVALS)

    def test_a_bare_any_closes_no_probe_the_shipped_rule_leaves_open(self):
        """THE PRICE BUYS NOTHING ON THE ACCUSATION SIDE, which is the whole
        argument for the restriction: same five closed, four honest licences
        kept."""
        still = as_a_bare_any(
            lambda: {lab for lab, s in ALL_PROBES.items() if convicted(s)})
        assert still == set()
        assert not any(convicted(s) for s in ALL_PROBES.values())

    def test_the_rivals_claim_is_read_as_the_rivals(self):
        """THE MECHANISM, NOT JUST THE OUTCOME. `_mention_speaks_for_this` asks
        the assertion's own subject who it is about, which is
        `_discreteness_licence`'s question asked of one match."""
        sentence = KEEPS["a rival graded at each inspection"]
        acc, text = cells_paper(sentence)
        rec = verification(acc, text, "var:cells")
        assert rec["discreteness_claim_is_per"] is None
        assert rec["establishes_step_of_one"] is True


class TestTheDirectionIsAConjunctOnALicence:
    """THE SAFETY ARGUMENT, EXECUTED RATHER THAN DOCUMENTED, and it is round
    26's own rail turned on round 26's rule: the new branch appears in ONE
    expression that RETURNS a refusal, so it can only ever turn a licence into a
    refusal. Asserted over every sentence in this file, both papers."""

    ALL = {**ALL_PROBES, **HONEST_PROSE}

    def test_it_never_turns_a_refusal_into_a_licence(self):
        before = without_the_guard(
            lambda: {lab for lab, s in self.ALL.items() if convicted(s)})
        after = {lab for lab, s in self.ALL.items() if convicted(s)}
        assert after <= before, sorted(after - before)

    def test_it_never_turns_a_refused_companion_into_a_licensed_one(self):
        before = without_the_guard(
            lambda: {lab for lab, s in self.ALL.items() if licensed(s)})
        after = {lab for lab, s in self.ALL.items() if licensed(s)}
        assert after <= before, sorted(after - before)

    def test_it_never_turns_a_clean_paper_into_an_accused_one(self):
        before = without_the_guard(
            lambda: {lab: accusations(*comb_paper(s))
                     for lab, s in self.ALL.items()})
        for lab, s in self.ALL.items():
            assert accusations(*comb_paper(s)) <= before[lab], lab

    def test_round_twenty_sixs_floor_is_kept(self):
        """WHERE EVERY SURVIVING MATCH IS PER SOMETHING ELSE the licence still
        falls, whether or not this reader could attribute any of them -- which
        is what makes this a superset of the rule it replaces rather than a
        different one. A sentence whose only assertion belongs to a quantity the
        account never declared is the case that reaches it."""
        sentence = ("Damaged frames were counted in whole units at each of "
                    "three inspections.")
        acc, _ = comb_paper(sentence)
        v = premises.readable_variables(acc)[0]
        spans = premises._assertion_spans(sentence)
        hits = [m for m, denied in premises._discreteness_hits(sentence, v)
                if denied is None]
        assert hits, sentence
        assert not any(premises._mention_speaks_for_this(
            sentence, spans, m.start(), v) for m in hits)
        assert premises.discreteness_is_per(
            sentence, v, premises.subject_terms(acc)) == "three inspections"

    def test_the_kind_licence_is_untouched(self):
        """A COUNT OF THINGS IS A WHOLE NUMBER OF THINGS whatever adjunct the
        sentence carries: this round narrows the SENTENCE licence and says
        nothing about the reported quantity being an average, so withdrawing the
        KIND's licence would supply a premise rather than narrow one (round 26's
        call, and round 24's before it)."""
        sentence = DISARMED["plus a card printed in whole units"]
        variables = [var("var:comb", "Comb uniformity", sentence, 0, 18,
                         kind="count", bound_quote=BOUND_C)]
        values = [cell("val:cm", "mean", V_MEAN, "var:comb", 1, "Mean (SD)"),
                  cell("val:cn", "n", str(N), "var:comb", 2, "n")]
        acc = account(variables, values)
        text = "\n\n".join(["## Methods", N_Q, BOUND_C, sentence]) + "\n"
        rec = verification(acc, text)
        assert rec["kind_makes_it_necessary"] is True
        assert rec["discreteness_source"] == premises.NECESSARY_DISCRETENESS
        assert rec["discreteness_claim_is_per"] == "three inspections"


class TestThePaidPathIsUntouched:
    """ROUND 25'S CALL AND ROUND 26'S, TAKEN AGAIN. Under a verdict this
    function replaces the SENTENCE TEST wholesale and this narrowing is part of
    that test: it is an absence-of-licence argument rather than the arithmetic
    fact `AVERAGED` carries, so it may not overrule a model that was shown the
    passage and asked. A model answering `true` on one of these is a model
    failure of round 24's class, and the veto for that class is a QUESTION put
    to a model, never a regex overruling one."""

    def test_a_model_true_still_grants_the_step(self):
        sentence = DISARMED["plus a card printed in whole units"]
        acc, text = comb_paper(sentence)
        verdict = {"establishes": True, "quote": sentence, "reason": "recorded",
                   "model": "sonnet"}
        assert verification(acc, text, verdict=verdict)["establishes_step_of_one"]

    def test_and_the_averaging_veto_still_beats_a_model_true(self):
        sentence = ("Comb uniformity was graded in whole points at each of three "
                    "inspections, and each colony's figure is the mean of the "
                    "three cards.")
        acc, text = comb_paper(sentence)
        verdict = {"establishes": True, "quote": sentence, "reason": "recorded",
                   "model": "sonnet"}
        rec = verification(acc, text, verdict=verdict)
        assert rec["establishes_step_of_one"] is False


class TestTheSpansAreTheLicencesOwnDecomposition:
    """ONE SPELLING OF THE BOUNDARY RULE, NOT TWO. `_assertion_spans` locates
    what `_clauses` and `assertion_segments` already produce; it does not
    re-split the text. This repo's recurring defect is two spellings of one rule
    written at different times with only one of them moved (CLAUDE.md 8j), and a
    splitter is exactly the shape it happens to."""

    def test_the_spans_are_the_segments_the_licence_walks(self):
        text = DISARMED["plus a rival counted in whole units"]
        spans = premises._assertion_spans(text)
        got = [text[a:b] for a, b in spans]
        want = [seg for clause in premises._clauses(text)
                for seg in premises.assertion_segments(clause)]
        assert got == want
        assert got == ["Comb uniformity was graded in whole points at each of "
                       "three inspections",
                       "damaged frames were counted in whole units."]

    def test_the_spans_are_ordered_and_do_not_overlap(self):
        for sentence in sorted({**ALL_PROBES, **HONEST_PROSE}.values()):
            spans = premises._assertion_spans(sentence)
            assert spans == sorted(spans)
            for (a, b), (c, _d) in zip(spans, spans[1:]):
                assert a < b <= c, sentence

    def test_a_match_in_no_span_is_read_as_the_clauses_own(self):
        """THE UNPLACEABLE CASE FAILS OPEN, which is the direction a refusal
        must fail in: a match this reader cannot site is treated as this
        variable's own and withdraws."""
        v = premises.readable_variables(comb_paper(CONTROL)[0])[0]
        assert premises._mention_speaks_for_this(CONTROL, [], 0, v) is True

    def test_no_second_splitter_was_written(self):
        """THE GREP RAIL. If a later round needs different boundaries here it
        owns the decision, and this test is where it says so."""
        import inspect
        src = inspect.getsource(premises._assertion_spans)
        assert "assertion_segments" in src and "_clauses" in src
        assert "re.compile" not in src and "split(" not in src
