"""The section gets a veto over the column header, in the register path too.

MEASURED 2026-08-27 on the corpus paper `10.1038--s41537-025-00576-3`:
`values.check_stated_denominators` returned 119 `suspicious` out of 244 checks
and ALL 119 WERE FALSE. It runs unconditionally from `agent.py` on every review
with NO MODEL IN THE LOOP, and `bundle.py` prints its tally straight to the
reader, so every one of those reached a human as an accusation.

THE MECHANISM. The false rows sit inside MULTI-RESPONSE sections -- a patient
appears on several drug rows -- so the section's counts sum ABOVE the column
total. `explaining_denominator` searches only DOWNWARD from n
(`range(n, count - 1, -1)`), so it structurally cannot find a denominator larger
than the header's; it reports no explanation, the near-miss downgrade never
fires, and the paper is accused of arithmetic it got right.

`check_table` already had this guard: `composite` refuses a column whose two
denominators disagree, in as many words. The register path never reached it,
because `dispatch` and the register are joined AFTER the run rather than before
it -- `dispatch.py` does not import `values.py` at all.

WHY THESE TESTS EXIST SEPARATELY. The existing suite for this function builds
every fixture through one helper that emits ONE cell, ONE row, no section band,
and sets `col_label` on the group anchor after the fact rather than on the cell.
That fixture cannot reach the new branch under any input -- it holds fixed the
very parameter the claim is about. See [[a-fixture-that-excludes-the-defect-region]].
"""
from __future__ import annotations

from metascience_agent import dispatch
from metascience_agent import values as V
from metascience_agent.tools.celltypes import parse_cells

COL = "Primary hypertension (n = 100)"

#: A multi-response section, the shape that produced all 119. Every percentage
#: is EXACT at a denominator of 120 (60/120, 36/120, 24/120) and wrong at the
#: header's 100 (60.0%, 36.0%, 24.0%). The paper is honest; only the pairing of
#: these rows to the column total is wrong.
COMPOSITE_CELLS = [
    {"raw": "Atypical antipsychotics", "row": 0,
     "row_label": "Atypical antipsychotics", "col_label": COL},
    {"raw": "60 (50.0)", "row": 1, "row_label": "Olanzapine, n (%)", "col_label": COL},
    {"raw": "36 (30.0)", "row": 2, "row_label": "Risperidone, n (%)", "col_label": COL},
    {"raw": "24 (20.0)", "row": 3, "row_label": "Quetiapine, n (%)", "col_label": COL},
]


def _register(cells):
    return V.build_register(
        tables=[{"name": "t1", "parsed": parse_cells(cells), "cells": cells}])


class TestTheFixtureIsNotVacuous:
    """The positive control. Without these assertions the tests below could
    pass on a fixture that never had the defect in it."""

    def test_composite_really_disputes_this_column(self):
        _derived, _pub, disputed = dispatch._section_denominators(COMPOSITE_CELLS)
        assert disputed, "the fixture must produce a disputed column or it proves nothing"
        assert "sum to 120" in next(iter(disputed.values()))

    def test_and_the_header_n_really_would_accuse_these_honest_rows(self):
        """The defect, reproduced directly: checked against the header's 100
        instead of the section's 120, every row is called suspicious."""
        from metascience_agent.tools.count_percent import check_count_percent
        for count, pct in ((60, 50.0), (36, 30.0), (24, 20.0)):
            assert check_count_percent(count=count, percentage=pct,
                                       n=100, decimals=1)["severity"] == "suspicious"
            assert check_count_percent(count=count, percentage=pct,
                                       n=120, decimals=1)["severity"] == "consistent"


class TestTheVetoFires:
    def test_a_disputed_column_is_refused_not_checked(self):
        reg = _register(COMPOSITE_CELLS)
        got = V.check_stated_denominators(reg)
        assert (got.get("by_severity") or {}).get("suspicious", 0) == 0, (
            "an honest multi-response section was accused")

    def test_the_refusal_says_why_in_the_papers_own_numbers(self):
        reg = _register(COMPOSITE_CELLS)
        V.check_stated_denominators(reg)
        why = " ".join(str(s) for s in (V.check_stated_denominators(reg).get("skipped")
                                        or {}).values() or [])
        blob = why + str(reg.get("_section_disputed"))
        assert "120" in blob and "100" in blob, (
            "a refusal a reader cannot audit is not better than an accusation")

    def test_the_structural_facts_reach_the_register(self):
        reg = _register(COMPOSITE_CELLS)
        assert reg.get("_section_disputed"), (
            "_section_disputed is empty: the fact was computed and dropped, "
            "which is the failure this whole repair is about")


class TestNothingElseChanged:
    """A table with no section band must behave exactly as before -- the
    ordinary case, and the one the existing suite covers."""

    def test_a_plain_table_is_still_checked(self):
        cells = [{"raw": "32 (80.0)", "row": 1, "row_label": "Male sex, n (%)",
                  "col_label": "Total (n = 40)"}]
        reg = _register(cells)
        got = V.check_stated_denominators(reg)
        assert got["n_attached"] == 1
        assert reg["groups"][0]["checks"][0]["severity"] == "consistent"

    def test_a_plain_table_produces_no_dispute(self):
        cells = [{"raw": "32 (80.0)", "row": 1, "row_label": "Male sex, n (%)",
                  "col_label": "Total (n = 40)"}]
        assert not _register(cells).get("_section_disputed")


class TestTheKeyCannotCollide:
    """`col_label` legitimately contains ' | ' -- the stacked-header fold joins
    a spanning header to its sub-header with it. A key built on a pipe would
    merge two different columns of one table into one entry."""

    def test_two_columns_differing_only_after_a_pipe_get_different_keys(self):
        a = V._section_key("t1", 3, "Comorbidity | Low-risk (n = 1293)")
        b = V._section_key("t1", 3, "Comorbidity | Heart failure (n = 375)")
        assert a != b

    def test_a_pipe_in_a_label_cannot_impersonate_the_separator(self):
        assert V._section_key("t1", 1, "a | b") != V._section_key("t1|1", None, "a | b")
