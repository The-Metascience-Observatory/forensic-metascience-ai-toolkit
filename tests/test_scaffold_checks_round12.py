"""ROUND 12 against the checks bridge and the premise-reading layer, and WAVE 7D
(the escalation their own synthesis named): recall for a REFUSAL premise has to
be a WINDOW, complete by construction over every passage that could plausibly
speak to it -- not a position-capped cut using the same name-matching rule three
rounds of adversarial probing kept defeating.

TWO FALSE-ACCUSATION CLASSES FROM ROUND 12, BOTH LEFT OPEN AT THAT ROUND'S OWN
COMMIT, NOW CLOSED.

F2 -- AN ORDINARY METHODS SENTENCE ABOUT A DIFFERENT DECLARED VARIABLE, sitting
between an anaphoric averaging sentence and its true antecedent, used to steal
the antecedent slot outright: `premises._antecedent_ids` stopped at the NEAREST
sentence naming ANY declared variable, so `Peal quality was scored in whole
points ... by each of two judges. Striking accuracy was recorded at the same
practice. The reported figure is the mean of the pair.` resolved to `var:strike`
and left `var:peal`'s step of 1 standing -- GRIM `impossible` on an honest
paper, and the same rule governs `premise_reading._averaging_candidates`'s
POOL, so the sentence was never even OFFERED to a paid reading. Fixed by
scanning the WHOLE reach window and unioning every sentence that clears the
naming threshold, not stopping at the first one (the same "a tie names both"
rule already used within one sentence, now extended across the window).

F3 -- `document.tables[].footnotes` REACHED ONLY THE AVERAGING VETO. Round 11
wired the field into `granularity_verification`; round 12 measured that
`named_estimator` (which `estimated_mean_reason` AND `weighted_percentage_reason`
call) and `value_premise`'s `analysis_n_varies` still could not see it, and on a
JATS-sourced paper the footnote is not in the served body text either
(`extraction/jats.py` strips `table-wrap-foot`). Fixed by threading a
`furniture` channel -- the table's own footnotes, by table id -- into all
three, computed once in `stamp` exactly as `captions` already is.

THE FOOTNOTE-CHANNEL FIX GENERALISES to `paper_max_n` (the alternative-base
ceiling) too: `premises.document_furniture_text` widens the text it scans, so a
subject count printed only in a table's caption or footnote is not invisible to
the one refusal that is deliberately regex-only and never adjudicated by a
model (D71).

`premises.REFUSAL_PREMISE_CHANNELS` NAMES THE MATRIX this file's
`TestThePremiseChannelRegistry` walks, so a channel going quiet again shows up
as a hole in ONE test rather than as a fresh adversarial fixture next round.
"""

from __future__ import annotations

import statistics as st

import pytest

from metascience_agent.scaffold import bind, checks, premise_reading as PR, premises

BAD = {"suspicious", "highly_suspicious", "impossible"}


# --------------------------------------------------------------------------
# The Wyecliffe Cathedral tower bell-ringing survey's real per-ringer data
# (round 12's own fixture paper; shares nothing with rounds 1-11)
# --------------------------------------------------------------------------

#: Peal quality, scored 0-14 in WHOLE points by EACH of two judges. The index
#: the paper reports is the mean of the pair, so a ringer's own value moves in
#: HALF points: this is the quantity the averaging veto must withdraw a step of
#: 1 from.
PEAL_A = [8, 4, 13, 6, 9, 2, 7, 5, 14, 3, 6, 12, 4, 8, 1, 10,
          13, 7, 3, 11, 5, 14, 2, 6, 12, 4, 9, 5, 11, 3, 8, 7]
PEAL_B = [8, 5, 12, 5, 8, 3, 8, 4, 13, 2, 7, 11, 3, 9, 2, 9,
          12, 6, 4, 10, 6, 13, 3, 5, 11, 5, 8, 6, 10, 4, 7, 8]
PEAL = [(a + b) / 2 for a, b in zip(PEAL_A, PEAL_B)]
N = len(PEAL)
PEAL_MEAN = f"{st.fmean(PEAL):.2f}"
PEAL_SD = f"{st.stdev(PEAL):.2f}"

# The fixture paper is honest by construction: at least one value of PEAL is a
# half-integer, so the true total over 32 ringers is not reproducible by any
# integer-step-1 reading -- exactly what a wrongly granted step of 1 convicts.
assert sorted({x % 1 for x in PEAL}) == [0.0, 0.5]

