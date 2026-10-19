"""The verifier counts a repeated row stub the same way on both sides.

THE DEFECT (D47, ajcp.70049 table:6 -- the EBP rating crosswalk). The walker
lifted the first column out of the grid as the row stub, so `Evidence-based (1)`
was the row_label of three rows and `Not Evidence-based (0)` of four, and the
walker counted each ONCE through its label set. The reading kept that column as
a column, so the same two strings arrived as seven cells and their digits were
counted seven times. The reading was refused for 11 digit runs it had not
invented and 2 cells it had not made up, and the table's 19 numeral-bearing
cells fell to the grid path and read as `unparsed`.

Two rules make the two sides agree, and each can only move a digit the walker
ALREADY read as a label:

  1. a reading cell whose text is one of the walker's row stubs counts through
     the label set, exactly as the walker counts it;
  2. a reading label whose text the walker's table does not print carries no
     digits, and is named in `labels_not_printed` rather than dropped silently.

What is NOT touched is the digit conservation on VALUES: a digit the walker read
in a cell must still appear in the reading, once per printing, and a digit the
reading prints that the walker's table does not contain is still a refusal.
"""

from __future__ import annotations

import pytest

from forensic_metascience_ai_toolkit.scaffold import reconstruct


def _cells(rows: list[tuple[str, list[str]]], cols: list[str]) -> list[dict]:
    return [{"row": r_i, "col": c_i, "raw": raw, "row_label": stub, "col_label": cols[c_i - 1]}
            for r_i, (stub, raws) in enumerate(rows, start=1)
            for c_i, raw in enumerate(raws, start=1)]


def _reading(rows: list[tuple[str, list[str]]], cols: list[str]) -> dict:
    """A tidy reading that reads the stub column back as a first column, which
    is the shape that was refused."""
    out = []
    for r_i, (stub, raws) in enumerate(rows, start=1):
        for c_i, raw in enumerate([stub] + raws, start=1):
            out.append({"row_label": f"(row {r_i})", "section": None, "column_index": c_i,
                        "column_label": (["Stub"] + cols)[c_i - 1], "cell": raw,
                        "variable": "v", "level": raw, "group": None,
                        "variable_id": None, "level_id": None, "group_id": None,
                        "numbers": [{"statistic": "score", "statistic_basis": "cell_form", "value": n}
                                    for n in reconstruct.numeral_tokens(raw)]})
    return {"caption": None, "column_labels": ["Stub"] + cols, "notes": "", "cells": out}


#: Three rows under `Rated (1)` and two under `Unrated (0)`, the ajcp shape.
ROWS = [("Rated (1)", ["Model", "4"]), ("Rated (1)", ["--", "3"]), ("Rated (1)", ["Promising", "2"]),
        ("Unrated (0)", ["--", "1"]), ("Unrated (0)", ["--", "0"])]
COLS = ["Blueprints", "NREPP"]


class TestARepeatedStubVerifies:

    def test_the_reading_that_reads_the_stub_as_a_column_verifies(self):
        got = reconstruct.verify(_cells(ROWS, COLS), _reading(ROWS, COLS))
        assert got["verified"], got["reasons"]

    def test_the_stub_cells_are_counted_and_named(self):
        got = reconstruct.verify(_cells(ROWS, COLS), _reading(ROWS, COLS))
        assert got["n_stub_cells_counted_as_labels"] == 5

    def test_the_reading_s_own_positional_labels_are_named_not_silently_dropped(self):
        got = reconstruct.verify(_cells(ROWS, COLS), _reading(ROWS, COLS))
        assert got["n_labels_not_printed"] == 6           # (row 1)..(row 5) and `Stub`
        assert "(row 1)" in got["labels_not_printed"]

    def test_it_was_refused_before_the_rule(self):
        """The old count, reproduced by withholding the walker's cells from
        `_recon_tokens` -- so the test says what the rule changed, not only that
        the table passes now."""
        w = _cells(ROWS, COLS)
        old = reconstruct._recon_tokens(_reading(ROWS, COLS))
        new = reconstruct._recon_tokens(_reading(ROWS, COLS),
                                        reconstruct.walker_stubs(w),
                                        reconstruct.walker_printed(w))
        wt = reconstruct._walker_tokens(w)
        assert (old - wt) and not (new - wt)


class TestTheValueRuleIsUntouched:

    def test_a_digit_the_reading_invents_in_a_cell_is_still_a_refusal(self):
        bad = _reading(ROWS, COLS)
        bad["cells"][2]["cell"] = "99"
        got = reconstruct.verify(_cells(ROWS, COLS), bad)
        assert not got["verified"]
        assert any("does not contain" in r for r in got["reasons"])

    def test_a_digit_the_reading_drops_is_still_a_refusal(self):
        short = _reading(ROWS, COLS)
        short["cells"] = [c for c in short["cells"] if c["cell"] != "4"]
        got = reconstruct.verify(_cells(ROWS, COLS), short)
        assert not got["verified"]
        assert any("absent from the reading" in r for r in got["reasons"])

    def test_a_value_read_off_its_own_cell_is_still_a_refusal(self):
        bad = _reading(ROWS, COLS)
        bad["cells"][1]["numbers"] = [{"statistic": "score", "statistic_basis": "cell_form",
                                       "value": "7"}]
        got = reconstruct.verify(_cells(ROWS, COLS), bad)
        assert not got["verified"]

    def test_a_stub_the_walker_never_read_is_not_a_stub(self):
        """The walker's row-label set is the authority. A reading cell that
        matches no stub is a value and is counted as one, so the rule cannot be
        used to hide an invented number behind a column of repeats."""
        bad = _reading(ROWS, COLS)
        for c in bad["cells"]:
            if c["column_index"] == 1:
                c["cell"] = "Rated (7)"
        got = reconstruct.verify(_cells(ROWS, COLS), bad)
        assert not got["verified"]
        assert any("'7'" in r for r in got["reasons"])


class TestTheRuleIsOffWithoutTheWalkersCells:

    @pytest.mark.parametrize("fn", ["walker_stubs", "walker_printed"])
    def test_an_empty_walker_yields_an_empty_set(self, fn):
        assert getattr(reconstruct, fn)([]) == set()

    def test_recon_tokens_alone_keeps_every_label(self):
        r = _reading(ROWS, COLS)
        assert "1" in reconstruct._recon_tokens(r)
