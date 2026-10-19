"""The admission decision, made once -- and the ratchet that keeps it once.

WHAT THIS FILE IS FOR. Six readers of the account's `values` table used to
decide independently whether a value was safe to use, from the same seven raw
fields, and they disagreed: three `quote_verified` admission rules under
`scaffold/` alone, two `CORROBORATED` constants, two quote locators. Wave 7b
moved the judgement into `scaffold/premises.py` and made every reader a lookup.
Two things have to hold for that to stay true, and both are tested here: the
stamp says everything a reader needs (so nobody has to re-derive), and no other
module under `scaffold/` may re-derive it anyway (the ratchet, in the mechanism
of `test_accusatory_vocabulary.TestNoModuleRedefinesIt`).

THE ADVERSARIAL FIXTURES ARE THE OTHER HALF OF THIS SUITE. Two rounds of them
(89 assertions and 43) live outside the repo and are the reason most of the
rules below have the shape they do; `tests/test_scaffold_checks_adversarial.py`
carries the ones that were reproduced in-tree.
"""

from __future__ import annotations

import ast
import copy
import json
import pathlib
import re

import pytest

from forensic_metascience_ai_toolkit.scaffold import bind, checks, coverage, premises

SRC = pathlib.Path(__file__).resolve().parent.parent / "src" / "forensic_metascience_ai_toolkit"
SCAFFOLD = SRC / "scaffold"

# --------------------------------------------------------------------------
# A paper whose premises are known by construction
# --------------------------------------------------------------------------

TEXT = """## METHODS

Mood was rated on a 1 to 7 point scale and was scored in whole points.
EBP reach was the sum reach of all EBPs supported by a coalition.
Weight was measured in kilograms to one decimal place on a calibrated scale.
Thirty adults completed the study; the analysed sample was n = 30.

## RESULTS

Twenty-six (86.7%) of the 30 participants reported at least one fall.
"""


def _var(vid, kind, *, name, source="not_stated", lower=None, upper=None,
         bquote=None, step=None, gquote=None):
    return {"id": vid, "name": name, "kind": kind, "printed_as": [],
            "bounds": {"source": source, "lower": lower, "upper": upper, "quote": bquote},
            "granularity": {"per_subject_step": step, "quote": gquote}}


def _cell(vid, statistic, printed, *, row, variable_id=None, id_check="agrees",
          col_label="All participants", source="table", quote_verified="cell"):
    got = premises.read_plain(printed)
    return {"id": vid, "statistic": statistic, "printed": printed,
            "numeric": (got or {}).get("value"), "decimals": (got or {}).get("decimals", 0),
            "printed_form": "plain", "variable_id": variable_id, "id_check": id_check,
            "statistic_disputed": False,
            "coordinate": {"study_id": "study:main", "group_id": "grp:all",
                           "phase_id": None},
            "applies_to_all_groups": False, "source": source,
            "location": {"kind": "table_cell", "table_id": "table:1", "row": row,
                         "col": 1, "row_label": "", "col_label": col_label},
            "quote": str(printed), "quote_verified": quote_verified}


def account() -> dict:
    """Honest by construction, and every premise in it is one a reader can
    check against the text above."""
    return {
        "schema_version": "scaffold_account/1",
        "paper": {"doi": "10.0000/premises", "title": "Premises"},
        "studies": [{"id": "study:main", "label": "Main",
                     "groups": [{"id": "grp:all", "label": "All participants (n = 30)",
                                 "n": 30, "n_source": "label"}]}],
        "variables": [
            _var("var:mood", "integer_score", name="Mood score", source="stated",
                 lower=1, upper=7, bquote="Mood was rated on a 1 to 7 point scale",
                 step=1, gquote="was scored in whole points"),
            # THE KIND-NECESSARY CASE, and it is ajcp's `var:ebp_reach` in
            # miniature: a `count` whose only granularity sentence describes what
            # the variable IS rather than what its step is.
            _var("var:reach", "count", name="EBP reach", source="definitional",
                 lower=0, upper=None,
                 bquote="EBP reach was the sum reach of all EBPs supported by a coalition.",
                 step=1,
                 gquote="EBP reach was the sum reach of all EBPs supported by a coalition."),
            _var("var:weight", "continuous", name="Weight (kg)"),
        ],
        "values": [
            _cell("val:n", "n", "30", row=1),
            _cell("val:mood:mean", "mean", "3.50", row=2, variable_id="var:mood"),
            _cell("val:mood:sd", "sd", "1.20", row=2, variable_id="var:mood"),
            _cell("val:reach:mean", "mean", "223.5", row=3, variable_id="var:reach"),
            _cell("val:w:mean", "mean", "71.4", row=4, variable_id="var:weight"),
        ],
        "comparisons": [], "claims": [],
        "statistical_analysis": {"alpha_declared": 0.05},
    }


