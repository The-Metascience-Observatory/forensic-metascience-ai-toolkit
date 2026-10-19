"""ROUND 10 against the checks bridge and the premise-reading layer: five
false-accusation classes and one coverage defect, every one of them reproduced
from the fixture generation at `/tmp/checks_bridge_adversarial_round10/` against
the unchanged tree before anything here was written.

THE FIXTURE PAPER IS HONEST BY CONSTRUCTION. "The Thornbury masters swim-club
audit" -- thirty-two swimmers, two poolside cards and a club register -- shares
no variable, sentence, scale or n with the nine earlier adversarial papers. Every
printed number below is the exact summary of the real per-swimmer data in this
file, so any verdict worse than `consistent` or `indeterminate` on any of them is
a false accusation as a matter of arithmetic.

FOUR OF THE FIVE ARE THE SAME DEFECT: A GUARD WHOSE DIRECTION MAKES AN
UNDER-READING DANGEROUS. Each of these readers REFUSES when it sees more, so
every phrasing it cannot see is a check that runs:

  * `stated_ranges` counts the scales a sentence states, and the shared-scale
    lift fires when it sees one. It read four phrasings, so `from 0 through to
    10`, `from 0 up to 10`, `from zero to ten`, `from 0 to as much as 10`, `a
    card whose highest possible value is 10`, an abbreviations footnote and `the
    former ... the latter` each hid a SECOND scale and the lift came back.
  * `_CLAUSE_BREAK` carried a semicolon and four contrastive conjunctions, so an
    em dash, the `--` a PDF conversion prints, an en dash, a colon, a slash, a
    plain `, and` and a `, which` relative clause each left two independent
    clauses as one, and one quantity's whole-unit claim became another's.
  * `_SUBJECT_COUNT` and `_count_of` read a comma and nothing else, so `1 240
    members` put the ceiling on an alternative percentage base at 240 -- the
    TAIL of the number -- and an honest 6/1240 was `suspicious`.
  * `_ESTIMATOR_STATEMENT` could not see `weighted` inside `reweighted`, could
    not cross the hyphen of `inverse-probability weighted`, and carried neither
    `raked` nor `post-stratified` nor a table that `reports` something.

THE FIFTH IS THE ONE THAT SURVIVES A PAID READING, and it is structural rather
than lexical: under a model `true` on the step, `premises.AVERAGED` is the only
guard left on the granted licence, and every question `premise_reading` asked was
a question that could only GRANT. A model cannot withdraw a premise it is never
shown. So the vocabulary is widened AND the withdrawing question is now asked --
`premise_reading` surfaces the combination-shaped sentences and a `true` there
vetoes, with the refusal polarity that makes a wrong answer cost a check and
never buy an accusation.
"""

from __future__ import annotations

import statistics as st

from metascience_agent.scaffold import checks, premise_reading as PR, premises

BAD = {"suspicious", "highly_suspicious", "impossible"}

# --------------------------------------------------------------------------
# The Thornbury audit's real per-swimmer data
# --------------------------------------------------------------------------

#: Perceived exertion, whole points on a 0-6 poolside card.
EXERT = [3, 5, 2, 4, 1, 6, 3, 0, 4, 2, 5, 3, 1, 6, 4, 2,
         3, 5, 0, 4, 6, 1, 3, 2, 5, 4, 0, 6, 3, 1, 4, 3]

#: Pool comfort, whole points on a 0-10 card. A DIFFERENT card.
COMFORT = [8, 3, 10, 5, 9, 1, 7, 4, 10, 2, 6, 9, 3, 8, 0, 5,
           10, 7, 2, 9, 4, 8, 1, 6, 10, 3, 7, 5, 9, 2, 8, 6]

#: Pool comfort as a HALF-POINT card, which is what the clause-break fixture
#: reports: its mean does not move in whole units.
HALF = [8.0, 3.5, 10.0, 5.0, 9.5, 1.0, 7.0, 4.5, 10.0, 2.0,
        6.5, 9.0, 3.0, 8.5, 0.5, 5.5, 10.0, 7.5, 2.5, 9.0,
        4.0, 8.0, 1.5, 6.0, 10.0, 3.5, 7.0, 5.0, 9.5, 2.0,
        8.5, 6.0]

#: Two observers' whole-point cards; the comfort INDEX is their average, so it
#: moves in half points.
OBS_A = [8, 4, 10, 5, 9, 1, 7, 4, 10, 2, 7, 9, 3, 8, 0, 5,
         10, 8, 2, 9, 4, 8, 1, 6, 10, 4, 7, 5, 9, 2, 8, 6]
