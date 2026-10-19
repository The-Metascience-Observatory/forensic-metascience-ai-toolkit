"""A cell's physical position, from the walker to the register.

`col_label` is NOT an address. A stacked header can give several columns the
same label, and on a table whose header repeats a span that is the ordinary
case: 10.1002--ajcp.70049 Table 2 carries three identical
`<th colspan="2">Coefficient</th>` spans over three regression models, so the
identity of each model appears NOWHERE in the table.

MEASURED before this existed: 42 cells collapsed to 18 distinct
`(row_label, col_label)` pairs, 36 of the 42 sat at a shared address, and the
archived register carried `anchor.col: None` on 146 of 146 table groups while
`anchor.row` was populated throughout. The three covariate coefficients
`0.31 (0.04)`, `0.35 (0.04)` and `0.36 (0.05)` -- one per model -- were the
same address, so any term-level join would have assigned all three of the
paper's headline coefficients to the first model WHILE READING AS PROOF.

Why it is worth its own file: position is the half of extraction verification
that conservation cannot supply. Checking every claimed value against the
printed cells catches INVENTION and OMISSION; only position catches
MISASSIGNMENT. Demonstrated by injecting each failure into a structured reading
of that table -- a substituted derived statistic, a mistranscribed digit, a
hallucinated row and a dropped model are all caught by value conservation
alone; two values SWAPPED BETWEEN MODELS conserves perfectly and is caught only
by where they sit.
"""
from __future__ import annotations

import collections
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
PAPER = REPO / "tests/fixtures/papers/high_value_pdfs_to_run_on" / "10.1002--ajcp.70049" / "10.1002--ajcp.70049.xml"


@pytest.fixture(scope="module")
def tables():
    if not PAPER.is_file():
        pytest.skip("corpus paper not present in this checkout")
    from forensic_metascience_ai_toolkit.extraction.jats import extract_xml_tables
    return extract_xml_tables(str(PAPER))


class TestTheCoordinateRoundTrips:
    def test_data_row_minus_one_col_is_the_cell(self, tables):
        """The contract, stated as arithmetic rather than prose: `row` is
        1-based into `data` (which is `[header] + body`) and `col` is 0-based
        into the grid row. Mixed conventions are a trap, so this pins it."""
        checked = 0
        for t in tables:
            data = t.get("data") or []
            for c in t.get("cells") or []:
                assert c.get("col") is not None, (t.get("label"), c)
                assert data[c["row"] - 1][c["col"]].strip() == c["raw"].strip(), c
                checked += 1
        assert checked > 100, f"only {checked} cells checked; fixture too small to prove anything"


class TestPositionSeparatesWhatLabelsCannot:
    def test_labels_collide_and_coordinates_do_not(self, tables):
        t = next(x for x in tables if "2" in str(x.get("label", "")))
        cells = t["cells"]
        by_label = collections.Counter((c["row_label"], c["col_label"]) for c in cells)
        by_coord = collections.Counter((c["row"], c["col"]) for c in cells)
        assert len(by_coord) == len(cells), "coordinates must address every cell uniquely"
        assert len(by_label) < len(cells), (
            "this fixture is chosen BECAUSE its labels collide; if that stops "
            "being true the test proves nothing and must be re-grounded")

    def test_the_register_carries_the_column(self, tables):
        from forensic_metascience_ai_toolkit.tools.celltypes import parse_cells
        from forensic_metascience_ai_toolkit.values import build_register
        t = next(x for x in tables if "2" in str(x.get("label", "")))
        reg = build_register(tables=[{"name": "Table 2",
                                      "parsed": parse_cells(t["cells"]),
                                      "cells": t["cells"]}])
        groups = reg["groups"]
        coords = {((g["anchor"].get("row"), g["anchor"].get("col"))) for g in groups}
        assert all(g["anchor"].get("col") is not None for g in groups)
        assert len(coords) == len(groups), "every group must have its own address"

    def test_the_typer_does_not_drop_the_coordinates(self, tables):
        """The seam this regressed at THREE times in one day: a producer selects
        a few keys from a larger record and the rest dies between two functions
        that both had it. `parse_cells` copied the two LABELS and dropped the
        two INDICES."""
        from forensic_metascience_ai_toolkit.tools.celltypes import parse_cells
        t = tables[0]
        out = parse_cells(t["cells"])["cells"]
        assert all("col" in c and "row" in c for c in out)
