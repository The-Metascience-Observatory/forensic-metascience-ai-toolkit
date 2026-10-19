"""The scaffold's deterministic half, on synthetic input.

Nothing here calls a model. The tests pin the properties the design argument
rests on: table numbers come from cells and never from the model; a printed
value must sit inside its quote; every numeral ends in exactly one disposition
with `unaccounted` allowed; a dangling id is an integrity problem; and the
applicability census names the missing premise instead of defaulting it.
"""

from __future__ import annotations

import json

import pytest

from metascience_agent.scaffold import applicability, bind, fontaudit, schema

# --------------------------------------------------------------------------
# A tiny paper: one table, one caption, one comparison.
# --------------------------------------------------------------------------

TEXT = """## RESULTS

Mice were injected with vehicle or drug 20 min before training (n = 6-9).
Drug significantly enhanced memory tested 24 h later (Figure 1a).

| | Veh | Drug |
|---|---|---|
| Weight | 23.0 (±0.40) | 24.83 (±0.48) |
| Whiskers (% with) | 100 | 100 |
| Pole test | 10.6 (±1.12) | 11.67 (±0.67) |

Figure 1 Drug enhances memory. (a) Data are mean (±SEM) % freezing (n = 6-9). *P<0.05.

## REFERENCES

Smith J (2001). A paper. J Things 12: 100-110.
"""


def _doc():
    from metascience_agent import numerals, sections
    secs = sections.map_sections(TEXT)
    cells = []
    rows = [("Weight", ["23.0 (±0.40)", "24.83 (±0.48)"]),
            ("Whiskers (% with)", ["100", "100"]),
            ("Pole test", ["10.6 (±1.12)", "11.67 (±0.67)"])]
    for ri, (rl, vals) in enumerate(rows, start=1):
        for ci, (cl, raw) in enumerate(zip(["Veh", "Drug"], vals), start=1):
            cells.append({"raw": raw, "row": ri, "col": ci, "row_label": rl, "col_label": cl})
    span_start = TEXT.index("| | Veh")
    span_end = TEXT.index("Figure 1 Drug") - 2
    nums = numerals.index(TEXT, tables_available=True)
    for r in nums:
        r["role"] = "back" if r["offset"] >= TEXT.index("## REFERENCES") else "results"
    return {
        "text": TEXT, "original_text": TEXT, "source": {}, "problems": [],
        "font_audit": {}, "repairs": {"n_repairs": 0}, "sections": secs,
        "tables": [{"id": "table:1", "label": "Table 1", "caption": None, "n_cells": len(cells),
                    "row_labels": [r[0] for r in rows], "col_labels": ["Veh", "Drug"],
                    "sections": [], "footnotes": [], "n_header_rows": 1, "header_rows": None,
                    "text_span": [span_start, span_end], "cells": cells}],
        "figures": [{"id": "figure:1", "label": "Figure 1", "panels": ["a"], "n_panels": 1}],
        "supplements_referenced": [], "numerals": nums, "numeral_floor": numerals.tally(nums),
    }