#: An honest roll-weighted mean of the 0-9 striking cards. 3.51 x 32 = 112.32,
#: so read as a plain total over n it is GRIM `impossible`.
W_MEAN, W_SD = "3.51", "2.22"
assert not any(round(k / N, 2) == float(W_MEAN) for k in range(N * 5))

#: An honest unweighted count beside its roll-weighted percentage over the full
#: guild roll (240 members), stated ONLY as prose naming the roll -- never as an
#: account `n` row. 12/32 = 37.5%, and no integer denominator at or below the
#: coordinate's own n of 32 reproduces 5.0%.
W_COUNT, W_PCT, ROLL = "12", "5.0", 240
assert round(100.0 * int(W_COUNT) / ROLL, 1) == float(W_PCT)
assert not any(round(100.0 * int(W_COUNT) / k, 1) == float(W_PCT)
              for k in range(1, N + 1))

#: An honest mean of 30 returned cards (item-level missingness). At n = 32 it
#: is reachable under neither the round-half nor the truncation convention.
MISS_MEAN = "3.89"
assert not any(round(k / N, 2) == float(MISS_MEAN) for k in range(N * 5))


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
        row=1, col=1, table="table:1"):
    lit = _lit(printed)
    return {"id": vid, "statistic": statistic, "printed": printed,
            "numeric": lit.get("value"), "decimals": lit.get("decimals", 0),
            "printed_form": "percent" if lit.get("is_percent") else "plain",
            "units": None, "variable_id": variable_id, "id_check": "agrees",
            "statistic_disputed": False, "source": "table", "quote": None,
            "quote_verified": "cell", "printed_in_quote": None,
            "location": {"kind": "table_cell", "table_id": table, "row": row,
                        "col": col, "col_label": col_label},
            "coordinate": {"study_id": "study:tower", "group_id": "grp:ringers",
                          "phase_id": None}}


def prose(vid, statistic, printed, quote, *, variable_id=None):
    lit = _lit(printed)
    return {"id": vid, "statistic": statistic, "printed": printed,
            "numeric": lit.get("value"), "decimals": lit.get("decimals", 0),
            "printed_form": "percent" if lit.get("is_percent") else "plain",
            "units": None, "variable_id": variable_id, "id_check": "agrees",
            "statistic_disputed": False, "source": "prose", "quote": quote,
            "quote_verified": "verbatim", "printed_in_quote": True,
            "location": {"kind": "prose", "offset": 0, "col_label": None},
            "coordinate": {"study_id": "study:tower", "group_id": "grp:ringers",
                          "phase_id": None}}


def account(*, variables=(), values=(), tables=None,
           caption="Table 1. Ringer-level scores from the Wyecliffe tower survey."):
    if tables is None:
        tables = [{"id": "table:1", "caption": caption}]
    return {"paper": {"doi": "10.0000/wyecliffe",
                      "title": "The Wyecliffe Cathedral tower bell-ringing survey"},
            "studies": [{"id": "study:tower", "design": "prospective_cohort",
                        "groups": [{"id": "grp:ringers", "label": "All tower ringers",
                                    "n": N, "n_source": "text"}]}],
            "variables": list(variables), "values": list(values),
            "document": {"tables": tables}}


def reading(*verdicts, candidates=()):
    cands = list(candidates)
    return {"schema": PR.SCHEMA_VERSION, "prompt_version": PR.PROMPT_VERSION,
            "model": "sonnet", "n_candidates": len(cands), "n_asked": len(cands),
            "n_dropped": 0, "candidates": cands, "verdicts": list(verdicts),
            "problems": [], "cost_usd": 0.0, "n_calls": 1}


def cand(cid, premise, quote, *, variable_id=None):
    return {"id": cid, "premise": premise, "quote": quote,
            "variable_id": variable_id, "value_ids": [],
            "source": "served_text", "target": "the target", "context": "",
            "asked_bounds": None, "question": PR.QUESTIONS[premise],
            "quote_located": True, "quote_not_located_because": ""}


def verdict(cid, premise, establishes, reason="a model reason"):
    return {"candidate_id": cid, "premise": premise, "establishes": establishes,
            "reason": reason, "model": "sonnet",
            "prompt_version": PR.PROMPT_VERSION}


def run(acc, text):
    return checks.evaluate(acc, text)


def accusations(got):
    return [(r["check_id"], r["severity"]) for r in got["checks"]
            if r["severity"] in BAD]


def n_averaging_candidates(acc, text, variable_id=None):
    got = [c for c in PR.candidates(acc, text) if c["premise"] == "averaging"]
    if variable_id is not None:
        got = [c for c in got if c["variable_id"] == variable_id]
    return len(got)


