"""The checks bridge, on synthetic input, in both directions.

NO NUMBER FROM AN INSTRUMENT THAT HAS NOT PASSED A SYNTHETIC CASE IN EACH
DIRECTION (CLAUDE.md 8n). Every fixture below is a paper whose answer is known
by construction: a mean that no integer sample can produce, the same mean one
hundredth lower which several can, a percentage that does not match its printed
count and one that does, a sample size at which GRIM has no resolution at all,
and an unbounded count that today's registry defaults would have called
`suspicious`. A bridge that only ever returned `consistent` would pass a
one-directional suite and be worthless.

Then the nine invariants. Each is asserted over EVERY args dict the bridge
emits, not over a happy-path sample -- the failure this repo keeps finding is a
guard that is present, imported, called, and inert on the shape the live path
actually produces.
"""

from __future__ import annotations

import copy
import json

import pytest

from forensic_metascience_ai_toolkit.scaffold import bind, checks, structure

# --------------------------------------------------------------------------
# A fixture paper whose every answer is known by construction.
# --------------------------------------------------------------------------

W7_TEXT = """## METHODS

Wellbeing was rated on a 1-7 scale, and each participant gave one whole-number
rating on that scale. Falls were counted, so each participant contributed a
whole number of falls and the count cannot be negative. Coalition members were
counted; the paper states no ceiling on that count. Thirty participants
completed the survey, two hundred patients were screened in the clinic, and
sixty-four coalitions returned the reach form.

## RESULTS

| | Survey | Clinic | Reach |
|---|---|---|---|
| n | 30 | 200 | 64 |
| Wellbeing | 3.51 | | |
| Wellbeing at follow-up | 3.50 (0.80) | | |
| Reach | | | 224 |
| Members | | | 35.78 |
| Improved | | 142 (73.0) | |
| Recovered | | 146 (73.0) | |
| Disputed | | 10 (5.0) | |
| Service area population | 84,299 | | |
| Wellbeing slope | 1.01 (0.38) | | |
| Wellbeing at endpoint | 3.50 (1.28) | | |

## REFERENCES

Smith J (2001). A paper. J Things 12: 100-110.
"""

_ROWS: list[tuple[str, list[tuple[int, str, list[dict]]]]] = [
    # (row label, [(col index, raw cell, tidy entries)])
    ("n", [
        (1, "30", [{"variable": "Sample size", "statistic": "n", "value": "30",
                    "group_id": "grp:survey"}]),
        (2, "200", [{"variable": "Sample size", "statistic": "n", "value": "200",
                     "group_id": "grp:clinic"}]),
        (3, "64", [{"variable": "Sample size", "statistic": "n", "value": "64",
                    "group_id": "grp:reach"}]),
    ]),
    ("Wellbeing", [
        (1, "3.51", [{"variable": "Wellbeing", "variable_id": "var:wellbeing",
                      "statistic": "mean", "value": "3.51", "group_id": "grp:survey"}]),
    ]),
    ("Wellbeing at follow-up", [
        (1, "3.50 (0.80)", [
            {"variable": "Wellbeing", "variable_id": "var:wellbeing",
             "statistic": "mean", "value": "3.50", "group_id": "grp:survey"},
            {"variable": "Wellbeing", "variable_id": "var:wellbeing",
             "statistic": "sd", "value": "0.80", "group_id": "grp:survey"}]),
    ]),
    ("Reach", [
        (3, "224", [{"variable": "Reach", "variable_id": "var:reach",
                     "statistic": "mean", "value": "224", "group_id": "grp:reach"}]),
    ]),
    ("Members", [
        (3, "35.78", [{"variable": "Members", "variable_id": "var:members",
                       "statistic": "mean", "value": "35.78", "group_id": "grp:reach"}]),
    ]),
    ("Improved", [
        (2, "142 (73.0)", [
            {"variable": "Improved", "variable_id": "var:improved", "statistic": "count",
             "value": "142", "group_id": "grp:clinic"},
            {"variable": "Improved", "variable_id": "var:improved", "statistic": "percentage",
             "value": "73.0", "group_id": "grp:clinic"}]),
    ]),
    ("Recovered", [
        (2, "146 (73.0)", [
            {"variable": "Recovered", "variable_id": "var:recovered", "statistic": "count",
             "value": "146", "group_id": "grp:clinic"},
            {"variable": "Recovered", "variable_id": "var:recovered", "statistic": "percentage",
             "value": "73.0", "group_id": "grp:clinic"}]),
    ]),
    # THE BINDING THE JOIN CONTRADICTS: the words say `Recovered`, the id says
    # `var:improved`, so `interpret` stamps `id_check: disagrees`.
    ("Disputed", [
        (2, "10 (5.0)", [
            {"variable": "Recovered", "variable_id": "var:improved", "statistic": "count",
             "value": "10", "group_id": "grp:clinic"},
            {"variable": "Recovered", "variable_id": "var:improved", "statistic": "percentage",
             "value": "5.0", "group_id": "grp:clinic"}]),
    ]),
    ("Service area population", [
        (1, "84,299", [{"variable": "Service area population",
                        "variable_id": "var:population", "statistic": "mean",
                        "value": "84,299", "group_id": "grp:survey"}]),
    ]),
    # A DISPERSION BESIDE A COEFFICIENT is a model standard error, not a
    # descriptive one, whatever the scale of the variable it names.
    ("Wellbeing slope", [
        (1, "1.01 (0.38)", [
            {"variable": "Wellbeing", "variable_id": "var:wellbeing",
             "statistic": "coefficient", "value": "1.01", "group_id": "grp:survey"},
            {"variable": "Wellbeing", "variable_id": "var:wellbeing",
             "statistic": "se", "value": "0.38", "group_id": "grp:survey"}]),
    ]),
    # THE OTHER DIRECTION FOR GRIMMER/SPRITE: the same mean with an SD that a
    # real integer sample can produce. Kept last so the row indices of every
    # fixture above stay where the tests name them.
    ("Wellbeing at endpoint", [
        (1, "3.50 (1.28)", [
            {"variable": "Wellbeing", "variable_id": "var:wellbeing",
             "statistic": "mean", "value": "3.50", "group_id": "grp:survey"},
            {"variable": "Wellbeing", "variable_id": "var:wellbeing",
             "statistic": "sd", "value": "1.28", "group_id": "grp:survey"}]),
    ]),
]


def _w7_doc() -> dict:
    from forensic_metascience_ai_toolkit import numerals, sections
    cells = []
    for ri, (rl, cols) in enumerate(_ROWS, start=1):
        for ci, raw, entries in cols:
            cells.append({"raw": raw, "row": ri, "col": ci, "row_label": rl,
                          "col_label": ["Survey", "Clinic", "Reach"][ci - 1],
                          "entries": [dict(e) for e in entries]})
    span_start = W7_TEXT.index("| | Survey")
    span_end = W7_TEXT.index("## REFERENCES") - 2
    nums = numerals.index(W7_TEXT, tables_available=True)
    for r in nums:
        r["role"] = "back" if r["offset"] >= W7_TEXT.index("## REFERENCES") else "results"
    return {
        "text": W7_TEXT, "original_text": W7_TEXT, "source": {}, "problems": [],
        "font_audit": {}, "repairs": {"n_repairs": 0},
        "sections": sections.map_sections(W7_TEXT),
        "tables": [{"id": "table:1", "label": "Table 1", "caption": None,
                    "n_cells": len(cells),
                    "row_labels": [r[0] for r in _ROWS],
                    "col_labels": ["Survey", "Clinic", "Reach"],
                    "sections": [], "footnotes": [], "n_header_rows": 1,
                    "header_rows": None, "text_span": [span_start, span_end],
                    "cells": cells, "reconstruction": {"status": "verified"}}],
        "figures": [], "supplements_referenced": [], "numerals": nums,
        "numeral_floor": numerals.tally(nums),
    }


