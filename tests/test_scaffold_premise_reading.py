"""The model-read premise pass: what it may move, what it may not, and what it
does when it has not been run.

THE FALLBACK IS THE WHOLE OF THE SAFETY ARGUMENT FOR EVERYTHING ELSE. Every one
of the fixture cases in `test_scaffold_checks{,_adversarial,_round3..round7}.py`
runs with no `premise_reading` block on the account, so they exercise the
vocabularies exactly as they were; this file is what pins the OTHER path, where
a reading exists.

THE FIXTURE PAPER IS HONEST. "The Marlow allotment survey" -- thirty plot-holders
whose plots a warden rates and whose harvest he weighs -- shares nothing with the
six adversarial papers. Every printed number below is the exact summary of the
real integer data in this file, so any verdict worse than `consistent` is a false
accusation as a matter of arithmetic, whichever way a model answers.

THE MODEL BOUNDARY IS MOCKED, the way `test_reconstruct` and
`test_scaffold_review` mock theirs: `premise_reading._passes.run_pass` is
replaced, so nothing here costs anything or depends on a model's mood. What is
measured is the WIRING -- which verdicts may move which premise, in which
direction -- and the wiring is what a model's answer is multiplied by.
"""

from __future__ import annotations

import json
import statistics as st
from pathlib import Path

from metascience_agent import numerals, sections
from metascience_agent.scaffold import bind, checks, premise_reading as PR, premises

BAD = {"suspicious", "highly_suspicious", "impossible"}

# --------------------------------------------------------------------------
# The Marlow allotment survey's real per-plot data
# --------------------------------------------------------------------------

#: The warden's tidiness rating of each plot, whole points on a 0-8 card.
TIDY = [2, 5, 1, 4, 3, 6, 2, 0, 4, 3, 5, 1, 2, 6, 4, 3, 0, 5, 2, 4,
        1, 3, 6, 2, 5, 4, 3, 1, 0, 2]

#: Weekly harvest per plot, RECORDED as whole grams, REPORTED in kilograms.
HARVEST_G = [4130, 2870, 5210, 3040, 6180, 2450, 4990, 3720, 5860, 4410,
             2980, 6320, 3550, 4870, 5140, 2760, 6010, 3390, 4620, 5480,
             2890, 6450, 3810, 4230, 5730, 3160, 4740, 5990, 2670, 4080]

N = len(TIDY)
TIDY_MEAN = f"{st.fmean(TIDY):.2f}"                 # 2.97
TIDY_SD = f"{st.stdev(TIDY):.2f}"                   # 1.83
HARVEST_KG = f"{sum(HARVEST_G) / N / 1000:.2f}"     # 4.39


def test_the_fixture_paper_is_honest():
    assert N == 30 and sum(TIDY) == 89 and sum(HARVEST_G) == 131730
    assert (TIDY_MEAN, TIDY_SD, HARVEST_KG) == ("2.97", "1.83", "4.39")
    # 89 whole points over 30 plots is 2.9667, printed 2.97: GRIM on it must
    # clear. The harvest is 131730 whole GRAMS over thirty plots and is printed
    # in KILOGRAMS as 4.39 -- a quantity that moves in thousandths, so a
    # whole-gram step is not the step of the number as printed.
    assert round(sum(TIDY) / N, 2) == float(TIDY_MEAN)
    assert not any(round(k / N, 2) == float(HARVEST_KG) for k in range(N * 10))


# --------------------------------------------------------------------------
# The paper, the account, and the shapes
# --------------------------------------------------------------------------

N_Q = "Thirty plot-holders took part in the Marlow allotment survey (n = 30)."
TIDY_B = "Each plot was given a tidiness rating between 0 and 8 by the warden."
TIDY_G = "Tidiness ratings were recorded in whole points on the warden's card."
TIDY_WEAK = "The tidiness rating summarised the state of a plot at each visit."
HARVEST_SENT = ("The weekly harvest of each plot was weighed to the nearest "
                "whole gram on the shed scale.")

TEXT = "\n\n".join([N_Q, TIDY_B, TIDY_WEAK, TIDY_G, HARVEST_SENT]) + "\n"


def var(vid, name, kind, *, bsource="not_stated", lower=None, upper=None,
        bquote=None, step=None, gquote=None, units=None):
    return {"id": vid, "name": name, "label": name, "printed_as": [],
            "kind": kind, "role": None, "units": units,
            "units_source": "stated" if units else "not_stated",
            "derivation": None, "derived_from": [],
            "bounds": {"source": bsource, "lower": lower, "upper": upper,
                       "quote": bquote},
            "granularity": {"per_subject_step": step, "quote": gquote}}


def _lit(printed):
    return premises.read_plain(printed) or {}


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


def cell(vid, statistic, printed, *, variable_id=None, col_label=None,
         table="table:1", row=1, col=1):
    lit = _lit(printed)
    return {"id": vid, "statistic": statistic, "printed": printed,
            "numeric": lit.get("value"), "decimals": lit.get("decimals", 0),
            "printed_form": "percent" if lit.get("is_percent") else "plain",
            "units": None, "variable_id": variable_id, "id_check": "agrees",
            "statistic_disputed": False, "source": "table", "quote": None,
            "quote_verified": "cell", "printed_in_quote": None,
            "location": {"kind": "table_cell", "table_id": table, "row": row,
                         "col": col, "col_label": col_label},
            "coordinate": {"study_id": "study:main", "group_id": "grp:all",
                           "phase_id": None}}