# --------------------------------------------------------------------------
# F2 -- A DECOY SENTENCE NAMING A DIFFERENT DECLARED VARIABLE
# --------------------------------------------------------------------------

INTRO = ("Peal quality was scored in whole points on a 0 to 14 card by each "
        "of two judges.")
G_STRIKE = "Striking accuracy was recorded in whole points at every practice."
ANAPHOR = "The reported figure is the mean of the pair."

#: THE SENTENCE A PAPER WRITES BETWEEN INTRODUCING THE VARIABLE AND SAYING HOW
#: THE TWO CARDS WERE COMBINED. Every one of these names a DIFFERENT declared
#: variable and says nothing about combining anything.
DECOYS = {
    "control -- nothing in between": None,
    "another declared variable, one plain sentence":
        "Striking accuracy was recorded at the same practice.",
    "a cross-reference to the table":
        "Table 1 gives the distribution of striking accuracy.",
    "two sentences in between":
        "Striking accuracy was recorded at the same practice. The band "
        "captain collected both sheets at the end of the evening.",
}


def _peal_variables():
    return [
        var("var:peal", "Peal quality", "ordinal", bsource="stated",
            lower=0, upper=14, bquote=INTRO, step=1, gquote=INTRO),
        var("var:strike", "Striking accuracy", "ordinal", bsource="not_stated",
            step=1, gquote=G_STRIKE),
    ]


def _peal_values():
    return [prose("val:n", "n", str(N),
                  "Thirty-two ringers took part in the Wyecliffe tower "
                  "survey (n = 32)."),
            cell("val:pm", "mean", PEAL_MEAN, variable_id="var:peal", row=1),
            cell("val:ps", "sd", PEAL_SD, variable_id="var:peal", row=1)]


def _text_with_decoy(decoy):
    parts = [
        "Thirty-two ringers took part in the Wyecliffe tower survey (n = 32).",
        INTRO,
    ] + ([decoy] if decoy else []) + [ANAPHOR, G_STRIKE]
    return "\n\n".join(parts) + "\n"


class TestADecoySentenceDoesNotStealTheAntecedent:
    """`_antecedent_ids` used to stop at the NEAREST sentence naming any
    declared variable. A decoy about a DIFFERENT variable, sitting between the
    anaphor and its true antecedent, stole the slot and left the true
    variable's step of 1 standing."""

    @pytest.mark.parametrize("tag,decoy", list(DECOYS.items()))
    def test_no_decoy_shape_leaves_the_step_standing(self, tag, decoy):
        acc = account(variables=_peal_variables(), values=_peal_values())
        text = _text_with_decoy(decoy)
        assert accusations(run(acc, text)) == [], tag

    def test_the_true_antecedent_is_in_the_returned_set_despite_the_decoy(self):
        acc = account(variables=_peal_variables(), values=_peal_values())
        text = _text_with_decoy(DECOYS["another declared variable, one plain sentence"])
        hay = premises.Haystack(text)
        declared = _peal_variables()
        offset = text.index(ANAPHOR)
        got = premises._antecedent_ids(hay, offset, declared)
        assert "var:peal" in got
        # THE TIE NAMES BOTH, deliberately: the decoy's own variable is not
        # excluded just because it lost the OLD nearest-sentence race.
        assert "var:strike" in got

    def test_the_free_path_alone_now_resolves_it_with_no_model_needed(self):
        """Round 12's own measurement was that the anaphor was never even a
        CANDIDATE for a model, so no amount of paid reading could have rescued
        it (`premise_reading._averaging_candidates` asks the identical
        `_antecedent_ids` question to decide admission). Fixing the shared
        function closes BOTH channels at once and, for this shape, the FREE
        path resolves it completely on its own: `averaging_statements` calls
        the same widened function, so the vocabulary already vetoes the step
        before a model would ever be asked -- `_averaging_candidates`
        correctly offers nothing here, because "only where the vocabulary did
        not already refuse" is the rule and there is nothing left to ask."""
        acc = account(variables=_peal_variables(), values=_peal_values())
        text = _text_with_decoy(DECOYS["another declared variable, one plain sentence"])
        stamped = premises.stamp(acc, text)
        rec = {v["id"]: v for v in stamped["variables"]}["var:peal"]["granularity"]["verification"]
        assert rec["quote_reports_an_average"]
        assert n_averaging_candidates(acc, text, "var:peal") == 0

    def test_a_planted_model_true_on_the_step_does_not_rescue_it(self):
        """THE HARDENED SHAPE (round 12's probe 9): the granularity sentence
        makes no mention of "two judges" at all, so a model asked only the
        STEP question has nothing to notice, and the averaging veto is the
        ONLY guard left. Simulated here with a planted verdict rather than a
        live call, to keep this test free and deterministic."""
        g_plain = "Peal quality was scored in whole points on a 0 to 14 card."
        variables = [
            var("var:peal", "Peal quality", "ordinal", bsource="stated",
                lower=0, upper=14, bquote=g_plain, step=1, gquote=g_plain),
            var("var:strike", "Striking accuracy", "ordinal",
                bsource="not_stated", step=1, gquote=G_STRIKE),
        ]
        text = "\n\n".join([
            "Thirty-two ringers took part in the Wyecliffe tower survey (n = 32).",
            g_plain,
            "Two judges sat independently at every practice.",
            "Striking accuracy was recorded at the same practice.",
            ANAPHOR,
            G_STRIKE,
        ]) + "\n"
        rd = reading(verdict("c1", "step", True, "whole points on the card"),
                     candidates=[cand("c1", "step", g_plain,
                                     variable_id="var:peal")])
        acc = account(variables=variables, values=_peal_values())
        acc["premise_reading"] = rd
        assert accusations(run(acc, text)) == []


