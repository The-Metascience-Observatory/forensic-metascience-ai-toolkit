"""ROUND 19 -- TWO BLIND PROBES OF THE REFUSAL PREMISES' RECALL NETS.

WHAT THE SECOND PROBE FOUND, COMPRESSED INTO ONE SENTENCE BY ITS OWN AUTHOR:
a recall net for a refusal premise is bounded by a constant somewhere, and does
not say so when the constant binds. Three of the seven defects are that sentence
counted in three different units -- SENTENCES (`premises._ANAPHORA_REACH`),
CANDIDATES (`premise_reading.MAX_REFUSAL_CANDIDATES`, spent DOWN a rank order)
and CHARACTERS (`premise_reading.MAX_QUOTE_CHARS`). The other four are the
attribution layer failing in four new places.

EVERY CASE BELOW WAS REPRODUCED AGAINST THE UNCHANGED TREE FIRST, at
`a24add71`, and the measurement sits beside the test for it. Four carry a PAID
PROOF from the probes -- a real sonnet batch answering the question correctly
about a passage the code would not show it -- and those are the ones that say
plainly that the failure was RECALL and never JUDGEMENT.

WHAT IS DELIBERATELY NOT FIXED HERE, and is pinned as an open position rather
than papered over:

  * THE PROSE HALF OF THE AVERAGING VOCABULARY. Nine ordinary English ways of
    saying "the mean of the two cards" evade `premises.AVERAGED`, and that is
    the treadmill rounds 4, 7, 9, 10, 11, 13 and 14 each paid for once. The
    answer already exists and is not another word: `adjudication.candidates`
    consults no averaging vocabulary and offers all of them to a model, which
    is what `test_the_prose_half_is_the_models_question_not_a_longer_word_list`
    pins. Whether that path becomes the DEFAULT is a spend decision.
  * `, and` AS A CLAUSE BREAK. Measured and rejected before this round with a
    stated reason -- it splits this repo's own canonical known-answer fixture --
    and re-opening it is not a bug fix.
  * WIDENING THE FREE PATH'S ANTECEDENT REACH ACROSS A HEADING. Round 12 pins
    the opposite answer for a path with no judge downstream of it, so the two
    consumers now differ deliberately. See
    `TestTheAnaphoraReachCountsEvidenceForStageOneOnly`.

THE FIXTURE PAPER IS A REGIONAL SEED-LIBRARY GERMINATION AUDIT and shares no
sentence, scale, noun or number with any earlier round.
"""

from __future__ import annotations

import statistics as st

from metascience_agent.scaffold import adjudication, checks, premises
from metascience_agent.scaffold import premise_reading as PR

BAD = {"suspicious", "highly_suspicious", "impossible"}

# --------------------------------------------------------------------------
# The Wenlow seed-library germination audit
# --------------------------------------------------------------------------

#: Seed vigour, graded 0-16 in WHOLE points by each of TWO inspectors; a plot's
#: figure is the mean of the two cards, so it moves in HALF points. Honest by
#: construction, and unreachable from any integer total -- which is what makes
#: leaving the averaging premise standing a conviction of a paper that did
#: nothing wrong.
VIGOUR = [8.5, 11.0, 6.5, 13.0, 9.5, 4.0, 12.5, 7.0, 10.5, 5.5,
          14.0, 8.0, 11.5, 6.0, 9.0, 12.0, 7.5, 10.0, 3.5, 13.5,
          8.5, 5.0, 11.0, 9.5, 6.5, 12.5, 7.0, 10.5, 4.5, 14.5,
          8.0, 11.5, 9.0, 6.0, 12.0, 7.5, 10.0]
N = len(VIGOUR)
V_MEAN = f"{st.fmean(VIGOUR):.2f}"
V_SD = f"{st.stdev(VIGOUR):.2f}"
assert N == 37
assert not any(round(k / N, 2) == float(V_MEAN) for k in range(N * 16 + 1)), V_MEAN
assert any(round(t / (2 * N), 2) == float(V_MEAN) for t in range(N * 32 + 1))

#: The honest WHOLE-number companion: packets dispatched per plot, an ordinary
#: integer count. It is the control for every licence this file narrows.
PACKETS = [12, 19, 7, 23, 15, 31, 9, 18, 26, 11, 14, 22, 8, 17, 29,
           13, 20, 10, 25, 16, 21, 6, 28, 12, 19, 24, 9, 15, 30, 11,
           18, 13, 27, 22, 8, 16, 23]
assert len(PACKETS) == N
P_MEAN = f"{st.fmean(PACKETS):.2f}"
P_SD = f"{st.stdev(PACKETS):.2f}"

N_Q = "Thirty-seven plots took part in the Wenlow seed-library audit (n = 37)."
#: ROUND 26 REMOVED `by each of two inspectors` FROM THIS SENTENCE. It was
#: incidental to round 19 -- which is about a RIVAL quantity's discreteness
#: being read as this variable's -- and it is not incidental to the licence: a
#: paper that says the grading happened twice per plot has stated the step for a
#: GRADING and not for the plot's own figure, so the sentence no longer licenses
#: at all and every case in this file would have been decided by the wrong rule.
GRAN_V = ("Seed vigour was graded in whole points on a card running from 0 to "
          "16 by the visiting inspector.")
GRAN_P = ("Packets dispatched were counted as whole packets, from 0 to 400 per "
          "plot.")