def account(*, variables=(), values=(), caption="Table 1. The Marlow plots.",
            reading=None):
    acc = {
        "paper": {"doi": "10.0000/marlow", "title": "The Marlow allotment survey"},
        "studies": [{"id": "study:main", "design": "prospective_cohort",
                     "groups": [{"id": "grp:all", "label": "All plots", "n": N,
                                 "n_source": "text"}]}],
        "variables": list(variables), "values": list(values),
        "document": {"tables": [{"id": "table:1", "caption": caption}]},
    }
    if reading is not None:
        acc["premise_reading"] = reading
    return acc


def tidy_var(**kw):
    """An ORDINAL, deliberately: `ordinal` is not one of the kinds whose own
    logic makes a step of 1 necessary, so the step and the range both rest on
    the paper's sentences -- which is where a model reading can move them."""
    kw.setdefault("step", 1)
    kw.setdefault("gquote", TIDY_G)
    kw.setdefault("bsource", "stated")
    kw.setdefault("lower", 0)
    kw.setdefault("upper", 8)
    kw.setdefault("bquote", TIDY_B)
    return var("var:tidy", "Plot tidiness rating", "ordinal", **kw)


def tidy_values():
    return [prose("val:n", "n", str(N), N_Q),
            cell("val:tidy_mean", "mean", TIDY_MEAN, variable_id="var:tidy",
                 col_label="Mean (SD)"),
            cell("val:tidy_sd", "sd", TIDY_SD, variable_id="var:tidy",
                 col_label="Mean (SD)")]


def reading(*verdicts, model="sonnet", candidates=None):
    """A `premise_reading.json` block, hand-built the way a paid run writes one."""
    cands = list(candidates or [])
    return {"schema": PR.SCHEMA_VERSION, "prompt_version": PR.PROMPT_VERSION,
            "model": model, "n_candidates": len(cands), "n_asked": len(cands),
            "n_dropped": 0, "candidates": cands, "verdicts": list(verdicts),
            "problems": [], "cost_usd": 0.0, "n_calls": 1}


#: The range `var:tidy` declares, and so the range a `bound` candidate about it
#: asks about. `_bound_candidates` records the pair on every bound candidate it
#: writes, and `index` admits a licence only where the pair asked about is still
#: the pair the account declares -- so a helper that omitted it would be
#: building a candidate no paid run produces.
TIDY_BOUNDS = [0, 8]

_UNSET = object()


def cand(cid, premise, quote, *, variable_id=None, value_ids=None,
         source="served_text", asked_bounds=_UNSET):
    asked = ((TIDY_BOUNDS if premise == "bound" else None)
             if asked_bounds is _UNSET else asked_bounds)
    return {"id": cid, "premise": premise, "quote": quote,
            "variable_id": variable_id, "value_ids": list(value_ids or []),
            "source": source, "target": "the target", "context": "",
            "asked_bounds": asked,
            "question": PR.QUESTIONS[premise], "quote_located": True,
            "quote_not_located_because": ""}


def verdict(cid, premise, establishes, reason="because"):
    return {"candidate_id": cid, "premise": premise, "establishes": establishes,
            "reason": reason, "model": "sonnet",
            "prompt_version": PR.PROMPT_VERSION}


def stamped(acc, text=None):
    return premises.stamp(acc, TEXT if text is None else text)


def var_of(acc, vid="var:tidy"):
    return {v["id"]: v for v in acc["variables"]}[vid]


def premise_of(acc, vid):
    return {v["id"]: v["premise"] for v in acc["values"]}[vid]


# --------------------------------------------------------------------------
# 1. NOTHING MOVES WHERE THE PASS HAS NOT RUN
# --------------------------------------------------------------------------


class TestTheFallbackIsTodaysCode:
    def test_an_account_with_no_reading_is_stamped_by_the_vocabularies(self):
        acc = stamped(account(variables=[tidy_var()], values=tidy_values()))
        g = var_of(acc)["granularity"]["verification"]
        b = var_of(acc)["bounds"]["verification"]
        assert g["discreteness_source"] == premises.STATED_DISCRETENESS
        assert b["bound_source"] == "stated"
        assert (b["lower_passed"], b["upper_passed"]) == (0, 8)
        # The record says a model was not consulted, rather than leaving the
        # question of whether one was unanswerable.
        assert g["model_reading"] is None and b["model_reading"] is None
        assert "premise_reading_applied" not in acc

    def test_the_bridge_still_runs_its_checks_and_accuses_nobody(self):
        got = checks.evaluate(account(variables=[tidy_var()],
                                      values=tidy_values()), TEXT)
        assert got["n_run"] >= 3
        assert not [r for r in got["checks"] if r["severity"] in BAD]

    def test_an_empty_index_is_the_same_as_no_index(self):
        hay = premises.Haystack(TEXT)
        assert PR.index(None, hay, {})["n_verdicts"] == 0
        assert PR.index({}, hay, {})["n_applied"] == 0


# --------------------------------------------------------------------------
# 2. A LICENCE PREMISE MOVES BOTH WAYS
# --------------------------------------------------------------------------