@pytest.fixture()
def stamped():
    return premises.stamp(account(), TEXT)


# --------------------------------------------------------------------------
# The stamp itself
# --------------------------------------------------------------------------


class TestEveryRowCarriesItsPremise:
    def test_every_value_has_the_six_fields(self, stamped):
        assert stamped["values"]
        for v in stamped["values"]:
            p = v["premise"]
            assert set(p) >= {"provenance", "binding", "literal", "descriptive",
                              "disputed", "reasons"}
            assert p["binding"] in premises.BINDINGS
            assert p["provenance"] in (None, "printed_table", "printed_text")

    def test_every_n_row_carries_an_n_premise_and_no_other_row_does(self, stamped):
        ns = [v for v in stamped["values"] if v["statistic"] == "n"]
        assert ns
        for v in stamped["values"]:
            if v["statistic"] == "n":
                np = v["n_premise"]
                assert set(np) >= {"provenance", "binding", "positive", "source"}
                assert np["source"] in premises.N_SOURCES
            else:
                assert "n_premise" not in v

    def test_every_variable_carries_both_verifications(self, stamped):
        for var in stamped["variables"]:
            b = var["bounds"]["verification"]
            g = var["granularity"]["verification"]
            assert b["bound_source"] in ("stated", "logically_necessary", "assumed")
            assert g["discreteness_source"] in ("stated", "logically_necessary", "assumed")

    def test_every_reason_is_in_the_closed_vocabulary(self, stamped):
        for v in stamped["values"]:
            for row in v["premise"]["reasons"]:
                assert row["reason"] in premises.REASONS
        for var in stamped["variables"]:
            for field in ("bounds", "granularity"):
                for row in var[field]["verification"]["reasons"]:
                    assert row["reason"] in premises.REASONS

    def test_the_two_halves_of_the_vocabulary_do_not_overlap(self):
        """`checks.REASONS` is `premises.REASONS` merged with the bridge's own.
        An overlap would be the same defect this wave exists to remove, one
        level up: two definitions of one word, and the merge silently picking."""
        assert not (set(premises.REASONS) & set(checks.BRIDGE_REASONS))
        assert set(checks.REASONS) == set(premises.REASONS) | set(checks.BRIDGE_REASONS)

    def test_stamping_does_not_touch_the_account_it_was_given(self):
        acc = account()
        before = json.dumps(acc, sort_keys=True)
        premises.stamp(acc, TEXT)
        premises.stamp(acc, TEXT)
        assert json.dumps(acc, sort_keys=True) == before

    def test_stamping_twice_in_place_is_the_same_stamp(self):
        acc = premises.stamp(account(), TEXT, inplace=True)
        once = json.dumps(acc, sort_keys=True)
        premises.stamp(acc, TEXT, inplace=True)
        assert json.dumps(acc, sort_keys=True) == once


class TestNoReaderCanBeHandedAnUnstampedValue:
    def test_is_stamped_is_all_and_not_any(self):
        """A partially stamped account is the shape that fails open: one reader
        stamps what it touched, the next finds a stamp on the first row and
        concludes the account is done."""
        acc = premises.stamp(account(), TEXT)
        assert premises.is_stamped(acc)
        del acc["values"][2]["premise"]
        assert not premises.is_stamped(acc)

    def test_the_bridges_index_stamps_whatever_it_is_handed(self):
        """`candidates` and `translate` are exported, and a premise reader given
        an unstamped value would read `None` and admit it."""
        raw = account()
        cands, idx = checks.candidates(raw, TEXT)
        assert cands
        assert all(isinstance(v.get("premise"), dict) for v in idx.values)
        assert all("premise" not in v for v in raw["values"]), "it wrote back"


