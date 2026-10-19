"""ROUND 9 against the checks bridge and the premise-reading layer: eight
defects, every one of them reproduced from the fixture generation at
`/tmp/checks_bridge_adversarial_round9/` before anything was changed.

THE FIXTURE PAPER IS HONEST BY CONSTRUCTION. "The Ardley school-canteen audit"
-- thirty-two pupils, a supervisor's cards and a plate-waste log -- shares
nothing with the eight earlier adversarial papers. Every printed number below is
the exact summary of the real integer data in this file, computed by the
estimator the paper's own sentence names, so any verdict worse than `consistent`
or `indeterminate` is a false accusation as a matter of arithmetic.

THE TWO FALSE ACCUSATIONS, and both are the same shape one level apart: a guard
that asked the WRONG WITNESS.

  * a bound stated for the OTHER variable in the same sentence. `The supervisor
    rated lunchtime enjoyment and lunchtime noise on cards running from 0 to 6
    and from 0 to 10 respectively` states two scales, and a reading that
    mis-splits `respectively` records the neighbour's 0-6 for noise.
    `_shared_scale` lifted the attribution tie by comparing THE TWO ACCOUNTS'
    DECLARED NUMBERS, which agree exactly when one was copied from the other --
    so the guard was satisfied when the account was wrong and refused when it was
    right. It now asks the SENTENCE how many scales it states.
  * a per-subject step read off the CONSTITUENTS of an average. The paper says
    the index is the mean of each pupil's three plate observations IN THE NEXT
    SENTENCE, and the averaging veto read the clauses of the account's own
    granularity quote only. It now asks its question wherever the paper answers
    it, and of the passage a model granted the step on.

AND THE MODEL HALF OF THE FIRST ONE IS FIXED IN THE PRE-FILTER, not in the
prompt. Measured on sonnet in two independently composed batches: with the target
saying only `the variable 'Lunchtime noise'`, the model answers `true` and its
own reason names the 0-to-10 range it read; with the target naming the range the
account records, it answers `false` ("Sentence gives noise range as 0-10, not the
0-6 the account claims") while the honest control -- the same abbreviations
block, asked about the variable whose range it does state -- stays `true`.
"""

from __future__ import annotations

import statistics as st

from metascience_agent.scaffold import checks, premise_reading as PR, premises

BAD = {"suspicious", "highly_suspicious", "impossible"}

# --------------------------------------------------------------------------
# The Ardley audit's real per-pupil data
# --------------------------------------------------------------------------

#: Lunchtime enjoyment, whole points on a 0-6 supervisor card.
ENJOY = [2, 4, 1, 3, 0, 2, 4, 3, 1, 2, 3, 4, 2, 0, 3, 1,
         2, 4, 3, 2, 1, 3, 0, 4, 2, 3, 1, 2, 4, 3, 2, 1]

#: Lunchtime noise, whole points on a 0-10 card. A DIFFERENT card.
NOISE = [7, 3, 9, 5, 8, 2, 6, 10, 4, 7, 1, 9, 3, 8, 5, 6,
         2, 10, 7, 4, 9, 3, 8, 5, 1, 6, 10, 2, 7, 4, 9, 5]

#: Each pupil's THREE plate observations of vegetable portions. The "vegetable
#: index" is the mean of her three, so it moves in steps of 1/3.
VEG = [[2, 0, 1], [1, 3, 2], [0, 0, 2], [3, 1, 1], [2, 2, 0], [1, 0, 3],
       [0, 2, 2], [3, 3, 1], [1, 1, 0], [2, 0, 2], [0, 3, 3], [1, 2, 1],
       [3, 0, 0], [2, 1, 3], [0, 1, 1], [1, 3, 0], [2, 2, 2], [3, 1, 0],
       [0, 0, 3], [1, 1, 2], [2, 3, 1], [0, 2, 0], [3, 2, 3], [1, 0, 1],
       [2, 1, 2], [0, 3, 1], [3, 0, 2], [1, 2, 3], [2, 0, 0], [0, 1, 2],
       [1, 3, 1], [3, 2, 0]]
VEG_INDEX = [sum(p) / 3 for p in VEG]