class TestALicencePremiseMovesBothWays:
    def test_a_model_no_withdraws_a_step_the_vocabulary_granted(self):
        acc = stamped(account(
            variables=[tidy_var()], values=tidy_values(),
            reading=reading(verdict("cand:1", "step", False,
                                    "the card is not the unit the cell prints"),
                            candidates=[cand("cand:1", "step", TIDY_G,
                                             variable_id="var:tidy",
                                             source="account_quote")])))
        g = var_of(acc)["granularity"]["verification"]
        assert g["discreteness_source"] == premises.ASSUMED_DISCRETENESS
        assert g["establishes_step_of_one"] is False
        assert [r["reason"] for r in g["reasons"]] == ["discreteness_assumed"]
        assert "a model read" in g["reasons"][0]["detail"]
        assert g["model_reading"]["candidate_id"] == "cand:1"

    def test_a_model_yes_on_another_sentence_grants_a_step_the_quote_did_not(self):
        """The NC7 shape, and the reason the pre-filter offers every candidate:
        the account's own sentence says what the variable IS, and a DIFFERENT
        sentence about the same variable says how it moves."""
        acc = stamped(account(
            variables=[tidy_var(gquote=TIDY_WEAK)], values=tidy_values(),
            reading=reading(verdict("cand:1", "step", False),
                            verdict("cand:2", "step", True, "whole points"),
                            candidates=[
                                cand("cand:1", "step", TIDY_WEAK,
                                     variable_id="var:tidy", source="account_quote"),
                                cand("cand:2", "step", TIDY_G,
                                     variable_id="var:tidy")])))
        g = var_of(acc)["granularity"]["verification"]
        assert g["discreteness_source"] == premises.STATED_DISCRETENESS
        assert g["clause"] == TIDY_G
        assert g["reasons"] == []

    def test_the_vocabulary_alone_refuses_that_same_account(self):
        """THE COVERAGE THE READING BUYS IS REAL, and this is the control that
        says so: the identical account with no reading refuses."""
        acc = stamped(account(variables=[tidy_var(gquote=TIDY_WEAK)],
                              values=tidy_values()))
        g = var_of(acc)["granularity"]["verification"]
        assert g["discreteness_source"] == premises.ASSUMED_DISCRETENESS

    def test_a_model_no_withdraws_a_stated_bound(self):
        acc = stamped(account(
            variables=[tidy_var()], values=tidy_values(),
            reading=reading(verdict("cand:1", "bound", False, "that range is the shed's"),
                            candidates=[cand("cand:1", "bound", TIDY_B,
                                             variable_id="var:tidy",
                                             source="account_quote")])))
        b = var_of(acc)["bounds"]["verification"]
        assert b["bound_source"] == premises.ASSUMED_BOUND_SOURCE
        assert (b["lower_passed"], b["upper_passed"]) == (None, None)
        assert [r["reason"] for r in b["reasons"]] == ["bound_quote_does_not_state_it"]
        assert "a model read" in b["reasons"][0]["detail"]

    def test_a_model_yes_still_needs_the_bounds_own_numeral(self):
        """THE MODEL MAY NOT SUPPLY A NUMBER. A `true` on a sentence that does
        not print the bound admits nothing, which is invariant 1 with a model in
        the loop rather than a regex."""
        acc = stamped(account(
            variables=[tidy_var(bquote=TIDY_G)], values=tidy_values(),
            reading=reading(verdict("cand:1", "bound", True, "it is the range"),
                            candidates=[cand("cand:1", "bound", TIDY_G,
                                             variable_id="var:tidy",
                                             source="account_quote")])))
        b = var_of(acc)["bounds"]["verification"]
        assert b["bound_source"] == premises.ASSUMED_BOUND_SOURCE
        assert (b["lower_passed"], b["upper_passed"]) == (None, None)

    def test_a_model_yes_on_a_sentence_that_prints_it_admits_the_bound(self):
        acc = stamped(account(
            variables=[tidy_var(bquote=TIDY_WEAK)], values=tidy_values(),
            reading=reading(verdict("cand:1", "bound", True, "0 and 8 are the ends"),
                            candidates=[cand("cand:1", "bound", TIDY_B,
                                             variable_id="var:tidy")])))
        b = var_of(acc)["bounds"]["verification"]
        assert b["bound_source"] == "stated"
        assert (b["lower_passed"], b["upper_passed"]) == (0, 8)
        assert (b["lower_admitted_by"], b["upper_admitted_by"]) == \
            ("model_reading", "model_reading")

    def test_the_averaging_veto_still_beats_a_model_yes(self):
        """A VETO THAT CAN ONLY REMOVE A CHECK IS NOT REPLACED. The average of k
        whole numbers is not whole, and no reading of the prose changes the
        arithmetic."""
        averaged = ("Each plot-holder's tidiness rating is the mean of her four "
                    "weekly whole-point ratings.")
        text = TEXT + "\n" + averaged + "\n"
        acc = stamped(account(
            variables=[tidy_var(gquote=averaged)], values=tidy_values(),
            reading=reading(verdict("cand:1", "step", True, "whole points"),
                            candidates=[cand("cand:1", "step", averaged,
                                             variable_id="var:tidy",
                                             source="account_quote")])), text)
        g = var_of(acc)["granularity"]["verification"]
        assert g["discreteness_source"] == premises.ASSUMED_DISCRETENESS
        assert g["quote_reports_an_average"]

    def test_the_kinds_own_licence_is_untouched_in_both_directions(self):
        """`count` MOVES IN WHOLE THINGS WHATEVER A SENTENCE SAYS, which is a
        schema fact and not a classification of prose. A model verdict on the
        sentence does not reach it."""
        acc = stamped(account(
            variables=[var("var:tools", "Tools borrowed", "count", step=1,
                           gquote=TIDY_G)],
            values=[prose("val:n", "n", str(N), N_Q),
                    cell("val:tools", "mean", TIDY_MEAN, variable_id="var:tools")],
            reading=reading(verdict("cand:1", "step", False, "no"),
                            candidates=[cand("cand:1", "step", TIDY_G,
                                             variable_id="var:tools",
                                             source="account_quote")])))
        g = var_of(acc, "var:tools")["granularity"]["verification"]
        assert g["discreteness_source"] == premises.NECESSARY_DISCRETENESS
        assert g["kind_makes_it_necessary"] is True

    def test_the_printed_values_still_contradict_a_bound_a_model_admitted(self):
        acc = stamped(account(
            variables=[tidy_var(bquote=TIDY_WEAK)],
            values=tidy_values() + [cell("val:out", "mean", "9.40",
                                         variable_id="var:tidy", row=9)],
            reading=reading(verdict("cand:1", "bound", True),
                            candidates=[cand("cand:1", "bound", TIDY_B,
                                             variable_id="var:tidy")])))
        b = var_of(acc)["bounds"]["verification"]
        assert b["bound_contradicted_by_printed_values"]
        assert b["bound_source"] == premises.ASSUMED_BOUND_SOURCE