OBS_B = [8, 3, 10, 5, 10, 1, 7, 5, 10, 2, 6, 9, 3, 9, 1, 6,
         10, 7, 3, 9, 4, 8, 2, 6, 10, 3, 7, 5, 10, 2, 9, 6]
INDEX = [(a + b) / 2 for a, b in zip(OBS_A, OBS_B)]

#: The club register's age-sex margins, as weights on the audited swimmers.
WEIGHTS = [1.4, 0.8, 1.1, 0.9, 1.3, 0.7, 1.2, 1.0, 0.6, 1.5,
           0.9, 1.1, 0.8, 1.4, 1.0, 0.7, 1.2, 0.9, 1.3, 0.6,
           1.1, 1.0, 0.8, 1.5, 0.7, 1.2, 0.9, 1.4, 0.6, 1.3,
           1.0, 0.8]

N = len(EXERT)
#: The whole club register, and the members of it who hold a coaching badge.
REGISTER, QUALIFIED = 1240, 6

EXERT_MEAN, EXERT_SD = f"{st.fmean(EXERT):.2f}", f"{st.stdev(EXERT):.2f}"
COMFORT_MEAN, COMFORT_SD = f"{st.fmean(COMFORT):.2f}", f"{st.stdev(COMFORT):.2f}"
HALF_MEAN, HALF_SD = f"{st.fmean(HALF):.2f}", f"{st.stdev(HALF):.2f}"
IDX_MEAN, IDX_SD = f"{st.fmean(INDEX):.2f}", f"{st.stdev(INDEX):.2f}"
W_MEAN = f"{sum(w * x for w, x in zip(WEIGHTS, COMFORT)) / sum(WEIGHTS):.2f}"
W_SD = f"{st.stdev(COMFORT):.2f}"
QUALIFIED_PCT = f"{100.0 * QUALIFIED / REGISTER:.1f}"


def test_the_fixture_paper_is_honest():
    assert N == 32 and len(COMFORT) == 32 and len(HALF) == 32
    assert min(COMFORT) == 0 and max(COMFORT) == 10
    # Pool comfort on its own 0-10 card is an exact integer total over 32 and
    # clears every family; on the 0-6 card the account mis-records, its SD of
    # 3.06 exceeds the largest an 0-6 quantity with that mean can have.
    assert round(sum(COMFORT) / N, 2) == float(COMFORT_MEAN)
    assert float(COMFORT_SD) > (float(COMFORT_MEAN) * (6 - float(COMFORT_MEAN))) ** 0.5
    # The half-point card and the two-observer index do NOT move in whole units,
    # so a wrongly granted step of 1 makes GRIM call each of them impossible.
    for mean in (HALF_MEAN, IDX_MEAN):
        assert not any(round(k / N, 2) == float(mean) for k in range(N * 11))
    # And 6 of 1240 is the printed 0.5%, which the audited n of 32 cannot be.
    assert round(100.0 * QUALIFIED / REGISTER, 1) == float(QUALIFIED_PCT)


# --------------------------------------------------------------------------
# The paper's sentences, the account shapes, and the bridge runner
# --------------------------------------------------------------------------

N_Q = ("Thirty-two swimmers took part in the Thornbury masters swim-club audit "
       "(n = 32).")
G_EXERT = "Perceived exertion was scored in whole points at every session."
G_COMFORT = "Pool comfort was scored in whole points at every session."
B_COMFORT = "Pool comfort was rated on a card running from 0 to 10."

#: THE TWO-SCALE SENTENCE, printed eight ways. The first is round 9's shape, kept
#: as the control that already refused; the rest are round 10's.
TWO_SCALES = [
    ("respectively",
     "The poolside observer rated perceived exertion and pool comfort on cards "
     "running from 0 to 6 and from 0 to 10 respectively."),
    ("through to",
     "The poolside observer rated perceived exertion on a card running from 0 "
     "to 6 and pool comfort on a card running from 0 through to 10."),
    ("up to",
     "The poolside observer rated perceived exertion on a card running from 0 "
     "to 6 and pool comfort on a card running from 0 up to 10."),
    ("spelled out",
     "The poolside observer rated perceived exertion on a card running from 0 "
     "to 6 and pool comfort on a card running from zero to ten."),
    ("to as much as",
     "Cards ran from 0 to 6 for perceived exertion and, for pool comfort, from "
     "0 to as much as 10."),
    ("a stated maximum",
     "Perceived exertion was rated from 0 to 6 and pool comfort on a card whose "
     "highest possible value is 10."),
    ("an abbreviations footnote",
     "Note. RPE, perceived exertion, rated 0 to 6; PCS, pool comfort, rated up "
     "to 10"),
    ("the former and the latter",
     "The observer rated perceived exertion and pool comfort on two cards; the "
     "former runs from 0 to 6 and the latter from 0 through to 10."),
]

