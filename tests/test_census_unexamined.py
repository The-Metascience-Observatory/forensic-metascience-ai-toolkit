"""An empty census is not a census of zero.

`census.summarise([])` returned every count as 0 with nothing to say why, and
the viewer renders that as an audited census -- "cells extracted from the
tables: 0" -- which a reader takes as a fact about the PAPER. It is equally the
shape of a paper whose tables were never enumerated, an extraction that failed,
or a caller that passed an empty list.

This is the same defect as `tables_note` on `extract_text_with_tables`, fixed
earlier the same night, and the same one as `supplements.audit`'s three-valued
`missing`: an observed zero and an unasked question must not be spelled
identically.

`n_cells: 0` is KEPT -- removing it would break every consumer -- and
`no_cells_examined` is added beside it so the difference can be branched on
without parsing prose.

NOTE ON WHAT THESE TESTS COVER. The Python contract is asserted here. The
viewer's rendering of it is NOT: the warning text sits inside a JS template
literal and is present in the served HTML whether or not the branch fires, so
searching the output proves nothing. (I made exactly that mistake while writing
this, asserting the string was absent from a healthy render when it never could
be.) What IS checked for the viewer is that its script still parses --
tests/test_viewer_js_parses.py -- because a broken template blanks the page.
"""
import pytest

from forensic_metascience_ai_toolkit.census import summarise

CELL = {"consumable": True, "routable": True, "runnable": True,
        "kind": "mean_sd", "missing": []}
TEXT = {"consumable": False, "routable": False, "runnable": False,
        "kind": "text", "missing": []}


class TestNothingExamined:
    def test_the_flag_is_set(self):
        assert summarise([])["no_cells_examined"] is True

    def test_a_note_explains_the_zeros(self):
        note = summarise([])["note"]
        assert "NO TABLE CELLS WERE EXAMINED" in note
        assert "UNKNOWN" in note

    def test_the_counts_are_still_zero_for_compatibility(self):
        """Consumers read n_cells; removing it would be a worse break than the
        ambiguity it carries."""
        s = summarise([])
        assert s["n_cells"] == 0 and s["n_consumable"] == 0


class TestARealCensus:
    def test_the_flag_is_clear(self):
        assert summarise([CELL, TEXT])["no_cells_examined"] is False

    def test_no_note_is_added(self):
        assert "note" not in summarise([CELL, TEXT])

    def test_the_counts_are_unchanged_by_this_fix(self):
        s = summarise([CELL, TEXT])
        assert s["n_cells"] == 2 and s["n_consumable"] == 1

    def test_a_genuine_zero_consumable_is_not_flagged_unexamined(self):
        """The case the flag must NOT swallow: cells were examined and none of
        them was a quantity. That IS a fact about the paper."""
        s = summarise([TEXT, TEXT])
        assert s["no_cells_examined"] is False
        assert s["n_cells"] == 2 and s["n_consumable"] == 0
        assert "note" not in s


class TestTheDistinctionIsTheWholePoint:
    def test_unexamined_and_examined_but_empty_differ(self):
        unexamined = summarise([])
        examined = summarise([TEXT, TEXT])
        assert unexamined["n_consumable"] == examined["n_consumable"] == 0
        assert unexamined["no_cells_examined"] != examined["no_cells_examined"]
