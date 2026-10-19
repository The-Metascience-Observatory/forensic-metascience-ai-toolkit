"""The harness GRIM sweep (`grim_harness`): premises, n sources, filing.

Synthetic tables use the cell shape every reader emits:
`{row, col, raw, row_label, col_label}`.
"""

import json

import pytest

from metascience_agent import findings_v2
from metascience_agent import grim_harness as G  # noqa: N812

LIKERT = {"id": "v_item", "name": "a 1-9 item", "family": "likert_item",
          "discreteness": "discrete", "lower_bound": 1, "upper_bound": 9}
SHARE = {"id": "v_share", "name": "share of participants", "family": "binary"}


def _table(rows, cols, label="Table 2", caption=None):
    """`rows`: [(row_label, [raw per data column])]; `cols`: column labels."""
    cells = []
    for r, (lab, values) in enumerate(rows, start=2):
        for c, raw in enumerate(values, start=1):
            cells.append({"row": r, "col": c, "raw": raw, "row_label": lab,
                          "col_label": cols[c - 1]})
    return {"label": label, "caption": caption, "cells": cells}


class TestColumnN:
    def test_the_innermost_header_n_is_the_columns_own(self):
        t = _table([("x", ["1"])], ["All, n = 318 | Drug (n = 117)"])
        assert G.column_ns(t)[1] == {"n": 117, "source": "header",
                                     "text": "All, n = 318 | Drug (n = 117)",
                                     "also": []}

    def test_a_grouping_header_alone_gives_no_n(self):
        # 318 covers several columns; it is no single column's denominator.
        t = _table([("x", ["1"])], ["All, n = 318 | Drug"])
        assert 1 not in G.column_ns(t)

    def test_a_header_row_printed_in_the_body_is_read(self):
        # Cureus: `Group 1 (n=70)` in <tbody>, no <thead>.
        t = _table([("(unlabelled row)", ["Group 1 (n=70)", "Group 2 (n=70)"]),
                    ("POST", ["14.3", "17.1"])], ["col1", "col2"])
        cols = G.column_ns(t)
        assert cols[1]["n"] == 70 and cols[1]["source"] == "header_row"

    def test_a_declared_n_fills_a_column_without_one(self):
        t = _table([("x", ["46.3"])], ["Consultant | Uni. staff"])
        cols = G.column_ns(t, {"columns": [{"col": 1, "n": 41, "quote": "41"}]})
        assert cols[1]["n"] == 41 and cols[1]["source"] == "declared"

    def test_disagreeing_sources_give_no_n(self):
        t = _table([("x", ["46.3"])], ["Drug (n = 40)"])
        cols = G.column_ns(t, {"columns": [{"col": 1, "n": 41}]})
        assert cols[1]["n"] is None and "disagree" in cols[1]["why"]


class TestPremise:
    def _target(self, raw, row="Male", col="Drug (n = 40)", decl=None, vars_=()):
        t = _table([(row, [raw])], [col])
        from metascience_agent.prepass import _typed
        cell = _typed(t["cells"])[0]
        return G.target_of(cell, t, decl, {v["id"]: v for v in vars_})

    def test_a_printed_n_percent_needs_no_declaration(self):
        tgt = self._target("12 (30.0)", row="Male, n (%)")
        assert tgt["what"] == "percent" and tgt["premise"] == "printed_count"

    def test_a_bare_percentage_is_refused_without_a_declaration(self):
        # HbA1c, % is a measurement; only a declaration can say it is a share.
        tgt = self._target("46.3", row="Male, %")
        assert "declaration" in tgt["refused"]

    def test_percent_of_units_makes_a_bare_number_a_share(self):
        tgt = self._target("46.3", row="Male", decl={"percent_of_units": True})
        assert tgt["premise"] == "declared_share" and tgt["decimals"] == 1

    def test_a_mean_without_a_variable_is_refused(self):
        assert "no variable" in self._target("3.48 (1.20)", row="Mood, mean (SD)")["refused"]

    def test_a_declared_item_mean_is_checked(self):
        tgt = self._target("6.64 (2.06)", row="I was hungry",
                           decl={"default_variable_id": "v_item"}, vars_=[LIKERT])
        assert tgt["what"] == "mean" and tgt["items"] == 1

    def test_an_averaged_subscale_is_refused(self):
        # Kelly's PCIT survey: the commonest GRIM false alarm.
        sub = {"id": "v_sub", "family": "likert_composite",
               "derivation": "mean_of_items"}
        tgt = self._target("3.48 (1.20)", row="ECBI", decl={"default_variable_id": "v_sub"},
                           vars_=[sub])
        assert tgt.get("refused")

    def test_a_continuous_variable_is_refused(self):
        cont = {"id": "v_w", "family": "continuous"}
        tgt = self._target("72.3 (18.2)", row="Weight",
                           decl={"default_variable_id": "v_w"}, vars_=[cont])
        assert "not integer-valued" in tgt["refused"]

    @pytest.mark.parametrize("col", ["F -test ( P value)", "t", "P Value",
                                     "F-Statistics | Effect of price"])
    def test_a_test_statistic_column_is_never_a_mean(self, col):
        tgt = self._target("0.42 (0.52)", row="I was hungry", col=col,
                           decl={"default_variable_id": "v_item"}, vars_=[LIKERT])
        assert tgt.get("refused") and tgt.get("silent")