#: THE CLAUSE BREAK, written seven ways. The first two are round 7's fix, kept as
#: the controls that already refused.
SEPARATORS = ["; ", ", whereas ", " — ", " -- ", " – ", ": ", " / "]
#: AND THE EIGHTH, WHICH THE VOCABULARY DELIBERATELY DOES NOT SPLIT. See
#: `TestTheCoordinatedClauseIsLeftToTheModel`.
COORDINATED = ", and "
LEFT = "Wall touches were tallied in whole units"
RIGHT = "pool comfort was recorded to the nearest half point"

#: THE THOUSANDS SEPARATOR, five ways beyond the comma.
REGISTER_FORMS = ["1,240", "1240", "One thousand two hundred and forty",
                  "1 240", "1 240", "1 240", "1'240", "1.240"]

#: AN AVERAGE, worded four ways `premises.AVERAGED` could not see. The first
#: three are the shapes it already caught.
AVERAGES = [
    "The comfort index is the mean of the two observers' ratings.",
    "Each swimmer's comfort index is the average of the two cards.",
    "The two ratings were averaged to give the comfort index.",
    "The comfort index is the average of the two observers.",
    "The comfort index is the midpoint of the two cards.",
    "The comfort index is the two card scores added together and halved.",
    "The comfort index is the arithmetic mean of the pair.",
]

#: THE PAPER'S GOVERNING STATEMENT ABOUT ITS OWN MEANS, six ways. The first two
#: are the shapes `_ESTIMATOR_STATEMENT` already carried.
ESTIMATOR_STATEMENTS = [
    "Means were weighted to the age and sex margins of the club register.",
    "All means reported in Table 1 are weighted to the club register.",
    "Means were reweighted to the age and sex margins of the club register.",
    "Means are inverse-probability weighted to the club register.",
    "All summary statistics in Table 1 are post-stratified to the club register.",
    "Means were raked to the register's age and sex margins.",
    "Table 1 reports register-calibrated means.",
    "Each swimmer contributes to the reported mean in proportion to the size of "
    "her stratum on the register.",
]


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
         row=1, col=1):
    lit = _lit(printed)
    return {"id": vid, "statistic": statistic, "printed": printed,
            "numeric": lit.get("value"), "decimals": lit.get("decimals", 0),
            "printed_form": "percent" if lit.get("is_percent") else "plain",
            "units": None, "variable_id": variable_id, "id_check": "agrees",
            "statistic_disputed": False, "source": "table", "quote": None,
            "quote_verified": "cell", "printed_in_quote": None,
            "location": {"kind": "table_cell", "table_id": "table:1",
                         "row": row, "col": col, "col_label": col_label},
            "coordinate": {"study_id": "study:main", "group_id": "grp:all",
                           "phase_id": None}}


def prose(vid, statistic, printed, quote, *, variable_id=None, offset=0):
    lit = _lit(printed)
    return {"id": vid, "statistic": statistic, "printed": printed,
            "numeric": lit.get("value"), "decimals": lit.get("decimals", 0),
            "printed_form": "percent" if lit.get("is_percent") else "plain",
            "units": None, "variable_id": variable_id, "id_check": "agrees",
            "statistic_disputed": False, "source": "prose", "quote": quote,
            "quote_verified": "verbatim", "printed_in_quote": True,
            "location": {"kind": "prose", "offset": offset, "col_label": None},
            "coordinate": {"study_id": "study:main", "group_id": "grp:all",
                           "phase_id": None}}


def account(*, variables=(), values=(), reading=None):
    acc = {"paper": {"doi": "10.0000/thornbury",
                     "title": "The Thornbury masters swim-club audit"},
           "studies": [{"id": "study:main", "design": "prospective_cohort",
                        "groups": [{"id": "grp:all", "label": "All swimmers",
                                    "n": N, "n_source": "text"}]}],
           "variables": list(variables), "values": list(values),
           "document": {"tables": [{"id": "table:1",
                                    "caption": "Table 1. Poolside ratings of "
                                               "the audited swimmers."}]}}
    if reading is not None:
        acc["premise_reading"] = reading
    return acc


def reading(*verdicts, candidates=()):
    cands = list(candidates)
    return {"schema": PR.SCHEMA_VERSION, "prompt_version": PR.PROMPT_VERSION,
            "model": "sonnet", "n_candidates": len(cands), "n_asked": len(cands),
            "n_dropped": 0, "candidates": cands, "verdicts": list(verdicts),
            "problems": [], "cost_usd": 0.0, "n_calls": 1}