def _group(gid: str, label: str, n: str) -> dict:
    return {"id": gid, "label": label, "description": "", "n_printed": n,
            "n_quote": None}


W7_P1 = {
    "paper": {"title": "W7", "authors": ["A"], "journal": None, "year": None,
              "doi": None, "species_or_population": "people"},
    "background": {"problem": "", "prior_findings": [], "gap": "", "aims": []},
    "subjects": {"population": None, "unit_of_analysis": None, "setting": None,
                 "recruitment": None, "eligibility": None, "species": None,
                 "strain": None, "sex": None, "age": None, "supplier": None,
                 "housing": None, "total_n_stated": True, "quote": "Thirty participants"},
    "statistical_analysis": {"methods_quote": "", "tests_named": [], "alpha_declared": None,
                             "alpha_quote": None, "significance_legend": [],
                             "detailed_statistics_location": None,
                             "test_to_experiment_mapping_in_main_text": False},
    "phases": [],
    "procedures": [],
    "studies": [
        {"id": "study:survey", "label": "Survey", "aim": "", "section_heading": "RESULTS",
         "reported_in": [{"kind": "table", "label": "Table 1", "panels": []}],
         "design_type": "cross_sectional", "design_description": "one occasion",
         "n_range_printed": None, "n_range_quote": None, "n_scope": "total",
         "groups": [_group("grp:survey", "Survey", "30")], "phases": [],
         "outcomes_described": ["wellbeing"], "manipulations_described": [],
         "result_summary_quotes": [], "interpretation_quotes": [], "procedure_ids": []},
        {"id": "study:clinic", "label": "Clinic", "aim": "", "section_heading": "RESULTS",
         "reported_in": [{"kind": "table", "label": "Table 1", "panels": []}],
         "design_type": "cross_sectional", "design_description": "one occasion",
         "n_range_printed": None, "n_range_quote": None, "n_scope": "total",
         "groups": [_group("grp:clinic", "Clinic", "200")], "phases": [],
         "outcomes_described": ["improvement"], "manipulations_described": [],
         "result_summary_quotes": [], "interpretation_quotes": [], "procedure_ids": []},
        {"id": "study:reach", "label": "Reach", "aim": "", "section_heading": "RESULTS",
         "reported_in": [{"kind": "table", "label": "Table 1", "panels": []}],
         "design_type": "cross_sectional", "design_description": "one occasion",
         "n_range_printed": None, "n_range_quote": None, "n_scope": "total",
         "groups": [_group("grp:reach", "Reach", "64")], "phases": [],
         "outcomes_described": ["reach"], "manipulations_described": [],
         "result_summary_quotes": [], "interpretation_quotes": [], "procedure_ids": []},
    ],
    "claims": [],
    "supplements_referenced": [],
}

_SCALE_QUOTE = "Wellbeing was rated on a 1-7 scale"
_STEP_QUOTE = "each participant gave one whole-number\nrating on that scale"
_FALLS_QUOTE = ("Falls were counted, so each participant contributed a\nwhole number of falls "
                "and the count cannot be negative")
_MEMBERS_QUOTE = "Coalition members were\ncounted; the paper states no ceiling on that count"


def _var(vid: str, name: str, kind: str, bounds: dict, gran: dict, **kw) -> dict:
    return {"id": vid, "name": name, "role": kw.get("role", "measured_outcome"),
            "kind": kind, "units": None, "units_source": "not_stated",
            "bounds": bounds, "granularity": gran, "derivation": None,
            "derived_from": [], "procedure_id": None, "printed_as": kw.get("printed_as", []),
            "levels": [], "studies_using": kw.get("studies_using", []),
            "quote": kw.get("quote", name), "notes": None}


W7_P2 = {
    "variables": [
        _var("var:wellbeing", "Wellbeing", "integer_score",
             {"lower": 1, "upper": 7, "source": "stated", "quote": _SCALE_QUOTE},
             {"per_subject_step": 1, "basis": "whole-number rating", "quote": _STEP_QUOTE},
             studies_using=["study:survey"], quote=_SCALE_QUOTE),
        _var("var:reach", "Reach", "count",
             {"lower": 0, "upper": None, "source": "definitional", "quote": _FALLS_QUOTE},
             {"per_subject_step": 1, "basis": "a count", "quote": _FALLS_QUOTE},
             studies_using=["study:reach"], quote=_FALLS_QUOTE),
        _var("var:members", "Members", "count",
             {"lower": None, "upper": None, "source": "not_stated", "quote": None},
             {"per_subject_step": 1, "basis": "a count", "quote": _MEMBERS_QUOTE},
             studies_using=["study:reach"], quote=_MEMBERS_QUOTE),
        _var("var:improved", "Improved", "percentage_of_subjects",
             {"lower": 0, "upper": 100, "source": "definitional", "quote": None},
             {"per_subject_step": None, "basis": None, "quote": None},
             studies_using=["study:clinic"], quote="Improved"),
        _var("var:recovered", "Recovered", "percentage_of_subjects",
             {"lower": 0, "upper": 100, "source": "definitional", "quote": None},
             {"per_subject_step": None, "basis": None, "quote": None},
             studies_using=["study:clinic"], quote="Recovered"),
        _var("var:population", "Service area population", "count",
             {"lower": 0, "upper": None, "source": "definitional", "quote": _FALLS_QUOTE},
             {"per_subject_step": 1, "basis": "a count", "quote": _FALLS_QUOTE},
             studies_using=["study:survey"], quote="Service area population"),
    ],
    "group_coordinates": [], "phase_coordinates": [], "procedure_parameters": [],
    "outcome_bindings": [], "population_descriptors": [],
}

W7_P3 = {
    "table_readings": [{
        "table_id": "table:1", "caption": None, "n_per_column_stated": True,
        "n_note": None,
        "column_map": [
            {"col_label": "Survey", "study_id": "study:survey", "group_id": "grp:survey",
             "phase_id": None},
            {"col_label": "Clinic", "study_id": "study:clinic", "group_id": "grp:clinic",
             "phase_id": None},
            {"col_label": "Reach", "study_id": "study:reach", "group_id": "grp:reach",
             "phase_id": None}],
        "row_map": [],
    }],
    "prose_values": [], "comparisons": [], "figure_panels": [],
}


@pytest.fixture(scope="module")
def w7():
    return bind.assemble(_w7_doc(), W7_P1, W7_P2, W7_P3)


@pytest.fixture(scope="module")
def w7_checks(w7):
    return checks.evaluate(w7, W7_TEXT)


def _ran(got: dict, check_id: str) -> dict:
    hits = [r for r in got["checks"] if r["check_id"] == check_id]
    assert hits, (f"{check_id} did not run; refused: "
                  + json.dumps([r for r in got["refused"] if r["check_id"] == check_id]))
    return hits[0]


