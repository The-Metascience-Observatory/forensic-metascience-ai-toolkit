"""Model + image table reading, verified by the walker (section 8n). No model here:
every test drives the render, the adapter and the verifier on fixed input."""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit.scaffold import reconstruct as RC

WRAP = """<table-wrap id="T2"><label>Table 2</label><caption><p>Outcomes by arm</p></caption>
<table><thead><tr><th rowspan="2">Outcome</th><th colspan="2">Model 1</th></tr>
<tr><th>Coefficient</th><th>p</th></tr></thead>
<tbody><tr><td colspan="3">Panel A (N=64)</td></tr>
<tr><td>Reach</td><td>3.16 (0.98)</td><td>.002</td></tr>
<tr><td>Fidelity</td><td>−0.21 (0.30)</td><td>.49</td></tr></tbody></table>
<table-wrap-foot><fn><p>Note: N = 64 coalitions.</p></fn></table-wrap-foot></table-wrap>"""

WALKER = [  # the walker read the banner as a data row, as it does (section 8f)
    {"row": 1, "col": 1, "row_label": "Panel A (N=64)", "col_label": "Model 1 | Coefficient", "raw": "Panel A (N=64)"},
    {"row": 2, "col": 1, "row_label": "Reach", "col_label": "Model 1 | Coefficient", "raw": "3.16 (0.98)"},
    {"row": 2, "col": 2, "row_label": "Reach", "col_label": "Model 1 | p", "raw": ".002"},
    {"row": 3, "col": 1, "row_label": "Fidelity", "col_label": "Model 1 | Coefficient", "raw": "−0.21 (0.30)"},
    {"row": 3, "col": 2, "row_label": "Fidelity", "col_label": "Model 1 | p", "raw": ".49"},
]
def _e(variable, level, group, statistic, value, cell, row_label, column_label, section, column_index=None,
       variable_id=None, level_id=None, group_id=None):
    if column_index is None:
        column_index = {"Model 1 | Coefficient": 1, "Model 1 | p": 2}.get(column_label, 1)
    return {"variable": variable, "level": level, "group": group, "statistic": statistic, "value": value,
            "statistic_basis": "column_header",
            "column_index": column_index, "variable_id": variable_id, "level_id": level_id, "group_id": group_id,
            "cell": cell, "row_label": row_label, "column_label": column_label, "section": section}


GOOD = {"caption": "Outcomes by arm", "column_labels": ["Model 1 | Coefficient", "Model 1 | p"], "notes": None,
        "entries": [
            _e("Reach", None, "Model 1", "coefficient", "3.16", "3.16 (0.98)", "Reach", "Model 1 | Coefficient", "Panel A (N=64)"),
            _e("Reach", None, "Model 1", "se", "0.98", "3.16 (0.98)", "Reach", "Model 1 | Coefficient", "Panel A (N=64)"),
            _e("Reach", None, "Model 1", "p", ".002", ".002", "Reach", "Model 1 | p", "Panel A (N=64)"),
            _e("Fidelity", None, "Model 1", "coefficient", "−0.21", "−0.21 (0.30)", "Fidelity", "Model 1 | Coefficient", "Panel A (N=64)"),
            _e("Fidelity", None, "Model 1", "se", "0.30", "−0.21 (0.30)", "Fidelity", "Model 1 | Coefficient", "Panel A (N=64)"),
            _e("Fidelity", None, "Model 1", "p", ".49", ".49", "Fidelity", "Model 1 | p", "Panel A (N=64)"),
        ]}


def _with_entries(*entries):
    return {**GOOD, "entries": list(entries)}

class TestRender:
    def test_the_wrap_becomes_standalone_html_with_its_caption_and_footnote(self):
        h = RC.table_html(ET.fromstring(WRAP))
        assert h and "<table>" in h and "Outcomes by arm" in h and "N = 64 coalitions" in h
        assert 'colspan="2"' in h and 'rowspan="2"' in h, "spans survive; they are the structure"

    def test_a_graphic_only_wrap_is_not_rendered(self):
        assert RC.table_html(ET.fromstring('<table-wrap id="T9"><graphic href="x"/></table-wrap>')) is None

    def test_the_wrap_is_found_by_its_own_id_before_its_order(self):
        root = ET.fromstring(f"<article><body>{WRAP.replace('T2', 'T1')}{WRAP}</body></article>")
        assert RC.table_element(root, "T2", 1).get("id") == "T2"
        assert RC.table_element(root, None, 2).get("id") == "T2"
        assert RC.table_element(root, "T7", 9) is None

    @pytest.mark.skipif(RC.chrome_binary() is None, reason="no headless Chromium on this machine")
    def test_headless_chromium_draws_it(self, tmp_path):
        err = RC.render_png(RC.table_html(ET.fromstring(WRAP)), tmp_path / "t.png")
        assert err is None and (tmp_path / "t.png").stat().st_size > 1000


class TestAdapter:
    def test_the_grid_is_recovered_from_the_entries(self):
        # The inverse transformation: six entries, four printed cells.
        cells = RC.adapt(GOOD)
        assert len(cells) == 4
        assert cells[0]["row_label"] == "Panel A (N=64) | Reach" and cells[0]["col_label"] == "Model 1 | Coefficient"
        assert cells[0]["raw"] == "3.16 (0.98)" and (cells[0]["row"], cells[0]["col"]) == (1, 1)
        assert [e["statistic"] for e in cells[0]["entries"]] == ["coefficient", "se"]
        assert all(c["raw"].strip() for c in cells), "an empty cell is no cell"


class TestVerifier:
    def test_a_banner_moving_from_a_cell_to_a_section_is_conserved(self):
        v = RC.verify(WALKER, GOOD)
        assert v["verified"], v["reasons"]
        assert v["n_sections"] == 1 and v["n_entries"] == 6 and v["n_cells_read"] == 4

    def test_an_invented_numeral_refuses(self):
        bad = _with_entries(*GOOD["entries"][:2], _e("Reach", None, "Model 1", "p", ".02", ".02", "Reach", "Model 1 | p", "Panel A (N=64)"), *GOOD["entries"][3:])
        v = RC.verify(WALKER, bad)
        assert not v["verified"] and any("does not contain" in r for r in v["reasons"])

    def test_a_dropped_numeral_refuses(self):
        v = RC.verify(WALKER, _with_entries(*GOOD["entries"][:3]))
        assert not v["verified"] and any("absent from the reading" in r for r in v["reasons"])

    def test_a_value_outside_its_own_cell_refuses(self):
        bad = _with_entries(*GOOD["entries"][:2], _e("Reach", None, "Model 1", "p", ".002", "3.16 (0.98)", "Reach", "Model 1 | p", "Panel A (N=64)"), *GOOD["entries"][3:])
        v = RC.verify(WALKER, bad)
        assert not v["verified"] and any("not inside their own cell" in r for r in v["reasons"])

    def test_thousands_groups_are_one_digit_run_on_both_sides(self):
        assert RC.numeral_tokens("226 150 662") == RC.numeral_tokens("226150662") == ["226150662"]
        assert RC.numeral_tokens("3.1 (3.0-3.2)") == ["3", "1", "3", "0", "3", "2"]
        assert RC.numeral_tokens("http://www.cebc4cw.org/ http://coalition4evidence.org/") == [], "URL digits are not numbers"
        assert RC.numeral_tokens("n = 64; contact a1@b.org") == ["64"]

    def test_a_statistic_outside_the_vocabulary_refuses(self):
        bad = _with_entries(*GOOD["entries"][:5], {**GOOD["entries"][5], "statistic": "pvalue"})
        v = RC.verify(WALKER, bad)
        assert not v["verified"] and any("vocabulary" in r for r in v["reasons"])


class TestStatisticBasis:
    def test_an_inferred_kind_is_counted_and_the_vocabulary_is_closed(self):
        rec = _with_entries(*GOOD["entries"][:5], {**GOOD["entries"][5], "statistic_basis": "inferred"})
        v = RC.verify(WALKER, rec)
        assert v["verified"] and v["n_inferred_statistics"] == 1
        assert "inferred" in RC.STATISTIC_BASES and "statistic_basis" in RC.prompt(
            __import__("pathlib").Path("/x.png"), "", "Table 1", None, [])

    def test_a_reading_may_not_stamp_the_adjudicated_tier_on_its_own_numbers(self):
        """`adjudicated` says a SECOND reading changed the kind under
        `review.apply_adjudication`'s gates. A reading that writes it on its own
        numbers is a model certifying its own premise tier -- the channel this
        codebase closes wherever it appears, by re-deriving a model's verdict
        rather than believing it. That the tier is WEAKER than a printed basis is
        beside the point: it is written by the adjudication step and nowhere else."""
        walker = [{"row": 1, "col": 1, "row_label": "Reach", "col_label": "M (SD)", "raw": "3.16"}]

        def rec(basis):
            return {"caption": None, "notes": None, "column_labels": ["M (SD)"], "cells": [
                {"row_label": "Reach", "section": None, "column_index": 1, "column_label": "M (SD)",
                 "cell": "3.16", "variable": "Reach", "level": None, "group": None,
                 "variable_id": None, "level_id": None, "group_id": None,
                 "numbers": [{"statistic": "mean", "statistic_basis": basis, "value": "3.16"}]}]}

        v = RC.verify(walker, rec("adjudicated"))
        assert not v["verified"] and any("only apply_adjudication may" in r for r in v["reasons"]), v["reasons"]
        assert RC.verify(walker, rec("column_header"))["verified"], "the same reading, honestly based, verifies"