N = len(ENJOY)
ENJOY_MEAN, ENJOY_SD = f"{st.fmean(ENJOY):.2f}", f"{st.stdev(ENJOY):.2f}"
NOISE_MEAN, NOISE_SD = f"{st.fmean(NOISE):.2f}", f"{st.stdev(NOISE):.2f}"
VEG_MEAN, VEG_SD = f"{st.fmean(VEG_INDEX):.2f}", f"{st.stdev(VEG_INDEX):.2f}"


def test_the_fixture_paper_is_honest():
    assert N == 32 and len(NOISE) == 32 and len(VEG) == 32
    assert sum(NOISE) == 185 and sum(sum(p) for p in VEG) == 136
    # The noise mean is an exact integer total over 32 and clears GRIM; the
    # vegetable index moves in thirds, so NO integer total over 32 reaches
    # 1.42 -- which is why a wrongly granted step of 1 accuses it.
    assert round(sum(NOISE) / N, 2) == float(NOISE_MEAN)
    assert not any(round(k / N, 2) == float(VEG_MEAN) for k in range(N * 4))


# --------------------------------------------------------------------------
# The paper's sentences, the account shapes, and the bridge runner
# --------------------------------------------------------------------------

N_Q = "Thirty-two pupils took part in the Ardley school-canteen audit (n = 32)."
#: One sentence, two cards, `respectively`.
RESP = ("The supervisor rated lunchtime enjoyment and lunchtime noise on cards "
        "running from 0 to 6 and from 0 to 10 respectively.")
#: The same two scales as an abbreviations block, which carries no terminal
#: punctuation, so `Haystack.sentence` expands one line into the whole block.
FOOT = ("Note. LEQ, Lunchtime Enjoyment Questionnaire, 0 to 6; NDS, Noise "
        "Disturbance Scale, 0 to 10; VPI, Vegetable Portions Index, 0 to 3")
G_ENJOY = "Lunchtime enjoyment was scored in whole points at every service."
G_NOISE = "Lunchtime noise was scored in whole points at every service."
#: The bound sentence whose numeral ENDS it, which is how most papers write one.
ENDS = "Lunchtime enjoyment was rated on a card running from 0 to 6."
VEG_COUNTED = ("Vegetable portions on each plate were counted in whole portions "
               "by the lunchtime supervisor.")
VEG_AVERAGED = ("Each pupil's vegetable index is the mean of her three lunchtime "
                "plate observations.")


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


def prose(vid, statistic, printed, quote, *, variable_id=None):
    lit = _lit(printed)
    return {"id": vid, "statistic": statistic, "printed": printed,
            "numeric": lit.get("value"), "decimals": lit.get("decimals", 0),
            "printed_form": "plain", "units": None, "variable_id": variable_id,
            "id_check": "agrees", "statistic_disputed": False,
            "source": "prose", "quote": quote, "quote_verified": "verbatim",
            "printed_in_quote": True,
            "location": {"kind": "prose", "offset": 0, "col_label": None},
            "coordinate": {"study_id": "study:main", "group_id": "grp:all",
                           "phase_id": None}}


def account(*, variables=(), values=(), reading=None):
    acc = {"paper": {"doi": "10.0000/ardley",
                     "title": "The Ardley school-canteen audit"},
           "studies": [{"id": "study:main", "design": "prospective_cohort",
                        "groups": [{"id": "grp:all", "label": "All pupils",
                                    "n": N, "n_source": "text"}]}],
           "variables": list(variables), "values": list(values),
           "document": {"tables": [{"id": "table:1",
                                    "caption": "Table 1. Lunchtime ratings of "
                                               "the audited pupils."}]}}
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


def ran(got):
    return {r["check_id"] for r in got["checks"]}


def every_reason(got):
    return {row["reason"] for r in got["refused"] for row in r["reasons"]}


def verification(acc, text, vid, field):
    return [v for v in premises.stamp(acc, text)["variables"]
            if v["id"] == vid][0][field]["verification"]


# --------------------------------------------------------------------------
# 1. A BOUND STATED FOR THE OTHER VARIABLE IN THE SAME SENTENCE
# --------------------------------------------------------------------------