def _refusal(got: dict, check_id: str) -> dict:
    hits = [r for r in got["refused"] if r["check_id"] == check_id]
    assert hits, f"{check_id} was not refused"
    return hits[0]


# --------------------------------------------------------------------------
# The fixture itself has to be the paper the tests think it is
# --------------------------------------------------------------------------


class TestTheFixtureIsWhatItClaims:
    def test_the_account_has_no_integrity_problems(self, w7):
        assert w7["integrity_problems"] == []

    def test_the_bindings_came_out_as_designed(self, w7):
        by_id = {v["id"]: v for v in w7["values"]}
        assert by_id["val:t1:r2:c1:0:mean"]["id_check"] == "agrees"
        assert by_id["val:t1:r8:c2:0:count"]["id_check"] == "disagrees"

    def test_the_premise_quotes_locate_in_the_served_text(self):
        for q in (_SCALE_QUOTE, _STEP_QUOTE, _FALLS_QUOTE, _MEMBERS_QUOTE):
            assert bind.locate(q, W7_TEXT) is not None, q


# --------------------------------------------------------------------------
# Both directions, one fixture each
# --------------------------------------------------------------------------


class TestKnownAnswers:
    def test_known_impossible_mean_is_impossible(self, w7_checks):
        r = _ran(w7_checks, "chk:grim:val:t1:r2:c1:0:mean")
        assert r["args"]["mean"] == 3.51 and r["args"]["n"] == 30
        assert r["args"]["decimals"] == 2
        assert r["severity"] == "impossible"
        assert r["result"]["failure_mode"] == "granularity"

    def test_known_consistent_mean_is_consistent(self, w7_checks):
        r = _ran(w7_checks, "chk:grim:val:t1:r3:c1:0:mean")
        assert r["args"]["mean"] == 3.50
        assert r["severity"] == "consistent"

    def test_count_percent_catches_the_mismatched_pair(self, w7_checks):
        r = _ran(w7_checks, "chk:count_percent:val:t1:r6:c2:1:percentage")
        assert r["args"] == {**r["args"], "count": 142, "percentage": 73.0, "n": 200,
                             "decimals": 1}
        assert r["severity"] == "suspicious"

    def test_count_percent_clears_the_matching_pair(self, w7_checks):
        r = _ran(w7_checks, "chk:count_percent:val:t1:r7:c2:1:percentage")
        assert r["args"]["count"] == 146
        assert r["severity"] == "consistent"

    def test_a_check_with_no_power_is_never_consistent(self, w7_checks):
        r = _ran(w7_checks, "chk:grim:val:t1:r4:c3:0:mean")
        assert r["args"]["mean"] == 224 and r["args"]["decimals"] == 0
        assert r["args"]["n"] == 64
        assert r["severity"] == "indeterminate"
        assert r["result"]["failure_mode"] == "no_discriminating_power"

    def test_an_unbounded_count_is_consistent_not_suspicious(self, w7_checks):
        """D1-A. Without the `None` bound this call runs against an INVENTED 1-7
        scale and comes back `suspicious` / `out_of_range` on an ordinary mean."""
        r = _ran(w7_checks, "chk:grim:val:t1:r5:c3:0:mean")
        assert r["args"]["scale_min"] is None and r["args"]["scale_max"] is None
        assert r["args"]["bound_source"] == "assumed"
        assert r["severity"] == "consistent"

    def test_grimmer_and_sprite_reach_both_verdicts_on_this_fixture(self, w7_checks):
        """An SD no integer sample of 30 on a 1-7 scale can produce, and one it
        can. A family that only ever returned one of the two would pass a
        one-directional suite and be worthless."""
        bad = _ran(w7_checks, "chk:grimmer:val:t1:r3:c1:0:mean")
        good = _ran(w7_checks, "chk:grimmer:val:t1:r11:c1:0:mean")
        assert bad["args"]["sd"] == 0.80 and bad["severity"] == "impossible"
        assert good["args"]["sd"] == 1.28 and good["severity"] == "consistent"
        for r in (bad, good):
            assert r["args"]["scale_min"] == 1 and r["args"]["scale_max"] == 7
            assert r["args"]["discreteness_source"] == "stated"
        sp = _ran(w7_checks, "chk:sprite:val:t1:r11:c1:0:mean")
        assert sp["args"]["decimals_mean"] == 2 and sp["args"]["decimals_sd"] == 2

    def test_grimmer_and_sprite_run_at_assumed_bounds_and_the_record_says_so(self, w7_checks):
        """Their ToolSpecs expose no `bound_source` parameter, so through the
        registry they run at `assumed` whatever the paper stated. Recorded on the
        premises rather than worked around."""
        r = _ran(w7_checks, "chk:grimmer:val:t1:r11:c1:0:mean")
        assert "bound_source" not in r["args"]
        assert r["premises"]["bounds"]["bound_source"] == "stated"
        assert r["premises"]["bounds"]["bound_source_not_exposed_by_toolspec"] is True

    def test_the_same_call_with_the_default_scale_would_have_accused(self):
        """The control for the test above: the accusation is real, and it is the
        bound rather than the arithmetic that produces it."""
        from forensic_metascience_ai_toolkit.tools.grim import grim_test
        assert grim_test(35.78, 64, decimals=2, data_type="count")["severity"] == "suspicious"
        assert grim_test(35.78, 64, decimals=2, data_type="count",
                         scale_min=None, scale_max=None)["severity"] == "consistent"


# --------------------------------------------------------------------------
# I1 - I9, each over EVERY emitted args dict
# --------------------------------------------------------------------------


BOUND_ARGS = ("scale_min", "scale_max", "variable_range_min", "variable_range_max",
              "min_val", "max_val")


