"""Group Findings (1.83.0): one tool family in one table or page range is one
entry in the review list, and a finding's numbers are highlighted cell by cell.
"""
import json

from forensic_metascience_ai_toolkit import finding_groups as FG  # noqa: N812


def _issue(i, tool="grim_check", sev=4, tables=(), pages=(), location=None,
           source="tool_verdict"):
    return {"id": f"f{i}", "kind": "numeric", "tool": tool, "tool_source": source,
            "severity_9": sev, "location": location,
            "location_basis": {"tables": list(tables), "pages": list(pages)}}


class TestRule:
    def test_one_family_in_one_table_is_one_entry(self):
        # grim_check and grim_percentage are one family.
        issues = [_issue(1, tables=["Table 2"]),
                  _issue(2, "grim_percentage", tables=["Table 2"]),
                  _issue(3, tables=["Table 3"])]
        entries = FG.group_issues(issues)
        assert sorted(len(e) for e in entries) == [1, 2]
        group = next(e for e in entries if len(e) == 2)
        assert group[0]["group"]["unit"] == "Table 2"
        assert group[0]["group"]["n"] == 2 and group[0]["group"]["family"] == "grim"
        assert "group" not in next(e for e in entries if len(e) == 1)[0]

    def test_a_table_named_only_in_the_location_text_counts(self):
        issues = [_issue(1, location="Table 2, row Age"),
                  _issue(2, location="table 2 (Weight)")]
        assert [len(e) for e in FG.group_issues(issues)] == [2]

    def test_different_tools_in_one_table_are_not_grouped(self):
        issues = [_issue(1, tables=["Table 2"]),
                  _issue(2, "statcheck", tables=["Table 2"])]
        assert [len(e) for e in FG.group_issues(issues)] == [1, 1]

    def test_prose_pages_group_when_within_one_page(self):
        issues = [_issue(1, pages=[4]), _issue(2, pages=[5]),
                  _issue(3, pages=[5, 6]), _issue(4, pages=[9])]
        entries = FG.group_issues(issues)
        assert sorted(len(e) for e in entries) == [1, 3]
        assert next(e for e in entries if len(e) == 3)[0]["group"]["unit"] == "pp. 4–6"

    def test_no_tool_or_no_place_is_never_grouped(self):
        issues = [_issue(1, tool=None, tables=["Table 2"]),
                  _issue(2, tool=None, tables=["Table 2"]),
                  _issue(3, source="not_recorded", tables=["Table 2"]),
                  _issue(4), _issue(5)]
        assert all(len(e) == 1 for e in FG.group_issues(issues))

    def test_an_old_docling_label_is_not_a_place(self):
        issues = [_issue(1, tables=["cref='#/texts/49'"]),
                  _issue(2, tables=["cref='#/texts/49'"])]
        assert all(len(e) == 1 for e in FG.group_issues(issues))

    def test_a_group_sits_where_its_worst_member_would(self):
        issues = [_issue(1, sev=6), _issue(2, sev=3, tables=["Table 2"]),
                  _issue(3, sev=8, tables=["Table 2"])]
        entries = FG.group_issues(issues)
        assert [e[0]["id"] for e in entries] == ["f3", "f1"]
        assert entries[0][0]["group"]["severity_9"] == 8


class TestServicePaging:
    def _service(self, tmp_path, n=60):
        from forensic_metascience_ai_toolkit.workbench.catalog import Catalog
        from forensic_metascience_ai_toolkit.workbench.service import Service
        c = Catalog(tmp_path / "cache.sqlite3")
        rows = [('corpora', '[1]', {'id': 1, 'name': 'project'}),
                ('papers', '[1]', {'id': 1, 'corpus_id': 1, 'dir': 'paper'}),
                ('runs', '[1]', {'id': 1, 'run_uid': 'r1', 'paper_id': 1,
                                 'component': 'comprehensive', 'status': 'complete'})]
        for i in range(1, n + 1):
            rows.append(('findings', f'[{i}]', {
                'id': i, 'run_id': 1, 'paper_id': 1, 'finding_id': f'F{i:03d}',
                'title': f'cell {i}', 'technique': 'grim_percentage',
                'outcome': 'problem', 'severity': 4,
                'tool_basis': {'tool_verdict': 'grim_percentage'},
                'location_basis': {'location': 'Table 3', 'pages': [4],
                                   'tables': ['Table 3']}}))
        rows.append(('findings', f'[{n + 1}]', {
            'id': n + 1, 'run_id': 1, 'paper_id': 1, 'finding_id': 'FX',
            'title': 'lone', 'technique': 'statcheck', 'outcome': 'problem',
            'severity': 3, 'tool_basis': {'tool_verdict': 'statcheck'},
            'location_basis': {'pages': [7], 'tables': []}}))
        c.apply_changes(rows, 1)
        return c, Service(c, background=False)

    def test_a_group_is_never_split_across_pages(self, tmp_path):
        c, s = self._service(tmp_path)
        try:
            got = s.handle('paper', {'project': 'project', 'dir': 'paper'})['issues']
            assert got['pagination']['total'] == 2          # two entries
            assert got['pagination']['findings_total'] == 61
            assert len(got['issues']) == 61                  # the whole group
            groups = {json.dumps(i.get('group'), sort_keys=True) for i in got['issues'][:60]}
            assert len(groups) == 1 and '"n": 60' in groups.pop()
            assert 'group' not in got['issues'][60]
        finally:
            c.close()

    def test_off_is_the_flat_list(self, tmp_path):
        c, s = self._service(tmp_path)
        try:
            got = s.handle('paper', {'project': 'project', 'dir': 'paper',
                                     'group': '0'})['issues']
            assert got['pagination']['total'] == 61 and len(got['issues']) == 50
            assert not any(i.get('group') for i in got['issues'])
        finally:
            c.close()