P1 = {
    "paper": {"title": "T", "authors": ["A"], "journal": None, "year": None, "doi": None,
              "species_or_population": "mice"},
    "background": {"problem": "", "prior_findings": [], "gap": "", "aims": []},
    "subjects": {"population": None, "unit_of_analysis": None, "setting": None, "recruitment": None,
                 "eligibility": None, "species": "mouse", "strain": None, "sex": None, "age": None, "supplier": None,
                 "housing": None, "total_n_stated": False, "quote": "Mice were injected"},
    "statistical_analysis": {"methods_quote": "", "tests_named": [], "alpha_declared": None,
                             "alpha_quote": None, "significance_legend": [], "detailed_statistics_location": None,
                             "test_to_experiment_mapping_in_main_text": False},
    "phases": [],
    "procedures": [{"id": "proc:cfc", "name": "CFC", "section_heading": "Methods", "summary": "", "scored_blind": None}],
    "studies": [{
        "id": "study:memory", "label": "Memory", "aim": "", "section_heading": "RESULTS",
        "reported_in": [{"kind": "figure", "label": "Figure 1", "panels": ["a"]}, {"kind": "table", "label": "Table 1", "panels": []}],
        "design_type": "between_subjects", "design_description": "veh vs drug",
        "n_range_printed": "6-9", "n_range_quote": "(n = 6-9)", "n_scope": "per_group_range",
        "groups": [{"id": "grp:veh", "label": "Veh", "description": "", "n_printed": None, "n_quote": None},
                   {"id": "grp:drug", "label": "Drug", "description": "", "n_printed": None, "n_quote": None}],
        "phases": [{"id": "phase:test_24h", "label": "Test 24 h", "when": "24 h after training"}],
        "outcomes_described": ["% freezing"], "manipulations_described": ["drug"],
        "result_summary_quotes": ["Drug significantly enhanced memory tested 24 h later (Figure 1a)."],
        "interpretation_quotes": [], "procedure_ids": ["proc:cfc"],
    }],
    "claims": [{"id": "claim:1", "text": "Drug enhances memory.", "location": "figure_caption",
                "kind": "finding", "study_ids": ["study:memory"], "hedged": False,
                "generalizes_beyond_sample": False, "causal": False}],
    "supplements_referenced": [],
}

P2 = {
    "variables": [
        {"id": "var:treatment", "name": "Treatment", "role": "manipulated_factor", "kind": "categorical",
         "units": None, "units_source": "not_stated",
         "bounds": {"lower": None, "upper": None, "source": "not_stated", "quote": None},
         "granularity": {"per_subject_step": None, "basis": None, "quote": None},
         "derivation": None, "derived_from": [], "procedure_id": None, "printed_as": [],
         "levels": [{"id": "lvl:veh", "label": "vehicle", "value": None, "units": None},
                    {"id": "lvl:drug", "label": "drug", "value": None, "units": None}],
         "studies_using": ["study:memory"], "quote": "vehicle or drug", "notes": None},
        {"id": "var:weight", "name": "Body weight", "role": "measured_outcome", "kind": "continuous",
         "units": None, "units_source": "not_stated",
         "bounds": {"lower": None, "upper": None, "source": "not_stated", "quote": None},
         "granularity": {"per_subject_step": None, "basis": None, "quote": None},
         "derivation": None, "derived_from": [], "procedure_id": None, "printed_as": [], "levels": [],
         "studies_using": ["study:memory"], "quote": "Weight", "notes": None},
        {"id": "var:whiskers", "name": "Whiskers present", "role": "measured_outcome",
         "kind": "percentage_of_subjects", "units": "%", "units_source": "stated",
         "bounds": {"lower": 0, "upper": 100, "source": "definitional", "quote": "% with"},
         "granularity": {"per_subject_step": None, "basis": "group-level percentage", "quote": None},
         "derivation": None, "derived_from": [], "procedure_id": None, "printed_as": [], "levels": [],
         "studies_using": ["study:memory"], "quote": "Whiskers (% with)", "notes": None},
        {"id": "var:pole", "name": "Pole test score", "role": "measured_outcome", "kind": "integer_score",
         "units": None, "units_source": "not_stated",
         "bounds": {"lower": 0, "upper": 15, "source": "definitional", "quote": "0 or 1"},
         "granularity": {"per_subject_step": 1, "basis": "integer score", "quote": None},
         "derivation": None, "derived_from": [], "procedure_id": None, "printed_as": [], "levels": [],
         "studies_using": ["study:memory"], "quote": "Pole test", "notes": None},
    ],
    "group_coordinates": [
        {"study_id": "study:memory", "group_id": "grp:veh", "assignments": [{"variable_id": "var:treatment", "level_id": "lvl:veh"}]},
        {"study_id": "study:memory", "group_id": "grp:drug", "assignments": [{"variable_id": "var:treatment", "level_id": "lvl:drug"}]},
    ],
    "phase_coordinates": [], "procedure_parameters": [
        {"procedure_id": "proc:cfc", "variable_id": None, "name": "injection-to-training interval",
         "printed": "20", "numeric": 20, "units": "min",
         "quote": "injected with vehicle or drug 20 min before training"}],
    "outcome_bindings": [{"study_id": "study:memory", "variable_ids": ["var:weight", "var:whiskers", "var:pole"]}],
    "population_descriptors": [],
}