# --------------------------------------------------------------------------
# 3. A REFUSAL PREMISE MOVES ONE WAY ONLY
# --------------------------------------------------------------------------

CALIBRATED = ("Table 1. The Marlow plots. Percentages are calibrated to the "
              "parish register.")
WEIGHTED = ("Table 1. The Marlow plots. All percentages are weighted to the "
            "parish population.")


def shed_var():
    return var("var:shed", "Plots with a shed", "percentage_of_subjects")


def pct_values():
    return [prose("val:n", "n", str(N), N_Q),
            cell("val:count", "count", "12", variable_id="var:shed",
                 col_label="No. (%)"),
            cell("val:pct", "percentage", "40.0", variable_id="var:shed",
                 col_label="No. (%)")]


class TestARefusalPremiseMovesOneWayOnly:
    def test_the_vocabulary_alone_lets_that_percentage_through(self):
        """The control for the next test: `calibrated` is not in
        `WEIGHTED_PERCENTAGE`, so nothing refuses, and 12/30 is 40.0% exactly."""
        acc = stamped(account(variables=[shed_var()], values=pct_values(),
                              caption=CALIBRATED))
        assert not premise_of(acc, "val:pct")["descriptive"]["percentage_is_weighted"]

    def test_a_model_yes_adds_a_refusal_the_vocabulary_missed(self):
        acc = stamped(account(
            variables=[shed_var()], values=pct_values(), caption=CALIBRATED,
            reading=reading(verdict("cand:1", "estimator", True,
                                    "calibration to a register is a weighting"),
                            candidates=[cand("cand:1", "estimator", CALIBRATED,
                                             value_ids=["val:pct"],
                                             source="printed_context")])))
        pre = premise_of(acc, "val:pct")
        assert pre["descriptive"]["percentage_is_weighted"]
        assert "percentage_is_weighted" in {r["reason"] for r in pre["reasons"]}
        assert pre["model_reading"]["estimator"]["candidate_id"] == "cand:1"

    def test_a_model_no_never_removes_a_refusal_the_vocabulary_made(self):
        """THE POLARITY THAT MATTERS. `index` does not carry a negative verdict
        for a refusal premise at all, so there is no path by which one could."""
        acc = stamped(account(
            variables=[shed_var()], values=pct_values(), caption=WEIGHTED,
            reading=reading(verdict("cand:1", "estimator", False, "no it is not"),
                            candidates=[cand("cand:1", "estimator", WEIGHTED,
                                             value_ids=["val:pct"],
                                             source="printed_context")])))
        assert premise_of(acc, "val:pct")["descriptive"]["percentage_is_weighted"]
        idx = PR.index(acc["premise_reading"], premises.Haystack(TEXT), {})
        assert idx["estimator"] == {}

    def test_a_model_yes_withdraws_a_number_a_correction_supersedes(self):
        notice = ("Correction. In Table 1 the mean tidiness rating was "
                  "misprinted as 3.40; it is in fact 2.97.")
        acc = stamped(account(
            variables=[tidy_var()],
            values=[prose("val:n", "n", str(N), N_Q),
                    prose("val:old", "mean", "3.40", notice,
                          variable_id="var:tidy")],
            reading=reading(verdict("cand:1", "correction", True, "3.40 is withdrawn"),
                            candidates=[cand("cand:1", "correction", notice,
                                             value_ids=["val:old"],
                                             source="account_quote")])))
        pre = premise_of(acc, "val:old")
        assert pre["withdrawn_by_a_correction"]
        rows = [r for r in pre["reasons"]
                if r["reason"] == "value_withdrawn_by_a_correction"]
        assert rows and "read by a model" in rows[0]["detail"]

    def test_a_refused_value_reaches_no_check(self):
        got = checks.evaluate(account(
            variables=[shed_var()], values=pct_values(), caption=CALIBRATED,
            reading=reading(verdict("cand:1", "estimator", True),
                            candidates=[cand("cand:1", "estimator", CALIBRATED,
                                             value_ids=["val:pct"],
                                             source="printed_context")])), TEXT)
        assert got["n_run"] == 0
        assert "percentage_is_weighted" in {row["reason"] for r in got["refused"]
                                            for row in r["reasons"]}


# --------------------------------------------------------------------------
# 4. THE ALTERNATIVE-BASE PREMISE IS NOT IN THIS MODULE
# --------------------------------------------------------------------------

REGISTER = ("The parish register held 480 allotment tenants, of whom 112 kept "
            "a plot at Marlow.")


class TestTheBaseCeilingIsNotRead:
    def test_base_is_not_a_premise_a_model_may_judge(self):
        assert "base" not in PR.PREMISES
        assert set(PR.QUESTIONS) == set(PR.PREMISES)
        assert PR.LICENCE_PREMISES | PR.REFUSAL_PREMISES == set(PR.PREMISES)
        assert not (PR.LICENCE_PREMISES & PR.REFUSAL_PREMISES)

    def test_no_candidate_is_ever_generated_for_it(self):
        acc = account(variables=[tidy_var(), shed_var()],
                      values=tidy_values() + pct_values()[1:])
        got = PR.candidates(acc, TEXT + "\n" + REGISTER + "\n")
        assert got and {c["premise"] for c in got} <= set(PR.PREMISES)

    def test_the_ceiling_is_still_the_regex_readers(self):
        text = TEXT + "\n" + REGISTER + "\n"
        assert 480 in premises.printed_subject_counts(text)
        assert premises.paper_max_n([], text) == 480
        assert premises.other_bases_that_fit(12, 32, 0, 30, 480) == [37, 38]

    def test_a_verdict_naming_it_is_ignored(self):
        """A block naming a premise this module does not read moves nothing --
        the membership test is the gate, and it is an allowlist."""
        block = reading(verdict("cand:1", "base", True),
                        candidates=[cand("cand:1", "step", TIDY_G,
                                         variable_id="var:tidy")])
        block["candidates"][0]["premise"] = "base"
        assert PR.index(block, premises.Haystack(TEXT), {})["n_verdicts"] == 0


