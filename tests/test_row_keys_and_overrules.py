"""Two report-integrity defects: a colliding row key, and a divergence nobody saw.

DEFECT 9 -- `dispatch.check_table` stamps `check_id = f"r{i}.{tool}"`, where `i`
indexes THAT CALL's `cells` list. `agent._checkable_coverage` filed its "which
cells were checked" set under the bare `r{i}` prefix, so `r0` from the second
call overwrote `r0` from the first. MEASURED over the archive on 2026-08-12: 8
runs produced `check_table` results, and the prefix set held 116 keys against
195 (cell, call) adjudications -- 79 dispositions, 40%, deleted by the
collision, all of it in 2 runs (51 -> 12 and 48 -> 8). That count divides the
census denominator and prints as the paper's coverage.

DEFECT 7 -- `severity_reconcile.annotate` writes `severity_source` onto SWEEP
findings; `report.md` prints EDITORIAL findings. 39 blocks across 14 archived
runs, 26 of them cited by a report finding, and not one reached the markdown a
reader is handed. All 12 upgrades -- the direction that asserts more than the
check established -- are in that cited set.
"""
from __future__ import annotations

import pytest

from metascience_agent.agent import _checked_cell_key
from metascience_agent.census import render, summarise, cell_census
from metascience_agent.report_render import _render_checkable_detail


def _cell(row, col, raw):
    return {"row_label": row, "col_label": col, "raw": raw}


class TestTheRowKeyIsUniquePerCell:
    def test_the_same_prefix_in_two_calls_is_two_keys(self):
        """The defect itself: `r0` names a different cell in every call."""
        a = _checked_cell_key("r0", [_cell("Age", "Ctrl", "40.1 (2.2)")], "call-1")
        b = _checked_cell_key("r0", [_cell("BMI", "Ctrl", "22.4 (3.1)")], "call-2")
        assert a != b

    def test_the_same_cell_re_submitted_is_one_key(self):
        """NOT merely per-call uniqueness. The s11031 run re-ran three tables
        against a second candidate `n`; keying by the call would have counted
        each of those cells twice and inflated coverage from 175 to 195."""
        cells = [_cell("Age", "Ctrl", "40.1 (2.2)")]
        assert (_checked_cell_key("r0", cells, "call-1")
                == _checked_cell_key("r0", list(cells), "call-2"))

    def test_a_missing_argument_list_costs_the_dedup_and_never_the_row(self):
        a = _checked_cell_key("r0", [], "call-1")
        b = _checked_cell_key("r0", [], "call-2")
        assert a != b, "with no cells to identify, per-call is the floor"
        assert a != _checked_cell_key("r0", [_cell("Age", "C", "1")], "call-1"), (
            "the fallback must not be confusable with an identity key")

    def test_a_blank_cell_falls_back_rather_than_collapsing_every_blank(self):
        blank = [{"row_label": "", "col_label": "", "raw": ""}]
        assert (_checked_cell_key("r0", blank, "call-1")
                != _checked_cell_key("r0", blank, "call-2"))


class TestCoverageIsNotAFractionAcrossTwoPopulations:
    """The fix raises the numerator, and on one archived run it raises it past
    the denominator: 28 cells checked against 24 surveyed, because two of that
    run's four "tables" were means read out of the prose, which the census
    cannot see. `117%` is our accounting failure printed as the paper's number,
    and capping it at 100% would assert that every surveyed cell was checked --
    which is not established, and here was not true (16 of the 24 were)."""

    def _entries(self):
        return cell_census([_cell("OR", "OR (95% CI)", "1.42 (1.10-1.83)")])

    def test_no_percentage_is_published_over_one_hundred(self):
        s = summarise(self._entries(), n_checked=4)
        assert s["n_consumable"] == 1
        assert s["coverage"] is None
        assert s["checked_outside_census"] == 3
        assert "%" not in render(s)

    def test_an_ordinary_run_still_gets_its_fraction(self):
        s = summarise(self._entries(), n_checked=1)
        assert s["coverage"] == 1.0
        assert "census_undercounts" not in s

def _sweep(fid, direction, explained, tool="consistent", model="suspicious"):
    return {fid: {"id": fid, "technique": "grim",
                  "severity_source": {"tool": tool, "model": model,
                                      "direction": direction,
                                      "explained": explained, "note": "n/a"}}}


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__]))


class TestTheCheckedCountNeverReadsAsImpossible:
    """Unique row keys raised `checked` above `n_consumable` on two runs, and the
    detail line printed the pair as though one were a share of the other: "24 of
    24 surveyed; checked: 28". The counts are different populations -- the census
    walks the XML tables, the run may submit cells read out of the prose -- so
    where they provably differ the report says so instead."""

    def _detail(self, consumable, checked, n_cells=None):
        return _render_checkable_detail({"checkable": {
            "n_consumable": consumable, "n_cells": n_cells or consumable,
            "cells_checked_via_check_table": checked}})

    def test_an_excess_is_explained_rather_than_printed_bare(self):
        out = "\n".join(self._detail(24, 28))
        assert "checked:** 28" in out
        assert "at least 4 of the cells checked came from outside" in out

    def test_it_refuses_to_imply_every_surveyed_cell_was_checked(self):
        out = "\n".join(self._detail(24, 28))
        assert "does NOT mean every surveyed cell was checked" in out

    def test_the_ordinary_case_gains_no_extra_line(self):
        out = self._detail(24, 8)
        assert len(out) == 1 and "outside the tables" not in out[0]

    def test_equality_is_not_an_excess(self):
        out = self._detail(24, 24)
        assert len(out) == 1