P3 = {
    "table_readings": [{
        "table_id": "table:1", "caption": None, "n_per_column_stated": False, "n_note": "no n in the table",
        "column_map": [{"col_label": "Veh", "study_id": "study:memory", "group_id": "grp:veh", "phase_id": None},
                       {"col_label": "Drug", "study_id": "study:memory", "group_id": "grp:drug", "phase_id": None}],
        "row_map": [{"row_label": "Weight", "variable_id": "var:weight", "statistic_form": "mean_pm_unstated",
                     "dispersion_stated_where": None, "note": None},
                    {"row_label": "Whiskers (% with)", "variable_id": "var:whiskers",
                     "statistic_form": "percentage_of_subjects", "dispersion_stated_where": None, "note": None},
                    {"row_label": "Pole test", "variable_id": "var:pole", "statistic_form": "mean_pm_unstated",
                     "dispersion_stated_where": None, "note": None}],
    }],
    "prose_values": [{
        "id": "val:n_range", "variable_id": None, "statistic": "n_range", "printed": "6-9", "numeric": None,
        "units": None, "coordinate": {"study_id": "study:memory", "group_id": None, "phase_id": None},
        "applies_to_all_groups": True, "quote": "(n = 6-9)", "location": "results", "note": None,
    }, {
        "id": "val:invented", "variable_id": None, "statistic": "n", "printed": "42", "numeric": 42,
        "units": None, "coordinate": {"study_id": "study:memory", "group_id": None, "phase_id": None},
        "applies_to_all_groups": False, "quote": "Drug significantly enhanced memory", "location": "results",
        "note": None,
    }],
    "comparisons": [{
        "id": "cmp:drug_vs_veh_24h", "study_id": "study:memory", "outcome_variable_id": None,
        "contrast": {"group_ids": ["grp:veh", "grp:drug"], "phase_ids": ["phase:test_24h"], "description": "drug vs veh"},
        "test_type_stated": None, "test_type_quote": None, "post_hoc_stated": None,
        "statistic_printed": None, "df_printed": None, "p_printed": None,
        "p_threshold": None, "significance": "significant", "direction": "second_higher",
        "direction_words": "drug higher", "reported_in_kind": "figure", "reported_in": "Figure 1a", "quote": "Drug significantly enhanced memory tested 24 h later",
        "detailed_statistics_elsewhere": None,
    }],
    "figure_panels": [{"figure": "Figure 1", "panel": "a", "study_id": "study:memory", "y_variable_id": None,
                       "group_ids": ["grp:veh", "grp:drug"], "phase_ids": ["phase:test_24h"],
                       "n_printed": "6-9", "error_bar": "SEM", "caption_quote": "Data are mean (±SEM) % freezing"}],
}


@pytest.fixture(scope="module")
def account():
    return bind.assemble(_doc(), P1, P2, P3)


class TestSchemas:
    def test_every_pass_schema_is_valid_json_schema(self):
        import jsonschema
        for name in ("pass1", "pass2", "pass3", "residual"):
            jsonschema.Draft202012Validator.check_schema(schema.pass_schema(name))

    def test_pass_outputs_here_validate(self):
        import jsonschema
        jsonschema.validate(P1, schema.pass_schema("pass1"))
        jsonschema.validate(P2, schema.pass_schema("pass2"))
        jsonschema.validate(P3, schema.pass_schema("pass3"))

    def test_unknown_pass_is_refused(self):
        with pytest.raises(KeyError):
            schema.pass_schema("pass9")