class TestCheckCell:
    def test_a_failure_at_a_header_n_is_retested_for_nonresponse(self):
        # 55% of 50 is 27.5: impossible at 50, but 27/49 prints 55%.
        tgt = {"what": "percent", "value": 55.0, "decimals": 0}
        v = G.check_cell(tgt, {"n": 50, "source": "header"})
        assert v["status"] == "explained_by_nonresponse" and v["consistent_at_n"] == 49

    def test_a_failure_no_nearby_n_explains_stays_a_failure(self):
        # 66.9% is unreachable for every n from 67 to 70.
        tgt = {"what": "percent", "value": 66.9, "decimals": 1}
        v = G.check_cell(tgt, {"n": 70, "source": "header_row"})
        assert v["status"] == "inconsistent"

    def test_a_truncated_percentage_is_rounding_only_not_a_failure(self):
        # Cureus Table 1: 41 (58%) at n = 70 is 58.57%, which truncates to 58.
        tgt = {"what": "percent", "value": 58.0, "decimals": 0, "count": 41}
        v = G.check_cell(tgt, {"n": 70, "source": "header_row"})
        assert v["status"] == "rounding_only"

    def test_a_printed_count_is_not_swapped_for_another_one(self):
        # 41 (57.0%) at n = 70: 40/70 = 57.1% would print it, but the paper
        # printed 41, and 41/m prints 57.0 for no m in 67..69.
        tgt = {"what": "percent", "value": 57.0, "decimals": 1, "count": 41}
        v = G.check_cell(tgt, {"n": 70, "source": "header_row"})
        assert v["status"] == "inconsistent"

    def test_a_printed_count_explained_by_a_smaller_n(self):
        # 10 (2.9%) under n = 352: 10/345 = 2.90%, within the 5% window.
        tgt = {"what": "percent", "value": 2.9, "decimals": 1, "count": 10}
        v = G.check_cell(tgt, {"n": 352, "source": "header"})
        assert v["status"] == "explained_by_nonresponse"

    def test_a_denominator_printed_in_the_cell_is_not_retested(self):
        tgt = {"what": "percent", "value": 55.0, "decimals": 0}
        assert G.check_cell(tgt, {"n": 50, "source": "cell"})["status"] == "inconsistent"

    def test_no_n_is_a_refusal_not_a_pass(self):
        v = G.check_cell({"what": "percent", "value": 55.0, "decimals": 0},
                         {"n": None, "why": "no n"})
        assert v == {"status": "refused", "why": "no n"}