# --------------------------------------------------------------------------
# THE REACH IS THE ENCLOSING SECTION, NOT A SENTENCE COUNT
# --------------------------------------------------------------------------

#: ORDINARY METHODS PROSE BETWEEN A VARIABLE AND THE SENTENCE SAYING HOW ITS TWO
#: CARDS WERE COMBINED. None of it names a declared variable and none of it says
#: anything about combining anything -- it is housekeeping, which is what a
#: Methods section is mostly made of, and there are seven sentences of it
#: because six was the old cap.
HOUSEKEEPING = [
    "The band captain collected both sheets at the end of the evening.",
    "Sheets were photographed and stored in the tower archive.",
    "A second copy was kept by the society secretary.",
    "No ringer saw another ringer's sheet before the practice ended.",
    "The archive was audited once a year by the district committee.",
    "Practices ran from seven until nine on Tuesday evenings.",
    "Attendance was noted in the tower book on arrival.",
]

_PEAL_DECLARED = [{"id": "var:peal", "name": "Peal quality"},
                  {"id": "var:strike", "name": "Striking accuracy"}]


def _antecedents(text):
    return premises._antecedent_ids(
        premises.Haystack(text), text.index(ANAPHOR), _PEAL_DECLARED)


class TestTheAnaphoraReachIsASectionNotASentenceCount:
    """`_ANAPHORA_REACH = 6` was a PROXY for a section boundary by its own
    comment's admission -- "a reach that crosses a whole section would attach a
    variable's veto to prose about something else. Six is what a Methods
    paragraph is." A paper that writes two ordinary housekeeping sentences more
    than that guess lost its true antecedent to an arbitrary cutoff while every
    word of the window was still the same Methods paragraph the constant was
    named for. The boundary is now `sections.map_sections`, which is the thing
    the constant was standing in for, and the count survives only as a FLOOR --
    so this can only ever WIDEN, which is the one direction a refusal's
    candidate window is allowed to move.

    OUT OF SCOPE, DELIBERATELY: an antecedent and a distractor in the SAME
    section. That is disambiguation, not reach, and `_antecedent_ids`'s tie rule
    already governs it by naming both."""

    def test_an_antecedent_past_the_old_cap_is_recovered(self):
        """THE MISS. Seven housekeeping sentences back, one section, no heading
        crossed: the old reach of six stopped short and returned NOTHING, so the
        step of 1 stood on an honest half-point index."""
        text = "\n\n".join(["## Methods", INTRO] + HOUSEKEEPING + [ANAPHOR]) + "\n"
        assert _antecedents(text) == {"var:peal"}

    def test_the_reach_still_stops_at_the_section_it_is_in(self):
        """AND IT IS NOT UNBOUNDED. The same distance, with a heading between
        the antecedent and the anaphor: the Introduction's sentence is not this
        Methods anaphor's subject, and reading it as one would attach a
        variable's veto to prose about something else -- the exact failure the
        replaced comment named."""
        text = "\n\n".join(
            ["## Introduction", INTRO, "## Methods"] + HOUSEKEEPING + [ANAPHOR]) + "\n"
        assert _antecedents(text) == set()

    def test_a_short_section_still_reaches_the_old_six_sentences(self):
        """NO NARROWING, which is the property that makes this safe. A section
        boundary two sentences up must not cut a window the sentence count would
        have reached: the reach is the LARGER of the two, always."""
        text = "\n\n".join(["## Methods", INTRO, "### Scoring"]
                           + HOUSEKEEPING[:3] + [ANAPHOR]) + "\n"
        assert _antecedents(text) == {"var:peal"}

    def test_an_antecedent_within_the_old_reach_resolves_unchanged(self):
        """The control: everything the old cap already found, it still finds."""
        text = "\n\n".join(["## Methods", INTRO, ANAPHOR]) + "\n"
        assert _antecedents(text) == {"var:peal"}

    def test_the_widened_window_does_not_accuse(self):
        """End to end, both channels: the free path vetoes the step, and the
        candidate pool a model would be offered stays inside
        `MAX_REFUSAL_CANDIDATES` with the larger window."""
        acc = account(variables=_peal_variables(), values=_peal_values())
        text = "\n\n".join(
            ["## Methods",
             "Thirty-two ringers took part in the Wyecliffe tower survey (n = 32).",
             INTRO] + HOUSEKEEPING + [ANAPHOR, G_STRIKE]) + "\n"
        assert accusations(run(acc, text)) == []
        got = [c for c in PR.candidates(acc, text) if c["premise"] == "averaging"]
        assert len(got) <= PR.MAX_REFUSAL_CANDIDATES