class TestKindConsistency:
    def test_identical_headers_read_with_different_kinds_are_disputed(self):
        def tbl(tid, kinds):
            return {"id": tid, "reconstruction": {"status": "verified"},
                    "cells": [{"col_label": "Coefficient | M (SD)", "raw": "1.0 (0.4)",
                               "entries": [{"statistic": k, "value": "x"} for k in kinds]}]}
        tables = [tbl("table:2", ("coefficient", "se")), tbl("table:3", ("coefficient", "sd")), tbl("table:4", ("coefficient", "se"))]
        probs = RC.kind_consistency(tables)
        assert len(probs) == 1 and "coefficient/se in table:2, table:4" in probs[0] and "coefficient/sd in table:3" in probs[0]
        assert all(e.get("statistic_disputed") for t in tables for c in t["cells"] for e in c["entries"])
        assert RC.kind_consistency([tbl("table:2", ("coefficient", "se")), tbl("table:3", ("coefficient", "se"))]) == []

    def test_different_printed_forms_under_one_header_are_not_a_disagreement(self):
        # ajcp Table 1: one `All coalitions` column carrying n, count (%), and mean (SD) by row.
        t = {"id": "table:1", "reconstruction": {"status": "verified"}, "cells": [
            {"col_label": "All coalitions", "raw": "n = 64", "entries": [{"statistic": "n"}]},
            {"col_label": "All coalitions", "raw": "38 (59%)", "entries": [{"statistic": "count"}, {"statistic": "percentage"}]},
            {"col_label": "All coalitions", "raw": "1.67 (2.15)", "entries": [{"statistic": "mean"}, {"statistic": "sd"}]}]}
        assert RC.kind_consistency([t]) == []
        assert RC.cell_form("1.67 (2.15)") == RC.cell_form("223.5 (410.75)") == "9 (9)"
        assert RC.cell_form("38 (59%)") == "9 (9%)" and RC.cell_form("< .001") == "< .9"


class TestNumeralFreeTables:
    def test_a_table_with_no_numerals_verifies_with_no_entries(self):
        walker = [{"row": 1, "col": 1, "row_label": "Blueprints", "col_label": "Location", "raw": "https://www.blueprintsprograms.org/"}]
        rec = {"caption": None, "notes": None, "column_labels": ["Location"], "entries": []}
        assert RC.verify(walker, rec)["verified"]
        assert not RC.verify(WALKER, rec)["verified"], "the same empty reading of a numeric table is refused"


class TestRepeatedHeaders:
    def test_identical_headers_are_distinct_columns_by_index(self):
        # ajcp Table 2: three `Coefficient | p` columns; `< .001` printed in all three.
        rec = {"caption": None, "notes": None, "column_labels": ["Coefficient | p"] * 3,
               "entries": [_e("x", None, None, "p", "< .001", "< .001", "r", "Coefficient | p", None, column_index=i)
                           for i in (1, 2, 3)]}
        cells = RC.adapt(rec)
        assert [c["col"] for c in cells] == [1, 2, 3], "three columns, not one"
        walker = [{"row": 1, "col": i, "row_label": "r", "col_label": "Coefficient | p", "raw": "< .001"} for i in (1, 2, 3)]
        v = RC.verify(walker, rec)
        assert v["verified"], v["reasons"]

    def test_a_column_index_outside_the_header_refuses(self):
        rec = _with_entries(*GOOD["entries"][:5], {**GOOD["entries"][5], "column_index": 9})
        v = RC.verify(WALKER, rec)
        assert not v["verified"] and any("column_index" in r for r in v["reasons"])


class TestContext:
    TEXT = ("Methods. Three models were fit, one per leadership measure (Table 2). Results. "
            "Table 2 shows the coefficients. Table 21 is unrelated. See table 2 for detail.")

    def test_plural_lists_and_ranges_name_each_table(self):
        assert RC._tables_named("Results in Tables 2, 3, 4 are shown as coefficients.") == {"2", "3", "4"}
        assert RC._tables_named("see Tables 2 and 5") == {"2", "5"}
        assert RC._tables_named("Tables 2–4 report") == {"2", "3", "4"}
        assert RC._tables_named("Table S1 lists") == {"S1"} and "1" not in RC._tables_named("Table S1 lists")
        assert "Results in Tables 2, 3, 4" in RC.citing_passages("Results in Tables 2, 3, 4 are shown as coefficients.", "Table 3")

    def test_citing_passages_are_the_sentences_that_name_this_table(self):
        c = RC.citing_passages(self.TEXT, "Table 2")
        assert "one per leadership measure" in c and "shows the coefficients" in c and "for detail" in c
        assert "Table 21" not in c, "Table 21 is not Table 2"
        assert RC.citing_passages(self.TEXT, "Table 3") == ""

    def test_vocabulary_and_groups_are_compact_id_lists(self):
        p2 = {"variables": [{"id": "var:state", "name": "State", "kind": "categorical", "units": None,
                             "levels": [{"id": "lvl:pa", "label": "Pennsylvania", "value": None}]}]}
        p1 = {"studies": [{"id": "study:a", "label": "A", "groups": [{"id": "grp:tx", "label": "Treatment"}]}]}
        assert "var:state: State [categorical" in RC.vocabulary(p2) and "lvl:pa" in RC.vocabulary(p2)
        assert "grp:tx = Treatment" in RC.declared_groups(p1)

    def test_the_context_is_part_of_the_cache_key(self):
        t = {"cells": list(WALKER)}
        assert RC._cache_key(t, "<table/>", None) != RC._cache_key(t, "<table/>", {"vocabulary": "x"})

    def test_the_prompt_carries_the_passages_and_the_vocabulary(self):
        p = RC.prompt(__import__("pathlib").Path("/x.png"), "| a |", "Table 2", None, [],
                      context={"citing_passages": "- one per leadership measure", "vocabulary": "- var:x: X",
                               "groups": "- study:a: grp:tx = Treatment"})
        assert "one per leadership measure" in p and "var:x: X" in p and "grp:tx" in p and "column_index" in p