def cand(cid, premise, quote, *, variable_id=None, value_ids=(),
         source="served_text", asked_bounds=None):
    return {"id": cid, "premise": premise, "quote": quote,
            "variable_id": variable_id, "value_ids": list(value_ids),
            "source": source, "target": "the target", "context": "",
            "asked_bounds": asked_bounds, "question": PR.QUESTIONS[premise],
            "quote_located": True, "quote_not_located_because": ""}


def verdict(cid, premise, establishes, reason="a model reason"):
    return {"candidate_id": cid, "premise": premise, "establishes": establishes,
            "reason": reason, "model": "sonnet",
            "prompt_version": PR.PROMPT_VERSION}


def accusations(got):
    return [(r["check_id"], r["severity"]) for r in got["checks"]
            if r["severity"] in BAD]


def verification(acc, text, vid, field):
    stamped = premises.stamp(acc, text)
    by_id = {v["id"]: v for v in stamped["variables"]}
    return by_id[vid][field]["verification"]


# --------------------------------------------------------------------------
# 1. A SENTENCE THAT STATES TWO SCALES ESTABLISHES NEITHER, HOWEVER IT PRINTS
#    THE SECOND ONE
# --------------------------------------------------------------------------


def _two_cards(sentence):
    """The account that mis-split `sentence`: pool comfort's own card is 0-10
    and the reading recorded the neighbour's 0-6."""
    text = "\n\n".join([N_Q, sentence, G_EXERT, G_COMFORT]) + "\n"
    variables = [
        var("var:exert", "Perceived exertion", "ordinal", bsource="stated",
            lower=0, upper=6, bquote=sentence, step=1, gquote=G_EXERT),
        var("var:comfort", "Pool comfort", "ordinal", bsource="stated",
            lower=0, upper=6, bquote=sentence, step=1, gquote=G_COMFORT)]
    values = [prose("val:n", "n", str(N), N_Q),
              cell("val:cm", "mean", COMFORT_MEAN, variable_id="var:comfort",
                   row=2),
              cell("val:cs", "sd", COMFORT_SD, variable_id="var:comfort", row=2),
              cell("val:em", "mean", EXERT_MEAN, variable_id="var:exert"),
              cell("val:es", "sd", EXERT_SD, variable_id="var:exert")]
    return account(variables=variables, values=values), text


class TestASentenceStatingTwoScalesEstablishesNeither:
    def test_no_phrasing_of_the_second_scale_lifts_the_tie(self):
        for tag, sentence in TWO_SCALES:
            acc, text = _two_cards(sentence)
            assert accusations(checks.evaluate(acc, text)) == [], tag

    def test_the_lift_is_refused_and_the_record_says_so(self):
        for tag, sentence in TWO_SCALES:
            acc, text = _two_cards(sentence)
            rec = verification(acc, text, "var:comfort", "bounds")
            assert rec["quote_states_a_shared_scale_with"] is None, tag
            assert rec["bound_source"] == premises.ASSUMED_BOUND_SOURCE, tag

    def test_every_phrasing_states_two_scale_claims(self):
        for tag, sentence in TWO_SCALES:
            assert len(premises.scale_claims(sentence)) > 1, tag

    def test_the_ajcp_sentence_this_lift_exists_for_states_one(self):
        """The case the lift was built for is untouched: one scale, two
        variables, and both readings of the ambiguity admit the same bound."""
        one = ("The means for inclusive decision making and inclusion of "
               "community residents were 4.06 and 4.01 on a 1-5 scale")
        assert premises.scale_claims(one) == [(1.0, 5.0)]

    def test_two_one_sided_claims_are_one_scale_not_two(self):
        """A sentence naming both ends separately states ONE scale. Pairing them
        is what keeps the lift available to the paper that writes it that way."""
        both = ("Pool comfort was rated on the observer's card, whose lowest "
                "possible value is 0 and whose highest possible value is 10.")
        assert premises.scale_claims(both) == [(0.0, 10.0)]

    def test_a_restated_endpoint_is_not_a_second_scale(self):
        assert premises.scale_claims("a card running from 0 up to 10") == \
            [(0.0, 10.0)]


# --------------------------------------------------------------------------
# 2. A CLAUSE BREAK IS WHATEVER PUNCTUATION THE PAPER JOINED TWO CLAUSES WITH
# --------------------------------------------------------------------------


def _half_point(sentence):
    text = "\n\n".join([N_Q, B_COMFORT, sentence]) + "\n"
    variables = [var("var:comfort", "Pool comfort", "ordinal", bsource="stated",
                     lower=0, upper=10, bquote=B_COMFORT, step=1,
                     gquote=sentence)]
    values = [prose("val:n", "n", str(N), N_Q),
              cell("val:m", "mean", HALF_MEAN, variable_id="var:comfort"),
              cell("val:s", "sd", HALF_SD, variable_id="var:comfort")]
    return account(variables=variables, values=values), text


