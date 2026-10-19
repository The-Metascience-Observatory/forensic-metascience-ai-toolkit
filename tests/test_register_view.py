"""The register inspector must not invent a join, and must not hide a gap."""
from __future__ import annotations

import pytest

from forensic_metascience_ai_toolkit import register_view as RV


class TestNumeralOffsetsAreVerifiedNotTrusted:
    """A drifted offset shifts every later span, so it is checked, not assumed."""

    def test_a_row_whose_offset_misses_its_token_is_dropped_and_counted(self):
        text = "the mean was 4.5 and n was 30"
        rows = [
            {"id": "a", "printed": "4.5", "offset": 13, "end": 16, "class": "statistic"},
            {"id": "b", "printed": "30", "offset": 0, "end": 2, "class": "statistic"},
        ]
        html, ok, dropped, overlap = RV.mark_numerals(text, rows)
        assert (ok, dropped, overlap) == (1, 1, 0)
        assert ">4.5<" in html
        # the bad row must not have marked "th" at offset 0
        assert not html.startswith("<span")

    def test_every_surviving_span_wraps_its_own_printed_text(self):
        text = "a 1.0 b 22.5 c"
        rows = [
            {"id": "a", "printed": "1.0", "offset": 2, "end": 5, "class": "statistic"},
            {"id": "b", "printed": "22.5", "offset": 8, "end": 12, "class": "ordinal"},
        ]
        html, ok, dropped, overlap = RV.mark_numerals(text, rows)
        assert (ok, dropped, overlap) == (2, 0, 0)
        assert ">1.0<" in html and ">22.5<" in html

    def test_overlapping_indexes_do_not_corrupt_the_page(self):
        text = "value 12.34 here"
        rows = [
            {"id": "a", "printed": "12.34", "offset": 6, "end": 11, "class": "statistic"},
            {"id": "b", "printed": "2.3", "offset": 7, "end": 10, "class": "statistic"},
        ]
        html, ok, bad, overlap = RV.mark_numerals(text, rows)
        assert (ok, bad, overlap) == (1, 0, 1), (
            "a skipped overlap must not be reported as drawn")
        assert html.count("<span") == ok
        # the untouched text either side must survive intact
        assert html.startswith("value ") and html.endswith(" here")

    def test_an_empty_index_marks_nothing_and_says_nothing(self):
        html, ok, dropped, overlap = RV.mark_numerals("no numbers here", [])
        assert (ok, dropped, overlap) == (0, 0, 0)
        assert "<span" not in html


class TestTheTableJoinKeysOnColumnLabel:
    """`anchor.col` is None on every value this register produces."""

    def _group(self, table, row, col_label, **kw):
        g = {"kind": "mean_sd", "anchor": {"where": "table", "table": table, "row": row},
             "values": [{"id": "v", "anchor": {"row": row, "col_label": col_label}}]}
        g.update(kw)
        return g

    def test_a_group_is_reachable_by_table_row_and_label(self):
        g = self._group("T1", 3, "Arm A")
        idx = RV.table_cell_index([g])
        assert idx[("T1", 3, "Arm A")] == [g]

    def test_two_groups_in_one_cell_are_both_kept(self):
        a = self._group("T1", 3, "Arm A")
        b = self._group("T1", 3, "Arm A", kind="p_value")
        idx = RV.table_cell_index([a, b])
        assert len(idx[("T1", 3, "Arm A")]) == 2, (
            "a mean and its SD share a cell; collapsing to one silently halves "
            "the register on the densest cells")

    def test_a_prose_group_never_enters_the_table_index(self):
        prose = {"kind": "mean_pm_prose", "anchor": {"where": "prose", "table": None},
                 "values": [{"id": "v", "anchor": {"row": None, "col_label": None}}]}
        assert RV.table_cell_index([prose]) == {}


class TestDispositionMirrorsCoverage:
    """The page must not invent a fourth vocabulary for the coverage strata."""

    @pytest.mark.parametrize("group,expected", [
        ({"checks": [{"tool": "grim"}], "dispatch_considered": True,
          "applicable_tools": ["grim"]}, "checked"),
        ({"checks": [], "dispatch_considered": True, "applicable_tools": []},
         "no_applicable_tool"),
        ({"checks": [], "dispatch_considered": True, "applicable_tools": ["grim"]},
         "silent"),
        ({"checks": [], "dispatch_considered": False, "applicable_tools": ["grim"]},
         "not_considered"),
    ])
    def test_each_stratum(self, group, expected):
        assert RV.group_disposition(group) == expected

    def test_every_disposition_is_documented(self):
        for name in ("checked", "no_applicable_tool", "silent", "not_considered"):
            assert name in RV.DISPOSITIONS
            blurb, _ = RV.DISPOSITIONS[name]
            assert blurb.strip(), f"{name} has no explanation for a reader"

    def test_silence_is_named_as_our_gap_not_the_paper_s(self):
        blurb, kind = RV.DISPOSITIONS["silent"]
        assert kind == "bad"
        assert "our" in blurb.lower() or "OUR" in blurb


class TestThePageRefusesToLaunderAbsence:
    def test_an_empty_register_does_not_render_as_a_clean_paper(self):
        html = RV.render({}, "text with 1 number", "body_md", [], "p")
        assert "lower bound" in html.lower()
        assert "0" in html

    def test_a_missing_text_source_is_reported_as_unknown(self):
        html = RV.render({}, "", None, [], "p")
        assert "UNKNOWN" in html, (
            "no readable source is unknown, never an absence of text")

    def test_a_table_with_no_cells_says_extraction_gap_not_empty_table(self):
        html = RV.render({}, "", "body_md", [{"label": "T1", "cells": []}], "p")
        assert "extraction gap" in html
        assert "not an empty table" in html

    def test_unmarked_cells_are_explained_rather_than_left_ambiguous(self):
        tables = [{"label": "T1", "extractor": "docling", "cells": [
            {"raw": "1.0", "row": 1, "row_label": "Age", "col_label": "Arm A"}]}]
        html = RV.render({"groups": []}, "", "body_md", tables, "p")
        assert "unmarked" in html.lower()
        assert "0 of 1" in html

    def test_dropped_offsets_are_surfaced_as_a_gap(self):
        reg = {"numerals": {"rows": [
            {"id": "a", "printed": "9.9", "offset": 0, "end": 3}], "n_total": 1}}
        html = RV.render(reg, "not a number at all", "body_md", [], "p")
        assert "did not land on" in html

    def test_no_gaps_found_is_not_a_claim_of_completeness(self):
        html = RV.render({"groups": [], "numerals": {"rows": [], "by_class": {}}},
                         "", "body_md", [], "p")
        assert "not a claim that the register is complete" in html