def _two_cards(bquote, noise_upper):
    text = "\n\n".join([N_Q, bquote, G_ENJOY, G_NOISE]) + "\n"
    variables = [
        var("var:enjoy", "Lunchtime enjoyment", "ordinal", bsource="stated",
            lower=0, upper=6, bquote=bquote, step=1, gquote=G_ENJOY),
        var("var:noise", "Lunchtime noise", "ordinal", bsource="stated",
            lower=0, upper=noise_upper, bquote=bquote, step=1, gquote=G_NOISE)]
    values = [prose("val:n", "n", str(N), N_Q),
              cell("val:nm", "mean", NOISE_MEAN, variable_id="var:noise", row=2),
              cell("val:ns", "sd", NOISE_SD, variable_id="var:noise", row=2),
              cell("val:em", "mean", ENJOY_MEAN, variable_id="var:enjoy"),
              cell("val:es", "sd", ENJOY_SD, variable_id="var:enjoy")]
    return account(variables=variables, values=values), text, variables, values


class TestASentenceThatStatesTwoScalesLicensesNeither:
    """`_shared_scale` lifted the attribution tie by comparing the two ACCOUNTS'
    declared numbers. A mis-split of `respectively` COPIES the neighbour's
    number, so the two declarations agree by construction: the lift fired
    exactly when the account was wrong, and refused exactly when it was right.
    The witness is now the sentence."""

    def test_the_mis_split_no_longer_accuses(self):
        for bquote in (RESP, FOOT):
            acc, text, _, _ = _two_cards(bquote, 6)
            got = checks.evaluate(acc, text)
            assert accusations(got) == [], bquote[:40]
            rec = verification(acc, text, "var:noise", "bounds")
            assert rec["quote_states_a_shared_scale_with"] is None, bquote[:40]
            assert rec["lower_admitted_by"] == "quote_not_about_this_variable"

    def test_the_measured_accusation_was_grimmer_and_sprite(self):
        """WHAT IT COST BEFORE, so the fix cannot be read as hypothetical: with
        the mis-split bound admitted, an exact mean of 32 whole points on a 0-10
        card came back `suspicious` on both families."""
        acc, text, variables, values = _two_cards(RESP, 6)
        # the same account with the bound the lift used to admit
        forced = [dict(v) for v in variables]
        forced[1] = dict(forced[1], bounds=dict(forced[1]["bounds"]))
        rec = premises.bounds_verification(
            forced[1], premises.Haystack(text), forced, values)
        assert rec["lower_passed"] is None and rec["upper_passed"] is None

    def test_the_correct_reading_is_still_refused_and_that_is_the_cost(self):
        """THE COST SIDE, stated. The sentence genuinely is ambiguous to a
        vocabulary -- only its grammar assigns the scales -- so the honest
        reading refuses too. That is the safe direction, and it is what the
        model-read path exists to recover."""
        acc, text, _, _ = _two_cards(RESP, 10)
        assert accusations(checks.evaluate(acc, text)) == []
        rec = verification(acc, text, "var:noise", "bounds")
        assert rec["bound_source"] == premises.ASSUMED_BOUND_SOURCE

    def test_one_sentence_stating_one_scale_still_lifts_the_tie(self):
        """The ajcp.70049 case this lift was built for is untouched: it states
        ONE scale for both variables it names."""
        one = ("The means for inclusive decision making and inclusion of "
               "community residents were 4.06 and 4.01 on a 1-5 scale")
        assert premises.stated_ranges(one) == [(1.0, 5.0)]
        assert len(premises.stated_ranges(RESP)) == 2
        assert len(premises.stated_ranges(FOOT)) == 3


# --------------------------------------------------------------------------
# 2. THE QUESTION HAS TO NAME THE RANGE IT LICENSES
# --------------------------------------------------------------------------