class TestAClauseBreakIsThePunctuationThePaperUsed:
    def test_no_separator_gives_one_quantitys_claim_to_another(self):
        for sep in SEPARATORS:
            sentence = LEFT + sep + RIGHT + "."
            acc, text = _half_point(sentence)
            assert accusations(checks.evaluate(acc, text)) == [], repr(sep)
            rec = verification(acc, text, "var:comfort", "granularity")
            assert rec["discreteness_source"] == premises.ASSUMED_DISCRETENESS, \
                repr(sep)

    def test_every_separator_splits_into_two_clauses(self):
        for sep in SEPARATORS:
            assert len(premises._clauses(LEFT + sep + RIGHT + ".")) == 2, repr(sep)

    def test_a_range_is_not_a_clause_break(self):
        """The dash and the colon guards. A spaced dash between digits is a
        range and an unspaced one is a compound; neither is two clauses."""
        for one in ("Scores ran from 0 - 6 on the card.",
                    "Scores ran from 0 – 6 on the card.",
                    "The allocation ratio was 3:1.",
                    "The session began at 10:30."):
            assert premises._clauses(one) == [one], one

    def test_the_honest_conjunction_is_still_one_clause(self):
        """`and` WITHOUT a comma joins a compound predicate about one subject,
        which is the sentence this whole gate exists to keep."""
        one = "Mood was rated on a 1 to 7 point scale and was scored in whole points"
        assert premises._clauses(one) == [one]

    def test_a_relative_clause_about_the_instrument_establishes_nothing(self):
        rel = ("Pool comfort was transcribed from the observer's tally sheet, "
               "which was kept in whole units.")
        acc, text = _half_point(rel)
        assert accusations(checks.evaluate(acc, text)) == []

    def test_a_tally_sheet_is_an_instrument_and_not_a_granularity_claim(self):
        assert not premises.DISCRETENESS.search("the observer's tally sheet")
        assert premises.DISCRETENESS.search("touches were tallied in whole units")

    def test_the_veto_is_still_clause_scoped(self):
        """Round 4's rule, and the reason the widening above stops where it
        does: an averaging clause about ANOTHER quantity does not withdraw this
        variable's step, the same rule the establishing clause is held to."""
        text = ("Mood was rated on a 1 to 7 point scale and was scored in whole "
                "points; the fidelity index is the mean of four item ratings.")
        v = var("var:mood", "Mood", "integer_score", step=1, gquote=text)
        rec = premises.granularity_verification(
            v, premises.Haystack(text), [v], [])
        assert rec["quote_reports_an_average"] is None
        assert rec["discreteness_source"] == premises.STATED_DISCRETENESS


class TestTheCoordinatedClauseIsLeftToTheModel:
    """`, and` IS NOT A CLAUSE BREAK HERE, AND BOTH SIDES OF THAT WERE MEASURED.

    Adding it closes the case below AND splits `Wellbeing was rated on a 1-7
    scale, and each participant gave one whole-number rating on that scale.` --
    this repo's own canonical known-answer fixture, whose discreteness clause
    then names no variable and whose step stops being established. The two
    sentences are the same shape and what separates them is whether the second
    subject is the variable or a person, which no boundary rule can see.

    THE FREE PATH NO LONGER LEAVES IT OPEN, AND NOT BY BECOMING A CLAUSE BREAK.
    Round 21 asks a different question of the same sentence -- not where the
    clause ends, but which ASSERTION inside it the discreteness word belongs to
    -- and `Wall touches were tallied in whole units` asserts about wall
    touches. The canonical fixture keeps its licence because `each participant
    gave one whole-number rating` asserts about nobody this reader can find and
    so belongs to its clause. The boundary rule still cannot tell the two
    apart; the subject rule can, and it is the one that decides.
    See `premises.assertion_segments`.

    THE MODEL PATH IS UNCHANGED AND IS STILL THE ONE THAT MATTERS, because the
    residue is the same shape: a competing assertion with a lexical verb this
    reader cannot find a subject before. The sentence is still surfaced as a
    `step` candidate, and a `false` still closes what the vocabulary cannot see.
    """

    def test_the_vocabulary_path_no_longer_accuses(self):
        """WAS `test_the_vocabulary_path_still_accuses_and_this_is_the_open_cost`,
        and it was pinning a FALSE ACCUSATION on an honest half-point paper as
        an accepted cost. Round 21 closed it. Measured at `680b150a`: this
        fixture returned GRIM `impossible`; it now refuses, with the record
        naming whose whole-unit claim it was."""
        acc, text = _half_point(LEFT + COORDINATED + RIGHT + ".")
        assert accusations(checks.evaluate(acc, text)) == []
        v = premises.readable_variables(acc)[0]
        rec = premises.granularity_verification(
            v, premises.Haystack(text), [v], [])
        assert rec["establishes_step_of_one"] is False
        assert rec["discreteness_belongs_to"] == "Wall touches"

    def test_the_sentence_reaches_the_model_as_a_step_candidate(self):
        acc, text = _half_point(LEFT + COORDINATED + RIGHT + ".")
        cands = [c for c in PR.candidates(acc, text) if c["premise"] == "step"]
        assert cands
        assert any(c["source"] == "account_quote" and RIGHT in c["quote"]
                   for c in cands)

    def test_a_model_false_closes_it(self):
        acc, text = _half_point(LEFT + COORDINATED + RIGHT + ".")
        cands = [c for c in PR.candidates(acc, text) if c["premise"] == "step"]
        read = reading(*[verdict(c["id"], "step", False,
                                 "the sentence says pool comfort was recorded "
                                 "to the nearest half point")
                         for c in cands], candidates=cands)
        acc = account(variables=acc["variables"], values=acc["values"],
                      reading=read)
        assert accusations(checks.evaluate(acc, text)) == []