class TestTableValuesComeFromCells:
    def test_mean_pm_cell_yields_mean_and_dispersion(self):
        assert bind.cell_components("23.0 (±0.40)", "mean_pm_unstated") == [
            ("mean", "23.0"), ("dispersion_unstated", "0.40")]
        assert bind.cell_components("23.0 (±0.40)", "mean_pm_sem")[1][0] == "sem"

    def test_a_cell_that_does_not_fit_the_form_is_not_guessed(self):
        assert bind.cell_components("n.s.", "mean_pm_sem") == []
        assert bind.cell_components("12/40", "percentage_of_subjects") == []

    def test_every_table_value_carries_its_cell_and_coordinate(self, account):
        tv = [v for v in account["values"] if v["source"] == "table"]
        assert len(tv) == 2 * 2 + 2 + 2 * 2   # weight mean+disp x2, whiskers x2, pole mean+disp x2
        for v in tv:
            assert v["location"]["table_id"] == "table:1"
            assert v["coordinate"]["study_id"] == "study:memory"
            assert v["coordinate"]["group_id"] in ("grp:veh", "grp:drug")
            assert v["quote"] and v["quote_verified"] == "cell"   # the cell text is the quote
        pole = [v for v in tv if v["variable_id"] == "var:pole" and v["statistic"] == "mean"]
        assert sorted(v["printed"] for v in pole) == ["10.6", "11.67"]


class TestProseValues:
    def test_a_printed_value_outside_its_quote_is_flagged(self, account):
        bad = next(v for v in account["values"] if v["id"] == "val:invented")
        assert bad["printed_in_quote"] is False
        assert any("val:invented" in p for p in account["problems"])

    def test_a_range_stays_a_range(self, account):
        rng = next(v for v in account["values"] if v["id"] == "val:n_range")
        assert rng["statistic"] == "n_range" and rng["printed"] == "6-9" and rng["numeric"] is None
        assert rng["quote_verified"] == "verbatim"

    def test_procedure_parameters_become_setting_values(self, account):
        s = [v for v in account["values"] if v["source"] == "methods_parameter"]
        assert len(s) == 1 and s[0]["printed"] == "20" and s[0]["units"] == "min"