class TestSweep:
    def test_counts_every_target_and_files_nothing_it_did_not_check(self):
        t = _table([("Male, n (%)", ["12 (30.0)", "13 (31.7)"]),
                    ("Mood, mean (SD)", ["3.48 (1.20)", "3.50 (1.10)"])],
                   ["Drug (n = 40)", "Placebo (n = 41)"])
        out = G.sweep_grim([t])
        assert out["checked"] == 2 and out["inconsistent"] == 0
        assert out["enumerated"] == 4
        assert sum(out["refused"].values()) == 2

    def test_a_declaration_finds_what_the_harness_alone_cannot(self):
        t = _table([("POST", ["14.3", "17.1", "66.9"])],
                   ["Group 1 (n=70)", "Group 2 (n=70)", "Group 3 (n=70)"])
        assert G.sweep_grim([t])["checked"] == 0
        out = G.sweep_grim([t], [{"table": "T1", "percent_of_units": True}])
        assert out["checked"] == 3
        assert [f["raw"] for f in out["failures"]] == ["66.9"]

    def test_a_sparse_row_under_columns_of_different_n_is_refused(self):
        # Shaaban 2012: a value spanning a rank's three subcolumns lands
        # under the first one, which has the wrong n.
        cols = [f"c{i} (n = {n})" for i, n in enumerate([41, 25, 66, 39, 23, 62], 1)]
        full = ["46.3", "40", "44", "38.5", "30.4", "35.5"]
        t = _table([("A", full), ("B", full), ("C", full),
                    ("Highest order", ["1.6", "", "", "13.8", "", ""])], cols)
        out = G.sweep_grim([t], [{"table": "T1", "percent_of_units": True}])
        assert "sparse row: its values may sit under the wrong column" in out["refused"]
        assert not any(f["row_label"] == "Highest order" for f in out["failures"])

    def test_a_complex_survey_refuses_the_whole_paper(self):
        t = _table([("Male, n (%)", ["12 (31.0)"])], ["Drug (n = 40)"])
        out = G.sweep_grim([t], paper_text=(
            "Estimates were weighted using NHANES MEC exam weights (WTMEC2YR) "
            "to account for the complex survey design."))
        assert out["checked"] == 0 and out["refused_whole_paper"]


class TestLedger:
    def test_declarations_are_read_back_in_call_order(self):
        ledger = [
            {"tool_short": "declare_table", "input": {
                "table": "T1", "percent_of_units": False,
                "variables": [dict(LIKERT, upper_bound=7)]}},
            {"tool_short": "declare_table", "is_error": True,
             "input": {"table": "T1", "percent_of_units": True}},
            {"tool_short": "declare_table", "input": {
                "table": "T1", "percent_of_units": True, "variables": [LIKERT]}},
            {"tool_short": "grim_check", "input": {"mean": 1.0}},
        ]
        decls, variables = G.declarations_from_ledger(ledger)
        assert [d["percent_of_units"] for d in decls] == [False, True]
        assert variables == [LIKERT]
        t = _table([("x", ["1"])], ["c"])
        assert G.match_declaration(decls, 1, t)["percent_of_units"] is True


class TestFindingRows:
    def _sweep(self):
        t = _table([("POST", ["14.3", "17.1", "66.9"]),
                    ("Male, %", ["55", "54", "52"])],
                   ["Group 1 (n=50)", "Group 2 (n=50)", "Group 3 (n=70)"],
                   label="Table 3")
        return G.sweep_grim([t], [{"table": "T1", "percent_of_units": True}])

    def test_one_row_per_table_with_every_failing_cell_anchored(self):
        sweep = self._sweep()
        rows = G.finding_rows(sweep, "10.9999--demo")
        assert len(rows) == 1
        row = rows[0]
        assert row["producer"] == "harness" and row["outcome"] == "problem"
        assert row["impossible"] is False and row["severity_is_provisional"]
        assert len(row["anchors"]) == len(sweep["failures"])
        assert {a["kind"] for a in row["anchors"]} == {"table_cell"}
        assert row["anchors"][0]["row"] is not None
        assert row["finding_id"].startswith("f_")
        assert not findings_v2.validate_producer_constraints(rows)

    def test_a_strict_failure_outranks_one_nonresponse_explains(self):
        rows = G.finding_rows(self._sweep(), "p")
        assert rows[0]["provisional_severity"] == 4      # 66.9 at n = 70
        weak = {"failures": [{"table": "T1", "label": "Table 3", "status":
                              "explained_by_nonresponse", "what": "percent",
                              "raw": "55", "n": 50}], "tables": []}
        assert G.finding_rows(weak, "p")[0]["provisional_severity"] == 3

    def test_the_rows_satisfy_the_findings_schema(self):
        import jsonschema

        from metascience_agent.core import prompts
        schema = prompts.findings_schema_v2()
        doc = {"schema_version": "2.0", "paper_id": "p",
               "findings": G.finding_rows(self._sweep(), "p")}
        item = schema["properties"]["findings"]["items"]
        for row in doc["findings"]:
            jsonschema.validate(row, item)

    def test_coverage_line_states_the_denominators(self):
        line = G.coverage_line(self._sweep())
        assert line.startswith("GRIM sweep: ") and "checked" in line


