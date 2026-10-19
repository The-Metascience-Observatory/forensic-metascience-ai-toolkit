"""ROUND 11 against the checks bridge and the premise-reading layer: seven
false-accusation classes and one cost defect, every one of them reproduced from
the fixture generation at `/tmp/checks_bridge_adversarial_round11/` against the
unchanged tree before anything here was written.

THE FIXTURE PAPER IS HONEST BY CONSTRUCTION. "The Ravenscar Allotment Society
plot audit" -- thirty plot-holders, two stewards' cards and a society roll --
shares no variable, sentence, scale or n with the ten earlier adversarial papers.
Every printed number below is the exact summary of the real per-plot data in this
file, so any verdict worse than `consistent` or `indeterminate` on any of them is
a false accusation as a matter of arithmetic.

FIVE OF THE SEVEN ARE ONE DEFECT: THE AVERAGING VETO WAS HELD TO THE LICENCE'S
ATTRIBUTION RULES. A licence must fail closed -- it may only fire where the
sentence positively names the variable, in the same clause, with no tie. A
REFUSAL held to those same rules fails OPEN, and round 11 walked through every
one of them on an index that is `(steward A + steward B) / 2` and so moves in
HALF points:

  * ENGLISH USES PRONOUNS. `The reported figure is the mean of the pair.` names
    nothing, so neither the vocabulary nor the model's own pre-filter would look
    at it -- six phrasings, GRIM/GRIMMER/SPRITE `impossible`, and ZERO averaging
    candidates offered to a model in every one.
  * EVERY SEPARATOR ROUND 10 ADDED TO SAVE A LICENCE ALSO DETACHED A VETO.
    `_averaging_here` split on `_CLAUSE_BREAK` and then demanded the clause name
    the variable, so `... by each of two stewards -- the two cards were
    averaged.` established the step and withdrew nothing. Seven separators.
  * A TIE DROPPED THE VETO. `names_another_variable` is set on a tie, which is
    what makes a LICENCE fail closed; the same rule let an ordinary Methods
    sentence naming a second declared variable keep the step of 1.
  * THE VETO WAS THE ONE REFUSAL THAT NEVER READ A TABLE'S CAPTION OR FOOTNOTE,
    which is exactly where a JAMA/BMJ house style states it.
  * AND THE MODEL'S CANDIDATE CAP IS A FILTER, NOT A CAP. Four decoy sentences
    took every slot and the sentence that withdraws the premise was never asked
    about -- so no amount of paid reading could rescue it.

THE OTHER TWO ARE UNDER-READING GUARDS, THE ROUND-10 SHAPE AGAIN:
`scale_claims` could not see a scale stated as a POINT COUNT, so the shared-scale
lift returned and admitted the neighbour's range; `_ESTIMATOR_STATEMENT` required
its noun BEFORE its copula, which is a constraint on word order and not on
meaning; and `_THOUSANDS_SEP` was still a list of marks, which eleven more
conversion artefacts walked past.

AND ONE COST DEFECT, not an accusation: `Haystack.sentence` re-scanned the
document from character 0 per call and rebuilt the whole served text each time,
so `premise_reading.candidates` cost 36.9 s on 104 kB of a converted table -- the
ordinary shape CLAUDE.md 8l records -- against 0.4 s of prose.
"""

from __future__ import annotations

import statistics as st
import time

from forensic_metascience_ai_toolkit.scaffold import checks, premise_reading as PR, premises

BAD = {"suspicious", "highly_suspicious", "impossible"}

# --------------------------------------------------------------------------
# The Ravenscar audit's real per-plot data
# --------------------------------------------------------------------------

#: Shed tidiness, whole points on a 0-7 warden card.
TIDY = [3, 5, 2, 6, 1, 7, 4, 0, 5, 2, 6, 3, 1, 7, 4, 2,
        3, 5, 0, 6, 7, 1, 4, 2, 5, 3, 0, 6, 4, 1]

#: Plot satisfaction, whole points on a 0-12 card. A DIFFERENT card.
SATIS = [0, 1, 2, 1, 1, 2, 0, 1, 2, 0, 1, 2, 0, 1, 2,
         10, 11, 12, 10, 11, 12, 10, 11, 12, 10, 11, 12, 10, 11, 12]

#: Bed health, scored 0-12 in WHOLE points by EACH of two stewards. The index the
#: paper reports is the mean of the pair, so a plot's own value moves in HALF
#: points: this is the quantity the averaging veto must withdraw a step of 1 from.
BED_A = [8, 4, 11, 6, 9, 2, 7, 5, 12, 3, 6, 10, 4, 8, 1,
         11, 7, 3, 9, 5, 12, 2, 6, 10, 4, 8, 5, 9, 3, 7]