class TestAccounting:
    def test_every_in_scope_numeral_has_exactly_one_disposition(self, account):
        rows = account["accounting"]
        assert rows, "nothing was indexed"
        assert all(r["disposition"] in schema.NUMERAL_DISPOSITIONS or r["disposition"] == "coordinate_label"
                   for r in rows)
        assert all(r.get("role") != "back" for r in rows), "reference-list numerals are out of scope"

    def test_table_cell_numerals_bind_to_table_values(self, account):
        bound = [r for r in account["accounting"] if r["disposition"] == "value"
                 and r["value_id"] and r["value_id"].startswith("val:t1:")]
        # 23.0 0.40 24.83 0.48 100 100 10.6 1.12 11.67 0.67 = 10 cell numerals
        assert len(bound) == 10

    def test_unaccounted_is_reported_not_hidden(self, account):
        c = account["completeness"]
        assert c["numerals_unaccounted"] == c["by_disposition"].get("unaccounted", 0)
        assert sum(c["three_buckets"].values()) == c["numerals_in_scope"]
        assert c["numerals_in_scope"] == sum(c["by_disposition"].values())
        assert 0 < c["share_accounted"] <= 1

    def test_residual_cannot_bind_to_a_value_that_does_not_exist(self, account):
        rows = [dict(r) for r in account["accounting"]]
        target = next(r for r in rows if r["disposition"] == "unaccounted")
        rows2, problems = bind.apply_residual(rows, {"dispositions": [
            {"numeral_id": target["id"], "disposition": "value", "value_id": "val:nope",
             "candidates": [], "distinguisher": None, "note": None}],
            "new_values": []}, {v["id"] for v in account["values"]})
        assert next(r for r in rows2 if r["id"] == target["id"])["disposition"] == "unaccounted"
        assert problems and "does not exist" in problems[0]

    def test_ambiguous_needs_two_candidates_and_is_its_own_bucket(self, account):
        rows = [dict(r) for r in account["accounting"]]
        targets = [r for r in rows if r["disposition"] == "unaccounted"][:2]
        assert len(targets) == 2
        cand = {"study_id": "study:memory", "group_id": "grp:veh", "phase_id": None,
                "variable_id": None, "statistic": "n", "why": "could be the n"}
        rows2, problems = bind.apply_residual(rows, {"dispositions": [
            {"numeral_id": targets[0]["id"], "disposition": "ambiguous", "value_id": None,
             "candidates": [cand, {**cand, "statistic": "timepoint", "why": "or the hours"}],
             "distinguisher": "a per-group n statement", "note": None},
            {"numeral_id": targets[1]["id"], "disposition": "ambiguous", "value_id": None,
             "candidates": [cand], "distinguisher": None, "note": None}],
            "new_values": []}, {v["id"] for v in account["values"]})
        a = next(r for r in rows2 if r["id"] == targets[0]["id"])
        b = next(r for r in rows2 if r["id"] == targets[1]["id"])
        assert a["disposition"] == "ambiguous" and len(a["candidates"]) == 2
        assert b["disposition"] == "unaccounted" and any("1 candidate" in p for p in problems)

    def test_residual_cannot_override_a_deterministic_disposition(self, account):
        rows = [dict(r) for r in account["accounting"]]
        target = next(r for r in rows if r["disposition"] == "value")
        rows2, _ = bind.apply_residual(rows, {"dispositions": [
            {"numeral_id": target["id"], "disposition": "axis_tick", "value_id": None,
             "candidates": [], "distinguisher": None, "note": None}],
            "new_values": []}, {v["id"] for v in account["values"]})
        assert next(r for r in rows2 if r["id"] == target["id"])["disposition"] == "value"


class TestIntegrityAndGaps:
    def test_a_clean_account_has_no_integrity_problems(self, account):
        assert account["integrity_problems"] == []

    def test_a_dangling_id_is_an_integrity_problem(self):
        p3 = json.loads(json.dumps(P3))
        p3["prose_values"][0]["coordinate"]["group_id"] = "grp:ghost"
        acc = bind.assemble(_doc(), P1, P2, p3)
        assert any("grp:ghost" in p for p in acc["integrity_problems"])

    def test_gaps_name_the_missing_premises(self, account):
        kinds = {g["kind"] for g in account["gaps"]}
        assert "per_group_n_not_stated" in kinds
        assert "table_n_not_stated" in kinds
        assert "dispersion_kind_not_stated" in kinds
        assert "test_not_named_for_comparison" in kinds

    def test_a_discarded_table_reading_is_a_docketed_gap(self):
        # A reading bought and refused leaves the walker's grid typing every cell
        # of that table. That is an absence a reader has to be able to find, and
        # it is OURS rather than the paper's, so it is named and costed rather
        # than left as one sentence in `problems`.
        doc = _doc()
        doc["tables"][0]["reconstruction"] = {
            "table_id": "table:1", "status": "refused", "cost_usd": 0.42,
            "verification": {"verified": False, "reasons": ["1 digit run(s) ..."], "basis": "region"},
            "substitution": {"happened": True, "why": ["1 digit run(s) ..."], "basis": "region",
                             "reading_cost_usd": 0.42, "n_entries_discarded": 7,
                             "reading_kept_at": ["tables/table_1.recon.json"],
                             "consequence": "typed from the walker's grid"}}
        acc = bind.assemble(doc, P1, P2, P3)
        g = next(g for g in acc["gaps"] if g["kind"] == "table_reading_bought_and_discarded")
        assert g["table_id"] == "table:1" and g["cost_usd"] == 0.42
        assert g["n_entries_discarded"] == 7 and g["reading_kept_at"] == "tables/table_1.recon.json"
        assert not any(g["kind"] == "table_reading_bought_and_discarded"
                       for g in bind.assemble(_doc(), P1, P2, P3)["gaps"]), "and it is silent otherwise"