# --------------------------------------------------------------------------
# 5. AN UNLOCATABLE PASSAGE IS NEVER EVIDENCE
# --------------------------------------------------------------------------


class TestAnUnlocatablePassageIsNeverEvidence:
    def test_a_candidate_that_does_not_locate_is_dropped_before_the_call(
            self, tmp_path, monkeypatch):
        called = {}

        def fake_run_pass(name, prompt, out_dir, **kw):
            called["prompt"] = prompt
            return {"data": {"verdicts": [{"candidate": 1, "establishes": True,
                                           "reason": "yes"}]},
                    "problems": [], "meta": {"cost_usd": 0.01}}

        monkeypatch.setattr(PR._passes, "run_pass", fake_run_pass)
        cands = [cand("cand:1", "step", TIDY_G, variable_id="var:tidy"),
                 cand("cand:2", "step", "a sentence this paper does not contain",
                      variable_id="var:tidy")]
        cands[1]["quote_located"] = False
        cands[1]["quote_not_located_because"] = "not a contiguous span"
        got = PR.read(account(variables=[tidy_var()], values=tidy_values()),
                      TEXT, tmp_path, only=cands)
        assert (got["n_candidates"], got["n_asked"], got["n_dropped"]) == (2, 1, 1)
        assert "a sentence this paper does not contain" not in called["prompt"]
        assert any("dropped before the call" in p for p in got["problems"])
        assert [v["candidate_id"] for v in got["verdicts"]] == ["cand:1"]

    def test_a_forged_block_cannot_offer_a_passage_the_paper_lacks(self):
        """RE-LOCATED AT STAMP TIME, against the text the stamp is running on.
        The account is a file anyone can edit; the only passages a block can
        ever offer are real sentences of the served document."""
        forged = "Tidiness was rated in whole points from 0 to 8 by the warden."
        acc = stamped(account(
            variables=[tidy_var(gquote=TIDY_WEAK)], values=tidy_values(),
            reading=reading(verdict("cand:1", "step", True),
                            candidates=[cand("cand:1", "step", forged,
                                             variable_id="var:tidy")])))
        g = var_of(acc)["granularity"]["verification"]
        assert g["discreteness_source"] == premises.ASSUMED_DISCRETENESS
        idx = PR.index(acc["premise_reading"], premises.Haystack(TEXT), {})
        assert idx["n_quote_refused"] == 1 and idx["step"] == {}

    def test_a_refusal_candidate_is_asked_although_its_evidence_is_furniture(
            self, tmp_path, monkeypatch):
        """A COLUMN BAND AND A CAPTION ARE NOT IN THE BODY TEXT, and requiring
        them to locate would silently drop every estimator candidate there is.
        A verdict on one can only ever remove a check, so it is asked."""
        called = {}

        def fake_run_pass(name, prompt, out_dir, **kw):
            called["prompt"] = prompt
            return {"data": {"verdicts": [{"candidate": 1, "establishes": True,
                                           "reason": "weighted"}]},
                    "problems": [], "meta": {"cost_usd": 0.01}}

        monkeypatch.setattr(PR._passes, "run_pass", fake_run_pass)
        acc = account(variables=[shed_var()], values=pct_values(), caption=CALIBRATED)
        cands = PR.candidates(acc, TEXT)
        est = [c for c in cands if c["premise"] == "estimator"]
        assert est and est[0]["quote_located"] is False and est[0]["askable"] is True
        got = PR.read(acc, TEXT, tmp_path, only=est[:1])
        assert got["n_asked"] == 1 and CALIBRATED in called["prompt"]

    def test_a_long_sentence_is_cut_at_a_word_boundary(self):
        """A HARD SLICE BREAKS LOCATION, which is the one property a candidate
        must have: `Haystack.locate` refuses a span that begins or ends inside a
        word, and three real passages of a reference paper were dropped for it."""
        long_sentence = ("Tidiness was rated in whole points " + "and again " * 90
                         + "by the warden.")
        text = TEXT + "\n" + long_sentence + "\n"
        clipped = PR._clip(long_sentence)
        assert len(clipped) <= PR.MAX_QUOTE_CHARS and not clipped.endswith(" ")
        assert premises.Haystack(text).locate(clipped)["located"]


# --------------------------------------------------------------------------
# 6. THE PRE-FILTER OFFERS EVERY CANDIDATE, NOT ONLY THE STAMPED ONE
# --------------------------------------------------------------------------