# --------------------------------------------------------------------------
# 3. THE CEILING READS EVERY SEPARATOR A PAPER PUTS BETWEEN THOUSANDS
# --------------------------------------------------------------------------


def _register(printed):
    reg = f"The club register lists {printed} members."
    q = (f"{QUALIFIED} members of the register ({QUALIFIED_PCT}%) hold a "
         f"national coaching qualification.")
    text = "\n\n".join([N_Q, reg, q]) + "\n"
    variables = [var("var:qualified", "National coaching qualification",
                     "percentage_of_subjects")]
    values = [prose("val:n", "n", str(N), N_Q),
              prose("val:c", "count", str(QUALIFIED), q,
                    variable_id="var:qualified", offset=1),
              prose("val:p", "percentage", f"{QUALIFIED_PCT}%", q,
                    variable_id="var:qualified", offset=1)]
    return account(variables=variables, values=values), text, values


class TestTheCeilingReadsEveryThousandsSeparator:
    def test_no_separator_leaves_the_paper_accused(self):
        for printed in REGISTER_FORMS:
            acc, text, _ = _register(printed)
            assert accusations(checks.evaluate(acc, text)) == [], printed

    def test_the_register_is_read_whole_and_never_by_its_tail(self):
        for printed in REGISTER_FORMS:
            _, text, values = _register(printed)
            assert premises.paper_max_n(values, text) == REGISTER, printed
            assert 240 not in premises.printed_subject_counts(text), printed

    def test_the_alternative_base_the_paper_prints_is_named(self):
        for printed in REGISTER_FORMS:
            _, text, values = _register(printed)
            ceiling = premises.paper_max_n(values, text)
            assert premises.other_bases_that_fit(
                QUALIFIED, float(QUALIFIED_PCT), 1, N, ceiling)

    def test_a_divisor_still_refuses_every_separator(self):
        """The loose reader is the CEILING's and no one else's. `read_plain` is
        the gate on a number a tool will divide by, and a thousands separator and
        a decimal comma are undecidable per value."""
        for printed in ("1,240", "1 240", "1 240", "1'240", "1.240"):
            assert premises.is_plain_integer(printed) is None, printed


# --------------------------------------------------------------------------
# 4. AN AVERAGE IS VETOED HOWEVER THE PAPER WORDS IT -- ON BOTH PATHS
# --------------------------------------------------------------------------

GRAN_TWO_OBSERVERS = ("Pool comfort was rated in whole points by two "
                      "independent observers.")


def _index(sentence):
    text = "\n\n".join([N_Q, GRAN_TWO_OBSERVERS, sentence]) + "\n"
    variables = [var("var:comfort", "Pool comfort", "ordinal", step=1,
                     gquote=GRAN_TWO_OBSERVERS)]
    values = [prose("val:n", "n", str(N), N_Q),
              cell("val:m", "mean", IDX_MEAN, variable_id="var:comfort"),
              cell("val:s", "sd", IDX_SD, variable_id="var:comfort")]
    return account(variables=variables, values=values), text, variables, values