class TestApplicability:
    def test_grim_is_blocked_by_the_missing_n_not_defaulted(self, account):
        cen = applicability.census(account)
        grim = next(f for f in cen["families"] if f["family"] == "grim")
        # Pole test: mean present, step present (integer score), n absent -> blocked by group_n.
        assert grim["n_bindable"] == 0
        assert grim["blocked_by"].get("group_n") == 2

    def test_supplying_the_n_makes_grim_bindable(self, account):
        acc = json.loads(json.dumps(account))
        for gid, n in (("grp:veh", "5"), ("grp:drug", "6")):
            acc["values"].append({"id": f"val:n:{gid}", "statistic": "n", "printed": n, "numeric": float(n),
                                  "decimals": 0, "units": None, "variable_id": None,
                                  "coordinate": {"study_id": "study:memory", "group_id": gid, "phase_id": None},
                                  "applies_to_all_groups": False, "source": "prose",
                                  "location": {"kind": "prose"}, "quote": f"n = {n}",
                                  # THE FIELD IS PART OF THE VALUE, and a hand-built row
                                  # that omits it is not a row the pipeline produces:
                                  # `bind._prose_values` always writes it. Wave 7b made an
                                  # ABSENT `printed_in_quote` mean NOT VERIFIED rather than
                                  # verified, so the census (which now reads the same
                                  # premise the bridge does) would otherwise skip these.
                                  "printed_in_quote": True, "quote_verified": "verbatim"})
        cen = applicability.census(acc)
        grim = next(f for f in cen["families"] if f["family"] == "grim")
        assert grim["n_bindable"] == 2
        cp = next(f for f in cen["families"] if f["family"] == "count_percent")
        assert cp["n_bindable"] == 2

    def test_bounds_check_binds_where_bounds_are_definitional(self, account):
        cen = applicability.census(account)
        rb = next(f for f in cen["families"] if f["family"] == "range_within_bounds")
        # whiskers (0-100 definitional) x2 and pole (0-15 definitional) x2; weight has no bounds.
        assert rb["n_bindable"] == 4
        assert rb["blocked_by"].get("variable_bounds") == 2

    def test_claim_check_is_blocked_by_undeclared_alpha(self, account):
        cen = applicability.census(account)
        cl = next(f for f in cen["families"] if f["family"] == "claim_vs_result")
        assert cl["n_bindable"] == 0 and cl["blocked_by"] == {"declared_alpha": 1}


class TestRenderIsTheVerificationInstrument:
    """Every element a reader would check must be visible with its provenance."""

    def test_render_shows_each_layer_with_a_quote_or_cell_beside_it(self, account):
        from metascience_agent.scaffold import render
        md = render.render(account)
        for heading in ("## 0. Headline coverage", "## 1. Structure",
                        "## How to verify this account",
                        "## 5. Studies", "## 6. Variables",
                        "## 7. Tables, as read", "## 9. Claims", "## 10. Gaps",
                        "## 11. Repairs", "## 14. Inventory", "## 15. Check applicability",
                        "## 16. Checks run on the account's own premises",
                        "## 17. What this form cannot show"):
            assert heading in md, heading
        # the range n is shown as printed, with its quote
        assert "6-9" in md and "(n = 6-9)" in md
        # a table value appears as the cell text, and the reading names the row's variable
        assert "23.0" in md and "mean_pm_unstated" in md
        # the flagged prose value is visibly flagged, not silently dropped
        assert "printed value NOT in its quote" in md
        # the unaccounted list is printed, not summarised away
        assert "### Unplaced numerals (" in md and "### Ambiguous numerals (" in md
        # the sentence-level and template bookkeeping reach the reader too
        assert "### Sentence accountability" in md and "Uncovered sentences (" in md
        assert "### Design template problems" in md

    def test_render_never_restates_a_value_the_account_lacks(self, account):
        from metascience_agent.scaffold import render
        md = render.render(account)
        assert "9999" not in md