class TestThePreFilter:
    def test_the_accounts_own_quote_comes_first(self):
        cands = PR.candidates(account(variables=[tidy_var()],
                                      values=tidy_values()), TEXT)
        steps = [c for c in cands if c["premise"] == "step"]
        assert steps[0]["source"] == "account_quote" and steps[0]["quote"] == TIDY_G

    def test_a_second_sentence_about_the_same_variable_is_surfaced(self):
        """THE NC7 FIX, AS A PROPERTY OF THE PRE-FILTER."""
        cands = PR.candidates(account(variables=[tidy_var(gquote=TIDY_WEAK)],
                                      values=tidy_values()), TEXT)
        steps = [c for c in cands if c["premise"] == "step"]
        assert steps[0]["quote"] == TIDY_WEAK and steps[0]["source"] == "account_quote"
        assert TIDY_G in [c["quote"] for c in steps[1:]]

    def test_a_sentence_about_another_variable_is_not_surfaced_for_this_one(self):
        cands = PR.candidates(account(variables=[tidy_var()],
                                      values=tidy_values()), TEXT)
        assert HARVEST_SENT not in [c["quote"] for c in cands]

    def test_a_bound_candidate_must_print_the_bound(self):
        cands = PR.candidates(account(variables=[tidy_var()],
                                      values=tidy_values()), TEXT)
        bounds = [c for c in cands if c["premise"] == "bound"]
        assert bounds
        for c in bounds:
            assert premises.numeral_in(c["quote"], 0) or premises.numeral_in(c["quote"], 8)

    def test_a_variable_with_no_declared_premise_is_not_asked_about(self):
        acc = account(variables=[var("var:harvest", "Weekly harvest", "continuous")],
                      values=[prose("val:n", "n", str(N), N_Q)])
        assert PR.candidates(acc, TEXT) == []

    def test_every_candidate_carries_its_question_and_a_stable_id(self):
        acc = account(variables=[tidy_var()], values=tidy_values())
        cands = PR.candidates(acc, TEXT)
        assert [c["id"] for c in cands] == [f"cand:{i}"
                                            for i in range(1, len(cands) + 1)]
        assert all(c["question"] == PR.QUESTIONS[c["premise"]] for c in cands)
        again = PR.candidates(account(variables=[tidy_var()],
                                      values=tidy_values()), TEXT)
        assert [c["quote"] for c in again] == [c["quote"] for c in cands]

    def test_the_printed_context_carries_the_column_the_number_sits_under(self):
        """THE UNIT/SCALE HALF OF THE STEP QUESTION. A table cell has no
        sentence, and `Total steps, thousands` over it is the whole evidence
        that the printed number is not the recorded one."""
        cands = PR.candidates(account(variables=[tidy_var()],
                                      values=tidy_values()), TEXT)
        steps = [c for c in cands if c["premise"] == "step"]
        assert "Mean (SD)" in steps[0]["context"]
        assert "Table 1. The Marlow plots." in steps[0]["context"]


# --------------------------------------------------------------------------
# 7. THE CALL, AND THE JOIN BACK
# --------------------------------------------------------------------------