class TestABoundCandidateSaysWhichRangeItAsksAbout:
    def test_the_target_names_the_range_the_account_records(self):
        acc, text, _, _ = _two_cards(RESP, 6)
        cands = [c for c in PR.candidates(acc, text)
                 if c["premise"] == "bound" and c["variable_id"] == "var:noise"]
        assert cands
        for c in cands:
            assert "the account records its range as 0 to 6" in c["target"]
            assert c["asked_bounds"] == [0, 6]

    def test_a_one_sided_range_is_named_as_one_side(self):
        v = var("var:tally", "Plates cleared", "count", bsource="definitional",
                lower=0, bquote=None)
        assert PR._variable_target(v, v["bounds"]) == (
            "the variable 'Plates cleared' "
            "(the account records its lowest possible value as 0)")

    def test_the_measured_model_verdict_withdraws_the_mis_split(self):
        """THE VERBATIM SONNET ANSWER to the fixed target, in both phrasings."""
        acc, text, variables, values = _two_cards(RESP, 6)
        cands = [cand("c1", "bound", RESP, variable_id="var:noise",
                      source="account_quote", asked_bounds=[0, 6]),
                 cand("c2", "bound", RESP, variable_id="var:enjoy",
                      source="account_quote", asked_bounds=[0, 6])]
        read = reading(
            verdict("c1", "bound", False,
                    "Sentence gives noise range as 0-10, not the 0-6 the "
                    "account claims; contradicts, doesn't establish it."),
            verdict("c2", "bound", True,
                    "States enjoyment cards ran 0 to 6."),
            candidates=cands)
        acc["premise_reading"] = read
        got = checks.evaluate(acc, text)
        assert accusations(got) == []
        noise = verification(acc, text, "var:noise", "bounds")
        assert noise["lower_admitted_by"] == "model_reading_refused"
        # AND THE HONEST HALF SURVIVES: the same sentence licenses the variable
        # whose range it does state, which is the coverage this wave buys.
        enjoy = verification(acc, text, "var:enjoy", "bounds")
        assert (enjoy["lower_passed"], enjoy["upper_passed"]) == (0, 6)
        assert enjoy["bound_source"] == "stated"

    def test_a_verdict_about_a_different_range_licenses_nothing(self):
        """A reading is a file that outlives the account it was taken against.
        A `bound` verdict answers about ONE range; asked about another, it is
        evidence in neither direction and the vocabulary decides."""
        acc, text, _, _ = _two_cards(RESP, 6)
        stale = reading(verdict("c1", "bound", True, "0 to 10 is the range"),
                        candidates=[cand("c1", "bound", RESP,
                                         variable_id="var:noise",
                                         source="account_quote",
                                         asked_bounds=[0, 10])])
        acc["premise_reading"] = stale
        assert accusations(checks.evaluate(acc, text)) == []
        rec = verification(acc, text, "var:noise", "bounds")
        assert rec["model_reading"] is None
        assert rec["lower_admitted_by"] == "quote_not_about_this_variable"
        applied = premises.stamp(acc, text)["premise_reading_applied"]
        assert applied["n_stale_question"] == 1

    def test_a_candidate_with_no_recorded_question_licenses_nothing(self):
        acc, text, _, _ = _two_cards(RESP, 6)
        acc["premise_reading"] = reading(
            verdict("c1", "bound", True, "it is the range"),
            candidates=[cand("c1", "bound", RESP, variable_id="var:noise",
                             source="account_quote")])
        assert accusations(checks.evaluate(acc, text)) == []
        assert premises.stamp(acc, text)[
            "premise_reading_applied"]["n_stale_question"] == 1


# --------------------------------------------------------------------------
# 3 and 8. THE AVERAGING VETO ASKS ITS QUESTION WHERE THE PAPER ANSWERS IT
# --------------------------------------------------------------------------

VEG_TEXT = "\n\n".join([N_Q, VEG_COUNTED, VEG_AVERAGED]) + "\n"


def _veg(derivation=None, gquote=VEG_COUNTED):
    return account(
        variables=[var("var:veg", "Vegetable index", "ordinal", step=1,
                       gquote=gquote, derivation=derivation)],
        values=[prose("val:n", "n", str(N), N_Q),
                cell("val:m", "mean", VEG_MEAN, variable_id="var:veg"),
                cell("val:s", "sd", VEG_SD, variable_id="var:veg")])