class TestInvariants:
    def test_i1_an_unstated_bound_is_never_passed_as_a_number(self, w7_checks, w7):
        variables = {v["id"]: v for v in w7["variables"]}
        seen = 0
        for r in w7_checks["checks"]:
            var = variables.get(r["variable_id"]) or {}
            if (var.get("bounds") or {}).get("source") != "not_stated":
                continue
            seen += 1
            for name in BOUND_ARGS:
                assert r["args"].get(name) is None, (r["check_id"], name)
            assert r["args"].get("bound_source", "assumed") == "assumed"
        assert seen, "no call rested on an unstated-bounds variable; the test proved nothing"

    def test_i2_an_uncorroborated_binding_appears_in_no_call(self, w7_checks, w7):
        by_id = {v["id"]: v for v in w7["values"]}
        bad = {v["id"] for v in w7["values"]
               if v.get("id_check") in ("disagrees", "unjoined")}
        assert bad, "the fixture carries no uncorroborated binding; the test proved nothing"
        for r in w7_checks["checks"]:
            assert not (set(r["value_ids"].values()) & bad), r["check_id"]
        assert all(by_id[i] for i in bad)

    def test_i3_every_decimals_is_the_strict_count_over_the_printed_literal(self, w7_checks, w7):
        by_id = {v["id"]: v for v in w7["values"]}
        for r in w7_checks["checks"]:
            for name, role in (("decimals", None), ("decimals_sd", "sd"),
                               ("decimals_mean", "mean")):
                if name not in r["args"]:
                    continue
                vid = r["value_ids"].get(role) if role else _primary_of(r)
                got = checks._read_plain(by_id[vid]["printed"])
                assert got is not None and got["decimals"] == r["args"][name], (r["check_id"], name)

    def test_i3b_a_literal_the_grammar_refuses_appears_in_no_call(self, w7_checks, w7):
        by_id = {v["id"]: v for v in w7["values"]}
        bad = {v["id"] for v in w7["values"] if checks._read_plain(v["printed"]) is None}
        assert "val:t1:r9:c1:0:mean" in bad          # `84,299`
        for r in w7_checks["checks"]:
            assert not (set(r["value_ids"].values()) & bad), r["check_id"]
        assert all(by_id[i] for i in bad)

    def test_i4_every_provenance_is_printed(self, w7_checks):
        for r in w7_checks["checks"]:
            assert r["premises"]["provenance"]["value"] in ("printed_table", "printed_text")
            if "provenance" in r["args"]:
                assert r["args"]["provenance"] in ("printed_table", "printed_text")

    def test_i4b_a_figure_sourced_value_is_refused(self, w7):
        acc = copy.deepcopy(w7)
        for v in acc["values"]:
            if v["id"] == "val:t1:r3:c1:0:mean":
                v["source"] = "figure"
        got = checks.evaluate(acc, W7_TEXT)
        row = _refusal(got, "chk:grim:val:t1:r3:c1:0:mean")
        assert "provenance_not_printed" in {x["reason"] for x in row["reasons"]}
        for r in got["checks"]:
            assert "val:t1:r3:c1:0:mean" not in set(r["value_ids"].values())

    def test_i5_stated_discreteness_needs_a_located_quote(self, w7, w7_checks):
        for r in w7_checks["checks"]:
            if r["args"].get("discreteness_source") == "stated":
                assert r["premises"]["discreteness"]["quote_located"] is True
        p2 = copy.deepcopy(W7_P2)
        for v in p2["variables"]:
            if v["id"] == "var:wellbeing":
                v["granularity"]["quote"] = "a sentence this paper does not contain"
        acc = bind.assemble(_w7_doc(), W7_P1, p2, W7_P3)
        got = checks.evaluate(acc, W7_TEXT)
        row = _refusal(got, "chk:grim:val:t1:r2:c1:0:mean")
        assert row["reason"] == "discreteness_assumed"

    def test_i6_every_severity_is_the_tools_own(self, w7_checks):
        assert w7_checks["checks"], "nothing ran; the test proved nothing"
        for r in w7_checks["checks"]:
            assert r["severity"] == r["result"]["severity"], r["check_id"]

    def test_i7_a_structure_mismatch_refuses_before_anything_runs(self, tmp_path, w7):
        out = tmp_path / "scaffold"
        out.mkdir()
        struct = {"schema_version": "structure/1", "version": 1, "status": "draft",
                  "paper_identity": {}, "document_sha256": "abc",
                  "pass1": W7_P1, "pass2": W7_P2}
        (out / "structure.json").write_text(json.dumps(struct), encoding="utf-8")
        (out / "body.repaired.md").write_text(W7_TEXT, encoding="utf-8")
        acc = copy.deepcopy(w7)
        acc["provenance"] = {"structure_version": 1,
                             "structure_sha256": "0" * 64}
        acc["structure"] = {"version": 1, "sha256": "0" * 64}
        (out / "account.json").write_text(json.dumps(acc), encoding="utf-8")
        with pytest.raises(structure.StructureMismatch):
            checks.run(out)
        assert not (out / "checks.json").exists()

    def test_i7b_the_stamps_agree_on_a_consistent_pair(self, tmp_path, w7):
        out = tmp_path / "scaffold"
        out.mkdir()
        struct = {"schema_version": "structure/1", "version": 3, "status": "frozen",
                  "paper_identity": {}, "document_sha256": "abc",
                  "pass1": W7_P1, "pass2": W7_P2}
        sha = structure.content_sha256(struct)
        (out / "structure.json").write_text(json.dumps(struct), encoding="utf-8")
        (out / "body.repaired.md").write_text(W7_TEXT, encoding="utf-8")
        acc = copy.deepcopy(w7)
        acc["provenance"] = {"structure_version": 3, "structure_sha256": sha}
        acc["structure"] = {"version": 3, "sha256": sha}
        (out / "account.json").write_text(json.dumps(acc), encoding="utf-8")
        got = checks.run(out)
        assert got["structure_sha256"] == sha == acc["structure"]["sha256"]
        assert got["structure_version"] == 3
        assert (out / "checks.json").is_file() and (out / "checks.md").is_file()

    def test_i8_every_n_is_the_unique_plain_integer_at_the_coordinate(self, w7_checks, w7):
        by_id = {v["id"]: v for v in w7["values"]}
        assert w7_checks["checks"]
        for r in w7_checks["checks"]:
            v = by_id[_primary_of(r)]
            c = v["coordinate"]
            rows = [w for w in w7["values"] if w["statistic"] == "n"
                    and (w["coordinate"] or {}).get("study_id") == c.get("study_id")
                    and (w["coordinate"] or {}).get("group_id") == c.get("group_id")]
            assert rows, r["check_id"]
            assert {int(w["printed"]) for w in rows} == {r["args"]["n"]}, r["check_id"]

    def test_i8b_a_second_distinct_n_at_the_coordinate_refuses(self, w7):
        acc = copy.deepcopy(w7)
        extra = copy.deepcopy(next(v for v in acc["values"] if v["id"] == "val:t1:r1:c1:0:n"))
        extra.update({"id": "val:t1:r1:c1:0:n:planted", "printed": "29", "numeric": 29.0})
        acc["values"].append(extra)
        got = checks.evaluate(acc, W7_TEXT)
        row = _refusal(got, "chk:grim:val:t1:r2:c1:0:mean")
        assert "ambiguous_n" in {x["reason"] for x in row["reasons"]}
        assert not [r for r in got["checks"]
                    if (r["coordinate"] or {}).get("group_id") == "grp:survey"]

    def test_i9_a_dispersion_beside_a_coefficient_appears_in_no_call(self, w7_checks, w7):
        by_id = {v["id"]: v for v in w7["values"]}
        row = _refusal(w7_checks, "chk:sd_or_se:val:t1:r10:c1:1:se")
        assert row["reason"] == "dispersion_of_coefficient"
        for r in w7_checks["checks"]:
            for vid in r["value_ids"].values():
                v = by_id[vid]
                if v["statistic"] not in ("sd", "se", "sem", "dispersion_unstated"):
                    continue
                loc = v["location"]
                sibs = {w["statistic"] for w in w7["values"]
                        if w["id"] != vid and (w["location"] or {}).get("kind") == "table_cell"
                        and (w["location"]["table_id"], w["location"]["row"],
                             w["location"]["col"]) == (loc["table_id"], loc["row"], loc["col"])}
                assert "coefficient" not in sibs, r["check_id"]


def _primary_of(record: dict) -> str:
    return record["check_id"].split(":", 2)[2]


# --------------------------------------------------------------------------
# The bridge's own contracts
# --------------------------------------------------------------------------