class TestTheKindNecessaryPaths:
    """The two places a premise is licensed by the declared KIND rather than by
    a sentence -- and the one place that licence is refused."""

    def test_a_count_licenses_its_own_step_without_a_granularity_sentence(self, stamped):
        """ajcp's `var:ebp_reach` in miniature: the only sentence quoted for the
        step says what the variable IS. A count moves in whole units whatever
        any sentence says, and the token is the tools' own
        `logically_necessary`, which licenses exactly what `stated` does."""
        from forensic_metascience_ai_toolkit.tools.grim import HARD_DISCRETENESS_SOURCES
        g = next(v for v in stamped["variables"]
                 if v["id"] == "var:reach")["granularity"]["verification"]
        assert g["kind_makes_it_necessary"] is True
        assert g["discreteness_source"] == premises.NECESSARY_DISCRETENESS
        assert g["discreteness_source"] in HARD_DISCRETENESS_SOURCES
        assert not g["reasons"]

    def test_the_recovered_call_actually_runs(self):
        """The coverage this recovers, end to end: the same variable is checked
        rather than refused, and the honest mean clears."""
        got = checks.evaluate(account(), TEXT)
        r = next(r for r in got["checks"] if r["check_id"] == "chk:grim:val:reach:mean")
        assert r["args"]["discreteness_source"] == premises.NECESSARY_DISCRETENESS
        assert r["severity"] in ("consistent", "indeterminate")

    def test_an_integer_score_is_not_kind_necessary(self, stamped):
        """`integer_score` is the READING's word for what the numbers look like,
        not a claim the paper is shown to make -- and round 2 built its whole
        first cluster out of a continuous measurement typed `integer_score`."""
        g = next(v for v in stamped["variables"]
                 if v["id"] == "var:mood")["granularity"]["verification"]
        assert g["kind_makes_it_necessary"] is False
        assert g["discreteness_source"] == premises.STATED_DISCRETENESS

    def test_a_kind_its_own_values_contradict_licenses_nothing(self):
        """A bound derived from the KIND is a bound derived from the reading. It
        stands where nothing disputes the kind and falls where the paper's own
        printed numbers do: a mean of 2.40 on a variable typed `binary` says the
        kind is wrong, and a 0-1 ceiling taken from it accuses an honest paper
        of the reading's error."""
        acc = account()
        v = next(x for x in acc["variables"] if x["id"] == "var:reach")
        v["kind"] = "binary"
        v["bounds"] = {"source": "definitional", "lower": 0, "upper": 1,
                       "quote": "EBP reach was the sum reach of all EBPs supported "
                                "by a coalition."}
        got = premises.stamp(acc, TEXT)
        b = next(x for x in got["variables"]
                 if x["id"] == "var:reach")["bounds"]["verification"]
        assert b["kind_contradicted_by"] == ["val:reach:mean"]
        assert b["lower_passed"] is None and b["upper_passed"] is None
        assert b["bound_source"] == "assumed"


class TestAQuoteIsAboutSomething:
    def test_the_papers_own_sentence_anchors_by_its_content_words(self, stamped):
        """`was scored in whole points` names no variable at all; the SENTENCE
        it was cut from names Mood, which is why the attribution test reads the
        sentence and not the fragment."""
        g = next(v for v in stamped["variables"]
                 if v["id"] == "var:mood")["granularity"]["verification"]
        assert g["quote_about_this_variable"] is True
        assert "Mood was rated" in g["quote_sentence"]

    @pytest.mark.parametrize("quote,why", [
        ("was scored in", "under the fragment floor"),
        ("scored in whol", "twelve characters ending inside a word"),
        ("EBP reach was the sum reach", "a sentence about a different variable"),
    ])
    def test_a_quote_that_is_not_about_this_variable_licenses_no_step(self, quote, why):
        acc = account()
        v = next(x for x in acc["variables"] if x["id"] == "var:weight")
        v["kind"] = "integer_score"
        v["granularity"] = {"per_subject_step": 1, "quote": quote}
        got = premises.stamp(acc, TEXT)
        g = next(x for x in got["variables"]
                 if x["id"] == "var:weight")["granularity"]["verification"]
        assert g["discreteness_source"] == premises.ASSUMED_DISCRETENESS, why
        assert g["reasons"] and g["reasons"][0]["reason"] == "discreteness_assumed"

    def test_a_bound_needs_its_own_numeral_in_a_sentence_about_this_variable(self):
        acc = account()
        v = next(x for x in acc["variables"] if x["id"] == "var:weight")
        v["bounds"] = {"source": "stated", "lower": 1, "upper": 7,
                       "quote": "1 to 7 point"}
        got = premises.stamp(acc, TEXT)
        b = next(x for x in got["variables"]
                 if x["id"] == "var:weight")["bounds"]["verification"]
        assert b["lower_passed"] is None and b["upper_passed"] is None
        assert b["reasons"][0]["reason"] == "bound_quote_does_not_state_it"