class TestTableSpan:
    def test_table_is_found_even_after_spacing_repairs(self):
        """The walker's cell reads `23.0 ( ± 0.40)`; the repaired body reads
        `23.0 (±0.40)`. A literal match found no table, so every table numeral
        fell out of the accounting (measured on Stern 2014, 2026-09-05)."""
        from metascience_agent.scaffold import document
        text = "intro\n\n| | Veh |\n|---|---|\n| Weight | 23.0 (±0.40) |\n| Pole | 10.6 (±1.12) |\n\nafter"
        cells = [{"raw": "23.0 ( ± 0.40)"}, {"raw": "10.6 ( ± 1.12)"}]
        span = document._table_span(text, cells)
        assert span is not None
        assert text[span[0]:span[1]].startswith("| | Veh |")
        assert "10.6" in text[span[0]:span[1]]


class TestLinearChunks:
    """Ordered service is structural: chunks tile the analytic text in order,
    exclude back matter, and every in-scope numeral is served exactly once."""

    def test_chunks_tile_the_analytic_text_in_order(self):
        from metascience_agent.scaffold import linear
        doc = _doc()
        for s in doc["sections"]:
            s["role"] = "back" if s["name"].startswith("references") else "results"
        cs = linear.chunks(doc)
        assert cs, "no chunks"
        assert [c["id"] for c in cs] == [f"chunk:{i}" for i in range(1, len(cs) + 1)]
        for a, b in zip(cs, cs[1:]):
            assert a["end"] <= b["start"]
        assert all("REFERENCES" not in c["text"] for c in cs)
        served = [n["numeral_id"] for c in cs for n in c["numerals"]]
        in_scope = [r["id"] for r in doc["numerals"] if r["role"] != "back"]
        assert sorted(served) == sorted(in_scope)
        assert len(served) == len(set(served))
        assert any(c["has_table"] for c in cs)

    def test_chunk_schema_requires_dispositions(self):
        from metascience_agent.scaffold import linear
        import jsonschema
        sch = linear.chunk_schema()
        jsonschema.Draft202012Validator.check_schema(sch)
        assert "numeral_dispositions" in sch["required"]