class TestTheBridgeContract:
    def test_every_family_names_a_registered_tool(self):
        from forensic_metascience_ai_toolkit import registry
        for fam, tool, _ in checks.FAMILIES:
            assert tool in registry.BY_NAME, (fam, tool)

    def test_the_census_tool_names_are_the_registrys_own(self):
        """The census's names were stale in five of seven rows when the bridge
        came to call them. Corrected in place; pinned here."""
        from forensic_metascience_ai_toolkit import registry
        from forensic_metascience_ai_toolkit.scaffold import applicability
        for fam, tools, _ in applicability.FAMILIES:
            for name in [t.strip() for t in tools.split("/")]:
                if name.startswith("("):
                    continue
                assert name in registry.BY_NAME, (fam, name)

    def test_every_emitted_reason_is_in_the_closed_vocabulary(self, w7_checks):
        for row in w7_checks["refused"]:
            assert row["reason"] in checks.REASONS, row["reason"]
            for r in row["reasons"]:
                assert r["reason"] in checks.REASONS
                assert r["premise"] in checks.PREMISE_ORDER

    def test_no_call_passes_variable_id_to_a_tool(self, w7_checks):
        """GATE 4 would reconcile it against the anatomy's `declared` store,
        which the scaffold never populates, so every call would come back
        `not_declared`. The id lives on the bridge's own record instead."""
        for r in w7_checks["checks"]:
            assert "variable_id" not in r["args"]
            assert r["variable_id"] is None or r["variable_id"].startswith("var:")

    def test_every_candidate_is_either_run_or_refused_with_a_reason(self, w7_checks):
        assert (w7_checks["n_run"] + w7_checks["n_refused"]) == w7_checks["n_candidates"]
        for row in w7_checks["refused"]:
            assert row["reasons"] and row["reason"] == row["reasons"][0]["reason"]

    def test_the_account_is_not_modified(self, w7):
        before = json.dumps(w7, sort_keys=True, default=str)
        checks.evaluate(w7, W7_TEXT)
        assert json.dumps(w7, sort_keys=True, default=str) == before

    def test_two_runs_on_one_disk_state_are_byte_identical(self, tmp_path, w7):
        out = tmp_path / "scaffold"
        out.mkdir()
        (out / "body.repaired.md").write_text(W7_TEXT, encoding="utf-8")
        (out / "account.json").write_text(json.dumps(w7, default=str), encoding="utf-8")
        checks.run(out)
        first = (out / "checks.json").read_bytes()
        checks.run(out)
        assert (out / "checks.json").read_bytes() == first

    def test_the_census_and_the_bridge_are_reconciled_coordinate_by_coordinate(self, w7_checks):
        cvb = w7_checks["census_vs_bridge"]
        for name, d in cvb.items():
            if name.startswith("_"):
                continue
            assert d["coordinates_run"] + d["coordinates_not_run"] == d["census_bindable"]
            for row in d["not_run"]:
                assert row["reason"] in checks.REASONS

    def test_a_family_with_no_registry_tool_says_so(self, w7_checks):
        rows = w7_checks["census_vs_bridge"]["range_within_bounds"]["not_run"]
        assert rows and all(r["reason"] == "no_registry_tool" for r in rows)

    def test_the_literal_is_read_twice_and_the_readings_are_compared(self, w7_checks):
        for r in w7_checks["checks"]:
            assert r["premises"]["literals"]
            for lit in r["premises"]["literals"]:
                assert lit["bridge_value"] is not None
                assert "agrees" in lit

    def test_d2_a_model_only_binding_is_refused_and_counted(self, w7):
        """D2. A prose value carries no name join at all, so its variable id
        rests on the model's reading alone; every family that reads a variable
        premise refuses it, and `check_count_percent`, which reads none, does
        not."""
        acc = copy.deepcopy(w7)
        mean = copy.deepcopy(next(v for v in acc["values"] if v["id"] == "val:t1:r2:c1:0:mean"))
        mean.update({"id": "val:prose:mean", "source": "prose", "id_check": None,
                     "quote_verified": "verbatim", "printed_in_quote": True,
                     "quote": "Wellbeing was rated on a 1-7 scale",
                     "location": {"kind": "results", "offset": 0, "end": 10}})
        pct = copy.deepcopy(next(v for v in acc["values"] if v["id"] == "val:t1:r6:c2:1:percentage"))
        cnt = copy.deepcopy(next(v for v in acc["values"] if v["id"] == "val:t1:r6:c2:0:count"))
        for v, vid in ((pct, "val:prose:pct"), (cnt, "val:prose:count")):
            v.update({"id": vid, "source": "prose", "id_check": None,
                      "quote_verified": "verbatim", "printed_in_quote": True,
                      "quote": "142 of 200 improved", "location": {"kind": "results",
                                                                   "offset": 0, "end": 10}})
        acc["values"] += [mean, pct, cnt]
        got = checks.evaluate(acc, W7_TEXT)
        assert _refusal(got, "chk:grim:val:prose:mean")["reason"] == "binding_model_only"
        assert _ran(got, "chk:count_percent:val:prose:pct")["severity"] == "suspicious"

    def test_d3_assumed_discreteness_is_refused_and_counted(self, w7_checks):
        """D3. Every granularity call that ran did so under a step of 1 the
        PAPER establishes or the KIND makes necessary; the refusal code exists
        and the vocabulary names it.

        THE SECOND LICENCE IS WAVE 7b's AND IT IS NOT A LOOSENING. A `count`
        kind makes a per-subject step of 1 logically necessary whatever any
        sentence says -- which is exactly what `bound_source:
        logically_necessary` already meant for a bound -- and both tokens are in
        `tools.grim.HARD_DISCRETENESS_SOURCES`, so both license the same
        verdicts. What it removes is the requirement that a paper print a
        sentence about the granularity of its own counts, which
        `var:ebp_reach` on ajcp.70049 does not."""
        from forensic_metascience_ai_toolkit.tools.grim import HARD_DISCRETENESS_SOURCES
        assert "discreteness_assumed" in checks.REASONS
        seen = set()
        for r in w7_checks["checks"]:
            if "discreteness_source" in r["args"]:
                got = r["args"]["discreteness_source"]
                assert got in HARD_DISCRETENESS_SOURCES, r["check_id"]
                seen.add(got)
        assert "stated" in seen, "no call rested on the paper's own sentence"

    def test_a_count_kind_licenses_its_own_step_and_an_integer_score_does_not(self, w7):
        """The kind-necessary licence, in both directions, on the fixture's own
        variables. `var:reach` is a `count`; `var:wellbeing` is an
        `integer_score`, which is the READING's word for what the numbers look
        like and not a claim about the instrument -- so it still needs the
        paper's sentence, and round 2 built its whole first cluster out of a
        continuous measurement typed `integer_score`."""
        from forensic_metascience_ai_toolkit.scaffold import premises
        by_id = {v["id"]: v for v in w7["variables"]}
        reach = by_id["var:reach"]["granularity"]["verification"]
        assert reach["discreteness_source"] == premises.NECESSARY_DISCRETENESS
        assert reach["kind_makes_it_necessary"] is True
        well = by_id["var:wellbeing"]["granularity"]["verification"]
        assert well["discreteness_source"] == premises.STATED_DISCRETENESS
        assert well["kind_makes_it_necessary"] is False

    def test_a_non_consistent_record_carries_the_denominator_window(self, w7_checks):
        """The per-row n is a premise the scaffold does not capture, and it moves
        in the accusing direction. Every non-consistent record therefore says
        which nearby denominators would have fitted -- as a question, and the
        severity is untouched."""
        bad = [r for r in w7_checks["checks"] if r["severity"] != "consistent"
               and "mean" in r["args"]]
        assert bad
        for r in bad:
            assert "n_that_would_fit" in r["premises"]["n"], r["check_id"]
        for r in w7_checks["checks"]:
            if r["severity"] == "consistent":
                assert "n_that_would_fit" not in r["premises"].get("n", {})

    def test_the_codestamp_names_this_module(self):
        from forensic_metascience_ai_toolkit.scaffold import codestamp
        assert "scaffold/checks.py" in codestamp.MODULES
        assert codestamp.stamp()["modules"]["scaffold/checks.py"]