# --------------------------------------------------------------------------
# F3 -- TABLE FOOTNOTE FOR ESTIMATOR / WEIGHTED-PERCENTAGE / VARYING-N
# --------------------------------------------------------------------------

BARE_CAPTION = "Table 1. Ringer-level scores from the Wyecliffe tower survey."
G_STRIKE_BOUND = "Striking accuracy was scored on a card running from 0 to 9."


def _place(statement, place, *, extra_body=()):
    """`(tables, text)` with `statement` in exactly one of body/caption/footnote
    (or nowhere, the accusing baseline)."""
    caption = BARE_CAPTION + (" " + statement if place == "caption" else "")
    tables = [{"id": "table:1", "caption": caption,
              "footnotes": [statement] if place == "footnote" else []}]
    body = ["Thirty-two ringers took part in the Wyecliffe tower survey (n = 32).",
            *extra_body] + ([statement] if place == "body" else [])
    return tables, "\n\n".join(body) + "\n"


class TestTheEstimatorRefusalReadsTheFootnote:
    """A. an honest roll-weighted mean; GRIM must not run once the paper's own
    statement is visible, wherever it sits."""

    SAYS = "Means are weighted to the guild roll."

    def _account_and_text(self, place):
        variables = [var("var:strike", "Striking accuracy", "ordinal",
                         bsource="stated", lower=0, upper=9, bquote=G_STRIKE_BOUND,
                         step=1, gquote=G_STRIKE)]
        values = [prose("val:n", "n", str(N),
                        "Thirty-two ringers took part in the Wyecliffe tower "
                        "survey (n = 32)."),
                  cell("val:wm", "mean", W_MEAN, variable_id="var:strike"),
                  cell("val:ws", "sd", W_SD, variable_id="var:strike")]
        tables, text = _place(self.SAYS, place, extra_body=[G_STRIKE, G_STRIKE_BOUND])
        return account(variables=variables, values=values, tables=tables), text

    def test_nowhere_is_the_accusing_control(self):
        acc, text = self._account_and_text("nowhere")
        assert accusations(run(acc, text)) != []

    @pytest.mark.parametrize("place", ["body", "caption", "footnote"])
    def test_every_channel_refuses(self, place):
        acc, text = self._account_and_text(place)
        assert accusations(run(acc, text)) == [], place

    def test_the_footnote_is_not_in_the_served_text(self):
        """The point of the fix: the footnote channel is NOT a roundabout way
        of reading the served text -- the statement genuinely never appears in
        `text` when it is only a footnote (the JATS shape)."""
        _, text = self._account_and_text("footnote")
        assert self.SAYS not in text


class TestTheWeightedPercentageRefusalReadsTheFootnote:
    """B. an unweighted count beside a roll-weighted percentage, with a PLAIN
    column band that carries no signal of its own -- so the only source of the
    weighting fact is body / caption / footnote."""

    SAYS = "Percentages are weighted to the guild roll."

    def _account_and_text(self, place):
        variables = [var("var:multi", "Ringing at more than one tower",
                         "binary", bsource="definitional", lower=0, upper=1)]
        values = [prose("val:n", "n", str(N),
                        "Thirty-two ringers took part in the Wyecliffe tower "
                        "survey (n = 32)."),
                  cell("val:c", "count", W_COUNT, variable_id="var:multi",
                       col_label="No. (%)"),
                  cell("val:p", "percentage", W_PCT, variable_id="var:multi",
                       col_label="No. (%)")]
        tables, text = _place(self.SAYS, place)
        return account(variables=variables, values=values, tables=tables), text

    def test_nowhere_is_the_accusing_control(self):
        acc, text = self._account_and_text("nowhere")
        assert accusations(run(acc, text)) != []

    @pytest.mark.parametrize("place", ["body", "caption", "footnote"])
    def test_every_channel_refuses(self, place):
        acc, text = self._account_and_text(place)
        assert accusations(run(acc, text)) == [], place