class TestAStepReadOffTheConstituentsOfAnAverage:
    def test_a_null_derivation_is_an_omission_and_not_a_licence(self):
        """`derivation` closes this shape from the account's side and is a field
        the account may leave null. Left null, GRIM returned `impossible` on an
        index that moves in thirds."""
        got = checks.evaluate(_veg(), VEG_TEXT)
        assert accusations(got) == []
        assert "discreteness_quote_reports_an_average" in every_reason(got)
        rec = verification(_veg(), VEG_TEXT, "var:veg", "granularity")
        assert rec["reports_an_average_in"] == "served_text"
        assert rec["discreteness_source"] == premises.ASSUMED_DISCRETENESS

    def test_the_derivation_witness_still_fires_where_it_is_filled(self):
        rec = verification(
            _veg(derivation="mean of the three lunchtime plate observations"),
            VEG_TEXT, "var:veg", "granularity")
        assert rec["derivation_reports_an_average"]

    def test_a_model_yes_on_the_averaging_sentence_licenses_nothing(self):
        """DEFECT 8, which had no measured model failure and was a structural
        gap awaiting one: under a verdict the step may be granted by ANY of the
        candidate sentences, including the averaging sentence itself, and
        `establishes = verdict and averaged is None` never re-read the granting
        quote."""
        acc = _veg(gquote="Portions on each plate were counted in whole units.")
        text = "\n\n".join([N_Q, "Portions on each plate were counted in whole "
                            "units.", VEG_AVERAGED]) + "\n"
        acc["premise_reading"] = reading(
            verdict("c1", "step", False, "no vegetable qualifier"),
            verdict("c2", "step", True, "whole portions"),
            candidates=[cand("c1", "step", acc["variables"][0]["granularity"]["quote"],
                             variable_id="var:veg", source="account_quote"),
                        cand("c2", "step", VEG_AVERAGED, variable_id="var:veg")])
        got = checks.evaluate(acc, text)
        assert accusations(got) == []
        rec = verification(acc, text, "var:veg", "granularity")
        assert rec["discreteness_source"] == premises.ASSUMED_DISCRETENESS
        assert rec["quote_reports_an_average"]

    def test_a_paper_that_says_no_such_thing_keeps_its_step(self):
        """THE COST SIDE. The veto can only ever remove a check, so the scan may
        be loose -- but it must not fire on a paper that never says it."""
        text = "\n\n".join([N_Q, VEG_COUNTED]) + "\n"
        rec = verification(_veg(), text, "var:veg", "granularity")
        assert rec["quote_reports_an_average"] is None
        assert rec["discreteness_source"] == premises.STATED_DISCRETENESS

    def test_an_averaging_sentence_about_another_variable_is_not_this_ones(self):
        text = "\n\n".join([N_Q, VEG_COUNTED,
                            "Each pupil's queue time is the mean of her three "
                            "recorded waits."]) + "\n"
        acc = _veg()
        acc["variables"].append(var("var:queue", "Queue time", "continuous"))
        rec = verification(acc, text, "var:veg", "granularity")
        assert rec["quote_reports_an_average"] is None


# --------------------------------------------------------------------------
# 4 and 5. A MALFORMED READING IS LOST COVERAGE, NEVER THE RUN
# --------------------------------------------------------------------------

ENJOY_TEXT = "\n\n".join([N_Q, ENDS, G_ENJOY]) + "\n"


def _enjoy(reading_block=None, **kw):
    v = var("var:enjoy", "Lunchtime enjoyment", "ordinal", bsource="stated",
            lower=0, upper=6, bquote=ENDS, step=1, gquote=G_ENJOY)
    v.update(kw)
    return account(variables=[v],
                   values=[prose("val:n", "n", str(N), N_Q),
                           cell("val:m", "mean", ENJOY_MEAN,
                                variable_id="var:enjoy"),
                           cell("val:s", "sd", ENJOY_SD,
                                variable_id="var:enjoy")],
                   reading=reading_block)


GOOD_CAND = cand("c1", "step", G_ENJOY, variable_id="var:enjoy",
                 source="account_quote")
GOOD_VERDICT = verdict("c1", "step", True)


def _block(**kw):
    out = dict(reading(GOOD_VERDICT, candidates=[GOOD_CAND]))
    out.update(kw)
    return out