class TestTheModelOutputChannelsAreStructuralNotStringy:
    @pytest.mark.parametrize("label", ["HR (SE)", "aHR (95% CI)", "Adjusted HR",
                                       "RR (SE)", "B (SD)", "β (SD)", "B"])
    def test_a_whole_header_that_is_an_estimate_symbol(self, label):
        """`prepass.reports_model_output` spells the words out (`hazard ratio`,
        `beta`) and misses every symbol form. The whole-header test asks what
        the column IS rather than which substring it contains."""
        acc = account()
        acc["values"].append(_cell("val:hr", "mean", "8.57", row=9,
                                   variable_id="var:mood", col_label=label))
        got = premises.stamp(acc, TEXT)
        v = next(x for x in got["values"] if x["id"] == "val:hr")
        assert v["premise"]["descriptive"]["reports_model_output"], label
        assert "reports_model_output" in {r["reason"] for r in v["premise"]["reasons"]}

    @pytest.mark.parametrize("label", ["All participants", "Mean (SD)", "n (%)",
                                       "Intervention", "Total", "Wave 1"])
    def test_an_ordinary_descriptive_header_is_untouched(self, label):
        acc = account()
        acc["values"].append(_cell("val:d", "mean", "8.57", row=9,
                                   variable_id="var:mood", col_label=label))
        got = premises.stamp(acc, TEXT)
        v = next(x for x in got["values"] if x["id"] == "val:d")
        assert not v["premise"]["descriptive"]["reports_model_output"], label

    def test_a_prose_estimate_has_no_column_and_is_caught_anyway(self):
        """The guard reads a column band and a caption; a value reported in
        prose has neither, so the string rule is asked a question with no
        evidence. The paper's own `B = ... SE = ... p = ...` notation is the
        evidence."""
        quote = "Mood predicted falls (B = 8.57, SE = 3.03, p = .005)."
        acc = account()
        acc["values"].append({
            "id": "val:p:b", "statistic": "mean", "printed": "8.57", "numeric": 8.57,
            "decimals": 2, "printed_form": "plain", "variable_id": "var:mood",
            "id_check": "agrees", "statistic_disputed": False,
            "coordinate": {"study_id": "study:main", "group_id": "grp:all",
                           "phase_id": None},
            "applies_to_all_groups": False, "source": "prose",
            "location": {"kind": "results", "offset": 0, "end": len(quote)},
            "quote": quote, "quote_verified": "verbatim", "printed_in_quote": True})
        got = premises.stamp(acc, TEXT + "\n" + quote + "\n")
        v = next(x for x in got["values"] if x["id"] == "val:p:b")
        assert v["premise"]["descriptive"]["reports_model_output"]

    def test_a_neighbour_the_reading_typed_as_an_estimate(self):
        acc = account()
        acc["values"] += [
            _cell("val:c:b", "coefficient", "8.57", row=9, variable_id="var:mood"),
            _cell("val:c:sd", "sd", "3.03", row=9, variable_id="var:mood"),
        ]
        got = premises.stamp(acc, TEXT)
        v = next(x for x in got["values"] if x["id"] == "val:c:sd")
        assert v["premise"]["descriptive"]["reports_model_output"]

    def test_the_repos_own_rule_is_asked_first_and_still_answers(self):
        from forensic_metascience_ai_toolkit import prepass
        assert prepass.reports_model_output("Coefficient (SE)", None)
        acc = account()
        acc["values"].append(_cell("val:x", "mean", "8.57", row=9,
                                   variable_id="var:mood", col_label="Coefficient (SE)"))
        got = premises.stamp(acc, TEXT)
        v = next(x for x in got["values"] if x["id"] == "val:x")
        why = v["premise"]["descriptive"]["reports_model_output"]
        assert why == prepass.reports_model_output("Coefficient (SE)", None)