BED_B = [7, 5, 10, 5, 8, 3, 8, 4, 11, 2, 7, 9, 3, 9, 2,
         10, 6, 4, 8, 6, 11, 3, 5, 9, 5, 7, 6, 8, 4, 7]
BED = [(a + b) / 2 for a, b in zip(BED_A, BED_B)]

N = len(TIDY)

#: The society's full membership roll, and the members holding a lifetime tenancy.
ROLL, LIFETIME = 1420, 9

TIDY_SD = f"{st.stdev(TIDY):.2f}"
SATIS_MEAN, SATIS_SD = f"{st.fmean(SATIS):.2f}", f"{st.stdev(SATIS):.2f}"
BED_MEAN, BED_SD = f"{st.fmean(BED):.2f}", f"{st.stdev(BED):.2f}"
#: A roll-weighted mean of the same whole-point tidiness cards. `3.51` is not
#: k/30 for any integer k, so every granularity family convicts it unless the
#: paper's own statement about its estimator is read.
WEIGHTED_TIDY = "3.51"
LIFETIME_PCT = f"{100.0 * LIFETIME / ROLL:.1f}"


def test_the_fixture_paper_is_honest():
    assert N == 30 and len(BED) == 30 and len(SATIS) == 30
    # The bed-health index moves in HALF points, so a wrongly granted step of 1
    # makes GRIM, GRIMMER and SPRITE all call an exact mean impossible.
    assert sorted({x % 1 for x in BED}) == [0.0, 0.5]
    assert round(st.fmean(BED), 2) == float(BED_MEAN)
    assert not any(round(k / N, 2) == float(BED_MEAN) for k in range(N * 13))
    # Plot satisfaction really runs 0-12; its SD of 5.12 is impossible on the
    # 0-7 card the account mis-splits onto it.
    assert min(SATIS) == 0 and max(SATIS) == 12
    assert float(SATIS_SD) > (float(SATIS_MEAN) * (7 - float(SATIS_MEAN))) ** 0.5
    # The roll-weighted tidiness mean is not an integer total over 30 either.
    assert not any(round(k / N, 2) == float(WEIGHTED_TIDY) for k in range(N * 8))
    # And 9 of 1420 is the printed 0.6%, which the audited n of 30 cannot be.
    assert round(100.0 * LIFETIME / ROLL, 1) == float(LIFETIME_PCT)


# --------------------------------------------------------------------------
# The paper's sentences and the account shapes
# --------------------------------------------------------------------------

HEAD = "Methods. Thirty plot-holders on the Ravenscar site were audited."
RESULTS = "Results. Table 1 gives the plot-level ratings of the thirty plots."
PLAIN_CAPTION = "Table 1. Plot-level ratings of the audited allotments."

BED_SCORING = ("Bed health was scored in whole points on a 0 to 12 card by each "
               "of two stewards.")
#: THE SAME FACT WITH THE TWO HALVES IN TWO SENTENCES, which is how a paper
#: usually writes it -- and which defeats a paid reading too, because the
#: sentence offered for granularity is then honestly true.
BED_SCORING_SPLIT = "Bed health was scored in whole points on a 0 to 12 card."

TIDY_SCORING = "Shed tidiness was scored in whole points on a 0 to 7 warden card."

#: AN AVERAGING SENTENCE WITH AN ANAPHORIC SUBJECT, six ways. The first two are
#: the shapes that already vetoed, kept as controls.
ANAPHORIC = [
    ("the noun repeated", "Bed health is the mean of the two stewards' cards."),
    ("each plot's bed health",
     "Each plot's bed health is the mean of the two cards."),
    ("the pair", "The reported figure is the mean of the pair."),
    ("this index", "This index is the mean of the two cards."),
    ("the latter", "The latter was averaged across the two stewards."),
    ("it", "It is the mean of the two scores that Table 1 reports."),
    ("each plot's score", "Each plot's score is the average of the two."),
    ("the two were averaged",
     "The two were averaged to give the figure in Table 1."),
]

#: THE SEPARATOR THAT DETACHES AN AVERAGING PREDICATE FROM ITS OWN SUBJECT. The
#: first two are the shapes `_CLAUSE_BREAK` deliberately does not split.
DETACHING = [", and ", " and then ", " -- ", " — ", " – ", ": ",
             " / ", "; ", ", which is how the figure was formed and "]
DETACHED_HEAD = "Bed health was scored in whole points by each of two stewards"
DETACHED_TAIL = "the two cards were averaged"