class TestTools:
    XML = """<?xml version="1.0"?>
<article><front><article-meta><title-group><article-title>T</article-title></title-group></article-meta></front>
<body><sec><p>Seventy patients per group.</p>
<table-wrap id="TAB3"><label>Table 3</label><caption><title>Incidence, %</title></caption>
<table><tbody>
<tr><td> </td><td>Group 1 (n=70)</td><td>Group 2 (n=70)</td><td>Group 3 (n=70)</td><td>P</td></tr>
<tr><td>POST</td><td>14.3</td><td>17.1</td><td>66.9</td><td>&lt;0.01</td></tr>
<tr><td>Hoarseness</td><td>15.7</td><td>17.1</td><td>71.4</td><td>&lt;0.01</td></tr>
</tbody></table></table-wrap></sec></body></article>"""

    def _paper(self, tmp_path):
        d = tmp_path / "10.9999--demo"
        d.mkdir()
        (d / "10.9999--demo.xml").write_text(self.XML)
        return d

    def test_list_tables_names_the_key_and_the_printed_n(self, tmp_path):
        out = G.list_tables(str(self._paper(tmp_path)))
        assert out["tables"][0]["table"] == "T1"
        ns = {c["col"]: c.get("n") for c in out["tables"][0]["columns"]}
        assert ns[2] == 70
        json.dumps(out)

    def test_declare_table_returns_the_sweep_for_that_table(self, tmp_path):
        out = G.declare_table(str(self._paper(tmp_path)), "T1",
                              percent_of_units=True)
        assert out["declared"] and out["checked"] == 6
        assert [f["raw"] for f in out["failures"]] == ["66.9"]
        assert out["severity"] == "highly_suspicious"

    def test_an_unknown_table_is_refused_with_the_index(self, tmp_path):
        out = G.declare_table(str(self._paper(tmp_path)), "Table 9")
        assert out["declared"] is False and out["tables"][0]["table"] == "T1"


from tests.test_parallel_pipeline import _doc, _row, _stage, fakes  # noqa: E402,F401