class TestTheVaryingNRefusalReadsTheFootnote:
    """C. item-level missingness: the mean is over 30 returned cards, not the
    audited n of 32."""

    SAYS = "Sample sizes vary across measures owing to missing cards."

    def _account_and_text(self, place):
        variables = [var("var:faults", "Bell-handling faults", "count",
                         bsource="definitional", lower=0, step=1)]
        values = [prose("val:n", "n", str(N),
                        "Thirty-two ringers took part in the Wyecliffe tower "
                        "survey (n = 32)."),
                  cell("val:fm", "mean", MISS_MEAN, variable_id="var:faults",
                       col_label="Mean")]
        tables, text = _place(self.SAYS, place)
        return account(variables=variables, values=values, tables=tables), text

    def test_nowhere_is_the_accusing_control(self):
        acc, text = self._account_and_text("nowhere")
        assert accusations(run(acc, text)) != []

    @pytest.mark.parametrize("place", ["body", "caption", "footnote"])
    def test_every_channel_refuses(self, place):
        acc, text = self._account_and_text(place)
        assert accusations(run(acc, text)) == [], place


class TestTheAlternativeBaseCeilingReadsTheFootnote:
    """D. the paper's full guild roll is a percentage base the account's own
    `n` rows never carry, and the ceiling that lets `check_count_percent` name
    it as an alternative denominator is regex-only and document-wide."""

    SAYS = f"The guild roll numbers {ROLL} members."

    def _account_and_text(self, place):
        variables = [var("var:multi", "Ringing at more than one tower",
                         "binary", bsource="definitional", lower=0, upper=1)]
        values = [prose("val:n", "n", str(N),
                        "Thirty-two ringers took part in the Wyecliffe tower "
                        "survey (n = 32)."),
                  cell("val:c", "count", W_COUNT, variable_id="var:multi",
                       col_label="No. (%)"),
                  cell("val:p", "percentage", W_PCT, variable_id="var:multi",
                       col_label="No. (%)")]
        tables, text = _place(self.SAYS, place)
        return account(variables=variables, values=values, tables=tables), text

    def test_nowhere_is_the_accusing_control(self):
        """No mention of the roll anywhere: the ceiling stays at the audited
        n of 32, no alternative denominator is found, and the pair is a real
        arithmetic disagreement at that n -- `suspicious`."""
        acc, text = self._account_and_text("nowhere")
        got = accusations(run(acc, text))
        assert got != []

    @pytest.mark.parametrize("place", ["body", "caption", "footnote"])
    def test_every_channel_raises_the_ceiling_and_refuses(self, place):
        acc, text = self._account_and_text(place)
        assert accusations(run(acc, text)) == [], place


# --------------------------------------------------------------------------
# THE PREMISE-CHANNEL REGISTRY -- ONE CONSERVATION TEST OVER THE MATRIX
# --------------------------------------------------------------------------

#: One (accounts_and_text_builder) per registered premise type, reusing the
#: classes above so the matrix is walked against the SAME fixtures the
#: per-class tests already verified individually -- this test exists to
#: notice a channel going QUIET, not to duplicate the honesty proof.
_MATRIX_FIXTURES = {
    "estimator": TestTheEstimatorRefusalReadsTheFootnote(),
    "weighted_percentage": TestTheWeightedPercentageRefusalReadsTheFootnote(),
    "varying_n": TestTheVaryingNRefusalReadsTheFootnote(),
    "alternative_base": TestTheAlternativeBaseCeilingReadsTheFootnote(),
}