class TestTheDenominatorPremise:
    def test_a_non_positive_n_is_never_usable(self):
        for printed in ("0", "-30"):
            acc = account()
            next(v for v in acc["values"] if v["id"] == "val:n")["printed"] = printed
            got = premises.stamp(acc, TEXT)
            np = next(v for v in got["values"] if v["id"] == "val:n")["n_premise"]
            assert np["positive"] is False and np["usable"] is False, printed

    def test_a_lone_uncorroborated_n_is_not_a_denominator(self):
        """Round 2's case: the only `statistic: n` row at a coordinate printed
        57 -- a count of falls among 30 people -- and every check in the run
        divided by it. Nothing in the row distinguishes a count of EVENTS from a
        count of SUBJECTS, so a second witness is required."""
        acc = account()
        acc["studies"][0]["groups"][0] = {"id": "grp:all", "label": "All participants",
                                          "n": None, "n_source": None}
        next(v for v in acc["values"] if v["id"] == "val:n")["printed"] = "57"
        got = checks.evaluate(acc, TEXT)
        assert got["n_run"] == 0
        assert "n_not_corroborated" in {r["reason"] for r in got["refused"]}

    def test_the_group_label_is_a_witness_and_the_rows_own_quote_is_not(self):
        """ROUND 3 WITHDREW THE FOURTH WITNESS, and this test is the record of
        why. It was the row's own quote printing `n = <that integer>`, admitted
        on the argument that the notation is the paper's own mark for a sample
        size. It is not: `Adverse events were recorded during the trial
        (n = 18).` is ordinary published prose, and it made an EVENT COUNT the
        denominator of `9 (30.0%)` of thirty participants -- the exact confusion
        the corroboration test exists to prevent, walking in through one of its
        own witnesses. A row cannot corroborate itself.

        The fact is still STAMPED (`n_premise.states_n`), because a reader of
        the record wants it; it is no longer evidence.
        """
        acc = account()
        acc["studies"][0]["groups"][0]["n"] = None
        n = next(v for v in acc["values"] if v["id"] == "val:n")
        n["quote"], n["source"], n["quote_verified"] = "n = 30", "prose", "verbatim"
        n["printed_in_quote"] = True
        n["location"] = {"kind": "results", "offset": 0, "end": 6}
        got = checks.evaluate(acc, TEXT)
        r = next(r for r in got["checks"] if r["check_id"] == "chk:grim:val:mood:mean")
        assert [c["by"] for c in r["premises"]["n"]["corroborated_by"]] == ["group_label"]
        stamped_n = next(v for v in premises.stamp(acc, TEXT)["values"]
                         if v["id"] == "val:n")
        assert stamped_n["n_premise"]["states_n"] is True

    def test_a_lone_n_in_the_papers_own_notation_is_not_corroborated(self):
        """The withdrawal, from the other side: strip every OTHER witness and
        the `n = 30` in the row's own sentence supports nothing."""
        acc = account()
        acc["studies"][0]["groups"][0] = {"id": "grp:all", "label": "All participants",
                                          "n": None, "n_source": None}
        n = next(v for v in acc["values"] if v["id"] == "val:n")
        n["quote"], n["source"], n["quote_verified"] = "n = 30", "prose", "verbatim"
        n["printed_in_quote"] = True
        n["location"] = {"kind": "results", "offset": 0, "end": 6}
        got = checks.evaluate(acc, TEXT)
        assert got["n_run"] == 0
        assert "n_not_corroborated" in {r["reason"] for r in got["refused"]}

    def test_the_states_n_probe_reads_a_sentence_final_full_stop(self):
        """The lookahead was `(?![\\d.])`, which rejected `n = 40.` at the end of
        a sentence and admitted `(n = 18).` -- the wrong one of the two. A digit
        may not follow, and a decimal point may not introduce more digits; a
        full stop is just a full stop."""
        def _states(quote, printed="40"):
            v = {"id": "v", "statistic": "n", "printed": printed, "quote": quote,
                 "source": "prose", "quote_verified": "verbatim",
                 "printed_in_quote": True, "id_check": None}
            return premises.n_premise(v, premises.value_premise(v, None, {}, {}))["states_n"]
        assert _states("the enrolled sample was n = 40.") is True
        assert _states("the enrolled sample was n = 40 in total") is True
        assert _states("the enrolled sample was n = 400") is False
        assert _states("the enrolled sample was n = 40.5") is False

    def test_a_study_level_n_is_not_an_arms_denominator(self):
        acc = account()
        acc["studies"][0]["groups"] = [
            {"id": "grp:a", "label": "Intervention", "n": None, "n_source": None},
            {"id": "grp:b", "label": "Control", "n": None, "n_source": None}]
        for v in acc["values"]:
            v["coordinate"]["group_id"] = "grp:a"
        n = next(v for v in acc["values"] if v["id"] == "val:n")
        n["coordinate"]["group_id"] = None
        n["applies_to_all_groups"] = True
        got = checks.evaluate(acc, TEXT)
        assert "study_n_over_several_arms" in {r["reason"] for r in got["refused"]}
        assert got["n_run"] == 0