class TestSection16:
    def test_the_render_says_so_when_no_checks_were_run(self, w7):
        from forensic_metascience_ai_toolkit.scaffold import render
        md = render.render(w7, W7_TEXT)
        assert "## 16. Checks run on the account's own premises" in md
        assert "Not run for this account" in md
        assert "## 17. What this form cannot show" in md

    def test_the_render_carries_the_checks_when_they_were(self, w7, w7_checks):
        from forensic_metascience_ai_toolkit.scaffold import render
        md = render.render(w7, W7_TEXT, {**w7_checks, "structure_version": None,
                                         "structure_status": None,
                                         "account_sha256": "0" * 64, "code": {}})
        assert "## 16. Checks run on the account's own premises" in md
        assert "`grim_check`" in md
        assert "The docket: candidates that did not run" in md


# --------------------------------------------------------------------------
# The literal parser (wave 7.0)
# --------------------------------------------------------------------------


class TestLiteralParser:
    @pytest.mark.parametrize("printed,form,numeric,decimals", [
        ("1.67", "plain", 1.67, 2),
        ("64", "plain", 64.0, 0),
        ("-0.5", "plain", -0.5, 1),
        (".001", "plain", 0.001, 3),
        ("85.94%", "percent", 85.94, 2),
        ("59%", "percent", 59.0, 0),
        ("84,299", "grouped_integer", 84299.0, 0),
        ("6-9", "range", None, 0),
        ("Twenty-six", "word", None, 0),
        ("approximately 84,000", "qualified", None, 0),
        ("< .001", "qualified", None, 3),
        ("more than 100", "qualified", None, 0),
        ("1 = None, 2 = A little", "other", None, 0),
        ("", "other", None, 0),
    ])
    def test_read_literal(self, printed, form, numeric, decimals):
        got = bind.read_literal(printed)
        assert got["printed_form"] == form
        assert got["numeric"] == numeric
        assert got["decimals"] == decimals

    def test_a_thousands_separator_is_not_a_decimal_point(self):
        """`84,299` read as 84.299 shrinks the rounding interval a thousandfold,
        and that is the accusing direction."""
        assert bind.read_literal("84,299")["numeric"] == 84299.0
        assert bind.read_literal("84,299")["decimals"] == 0

    def test_the_convention_is_the_documents_and_the_period_wins_a_tie(self):
        assert bind.decimal_convention("the mean was 1.67 (2.15) of 84,299") == "."
        assert bind.decimal_convention("der Mittelwert war 1,67 (2,15)") == ","
        assert bind.decimal_convention("no numbers here") == "."

    def test_under_a_comma_convention_the_comma_is_the_point(self):
        got = bind.read_literal("1,67", decimal_sep=",")
        assert got["printed_form"] == "plain" and got["numeric"] == 1.67
        assert got["decimals"] == 2
        got = bind.read_literal("84.299", decimal_sep=",")
        assert got["printed_form"] == "grouped_integer" and got["numeric"] == 84299.0

    def test_every_form_is_in_the_closed_vocabulary(self):
        for s in ("1.67", "85.94%", "84,299", "6-9", "Twenty-six", "approximately 84,000",
                  "p < .05", "", "1 = None, 2 = A little", "n/a", "±"):
            assert bind.read_literal(s)["printed_form"] in bind.PRINTED_FORMS

    def test_the_bridge_grammar_is_stricter_than_the_accounts(self):
        """Two independent readings of one literal. The bridge admits only
        `plain` and `percent`; everything the account can still make a number of
        -- a grouped integer above all -- it refuses."""
        assert checks._read_plain("84,299") is None
        assert bind.read_literal("84,299")["numeric"] == 84299.0
        assert checks._read_plain("85.94%") == {"value": 85.94, "decimals": 2,
                                                "is_percent": True}


# --------------------------------------------------------------------------
# The coordinate is a type, and the account's own verdict is read
# --------------------------------------------------------------------------


class TestTheCoordinateIsATypeNotATupleLiteral:
    """THE DEFECT THIS REPLACES WAS AN ARITY, NOT A VALUE. `_Index` built eight
    dictionaries over one value population with hand-written tuple keys, and two
    of them -- written months apart, ten lines apart -- disagreed about whether
    the phase was part of a coordinate. `bfc3a4b` fixed the instance; `Coord`
    is the attempt to make the instance unwriteable.

    WHAT IT ACTUALLY BUYS, STATED HONESTLY. Python has no static enforcement
    here and there is no type checker in CI, so nothing catches a bad key before
    the line runs. What the keyword-only, default-free constructor buys is that
    dropping an axis RAISES at the construction site instead of silently keying
    two-wide, and that dropping one deliberately has to be WRITTEN
    (`phase_id=None`) where a reviewer can see it in the diff.
    """

    def test_an_axis_cannot_be_dropped_by_omission(self):
        with pytest.raises(TypeError):
            checks.Coord(study_id="st:1", group_id="grp:a")     # the bfc3a4b shape
        with pytest.raises(TypeError):
            checks.Coord(study_id="st:1")

    def test_the_axes_cannot_be_supplied_positionally_either(self):
        """Positional construction is what would let two axes be passed where
        three are meant, silently, with the third defaulted."""
        with pytest.raises(TypeError):
            checks.Coord("st:1", "grp:a", None)

    def test_the_keys_are_the_arities_their_names_claim(self):
        c = checks.Coord(study_id="st:1", group_id="grp:a", phase_id="ph:1")
        assert c.key() == ("st:1", "grp:a", "ph:1")
        assert c.group_key() == ("st:1", "grp:a")
        assert c.var_key("var:mood") == ("st:1", "grp:a", "ph:1", "var:mood")
        assert c.at_phase(None).key() == ("st:1", "grp:a", None)
        assert c.at_group(None).key() == ("st:1", None, "ph:1")

    def test_a_coordinate_is_read_the_same_way_from_a_value_and_from_a_mapping(self):
        """The two readers that have to agree: a VALUE record (whose coordinate
        is nested) and a candidate's or census row's flat mapping."""
        v = {"coordinate": {"study_id": "st:1", "group_id": "grp:a", "phase_id": "ph:1"}}
        assert checks.Coord.of(v) == checks.Coord.from_mapping(v["coordinate"])
        assert checks.Coord.of({}) == checks.Coord(study_id=None, group_id=None,
                                                   phase_id=None)

    def test_the_index_keys_through_it(self, w7):
        """The live index, not a constructed one: every `n_at` key is a full
        three-axis coordinate and every `phases_with_n` key is a two-axis one."""
        idx = checks._Index(w7, W7_TEXT)
        assert idx.n_at, "the fixture prints an n"
        assert all(len(k) == 3 for k in idx.n_at)
        assert all(len(k) == 2 for k in idx.phases_with_n)
        assert all(len(k) == 4 for k in idx.by_coord_var)