class TestTheCall:
    def _fake(self, verdicts, seen):
        """The model boundary, with `run_pass`'s own side effects on disk --
        the prompt and the parsed output beside each other, which is what the
        reuse guard reads."""
        def fake_run_pass(name, prompt, out_dir, **kw):
            seen.append((name, prompt))
            out = Path(out_dir)
            out.mkdir(parents=True, exist_ok=True)
            data = {"verdicts": verdicts}
            (out / f"{name}.prompt.md").write_text(prompt, encoding="utf-8")
            (out / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")
            (out / f"{name}.meta.json").write_text(
                json.dumps({"cost_usd": 0.02, "problems": []}), encoding="utf-8")
            return {"data": data, "problems": [], "meta": {"cost_usd": 0.02}}
        return fake_run_pass

    def test_one_batched_call_carries_every_candidate(self, tmp_path, monkeypatch):
        seen = []
        acc = account(variables=[tidy_var()], values=tidy_values())
        cands = PR.candidates(acc, TEXT)
        vs = [{"candidate": i, "establishes": True, "reason": "r"}
              for i in range(1, len(cands) + 1)]
        monkeypatch.setattr(PR._passes, "run_pass", self._fake(vs, seen))
        got = PR.read(acc, TEXT, tmp_path)
        assert got["n_calls"] == 1 and len(seen) == 1
        assert len(got["verdicts"]) == len(cands)
        assert got["cost_usd"] == 0.02
        on_disk = json.loads((tmp_path / "premise_reading.json").read_text())
        assert on_disk["n_calls"] == 1 and on_disk["prompt_version"] == PR.PROMPT_VERSION

    def test_a_verdict_addressing_nothing_asked_about_is_dropped(
            self, tmp_path, monkeypatch):
        seen = []
        vs = [{"candidate": 7, "establishes": True, "reason": "r"}]
        monkeypatch.setattr(PR._passes, "run_pass", self._fake(vs, seen))
        cands = [cand("cand:1", "step", TIDY_G, variable_id="var:tidy")]
        got = PR.read(account(), TEXT, tmp_path, only=cands)
        assert got["verdicts"] == []
        assert any("not an addressing" in p for p in got["problems"])

    def test_a_reply_that_skips_candidates_still_addresses_the_rest(
            self, tmp_path, monkeypatch):
        """MEASURED ON THE LIVE 37679 CALL: the model answered 1-6, skipped
        5, and answered 12. Read positionally that loses six answers and calls
        five gaps six; read by its own numbers it is what it says."""
        seen = []
        cands = [cand(f"cand:{i}", "step", TIDY_G, variable_id="var:tidy")
                 for i in range(1, 13)]
        vs = [{"candidate": i, "establishes": i == 12, "reason": "r"}
              for i in (1, 2, 3, 4, 5, 6, 12)]
        monkeypatch.setattr(PR._passes, "run_pass", self._fake(vs, seen))
        got = PR.read(account(), TEXT, tmp_path, only=cands)
        assert [v["candidate_id"] for v in got["verdicts"]] == [
            "cand:1", "cand:2", "cand:3", "cand:4", "cand:5", "cand:6", "cand:12"]
        assert sum(1 for p in got["problems"] if "no verdict returned" in p) == 5

    def test_a_reply_whose_numbering_has_slipped_is_joined_by_position(
            self, tmp_path, monkeypatch):
        """THE DANGEROUS SHAPE, and why the numbers are not simply believed: a
        reply numbered 2..n+1 would address every verdict to the wrong
        candidate. Position catches it and every row is dropped."""
        seen = []
        cands = [cand(f"cand:{i}", "step", TIDY_G, variable_id="var:tidy")
                 for i in range(1, 5)]
        vs = [{"candidate": i + 1, "establishes": True, "reason": "r"}
              for i in range(1, 5)]
        monkeypatch.setattr(PR._passes, "run_pass", self._fake(vs, seen))
        got = PR.read(account(), TEXT, tmp_path, only=cands)
        assert got["verdicts"] == []
        assert any("position is the join" in p for p in got["problems"])

    def test_a_reply_that_repeats_a_number_is_joined_by_position(
            self, tmp_path, monkeypatch):
        seen = []
        cands = [cand(f"cand:{i}", "step", TIDY_G, variable_id="var:tidy")
                 for i in range(1, 4)]
        vs = [{"candidate": 1, "establishes": True, "reason": "r"},
              {"candidate": 1, "establishes": False, "reason": "r"},
              {"candidate": 3, "establishes": True, "reason": "r"}]
        monkeypatch.setattr(PR._passes, "run_pass", self._fake(vs, seen))
        got = PR.read(account(), TEXT, tmp_path, only=cands)
        assert [v["candidate_id"] for v in got["verdicts"]] == ["cand:1", "cand:3"]
        assert any("not an addressing" in p for p in got["problems"])

    def test_a_short_reply_is_a_named_problem_not_a_silent_gap(
            self, tmp_path, monkeypatch):
        seen = []
        monkeypatch.setattr(PR._passes, "run_pass", self._fake([], seen))
        cands = [cand("cand:1", "step", TIDY_G, variable_id="var:tidy")]
        got = PR.read(account(), TEXT, tmp_path, only=cands)
        assert got["verdicts"] == []
        assert any("no verdict returned" in p for p in got["problems"])

    def test_the_batch_is_chunked_rather_than_truncated(self, tmp_path, monkeypatch):
        seen = []
        cands = [cand(f"cand:{i}", "step", TIDY_G, variable_id="var:tidy")
                 for i in range(1, PR.MAX_PER_CALL + 3)]
        vs = [{"candidate": i, "establishes": False, "reason": "r"}
              for i in range(1, PR.MAX_PER_CALL + 3)]
        monkeypatch.setattr(PR._passes, "run_pass", self._fake(vs, seen))
        got = PR.read(account(), TEXT, tmp_path, only=cands)
        assert got["n_calls"] == 2 and len(seen) == 2
        assert len(got["verdicts"]) == PR.MAX_PER_CALL + 2

    def test_load_and_attach_put_the_block_where_the_stamp_looks(
            self, tmp_path, monkeypatch):
        seen = []
        monkeypatch.setattr(PR._passes, "run_pass", self._fake(
            [{"candidate": 1, "establishes": False, "reason": "r"}], seen))
        acc = account(variables=[tidy_var()], values=tidy_values())
        (tmp_path / "account.json").write_text(json.dumps(acc), encoding="utf-8")
        PR.read(acc, TEXT, tmp_path,
                only=[cand("cand:1", "step", TIDY_G, variable_id="var:tidy",
                           source="account_quote")])
        assert PR.load(tmp_path)["prompt_version"] == PR.PROMPT_VERSION
        assert PR.attach(tmp_path) is True
        back = json.loads((tmp_path / "account.json").read_text(encoding="utf-8"))
        after = premises.stamp(back, TEXT)
        assert var_of(after)["granularity"]["verification"]["discreteness_source"] \
            == premises.ASSUMED_DISCRETENESS
        assert after["premise_reading_applied"]["n_verdicts"] == 1

    def test_a_reply_already_paid_for_is_reused(self, tmp_path, monkeypatch):
        seen = []
        vs = [{"candidate": 1, "establishes": True, "reason": "r"}]
        monkeypatch.setattr(PR._passes, "run_pass", self._fake(vs, seen))
        cands = [cand("cand:1", "step", TIDY_G, variable_id="var:tidy")]
        first = PR.read(account(), TEXT, tmp_path, only=cands)
        again = PR.read(account(), TEXT, tmp_path, only=cands)
        assert len(seen) == 1, "the second run paid for a call it already had"
        assert [v["establishes"] for v in again["verdicts"]] == [True]
        assert (first["cost_usd"], again["cost_usd"]) == (0.02, 0.0)

    def test_a_changed_candidate_set_pays_again(self, tmp_path, monkeypatch):
        """THE GUARD IS THE PROMPT'S OWN BYTES. The join is positional, so
        joining a saved reply to a different candidate set would address a
        verdict to a quantity nobody asked about."""
        seen = []
        vs = [{"candidate": 1, "establishes": True, "reason": "r"}]
        monkeypatch.setattr(PR._passes, "run_pass", self._fake(vs, seen))
        PR.read(account(), TEXT, tmp_path,
                only=[cand("cand:1", "step", TIDY_G, variable_id="var:tidy")])
        PR.read(account(), TEXT, tmp_path,
                only=[cand("cand:1", "bound", TIDY_B, variable_id="var:tidy")])
        assert len(seen) == 2

    def test_attach_says_no_where_there_is_nothing_to_attach(self, tmp_path):
        assert PR.attach(tmp_path) is False
        assert PR.load(tmp_path) is None


# --------------------------------------------------------------------------
# 8. THE PROMPT IS THE INSTRUMENT E1 MEASURED
# --------------------------------------------------------------------------


class TestThePromptIsTheValidatedOne:
    """A RATCHET, NOT A STYLE TEST. `37/37` is a claim about these bytes; an
    edit that reads as an improvement discards the measurement silently, and
    this is what makes it fail loudly instead."""

    def test_the_preamble_is_unchanged(self):
        assert PR.PREAMBLE.startswith(
            "You are judging, for each candidate below, whether one sentence "
            "taken from a research paper establishes a specific premise about a "
            "specific quantity.")
        for rule in ("Judge ONLY from what the quoted sentence says.",
                     "The sentence may be about a DIFFERENT variable",
                     "Do not invent or supply a number.",
                     "Answer true only if the sentence, read plainly, does "
                     "establish the premise for the stated target.",
                     "Candidates are independent."):
            assert rule in PR.PREAMBLE

    def test_the_three_measured_questions_are_unchanged(self):
        assert PR.QUESTIONS["bound"] == (
            "Does this sentence state the numeric range (lowest and highest "
            "possible value) of the target variable, as that variable is "
            "reported in this paper?")
        assert PR.QUESTIONS["step"] == (
            "Does this sentence establish that each subject's value of the "
            "target variable, in the unit and scale the number is PRINTED in, "
            "is a whole number (an integer)?")
        assert PR.QUESTIONS["correction"] == (
            "Does this correction notice say that the target number is the OLD, "
            "erroneous value the paper is withdrawing (as opposed to the "
            "corrected value that now stands)?")

    def test_the_reply_shape_is_the_one_that_was_scored(self):
        assert PR.SCHEMA["required"] == ["verdicts"]
        item = PR.SCHEMA["properties"]["verdicts"]["items"]
        assert item["required"] == ["candidate", "establishes", "reason"]
        assert item["additionalProperties"] is False

    def test_the_codestamp_names_this_module(self):
        """AN ACCOUNT READ WITH THIS PASS IS DECIDED BY THIS FILE, so the stamp
        that says which code built an account has to name it -- the same claim
        `test_scaffold_checks` makes for the bridge."""
        from metascience_agent.scaffold import codestamp
        assert "scaffold/premise_reading.py" in codestamp.MODULES
        assert codestamp.stamp()["modules"]["scaffold/premise_reading.py"]

    def test_an_item_reads_the_way_the_measured_one_did(self):
        got = PR.build_prompt([cand("cand:1", "step", TIDY_G,
                                    variable_id="var:tidy")])
        assert "--- CANDIDATE 1" in got
        assert "TARGET: the target" in got
        assert "SENTENCE(S) FROM THE PAPER:" in got
        assert "PREMISE QUESTION: " + PR.QUESTIONS["step"] in got
        assert "array of 1 objects" in got


# --------------------------------------------------------------------------
# 9. THE COST SIDE -- A READING THAT REFUSED EVERYTHING WOULD PASS EVERY TEST
#    ABOVE AND BE WORTHLESS
# --------------------------------------------------------------------------


def _doc(text: str) -> dict:
    nums = numerals.index(text, tables_available=False)
    for r in nums:
        r["role"] = "results"
    return {"text": text, "original_text": text, "source": {"text_sha256": "x"},
            "problems": [], "font_audit": {}, "repairs": {"n_repairs": 0},
            "sections": sections.map_sections(text), "tables": [], "figures": [],
            "supplements_referenced": [], "numerals": nums,
            "numeral_floor": numerals.tally(nums)}


class TestTheCostSide:
    def test_the_bridge_still_reaches_verdicts_under_a_reading(self):
        acc = account(
            variables=[tidy_var(gquote=TIDY_WEAK, bquote=TIDY_WEAK)],
            values=tidy_values(),
            reading=reading(verdict("cand:1", "step", True),
                            verdict("cand:2", "bound", True),
                            candidates=[
                                cand("cand:1", "step", TIDY_G,
                                     variable_id="var:tidy"),
                                cand("cand:2", "bound", TIDY_B,
                                     variable_id="var:tidy")]))
        got = checks.evaluate(acc, TEXT)
        assert got["n_run"] >= 3
        assert not [r for r in got["checks"] if r["severity"] in BAD]

    def test_the_same_account_without_the_reading_runs_fewer(self):
        bare = account(variables=[tidy_var(gquote=TIDY_WEAK, bquote=TIDY_WEAK)],
                       values=tidy_values())
        assert checks.evaluate(bare, TEXT)["n_run"] == 0

    def test_assemble_carries_a_reading_into_the_stamp(self):
        block = reading(verdict("cand:1", "step", False),
                        candidates=[cand("cand:1", "step", TIDY_G,
                                         variable_id="var:tidy",
                                         source="account_quote")])
        p1 = {"studies": [{"id": "study:main", "label": "Marlow",
                           "design": "prospective_cohort",
                           "groups": [{"id": "grp:all", "label": "All plots",
                                       "n_printed": str(N), "n_quote": N_Q}],
                           "phases": []}]}
        p2 = {"variables": [tidy_var()]}
        acc = bind.assemble(_doc(TEXT), p1, p2, {}, premise_reading=block)
        assert acc["premise_reading"]["prompt_version"] == PR.PROMPT_VERSION
        got = {v["id"]: v for v in acc["variables"]}["var:tidy"]
        assert got["granularity"]["verification"]["model_reading"] is not None
        assert got["granularity"]["verification"]["discreteness_source"] \
            == premises.ASSUMED_DISCRETENESS

    def test_assemble_without_one_leaves_the_account_saying_so(self):
        p1 = {"studies": [{"id": "study:main", "label": "Marlow",
                           "design": "prospective_cohort",
                           "groups": [{"id": "grp:all", "label": "All plots",
                                       "n_printed": str(N), "n_quote": N_Q}],
                           "phases": []}]}
        acc = bind.assemble(_doc(TEXT), p1, {"variables": [tidy_var()]}, {})
        assert "premise_reading" not in acc
        got = {v["id"]: v for v in acc["variables"]}["var:tidy"]
        assert got["granularity"]["verification"]["discreteness_source"] \
            == premises.STATED_DISCRETENESS
