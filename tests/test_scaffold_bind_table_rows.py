"""A floor row with no body offset is a table cell, and `bind` must not
compare it to a byte position.

FOUND on the first end-to-end JATS run (2026-09-06): `numerals.index_table_cells`
puts a table's cells into the floor with `offset: None` -- their coordinate is
(table, cell), not a byte -- and `bind.account_numerals` did `loc["offset"] <=
r["offset"]` on them and crashed with TypeError, after three paid passes
($7.49). The guard existed in `linear.chunks` and not here: one seam patched,
the next left open.
"""
from metascience_agent.scaffold import bind


def _doc(text="The mean was 4.01 (0.92) in the sample of 120 people."):
    body = [{"id": f"num:{i}", "printed": p, "offset": text.index(p), "end": text.index(p) + len(p),
             "class": "unclassified", "context": text, "role": "results", "source": "article"}
            for i, p in enumerate(["4.01", "0.92", "120"])]
    cells = [{"id": "num:cell:article:Table 1:t1:c0:0", "printed": "9", "offset": None, "end": None,
              "class": "table_cell", "context": "Male | Mean: 9 (100)", "role": "table",
              "source": "article", "file": "Table 1", "table_index": 1, "cell_index": 0}]
    return {"text": text, "numerals": body + cells, "tables": [], "sections": []}


def test_a_table_cell_row_does_not_crash_the_accounting():
    rows = bind.account_numerals(_doc(), values=[], text=_doc()["text"])
    assert len(rows) == 4


def test_a_table_cell_row_is_dispositioned_to_the_table_pass():
    rows = bind.account_numerals(_doc(), values=[], text=_doc()["text"])
    cell = [r for r in rows if r.get("offset") is None][0]
    assert cell["disposition"] == "table_cell"


def test_a_table_cell_row_is_never_served_as_residual_work():
    """`residual_rows` sorts by offset and looks up a sentence at it; a row
    with no offset can do neither, and it has no business in the residual
    queue because the table pass already owns it."""
    doc = _doc()
    rows = bind.account_numerals(doc, values=[], text=doc["text"])
    served = bind.residual_rows(rows, text=doc["text"], pages=None)
    assert all(r.get("numeral_id") != "num:cell:article:Table 1:t1:c0:0" for r in served)


class TestAVerifiedTableNeedsNoPass3Reading:
    def test_entries_become_values_without_a_reading(self):
        from metascience_agent.scaffold import bind as B
        doc = {"tables": [{"id": "table:1", "label": "Table 1", "n_cells": 1, "row_labels": ["r"], "col_labels": ["c"],
                           "reconstruction": {"status": "verified"},
                           "cells": [{"row": 1, "col": 1, "row_label": "r", "col_label": "c", "raw": "38 (59%)",
                                      "entries": [{"variable": "x", "level": None, "group": None, "statistic": "count",
                                                   "statistic_basis": "cell_form", "value": "38", "variable_id": None},
                                                  {"variable": "x", "level": None, "group": None, "statistic": "percentage",
                                                   "statistic_basis": "cell_form", "value": "59%", "variable_id": None}]}]}]}
        problems: list[str] = []
        values, unparsed = B._table_values(doc, {"table_readings": []}, {}, problems)
        assert [v["statistic"] for v in values] == ["count", "percentage"]
        assert unparsed == [] and not any("no reading" in p for p in problems)