class TestAnAverageIsVetoedHoweverItIsWorded:
    def test_the_vocabulary_path_accuses_nobody(self):
        for sentence in AVERAGES:
            acc, text, _, _ = _index(sentence)
            assert accusations(checks.evaluate(acc, text)) == [], sentence

    def test_a_model_true_on_the_step_does_not_defeat_the_veto(self):
        """Under a verdict the averaging veto is the only guard left on a
        granted step, so it is the one that has to hold."""
        granted = cand("c1", "step", GRAN_TWO_OBSERVERS,
                       variable_id="var:comfort", source="account_quote")
        read = reading(verdict("c1", "step", True,
                               "Ratings in 'whole points' means each subject's "
                               "value is an integer on that scale."),
                       candidates=[granted])
        for sentence in AVERAGES:
            _, text, variables, values = _index(sentence)
            acc = account(variables=variables, values=values, reading=read)
            assert accusations(checks.evaluate(acc, text)) == [], sentence

    def test_a_group_mean_over_the_papers_own_n_is_not_an_average_of_two(self):
        """The cardinal branch must not touch the honest group mean this gate
        exists to keep, nor an ordinary results sentence."""
        for honest in ("the mean of the 28 patients",
                       "the mean of the children's scores",
                       "attendance averaged 82.5% of scheduled sessions",
                       "Body mass averaged 78.4 kg"):
            assert not premises.AVERAGED.search(honest), honest


# --------------------------------------------------------------------------
# 5. THE PAPER'S GOVERNING STATEMENT ABOUT ITS OWN MEANS IS READ, AND CAN BE
#    ASKED ABOUT
# --------------------------------------------------------------------------


def _weighted(statement):
    text = "\n\n".join([N_Q, B_COMFORT, G_COMFORT, statement]) + "\n"
    variables = [var("var:comfort", "Pool comfort", "ordinal", bsource="stated",
                     lower=0, upper=10, bquote=B_COMFORT, step=1,
                     gquote=G_COMFORT)]
    values = [prose("val:n", "n", str(N), N_Q),
              cell("val:m", "mean", W_MEAN, variable_id="var:comfort"),
              cell("val:s", "sd", W_SD, variable_id="var:comfort")]
    return account(variables=variables, values=values), text, variables, values


class TestAGoverningEstimatorStatementIsRead:
    def test_no_phrasing_leaves_the_weighted_mean_accused(self):
        for statement in ESTIMATOR_STATEMENTS:
            acc, text, _, _ = _weighted(statement)
            assert accusations(checks.evaluate(acc, text)) == [], statement

    def test_every_phrasing_is_the_papers_statement_about_its_own_means(self):
        for statement in ESTIMATOR_STATEMENTS:
            acc, text, _, _ = _weighted(statement)
            assert premises.estimator_statement(text), statement

    def test_a_plain_descriptive_paper_is_untouched(self):
        """`Mean (SD)` over a plain caption stays checkable: it is the honest
        column this whole family exists for."""
        text = "\n\n".join([N_Q, B_COMFORT, G_COMFORT,
                            "Pool comfort was summarised for the whole club."])
        assert premises.estimator_statement(text) is None

    def test_a_marginal_difference_is_not_a_marginal_mean(self):
        """The word means SIZE in ordinary English and an ESTIMATOR in a table
        caption, so it is admitted only where the context settles which. This
        pattern is matched against the WHOLE document, so a loose `marginal`
        would withdraw every mean in a paper that called a difference small."""
        assert premises.estimator_statement(
            "The differences in means were marginal.") is None
        assert premises.estimator_statement(
            "Table 2 reports estimated marginal means.")
        assert premises.estimator_statement(
            "The means reported above are the least-squares means.")


# --------------------------------------------------------------------------
# 6. A MODEL CANNOT WITHDRAW A PREMISE IT IS NEVER SHOWN
# --------------------------------------------------------------------------

#: An average stated without `mean`, `average`, `midpoint`, `halved` or a
#: cardinal beside any of them -- outside the widened vocabulary on purpose.
OUTSIDE_THE_VOCABULARY = ("The comfort index for each swimmer was formed from "
                          "her two cards by taking the central value of the pair.")