#: AN AVERAGING SENTENCE THAT ALSO NAMES A SECOND DECLARED VARIABLE. All three
#: are ties or near-ties in the attribution heuristic.
TIED = [
    "Bed health is the mean of the two stewards' cards, and steward workload "
    "was logged at the same visit.",
    "Steward workload was logged at each visit, and bed health is the mean of "
    "the two stewards' cards.",
    "Bed health is the mean of the two cards the stewards filled in while "
    "steward workload was being logged.",
]

#: THE SECOND SCALE, STATED FOUR WAYS `scale_claims` CANNOT COUNT. The first two
#: are round 9/10's printed ranges, kept as the controls that already refused.
SECOND_SCALE = [
    ("two printed ranges",
     "The warden rated shed tidiness and plot satisfaction on cards running "
     "from 0 to 7 and from 0 to 12 respectively."),
    ("in that order",
     "The warden rated shed tidiness and plot satisfaction on cards running "
     "from 0 to 7 and from 0 to 12, in that order."),
    ("a point count",
     "The warden rated shed tidiness on a card running from 0 to 7 and plot "
     "satisfaction on a thirteen-point card."),
    ("a 12-point card",
     "The warden rated shed tidiness on a card running from 0 to 7 and plot "
     "satisfaction on a 12-point card."),
    ("out of 12",
     "The warden rated shed tidiness from 0 to 7, while plot satisfaction was "
     "scored out of 12."),
    ("out of twelve",
     "The warden rated shed tidiness from 0 to 7 and plot satisfaction out of "
     "twelve."),
    ("response options",
     "The warden rated shed tidiness on a card running from 0 to 7; plot "
     "satisfaction used a card with thirteen response options."),
    ("a comparison",
     "The warden rated shed tidiness on a card running from 0 to 7 and plot "
     "satisfaction on a card with almost twice as many points."),
]

#: THE PAPER'S GOVERNING STATEMENT ABOUT ITS OWN MEANS, with the noun AFTER the
#: copula. The first two are the shapes `_ESTIMATOR_STATEMENT` already carried.
ESTIMATOR_STATEMENTS = [
    "Means were weighted to the society roll.",
    "All means reported are roll-weighted.",
    "Data are presented as roll-weighted means (SD).",
    "Values are shown as adjusted means and standard deviations.",
    "Table 1 presents means adjusted for plot size.",
    "Means are shrunken towards the site mean by an empirical Bayes step.",
    "Means were computed with the Horvitz-Thompson estimator for the roll.",
]

#: THE THOUSANDS SEPARATOR, eleven forms beyond the nine already enumerated.
ROLL_FORMS = [
    "1,420", "1420", "One thousand four hundred and twenty",
    "1 420", "1 420", "1’420",
    "1 420", "1 420", "1 420", "1 420", "1⁠420",
    "1​420", "1，420", "1٬420", "1ʼ420",
    "１，４２０", "1·420",
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
            "coordinate": {"study_id": "study:audit", "group_id": "grp:plots",
                           "phase_id": None}}


def account(*, variables=(), values=(), caption=PLAIN_CAPTION, footnotes=None,
            reading=None):
    table = {"id": "table:1", "caption": caption}
    if footnotes is not None:
        table["footnotes"] = list(footnotes)
    acc = {"paper": {"doi": "10.0000/ravenscar",
                     "title": "The Ravenscar Allotment Society plot audit"},
           "studies": [{"id": "study:audit", "design": "prospective_cohort",
                        "groups": [{"id": "grp:plots",
                                    "label": "All plot-holders",
                                    "n": N, "n_source": "text"}]}],
           "variables": list(variables), "values": list(values),
           "document": {"tables": [table]}}
    if reading is not None:
        acc["premise_reading"] = reading
    return acc


def reading(*verdicts, candidates=()):
    cands = list(candidates)
    return {"schema": PR.SCHEMA_VERSION, "prompt_version": PR.PROMPT_VERSION,
            "model": "sonnet", "n_candidates": len(cands), "n_asked": len(cands),
            "n_dropped": 0, "candidates": cands, "verdicts": list(verdicts),
            "problems": [], "cost_usd": 0.0, "n_calls": 1}