class TestTheAccountsOwnIntegrityRecordIsRead:
    """`bind.assemble` writes `schema.validate_account`'s problems to
    `account["integrity_problems"]`, and until now only the RENDERER read them --
    so the bridge adjudicated values the account had already declared
    unbindable. Reading them can only ever REMOVE a check."""

    def test_a_clean_account_is_unaffected(self, w7, w7_checks):
        """THE NO-OP CASE, WHICH IS THE COMMON ONE. An empty problem list must
        change nothing at all."""
        assert w7["integrity_problems"] == []
        idx = checks._Index(w7, W7_TEXT)
        assert not idx.integrity_problems
        assert not any(r["reason"] == "account_integrity_problem"
                       for r in w7_checks["refused"])

    def test_a_value_the_account_calls_broken_is_refused_by_name(self, w7):
        acc = copy.deepcopy(w7)
        target = "val:t1:r2:c1:0:mean"
        # The real defect shape: a coordinate naming a group the structure never
        # declared. `validate_account` is the author of the message, not this
        # test.
        val = next(v for v in acc["values"] if v["id"] == target)
        val["coordinate"]["group_id"] = "grp:ghost"
        acc["integrity_problems"] = bind._schema.validate_account(acc)
        assert any("grp:ghost" in p for p in acc["integrity_problems"])
        got = checks.evaluate(acc, W7_TEXT)
        row = _refusal(got, f"chk:grim:{target}")
        assert row["reason"] == "account_integrity_problem"
        assert "grp:ghost" in row["reasons"][0]["detail"]

    def test_only_the_named_value_is_withdrawn(self, w7):
        """A dangling id on one value says nothing about the rest of the paper,
        so nothing else may be lost to it."""
        acc = copy.deepcopy(w7)
        target = "val:t1:r2:c1:0:mean"
        clean = checks.evaluate(acc, W7_TEXT)
        next(v for v in acc["values"]
             if v["id"] == target)["coordinate"]["group_id"] = "grp:ghost"
        acc["integrity_problems"] = bind._schema.validate_account(acc)
        got = checks.evaluate(acc, W7_TEXT)
        lost = ({r["check_id"] for r in clean["checks"]}
                - {r["check_id"] for r in got["checks"]})
        assert lost <= {f"chk:{fam}:{target}" for fam in ("grim", "grimmer", "sprite")}

    def test_every_value_problem_the_validator_writes_is_recognised(self):
        """THE PINNING TEST FOR THE ONE STRING JOIN. `values_with_problems`
        reads messages `validate_account` writes, so a message in a new shape
        must fail here rather than going quietly unread."""
        from forensic_metascience_ai_toolkit.scaffold import schema as _schema
        acc = {"studies": [{"id": "st:1", "groups": [], "phases": []}],
               "variables": [], "procedures": [], "comparisons": [], "claims": [],
               "values": [
                   {"id": "val:a", "statistic": "mean",
                    "coordinate": {"study_id": "st:nope"}},
                   {"id": "val:b", "statistic": "mean",
                    "coordinate": {"study_id": "st:1", "group_id": "grp:ghost"}},
                   {"id": "val:c", "statistic": "mean",
                    "coordinate": {"study_id": "st:1", "phase_id": "ph:ghost"}},
                   {"id": "val:d", "statistic": "mean",
                    "coordinate": {"study_id": "st:1"}, "variable_id": "var:ghost"},
                   {"id": "val:e", "statistic": "not_a_statistic",
                    "coordinate": {"study_id": "st:1"}},
                   {"id": "val:f", "statistic": "mean", "coordinate": {"study_id": "st:1"},
                    "reference_group_id": "grp:ghost"},
                   {"id": "val:f", "statistic": "mean", "coordinate": {"study_id": "st:1"}},
               ]}
        problems = _schema.validate_account(acc)
        # The criterion is INDEPENDENT of the pattern under test: a message is
        # about a value if it names one of the planted value ids.
        planted = {"val:a", "val:b", "val:c", "val:d", "val:e", "val:f"}
        about_values = [p for p in problems if any(f"`{v}`" in p for v in planted)]
        assert len(about_values) >= 7, problems
        assert _schema.values_with_problems(problems) == {
            "val:a", "val:b", "val:c", "val:d", "val:e", "val:f"}
        for p in about_values:
            assert _schema.values_with_problems([p]), f"unrecognised message: {p}"

    def test_it_does_not_read_a_problem_about_something_else(self):
        from forensic_metascience_ai_toolkit.scaffold import schema as _schema
        assert _schema.values_with_problems(
            ["variable `var:x` names unknown study `st:9`",
             "duplicate variable id `var:x`",
             "missing top-level key `values`",
             "comparison `cmp:1` names unknown study `st:9`"]) == set()