class TestTheWithdrawingQuestionIsAsked:
    def test_the_sentence_is_outside_every_averaging_vocabulary(self):
        assert not premises.AVERAGED.search(OUTSIDE_THE_VOCABULARY)

    def test_the_pre_filter_surfaces_it_as_a_withdrawal(self):
        _, text, variables, values = _index(OUTSIDE_THE_VOCABULARY)
        acc = account(variables=variables, values=values)
        cands = [c for c in PR.candidates(acc, text)
                 if c["premise"] == "averaging"]
        assert cands
        assert any("central value" in c["quote"] for c in cands)
        assert all(c["variable_id"] == "var:comfort" for c in cands)

    def test_a_model_true_withdraws_the_step_the_model_granted(self):
        _, text, variables, values = _index(OUTSIDE_THE_VOCABULARY)
        granted = cand("c1", "step", GRAN_TWO_OBSERVERS,
                       variable_id="var:comfort", source="account_quote")
        step_only = reading(verdict("c1", "step", True, "whole points"),
                            candidates=[granted])
        acc = account(variables=variables, values=values, reading=step_only)
        assert accusations(checks.evaluate(acc, text))
        both = reading(verdict("c1", "step", True, "whole points"),
                       verdict("c2", "averaging", True,
                               "the index is the central value of two cards"),
                       candidates=[granted,
                                   cand("c2", "averaging",
                                        OUTSIDE_THE_VOCABULARY,
                                        variable_id="var:comfort")])
        acc = account(variables=variables, values=values, reading=both)
        assert accusations(checks.evaluate(acc, text)) == []
        rec = verification(acc, text, "var:comfort", "granularity")
        assert rec["reports_an_average_in"] == "model_reading"

    def test_a_model_false_may_not_lift_a_veto_the_vocabulary_made(self):
        """The polarity that makes this question safe to ship: a refusal premise
        moves only on `true`."""
        inside = "Each swimmer's comfort index is the mean of the two cards."
        _, text, variables, values = _index(inside)
        granted = cand("c1", "step", GRAN_TWO_OBSERVERS,
                       variable_id="var:comfort", source="account_quote")
        no = reading(verdict("c1", "step", True, "whole points"),
                     verdict("c2", "averaging", False, "the model says no"),
                     candidates=[granted,
                                 cand("c2", "averaging", inside,
                                      variable_id="var:comfort")])
        acc = account(variables=variables, values=values, reading=no)
        assert accusations(checks.evaluate(acc, text)) == []

    def test_a_variable_the_vocabulary_already_vetoed_is_not_asked_about(self):
        """A refusal premise can only be ADDED, so a variable already refused
        cannot be moved by a verdict and is not worth a line of the prompt."""
        _, text, variables, values = _index(
            "Each swimmer's comfort index is the mean of the two cards.")
        acc = account(variables=variables, values=values)
        assert not [c for c in PR.candidates(acc, text)
                    if c["premise"] == "averaging"]


#: An estimator statement with no `mean ... are ... weighted` shape at all.
GOVERNING_OUTSIDE = ("Each swimmer's card was up-weighted by the reciprocal of "
                     "her selection probability before the reported values were "
                     "formed.")


class TestAGoverningSentenceReachesTheModel:
    def test_the_sentence_is_outside_the_vocabulary(self):
        _, text, _, _ = _weighted(GOVERNING_OUTSIDE)
        assert premises.estimator_statement(text) is None

    def test_the_fourth_place_is_now_in_the_models_net(self):
        """`premises.named_estimator` reads four places and this generator read
        three: a DOCUMENT-LEVEL statement produced zero candidates."""
        acc, text, _, _ = _weighted(GOVERNING_OUTSIDE)
        cands = [c for c in PR.candidates(acc, text)
                 if c["premise"] == "estimator"]
        assert cands
        assert any(c["source"] == "served_text" for c in cands)
        assert any("val:m" in (c.get("value_ids") or []) for c in cands)

    def test_a_model_true_on_it_refuses_the_mean(self):
        acc, text, variables, values = _weighted(GOVERNING_OUTSIDE)
        assert accusations(checks.evaluate(acc, text))
        cands = [c for c in PR.candidates(acc, text)
                 if c["premise"] == "estimator"]
        chosen = next(c for c in cands if c["source"] == "served_text"
                      and "val:m" in (c.get("value_ids") or []))
        read = reading(verdict(chosen["id"], "estimator", True,
                               "the reported values are selection-weighted"),
                       candidates=[chosen])
        acc = account(variables=variables, values=values, reading=read)
        assert accusations(checks.evaluate(acc, text)) == []


# --------------------------------------------------------------------------
# 7. THE SENTENCE SPLITTER BREAKS ON THE QUOTATION MARKS PUBLISHERS SET
# --------------------------------------------------------------------------


class TestTheSplitterBreaksOnACurlyClosingQuote:
    def test_a_period_before_a_curly_quote_ends_the_sentence(self):
        """MEASURED on ajcp.70049, where it cost two real `check_sd_or_se`
        calls: the bounds sentence ran on into the next one, the shared-scale
        lift saw two ranges where the paper states one, and BOTH variables lost
        a genuinely stated bound -- reciprocally, which is the tell."""
        text = ('The means were 4.06 and 4.01 on a 1-5 scale.” '
                'The number of EBPs reported ranged from 0 to 9.')
        hay = premises.Haystack(text)
        first = hay.sentence((4, 9))
        assert "EBPs" not in first
        assert len(premises.scale_claims(first)) == 1

    def test_the_ascii_closers_still_end_a_sentence(self):
        for closer in ('"', "'", ")", "]", "’", "»"):
            text = f"One card runs 0 to 6.{closer} A second runs 0 to 10."
            hay = premises.Haystack(text)
            assert "second" not in hay.sentence((4, 8)), closer