class TestTheSpriteCeiling:
    def test_a_denominator_above_the_ceiling_refuses_by_name(self):
        """MEASURED (round 2's own probe): one `sprite_reconstruct` call at
        n = 5,000 costs 1.9 s, at n = 50,000 costs 110 s, and at n = 5,000,000
        does not return. The per-candidate try/except catches exceptions, not
        seconds, so an n the account got wrong stalls the run instead of failing
        it. The other families are untouched: this is a fact about the tool."""
        acc = account()
        acc["studies"][0]["groups"][0]["n"] = 50000
        next(v for v in acc["values"] if v["id"] == "val:n")["printed"] = "50000"
        got = checks.evaluate(acc, TEXT)
        row = next(r for r in got["refused"]
                   if r["check_id"] == "chk:sprite:val:mood:mean")
        assert row["reason"] == "n_too_large_for_sprite"
        assert str(checks.SPRITE_MAX_N) in row["reasons"][0]["detail"]
        assert any(r["check_id"] == "chk:grim:val:mood:mean" for r in got["checks"])


class TestPipelineOnly:
    def test_the_model_may_not_author_its_own_premise(self):
        """`anatomy.PIPELINE_ONLY_FIELDS` strips `provenance_verdict` for the
        same reason: a verdict about whether the model's own quote is real
        cannot be authored by the model."""
        payload = {"variables": [{"id": "var:x", "premise": {"provenance": "printed_table"},
                                  "bounds": {"source": "stated",
                                             "verification": {"bound_source": "stated"}}}],
                   "prose_values": [{"id": "val:x", "n_premise": {"usable": True}}]}
        n = premises.strip_pipeline_only(payload)
        assert n == 3
        assert "premise" not in payload["variables"][0]
        assert "verification" not in payload["variables"][0]["bounds"]
        assert "n_premise" not in payload["prose_values"][0]

    def test_the_fields_match_the_names_the_stamp_writes(self):
        assert premises.PIPELINE_ONLY == {"premise", "n_premise", "verification"}

    def test_assembly_strips_a_forged_premise_and_says_so(self, tmp_path):
        from tests.test_scaffold_checks import W7_P1, W7_P2, W7_P3, _w7_doc
        p2 = copy.deepcopy(W7_P2)
        p2["variables"][0]["premise"] = {"provenance": "printed_table"}
        p2["variables"][0]["bounds"]["verification"] = {"bound_source": "stated",
                                                        "lower_passed": 1}
        acc = bind.assemble(_w7_doc(), copy.deepcopy(W7_P1), p2, copy.deepcopy(W7_P3))
        assert any("pipeline-only field" in p for p in acc["problems"])
        var = next(v for v in acc["variables"] if v["id"] == "var:wellbeing")
        assert "premise" not in var
        assert var["bounds"]["verification"]["lower_passed"] == 1  # the pipeline's own


class TestTheBridgeAddsNoPremiseJudgement:
    def test_every_premise_shaped_refusal_is_the_values_own(self):
        """CONSERVATION. Every refusal the bridge emits whose reason belongs to
        `premises.REASONS` must appear in the premise (or the n-premise) of the
        value it names -- otherwise the bridge is deciding something the stamp
        did not, which is the whole defect this wave removes."""
        acc = account()
        acc["values"] += [
            _cell("val:bad:mean", "mean", "Twenty-six", row=7, variable_id="var:mood"),
            _cell("val:dis:mean", "mean", "4.10", row=8, variable_id="var:mood",
                  id_check="disagrees"),
            _cell("val:mo:mean", "mean", "8.57", row=9, variable_id="var:mood",
                  col_label="Coefficient (SE)"),
        ]
        stamped_acc = premises.stamp(acc, TEXT)
        by_id = {v["id"]: v for v in stamped_acc["values"]}
        by_var = {v["id"]: v for v in stamped_acc["variables"]}
        got = checks.evaluate(acc, TEXT)
        seen = 0
        for row in got["refused"]:
            for r in row["reasons"]:
                if r["reason"] not in premises.REASONS:
                    continue
                where = r["where"]
                if where in by_id:
                    owned = {x["reason"] for x in by_id[where]["premise"]["reasons"]}
                elif where in by_var:
                    var = by_var[where]
                    owned = {x["reason"] for x in
                             (var["bounds"]["verification"]["reasons"]
                              + var["granularity"]["verification"]["reasons"])}
                    # The bridge may say a family needs a bound the variable
                    # simply has not got; that is a fact about the FAMILY.
                    owned |= {"lower_bound_not_stated", "upper_bound_not_stated"}
                else:
                    continue
                seen += 1
                assert r["reason"] in owned, (row["check_id"], r["reason"], where)
        assert seen > 5, "the fixture produced too few premise refusals to prove anything"


# --------------------------------------------------------------------------
# The ratchet
# --------------------------------------------------------------------------