class TestPipeline:
    """The declaration travels: declare_table call -> ledger -> harness sweep
    -> a `harness` finding row in findings.v2.json and a coverage line."""

    def _paper(self, tmp_path):
        d = TestTools()._paper(tmp_path)
        (d / "body.md").write_text("Seventy patients per group.")
        return d

    def _messages(self, paper_dir, decl):
        from metascience_agent import agent
        return [
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "d1", "name": agent._mcp("declare_table"),
                 "input": {"paper_dir": str(paper_dir), **decl}}]}},
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "d1",
                 "content": [{"type": "text", "text": "{\"declared\": true}"}]}]}},
        ]

    def _run(self, paper_dir):
        import asyncio

        from metascience_agent import agent
        from metascience_agent import pipeline_config as pc
        return asyncio.run(agent.analyze_paper(str(paper_dir), mode="parallel",
                                               pipeline=pc.load("tools_only")))

    def test_a_declared_table_is_swept_and_its_failure_filed(self, tmp_path, fakes):
        d = self._paper(tmp_path)
        fakes["tool"] = {**_stage(_doc([_row("t1")])),
                         "messages": self._messages(d, {"table": "T1",
                                                        "percent_of_units": True})}
        r = self._run(d)
        doc = r["findings_v2"]
        harness = [f for f in doc["findings"] if f["producer"] == "harness"]
        assert len(harness) == 1
        assert [c["raw"] for c in harness[0]["inputs"]["cells"]] == ["66.9"]
        assert harness[0]["severity_is_provisional"]
        sweep = doc["coverage"]["grim_sweep"]
        assert sweep["checked"] == 6 and sweep["n_declarations"] == 1
        assert sweep["line"].startswith("GRIM sweep:")
        from metascience_agent.report_v2 import render_report_v2
        assert "- GRIM sweep: 6 mean/percentage cell(s)" in render_report_v2(
            doc, r.get("run_meta"))

    def test_without_a_declaration_nothing_is_filed_and_the_gap_is_counted(
            self, tmp_path, fakes):
        d = self._paper(tmp_path)
        fakes["tool"] = {**_stage(_doc([_row("t1")])),
                         "messages": self._messages(d, {"table": "T9"})}
        doc = self._run(d)["findings_v2"]
        assert not [f for f in doc["findings"] if f["producer"] == "harness"]
        sweep = doc["coverage"]["grim_sweep"]
        assert sweep["checked"] == 0 and sweep["enumerated"] == 6


class TestDoclingCaptions:
    """A docling caption is a reference; it must be resolved, not printed."""

    class _T:
        def __init__(self, text):
            self.text = text
            self.captions = [type("Ref", (), {"__str__": lambda s: "cref='#/texts/49'"})()]

        def caption_text(self, doc):
            return self.text

    @pytest.mark.parametrize("caption, label", [
        ("Table 2 Percentage of CS practice among Egyptian obstetricians", "Table 2"),
        ("TABLE 3. MAIN AND INTERACTION EFFECTS OF PRICE PAID", "TABLE 3"),
        ("Supplementary Table S1: Baseline", "Supplementary Table S1"),
        ("eTable 4. Outcomes", "eTable 4"),
    ])
    def test_the_label_comes_from_the_resolved_caption(self, caption, label):
        from metascience_agent.extraction.docling_tables import _label_and_caption
        assert _label_and_caption(self._T(caption), 7, doc=None) == (label, caption)

    def test_no_caption_falls_back_to_the_ordinal(self):
        from metascience_agent.extraction.docling_tables import _label_and_caption
        t = self._T("")
        t.captions = []
        assert _label_and_caption(t, 3, doc=None) == ("Table 3", "")


class TestUserPrompt:
    """1.84.0: the per-paper prompt names the declaration step and the paper
    directory on every source layout; a toolset without it drops the block."""

    @pytest.mark.parametrize("layout", ["xml", "html", "pdf_md", "pdf"])
    def test_every_layout_names_the_step_and_the_directory(self, tmp_path, layout):
        from metascience_agent import agent
        d = tmp_path / "p"
        kw = {"xml": d / "p.xml"} if layout == "xml" else (
            {"html": d / "p.html"} if layout == "html" else {})
        text = agent._build_sweep_prompt(
            d / "body.md" if layout == "pdf_md" else None,
            d / "p.pdf" if layout != "xml" else None, "p", si_pdfs=[],
            paper_dir=d, **kw)
        assert agent.TABLE_DECLARATIONS_HEADING in text
        assert f"`paper_dir` `{d}`" in text and "`declare_table`" in text

    def test_a_toolset_without_declare_table_drops_the_block(self, tmp_path):
        from metascience_agent import agent, parallel
        text = agent._build_sweep_prompt(None, tmp_path / "p.pdf", "p",
                                         paper_dir=tmp_path)
        kept = parallel._restrict_user_prompt(text, frozenset({"declare_table"}))
        cut = parallel._restrict_user_prompt(text, frozenset({"grim_check"}))
        assert agent.TABLE_DECLARATIONS_HEADING in kept
        assert agent.TABLE_DECLARATIONS_HEADING not in cut
        assert cut == agent._build_sweep_prompt(None, tmp_path / "p.pdf", "p")