class TestThePremiseChannelRegistry:
    """`premises.REFUSAL_PREMISE_CHANNELS` names which channels each refusal
    premise is wired to read; this walks the matrix for the four premise types
    that have a `body`/`caption`/`footnote`-parametrised fixture above (the
    averaging premise's own matrix is
    `TestTheTableFurnitureIsReadByTheAveragingVeto` in
    `test_scaffold_checks_round11.py`, unchanged by this wave)."""

    @pytest.mark.parametrize("premise", sorted(_MATRIX_FIXTURES))
    def test_every_declared_channel_refuses(self, premise):
        fx = _MATRIX_FIXTURES[premise]
        channels = premises.REFUSAL_PREMISE_CHANNELS[premise]
        for channel in ("body", "caption", "footnote"):
            if channel not in channels:
                continue
            acc, text = fx._account_and_text(channel)
            assert accusations(run(acc, text)) == [], (premise, channel)

    def test_the_registry_itself_only_names_real_premise_types(self):
        assert set(premises.REFUSAL_PREMISE_CHANNELS) == {
            "averaging", "estimator", "weighted_percentage", "varying_n",
            "alternative_base"}


# --------------------------------------------------------------------------
# ITEM 4 -- THE checks.evaluate BOUNDARY IS TOTAL: A HOSTILE-SHAPE SWEEP
# --------------------------------------------------------------------------

_N_Q = "Thirty-two ringers took part in the Wyecliffe tower survey (n = 32)."
_G = "Striking accuracy was recorded in whole points at every practice."
_B = "Striking accuracy was scored on a card running from 0 to 9."
_TEXT = "\n\n".join([_N_Q, _B, _G]) + "\n"


def _base_var(**over):
    v = var("var:strike", "Striking accuracy", "ordinal", bsource="stated",
           lower=0, upper=9, bquote=_B, step=1, gquote=_G)
    v.update(over)
    return v


def _base_values():
    return [prose("val:n", "n", str(N), _N_Q),
            cell("val:sm", "mean", "3.72", variable_id="var:strike"),
            cell("val:ss", "sd", "2.29", variable_id="var:strike")]


#: EVERY SHAPE ROUND 12'S OWN CRASH HUNT TRIED (probe6_hostile_shapes.py),
#: reproduced here as a PERMANENT regression test rather than a one-off script.
#: `checks.evaluate` and `premise_reading.candidates` must survive every one --
#: "survive" meaning no exception, not that the shape is read correctly, which
#: is the same bar `well_formed`/`well_formed_variable`/`printed_labels` are
#: held to elsewhere.
_VARIABLE_SHAPES = {
    "printed_as is an int": {"printed_as": 5},
    "printed_as is a dict": {"printed_as": {"a": 1}},
    "printed_as is a bool": {"printed_as": True},
    "printed_as holds a list": {"printed_as": [["a"]]},
    "name is a list": {"name": ["Striking", "accuracy"]},
    "name is a dict": {"name": {"en": "Striking accuracy"}},
    "derived_from is an int": {"derived_from": 7},
    "kind is a list": {"kind": ["ordinal"]},
    "units is a list": {"units": ["min"]},
    "derivation is a list": {"derivation": ["mean of two"]},
    "bounds.lower is a list": {"bounds": {"source": "stated", "lower": [0],
                                          "upper": 9, "quote": _B}},
    "granularity.per_subject_step is a str":
        {"granularity": {"per_subject_step": "1", "quote": _G}},
    "label is an int": {"label": 7},
}

_DOCUMENT_SHAPES = {
    "document.tables is a dict of tables":
        {"tables": {"table:1": {"id": "table:1", "caption": "Table 1."}}},
    "a table row is a string": {"tables": ["Table 1."]},
    "footnotes is a string": {"tables": [
        {"id": "table:1", "caption": "Table 1.", "footnotes": "a note"}]},
    "footnotes holds a dict": {"tables": [
        {"id": "table:1", "caption": "Table 1.", "footnotes": [{"a": 1}]}]},
    "caption is a list": {"tables": [{"id": "table:1", "caption": ["T1"]}]},
}

_READING_SHAPES = {
    "premise_reading.candidates is a string":
        {"candidates": "x", "verdicts": []},
    "a candidate is a list":
        {"candidates": [["c1"]], "verdicts": []},
    "a verdict's candidate_id is a dict":
        {"candidates": [], "verdicts": [{"candidate_id": {"a": 1}}]},
    "candidate.value_ids is a string":
        {"candidates": [{"id": "c1", "premise": "estimator", "quote": _B,
                         "value_ids": "val:sm"}],
         "verdicts": [{"candidate_id": "c1", "establishes": True}]},
    "candidate.asked_bounds is a scalar":
        {"candidates": [{"id": "c1", "premise": "bound", "quote": _B,
                         "variable_id": "var:strike", "asked_bounds": 0}],
         "verdicts": [{"candidate_id": "c1", "establishes": True}]},
}