class TestFontAudit:
    def test_symbol_fonts_are_recognised_and_body_fonts_are_not(self):
        for name in ("AdvPi1", "AdvPi2", "AdvP4C4E74", "AdvEls-ent4", "AdvEls-Ent1", "Symbol",
                     "AdvItcSymbol-M", "AdvTA42", "Wingdings-Regular"):
            assert fontaudit._is_symbol_font(name), name
        for name in ("AdvMinionTB-R", "AdvGillSan-L", "Helvetica", "Palatino-Roman", "Capitals", "ArialMT"):
            assert not fontaudit._is_symbol_font(name), name

    def test_repair_edits_only_the_slot_and_logs_it(self):
        text = "were injected with 5, 15, 30, 45, 60, or 100 m g/kg of IGF-II or vehicle. Ketamine (100 mg/kg)."
        audit = {"suspects": [{"page": 4, "font": "AdvPi1", "char": "m", "codepoint": "U+006D",
                               "line": "with 5, 15, 30, 45, 60, or 100 mg/kg of IGF-II or vehicle",
                               "index_in_line": 31, "line_bbox": [0, 0, 1, 1]}]}
        res = fontaudit.apply_glyph_map(text, audit, {"AdvPi1": {"m": "µ"}})
        assert res["n_applied"] == 1
        assert "or 100 µg/kg of IGF-II" in res["text"]
        assert "Ketamine (100 mg/kg)" in res["text"], "the body-font milligrams are untouched"
        r = res["repairs"][0]
        assert r.rule == "scaffold.fontaudit" and "AdvPi1" in r.reason and r.offset is not None
        assert text[r.offset:r.offset + len(r.before)] == r.before

    def test_adjacent_suspects_do_not_block_each_other(self):
        text = "(Post, n ¼ 7). * P o 0.05, ** P o 0.01, *** P o 0.001."
        line = "(Post, n ¼ 7). *Po0.05, **Po0.01, ***Po0.001."
        # only the three `o` glyphs standing for `<` -- not the `o` in `Post`
        idx = [i for i, c in enumerate(line) if c == "o" and line[i - 1] == "P" and line[i + 1] == "0"]
        audit = {"suspects": [{"page": 5, "font": "AdvEls-ent4", "char": "o", "codepoint": "U+006F",
                               "line": line, "index_in_line": i, "line_bbox": [0, 0, 1, 1]} for i in idx]}
        res = fontaudit.apply_glyph_map(text, audit, {"AdvEls-ent4": {"o": "<"}})
        assert res["n_applied"] == 3 and res["unlocated"] == []
        assert "P<0.05" in res["text"] and "P<0.01" in res["text"] and "P<0.001" in res["text"]

    def test_an_unmapped_suspect_is_reported_and_left_alone(self):
        text = "GSK3 b activation"
        audit = {"suspects": [{"page": 10, "font": "AdvPi2", "char": "b", "codepoint": "U+0062",
                               "line": "GSK3b activation", "index_in_line": 4, "line_bbox": [0, 0, 1, 1]}]}
        res = fontaudit.apply_glyph_map(text, audit, {})
        assert res["n_applied"] == 0 and res["text"] == text and len(res["unmapped"]) == 1


class TestPass3InParts:
    def test_verified_tables_are_not_re_read_and_unread_ones_are_batched(self):
        from metascience_agent.scaffold import prompts as PR
        def t(i, n, verified=False):
            return {"id": f"table:{i}", "label": f"Table {i}", "n_cells": n, "cells": [], "col_labels": [], "row_labels": [],
                    "reconstruction": {"status": "verified"} if verified else {"status": "not_attempted"}}
        tables = [t(1, 40, True), t(2, 100), t(3, 120), t(4, 200), t(5, 60), t(6, 300)]
        main, batches = PR.pass3_batches(tables, budget=250)
        assert [x["id"] for x in main] == ["table:2", "table:3"], "up to the budget, in order"
        assert [[x["id"] for x in b] for b in batches] == [["table:4"], ["table:5"], ["table:6"]], (
            "each batch within the budget; an oversized table alone")
        assert not any(x["id"] == "table:1" for b in [main] + batches for x in b), "a verified table is entries already"

    def test_the_main_prompt_names_the_tables_read_elsewhere(self):
        from metascience_agent.scaffold import prompts as PR
        tables = [{"id": "table:1", "label": "Table 1", "n_cells": 3, "cells": [], "col_labels": [], "row_labels": [],
                   "caption": "c", "reconstruction": {"status": "verified"}}]
        p = PR.pass3_prompt("text", {"studies": []}, {"variables": []}, tables, [])
        assert "TABLES ALREADY READ AS ENTRIES" in p and "already read as entries" in p
        assert "RESULTS TEXT or a figure caption" in p
        tp = PR.pass3_tables_prompt({"studies": []}, {"variables": []}, tables)
        assert "TABLES ONLY" in tp and "Table 1" in tp


    def test_merged_readings_are_one_per_table(self):
        from metascience_agent.scaffold import prompts as PR
        rs = [{"table_id": "table:1", "x": 1}, {"table_id": "table:2"}, {"table_id": "table:1", "x": 2}]
        out = PR.dedupe_readings(rs)
        assert [r["table_id"] for r in out] == ["table:1", "table:2"] and out[0]["x"] == 1
