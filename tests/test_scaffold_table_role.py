"""A table's role is a positive, reported tier -- never a denominator subtraction.

ajcp.70049 table:6 is the EBP rating crosswalk: `Rating 1 | Rating 2 |
Blueprints | NREPP | ...` over `Evidence-based (1) | Effective (5) | Model | 4 |
...`. Its 19 numeral-bearing cells are rating CODES, and read as a statistics
table they are 15 cells nobody covered -- a false thing to say about the account.

THE HAZARD IS `25e2f9f`, IN ITS CHEAPEST FORM: a "not a measurement table" test
that is wrong takes a real statistics supplement out of the denominator and
coverage rises for free. So the tier is a DISCLOSURE. The cells stay in `cells`,
`non_statistical` is a tier beside `placed`, and calling a table a codebook can
only LOWER `share_placed`. The tests below pin that in both directions.

Both conditions are required, and each is evidence of a different kind: the
reading (verified against the walker's digits) found nothing but rating codes,
counts and unclassifiable tokens; and the table's own printed furniture --
caption, footnote, or a header the WALKER read -- names a codebook.
"""

from __future__ import annotations

import copy

import pytest

from forensic_metascience_ai_toolkit.scaffold import coverage

from .test_scaffold_coverage import TEXT, account


def _crosswalk_table() -> dict:
    """The ajcp table:6 shape, small: a stub column of rating codes, a caption
    that says what the table is, and a verified reading of nothing but scores."""
    cells = [{"row": r, "col": c, "raw": raw, "row_label": stub, "col_label": col}
             for r, (stub, row) in enumerate([("Evidence-based (1)", [("Blueprints", "Model"),
                                                                     ("NREPP", "4")]),
                                              ("Not Evidence-based (0)", [("Blueprints", "--"),
                                                                          ("NREPP", "1")])], start=1)
             for c, (col, raw) in enumerate(row, start=1)]
    return {"id": "table:9", "label": "Table S2", "source": "supplement",
            "caption": "Crosswalk of equivalent ratings across program registries.",
            "footnotes": [], "n_cells": 4, "walker_cells": cells, "cells": cells,
            "reconstruction": {"status": "verified",
                               "verification": {"by_statistic": {"score": 3, "count": 1}}}}


class TestTheTestIsPositiveAndNeedsBothHalves:

    def test_a_crosswalk_with_only_codes_is_non_statistical(self):
        got = coverage.table_role(_crosswalk_table())
        assert got["role"] == "non_statistical"
        assert "crosswalk" in got["why"]

    def test_the_same_table_without_the_word_is_unknown_not_non_statistical(self):
        t = _crosswalk_table()
        t["caption"] = "Ratings by programme."
        assert coverage.table_role(t)["role"] == "unknown"

    def test_a_single_measurement_makes_it_statistics_whatever_the_caption_says(self):
        t = _crosswalk_table()
        t["reconstruction"]["verification"]["by_statistic"]["mean"] = 1
        got = coverage.table_role(t)
        assert got["role"] == "statistics" and "mean" in got["why"]

    def test_a_table_with_no_verified_reading_is_unknown(self):
        t = _crosswalk_table()
        t["reconstruction"] = {"status": "refused"}
        assert coverage.table_role(t)["role"] == "unknown"

    def test_a_reading_with_no_statistic_at_all_is_unknown(self):
        t = _crosswalk_table()
        t["reconstruction"]["verification"]["by_statistic"] = {}
        assert coverage.table_role(t)["role"] == "unknown"

    def test_the_evidence_comes_from_the_walkers_headers_not_the_readings(self):
        """A verified reconstruction REPLACES `cells` and refreshes the labels,
        so a role read off `cells` would be read off the model. The walker's
        headers are the paper's."""
        t = _crosswalk_table()
        t["caption"] = None
        for c in t["walker_cells"]:
            c["col_label"] = "Clearinghouse rating"
        t["cells"] = [dict(c, col_label="Column A", row_label="(row 1)") for c in t["walker_cells"]]
        assert coverage.table_role(t)["role"] == "non_statistical"

    def test_a_registry_named_only_in_a_cell_does_not_decide_it(self):
        t = _crosswalk_table()
        t["caption"] = None
        t["walker_cells"][0]["raw"] = "Recruited from the registry"
        assert coverage.table_role(t)["role"] == "unknown"


class TestTheTierIsNeverASubtraction:

    def test_marking_a_statistics_table_a_crosswalk_does_not_raise_placed(self):
        acct = account()
        before = coverage.headline(acct, TEXT)["table_cells_placed"]
        art = acct["document"]["tables"][0]
        art["caption"] = "Crosswalk of coding categories."
        art["reconstruction"] = {"status": "verified",
                                 "verification": {"by_statistic": {"score": 4}}}
        after = coverage.headline(acct, TEXT)["table_cells_placed"]
        assert after["cells"] == before["cells"]
        assert after["placed"] <= before["placed"]
        assert after["by_tier"]["non_statistical"] == 4
        assert sum(after["by_tier"].values()) == after["cells"]

    def test_the_share_placed_denominator_does_not_move(self):
        acct = account()
        before = coverage.headline(acct, TEXT)["table_cells_placed"]
        acct["document"]["tables"][0]["caption"] = "Codebook for the rating scheme."
        acct["document"]["tables"][0]["reconstruction"] = {
            "status": "verified", "verification": {"by_statistic": {"count": 4}}}
        after = coverage.headline(acct, TEXT)["table_cells_placed"]
        assert after["cells"] == before["cells"] == 5
        assert after["share_placed"] < before["share_placed"]

    def test_the_role_and_its_reason_are_printed_per_table(self):
        acct = account()
        acct["document"]["tables"].append(_crosswalk_table())
        head = coverage.headline(acct, TEXT)
        md = "\n".join(coverage.render_lines(head))
        assert "role **non_statistical**" in md
        assert "names a crosswalk" in md
        assert "Tables by role:" in md

    def test_every_table_carries_a_role_even_when_it_is_unknown(self):
        head = coverage.headline(account(), TEXT)["table_cells_placed"]
        assert {t["role"] for t in head["by_table"]} <= set(coverage.TABLE_ROLES)
        assert all(t["role_why"] for t in head["by_table"])
        assert sum(d["cells"] for d in head["by_role"].values()) == head["cells"]