class TestTheBoundaryIsTotal:
    """`checks.evaluate` and `premise_reading.candidates` both run OUTSIDE
    every per-candidate try/except while they build their index -- so a field
    that is ITERATED without its shape being checked first takes the whole
    account's sidecar with it (round 9's malformed-reading crashes; round 12's
    F7, `printed_as` as a scalar). Every shape here must SURVIVE; none is
    asserted to be read CORRECTLY, which is a stronger and separate claim the
    per-defect tests above make."""

    @pytest.mark.parametrize("tag,over", list(_VARIABLE_SHAPES.items()))
    def test_variable_shapes_survive(self, tag, over):
        acc = account(variables=[_base_var(**over)], values=_base_values())
        checks.evaluate(acc, _TEXT)
        PR.candidates(acc, _TEXT)

    @pytest.mark.parametrize("tag,doc", list(_DOCUMENT_SHAPES.items()))
    def test_document_shapes_survive(self, tag, doc):
        acc = account(variables=[_base_var()], values=_base_values())
        acc["document"] = doc
        checks.evaluate(acc, _TEXT)
        PR.candidates(acc, _TEXT)

    @pytest.mark.parametrize("tag,rd", list(_READING_SHAPES.items()))
    def test_premise_reading_shapes_survive(self, tag, rd):
        acc = account(variables=[_base_var()], values=_base_values())
        acc["premise_reading"] = rd
        checks.evaluate(acc, _TEXT)
        premises.stamp(acc, _TEXT)


# --------------------------------------------------------------------------
# ITEM 5 -- A LITERAL THAT IS ITS OWN ONLY NUMERAL AND PARSES UNDER NEITHER
# GRAMMAR RECURSED FOREVER (`bind.read_literal`, found by probe, round 13)
# --------------------------------------------------------------------------

#: Printed literals that reach `read_literal`'s single-token branch and, before
#: the fix, were handed BACK TO IT UNCHANGED -- `tokens[0].rstrip(".,")` strips
#: nothing from them -- so the call recursed on the identical string until the
#: interpreter raised `RecursionError`. `4,16` is the live shape: a
#: comma-decimal value in a paper whose decimal convention reads as the period.
_NON_PROGRESSING_LITERALS = ["4,16", "1,2", "12,345,6", "0,5", "1,23"]

#: Literals that DO reach the same branch and must keep reading as they did --
#: the inner token is genuinely shorter than what was handed in, so the
#: recursion makes progress and the qualifier's precision still survives.
_QUALIFIED_LITERALS = {"< .001": 3, "approximately 84,000": 0, "p = 0.03": 2,
                       "n = 32": 0, "~1.5": 1}


class TestReadLiteralTerminates:
    """`bind.read_literal` had no base case on its own single-token branch, and
    `premises.printed_integer` reads EVERY account value typed `n` or `count`
    through it -- from inside `checks._Index.__init__`, which is outside the
    bridge's per-candidate isolation. So one comma-decimal `n` took the whole
    account's sidecar with it: no checks, no refusals, no docket at all. Same
    class as round 12's F7 (`printed_as` as a scalar)."""

    @pytest.mark.parametrize("printed", _NON_PROGRESSING_LITERALS)
    def test_an_unreadable_literal_returns_rather_than_recursing(self, printed):
        got = bind.read_literal(printed, ".")
        assert got["numeric"] is None and got["decimals"] == 0
        assert premises.printed_integer(printed, ".") is None

    @pytest.mark.parametrize("printed,decimals", list(_QUALIFIED_LITERALS.items()))
    def test_a_qualified_literal_still_keeps_its_precision(self, printed, decimals):
        got = bind.read_literal(printed, ".")
        assert got["printed_form"] == "qualified" and got["decimals"] == decimals

    @pytest.mark.parametrize("printed,sep,numeric", [
        ("84,299", ".", 84299.0), ("85.94%", ".", 85.94), ("3.14", ".", 3.14),
        ("12,5", ",", 12.5), ("84.299", ",", 84299.0), (".5", ".", 0.5)])
    def test_an_honestly_readable_literal_is_not_refused(self, printed, sep, numeric):
        assert bind.read_literal(printed, sep)["numeric"] == numeric

    @pytest.mark.parametrize("printed", _NON_PROGRESSING_LITERALS)
    def test_the_account_still_gets_its_sidecar(self, printed):
        """The end-to-end half: an honest account carrying ONE such `n`
        produced nothing at all. It must now produce a run -- the bad value
        contributes no ceiling, which can only remove checks."""
        acc = account(variables=[_base_var()],
                      values=_base_values() + [cell("val:odd", "n", printed)])
        got = checks.evaluate(acc, _TEXT)
        assert got["n_candidates"] == got["n_run"] + got["n_refused"]
        assert got["n_candidates"] > 0