class TestCellAnchors:
    XML = """<?xml version="1.0"?>
<article><front><article-meta><title-group><article-title>T</article-title></title-group></article-meta></front>
<body><sec><p>Seventy patients per group.</p>
<table-wrap id="TAB3"><label>Table 3</label><caption><title>Incidence, %</title></caption>
<table><tbody>
<tr><td> </td><td>Group 1 (n=70)</td><td>Group 2 (n=70)</td><td>Group 3 (n=70)</td></tr>
<tr><td>POST</td><td>14.3</td><td>17.1</td><td>66.9</td></tr>
</tbody></table></table-wrap></sec></body></article>"""

    def _rows(self, paper):
        from forensic_metascience_ai_toolkit import grim_harness, prepass
        sweep = grim_harness.sweep_grim(
            prepass.paper_tables(paper, include_supplements=True),
            [{"table": "T1", "percent_of_units": True}])
        return grim_harness.finding_rows(sweep, paper.name)

    def test_an_xml_cell_is_addressed_by_table_row_and_column(self, tmp_path):
        from forensic_metascience_ai_toolkit import anchors
        from forensic_metascience_ai_toolkit.extraction.xml_html import article_view
        paper = tmp_path / "10.9999--demo"
        paper.mkdir()
        (paper / "10.9999--demo.xml").write_text(self.XML)
        rows = self._rows(paper)
        anchors.annotate_findings(paper, rows)
        cell = next(a for a in rows[0]["anchors"] if a["kind"] == "xml_cell")
        assert (cell["table_num"], cell["row"], cell["col"], cell["raw"]) == (1, 3, 3, "66.9")
        assert cell["status"] == "anchored" and cell["passage_key"].endswith("r3c3")
        # The rendered pane carries the same address, on the cell that prints it.
        html = article_view(paper)["html"]
        assert 'data-table-num="1"' in html
        assert '<td data-row="3" data-col="3">66.9</td>' in html
        # Re-annotation keeps the cell: the enriched record carries it.
        anchors.annotate_findings(paper, rows, force=True)
        assert [a["kind"] for a in rows[0]["anchors"]] == ["xml_cell"]

    def test_persisted_cell_anchors_become_targets_with_no_file(self, tmp_path):
        from forensic_metascience_ai_toolkit import anchors, locators
        paper = tmp_path / "10.9999--demo"
        paper.mkdir()
        (paper / "10.9999--demo.xml").write_text(self.XML)
        rows = self._rows(paper)
        anchors.annotate_findings(paper, rows)
        issue = {"id": rows[0]["finding_id"], "anchors": rows[0]["anchors"]}
        loc = locators.persisted_locators([issue])["locators"][0]
        t = loc["targets"][0]
        assert (t["kind"], t["table_num"], t["row"], t["col"]) == ("xml_cell", 1, 3, 3)
        assert locators.persisted_locators([{"id": "x", "anchors": [
            {"kind": "table_cell", "row": 1, "col": 1}]}])["locators"] == []


class TestPdfCellBox:
    """A box only where the row band settles it; never a guessed one."""

    def _pdf(self, path, rows):
        import fitz
        doc = fitz.open()
        page = doc.new_page(width=500, height=300)
        y = 60
        for label, values in rows:
            page.insert_text((40, y), label, fontsize=9)
            for k, v in enumerate(values):
                page.insert_text((220 + 60 * k, y), v, fontsize=9)
            y += 16
        doc.save(path)

    def _ctx(self, paper, cells):
        from forensic_metascience_ai_toolkit import anchors
        ctx = anchors._paper_ctx(paper)
        ctx["tables"] = [{"cells": cells}]
        return ctx

    def test_the_kth_equal_value_gets_the_kth_box(self, tmp_path):
        from forensic_metascience_ai_toolkit import anchors
        paper = tmp_path / "p"
        paper.mkdir()
        self._pdf(paper / "p.pdf", [("Accepting breech delivery", ["66.7", "65.9", "66.7"])])
        cells = [{"row": 2, "col": c, "raw": v, "row_label": "Accepting breech delivery"}
                 for c, v in [(1, "66.7"), (2, "65.9"), (3, "66.7")]]
        ctx = self._ctx(paper, cells)
        cell = {**cells[2], "table_key": "T1", "source": "article"}
        page, boxes, method = anchors._cell_pdf(ctx, cell)
        assert (page, method) == (1, "cell_row_band")
        assert boxes and boxes[0]["x0"] > 330      # the third column, not the first
        ctx["doc"].close()

    def test_a_count_mismatch_in_the_band_draws_no_box(self, tmp_path):
        from forensic_metascience_ai_toolkit import anchors
        paper = tmp_path / "p"
        paper.mkdir()
        # The page prints 66.7 three times; the extracted row has it twice.
        self._pdf(paper / "p.pdf", [("Accepting breech delivery", ["66.7", "66.7", "66.7"])])
        cells = [{"row": 2, "col": c, "raw": "66.7", "row_label": "Accepting breech delivery"}
                 for c in (1, 2)]
        ctx = self._ctx(paper, cells)
        page, boxes, method = anchors._cell_pdf(
            ctx, {**cells[0], "table_key": "T1", "source": "article"})
        assert boxes == [] and method in ("cell_page", "unlocated")
        ctx["doc"].close()