#: Names whose one definition is `premises.py`'s. Anything under `scaffold/`
#: that assigns one of these to a literal collection is a second copy, which is
#: how every one of the seventeen prior instances of this defect began.
_OWNED = re.compile(r"CORROBORATED|BOUND_SOURCE|PROVENANCE_OF|LOCATED|DISCRETENESS")

#: Functions that decide whether a quote is really in the paper.
_LOCATORS = frozenset({"locate", "locates", "verify", "classify"})

#: Modules exempt from the LITERAL-COLLECTION clause. One entry, and it is a
#: DIFFERENT vocabulary wearing a similar name: `schema.BOUND_SOURCES` is what a
#: model may WRITE in `bounds.source` (three tokens, `not_stated` among them),
#: while `premises.BOUND_SOURCE_OF` is which of those may pass a NUMBER (two).
#: They are kept from drifting by `test_the_schema_and_the_gate_agree` below
#: rather than by being merged, because merging them would let `not_stated`
#: through the gate that exists to stop it.
_LITERAL_EXEMPT: dict[str, str] = {
    "schema.py": "`BOUND_SOURCES` is the schema's enum of what a model may write, "
                 "not the allowlist of what may pass a number; the subset relation "
                 "between the two is asserted separately",
}

#: Modules exempt from the COMPARISON clause, each with the reason it is not the
#: admission decision. Obligations-style: an exemption that carries no reason is
#: a hole, and a hole nobody named is how the rule dies.
_COMPARISON_EXEMPT: dict[str, str] = {
    "render.py": "prints the raw field beside the quote as a display flag "
                 "(`[stitched]`); it admits nothing and reads no premise from it",
    "coverage.py": "the numeral-credit pass reads a COMPARISON's quote, and a "
                   "comparison is not a value: it carries no premise stamp",
    "review.py": "reads the quote of a MODEL'S REVIEW NOTE, which is the model's "
                 "own second reading of the paper and not an account value at all",
    "structure.py": "reads the evidence quote of a STRUCTURAL EDIT, adjudicated by "
                    "the structure lifecycle rather than by a value's premise",
}

#: Modules exempt from the LOCATOR clause, same rule.
_LOCATOR_EXEMPT: dict[str, str] = {
    "bind.py": "the assembler is where `quote_verified` is COMPUTED; premises reads "
               "what it wrote, and something has to write it",
    "coverage.py": "locates a COMPARISON's quote and a claim's, to credit the "
                   "numerals they carry; neither is a value premise",
    "review.py": "verifies the quote of a model's review note, which is not a value",
    "structure.py": "verifies a structural edit's evidence quote",
    "premise_reading.py": "locates THROUGH `premises.Haystack` -- the definition this "
                          "ratchet exists to keep single -- and what it locates is a "
                          "CANDIDATE SENTENCE it drew out of the served text before "
                          "offering it to a model, which is not a value's quote and "
                          "carries no premise stamp; the refusal it makes is that an "
                          "unlocatable candidate is never asked about at all",
    "adjudication.py": "locates THROUGH `premises.Haystack` for the same reason and "
                       "on the same object -- a CANDIDATE PASSAGE drawn out of the "
                       "served text, never a value's quote. It records the answer and "
                       "does NOT refuse on it: the passage is a WINDOW of two or three "
                       "sentences, which is exactly the shape that will not locate as "
                       "one contiguous span, and dropping it would reintroduce the "
                       "recall gap the module exists to close. Safe only because "
                       "`averaging` is a refusal premise",
}


def _modules() -> list[pathlib.Path]:
    return sorted(p for p in SCAFFOLD.rglob("*.py") if p.name != "premises.py")


def _offenders_literal(tree: ast.AST) -> list[str]:
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        names = {t.id for t in node.targets if isinstance(t, ast.Name)}
        if not any(_OWNED.search(n) for n in names):
            continue
        if isinstance(node.value, (ast.Set, ast.Tuple, ast.List, ast.Dict, ast.Call)):
            out.append(f"{node.lineno} {sorted(names)}")
    return out


def _offenders_compare(tree: ast.AST) -> list[str]:
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        src = ast.unparse(node)
        if "quote_verified" not in src and "id_check" not in src:
            continue
        if any(isinstance(c, ast.Constant) and isinstance(c.value, str)
               for c in node.comparators) or any(
                   isinstance(c, (ast.Tuple, ast.List, ast.Set))
                   and any(isinstance(e, ast.Constant) and isinstance(e.value, str)
                           for e in c.elts) for c in node.comparators):
            out.append(f"{node.lineno} {src[:70]}")
    return out