class TestDriver:
    def test_without_a_model_and_without_a_cache_the_walker_stands(self, tmp_path):
        t = {"label": "Table 2", "cells": list(WALKER), "source": "article", "table_id": "T2", "table_num": 1}
        probs: list[str] = []
        rec = RC.reconstruct_table(tmp_path, t, 1, tmp_path / "tables", model=None,
                                   root=ET.fromstring(f"<article><body>{WRAP}</body></article>"), problems=probs)
        assert rec["status"] in ("not_attempted", "not_rendered")
        assert t["cells"] == WALKER and t["walker_cells"] == WALKER

    def test_a_supplement_table_is_left_alone(self, tmp_path):
        t = {"label": "S1", "cells": list(WALKER), "source": "supplement"}
        rec = RC.reconstruct_table(tmp_path, t, 1, tmp_path / "tables", model="x", root=None, problems=[])
        assert rec["status"] == "not_attempted" and "supplement" in rec["reason"]

    @pytest.mark.skipif(RC.chrome_binary() is None, reason="no headless Chromium on this machine")
    def test_a_verified_reading_replaces_the_cells_and_a_refused_one_does_not(self, tmp_path, monkeypatch):
        # TWO READINGS OF ONE TABLE, WHICH IS WHAT THE STORE EXISTS TO PREVENT
        # BUYING. This test serves the same cells twice and varies only the
        # model's answer, so it must run with `reading_store` off -- otherwise
        # the second call is answered with the first reading, correctly. A
        # deliberate re-read of a paper (test-retest) needs the same switch.
        monkeypatch.setenv("METASCIENCE_READING_CACHE", "off")
        calls = {}

        def fake_run_pass(name, prompt, out_dir, **kw):
            calls["tools"] = kw.get("tools")
            calls["schema"] = kw.get("schema")
            meta = {"cost_usd": 0.01, "model": kw.get("model"), **(kw.get("extra_meta") or {})}
            # WRITTEN, BECAUSE `run_pass` WRITES. A reading that exists only as
            # a return value is one `reading_store` cannot keep, and it now
            # says so rather than losing the purchase quietly.
            Path(out_dir).mkdir(parents=True, exist_ok=True)
            (Path(out_dir) / f"{name}.json").write_text(json.dumps(calls["recon"]), encoding="utf-8")
            (Path(out_dir) / f"{name}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
            return {"data": calls["recon"], "problems": [], "meta": meta}
        monkeypatch.setattr(RC._passes, "run_pass", fake_run_pass)
        root = ET.fromstring(f"<article><body>{WRAP}</body></article>")
        calls["recon"] = GOOD
        t = {"label": "Table 2", "cells": list(WALKER), "source": "article", "table_id": "T2", "table_num": 1}
        probs: list[str] = []
        rec = RC.reconstruct_table(tmp_path, t, 1, tmp_path / "tables", model="sonnet", root=root, problems=probs)
        assert rec["status"] == "verified", rec
        assert calls["tools"] == "Read" and calls["schema"] is RC.RECON_SCHEMA
        assert t["cells"] == RC.adapt(GOOD) and t["walker_cells"] == WALKER and not probs
        calls["recon"] = _with_entries(*GOOD["entries"][:3])
        t2 = {"label": "Table 2", "cells": list(WALKER), "source": "article", "table_id": "T2", "table_num": 1}
        rec2 = RC.reconstruct_table(tmp_path, t2, 2, tmp_path / "tables2", model="sonnet", root=root, problems=probs)
        assert rec2["status"] == "refused" and t2["cells"] == WALKER and probs and "refused" in probs[0]


class TestCrop:
    @pytest.mark.skipif(RC.chrome_binary() is None, reason="no headless Chromium on this machine")
    def test_the_blank_canvas_is_trimmed(self, tmp_path):
        pytest.importorskip("PIL")
        from PIL import Image
        err = RC.render_png(RC.table_html(ET.fromstring(WRAP)), tmp_path / "t.png")
        assert err is None
        with Image.open(tmp_path / "t.png") as im:
            assert im.height < 1500 and im.width < 1400, im.size




class TestSupplementTables:
    def _docx(self, tmp_path):
        docx = pytest.importorskip("docx")
        d = docx.Document()
        t = d.add_table(rows=3, cols=3)
        t.cell(0, 1).merge(t.cell(0, 2))          # header spanning two columns
        t.cell(1, 0).merge(t.cell(2, 0))          # stub spanning two rows
        vals = [["", "Group A", ""], ["Outcome", "1.5 (0.2)", "3"], ["", "2.5 (0.4)", "4"]]
        for r in range(3):
            for c in range(3):
                if vals[r][c]:
                    t.cell(r, c).text = vals[r][c]
        path = tmp_path / "paper_supplementary_info_1_s001.docx"
        d.save(str(path))
        return path

    def test_word_merges_are_drawn_as_spans(self, tmp_path):
        path = self._docx(tmp_path)
        h = RC.docx_table_html(path, 1, label="s001.docx :: Table 1")
        assert h and 'colspan="2"' in h and 'rowspan="2"' in h and "1.5 (0.2)" in h
        assert RC.docx_table_html(path, 2) is None, "a table number past the file's tables is None, not a guess"

    def test_a_supplement_table_is_rendered_from_its_own_file(self, tmp_path):
        path = self._docx(tmp_path)
        table = {"label": f"{path.name} :: Table 1", "walker_label": f"{path.name} :: Table 1",
                 "supplement_file": path.name, "source": "supplement",
                 "cells": [{"row": 1, "col": 1, "row_label": "Outcome", "col_label": "Group A", "raw": "1.5 (0.2)"}]}
        html, why = RC.supplement_table_html(tmp_path, table)
        assert html and why is None
        # The document numbers this table 5 among the paper's tables; inside the file it is Table 1.
        html5, why5 = RC.supplement_table_html(tmp_path, {**table, "table_num": 5, "label": "Table 5",
                                                          "walker_label": f"{path.name} :: Table 1"})
        assert html5 and why5 is None
        pdf_table = {**table, "supplement_file": "s002.pdf"}
        (tmp_path / "s002.pdf").write_bytes(b"%PDF-1.4 stub")
        # A PDF supplement has no markup to draw: it is drawn as a PAGE, by
        # `supplement_table_render`, and this function says so rather than
        # calling the format unsupported.
        assert RC.supplement_table_html(tmp_path, pdf_table) == (
            None, "supplement format .pdf is not rendered as HTML")

    def test_the_walker_label_gives_the_number_even_with_a_page_suffix(self):
        # `supplements_read.extract_pdf_tables` labels a PDF supplement's table
        # `Table 3 (p. 4)`; an anchored `Table N$` matched none of them, so
        # every PDF supplement was read with no citing passages at all.
        assert RC._SUPP_LABEL_NUM.search("s001.pdf :: Table 3 (p. 4)").group(1) == "3"
        assert RC._SUPP_LABEL_NUM.search("s001.docx :: Table 1").group(1) == "1"

    @pytest.mark.skipif(RC.chrome_binary() is None, reason="no headless Chromium on this machine")
    def test_without_a_model_the_supplement_table_is_rendered_and_left_to_the_walker(self, tmp_path):
        path = self._docx(tmp_path)
        table = {"label": f"{path.name} :: Table 1", "walker_label": f"{path.name} :: Table 1",
                 "supplement_file": path.name, "source": "supplement",
                 "cells": [{"row": 1, "col": 1, "row_label": "Outcome", "col_label": "Group A", "raw": "1.5 (0.2)"}]}
        rec = RC.reconstruct_table(tmp_path, table, 5, tmp_path / "tables", model=None, root=None, problems=[])
        assert rec["png"] and rec["status"] == "not_attempted" and "model is off" in rec["reason"]

    def test_citing_passages_for_a_supplement_table_use_the_paper_s_spelling(self):
        ctx = RC.context_for({"source": "supplement", "walker_label": "s001.docx :: Table 1"},
                             "Detailed statistics are in Table S1. Baseline data are in eTable 1. Table 1 is the article's.",
                             None, None)
        assert "Table S1" in ctx["citing_passages"] and "eTable 1" in ctx["citing_passages"]
        assert "article's" not in ctx["citing_passages"]


class TestPdfSupplementTables:
    """A PDF supplement is read like every other table: find its page, draw the
    page, hand the image to the same call and the same verifier.

    THE RULING (Greg, 2026-09-06): "the supplements/repos aren't 'second-class
    citizens' in the context of the analysis." Before this, every PDF
    supplement table was recorded `supplement format .pdf not rendered yet` --
    nine tables and 592 cells on jamanetworkopen.2023.37679 alone.
    """

    def _pdf(self, tmp_path, pages, name="paper_supplementary_info_1_s001.pdf"):
        fitz = pytest.importorskip("fitz", reason="PyMuPDF is not installed")
        doc = fitz.open()
        for lines in pages:
            page = doc.new_page()
            y = 100
            for line in lines:
                page.insert_text((72, y), line, fontsize=11)
                y += 18
        path = tmp_path / name
        doc.save(str(path))
        doc.close()
        return path

    def _table(self, path, cells, **kw):
        return {"label": f"{path.name} :: Table 1 (p. 2)", "walker_label": f"{path.name} :: Table 1 (p. 2)",
                "supplement_file": path.name, "source": "supplement",
                "cells": [{"row": i, "col": 1, "row_label": f"r{i}", "col_label": "Value", "raw": c}
                          for i, c in enumerate(cells, start=1)], **kw}

    def test_the_locator_finds_the_page_the_table_is_printed_on(self, tmp_path):
        path = self._pdf(tmp_path, [["Introduction to the appendix", "Nothing tabular here"],
                                    ["eTable 1. Outcomes", "Weight 23.0 (0.40)", "Pole 10.6 (1.12)"]])
        table = self._table(path, ["23.0 (0.40)", "10.6 (1.12)"])
        loc = RC.locate_pdf_table(path, table)
        assert loc["pages"] == [2] and loc["basis"] == "text_match" and loc["coverage"] == 1.0

    def test_the_walkers_own_page_is_the_first_witness(self, tmp_path):
        # docling stamps the page on a PDF supplement's table and the document
        # layer carries it as `supplement_page`; the cell-string coverage is
        # measured beside it as something a reader can see, not as a veto --
        # measured on jamanetworkopen.2023.37679, docling FUSES several printed
        # cells into one (`1.00 1.37 (0.91-2.06)`), and such a string appears
        # nowhere in the page's own text layer even on the right page.
        path = self._pdf(tmp_path, [["Appendix"], ["eTable 1. Outcomes", "23.0 (0.40)"]])
        table = self._table(path, ["23.0 (0.40)", "1.00 1.37 (0.91-2.06)"], supplement_page=2)
        loc = RC.locate_pdf_table(path, table)
        assert loc["pages"] == [2] and loc["basis"] == "walker_page"
        assert loc["coverage"] == 0.5, "the coverage is reported, not enforced, on the walker's page"

    def test_a_table_running_over_a_page_break_takes_both_pages(self, tmp_path):
        path = self._pdf(tmp_path, [["Appendix"],
                                    ["eTable 1", "11.1 (1)", "22.2 (2)", "33.3 (3)"],
                                    ["44.4 (4)", "55.5 (5)", "66.6 (6)"]])
        table = self._table(path, ["11.1 (1)", "22.2 (2)", "33.3 (3)",
                                   "44.4 (4)", "55.5 (5)", "66.6 (6)"])
        loc = RC.locate_pdf_table(path, table)
        assert loc["pages"] == [2, 3] and loc["spill_coverage"] == 1.0

    def test_a_table_found_on_no_page_is_refused_by_name(self, tmp_path):
        path = self._pdf(tmp_path, [["Appendix"], ["eTable 1. Outcomes", "23.0 (0.40)"]])
        table = self._table(path, ["23.0 (0.40)", "99.9 (9.9)", "88.8 (8.8)", "77.7 (7.7)"])
        loc = RC.locate_pdf_table(path, table)
        assert loc["pages"] is None
        assert "could not be located" in loc["reason"] and "1 of 4 cell strings (25%)" in loc["reason"]

    def test_a_table_the_walker_read_no_cells_from_is_not_bought(self, tmp_path):
        # `verify` compares the reading's digits against the walker's; with no
        # walker cells any reading with a digit is refused and an empty one is
        # accepted on no evidence. Either way the call tells us nothing.
        path = self._pdf(tmp_path, [["Appendix"], ["eTable 1"]])
        loc = RC.locate_pdf_table(path, self._table(path, [], supplement_page=2))
        assert loc["pages"] is None and "could not be verified against anything" in loc["reason"]

    def test_the_page_is_drawn_and_the_reader_is_told_it_is_a_page(self, tmp_path):
        pytest.importorskip("fitz", reason="PyMuPDF is not installed")
        path = self._pdf(tmp_path, [["Appendix"], ["eTable 1. Outcomes", "23.0 (0.40)", "10.6 (1.12)"]])
        table = self._table(path, ["23.0 (0.40)", "10.6 (1.12)"])
        html, png, meta, why = RC.supplement_table_render(tmp_path, table, tmp_path / "t.png")
        assert html is None and why is None
        assert png and png.exists() and png.stat().st_size > 0
        assert meta["render"] == "pdf_page" and meta["pages"] == [2]
        page_prompt = RC.prompt(png, "| Value |", "Table 1", None, [], page_image=True)
        assert ("The image is a full supplement page; the table to read is the one whose "
                "cells are listed below." in page_prompt)
        assert "full supplement page" not in RC.prompt(png, "| Value |", "Table 1", None, [])

    def test_the_reconstruction_record_names_the_pages_it_drew(self, tmp_path):
        pytest.importorskip("fitz", reason="PyMuPDF is not installed")
        path = self._pdf(tmp_path, [["Appendix"], ["eTable 1. Outcomes", "23.0 (0.40)"]])
        table = self._table(path, ["23.0 (0.40)"], supplement_page=2)
        rec = RC.reconstruct_table(tmp_path, table, 4, tmp_path / "tables",
                                   model=None, root=None, problems=[])
        # No model, so the reading is not bought -- but the page was found and
        # drawn, and the record says which page and on what basis.
        assert rec["png"] and rec["render"] == "pdf_page" and rec["pages"] == [2]
        assert rec["page_basis"] == "walker_page" and rec["status"] == "not_attempted"
        assert "model is off" in rec["reason"]


class TestFiguresFromTheManifest:
    def test_fetched_images_join_the_caption_figures_by_number(self):
        from forensic_metascience_ai_toolkit.scaffold import document as D
        figs = [{"id": "figure:1", "label": "Figure 1", "caption": "Figure 1. Recall.", "panels": ["a", "b"], "n_panels": 2}]
        manifest = {"source": "local_html_page", "figures": [
            {"id": "fig01", "figure_label": "Figure 1", "file": "f1.jpg", "status": "ok", "caption": "Recall."},
            {"id": "fig02", "figure_label": "Figure 2", "file": "f2.jpg", "status": "ok", "caption": "Dose response."}]}
        out = D.merge_pmc_figures(figs, manifest)
        assert [(f["label"], f.get("image"), f.get("image_status")) for f in out] == [
            ("Figure 1", "f1.jpg", "ok"), ("Figure 2", "f2.jpg", "ok")]
        assert out[0]["panels"] == ["a", "b"], "the caption's panels survive the join"
        assert out[1]["values_readable_from_text"] is False and out[1]["caption"] == "Dose response."
        assert D.merge_pmc_figures(figs, None) == figs


class TestFootnoteMarkers:
    def test_a_marker_on_the_value_but_not_the_cell_is_not_a_refusal(self):
        walker = [{"row": 1, "col": 1, "row_label": "1 Limitation", "col_label": "AOR (95% CI)", "raw": "2.23c (1.62-3.07)"}]
        rec = {"caption": None, "notes": None, "column_labels": ["AOR (95% CI)"], "cells": [
            {"row_label": "1 Limitation", "section": "Veteran", "column_index": 1, "column_label": "AOR (95% CI)",
             "cell": "2.23 (1.62-3.07)", "variable": "Limitations", "level": "1 Limitation", "group": "Veteran",
             "variable_id": None, "level_id": None, "group_id": None,
             "numbers": [{"statistic": "ratio", "statistic_basis": "column_header", "value": "2.23c"},
                         {"statistic": "ci_lower", "statistic_basis": "column_header", "value": "1.62"},
                         {"statistic": "ci_upper", "statistic_basis": "column_header", "value": "3.07"}]}]}
        v = RC.verify(walker, rec)
        assert v["verified"], v["reasons"]
        assert RC._strip_marker("2.23c") == "2.23" and RC._strip_marker("0.90*") == "0.90" and RC._strip_marker("12") == "12"


class TestPerCellForm:
    def test_the_per_cell_form_flattens_to_entries_and_verifies(self):
        rec = {"caption": None, "notes": None, "column_labels": ["Model 1 | Coefficient", "Model 1 | p"], "cells": [
            {"row_label": "Reach", "section": "Panel A (N=64)", "column_index": 1, "column_label": "Model 1 | Coefficient",
             "cell": "3.16 (0.98)", "variable": "Reach", "level": None, "group": "Model 1", "variable_id": None,
             "level_id": None, "group_id": None,
             "numbers": [{"statistic": "coefficient", "statistic_basis": "column_header", "value": "3.16"},
                         {"statistic": "se", "statistic_basis": "citing_text", "value": "0.98"}]},
            {"row_label": "Reach", "section": "Panel A (N=64)", "column_index": 2, "column_label": "Model 1 | p",
             "cell": ".002", "variable": "Reach", "level": None, "group": "Model 1", "variable_id": None,
             "level_id": None, "group_id": None,
             "numbers": [{"statistic": "p", "statistic_basis": "column_header", "value": ".002"}]},
            {"row_label": "Fidelity", "section": "Panel A (N=64)", "column_index": 1, "column_label": "Model 1 | Coefficient",
             "cell": "−0.21 (0.30)", "variable": "Fidelity", "level": None, "group": "Model 1", "variable_id": None,
             "level_id": None, "group_id": None,
             "numbers": [{"statistic": "coefficient", "statistic_basis": "column_header", "value": "−0.21"},
                         {"statistic": "se", "statistic_basis": "citing_text", "value": "0.30"}]},
            {"row_label": "Fidelity", "section": "Panel A (N=64)", "column_index": 2, "column_label": "Model 1 | p",
             "cell": ".49", "variable": "Fidelity", "level": None, "group": "Model 1", "variable_id": None,
             "level_id": None, "group_id": None,
             "numbers": [{"statistic": "p", "statistic_basis": "column_header", "value": ".49"}]}]}
        es = RC.entries_of(rec)
        assert len(es) == 6 and es[0]["cell"] == "3.16 (0.98)" and es[1]["statistic"] == "se" and es[1]["section"] == "Panel A (N=64)"
        v = RC.verify(WALKER, rec)
        assert v["verified"], v["reasons"]
        assert len(RC.adapt(rec)) == 4 and RC.adapt(rec)[0]["entries"][1]["statistic"] == "se"

    def test_mirrored_panels_with_identical_stubs_are_distinct_cells(self):
        # Veteran / Nonveteran panels both print `1 [Reference]` under `No limitations`.
        walker = [{"row": r, "col": 1, "row_label": f"{sec} | No limitations", "col_label": "AOR", "raw": "1 [Reference]"}
                  for r, sec in ((1, "Veteran"), (2, "Nonveteran"))]
        rec = {"caption": None, "notes": None, "column_labels": ["AOR"], "cells": [
            {"row_label": "No limitations", "section": sec, "column_index": 1, "column_label": "AOR", "cell": "1 [Reference]",
             "variable": "Limitations", "level": "No limitations", "group": sec, "variable_id": None, "level_id": None,
             "group_id": None, "numbers": [{"statistic": "ratio", "statistic_basis": "column_header", "value": "1"}]}
            for sec in ("Veteran", "Nonveteran")]}
        assert RC.verify(walker, rec)["verified"]


class TestAPageIsNotATable:
    """A PDF supplement's page render, cropped to the table that was asked for.

    jamanetworkopen.2023.51752's first supplement puts two walked tables on each
    of three pages, and each pair was drawn as the same image -- so a reading of
    one was made against a picture holding both, which is the cross-table
    attribution route.
    """

    def _pdf(self, tmp_path, blocks, name="paper_supplementary_info_1_s001.pdf"):
        """One page, `blocks` drawn as `(y, [lines])` so the vertical layout is
        the fixture's own and not an accident of the writer."""
        fitz = pytest.importorskip("fitz", reason="PyMuPDF is not installed")
        doc = fitz.open()
        page = doc.new_page()
        for y, lines in blocks:
            for i, line in enumerate(lines):
                page.insert_text((72, y + 14 * i), line, fontsize=11)
        path = tmp_path / name
        doc.save(str(path))
        doc.close()
        return path

    def _table(self, path, label, rows, page=1):
        cells = [{"row": i, "col": j + 1, "row_label": r[0], "col_label": f"c{j + 1}", "raw": v}
                 for i, r in enumerate(rows, start=1) for j, v in enumerate(r[1:])]
        return {"label": f"{path.name} :: {label}", "walker_label": f"{path.name} :: {label}",
                "supplement_file": path.name, "source": "supplement", "supplement_page": page,
                "cells": cells, "row_labels": [r[0] for r in rows],
                "col_labels": [f"c{j + 1}" for j in range(max(len(r) - 1 for r in rows))]}

    def _two_on_one_page(self, tmp_path):
        path = self._pdf(tmp_path, [
            (100, ["Table 6. Allele frequencies by sex", "Population   N     H     L",
                   "Males        620   0.051 0.503", "Females      340   0.072 0.474",
                   "Unknown      117   0.064 0.488"]),
            (300, ["Prose between the two tables, which is neither of them and mentions 0.45."]),
            (500, ["Table 7. Genotypes by ancestry", "Population        N     HH    HL",
                   "African-Americans 263   0.421 0.452", "Whites            379   0.223 0.501",
                   "Other             194   0.318 0.409"])])
        upper = self._table(path, "Table 6 (p. 1)",
                            [["Males", "620", "0.051", "0.503"], ["Females", "340", "0.072", "0.474"],
                             ["Unknown", "117", "0.064", "0.488"]])
        lower = self._table(path, "Table 7 (p. 1)",
                            [["African-Americans", "263", "0.421", "0.452"],
                             ["Whites", "379", "0.223", "0.501"],
                             ["Other", "194", "0.318", "0.409"]])
        return path, upper, lower

    def test_each_table_on_a_shared_page_is_drawn_alone(self, tmp_path):
        fitz = pytest.importorskip("fitz", reason="PyMuPDF is not installed")
        path, upper, lower = self._two_on_one_page(tmp_path)
        locs = [RC.locate_pdf_table(path, t, siblings=[o]) for t, o in ((upper, lower), (lower, upper))]
        assert [l["pages"] for l in locs] == [[1], [1]]
        assert [l["band"]["basis"] for l in locs] == ["text_band", "text_band"]
        with fitz.open(str(path)) as doc:
            page = doc[0]
            seen = [RC._squash(page.get_text(clip=fitz.Rect(*l["clip"]))) for l in locs]
        assert "620" in seen[0] and "0.051" in seen[0]
        assert "263" not in seen[0] and "0.421" not in seen[0], "the other table's digits are not in this render"
        assert "263" in seen[1] and "0.421" in seen[1]
        assert "620" not in seen[1] and "0.051" not in seen[1]
        assert "Table6" in seen[0], "the table's own caption is drawn with it (the text here is squashed)"

    def test_the_two_renders_are_different_images(self, tmp_path):
        pytest.importorskip("fitz", reason="PyMuPDF is not installed")
        path, upper, lower = self._two_on_one_page(tmp_path)
        pngs = []
        for i, (t, o) in enumerate(((upper, lower), (lower, upper))):
            html, drawn, meta, why = RC.supplement_table_render(tmp_path, t, tmp_path / f"t{i}.png",
                                                                siblings=[o])
            assert why is None and drawn is not None and meta["clip"]
            pngs.append(drawn.read_bytes())
        assert pngs[0] != pngs[1], "one page drawn twice is the defect, not the fix"

    def test_a_shared_page_that_cannot_be_cut_is_refused_rather_than_drawn_whole(self, tmp_path):
        # Both tables print the same strings, so nothing on the page is
        # distinctive and the two bands cannot be separated. Drawing the page
        # would hand each reading the other's table.
        pytest.importorskip("fitz", reason="PyMuPDF is not installed")
        path = self._pdf(tmp_path, [(100, ["Table 1", "A 1.11 2.22", "B 3.33 4.44"]),
                                    (400, ["Table 2", "A 1.11 2.22", "B 3.33 4.44"])])
        a = self._table(path, "Table 1 (p. 1)", [["A", "1.11", "2.22"], ["B", "3.33", "4.44"]])
        b = self._table(path, "Table 2 (p. 1)", [["A", "1.11", "2.22"], ["B", "3.33", "4.44"]])
        loc = RC.locate_pdf_table(path, a, siblings=[b])
        assert loc["pages"] is None and loc["band"]["basis"] == "refused"
        assert "walked tables" in loc["reason"] and "not asked about" in loc["reason"]

    def test_a_page_with_one_table_is_still_drawn_whole_when_the_band_is_weak(self, tmp_path):
        # The economy is optional; the separation is not. A lone table whose
        # cells the walker fused stays a whole-page render, as before.
        pytest.importorskip("fitz", reason="PyMuPDF is not installed")
        path = self._pdf(tmp_path, [(100, ["eTable 1. Outcomes", "Weight 23.0 (0.40)"])])
        t = self._table(path, "Table 1 (p. 1)", [["Weight", "23.0 (0.40) 99.9 (9.9) fused"]])
        loc = RC.locate_pdf_table(path, t, siblings=[])
        assert loc["pages"] == [1] and loc.get("clip") is None
        assert loc["band"]["basis"] == "not_cropped" and "drawn whole" in loc["band"]["reason"]


class TestTheRenderWindowFitsTheTable:
    """`--screenshot` captures the WINDOW, so a table taller than it was drawn
    short with no error: the meta-analysis Table 2 (237 rows, 6,824 px) came
    back at 1400x4996 and `_crop_to_content` then trimmed it to a tidy row
    boundary."""

    def _html(self, rows: int) -> str:
        body = "".join(f"<tr><td>Study {i}</td><td>{i}.{i:02d}</td><td>0.0{i}</td></tr>"
                       for i in range(1, rows + 1))
        return ("<html><head><meta charset='utf-8'><style>" + RC._CSS + "</style></head><body>"
                "<div class='label'>Table 2</div><table><thead><tr><th>Study</th><th>Effect</th>"
                f"<th>SE</th></tr></thead><tbody>{body}</tbody></table></body></html>")

    def _chrome(self):
        if not RC.chrome_binary():
            pytest.skip("no headless Chromium on this machine")

    def test_the_window_is_sized_from_the_tables_own_rows(self):
        assert RC._estimated_height(self._html(3)) == RC._DEFAULT_RENDER_PX
        tall = RC._estimated_height(self._html(237))
        assert tall > 6824, "the meta-analysis Table 2 draws at 6,824 px and must fit in one shot"

    def test_a_table_taller_than_the_old_window_is_drawn_whole(self, tmp_path):
        self._chrome()
        pytest.importorskip("PIL", reason="Pillow is not installed; clipping cannot be detected")
        html = self._html(237)
        meta = {}
        assert RC.render_png(html, tmp_path / "t.png", meta=meta) is None
        assert meta["clipped"] is False and meta["render_attempts"] == 1
        from PIL import Image
        with Image.open(tmp_path / "t.png") as im:
            drawn = im.size[1]
        assert drawn > 5000, "the whole table, not the first 5,000 px of it"

    def test_the_old_window_is_shown_to_have_clipped_the_same_table(self, tmp_path):
        self._chrome()
        pytest.importorskip("PIL", reason="Pillow is not installed; clipping cannot be detected")
        meta = {}
        assert RC.render_png(self._html(237), tmp_path / "t.png", height=5000, meta=meta) is None
        assert meta["render_attempts"] >= 2 and meta["render_height_px"] > 5000, (
            "this is the defect: at the old fixed window the ink reached the bottom edge and the "
            "rows below it were absent, with nothing anywhere saying so")
        assert meta["clipped"] is False, "and it is only left when the whole table is in the image"

    def test_a_table_that_cannot_fit_is_refused_rather_than_served_short(self, tmp_path, monkeypatch):
        self._chrome()
        pytest.importorskip("PIL", reason="Pillow is not installed; clipping cannot be detected")
        monkeypatch.setattr(RC, "_MAX_RENDER_PX", 400)
        monkeypatch.setattr(RC, "_DEFAULT_RENDER_PX", 400)
        why = RC.render_png(self._html(60), tmp_path / "t.png")
        assert why and "taller than the 400 px render window" in why
        assert "Refused rather than served short" in why

    def test_a_clipped_render_stops_the_reading_before_it_is_bought(self, tmp_path, monkeypatch):
        self._chrome()
        pytest.importorskip("PIL", reason="Pillow is not installed; clipping cannot be detected")
        monkeypatch.setattr(RC, "_MAX_RENDER_PX", 400)
        monkeypatch.setattr(RC, "_DEFAULT_RENDER_PX", 400)
        root = ET.fromstring("<article><body>" + WRAP.replace(
            "</tbody>", "".join(f"<tr><td>r{i}</td><td>{i}.0</td><td>.0{i}</td></tr>"
                                for i in range(1, 40)) + "</tbody>") + "</body></article>")
        table = {"wrap_id": "T2", "table_num": 1, "cells": list(WALKER), "label": "Table 2"}
        rec = RC.reconstruct_table(tmp_path, table, 2, tmp_path / "tables",
                                   model="sonnet", root=root, problems=[])
        assert rec["status"] == "not_rendered" and "served short" in rec["reason"]
        assert rec["cost_usd"] is None, "nothing was bought against an image missing rows"


class TestALongTableIsReadInRowBlocks:
    """A table over ~250 cells had no reading path: one record per cell
    overflows the output cap, and the meta-analysis Table 2 is 1,845 cells. It
    is cut into bands of rows with the header repeated into each, and the
    conservation check is over their UNION -- so a block that never came back is
    a refusal, not a shorter table."""

    def _table(self, rows: int, cols: int = 4):
        cells = [{"row": r, "col": c, "row_label": f"Study {r}", "col_label": f"c{c}",
                  "raw": f"{r}.{c}{c}"}
                 for r in range(2, rows + 2) for c in range(1, cols + 1)]
        return {"label": "Table 2", "cells": cells, "n_header_rows": 1,
                "col_labels": [f"c{c}" for c in range(1, cols + 1)]}

    def _reading(self, cells, cols):
        return {"caption": None, "column_labels": cols, "notes": None,
                "cells": [{"row_label": c["row_label"], "section": None, "column_index": c["col"],
                           "column_label": c["col_label"], "cell": c["raw"], "variable": "x",
                           "level": None, "group": None, "variable_id": None, "level_id": None,
                           "group_id": None,
                           "numbers": [{"statistic": "other", "statistic_basis": "cell_form",
                                        "value": c["raw"]}]}
                          for c in cells]}

    def test_a_400_cell_table_is_cut_into_blocks_that_conserve_every_row(self):
        t = self._table(100)                       # 100 rows x 4 = 400 cells
        blocks = RC.row_blocks(t)
        assert len(blocks) == 3 and [b["index"] for b in blocks] == [1, 2, 3]
        assert all(b["n_blocks"] == 3 for b in blocks)
        assert all(len(b["cells"]) <= RC._MAX_BLOCK_CELLS for b in blocks)
        assert sum(len(b["cells"]) for b in blocks) == 400
        rows = [r for b in blocks for r in sorted(b["row_set"])]
        assert rows == sorted(rows) and len(set(rows)) == 100, "printed order, every row once"
        assert not set.intersection(*[b["row_set"] for b in blocks]), "no row is in two blocks"

    def test_a_table_that_fits_in_one_call_is_not_split(self):
        assert RC.row_blocks(self._table(10)) == []

    def test_the_header_is_drawn_into_every_block(self):
        wrap = ET.fromstring(WRAP)
        block = RC.table_html(wrap, keep_rows={4}, note="rows 4-4 of this table, block 1 of 2")
        assert "Coefficient" in block and "Outcome" in block, "the header rows are never dropped"
        assert "Reach" in block and "Fidelity" not in block
        assert "block 1 of 2" in block, "the image says which rows of the table it is"

    def test_the_union_of_the_blocks_verifies_against_the_whole_walker_table(self):
        t = self._table(100)
        blocks = RC.row_blocks(t)
        cols = t["col_labels"]
        recons = [self._reading(b["cells"], cols) for b in blocks]
        ver = RC.verify_blocks(t, blocks, recons)
        assert ver["verified"] is True, ver["reasons"]
        assert ver["n_blocks"] == 3 and ver["n_blocks_read"] == 3
        assert ver["n_entries"] == 400

    def test_a_missing_block_is_refused_and_named(self):
        t = self._table(100)
        blocks = RC.row_blocks(t)
        cols = t["col_labels"]
        recons = [self._reading(blocks[0]["cells"], cols), None,
                  self._reading(blocks[2]["cells"], cols)]
        ver = RC.verify_blocks(t, blocks, recons)
        assert ver["verified"] is False and ver["n_blocks_read"] == 2
        assert any("block 2 of 3" in r and "has no reading" in r for r in ver["reasons"]), ver["reasons"]

    def test_a_block_that_read_the_repeated_header_differently_is_named(self):
        t = self._table(100)
        blocks = RC.row_blocks(t)
        cols = t["col_labels"]
        odd = self._reading(blocks[1]["cells"], ["c1", "c2", "c3", "c4 (renamed)"])
        ver = RC.verify_blocks(t, blocks,
                               [self._reading(blocks[0]["cells"], cols), odd,
                                self._reading(blocks[2]["cells"], cols)])
        assert ver["verified"] is False
        assert any("read the repeated header differently" in r for r in ver["reasons"])

    def test_the_driver_takes_the_block_path_and_buys_nothing_with_the_model_off(self, tmp_path):
        if not RC.chrome_binary():
            pytest.skip("no headless Chromium on this machine")
        rows = "".join(f"<tr><td>Study {r}</td><td>{r}.11</td><td>{r}.22</td><td>{r}.33</td></tr>"
                       for r in range(2, 102))
        wrap = ET.fromstring(
            '<table-wrap id="T2"><label>Table 2</label><table><thead><tr><th>Study</th>'
            f'<th>c1</th><th>c2</th><th>c3</th></tr></thead><tbody>{rows}</tbody></table></table-wrap>')
        root = ET.fromstring("<article><body/></article>")
        root[0].append(wrap)
        t = self._table(100, cols=3)
        t.update({"wrap_id": "T2", "table_num": 1})
        rec = RC.reconstruct_table(tmp_path, t, 2, tmp_path / "tables",
                                   model=None, root=root, problems=[])
        assert [b["index"] for b in rec["blocks"]] == [1, 2], "300 cells is two blocks"
        assert all(Path(b["png"]).exists() for b in rec["blocks"])
        assert rec["status"] == "not_attempted" and "none read" in rec["reason"]
        assert rec["cost_usd"] is None


class TestAnEmptyWalkedTableIsNotRendered:
    """The walker returns a table record with no cells for a `<table-wrap>` it
    could not read. `locate_pdf_table` refused those from the day it was
    written; the article path rendered them and would have read them --
    10.1038/s41392-026-02904-0 carries two."""

    def test_it_is_recorded_as_empty_after_walk_and_nothing_is_drawn(self, tmp_path):
        root = ET.fromstring(f"<article><body>{WRAP}</body></article>")
        table = {"label": "Table 2", "wrap_id": "T2", "table_num": 1, "position": 1, "cells": []}
        problems: list[str] = []
        rec = RC.reconstruct_table(tmp_path, table, 2, tmp_path / "tables",
                                   model="sonnet", root=root, problems=problems)
        assert rec["status"] == "empty_after_walk"
        assert "could not be verified against anything" in rec["reason"]
        assert rec["png"] is None and rec["cost_usd"] is None
        assert not (tmp_path / "tables").exists(), "no image is drawn for a table with no cells"
        assert problems and "empty_after_walk" in problems[0]

    def test_a_table_with_cells_is_unaffected(self, tmp_path):
        if not RC.chrome_binary():
            pytest.skip("no headless Chromium on this machine")
        root = ET.fromstring(f"<article><body>{WRAP}</body></article>")
        table = {"label": "Table 2", "wrap_id": "T2", "table_num": 1, "position": 1,
                 "cells": list(WALKER)}
        rec = RC.reconstruct_table(tmp_path, table, 2, tmp_path / "tables",
                                   model=None, root=root, problems=[])
        assert rec["status"] == "not_attempted" and rec["png"], "drawn, then not bought"


class TestTheRenderDoesNotCarryTheWalkersGuess:
    """E3 of the walker-as-witness spec (2026-09-08): the image the model reads
    must be the table as PRINTED, and must not encode `n_header_rows` -- the
    walker's own guess about which rows are header. If it did, a walker mistake
    would not merely be mis-scored, it would be transmitted to the one reading
    this design exists to trust instead.

    MEASURED, all four renderers, on a table whose first row is genuinely data:
    `docx_table_html` emits every cell as `<td>` with no styling; `table_html`
    takes no walker record at all and draws the publisher's own markup;
    `render_png` writes the HTML it was handed, byte for byte, and sizes its
    window from the `<tr>` count; the PDF-page crop DID depend on the guess and
    was fixed in the same commit (`region_strings`).
    """

    GRID = [["CFC - IGF-IIR", "7-9", "43.83", "3.64"],
            ["CFC - IGF-IIR", "7-9", "51.20", "4.10"],
            ["CFC - Veh", "8", "39.05", "2.98"]]

    def _docx_first_row_is_data(self, tmp_path):
        docx = pytest.importorskip("docx")
        d = docx.Document()
        t = d.add_table(rows=len(self.GRID), cols=4)
        for r, row in enumerate(self.GRID):
            for c, v in enumerate(row):
                t.cell(r, c).text = v
        path = tmp_path / "paper_supplementary_info_1_s001.docx"
        d.save(str(path))
        return path

    def test_a_word_supplement_is_drawn_with_no_header_marking_at_all(self, tmp_path):
        h = RC.docx_table_html(self._docx_first_row_is_data(tmp_path), 1, label="s001.docx :: Table 1")
        assert h and "<th" not in h.lower(), "every cell is a <td>; the render marks no row as header"
        assert h.count("<td") == 12 and h.count("<tr") == 3
        assert "style=" not in h.lower() and "<b>" not in h.lower() and "bold" not in h.split("<body>")[1]

    def test_the_jats_render_is_the_publishers_markup_and_takes_no_walker_record(self):
        import inspect
        assert "header" not in str(inspect.signature(RC.table_html))
        no_thead = ("<table-wrap id='T1'><label>Table 1</label><table><tbody>"
                    + "".join("<tr>" + "".join(f"<td>{v}</td>" for v in row) + "</tr>" for row in self.GRID)
                    + "</tbody></table></table-wrap>")
        h = RC.table_html(ET.fromstring(no_thead))
        assert h and "<th" not in h.lower(), "no <thead> in the source, so no header marking in the render"

    def test_render_png_draws_the_html_it_was_handed_byte_for_byte(self, tmp_path):
        # The window height is a function of the `<tr>` count and nothing else,
        # and the sidecar Chromium is pointed at is the caller's own HTML.
        html = "<html><body><table><tr><td>1</td></tr><tr><td>2</td></tr></table></body></html>"
        out = tmp_path / "t.png"
        RC.render_png(html, out, chrome="/nonexistent/chrome")
        assert out.with_suffix(".html").read_text(encoding="utf-8") == html
        assert RC._estimated_height(html) == RC._estimated_height(html.replace("<td>", "<th>"))

    def test_the_pdf_page_crop_is_the_same_image_at_every_header_depth(self, tmp_path):
        """THE ONE THAT FAILED. `_table_needles` was built from `cell_strings`
        plus the FLATTENED column labels, so the walker's depth decided which
        strings were looked for on the page: at depth 2 the needles are
        `N | 620`, a string the page never printed, the located share falls to
        73% and `_add_band` refuses to draw the page at all. Three depths, three
        different images, one of them no image."""
        pytest.importorskip("fitz", reason="PyMuPDF is not installed")
        from forensic_metascience_ai_toolkit.extraction import supplements_read as SR
        path = TestAPageIsNotATable()._pdf(tmp_path, [
            (100, ["Table 6. Allele frequencies by sex", "Population   N     H     L",
                   "Males        620   0.051 0.503", "Females      340   0.072 0.474",
                   "Unknown      117   0.064 0.488"]),
            (500, ["Table 7. Genotypes by ancestry", "Population        N     HH    HL",
                   "African-Americans 263   0.421 0.452", "Whites            379   0.223 0.501"])])

        def walked(grid, depth, label):
            t = SR._finish(grid=[list(r) for r in grid], caption=None, table_num=1, label=label,
                           section="", source="supplement", page=1, header_rows=depth)
            return {"label": f"{path.name} :: {label}", "walker_label": f"{path.name} :: {label}",
                    "supplement_file": path.name, "source": "supplement", "supplement_page": 1,
                    "cells": t["cells"], "header_rows": t["header_rows"],
                    "n_header_rows": t["n_header_rows"],
                    "row_labels": list(dict.fromkeys(c["row_label"] for c in t["cells"])),
                    "col_labels": list(dict.fromkeys(c["col_label"] for c in t["cells"]))}

        mine = [["Population", "N", "H", "L"], ["Males", "620", "0.051", "0.503"],
                ["Females", "340", "0.072", "0.474"], ["Unknown", "117", "0.064", "0.488"]]
        other = walked([["Population", "N", "HH", "HL"], ["African-Americans", "263", "0.421", "0.452"],
                        ["Whites", "379", "0.223", "0.501"]], 1, "Table 7 (p. 1)")
        drawn = []
        for depth in (0, 1, 2):
            t = walked(mine, depth, "Table 6 (p. 1)")
            assert t["n_header_rows"] == depth, "the fixture drives the depth it means to"
            html, png, meta, why = RC.supplement_table_render(tmp_path, t, tmp_path / f"d{depth}.png",
                                                              siblings=[other])
            assert why is None and png is not None, f"depth {depth}: {why}"
            drawn.append((png.read_bytes(), meta["clip"]))
        assert len({d for d, _ in drawn}) == 1, "one printed table, one image, whatever the walker guessed"
        assert len({tuple(c) for _, c in drawn}) == 1


class TestConservationOverTheRegion:
    """`verify_coarse`: the same verdict as `verify`, computed over every string
    the walked region prints rather than over the cells the walker called DATA.

    The defect it closes: a row misfiled as a header leaves `walker_cells`, so
    its digits reach `verify` only through the flattened column labels, where a
    SET counts them once however often they were printed -- while the reading,
    which read the row correctly off the image, counts them per cell. The two
    are then incomparable and an honest reading is refused.
    """

    GRID_H1 = {
        "n_header_rows": 1,
        "header_rows": [["Group", "5", "5", "12"]],
        "cells": [{"row": 2, "col": 1, "row_label": "Males", "col_label": "5", "raw": "620"},
                  {"row": 2, "col": 2, "row_label": "Males", "col_label": "5", "raw": "0.051"},
                  {"row": 2, "col": 3, "row_label": "Males", "col_label": "12", "raw": "0.503"}],
        "row_labels": ["Males"], "col_labels": ["5", "12"]}

    @staticmethod
    def _row(row_label, cells, section=None):
        return [{"row_label": row_label, "section": section, "column_index": i,
                 "column_label": f"(unlabelled column {i})", "cell": text, "variable": row_label,
                 "level": None, "group": None, "variable_id": None, "level_id": None, "group_id": None,
                 "statistic": stat, "statistic_basis": "cell_form", "value": val}
                for i, (text, stat, val) in enumerate(cells, start=1)]

    def _read(self, third="0.503"):
        return {"caption": None, "notes": "no header row; the columns are unlabelled",
                "column_labels": [f"(unlabelled column {i})" for i in (1, 2, 3)],
                "entries": self._row("Group", [("5", "n", "5"), ("5", "n", "5"), ("12", "n", "12")])
                + self._row("Males", [("620", "n", "620"), ("0.051", "p", "0.051"), (third, "p", third)])}

    def test_a_data_row_the_walker_filed_as_a_header_conserves(self):
        # The walker took row 0 for the header, so `5` reaches `verify` once as a
        # column label while the reading prints it twice. Nothing was invented.
        old = RC.verify(self.GRID_H1["cells"], self._read())
        assert not old["verified"] and any("does not contain: ['5']" in r for r in old["reasons"])
        new = RC.verify_coarse(self.GRID_H1, self._read())
        assert new["verified"], new["reasons"]
        assert new["n_walker_tokens"] == new["n_recon_tokens"] == 7

    def test_it_did_not_become_a_rubber_stamp(self):
        v = RC.verify_coarse(self.GRID_H1, self._read(third="0.507"))
        assert not v["verified"]
        assert any("does not contain" in r and "507" in r for r in v["reasons"])
        assert any("absent from the reading" in r and "503" in r for r in v["reasons"])
        assert any("traceable to no walker cell" in r for r in v["reasons"])

    def test_a_header_that_is_itself_a_number_is_present_not_missing(self):
        # THE CORRECTNESS QUESTION the region pool raises: widening the walker's
        # side to the header block means the reading must account for the header's
        # digits too. It does -- a column headed `2019` is `column_labels[0]` and
        # `column_label` on every cell beneath it, so the token balances.
        table = {"n_header_rows": 1, "header_rows": [["Measure", "2019", "2020"]],
                 "row_labels": ["Enrolled"], "col_labels": ["2019", "2020"],
                 "cells": [{"row": 2, "col": 1, "row_label": "Enrolled", "col_label": "2019", "raw": "412"},
                           {"row": 2, "col": 2, "row_label": "Enrolled", "col_label": "2020", "raw": "389"}]}
        read = {"caption": None, "column_labels": ["2019", "2020"], "notes": None,
                "entries": self._row("Enrolled", [("412", "n", "412"), ("389", "n", "389")])}
        for i, e in enumerate(read["entries"]):
            e["column_label"] = ["2019", "2020"][i]
        v = RC.verify_coarse(table, read)
        assert v["verified"], v["reasons"]
        assert v["n_walker_tokens"] == 4, "2019, 2020, 412, 389 -- the header counts"

    def test_the_stub_columns_own_heading_is_not_required_of_the_reading(self):
        # The one region string the schema gives the reading nowhere to put:
        # `column_labels` is defined as the leaf headers EXCLUDING the stub.
        # Requiring it would refuse a reading for obeying its instructions.
        table = {"n_header_rows": 1, "header_rows": [["Measure (n = 3 studies)", "Mean"]],
                 "row_labels": ["Age"], "col_labels": ["Mean"],
                 "cells": [{"row": 2, "col": 1, "row_label": "Age", "col_label": "Mean", "raw": "41.2"}]}
        read = {"caption": None, "column_labels": ["Mean"], "notes": None,
                "entries": self._row("Age", [("41.2", "mean", "41.2")])}
        read["entries"][0]["column_label"] = "Mean"
        v = RC.verify_coarse(table, read)
        assert v["verified"], v["reasons"]
        assert v["stub_headings_not_required"] == ["Measure(n=3studies)"]

    def test_a_caption_printed_as_the_first_grid_row_is_accounted_for(self):
        # `supplements_read._finish` keeps a Word table's caption row in
        # `header_rows`, so its digits are in the region; the reading puts them in
        # `caption`, which is therefore counted when the region prints it.
        table = {"n_header_rows": 2, "row_labels": ["Drug"], "col_labels": ["n", "Mean"],
                 "header_rows": [["eTable 4. Outcomes at 12 months", "", ""], ["Arm", "n", "Mean"]],
                 "cells": [{"row": 3, "col": 1, "row_label": "Drug", "col_label": "n", "raw": "64"},
                           {"row": 3, "col": 2, "row_label": "Drug", "col_label": "Mean", "raw": "3.1"}]}
        read = {"caption": "eTable 4. Outcomes at 12 months", "column_labels": ["n", "Mean"],
                "notes": None, "entries": self._row("Drug", [("64", "n", "64"), ("3.1", "mean", "3.1")])}
        for i, e in enumerate(read["entries"]):
            e["column_label"] = ["n", "Mean"][i]
        assert RC.verify_coarse(table, read)["verified"]

    def test_twins_are_two_and_a_third_twin_is_refused(self):
        # What the distinct-string pool gives up is multiplicity, so the ceiling
        # is restored from the other side: a reading may not claim more copies of
        # a printed string than the region holds anywhere.
        table = {"n_header_rows": 1, "header_rows": [["Arm", "Baseline"]],
                 "row_labels": ["A", "B"], "col_labels": ["Baseline"],
                 "cells": [{"row": 2, "col": 1, "row_label": "A", "col_label": "Baseline", "raw": "1 [Reference]"},
                           {"row": 3, "col": 1, "row_label": "B", "col_label": "Baseline", "raw": "1 [Reference]"}]}
        ok = {"caption": None, "column_labels": ["Baseline"], "notes": None,
              "entries": self._row("A", [("1 [Reference]", "ratio", "1")])
              + self._row("B", [("1 [Reference]", "ratio", "1")])}
        assert RC.verify_coarse(table, ok)["verified"]
        three = {**ok, "entries": ok["entries"] + self._row("C", [("1 [Reference]", "ratio", "1")])}
        v = RC.verify_coarse(table, three)
        assert not v["verified"] and any("more times than the table prints" in r for r in v["reasons"])

    def test_the_region_is_the_same_whatever_the_walker_guessed(self):
        headerless = {"n_header_rows": 0, "header_rows": [], "row_labels": ["Group", "Males"],
                      "col_labels": ["(unlabelled column 1)", "(unlabelled column 2)",
                                     "(unlabelled column 3)"],
                      "cells": [{"row": 1, "col": 1, "row_label": "Group", "col_label": "(unlabelled column 1)", "raw": "5"},
                                {"row": 1, "col": 2, "row_label": "Group", "col_label": "(unlabelled column 2)", "raw": "5"},
                                {"row": 1, "col": 3, "row_label": "Group", "col_label": "(unlabelled column 3)", "raw": "12"},
                                {"row": 2, "col": 1, "row_label": "Males", "col_label": "(unlabelled column 1)", "raw": "620"},
                                {"row": 2, "col": 2, "row_label": "Males", "col_label": "(unlabelled column 2)", "raw": "0.051"},
                                {"row": 2, "col": 3, "row_label": "Males", "col_label": "(unlabelled column 3)", "raw": "0.503"}]}
        assert RC.region_tokens(self.GRID_H1) == RC.region_tokens(headerless)
        assert RC.verify_coarse(headerless, self._read())["verified"]

    def test_it_agrees_with_verify_on_every_fixture_in_this_module(self):
        # E1's control: nothing the old check accepts becomes a refusal here, and
        # nothing it refuses is waved through, on the fixtures already in the suite.
        cases = {
            "good": GOOD,
            "invented": _with_entries(*GOOD["entries"][:2],
                                      _e("Reach", None, "Model 1", "p", ".02", ".02", "Reach",
                                         "Model 1 | p", "Panel A (N=64)"), *GOOD["entries"][3:]),
            "dropped": _with_entries(*GOOD["entries"][:3]),
            "off_cell": _with_entries(*GOOD["entries"][:2],
                                      _e("Reach", None, "Model 1", "p", ".002", "3.16 (0.98)", "Reach",
                                         "Model 1 | p", "Panel A (N=64)"), *GOOD["entries"][3:]),
            "bad_statistic": _with_entries(*GOOD["entries"][:5], {**GOOD["entries"][5], "statistic": "pvalue"}),
            "inferred": _with_entries(*GOOD["entries"][:5], {**GOOD["entries"][5], "statistic_basis": "inferred"}),
            "adjudicated": _with_entries(*GOOD["entries"][:5],
                                         {**GOOD["entries"][5], "statistic_basis": "adjudicated"}),
        }
        for name, recon in cases.items():
            old = RC.verify(WALKER, recon)["verified"]
            new = RC.verify_coarse({"cells": WALKER}, recon)["verified"]
            assert old == new, f"{name}: verify {old}, verify_coarse {new}"
        assert RC.verify_coarse({"cells": WALKER}, GOOD)["verified"]

    def test_a_numeral_free_table_still_verifies_with_no_entries(self):
        table = {"cells": [{"row": 2, "col": 1, "row_label": "Registry",
                            "col_label": "URL", "raw": "http://www.cebc4cw.org/"}],
                 "row_labels": ["Registry"], "col_labels": ["URL"], "header_rows": [["Source", "URL"]]}
        v = RC.verify_coarse(table, {"caption": None, "column_labels": ["URL"], "notes": None, "entries": []})
        assert v["verified"] and v["n_entries"] == 0


# ---------------------------------------------------------------------------
# the region verdict is the one the driver keeps (2026-09-15)
# ---------------------------------------------------------------------------

#: The real walker cells of the ONE row of eTable 4 of
#: 10.1001--jamanetworkopen.2023.37679 that names the fused-row defect: a
#: converted PDF supplement whose text extraction ran four printed rows together,
#: so `189153851 28668870 10307907 8421099` -- four weighted Ns -- is one walker
#: cell and, with the spaces removed, one 32-digit run. Copied verbatim from the
#: walk, not invented.
FUSED_SUPPLEMENT = [
    {"row": 2, "col": c, "row_label": "Disability status No limitations 1 limitation 2 limitations",
     "col_label": lab, "raw": raw}
    for c, (lab, raw) in enumerate([
        ("Weighted No.", "189153851 28668870 10307907 8421099"),
        ("No suicide- related outcome", "81.2 (81.0-81.6) 11.6 (11.3-11.9) 4.0 (3.8-4.1) 3.2 (3.1-3.4)"),
        ("Suicidal ideation only", "55.4 (53.9-57.0) 22.8 (21.5-24.2) 11.9 (10.7-13.1) 9.8 (8.7-10.9)"),
    ], start=1)]


class TestTheRegionVerdictIsTheOneTheDriverKeeps:
    """`verify_coarse` decides what is kept; `verify` is the control beside it.

    MEASURED over the seventeen reference accounts on 2026-09-15, on readings
    already bought: `verify` refuses 24 of 72 tables and NINE of those refusals
    are false -- each of the nine reproduces every distinct numeral-bearing
    string its table prints, invents none, and reproduces all 355 stratum-M key
    cells of those tables verbatim, the ten proven-defective ones included. The
    region form refuses 15, keeps every refusal `verify` was right about, and
    turns none of `verify`'s 48 acceptances into a refusal.

    The trade it makes, measured on the same 54 accepted readings by mutating
    each one: a MISREAD digit is caught 54/54 by both forms -- the accusation
    channel is not widened at all -- while a DROPPED printed cell is caught
    53/54 by `verify` and 40/54 here. An omission costs a check that cannot run;
    a misread costs a wrong number reaching one.
    """

    def test_a_converted_pdf_supplement_that_fused_the_walker_rows_still_refuses(self):
        # The refusal that must survive: the walker is not a valid witness for
        # this table, and a correct reading of the page cannot balance against a
        # corrupted one. THE READING HERE IS THE RIGHT ANSWER -- each fused cell
        # split at the spaces the extractor kept -- and it must still be refused,
        # because what is wrong is the witness, not the reading.
        table = {"n_header_rows": 1, "cells": FUSED_SUPPLEMENT,
                 "header_rows": [["Characteristic", "Weighted No.", "No suicide- related outcome",
                                  "Suicidal ideation only"]],
                 "row_labels": [FUSED_SUPPLEMENT[0]["row_label"]],
                 "col_labels": [c["col_label"] for c in FUSED_SUPPLEMENT]}
        entries = []
        for c in FUSED_SUPPLEMENT:
            for piece in c["raw"].replace(") ", ")\x00").split("\x00"):
                for part in ([piece] if "(" in piece else piece.split()):
                    entries.append({"variable": "Disability status", "level": None, "group": None,
                                    "statistic": "n" if part.isdigit() else "percentage",
                                    "statistic_basis": "column_header",
                                    "value": part.split(" ")[0], "cell": part,
                                    "row_label": "No limitations", "section": "Disability status",
                                    "column_index": c["col"], "column_label": c["col_label"],
                                    "variable_id": None, "level_id": None, "group_id": None})
        recon = {"caption": None, "notes": None,
                 "column_labels": [c["col_label"] for c in FUSED_SUPPLEMENT], "entries": entries}
        v = RC.verify_coarse(table, recon)
        assert not v["verified"], "a fused walker row is a conservation failure, not a shorter table"
        assert any("18915385128668870103079078421099" in r for r in v["reasons"]), v["reasons"]
        assert not RC.verify(FUSED_SUPPLEMENT, recon)["verified"], "and the old form refused it too"

    def test_a_curly_quotation_mark_and_a_straight_one_are_one_string(self):
        # PMC5557087 Table 2. The banner the paper prints carries `(n=171)` in
        # curly quotes; the reading writes the same banner in straight ones. With
        # the two treated as different strings the reading's section is a label
        # the table does not print, its `171` is dropped, and a reading that
        # transcribed every cell correctly is refused for a digit run it did
        # carry. This was the ONLY table the region form lost, and the cause was
        # a quotation mark.
        curly = 'IPSS QOL “the way it is now” (n=171), n (%)'
        straight = 'IPSS QOL "the way it is now" (n=171), n (%)'
        assert RC._norm(curly) == RC._norm(straight)
        table = {"n_header_rows": 1, "header_rows": [["Outcome", "n (%)"]],
                 "row_labels": [f"{curly} | Delighted"], "col_labels": ["n (%)"],
                 "cells": [{"row": 2, "col": 1, "row_label": f"{curly} | Delighted",
                            "col_label": "n (%)", "raw": "12 (7.0)"}]}
        recon = {"caption": None, "column_labels": ["n (%)"], "notes": None,
                 "entries": [{"variable": "IPSS QOL", "level": "Delighted", "group": None,
                              "statistic": "count", "statistic_basis": "column_header",
                              "value": "12", "cell": "12 (7.0)", "row_label": "Delighted",
                              "section": straight, "column_index": 1, "column_label": "n (%)",
                              "variable_id": None, "level_id": None, "group_id": None}]}
        v = RC.verify_coarse(table, recon)
        assert v["verified"], v["reasons"]
        assert v["n_labels_not_printed"] == 0

    def test_a_misread_digit_is_still_refused(self):
        # The direction that can manufacture an accusation. Widening what is
        # accepted must not widen THIS.
        bad = _with_entries(*GOOD["entries"][:1],
                            _e("Reach", None, "Model 1", "coefficient", "3.17", "3.17 (0.98)",
                               "Reach", "Model 1 | Coefficient", "Panel A (N=64)"),
                            *GOOD["entries"][2:])
        v = RC.verify_coarse({"cells": WALKER}, bad)
        assert not v["verified"]
        assert any("317" in r or "3.17" in r for r in v["reasons"]), v["reasons"]

    def test_the_driver_keeps_the_region_verdict_and_records_no_substitution(self, tmp_path):
        # END TO END, no model: a table the walker filed at the wrong header
        # depth, a cached reading of it, and the driver keeping it. Under
        # `verify` the banner row's digits are counted once as a label and twice
        # by the reading, and this table was refused.
        if not RC.chrome_binary():
            pytest.skip("no headless Chromium on this machine")
        table, root, el = _wrap_table()
        key = RC._cache_key(table, RC.table_html(el), None)
        _seed_reading(tmp_path / "tables", "table_2.recon", key, GOOD)
        problems: list[str] = []
        rec = RC.reconstruct_table(tmp_path, table, 2, tmp_path / "tables",
                                   model=None, root=root, problems=problems)
        assert rec["status"] == "verified", rec.get("verification")
        assert (rec.get("verification") or {}).get("basis") == "region", "the region verdict, not the walker's"
        assert "substitution" not in rec
        assert table["entries"], "a kept reading replaces the walker's cells"

    def test_a_refused_reading_is_recorded_as_a_substitution_not_a_silence(self, tmp_path):
        # THE MONEY LEAK AND THE TYPING LEAK ARE THE SAME EVENT. A refusal used
        # to leave one sentence in `problems`; the account could not say which
        # of a table's cells were typed by a reading and which by the fallback.
        if not RC.chrome_binary():
            pytest.skip("no headless Chromium on this machine")
        table, root, el = _wrap_table()
        invented = _with_entries(*GOOD["entries"][:2],
                                 _e("Reach", None, "Model 1", "p", ".02", ".02", "Reach",
                                    "Model 1 | p", "Panel A (N=64)"), *GOOD["entries"][3:])
        key = RC._cache_key(table, RC.table_html(el), None)
        _seed_reading(tmp_path / "tables", "table_2.recon", key, invented, cost_usd=0.5)
        problems: list[str] = []
        rec = RC.reconstruct_table(tmp_path, table, 2, tmp_path / "tables",
                                   model=None, root=root, problems=problems)
        assert rec["status"] == "refused"
        sub = rec["substitution"]
        assert sub["happened"] is True
        assert sub["why"] == rec["verification"]["reasons"] and sub["why"]
        assert sub["basis"] == "region"
        assert sub["n_entries_discarded"] == len(invented["entries"])
        assert sub["n_walker_cells_used_instead"] == len(table["cells"])
        assert sub["reading_kept_at"] == ["tables/table_2.recon.json"], "the discarded reading is not deleted"
        assert Path(tmp_path / "tables" / "table_2.recon.json").is_file()
        assert sub["reading_cost_usd"] == 0.5 and "$0.50" in problems[0], problems
        assert "entries" not in table, "the walker's cells were kept, not the reading's"


def _wrap_table():
    """The WRAP fixture as the walker leaves it, with its banner row filed as data."""
    root = ET.fromstring("<article><body/></article>")
    el = ET.fromstring(WRAP)
    root[0].append(el)
    table = {"id": "table:2", "label": "Table 2", "wrap_id": "T2", "table_num": 2, "position": 1,
             "caption": "Outcomes by arm", "source": "article", "n_header_rows": 2,
             "header_rows": [["Outcome", "Model 1", "Model 1"], ["Outcome", "Coefficient", "p"]],
             "cells": [dict(c) for c in WALKER],
             "row_labels": ["Panel A (N=64)", "Reach", "Fidelity"],
             "col_labels": ["Model 1 | Coefficient", "Model 1 | p"],
             "footnotes": ["Note: N = 64 coalitions."], "n_cells": len(WALKER)}
    return table, root, el


def _seed_reading(out_dir: Path, name: str, key: str, data: dict, cost_usd: float | None = None) -> None:
    """A reading already paid for, put where `reading_store.reuse` looks first."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")
    (out_dir / f"{name}.meta.json").write_text(
        json.dumps({"cache_key": key, "model": "sonnet", "cost_usd": cost_usd, "problems": []}),
        encoding="utf-8")