class TestAHandEditedReadingCannotTakeTheRun:
    """`premise_reading.json` is loaded off disk and `attach()` writes it into
    `account.json`, so every shape a half-written or hand-edited file can have
    reaches `index` -- which is called from `premises.stamp`, the FIRST statement
    of `checks.evaluate`, outside every per-candidate try/except. Three scalars
    took the whole run: no checks, no refusals, no `checks.json`."""

    SHAPES = [
        ("verdicts is an int", _block(verdicts=7)),
        ("verdicts is a dict", _block(verdicts={"a": 1})),
        ("candidates is an int", _block(candidates=7)),
        ("candidates is a string", _block(candidates="c1")),
        ("the whole block is a list", ["not", "a", "dict"]),
        ("the whole block is a string", "premise_reading"),
    ]

    def test_no_shape_of_a_reading_raises(self):
        for name, block in self.SHAPES:
            got = checks.evaluate(_enjoy(block), ENJOY_TEXT)
            assert got["n_candidates"] == got["n_run"] + got["n_refused"], name
            assert accusations(got) == [], name

    def test_a_scalar_value_ids_is_not_iterated(self):
        block = _block(
            candidates=[cand("c1", "estimator", "Weighted %")],
            verdicts=[verdict("c1", "estimator", True)])
        block["candidates"][0]["value_ids"] = 5
        got = checks.evaluate(_enjoy(block), ENJOY_TEXT)
        assert accusations(got) == []

    def test_the_two_readers_of_bounds_and_granularity_agree(self):
        """`stamp` was hardened against a `bounds` that arrives as a list and a
        `granularity` that arrives as a string; `premise_reading.candidates`
        read the same two fields with `or {}`, which returns a non-empty list
        unchanged -- so the paid pass died on an account the stamp reads fine."""
        for field, shape in (("bounds", ["stated", 0, 6]),
                             ("bounds", "0 to 6"),
                             ("granularity", "whole"),
                             ("granularity", [1])):
            acc = _enjoy(**{field: shape})
            PR.build_prompt(PR.candidates(acc, ENJOY_TEXT))
            got = checks.evaluate(acc, ENJOY_TEXT)
            assert accusations(got) == [], f"{field}={shape!r}"


# --------------------------------------------------------------------------
# 6. A NUMERAL THAT ENDS ITS SENTENCE IS STILL A NUMERAL
# --------------------------------------------------------------------------


class TestAFullStopIsJustAFullStop:
    def test_the_bound_at_the_end_of_a_sentence_is_seen(self):
        assert premises.numeral_in(ENDS, 6)
        assert premises.numeral_in("the analysed sample was n = 40.", 40)

    def test_the_decimal_boundary_still_holds(self):
        assert not premises.numeral_in("a ratio of 1.25", 1)
        assert not premises.numeral_in("a ratio of 1.25", 5)
        assert not premises.numeral_in("version 6.5 of the card", 6)

    def test_the_four_checks_it_was_costing_run(self):
        got = checks.evaluate(_enjoy(), ENJOY_TEXT)
        assert accusations(got) == []
        assert {c.split(":")[1] for c in ran(got)} == {
            "grim", "grimmer", "sprite", "sd_or_se"}
        rec = verification(_enjoy(), ENJOY_TEXT, "var:enjoy", "bounds")
        assert (rec["lower_passed"], rec["upper_passed"]) == (0, 6)

    def test_the_same_fix_lives_in_one_place(self):
        """`n_premise.states_n` met this bug, wrote it down and fixed it in
        place; the fix was not carried to the numeral test every bound passes
        through. Both now read `_numeral_pattern`."""
        assert premises._numeral_pattern("6").endswith(r"(?!\d)(?!\.\d)")
        assert premises.numeral_counts_subjects("we analysed 40 pupils.", 40)


# --------------------------------------------------------------------------
# 7. THE BOUND SOURCE NAMES HOW THE BOUND WAS ADMITTED
# --------------------------------------------------------------------------