def _offenders_locator(tree: ast.AST) -> list[str]:
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else (
            fn.id if isinstance(fn, ast.Name) else "")
        if name not in _LOCATORS or not node.args:
            continue
        arg = ast.unparse(node.args[0])
        if "quote" in arg:
            out.append(f"{node.lineno} {name}({arg[:50]})")
    return out


class TestNoModuleUnderScaffoldReDerivesIt:
    """The ratchet, in the mechanism of `test_accusatory_vocabulary`."""

    def test_no_second_copy_of_an_owned_vocabulary(self):
        offenders = []
        for path in _modules():
            if path.name in _LITERAL_EXEMPT:
                continue
            for hit in _offenders_literal(ast.parse(path.read_text(encoding="utf-8"))):
                offenders.append(f"{path.relative_to(SCAFFOLD)}:{hit}")
        assert not offenders, (
            "these define one of premises.py's vocabularies from a literal rather "
            "than importing it: " + "; ".join(offenders))

    def test_no_module_compares_quote_verified_or_id_check_to_a_literal(self):
        offenders = []
        for path in _modules():
            if path.name in _COMPARISON_EXEMPT:
                continue
            for hit in _offenders_compare(ast.parse(path.read_text(encoding="utf-8"))):
                offenders.append(f"{path.relative_to(SCAFFOLD)}:{hit}")
        assert not offenders, (
            "the admission rule these fields feed lives in `premises.py`; read "
            "`value['premise']` instead of re-deriving it: " + "; ".join(offenders))

    def test_no_module_locates_a_values_own_quote(self):
        offenders = []
        for path in _modules():
            if path.name in _LOCATOR_EXEMPT:
                continue
            for hit in _offenders_locator(ast.parse(path.read_text(encoding="utf-8"))):
                offenders.append(f"{path.relative_to(SCAFFOLD)}:{hit}")
        assert not offenders, (
            "a quote's location is decided once, in `premises.Haystack`: "
            + "; ".join(offenders))

    def test_the_schema_and_the_gate_agree_about_the_bound_sources(self):
        """The one exempted vocabulary, pinned to the one it is not. Every source
        the gate admits must be a source the schema allows, and the one the
        schema allows and the gate does not is `not_stated` -- which is the
        whole point of the gate."""
        from forensic_metascience_ai_toolkit.scaffold import schema
        assert set(premises.BOUND_SOURCE_OF) < set(schema.BOUND_SOURCES)
        assert set(schema.BOUND_SOURCES) - set(premises.BOUND_SOURCE_OF) == {"not_stated"}

    def test_every_exemption_carries_a_reason(self):
        for table in (_LITERAL_EXEMPT, _COMPARISON_EXEMPT, _LOCATOR_EXEMPT):
            for module, why in table.items():
                assert (SCAFFOLD / module).is_file(), module
                assert len(why) > 40, module

    @pytest.mark.parametrize("planted,check", [
        ('CORROBORATED = {"agrees", "join"}\n', _offenders_literal),
        ('BOUND_SOURCE_OF = {"stated": "stated"}\n', _offenders_literal),
        ('x = v.get("quote_verified") == "verbatim"\n', _offenders_compare),
        ('y = v["id_check"] in ("agrees", "join")\n', _offenders_compare),
        ('z = locate(v.get("quote"), text)\n', _offenders_locator),
        ('w = hay.verify(var["quote"])\n', _offenders_locator),
    ])
    def test_the_ratchet_fires_on_a_planted_copy(self, planted, check):
        """A guard that cannot fire passed for the wrong reason."""
        assert check(ast.parse(planted))

    def test_the_ratchet_passes_clean_code(self):
        clean = ('from .premises import CORROBORATED\n'
                 'CORROBORATED = premises.CORROBORATED\n'
                 'ok = value["premise"]["binding"] == "corroborated"\n'
                 'span = locate(sentence, text)\n')
        tree = ast.parse(clean)
        assert not _offenders_literal(tree)
        assert not _offenders_compare(tree)
        assert not _offenders_locator(tree)


class TestTheOneDefinitionIsShared:
    def test_coverage_imports_the_corroborated_set_rather_than_restating_it(self):
        assert coverage.CORROBORATED is premises.CORROBORATED

    def test_the_bridge_aliases_rather_than_copies(self):
        assert checks.CORROBORATED is premises.CORROBORATED
        assert checks.PROVENANCE_OF is premises.PROVENANCE_OF
        assert checks.BOUND_SOURCE_OF is premises.BOUND_SOURCE_OF
        assert checks._read_plain is premises.read_plain
