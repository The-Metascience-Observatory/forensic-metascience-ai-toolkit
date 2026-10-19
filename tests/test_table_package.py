"""The derived split exists on disk and never becomes evidence.

Greg, 2026-08-27, resolving the standing "do NOT cut the table into synthetic
sub-tables" decision: "go ahead with the derived split, keep the register
anchored." The whole safety of that rests on one invariant, which is why it gets
the most tests here:

    A BLOCK ID NEVER APPEARS IN A VALUE ANCHOR, A FINDING, OR A CHECK.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit import table_package as TP

# A composite table: two banner sections, and labels carrying the pipe that the
# stacked-header fold introduces.
CELLS = [
    {"raw": "Gender", "row": 1, "row_label": "Gender", "col_label": "Overall"},
    {"raw": "1254 (44.3)", "row": 2, "row_label": "Female", "col_label": "Overall"},
    {"raw": "646 (50.0)", "row": 2, "row_label": "Female",
     "col_label": "Patterns | Arm A"},
    {"raw": "1576 (55.7)", "row": 3, "row_label": "Male", "col_label": "Overall"},
    {"raw": "647 (50.0)", "row": 3, "row_label": "Male",
     "col_label": "Patterns | Arm A"},
    {"raw": "Age group", "row": 4, "row_label": "Age group", "col_label": "Overall"},
    {"raw": "229 (8.1)", "row": 5, "row_label": "25 and under",
     "col_label": "Overall"},
    {"raw": "90 (7.0)", "row": 5, "row_label": "25 and under",
     "col_label": "Patterns | Arm A"},
]


def _cells_in(md: str) -> int:
    """Cells in the first data row, respecting escaped pipes."""
    row = [l for l in md.splitlines() if l.startswith("| ")][1]
    return len(re.split(r"(?<!\\)\|", row)) - 2


class TestMarkdownIsNotSilentlyCorrupted:
    """A label containing `|` splits the row and markdown renders a table with
    the wrong number of columns and the values shifted -- a corruption that
    still looks like a table."""

    def test_an_embedded_pipe_is_escaped(self):
        assert TP._cell("Typical antipsychotics | No") == r"Typical antipsychotics \| No"

    def test_a_newline_would_end_the_row_and_is_removed(self):
        assert "\n" not in TP._cell("two\nlines")

    def test_none_becomes_empty_not_the_string_None(self):
        assert TP._cell(None) == ""

    def test_header_separator_and_rows_all_agree(self):
        md = TP._markdown(CELLS, "T")
        header = [l for l in md.splitlines() if l.startswith("| ")][0]
        sep = [l for l in md.splitlines() if l.startswith("|---")][0]
        n_header = len(re.split(r"(?<!\\)\|", header)) - 2
        assert n_header == sep.count("---") == _cells_in(md)

    def test_the_grid_is_built_from_col_label_not_a_col_index(self):
        """A walked cell carries no `col`. Reading one yields a one-column
        table on every paper while looking correct."""
        rows, cols, idx = TP._grid(CELLS)
        assert len(cols) == 2
        assert {idx["col_labels"][c] for c in cols} == {"Overall", "Patterns | Arm A"}


# PLOS ONE 10.1371/journal.pone.0042828 Table 2, two body rows of it. The XML
# prints each spanner ("Locomotor Activity") as two `colspan="1"` cells, so the
# fold gives columns 2 and 4 the SAME label, "Activity | Day28 ISCH".
OPEN_FIELD = [("CON(6)", "51.9±2.1", "45.9±2.3", "18.4±1.3", "16.5±0.8",
               "72.7±2.5", "71.3±2.0"),
              ("CMS(6)", "52.1±1.8", "40.1±2.0a", "17.8±0.8", "11.2±0.7a",
               "71.7±2.6", "62.1±3.1a")]


def _open_field_xml(spanned: bool) -> str:
    if spanned:
        top = ('<td rowspan="2">Group(n)</td><td colspan="2">Locomotor Activity</td>'
               '<td colspan="2">Rearing Activity</td>'
               '<td colspan="2">Sucrose preference (%)</td>')
        sub = "<td>Baseline</td><td>Day28 ISCH</td>" * 3
    else:
        top = "".join(f"<td>{w}</td>" for w in [
            "Group(n)", "Locomotor", "Activity", "Rearing", "Activity",
            "Sucrose", "preference (%)"])
        sub = "<td/>" + "<td>Baseline</td><td>Day28 ISCH</td>" * 3
    body = "".join("<tr>" + "".join(f"<td>{v}</td>" for v in r) + "</tr>"
                   for r in OPEN_FIELD)
    return ('<article><body><sec><p>Text.</p><table-wrap id="t2">'
            '<label>Table 2</label><caption><title>Open field.</title></caption>'
            f'<table><thead><tr>{top}</tr><tr>{sub}</tr></thead>'
            f'<tbody>{body}</tbody></table></table-wrap></sec></body></article>')


def _rows(md: str) -> list[list[str]]:
    lines = [l for l in md.splitlines() if l.startswith("| ")]
    return [[c.strip().replace("\\|", "|")
             for c in re.split(r"(?<!\\)\|", l)[1:-1]] for l in lines]


class TestATwoRowHeaderKeepsEveryColumn:
    """`tables/printed/01_table-2.md` for 10.1371/journal.pone.0042828 was
    written with 6 of the table's 7 columns: two columns shared a label, the
    writer keyed columns by label, and the second overwrote the first. The
    locomotor Day-28 values vanished and the rearing Day-28 values sat under the
    locomotor heading -- a human reading the export saw wrong data, while the
    analysts (reading cells by index) saw the right data."""

    def _export(self, tmp_path, spanned):
        paper = tmp_path / "paper"
        paper.mkdir()
        (paper / "paper.xml").write_text(_open_field_xml(spanned), encoding="utf-8")
        idx = TP.build(paper, out_dir=tmp_path / "out")
        assert not idx.get("error") and len(idx["printed"]) == 1
        return _rows((tmp_path / "out" / idx["printed"][0]["file"]).read_text(
            encoding="utf-8"))

    @pytest.mark.parametrize("spanned", [False, True])
    def test_every_value_is_written_in_its_own_column(self, tmp_path, spanned):
        header, *body = self._export(tmp_path, spanned)
        assert len(header) == 7, header
        assert [tuple(r) for r in body] == OPEN_FIELD

    def test_a_spanned_header_names_the_spanner_on_every_column(self, tmp_path):
        header, *_ = self._export(tmp_path, spanned=True)
        assert header[1:] == [
            "Locomotor Activity | Baseline", "Locomotor Activity | Day28 ISCH",
            "Rearing Activity | Baseline", "Rearing Activity | Day28 ISCH",
            "Sucrose preference (%) | Baseline",
            "Sucrose preference (%) | Day28 ISCH"]

    def test_a_split_word_header_keeps_both_same_named_columns(self, tmp_path):
        """The labels are the XML's own; the writer must not merge columns
        because two of them read alike."""
        header, *_ = self._export(tmp_path, spanned=False)
        assert header.count("Activity | Day28 ISCH") == 2

    def test_indexed_columns_are_ordered_by_index_not_first_appearance(self):
        """A column blank in the first row must not be moved to the end."""
        cells = [{"raw": "a", "row": 1, "col": 1, "row_label": "r1", "col_label": "X"},
                 {"raw": "c", "row": 1, "col": 3, "row_label": "r1", "col_label": "Z"},
                 {"raw": "b", "row": 2, "col": 2, "row_label": "r2", "col_label": "X"},
                 {"raw": "d", "row": 2, "col": 3, "row_label": "r2", "col_label": "Z"}]
        header, r1, r2 = _rows(TP._markdown(cells, "T"))
        assert header == ["", "X", "X", "Z"]
        assert r1 == ["r1", "a", "", "c"] and r2 == ["r2", "", "b", "d"]


class TestTheDerivedPackage:
    def test_it_writes_printed_and_blocks(self, tmp_path, monkeypatch):
        idx = self._build(tmp_path, monkeypatch)
        assert idx["printed"], "the printed table must always be written"
        assert (tmp_path / "out" / idx["printed"][0]["file"]).is_file()

    def test_every_block_carries_provenance_to_a_printed_table(self, tmp_path, monkeypatch):
        idx = self._build(tmp_path, monkeypatch)
        printed = {p["label"] for p in idx["printed"]}
        for b in idx["blocks"]:
            assert b["printed_table_label"] in printed
            assert b["printed_row_indices"], "a block must say which printed rows it holds"
            assert b["is_evidence"] is False

    def test_a_block_is_never_labelled_like_a_table_the_paper_printed(self, tmp_path, monkeypatch):
        """"Table 1b" is a label the paper does not have, and a reader would
        reasonably believe it was printed."""
        idx = self._build(tmp_path, monkeypatch)
        for b in idx["blocks"]:
            assert "block" in b["block_id"]
            assert not re.search(r"Table \d+[a-z]\b", b["block_id"])

    def test_a_non_composite_table_gets_no_block(self, tmp_path, monkeypatch):
        """Writing a block for a table with no banner row would double every
        table on disk and invite a reader to cite the copy."""
        flat = [{"raw": "1", "row": 1, "row_label": "A", "col_label": "X"},
                {"raw": "2", "row": 2, "row_label": "B", "col_label": "X"}]
        idx = self._build(tmp_path, monkeypatch, cells=flat)
        assert idx["printed"] and not idx["blocks"]

    def test_the_index_and_captions_are_written(self, tmp_path, monkeypatch):
        self._build(tmp_path, monkeypatch)
        out = tmp_path / "out"
        assert (out / "index.json").is_file() and (out / "captions.md").is_file()
        assert json.loads((out / "index.json").read_text())["derived"] is True

    def test_every_block_file_declares_itself_derived(self, tmp_path, monkeypatch):
        idx = self._build(tmp_path, monkeypatch)
        for b in idx["blocks"]:
            text = (tmp_path / "out" / b["file"]).read_text(encoding="utf-8")
            assert "DERIVED" in text and "Cite the printed table" in text

    def _build(self, tmp_path, monkeypatch, cells=None):
        from forensic_metascience_ai_toolkit import table_package
        monkeypatch.setattr(
            "forensic_metascience_ai_toolkit.prepass.paper_tables",
            lambda *a, **k: [{"label": "Table 1", "cells": cells or CELLS,
                              "extractor": "test"}])
        return table_package.build(tmp_path, out_dir=tmp_path / "out")


class TestTheAnchoringInvariant:
    """The reason the standing decision survives: a block is a reading aid, and
    the moment it becomes evidence the provenance argument is lost."""

    def test_no_block_id_appears_in_a_value_anchor(self, tmp_path, monkeypatch):
        from forensic_metascience_ai_toolkit import table_package, values
        monkeypatch.setattr(
            "forensic_metascience_ai_toolkit.prepass.paper_tables",
            lambda *a, **k: [{"label": "Table 1", "cells": CELLS, "extractor": "t"}])
        idx = table_package.build(tmp_path, out_dir=tmp_path / "out")
        ids = TP.block_ids(idx)
        assert ids, "the fixture must actually produce blocks or this proves nothing"
        reg = values.build_from_paper(str(tmp_path), variables=[], bindings={})
        anchored = {str((g.get("anchor") or {}).get("table")) for g in reg.get("groups") or []}
        assert not (anchored & ids), (
            "a value anchored to a derived block would let a finding cite a "
            "table the paper never printed")

    def test_the_package_writes_nothing_the_register_reads(self, tmp_path, monkeypatch):
        """The register is built from the walked tables. Building the package
        must not change what it sees."""
        from forensic_metascience_ai_toolkit import table_package, values
        monkeypatch.setattr(
            "forensic_metascience_ai_toolkit.prepass.paper_tables",
            lambda *a, **k: [{"label": "Table 1", "cells": CELLS, "extractor": "t"}])
        before = values.build_from_paper(str(tmp_path), variables=[], bindings={})
        table_package.build(tmp_path, out_dir=tmp_path / "out")
        after = values.build_from_paper(str(tmp_path), variables=[], bindings={})
        assert before.get("n_values") == after.get("n_values")
        assert before.get("n_groups") == after.get("n_groups")


class TestItNeverFailsARun:
    def test_an_unreadable_paper_returns_a_structured_error(self, tmp_path):
        out = TP.build(tmp_path / "does-not-exist", out_dir=tmp_path / "o")
        assert isinstance(out, dict)
        assert out["printed"] == [] and out["blocks"] == []

    def test_block_ids_on_an_empty_index_is_an_empty_set(self):
        assert TP.block_ids({}) == set()
        assert TP.block_ids({"blocks": []}) == set()

class TestTheSplitIsLossless:
    """Greg, 2026-08-29, asking for the blocks in the viewer: "without seeing
    those subtables, I am still not certain that all the table data was properly
    extracted."

    That is the property, and it is checkable: every cell of the printed table
    appears in exactly one block. A split that quietly dropped a section would
    reassure a reader while hiding the thing they were checking for.
    """

    def test_every_parent_cell_lands_in_exactly_one_block(self):
        from forensic_metascience_ai_toolkit import table_package as TP
        table = {"label": "T", "cells": CELLS,
                 "sections": [{"row": 0, "label": "Gender"},
                              {"row": 4, "label": "Age group"}]}
        secs = TP._sections_from_record(table, CELLS)
        assert secs, "the record's own sections must be used"
        seen = [id(c) for s in secs for c in s["cells"]]
        assert len(seen) == len(CELLS), (
            f"{len(CELLS)} cells in, {len(seen)} out -- the split lost or "
            f"duplicated data")
        assert len(set(seen)) == len(seen), "a cell landed in two blocks"

    def test_the_records_sections_are_preferred_over_a_banner_scan(self):
        """MEASURED 2026-08-29 on `10.1002--ajcp.70049` Table 2: the record
        carries sections at rows 2 and 6, the cells start at row 3 and skip 6
        because the band rows are dropped before cells are built, and the banner
        scan therefore found ONE section and wrote ZERO blocks on a table that
        is visibly composite. Preferring the record took it to 10 blocks across
        the paper."""
        from forensic_metascience_ai_toolkit import table_package as TP
        table = {"label": "T", "cells": CELLS,
                 "sections": [{"row": 2, "label": "Recorded"}]}
        secs = TP._sections_from_record(table, CELLS)
        assert [s["label"] for s in secs] == [None, "Recorded"], (
            "rows before the first band must survive as a leading block")

    def test_no_sections_on_the_record_falls_back_rather_than_asserting_none(self):
        from forensic_metascience_ai_toolkit import table_package as TP
        assert TP._sections_from_record({"label": "T", "cells": CELLS}, CELLS) == []


class TestTheSecondInvariant:
    """A DERIVED BOUNDARY MAY NARROW A PREMISE, NEVER SUPPLY ONE.

    The invariant above protects PROVENANCE -- a finding cannot cite a table the
    paper never printed. It does not protect CORRECTNESS, and reading it as if
    it did is how a block-boundary error becomes an accusation with a perfectly
    honest citation attached.

    `table_package`'s own docstring gives three reasons for derived-not-cut: a
    finding citing "Table 1b"; `n_table_items` moving; two walkers disagreeing
    about how many tables exist. All three are about CITATION and COUNTING. None
    is about premises.

    But a cell's premises -- what kind of number it is, who it is about, what it
    was divided by -- are resolved by walking structure, and under a composite
    reading those paths differ per block. So a wrong boundary yields a wrong
    denominator, a wrong subject or a wrong role, and the finding names the
    right table while having read it as two tables it is not.

    THE GROUNDING CASE, from the PMC survey's own audit: PMC10972345 table t005
    repeats its header at body row 25 and then repeats rows 1-4 byte-for-byte.
    That is a PAGE-BREAK CONTINUATION, not a second logical table -- and an
    agent that reads the repeat as a block boundary gets a phantom second table
    whose values duplicate the first, with a flawless citation.

    Stated as the rule this pins: a derived boundary may cause a check to
    REFUSE; it may never be the reason a check RUNS, and it may never be the
    source of a denominator, a subject or a role. That makes boundary detection
    free -- getting it wrong costs coverage and cannot cost an accusation -- and
    it forecloses by construction the two promotions already proposed and
    rejected: an adjunct row's `n` becoming a denominator, and a band's variable
    binding the rows beneath it.
    """

    #: The continuation shape, minimised: a header repeat mid-body followed by
    #: rows already present above it.
    CONTINUATION = [
        {"raw": "1.01", "row": 1, "row_label": "Communication", "col_label": "Coefficient"},
        {"raw": ".01", "row": 1, "row_label": "Communication", "col_label": "p"},
        {"raw": "Driver", "row": 2, "row_label": "Indicator", "col_label": "Coefficient"},
        {"raw": "p_value", "row": 2, "row_label": "Indicator", "col_label": "p"},
        {"raw": "1.01", "row": 3, "row_label": "Communication", "col_label": "Coefficient"},
        {"raw": ".01", "row": 3, "row_label": "Communication", "col_label": "p"},
    ]

    def _package(self, tmp_path, monkeypatch, cells):
        from forensic_metascience_ai_toolkit import table_package
        monkeypatch.setattr(
            "forensic_metascience_ai_toolkit.prepass.paper_tables",
            lambda *a, **k: [{"label": "Table 1", "cells": cells, "extractor": "t"}])
        return table_package.build(tmp_path, out_dir=tmp_path / "out")

    def test_the_register_is_identical_with_and_without_the_package(
            self, tmp_path, monkeypatch):
        """The strongest form of "never supplies": every premise the register
        carries must be reachable without the derived split existing at all."""
        from forensic_metascience_ai_toolkit import values
        from forensic_metascience_ai_toolkit import table_package
        monkeypatch.setattr(
            "forensic_metascience_ai_toolkit.prepass.paper_tables",
            lambda *a, **k: [{"label": "Table 1", "cells": CELLS, "extractor": "t"}])
        without = values.build_from_paper(str(tmp_path), variables=[], bindings={})
        table_package.build(tmp_path, out_dir=tmp_path / "out")
        with_pkg = values.build_from_paper(str(tmp_path), variables=[], bindings={})
        premise = lambda reg: [
            {"anchor": g.get("anchor"), "row_label": g.get("row_label"),
             "col_label": g.get("col_label"), "kind": g.get("kind"),
             "variable_id": g.get("variable_id"),
             "roles": [v.get("role") for v in (g.get("values") or [])],
             "n": g.get("n"), "applicable_tools": g.get("applicable_tools")}
            for g in (reg.get("groups") or [])]
        assert premise(without) == premise(with_pkg)

    def test_blocks_declare_themselves_non_evidence(self, tmp_path, monkeypatch):
        idx = self._package(tmp_path, monkeypatch, CELLS)
        assert idx["blocks"], "the fixture must produce blocks or this proves nothing"
        assert all(b.get("is_evidence") is False for b in idx["blocks"])

    def test_a_continuation_boundary_cannot_reach_the_register(
            self, tmp_path, monkeypatch):
        """The grounding case. Whatever the package makes of a header repeat
        mid-body, the register must anchor every value to the printed table and
        must not acquire a premise from the split."""
        from forensic_metascience_ai_toolkit import values
        idx = self._package(tmp_path, monkeypatch, self.CONTINUATION)
        ids = TP.block_ids(idx)
        reg = values.build_from_paper(str(tmp_path), variables=[], bindings={})
        anchored = {str((g.get("anchor") or {}).get("table"))
                    for g in (reg.get("groups") or [])}
        assert not (anchored & ids)
        assert all((g.get("anchor") or {}).get("table") == "Table 1"
                   for g in (reg.get("groups") or []))