class TestBoundSourceIsNotTheDeclarationItIsTheAdmission:
    """`bound_source` came from `BOUND_SOURCE_OF[declared_source]` and never
    consulted `lower_admitted_by`, so a variable DECLARING `definitional` whose
    bound was in fact admitted by reading a sentence was handed to GRIM and
    `check_sd_or_se` as `logically_necessary` -- the token meaning the KIND'S own
    logic makes it necessary. Both tokens are hard bounds, so no severity moves;
    what moves is that the record stops asserting a necessity nobody
    established."""

    B = "Six of the audit days fell in the summer term, numbered 0 through 6."
    TEXT = "\n\n".join([N_Q, B, G_ENJOY]) + "\n"

    def _acc(self, reading_block=None):
        return account(
            variables=[var("var:enjoy", "Lunchtime enjoyment", "count",
                           bsource="definitional", lower=0, upper=6,
                           bquote=self.B, step=1, gquote=G_ENJOY)],
            values=[prose("val:n", "n", str(N), N_Q),
                    cell("val:m", "mean", ENJOY_MEAN, variable_id="var:enjoy"),
                    cell("val:s", "sd", ENJOY_SD, variable_id="var:enjoy")],
            reading=reading_block)

    def test_a_model_admitted_bound_is_not_logically_necessary(self):
        acc = self._acc(reading(
            verdict("q1", "bound", True, "the sentence prints 0 and 6"),
            candidates=[cand("q1", "bound", self.B, variable_id="var:enjoy",
                             source="account_quote", asked_bounds=[0, 6])]))
        rec = verification(acc, self.TEXT, "var:enjoy", "bounds")
        assert rec["declared_source"] == "definitional"
        assert rec["upper_admitted_by"] == "model_reading"
        assert rec["bound_source"] == "stated"
        assert accusations(checks.evaluate(acc, self.TEXT)) == []

    def test_a_bound_the_kind_makes_necessary_keeps_its_name(self):
        acc = account(
            variables=[var("var:plates", "Plates cleared", "count",
                           bsource="definitional", lower=0)],
            values=[prose("val:n", "n", str(N), N_Q)])
        rec = verification(acc, ENJOY_TEXT, "var:plates", "bounds")
        assert rec["lower_admitted_by"] == "kind_necessary"
        assert rec["bound_source"] == "logically_necessary"

    def test_a_refused_bound_is_still_assumed(self):
        rec = verification(self._acc(), self.TEXT, "var:enjoy", "bounds")
        assert rec["bound_source"] == premises.ASSUMED_BOUND_SOURCE


# --------------------------------------------------------------------------
# THE CONTROL: THE WHOLE HONEST PAPER, EVERY PATH, ACCUSES NOBODY
# --------------------------------------------------------------------------


def test_and_accuses_nobody():
    text = "\n\n".join([N_Q, RESP, FOOT, G_ENJOY, G_NOISE, ENDS,
                        VEG_COUNTED, VEG_AVERAGED]) + "\n"
    variables = [
        var("var:enjoy", "Lunchtime enjoyment", "ordinal", bsource="stated",
            lower=0, upper=6, bquote=ENDS, step=1, gquote=G_ENJOY),
        var("var:noise", "Lunchtime noise", "ordinal", bsource="stated",
            lower=0, upper=10, bquote=RESP, step=1, gquote=G_NOISE),
        var("var:veg", "Vegetable index", "ordinal", step=1, gquote=VEG_COUNTED)]
    values = [prose("val:n", "n", str(N), N_Q),
              cell("val:em", "mean", ENJOY_MEAN, variable_id="var:enjoy"),
              cell("val:es", "sd", ENJOY_SD, variable_id="var:enjoy"),
              cell("val:nm", "mean", NOISE_MEAN, variable_id="var:noise", row=2),
              cell("val:ns", "sd", NOISE_SD, variable_id="var:noise", row=2),
              cell("val:vm", "mean", VEG_MEAN, variable_id="var:veg", row=3),
              cell("val:vs", "sd", VEG_SD, variable_id="var:veg", row=3)]
    acc = account(variables=variables, values=values)
    got = checks.evaluate(acc, text)
    assert accusations(got) == []
    # AND THE COVERAGE IS NOT BOUGHT BY REFUSING EVERYTHING: enjoyment's own
    # sentence names only enjoyment and states one range, so its checks run.
    assert "chk:grim:val:em" in ran(got)