class TestACoordinateMayNameFewerThanThreeAxes:
    """`sid`'s missing guard, and what it cost.

    `validate_account`'s study check reads `if sid is not None and sid not in
    studies`. Its two siblings, written in the same breath, guarded `gid` and
    `pid` and NOT `sid` -- so a value naming a group and no study was asked
    whether `(None, gid)` was declared, which it never is, there being no study
    called `None`. The account was then reported as naming an unknown group "in
    `None`" while declaring that group perfectly well.

    MEASURED over the 17 paid reference accounts: 469 integrity problems, 461
    of them this shape, and every one of the 461 named an id the account
    DECLARES. `_Index` withdraws any candidate whose input the record names, so
    those false alarms refused 206 candidates as `account_integrity_problem` --
    the account calling itself broken -- rather than letting them reach the gate
    that would refuse them for a reason that is true. Under the fix all 206
    reach that gate and 204 are refused there by name (`no_paired_mean` 90,
    `binding_model_only` 86, `no_variable` 12, `no_group_n` 10,
    `printed_not_plain_numeral` 6); the remaining 2 are a real defect the fix
    deliberately keeps. No check ran that had not run before, and no verdict
    moved.

    THE GUARANTEE IS NOT WEAKENED, WHICH IS THE POINT. A part that names nothing
    is still named: where the value gives no study, the part is asked of EVERY
    study rather than of a study called `None`. That is the rule
    `reference_group_id` in the same function has always used.
    """

    @staticmethod
    def _at(acc: dict, vid: str) -> dict:
        return next(v for v in acc["values"] if v["id"] == vid)

    def test_a_group_named_without_a_study_is_not_a_problem(self, w7):
        """The 461. `grp:clinic` is declared; the value just does not say by whom."""
        acc = copy.deepcopy(w7)
        self._at(acc, "val:t1:r7:c2:1:percentage")["coordinate"]["study_id"] = None
        problems = bind._schema.validate_account(acc)
        assert not [p for p in problems if "val:t1:r7:c2:1:percentage" in p], problems

    def test_an_occasion_named_without_a_study_is_not_a_problem(self, w7):
        """The phase check had the same shape and the same omission."""
        acc = copy.deepcopy(w7)
        next(s for s in acc["studies"]
             if s["id"] == "study:clinic")["phases"] = [{"id": "phase:followup"}]
        self._at(acc, "val:t1:r7:c2:1:percentage")["coordinate"].update(
            {"study_id": None, "phase_id": "phase:followup"})
        problems = bind._schema.validate_account(acc)
        assert not [p for p in problems if "val:t1:r7:c2:1:percentage" in p], problems

    def test_a_group_declared_nowhere_still_fires_without_a_study(self, w7):
        """A NULL STUDY IS NOT A PASS. The part still has to name a record."""
        acc = copy.deepcopy(w7)
        self._at(acc, "val:t1:r7:c2:1:percentage")["coordinate"].update(
            {"study_id": None, "group_id": "grp:ghost"})
        problems = bind._schema.validate_account(acc)
        assert any("grp:ghost" in p and "val:t1:r7:c2:1:percentage" in p
                   for p in problems), problems

    def test_an_occasion_declared_nowhere_still_fires_without_a_study(self, w7):
        acc = copy.deepcopy(w7)
        self._at(acc, "val:t1:r7:c2:1:percentage")["coordinate"].update(
            {"study_id": None, "phase_id": "phase:ghost"})
        problems = bind._schema.validate_account(acc)
        assert any("phase:ghost" in p and "val:t1:r7:c2:1:percentage" in p
                   for p in problems), problems

    def test_a_group_the_named_study_does_not_declare_still_fires(self, w7):
        """THE CASE THE FIX MAY NOT COST US. `grp:clinic` exists, and
        `study:survey` does not have it -- which is a real referential defect and
        the reason the pair set is keyed by study at all."""
        acc = copy.deepcopy(w7)
        self._at(acc, "val:t1:r7:c2:1:percentage")["coordinate"].update(
            {"study_id": "study:survey", "group_id": "grp:clinic"})
        problems = bind._schema.validate_account(acc)
        assert any("grp:clinic" in p and "study:survey" in p
                   and "val:t1:r7:c2:1:percentage" in p for p in problems), problems

    def test_the_refusal_stops_being_an_accusation_about_the_account(self, w7):
        """THE CONSEQUENCE ON THE REAL ACCOUNTS, and it is why this is a defect
        rather than a cosmetic message. Move the percentage and its count off the
        study: every id still names a record, so the bridge must send the
        candidate to the gates that judge its premises. It is still refused --
        the denominator is a study away and cannot be shown to be this value's --
        but by a reason that is TRUE about the paper instead of a false one about
        the account. 204 of the 206 moved exactly like this."""
        acc = copy.deepcopy(w7)
        for vid in ("val:t1:r7:c2:0:count", "val:t1:r7:c2:1:percentage"):
            self._at(acc, vid)["coordinate"]["study_id"] = None
        acc["integrity_problems"] = bind._schema.validate_account(acc)
        got = checks.evaluate(acc, W7_TEXT)
        cid = "chk:count_percent:val:t1:r7:c2:1:percentage"
        row = _refusal(got, cid)
        assert row["reason"] != "account_integrity_problem"
        assert checks.REASONS[row["reason"]][0] in ("n", "binding", "literal",
                                                    "granularity", "bounds")

    def test_a_studyless_coordinate_whose_premises_hold_is_adjudicated(self, w7):
        """AND THE GATE GENUINELY OPENS, so the fix is not merely a rename. Give
        the studyless coordinate a denominator of its own that a second printed
        row corroborates -- the structure declares no n for a group at no study,
        so a lone integer there could be a count of events -- and the check runs
        and returns the tool's verdict."""
        acc = copy.deepcopy(w7)
        for vid in ("val:t1:r7:c2:0:count", "val:t1:r7:c2:1:percentage",
                    "val:t1:r1:c2:0:n"):
            self._at(acc, vid)["coordinate"]["study_id"] = None
        echo = copy.deepcopy(self._at(acc, "val:t1:r1:c2:0:n"))
        echo["id"] = "val:t1:r12:c2:0:n"
        echo["location"] = {**echo["location"], "row": 12, "row_label": "n analysed"}
        acc["values"].append(echo)
        acc["integrity_problems"] = bind._schema.validate_account(acc)
        assert acc["integrity_problems"] == []
        got = checks.evaluate(acc, W7_TEXT)
        ran = _ran(got, "chk:count_percent:val:t1:r7:c2:1:percentage")
        assert ran["args"]["n"] == 200
        assert ran["severity"] == "consistent"

    def test_a_studyless_coordinate_does_not_inherit_the_cohort_n(self, w7):
        """THE SAFETY PROBE FOR THE UNBLOCKING, and it is the documented route:
        no n at the value's own coordinate, fall through to a study-level n, and
        inherit the whole cohort's denominator. Leave the n where it was and move
        only the percentage. The check must NOT run -- a denominator this value
        cannot be shown to own is the guess the bridge exists to refuse -- and
        the refusal must name a premise rather than the account."""
        acc = copy.deepcopy(w7)
        self._at(acc, "val:t1:r7:c2:1:percentage")["coordinate"]["study_id"] = None
        self._at(acc, "val:t1:r7:c2:0:count")["coordinate"]["study_id"] = None
        acc["integrity_problems"] = bind._schema.validate_account(acc)
        assert acc["integrity_problems"] == []
        got = checks.evaluate(acc, W7_TEXT)
        cid = "chk:count_percent:val:t1:r7:c2:1:percentage"
        assert not [r for r in got["checks"] if r["check_id"] == cid], \
            "a studyless value took the clinic's 200 as its denominator"
        assert _refusal(got, cid)["reason"] != "account_integrity_problem"

    def test_a_studyless_coordinate_does_not_inherit_a_cohort_n_either(self, w7):
        """THE SAME PROBE WITH THE COHORT n ACTUALLY THERE, which is the route
        the integrity gate was written to block: no n at the value's own
        coordinate, a paper-level figure the sentence says applies to every
        group, and the arm inherits it. 146 of 294 is 49.7% against a printed
        73.0%, so an unguarded run would accuse this paper.

        The gate that stops it is `study_n_over_several_arms`, and it stops this
        shape for the reason it was widened in round 3: a study-level n is an
        arm's n only where that arm is the study's ONLY arm, which cannot be
        shown for a group the study does not list -- and a study called `None`
        lists nothing. So removing the false integrity alarm does not open this
        door; a guard that was always the right one is what holds it."""
        acc = copy.deepcopy(w7)
        for vid in ("val:t1:r7:c2:1:percentage", "val:t1:r7:c2:0:count"):
            self._at(acc, vid)["coordinate"]["study_id"] = None
        cohort = copy.deepcopy(self._at(acc, "val:t1:r1:c2:0:n"))
        cohort.update({"id": "val:cohort:n", "printed": "294", "numeric": 294.0,
                       "applies_to_all_groups": True,
                       "coordinate": {"study_id": None, "group_id": None,
                                      "phase_id": None}})
        echo = copy.deepcopy(cohort)
        echo["id"] = "val:cohort:n2"
        echo["location"] = {**echo["location"], "row": 13}
        acc["values"] += [cohort, echo]
        acc["integrity_problems"] = bind._schema.validate_account(acc)
        assert acc["integrity_problems"] == []
        got = checks.evaluate(acc, W7_TEXT)
        cid = "chk:count_percent:val:t1:r7:c2:1:percentage"
        assert not [r for r in got["checks"] if r["check_id"] == cid], \
            "a studyless arm divided by the whole cohort"
        assert _refusal(got, cid)["reason"] == "study_n_over_several_arms"