def cand(cid, premise, quote, *, variable_id=None, asked_bounds=None):
    return {"id": cid, "premise": premise, "quote": quote,
            "variable_id": variable_id, "value_ids": [],
            "source": "served_text", "target": "the target", "context": "",
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


def n_candidates(acc, text, premise):
    return len([c for c in PR.candidates(acc, text) if c["premise"] == premise])


# --------------------------------------------------------------------------
# The bed-health account, which every averaging fixture reports
# --------------------------------------------------------------------------


def _bed(*, gquote=BED_SCORING, caption=PLAIN_CAPTION, footnotes=None,
         second_variable=False, with_reading=False):
    variables = [var("var:bed", "Bed health index", "ordinal", bsource="stated",
                     lower=0, upper=12, bquote=gquote, step=1, gquote=gquote)]
    if second_variable:
        variables.append(var("var:work", "Steward workload", "continuous"))
    values = [cell("val:bm", "mean", BED_MEAN, variable_id="var:bed"),
              cell("val:bs", "sd", BED_SD, variable_id="var:bed"),
              cell("val:n", "n", str(N), col_label="No.", row=0)]
    rd = None
    if with_reading:
        # THE PAID PATH'S WORST CASE: the model is shown the granularity
        # sentence, which is HONESTLY TRUE about the stewards' cards, and says
        # so. Under a model `true` the vocabulary's veto is the only guard left.
        rd = reading(verdict("cand:1", "step", True),
                     candidates=[cand("cand:1", "step", gquote,
                                      variable_id="var:bed")])
    return account(variables=variables, values=values, caption=caption,
                   footnotes=footnotes, reading=rd)


def _bed_text(*sentences):
    return "\n\n".join([HEAD, *sentences, RESULTS]) + "\n"


# --------------------------------------------------------------------------
# 1. AN AVERAGING SENTENCE WITH AN ANAPHORIC SUBJECT STILL WITHDRAWS THE STEP
# --------------------------------------------------------------------------


class TestAnAnaphoricAveragingSentenceWithdrawsTheStep:
    """English does not repeat a noun phrase it has just introduced. Every
    reader here required the averaging sentence to NAME the variable, so six
    ordinary phrasings left the step of 1 standing on an index that moves in
    half points -- and offered a model ZERO candidates, so a paid pass could not
    have rescued it either."""

    def test_no_phrasing_accuses(self):
        for tag, second in ANAPHORIC:
            acc = _bed()
            text = _bed_text(BED_SCORING, second)
            assert accusations(checks.evaluate(acc, text)) == [], tag

    def test_no_phrasing_accuses_under_a_model_true_on_the_step(self):
        for tag, second in ANAPHORIC:
            acc = _bed(with_reading=True)
            text = _bed_text(BED_SCORING, second)
            assert accusations(checks.evaluate(acc, text)) == [], tag

    def test_the_record_names_the_sentence_that_withdrew_it(self):
        for tag, second in ANAPHORIC:
            acc = _bed()
            text = _bed_text(BED_SCORING, second)
            rec = verification(acc, text, "var:bed", "granularity")
            assert rec["quote_reports_an_average"], tag
            assert rec["discreteness_source"] == premises.ASSUMED_DISCRETENESS, tag

    def test_the_two_facts_may_sit_in_two_sentences(self):
        """The shape that defeats a paid reading as well: the sentence offered
        for granularity is honestly true, and the withdrawal is the next one."""
        acc = _bed(gquote=BED_SCORING_SPLIT, with_reading=True)
        text = _bed_text(BED_SCORING_SPLIT,
                         "Two stewards rated every plot independently, and the "
                         "reported figure is the mean of the pair.")
        assert accusations(checks.evaluate(acc, text)) == []

    def test_an_ambiguous_antecedent_withdraws_both_candidates_safely(self):
        """UPDATED, WAVE 7D. This test originally asserted that the rule
        resolves an anaphor to the NEAREST preceding sentence that names a
        declared variable, so a paper whose averaging sentence follows a
        DIFFERENT variable's leaves THIS one's step alone. Round 12's F2 shows
        that rule is the same position-ordered cut the rest of this wave
        removes for a refusal premise: a decoy sentence about `var:work`,
        sitting between the anaphor and `var:bed`'s own granularity sentence,
        stole the antecedent slot outright on a fresh paper sharing the same
        shape. `_antecedent_ids` now unions every sentence in the reach window
        that clears the naming threshold, so BOTH variables are candidates
        here -- exactly the "a tie names both" rule this module already
        applied within one sentence, extended across the window. Costing a
        real check on `var:bed` in this specific two-variable collision is the
        safe direction: a refusal can only ever REMOVE a check, and F2's
        fixture (this file's sibling, `test_scaffold_checks_round12.py`) shows
        the alternative -- stopping at the nearer sentence -- leaves a real
        GRIM `impossible` standing on an honest paper."""
        acc = _bed(gquote=BED_SCORING_SPLIT, second_variable=True)
        text = _bed_text(BED_SCORING_SPLIT,
                         "Steward workload was recorded at every visit.",
                         "It is the mean of the two logged intervals.")
        rec = verification(acc, text, "var:bed", "granularity")
        assert rec["quote_reports_an_average"]
        assert rec["discreteness_source"] == premises.ASSUMED_DISCRETENESS
        # AND IT NEVER BUYS AN ACCUSATION: the check is refused, not run wrong.
        assert accusations(checks.evaluate(acc, text)) == []

    def test_an_unmentioned_variable_is_never_swept_in(self):
        """The window is bounded and the test is on NAMING, not on being
        declared: a variable that appears nowhere within reach of the anaphor
        is not part of any tie, so a genuinely unambiguous case still resolves
        cleanly."""
        acc = _bed(gquote=BED_SCORING_SPLIT, second_variable=True)
        text = _bed_text(BED_SCORING_SPLIT, "It is the mean of the pair.")
        hay = premises.Haystack(text)
        offset = text.index("It is the mean of the pair.")
        got = premises._antecedent_ids(
            hay, offset, [{"id": "var:bed", "name": "Bed health index"},
                         {"id": "var:work", "name": "Steward workload"}])
        assert got == {"var:bed"}


# --------------------------------------------------------------------------
# 2. A SEPARATOR MAY DETACH AN AVERAGING PREDICATE FROM ITS SUBJECT AND THE
#    PREDICATE STILL BELONGS TO THE SENTENCE
# --------------------------------------------------------------------------


class TestAClauseBreakDoesNotDetachTheVeto:
    """Every separator round 10 added to save a LICENCE also detached a VETO,
    because `_averaging_here` split on the same pattern and then demanded the
    clause name the variable. `_CLAUSE_BREAK` is unchanged; what changed is that
    a predicate on the CONSTITUENTS (`the two cards were averaged`) names no
    quantity, so it belongs to whatever the passage is about."""

    def test_no_separator_accuses(self):
        for sep in DETACHING:
            sentence = DETACHED_HEAD + sep + DETACHED_TAIL + "."
            acc = _bed(gquote=sentence)
            text = _bed_text(sentence, "Bed health runs from 0 to 12.")
            assert accusations(checks.evaluate(acc, text)) == [], repr(sep)

    def test_a_definition_of_another_quantity_still_leaves_the_step(self):
        """Round 4's rule, kept: `<NP> is the mean of <X>` DEFINES its subject,
        and a subject that names a quantity of its own is not this variable."""
        text = ("# The Ravenscar audit\n\n## Methods\n\n" + HEAD + "\n"
                "Bed health was scored in whole points on a 0 to 12 card; the "
                "fidelity index is the mean of four steward ratings.\n\n"
                "## Results\n\n" + RESULTS + "\n")
        acc = _bed(gquote="Bed health was scored in whole points on a 0 to 12 "
                          "card; the fidelity index is the mean of four steward "
                          "ratings.")
        rec = verification(acc, text, "var:bed", "granularity")
        assert rec["quote_reports_an_average"] is None
        assert rec["discreteness_source"] == premises.STATED_DISCRETENESS


# --------------------------------------------------------------------------
# 3. A TIE IN THE ATTRIBUTION HEURISTIC DOES NOT DROP A REFUSAL
# --------------------------------------------------------------------------


class TestATieDoesNotDropTheVeto:
    """`about_this_variable` sets `names_another_variable` on a tie, which is
    what makes a LICENCE fail closed. `_averaging_here` reused it for a REFUSAL,
    where the same rule fails OPEN."""

    def test_a_second_declared_variable_in_the_sentence_does_not_save_the_step(self):
        for sentence in TIED:
            acc = _bed(second_variable=True)
            text = _bed_text(
                "Both stewards scored bed health in whole points on a 0 to 12 "
                "card.", sentence)
            assert accusations(checks.evaluate(acc, text)) == [], sentence

    def test_the_tie_is_still_an_ambiguity_for_the_licence(self):
        """The polarity is the point: the same tie that no longer blocks a
        refusal still refuses a bound."""
        here = premises.about_this_variable(
            {"id": "var:bed", "name": "Bed health index"},
            "Bed health index and bed health rating were both recorded.",
            [{"id": "var:other", "name": "Bed health rating"}])
        assert here["names_another_variable"] == "var:other"


# --------------------------------------------------------------------------
# 4. THE TABLE'S OWN CAPTION AND FOOTNOTES ARE READ BY THE VETO
# --------------------------------------------------------------------------


class TestTheTableFurnitureIsReadByTheAveragingVeto:
    """`model_output_reason`, `table_notes` and both `named_estimator` callers
    read a table's caption; the averaging veto read the served text and the
    account's `derivation` and nothing else. A JAMA/BMJ house-style footnote is
    exactly where a paper states this premise."""

    FOOTNOTE = "Each entry is the mean of the two stewards' cards."

    def test_the_statement_in_the_caption_withdraws_the_step(self):
        acc = _bed(caption=PLAIN_CAPTION + " " + self.FOOTNOTE)
        assert accusations(checks.evaluate(acc, _bed_text(BED_SCORING))) == []

    def test_the_statement_in_the_footnotes_field_withdraws_the_step(self):
        acc = _bed(footnotes=[self.FOOTNOTE])
        assert accusations(checks.evaluate(acc, _bed_text(BED_SCORING))) == []

    def test_the_record_says_where_it_read_it(self):
        acc = _bed(footnotes=[self.FOOTNOTE])
        rec = verification(acc, _bed_text(BED_SCORING), "var:bed", "granularity")
        assert rec["reports_an_average_in"] == "table_furniture"

    def test_a_plain_caption_leaves_the_step_where_it_was(self):
        """The control: with nothing said anywhere the check still RUNS, so the
        fixture cannot pass by refusing everything."""
        acc = _bed(gquote=TIDY_SCORING)
        tidy = [var("var:tidy", "Shed tidiness", "ordinal", bsource="stated",
                    lower=0, upper=7, bquote=TIDY_SCORING, step=1,
                    gquote=TIDY_SCORING)]
        values = [cell("val:tm", "mean", WEIGHTED_TIDY, variable_id="var:tidy"),
                  cell("val:ts", "sd", TIDY_SD, variable_id="var:tidy"),
                  cell("val:n", "n", str(N), col_label="No.", row=0)]
        acc = account(variables=tidy, values=values)
        text = _bed_text(TIDY_SCORING)
        assert accusations(checks.evaluate(acc, text)) != []


# --------------------------------------------------------------------------
# 5. THE MODEL'S CANDIDATE SET IS ORDERED BY EVIDENCE, NOT BY POSITION
# --------------------------------------------------------------------------


DECOYS = (
    "Bed health has a long history as a composite of warden judgements. "
    "Bed health means for the borough are published each spring. "
    "The bed health index is summed into a site-level aggregate. "
    "Bed health averages for the county are divided by tenancy type. ")


class TestARefusalCandidateSetIsAFilterUnlessItIsRanked:
    """A cap ordered by POSITION is a cap for a licence and a FILTER for a
    refusal: the candidate set is what the model is allowed to see, and a
    premise it is never shown is one it cannot withdraw."""

    #: NINE SENTENCES THAT NAME THE VARIABLE AND CARRY COMBINATION LANGUAGE, and
    #: say nothing about how its own values were formed. Each matches the loose
    #: recall net and none matches the narrow `AVERAGED` shape, which is exactly
    #: what an introduction and a discussion are full of.
    WORKLOAD_DECOYS = [
        "Steward workload has a long history as a composite of warden judgements.",
        "Steward workload means for the borough are published each spring.",
        "The steward workload figures are summed into a site-level aggregate.",
        "Steward workload averages for the county are divided by tenancy type.",
        "Steward workload was combined with plot area in an earlier report.",
        "A steward workload index has been published since 1994.",
        "Steward workload indices for neighbouring sites are pooled by the borough.",
        "Steward workload averaging was discussed at the annual meeting.",
        "Steward workload aggregated across sites is reported elsewhere.",
    ]

    def test_the_sentence_that_withdraws_the_premise_survives_the_cap(self):
        """Asked of a variable the vocabulary does NOT already veto -- the
        averaging clause defines ANOTHER declared quantity, so the veto is
        correctly silent and the question is the model's. Nine decoys precede
        it, which is more than the budget."""
        sentence = ("The warden fidelity index is the mean of two steward "
                    "workload logs.")
        variables = [
            var("var:work", "Steward workload", "continuous", step=1,
                gquote="Steward workload was recorded in whole minutes."),
            var("var:fid", "Warden fidelity index", "continuous")]
        values = [cell("val:wm", "mean", "12.34", variable_id="var:work"),
                  cell("val:n", "n", str(N), col_label="No.", row=0)]
        acc = account(variables=variables, values=values)
        text = _bed_text("Steward workload was recorded in whole minutes.",
                         *self.WORKLOAD_DECOYS, sentence)
        offered = [c["quote"] for c in PR.candidates(acc, text)
                   if c["premise"] == "averaging"]
        assert offered, "no averaging candidate was offered at all"
        assert len(offered) > PR.MAX_TEXT_CANDIDATES
        # IT IS FIRST, because it is the only one carrying the narrow shape a
        # judgement would actually use; ordered by position it was tenth of ten
        # and the budget stopped at four.
        assert offered[0] == sentence
        assert all(not premises.AVERAGED.search(q) for q in offered[1:])

    def test_four_decoys_do_not_bury_the_vocabulary_veto(self):
        sentence = DETACHED_HEAD + " -- " + DETACHED_TAIL + "."
        acc = _bed(gquote=sentence)
        text = _bed_text(DECOYS + sentence, "Bed health runs from 0 to 12.")
        assert accusations(checks.evaluate(acc, text)) == []


# --------------------------------------------------------------------------
# 6. A SCALE PRINTED BETWEEN TWO NAMES MODIFIES THE NEARER ONE
# --------------------------------------------------------------------------


def _two_cards(sentence):
    """The account that mis-split `sentence`: plot satisfaction's own card is
    0-12 and the reading recorded the neighbour's 0-7."""
    gran = "Plot satisfaction was scored in whole points by the warden."
    text = _bed_text(sentence, gran)
    variables = [
        var("var:tidy", "Shed tidiness", "ordinal", bsource="stated", lower=0,
            upper=7, bquote=sentence, step=1,
            gquote="Shed tidiness was scored in whole points."),
        var("var:satis", "Plot satisfaction", "ordinal", bsource="stated",
            lower=0, upper=7, bquote=sentence, step=1, gquote=gran)]
    values = [cell("val:sm", "mean", SATIS_MEAN, variable_id="var:satis", row=2),
              cell("val:ss", "sd", SATIS_SD, variable_id="var:satis", row=2),
              cell("val:n", "n", str(N), col_label="No.", row=0)]
    return account(variables=variables, values=values), text


class TestASecondScaleNeedNotBeCountableToRefuseTheLift:
    def test_no_phrasing_of_the_second_scale_lifts_the_tie(self):
        for tag, sentence in SECOND_SCALE:
            acc, text = _two_cards(sentence)
            assert accusations(checks.evaluate(acc, text)) == [], tag

    def test_the_lift_is_refused_and_the_record_says_so(self):
        for tag, sentence in SECOND_SCALE:
            acc, text = _two_cards(sentence)
            rec = verification(acc, text, "var:satis", "bounds")
            assert rec["quote_states_a_shared_scale_with"] is None, tag
            assert rec["bound_source"] == premises.ASSUMED_BOUND_SOURCE, tag

    def test_the_uncountable_phrasings_really_do_defeat_the_counter(self):
        """The four new ones state ONE countable scale, which is why the count
        could not settle them and the position had to."""
        for tag, sentence in SECOND_SCALE[2:]:
            assert len(premises.scale_claims(sentence)) == 1, tag

    def test_the_ajcp_sentence_this_lift_exists_for_is_untouched(self):
        """The case the lift was built for names ONE of its variables again
        AFTER the scale, so the two names are not on opposite sides of it."""
        one = ("The means for inclusive decision making and inclusion of "
               "community residents were 4.06 and 4.01 on a 1-5 scale, "
               "corresponding to “agree” to inclusive decision "
               "making-related prompts.")
        a = {"id": "var:idm", "name": "Inclusive decision making"}
        b = {"id": "var:icr", "name": "Inclusion of community residents"}
        assert premises.scale_claims(one) == [(1.0, 5.0)]
        assert premises.scale_sits_between(one, a, b) is False
        assert premises.scale_sits_between(one, b, a) is False

    def test_a_scale_between_the_two_names_is_the_first_one_s(self):
        sentence = SECOND_SCALE[2][1]
        a = {"id": "var:tidy", "name": "Shed tidiness"}
        b = {"id": "var:satis", "name": "Plot satisfaction"}
        assert premises.scale_sits_between(sentence, a, b) is True
        assert premises.scale_sits_between(sentence, b, a) is True


# --------------------------------------------------------------------------
# 7. AN ESTIMATOR STATEMENT MAY PUT ITS NOUN AFTER ITS COPULA
# --------------------------------------------------------------------------


def _weighted(statement):
    variables = [var("var:tidy", "Shed tidiness", "ordinal", bsource="stated",
                     lower=0, upper=7, bquote=TIDY_SCORING, step=1,
                     gquote=TIDY_SCORING)]
    values = [cell("val:tm", "mean", WEIGHTED_TIDY, variable_id="var:tidy"),
              cell("val:ts", "sd", TIDY_SD, variable_id="var:tidy"),
              cell("val:n", "n", str(N), col_label="No.", row=0)]
    return (account(variables=variables, values=values),
            _bed_text(TIDY_SCORING, statement))


class TestTheEstimatorStatementIsNotAConstraintOnWordOrder:
    def test_no_phrasing_accuses(self):
        for statement in ESTIMATOR_STATEMENTS:
            acc, text = _weighted(statement)
            assert accusations(checks.evaluate(acc, text)) == [], statement

    def test_the_vocabulary_reads_every_one_of_them(self):
        for statement in ESTIMATOR_STATEMENTS:
            assert premises.estimator_statement(
                _bed_text(TIDY_SCORING, statement)), statement

    def test_a_plain_descriptive_paper_is_still_checked(self):
        """`Mean (SD)` over a plain caption stays checkable, which is the honest
        column this whole family exists for."""
        acc, text = _weighted("Means and standard deviations are reported for "
                              "every plot-level rating.")
        assert premises.estimator_statement(text) is None
        assert accusations(checks.evaluate(acc, text)) != []


# --------------------------------------------------------------------------
# 8. THE THOUSANDS SEPARATOR IS DEFINED BY WHAT IT IS NOT
# --------------------------------------------------------------------------


def _roll(printed):
    variables = [var("var:life", "Lifetime tenancy", "percentage_of_subjects")]
    values = [cell("val:c", "count", str(LIFETIME), variable_id="var:life",
                   col_label="No. (%)"),
              cell("val:p", "percentage", LIFETIME_PCT + "%",
                   variable_id="var:life", col_label="No. (%)"),
              cell("val:n", "n", str(N), col_label="No.", row=0)]
    text = _bed_text(f"The society roll lists {printed} members.")
    return account(variables=variables, values=values), text


class TestEveryPrintedFormOfTheRollReachesTheCeiling:
    def test_the_ceiling_reads_every_form(self):
        for printed in ROLL_FORMS:
            _, text = _roll(printed)
            assert ROLL in premises.printed_subject_counts(text), repr(printed)
            assert premises.paper_max_n([], text) == ROLL, repr(printed)

    def test_no_form_accuses(self):
        for printed in ROLL_FORMS:
            acc, text = _roll(printed)
            assert accusations(checks.evaluate(acc, text)) == [], repr(printed)

    def test_the_tail_of_the_number_is_never_the_ceiling(self):
        for printed in ROLL_FORMS:
            _, text = _roll(printed)
            assert 420 not in premises.printed_subject_counts(text), repr(printed)


# --------------------------------------------------------------------------
# 9. THE COST OF READING ONE PAPER IS LINEAR IN ITS LENGTH
# --------------------------------------------------------------------------


class TestTheSentenceReaderIsNotQuadratic:
    """`Haystack.sentence` re-ran `_SENT_END.finditer(text, 0, start)` from
    character 0 on every call and rebuilt the whole served text each time, so a
    CONVERTED TABLE -- numbers, dashes, colons and slashes with no terminal
    punctuation, which CLAUDE.md 8l records as the ordinary output of a
    converter -- cost 36.9 s on 104 kB against 0.4 s of prose of the same
    length. A paper plus supplement at 200-400 kB cost minutes before a model
    was asked anything."""

    ROW = "| plot 3 - 12 : 4 / 5 - 6 "

    def _text(self, k):
        return HEAD + " " + BED_SCORING + " " + self.ROW * k

    def test_the_same_sentence_is_built_once_however_many_matches_land_in_it(self):
        hay = premises.Haystack(self._text(2000))
        spans = [(i, i + 4) for i in range(200, 4000, 40)]
        first = hay.sentence(spans[0])
        assert all(hay.sentence(s) == first for s in spans)

    def test_doubling_the_document_does_not_quadruple_the_cost(self):
        acc = _bed()
        small, large = self._text(1000), self._text(4000)
        t0 = time.monotonic()
        PR.candidates(acc, small)
        short = time.monotonic() - t0
        t0 = time.monotonic()
        PR.candidates(acc, large)
        long = time.monotonic() - t0
        # Four times the text, and quadratic would be sixteen times the work.
        assert long < max(8 * short, 0.25), (short, long)

    def test_the_boundaries_agree_with_a_direct_scan(self):
        """The index replaces a per-call scan, so it has to answer the same
        question the scan did on ordinary prose."""
        text = ("First sentence about bed health. Second one, with a 0 to 12 "
                "card.\n\nA new paragraph.\nAnd a line.\n\n\nAnd another.\n")
        hay = premises.Haystack(text)
        for i in range(len(text) - 3):
            left, right = hay.sentence_bounds((i, i + 2))
            assert 0 <= left <= i
            assert right >= i + 1