def var(vid, name, quote, lower, upper, *, kind="ordinal", derivation=None,
        bsource="stated"):
    return {"id": vid, "name": name, "label": name, "printed_as": [],
            "kind": kind, "role": None, "units": None,
            "units_source": "not_stated", "derivation": derivation,
            "derived_from": [],
            "bounds": {"source": bsource, "lower": lower, "upper": upper,
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
            "coordinate": {"study_id": "study:wenlow", "group_id": "grp:plots",
                           "phase_id": None}}


def account(*, variables=None, values=None, footnotes=(), vigour_derivation=None):
    if variables is None:
        variables = [var("var:vigour", "Seed vigour", GRAN_V, 0, 16,
                         derivation=vigour_derivation),
                     var("var:packets", "Packets dispatched", GRAN_P, 0, 400,
                         kind="count")]
    if values is None:
        values = [cell("val:vm", "mean", V_MEAN, "var:vigour", 1, "Mean (SD)"),
                  cell("val:vs", "sd", V_SD, "var:vigour", 2, "Mean (SD)"),
                  cell("val:vn", "n", str(N), "var:vigour", 3, "n"),
                  cell("val:pm", "mean", P_MEAN, "var:packets", 1, "Mean (SD)"),
                  cell("val:ps", "sd", P_SD, "var:packets", 2, "Mean (SD)"),
                  cell("val:pn", "n", str(N), "var:packets", 3, "n")]
    return {"paper": {"doi": "10.0000/wenlow",
                      "title": "Germination quality in a regional seed library"},
            "studies": [{"id": "study:wenlow", "design": "prospective_cohort",
                         "groups": [{"id": "grp:plots", "label": "All plots",
                                     "n": N, "n_source": "text"}]}],
            "variables": variables, "values": values,
            "document": {"tables": [
                {"id": "table:1",
                 "caption": "Table 1. Plot-level germination measures.",
                 "footnotes": list(footnotes)}]}}


def paper(*sentences, head="## Methods"):
    return "\n\n".join((head, N_Q, GRAN_V, GRAN_P) + sentences) + "\n"


def accusations(acc, text):
    return sorted({(r["check_id"], r["severity"])
                   for r in checks.evaluate(acc, text)["checks"]
                   if r["severity"] in BAD})


def verification(acc, text, vid="var:vigour"):
    hay = premises.Haystack(text)
    variables = premises.readable_variables(acc)
    v = [x for x in variables if x["id"] == vid][0]
    mine = [x for x in acc["values"] if x.get("variable_id") == vid]
    return premises.granularity_verification(
        v, hay, variables, mine, passages=premises.table_passages(acc, mine))


def offered(acc, text, needle, vid="var:vigour"):
    """Did stage 1 put `needle` in front of a model at all?"""
    return [c for c in adjudication.candidates(acc, text)
            if c["variable_id"] == vid and needle in c["quote"]]


def families(acc, text):
    return sorted((r["family"], r["variable_id"], r["severity"])
                  for r in checks.evaluate(acc, text)["checks"])


def test_the_fixture_is_not_toothless():
    """THE ASSERTION EVERY `accusations(...) == []` IN THIS FILE RESTS ON, and
    it is here because the first draft of this fixture did not satisfy it: the
    bounds premise refused `bound_quote_does_not_assert_a_scale` on `0 to 16
    inspection card`, so GRIM never reached the half-point variable at all and
    every refusal test in the file was passing on a check that never ran.

    [[a-fixture-that-excludes-the-defect-region]]. With the premises standing
    this paper IS convicted, so a test that shows no accusation has shown
    something."""
    acc = account()
    assert ("grim", "var:vigour", "impossible") in families(acc, paper())
    # AND THE HONEST COMPANION IS CHECKED AND PASSES, so a fix that buys safety
    # by refusing everything fails here.
    assert ("grim", "var:packets", "consistent") in families(acc, paper())


# --------------------------------------------------------------------------
# D1 -- THE DERIVATION FIELD HOLDS A FORMULA AND WAS READ BY A WORD LIST
# --------------------------------------------------------------------------

FORMULA = "Seed vigour = (inspector A card + inspector B card) / 2"


class TestADerivationMayBeWrittenAsArithmetic:
    """`schema.py` asks `variable.derivation` for "the formula in the paper's
    words", and `premises.DERIVED_AVERAGE` matched only the WORDS mean /
    average / midpoint / halved / divided by two. MEASURED at `a24add71`: an
    account that records the formula exactly as the schema asks returned GRIM
    `impossible` on this honest half-point paper.

    IT IS THE ONE EVASION OF ITS ROUND WITH NO RESCUE ON ANY PATH, which is why
    it is fixed here while the nine PROSE phrasings beside it are not: stage 1
    reads the served text and the table furniture, and NO reader anywhere
    offers a model the derivation field."""

    def test_a_sum_over_its_own_term_count_withdraws_the_step(self):
        acc = account(vigour_derivation=FORMULA)
        assert accusations(acc, paper()) == []
        rec = verification(acc, paper())
        assert rec["derivation_reports_an_average"] == FORMULA
        assert rec["establishes_step_of_one"] is False

    def test_it_counts_the_terms_rather_than_matching_a_word(self):
        assert premises.formula_reports_an_average("(a + b) / 2")
        assert premises.formula_reports_an_average("(a + b + c) / 3")
        # NOT an average: the divisor is not the number of terms, so the
        # arithmetic says nothing about the step and the check is owed.
        assert premises.formula_reports_an_average("(a + b) / 4") is None
        assert premises.formula_reports_an_average("(a + b + c) / 2") is None
        assert premises.formula_reports_an_average("total / 2") is None

    def test_a_divisor_that_is_not_the_term_count_keeps_the_check(self):
        acc = account(vigour_derivation="(card A + card B) / 4")
        assert verification(acc, paper())["derivation_reports_an_average"] is None

    def test_all_three_readers_of_the_field_agree(self):
        """ONE DEFINITION, AND THERE WERE THREE. The same expression was spelled
        by hand in `granularity_verification`, in
        `premise_reading._averaging_candidates` and in
        `adjudication.already_refused`, so a fourth way of reading the field
        would have reached one of them and not the others."""
        acc = account(vigour_derivation=FORMULA)
        text = paper()
        hay = premises.Haystack(text)
        variables = premises.readable_variables(acc)
        v = variables[0]
        assert premises.derivation_reports_an_average(v)
        assert adjudication.already_refused(v, hay, variables)
        assert [c for c in PR.candidates(acc, text)
                if c["premise"] == "averaging"
                and c["variable_id"] == "var:vigour"] == []


PROSE_EVASIONS = (
    "Each plot's seed vigour lies halfway between the two inspectors' cards.",
    "Where the two inspectors disagreed the vigour splits the difference "
    "between their cards.",
    "Each plot's seed vigour equals half the sum of the two cards.",
    "The two cards were reconciled by taking their midpoint.",
    "Averaging the two inspectors' cards gave each plot's seed vigour.",
    "The mean card was reported as the seed vigour.",
    "Seed vigour is the two inspectors' cards averaged.",
    "Each plot's seed vigour is the two cards' arithmetic centre.",
    "Seed vigour was computed as the per-plot average card.",
)


def test_the_prose_half_is_the_models_question_not_a_longer_word_list():
    """THE POSITION, PINNED SO IT IS ARGUED WITH RATHER THAN QUIETLY UNDONE.
    Nine ordinary English ways of saying "the mean of the two cards" evade
    `premises.AVERAGED`, and adding any of them buys exactly one round. The
    answer this repo already built is that stage 1 consults NO averaging
    vocabulary, so every one of them reaches a model -- 9 of 9 here, and 10 of
    10 on the probe's own fixture."""
    for sentence in PROSE_EVASIONS:
        assert offered(account(), paper(sentence), sentence[:40]), sentence


# --------------------------------------------------------------------------
# D2 -- AN ANAPHOR LIVES IN A CLAUSE, NOT IN A SENTENCE
# --------------------------------------------------------------------------

ANAPHOR_ONE_SENTENCE = ("Packets dispatched per plot were logged in the day "
                        "book alongside the two cards, which were averaged.")


class TestAnAnaphoricAveragingClauseInASentenceAboutSomethingElse:
    """MEASURED at `a24add71`: GRIM `impossible` on the free path AND ZERO
    stage-1 windows, so `--read-premises` could not rescue it either. Both nets
    routed through `_names_a_declared_variable` asked of the whole SENTENCE, so
    ONE RULE FAILED TWICE -- which is the exact property the adjudication
    module's docstring claims it does not have ("the two stages have different
    failure directions").

    PAID PROOF FROM THE PROBE ($0.054618): handed this sentence, the model
    answers that the veto is owed. The failure was recall in both nets."""

    def test_the_free_path_now_withdraws_the_step(self):
        acc, text = account(), paper(ANAPHOR_ONE_SENTENCE)
        assert accusations(acc, text) == []
        assert verification(acc, text)["quote_reports_an_average"]

    def test_stage_ones_recall_net_reaches_it_too(self):
        """BOTH NETS, WHICH IS THE POINT -- the probe's finding is that one rule
        failed twice. Asked of `relevant_passages` rather than of
        `candidates`, because `already_refused` now short-circuits the whole
        variable: the free path has withdrawn the step, so there is nothing
        left to buy a paid line for."""
        text = paper(ANAPHOR_ONE_SENTENCE)
        hay = premises.Haystack(text)
        variables = premises.readable_variables(account())
        v = [x for x in variables if x["id"] == "var:vigour"][0]
        assert adjudication.already_refused(v, hay, variables)
        got = adjudication.relevant_passages(v, hay, variables)
        assert any("which were averaged" in q for _, q, _ in got)

    def test_the_clause_is_the_unit(self):
        declared = premises.readable_variables(account())
        assert premises.is_anaphoric_averaging(ANAPHOR_ONE_SENTENCE, declared)

    def test_an_averaging_clause_that_names_another_variable_is_left_alone(self):
        """THE CONTROL, and it is what stops this becoming a blanket refusal:
        where the averaging clause NAMES the variable it belongs to, nothing
        anaphoric is happening and this variable's step is untouched."""
        other = "Packets dispatched is the mean of the two depots' tallies."
        declared = premises.readable_variables(account())
        assert not premises.is_anaphoric_averaging(other, declared)
        assert verification(account(), paper(other))["quote_reports_an_average"] is None


# --------------------------------------------------------------------------
# D3 -- A DISCRETENESS WORD BELONGING TO AN UNDECLARED QUANTITY
# --------------------------------------------------------------------------

LEAKS = {
    "number of, after a comma-and":
        "Seed vigour was graded on a card running from 0 to 16, and the number "
        "of mainspring failures at each visit was recorded.",
    "a bare while":
        "Seed vigour was graded on a card running from 0 to 16 while damaged "
        "packets were tallied in whole units.",
    "a parenthetical with its own subject":
        "Seed vigour was graded on a card running from 0 to 16 (damaged packets "
        "were counted in whole units).",
}

#: THE SAME SENTENCE WITH A SEMICOLON, which `_CLAUSE_BREAK` has always carried.
#: It refused at `a24add71` and refuses now, which is what says the boundary
#: list -- and not the reading -- was the whole difference.
SEMICOLON_CONTROL = ("Seed vigour was graded on a card running from 0 to 16; "
                     "damaged packets were counted in whole units.")


def one_variable_account(sentence):
    """The vigour paper alone, with `sentence` as its granularity quote."""
    v = var("var:vigour", "Seed vigour", sentence, 0, 16)
    return account(variables=[v],
                   values=[cell("val:vm", "mean", V_MEAN, "var:vigour", 1,
                                "Mean (SD)"),
                           cell("val:vs", "sd", V_SD, "var:vigour", 2,
                                "Mean (SD)"),
                           cell("val:vn", "n", str(N), "var:vigour", 3, "n")])


class TestALicenceIsNotSuppliedByAnotherQuantitysDiscreteness:
    """THE OPPOSITE POLARITY FROM EVERY OTHER DEFECT IN THESE TWO PROBES. D1 and
    D2 are REFUSALS that failed to fire, where being wrong costs a check; this
    is a LICENCE that fired, manufacturing a step of 1 the paper never granted
    out of a whole-unit statement about a DIFFERENT, UNDECLARED quantity. All
    three returned GRIM `impossible` at `a24add71` on this honest half-point
    card, and the same sentence with a SEMICOLON refused -- which is the tell
    that the boundary list, and not the reading, was the whole difference.

    PAID PROOF FROM THE PROBE ($0.054618): sonnet answers `false` on all three
    ("Whole units modifies damaged packets, not seed vigour") and `true` on the
    true-licence control, so `--read-premises` already rescued these and an
    ordinary run did not."""

    def test_each_leak_no_longer_licenses_a_step(self):
        for label, sentence in LEAKS.items():
            acc = one_variable_account(sentence)
            text = "\n\n".join(("## Methods", sentence)) + "\n"
            assert accusations(acc, text) == [], label
            assert verification(acc, text)["establishes_step_of_one"] is False, label

    def test_the_semicolon_control_is_unchanged(self):
        acc = one_variable_account(SEMICOLON_CONTROL)
        text = "\n\n".join(("## Methods", SEMICOLON_CONTROL)) + "\n"
        assert accusations(acc, text) == []

    def test_the_number_of_phrase_must_count_this_variable(self):
        """`number of` is the ONE member of the discreteness vocabulary that
        NAMES a quantity instead of describing how one was recorded, so it is
        the one that can be asked what it counts."""
        v = var("var:packets", "Packets dispatched", GRAN_P, 0, 400, kind="count")
        assert premises.discreteness_about(
            "The number of packets dispatched was recorded for each plot.", v)
        assert not premises.discreteness_about(
            "The number of mainspring failures at each visit was recorded.", v)

    def test_an_ordinary_predicate_is_untouched(self):
        """Every OTHER member stays exactly as it was: this narrows one phrase,
        not the vocabulary."""
        v = var("var:packets", "Packets dispatched", GRAN_P, 0, 400, kind="count")
        for honest in ("Packets were counted in whole units.",
                       "Packets dispatched were tallied at each visit.",
                       "Responses were given on a 7-point scale."):
            assert premises.discreteness_about(honest, v), honest

    def test_a_parenthetical_with_no_subject_of_its_own_stays_in_its_clause(self):
        """THE COST CONTROL FOR THE PARENTHESIS RULE. `(values were recorded in
        whole units)` has a finite verb and NO subject of its own -- every word
        before the verb is generic -- so it modifies the host clause, and an
        honest paper that writes its granularity that way keeps its step."""
        assert not premises._is_own_assertion("values were recorded in whole units")
        assert not premises._is_own_assertion("0 to 16")
        assert premises._is_own_assertion("damaged packets were counted in whole units")

    def test_the_honest_whole_number_variable_keeps_its_stated_step(self):
        """AND THE WHOLE POINT: a paper that really does say its own variable
        moves in whole units still says so."""
        sentence = "Packets dispatched were counted in whole packets at every visit."
        acc = account()
        acc["variables"][1]["granularity"] = {"per_subject_step": 1,
                                              "quote": sentence}
        rec = verification(acc, paper(sentence), vid="var:packets")
        assert rec["discreteness_source"] == premises.STATED_DISCRETENESS

    def test_the_canonical_comma_and_fixture_is_not_re_opened(self):
        """`, and` IS STILL NOT A CLAUSE BREAK, and that decision is older than
        this round. Splitting there costs this repo's own known-answer shape --
        `<variable> was rated on a scale, and each participant gave one
        whole-number rating on that scale` -- whose discreteness clause then
        names no variable at all."""
        sentence = ("Packets dispatched were recorded on a 0 to 400 sheet, and "
                    "each grower gave one whole-number tally on that sheet.")
        assert len(premises._clauses(sentence)) == 1


# --------------------------------------------------------------------------
# THE THREE BUDGETS -- SENTENCES, CANDIDATES, CHARACTERS
# --------------------------------------------------------------------------

WITHDRAW_ROLE = ("The primary outcome was taken as what the two inspectors' "
                 "cards come to on balance.")
FILLER = ("Visits ran from April until the end of September.",
          "Stewards collected the cards at the close of each visit.",
          "Entries were checked against the published register.",
          "One plot withdrew before the second visit and was excluded.",
          "All analyses were carried out in R 4.3.1.",
          "No data were imputed.",
          "Two stewards supervised the store throughout.",
          "The register was printed a fortnight in advance.")


def two_section_paper(n_filler):
    methods = " ".join([N_Q, GRAN_V] + list(FILLER[:n_filler]))
    return (f"## Methods\n\n{methods}\n\n"
            f"## Statistical analysis\n\n{WITHDRAW_ROLE}\n")


class TestTheAnaphoraReachCountsEvidenceForStageOneOnly:
    """MEASURED at `a24add71`, with a PAID PROOF ($0.068350): at five filler
    sentences stage 1 offers the withdrawing window, the model answers
    `establishes: true`, and the accusation is removed; at SIX the same sentence
    in the same paper reaches no model and `impossible` stands. The section
    floor is no help, because the antecedent is in the PREVIOUS section -- so
    the reach collapses to the bare six-sentence count, and a reach ordered by
    POSITION is a filter for a refusal by exactly the argument
    `MAX_REFUSAL_CANDIDATES` already makes about a cap.

    AND THE FREE PATH IS DELIBERATELY NOT CHANGED. Round 12 pins the opposite
    answer there with a stated reason, and that path has no judge downstream.
    Widening it would overturn a decision, which is not this round's to make."""

    def test_stage_one_reaches_the_antecedent_at_every_distance(self):
        for n in range(0, len(FILLER) + 1):
            assert offered(account(), two_section_paper(n), "come to on balance"), n

    def test_the_free_paths_reach_is_unchanged(self):
        """The asymmetry asserted directly rather than inferred from round 12
        staying green: same offset, same declared variables, two answers, and
        the DEFAULT is still the narrow one."""
        text = two_section_paper(len(FILLER))
        hay = premises.Haystack(text)
        declared = premises.readable_variables(account())
        off = text.index(WITHDRAW_ROLE)
        assert premises._antecedent_ids(hay, off, declared) == set()
        assert premises._antecedent_ids(hay, off, declared, count_naming=True) \
            == {"var:vigour"}


DECOY = "The mean seed vigour in block {i} was {v} points."
EVASIVE = ("Each plot's seed vigour is the central value of the two inspectors' "
           "cards.")


class TestTheCapIsNotSpentDownTheVocabularyThatIsBlind:
    """`adjudication._rank` scores a passage 0 if the STRICT averaging
    vocabulary sees it, 1 if the LOOSE one does and 2 otherwise -- so the
    sentences this module exists to rescue are rank 2 BY CONSTRUCTION, sort
    last, and are the first thing the cap removes. MEASURED at `a24add71`: with
    36 vocabulary-matching decoys the withdrawal survives; with 38 the candidate
    set is 40 decoys and it reaches no model. PAID PROOF from the probe
    ($0.200960): that 40-row set was asked in one real call, returned zero
    `true` verdicts, and the accusation stood on both sides of it."""

    def _text(self, n):
        decoys = tuple(DECOY.format(i=i, v=10 + (i % 7)) for i in range(1, n + 1))
        gap = ("Entries were checked against the published register.",
               "One plot withdrew before the second visit and was excluded.")
        return paper(*(decoys + gap + (EVASIVE,)))

    def test_a_crowd_of_vocabulary_matches_cannot_cut_the_evasive_one(self):
        for n in (0, 20, 38, 50, 80):
            assert offered(account(), self._text(n), "central value"), n

    def test_the_cap_still_binds(self):
        cands = [c for c in adjudication.candidates(account(), self._text(80))
                 if c["variable_id"] == "var:vigour"]
        assert 0 < len(cands) <= PR.MAX_REFUSAL_CANDIDATES

    def test_a_set_inside_the_cap_is_ordered_exactly_as_before(self):
        """RANKING STILL ORDERS THE PROMPT. `_stratified` changes WHO IS CUT and
        nothing else, so a paper whose whole candidate set fits comes out in the
        order the previous code produced."""
        rows = [(0, "a"), (1, "b"), (2, "c"), (1, "d")]
        assert adjudication._stratified(rows, 10) == rows

    def test_every_stratum_loses_its_weakest_before_one_loses_all(self):
        rows = [(1, f"decoy{i}") for i in range(30)] + [(2, "withdrawal")]
        assert (2, "withdrawal") in adjudication._stratified(rows, 10)

    def test_the_binding_is_recorded_on_the_row(self):
        cands = [c for c in adjudication.candidates(account(), self._text(80))
                 if c["variable_id"] == "var:vigour"]
        assert cands and cands[0]["passages_cut"] > 0
        assert cands[0]["passages_considered"] > PR.MAX_REFUSAL_CANDIDATES


FOLD = ("Vigour | Packets | Block | Steward | Register | Entry | Plot | Parish "
        "| Placing | Points ")


class TestAnOverLongPassageIsCutIntoPiecesRatherThanTruncated:
    """CLAUDE.md 8l records that ordinary converter output folds a block onto one
    line with no terminal punctuation, so `Haystack.sentence` returns the whole
    block as ONE sentence and `_clip` kept a 700-character prefix. MEASURED at
    `a24add71`, with a PAID PROOF ($0.045754 + $0.047762): a withdrawing
    statement 300 characters in was served, judged `true`, and the accusation
    removed; the same statement 900 characters in was cut out of a candidate
    that was STILL EMITTED, still `askable`, still batched and still paid for,
    three `false` verdicts came back about text that no longer contained it, and
    nothing recorded that anything had been cut.

    `askable = True` EXISTS SO A REFUSAL CANDIDATE IS NEVER DROPPED, and its
    contents were being dropped instead. That is
    [[absence-must-be-representable]] at an artifact boundary."""

    def _text(self, pad):
        folded = (FOLD * ((pad // len(FOLD)) + 1))[:pad] if pad else ""
        return f"## Methods\n\n{N_Q}\n\n{GRAN_V}\n\n{folded}{EVASIVE}\n"

    def test_the_statement_is_served_however_deep_it_sits(self):
        for pad in (0, 300, 600, 700, 900, 1400, 2600):
            assert offered(account(), self._text(pad), "central value"), pad

    def test_the_pieces_overlap_so_a_statement_cannot_straddle_a_cut(self):
        """A BUTT-JOINTED SEGMENTATION TRADES TRUNCATION FOR STRADDLING, and
        measured, that fixes nothing: the first attempt at this cut the
        statement in half at 600 characters and it reached a model in neither
        piece."""
        s = " ".join(f"w{i:04d}" for i in range(400))
        pieces, dropped = PR._segments(s)
        assert dropped == 0 and len(pieces) > 1
        for i in range(0, len(s) - 200, 53):
            assert any(s[i:i + 200] in p for p in pieces)

    def test_each_piece_says_which_it_is(self):
        cands = [c for c in adjudication.candidates(account(), self._text(2600))
                 if c["variable_id"] == "var:vigour"]
        segmented = [c for c in cands if c["quote_segment"]]
        assert segmented
        for c in segmented:
            i, k = c["quote_segment"]
            assert 1 <= i <= k and k > 1
            assert len(c["quote"]) <= PR.MAX_QUOTE_CHARS

    def test_what_does_not_fit_is_reported_rather_than_taken_away(self):
        pieces, dropped = PR._segments("x" * 60000)
        assert len(pieces) == PR.MAX_QUOTE_SEGMENTS
        assert dropped > 0

    def test_a_short_passage_is_one_row_exactly_as_before(self):
        cands = [c for c in adjudication.candidates(account(), self._text(0))
                 if c["variable_id"] == "var:vigour"]
        assert cands and all(c["quote_segment"] is None for c in cands)
        assert all(c["quote_chars_not_carried"] == 0 for c in cands)


# --------------------------------------------------------------------------
# THE NAME FLOOR, AND THE LICENCE THAT NEEDS NO NAME
# --------------------------------------------------------------------------

ABBREVIATED = ("The {n} figure printed in Table 1 is the mean of the three "
               "inspectors' tallies.")


def abbreviated_account(name, *, mean=None, sd=None):
    grant = f"{name} was recorded as a whole tally by each of three inspectors."
    v = var("var:x", name, grant, None, None, kind="count", bsource="not_stated")
    return account(
        variables=[v],
        values=[cell("val:m", "mean", mean or V_MEAN, "var:x", 1, "Mean (SD)"),
                cell("val:s", "sd", sd or V_SD, "var:x", 2, "Mean (SD)"),
                cell("val:n", "n", str(N), "var:x", 3, "n")])


def abbreviated_paper(name):
    grant = f"{name} was recorded as a whole tally by each of three inspectors."
    return "\n\n".join(("## Methods", N_Q, grant,
                        ABBREVIATED.format(n=name))) + "\n"


class TestAVariableNamedByAnAbbreviationCanBeAttributedSomething:
    """`anchor_score` required a matched word of FOUR characters and `_content`
    dropped anything under three, so `ADL`, `PSS`, `IQ`, `BMI` and `ADLs` scored
    0.0 against EVERY sentence of their own paper. MEASURED at `a24add71` with a
    PAID PROOF ($0.039101 + $0.035540): identical paper, identical sentence,
    `kind=count`. Named `Falls per week` the sentence is offered, the model says
    `true`, the accusation is removed; named `ADL` stage 1 offers ONE candidate
    -- the table caption `Table 1.` -- and `impossible` stands.

    A LENGTH FLOOR APPLIED TO THE ONE CLASS OF NAME THAT IS SHORT BECAUSE IT IS
    A NAME. It is relaxed for CAPITALS only, so an ordinary short word does not
    start anchoring."""

    def test_an_abbreviation_anchors(self):
        for name in ("ADL", "PSS", "IQ", "BMI", "ADLs"):
            assert accusations(abbreviated_account(name),
                               abbreviated_paper(name)) == [], name

    def test_an_ordinary_short_word_still_does_not(self):
        """THE FLOOR IS NOT WIDENED IN GENERAL, which is what keeps it a
        coincidence guard: a three-letter ordinary word in a sentence is a
        coincidence far more often than it is a reference."""
        for name in ("Age", "Sex", "Day"):
            v = {"id": "v", "name": name, "label": name, "printed_as": []}
            words = premises._sentence_words(
                f"The {name.lower()} of each grower was noted at entry.")
            assert premises.anchor_score(v, words) == 0.0, name

    def test_a_name_of_generic_words_alone_is_named_as_such(self):
        assert premises.name_is_anchorable(
            {"id": "v", "name": "Seed vigour", "label": "", "printed_as": []})
        assert not premises.name_is_anchorable(
            {"id": "v", "name": "Total count", "label": "", "printed_as": []})


class TestAKindLicenceRestsOnAVetoThatCanFire:
    """THE PAIRING IS THE FINDING, and it is not the matcher failing once more.
    `granularity_verification`'s KIND licence grants a `count` its step of 1
    from the SCHEMA -- no quote, no attribution -- and is vetoed only by
    `averaged`, every route to which resolves its subject through
    `anchor_score`. So for a variable no sentence can ever be attributed to, the
    licence is granted by a route that needs no name while its only refusal is
    withheld by a route that needs one.

    THE FIX IS THE MODE A TABLE FOOTNOTE ALREADY GETS. `_averaging_here`'s
    `unattributed="refuse"` exists because a caption governs its own table and
    has NO SENTENCE TO BE ABOUT; an unnameable variable is in exactly that
    position, and gets the same mode for the same stated reason."""

    def test_an_unnameable_count_no_longer_convicts(self):
        acc, text = abbreviated_account("Total count"), abbreviated_paper("Total count")
        assert accusations(acc, text) == []
        assert verification(acc, text, vid="var:x")["quote_reports_an_average"]

    def test_a_nameable_count_is_untouched(self):
        """The control: a variable with an ordinary name keeps the DEFERRAL, so
        an averaging statement plainly about something else does not withdraw
        its step."""
        acc = abbreviated_account("Falls per week")
        text = paper("Seed vigour is the mean of the two inspectors' cards.")
        assert verification(acc, text, vid="var:x")["quote_reports_an_average"] is None

    def test_a_silent_paper_keeps_the_kind_licence(self):
        """AND THE COVERAGE COST IS BOUNDED BY THE PAPER'S OWN WORDS: an
        unnameable count in a paper that says nothing about averaging anywhere
        still gets its step from its kind. Only a statement the veto cannot be
        shown NOT to be about takes it away."""
        acc = abbreviated_account("Total count", mean=P_MEAN, sd=P_SD)
        rec = verification(acc, paper(), vid="var:x")
        assert rec["kind_makes_it_necessary"] is True
        assert rec["discreteness_source"] == premises.NECESSARY_DISCRETENESS


# --------------------------------------------------------------------------
# THE LIMIT OF THE RELAXATION -- A RIVAL THAT NEWLY ANCHORS MAY NOT TAKE A
# REFUSAL AWAY FROM ANOTHER VARIABLE
# --------------------------------------------------------------------------

#: The abbreviation is now a declared variable of the SAME paper rather than
#: the variable under test, which is the only thing that changes from
#: `TestAVariableNamedByAnAbbreviationCanBeAttributedSomething` above.
RIVAL = "BMI"

#: Every one an HONEST paper: seed vigour is the mean of two whole-point cards,
#: so it moves in half points and no integer total reaches its mean. The paper
#: says so in its own words, in four ordinary shapes, each with the
#: abbreviation somewhere in the sentence.
STEALS = {
    "the rival is named beside this variable":
        "The vigour and BMI figures were averaged across the two inspectors' "
        "cards.",
    "the averaging clause is anaphoric, the rival is in the sentence":
        "Vigour was graded by two inspectors alongside BMI and the two cards "
        "were averaged.",
    "the rival sits INSIDE the averaging clause":
        "Each plot was visited twice; the two cards were averaged and filed "
        "beside BMI.",
}

CO_NAMED = "Vigour and BMI were both entered on the same sheet."
ANAPHOR = "The two cards were averaged for each plot."


def rival_account(name=RIVAL):
    """The vigour paper beside a variable the paper names by an abbreviation.

    Only vigour carries values, so the check under test is vigour's and the
    rival's whole contribution is its NAME."""
    return account(
        variables=[var("var:vigour", "Seed vigour", GRAN_V, 0, 16),
                   var("var:rival", name,
                       f"{name} was recorded to the nearest whole unit at "
                       "entry.", None, None, kind="continuous",
                       bsource="not_stated")],
        values=[cell("val:vm", "mean", V_MEAN, "var:vigour", 1, "Mean (SD)"),
                cell("val:vs", "sd", V_SD, "var:vigour", 2, "Mean (SD)"),
                cell("val:vn", "n", str(N), "var:vigour", 3, "n")])


def rival_antecedent_paper(name=RIVAL):
    """The anaphor under `## Statistical analysis`, its only in-reach antecedent
    a sentence naming this variable IN PART and the abbreviation IN FULL."""
    stat = " ".join(list(FILLER) + [CO_NAMED.replace(RIVAL, name),
                                    ANAPHOR])
    return (f"## Methods\n\n{N_Q} {GRAN_V}\n\n"
            f"## Statistical analysis\n\n{stat}\n")


class TestAnAbbreviationMayNotTakeAnotherVariablesRefusalAway:
    """THE REGRESSION `108e9ec6` ITSELF INTRODUCED, and it is the shape this
    repo has been caught by twice: a commit whose stated purpose is safety,
    widening a recall net, opening an accusation channel on the way past.

    `_acronym_words` is right that a length floor applied to `ADL`, `PSS`, `IQ`
    and `BMI` is a floor applied to the one class of name that is short BECAUSE
    it is a name -- and the class above measures what it bought. But the same
    score is read in two directions. Read of a variable's OWN name it decides
    what a sentence is about; read of a RIVAL'S name it decides what a sentence
    is NOT about, and there it takes an averaging statement away from the
    variable the paper was talking about and leaves a step of 1 standing.

    AN ABBREVIATION IS THE STRONGEST POSSIBLE RIVAL BY CONSTRUCTION: one content
    word, so 1.0 whenever it appears at all, against the 0.5 a two-word name
    scores when a paper prints `vigour` for `Seed vigour` -- which is what
    papers do.

    MEASURED AT `108e9ec6`, ON THE DEFAULT PATH WITH NO FLAG, and clean at its
    parent `a24add71`: all four shapes below returned GRIM `impossible` on this
    honest half-point paper. THREE SEPARATE COMPARISONS carry it, which is why
    fixing the first alone still left two live:

      1. `_attribution` -- the rival outscores this variable, so the averaging
         clause is read as the rival's (`anchor_score_agreed`);
      2. `is_anaphoric_averaging` -- the rival sits in the averaging clause, so
         the clause names a declared variable, stops being anaphoric and never
         reaches the antecedent walk;
      3. `_antecedent_ids` -- only the BEST-named variable of each sentence is
         kept, so the rival wins the one in-reach sentence outright
         (`_best_named`).
    """

    def test_the_fixture_is_not_toothless(self):
        """With no withdrawal in the paper at all this account IS convicted, so
        every empty list below has shown something."""
        assert ("grim", "var:vigour", "impossible") in families(
            rival_account(), paper())

    def test_none_of_the_three_sentence_shapes_convicts(self):
        for label, sentence in STEALS.items():
            acc, text = rival_account(), paper(sentence)
            assert accusations(acc, text) == [], label
            assert verification(acc, text)["quote_reports_an_average"], label

    def test_nor_does_the_antecedent_shape(self):
        acc, text = rival_account(), rival_antecedent_paper()
        assert accusations(acc, text) == []

    def test_the_antecedent_walk_keeps_this_variable(self):
        """The mechanism, asserted directly: the rival joins the antecedent set
        and does not replace what was already in it."""
        text = rival_antecedent_paper()
        hay = premises.Haystack(text)
        declared = premises.readable_variables(rival_account())
        got = premises._antecedent_ids(hay, text.index(ANAPHOR), declared)
        assert "var:vigour" in got

    def test_the_clause_is_still_anaphoric_with_the_rival_in_it(self):
        declared = premises.readable_variables(rival_account())
        assert premises.is_anaphoric_averaging(
            STEALS["the rival sits INSIDE the averaging clause"], declared)

    # ---- and the three controls that stop this buying its quiet ------------

    def test_the_abbreviation_still_anchors_its_own_sentence(self):
        """THE GOOD HALF OF `108e9ec6`, UNTOUCHED. The relaxation is not
        reverted: a variable named `BMI` still scores 1.0 against a sentence of
        its own paper, which is what the class above measures end to end."""
        v = {"id": "v", "name": RIVAL, "label": RIVAL, "printed_as": []}
        words = premises._sentence_words(
            f"{RIVAL} was recorded to the nearest whole unit at entry.")
        assert premises.anchor_score(v, words) == 1.0

    def test_a_fully_spelled_rival_is_still_a_rival(self):
        """ROUND 4'S RULE IS KEPT. A variable whose whole printed name is in the
        sentence, where this one's is half there, still takes the clause -- the
        guard narrows what the ABBREVIATION relaxation may do and nothing else.
        Asserted on the attribution rather than on a verdict, because whether
        that reading convicts anybody is round 4's question and not this one."""
        acc = rival_account("Body mass index")
        declared = premises.readable_variables(acc)
        sentence = STEALS["the rival is named beside this variable"].replace(
            RIVAL, "body mass index")
        assert premises._attribution(declared[0], sentence, declared) == "other"

    def test_the_old_rule_is_not_the_answer_because_the_relaxation_can_lower(self):
        """THE TRAP IN THE OBVIOUS FIX, MEASURED. Scoring the rival by the
        pre-relaxation rule instead of by both looks equivalent and is not: the
        relaxation enlarges the DENOMINATOR as well as the numerator, so `IQ
        test score` is `test` alone without it and `iq, test` with it, and a
        sentence saying `test` scores 1.0 under the old rule and 0.5 under the
        new one. Reverting the rival's score would have taken an averaging
        statement away on a name of that shape -- an accusation manufactured BY
        the fix, on a case `108e9ec6` had accidentally made safe."""
        v = {"id": "v", "name": "IQ test score", "label": "IQ test score",
             "printed_as": []}
        words = premises._sentence_words("The test was administered at entry.")
        assert premises.anchor_score(v, words) == 0.5
        assert premises.anchor_score(v, words, acronyms=False) == 1.0
        assert premises.anchor_score_agreed(v, words) == 0.5

        acc = rival_account("IQ test score")
        declared = premises.readable_variables(acc)
        sentence = ("Vigour and the test were averaged across the two "
                    "inspectors' cards.")
        assert premises._attribution(declared[0], sentence, declared) == "this"
        assert accusations(acc, paper(sentence)) == []
