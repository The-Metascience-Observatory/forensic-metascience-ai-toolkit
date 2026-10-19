"""Tests for table ingestion (parse_cell / parse_table / reconcile_tables)."""

from forensic_metascience_ai_toolkit.tools.tableparse import (
    parse_cell,
    parse_table,
    reconcile_tables,
)


class TestParseCell:
    def test_mean_sd_paren_with_subscript(self):
        r = parse_cell("5.38 (1.17) a")
        assert r["value"] == 5.38 and r["sd"] == 1.17 and r["extras"] == ["a"]

    def test_m_sd_equals(self):
        r = parse_cell("M=5.38, SD=1.17")
        assert r["value"] == 5.38 and r["sd"] == 1.17

    def test_plus_minus(self):
        r = parse_cell("5.38±1.17")
        assert r["value"] == 5.38 and r["sd"] == 1.17

    def test_bare_number(self):
        r = parse_cell("5.38")
        assert r["value"] == 5.38 and r["sd"] is None

    def test_non_numeric(self):
        r = parse_cell("Clarity")
        assert r["value"] is None and r["sd"] is None

    def test_merged_blob_returns_list(self):
        r = parse_cell("Age (years) 17.2±5.2 18.1±5.5 19.0±6.1")
        assert isinstance(r, list)
        assert [c["value"] for c in r] == [17.2, 18.1, 19.0]
        assert [c["sd"] for c in r] == [5.2, 5.5, 6.1]

    def test_thousands_separator_not_guessed(self):
        r = parse_cell("1,234.5")
        assert r["value"] is None and "warning" in r

    def test_empty(self):
        r = parse_cell("")
        assert r["value"] is None


class TestParseTable:
    def test_markdown_table(self):
        md = (
            "| Measures | Unethical | Ethical |\n"
            "|---|---|---|\n"
            "| Clarity | 5.38 (1.17) a | 6.00 (0.88) b |\n"
            "| Positive affect | 2.37 (0.92) a | 3.06 (0.97) b |\n"
        )
        t = parse_table(md, source_label="Table S1")
        assert t["n_numeric_cells"] == 4
        # column labels aligned
        clar_un = next(c for c in t["cells"] if c["row_label"] == "Clarity"
                       and c["value"] == 5.38)
        assert clar_un["col_label"] == "Unethical" and clar_un["sd"] == 1.17

    def test_grid_input(self):
        grid = [["M", "A", "B"], ["r1", "1.5 (0.2)", "2.5 (0.3)"]]
        t = parse_table(grid, source_format="grid")
        assert t["n_numeric_cells"] == 2

    def test_merged_row_blob_split(self):
        md = (
            "| Measures | G1 | G2 | G3 |\n"
            "|---|---|---|---|\n"
            "| Age (years) 17.2±5.2 18.1±5.5 19.0±6.1 |\n"
        )
        t = parse_table(md, source_label="T")
        vals = sorted(c["value"] for c in t["cells"])
        assert vals == [17.2, 18.1, 19.0]
        assert any("merged blob" in w for w in t["warnings"])


class TestFractionBlobsAreNotFabricated:
    """`12/30 (40.0) 15/30 (50.0)` is two `numerator/denominator (percent)`
    tokens, not two `value (sd)` cells. The inline splitter used to start its
    value token mid-fraction and return value=30, sd=40.0 and value=30, sd=50.0
    -- four numbers welded into readings the paper never printed, which then
    fed reconciliation and duplication detection as data."""

    def test_a_merged_fraction_row_is_refused_not_invented(self):
        r = parse_cell("12/30 (40.0) 15/30 (50.0)")
        assert isinstance(r, dict)
        assert r["value"] is None and r["sd"] is None

    def test_a_single_fraction_cell_is_still_refused(self):
        r = parse_cell("12/30 (40.0)")
        assert isinstance(r, dict)
        assert r["value"] is None

    def test_a_genuine_merged_blob_still_splits(self):
        r = parse_cell("Age (years) 17.2±5.2 18.1±5.5 19.0±6.1")
        assert isinstance(r, list)
        assert [c["value"] for c in r] == [17.2, 18.1, 19.0]


class TestReconcileComparesIntervalsNotRoundings:
    """A printed number is an interval. `5.35` in the text and `5.4` in the
    table are the SAME claim at 1 dp -- 5.35 rounds to 5.4 -- but comparing
    `round(a, d) == round(b, d)` put the boundary value on the wrong side
    (banker's rounding sends 5.35 to 5.3) and stamped an honest text-vs-table
    pair `suspicious`."""

    def _table(self, v):
        return parse_table(
            f"| M | c1 |\n|---|---|\n| rowA | {v} |\n", source_label="x"
        )

    def test_a_boundary_rounding_pair_agrees(self):
        rec = reconcile_tables(self._table("5.35"), self._table("5.4"))
        assert rec["severity"] == "consistent"
        assert rec["n_disagree"] == 0

    def test_coarser_side_printed_to_zero_decimals(self):
        # "142" asserts [141.5, 142.5); a text value 142.3 is inside it.
        rec = reconcile_tables(self._table("142"), self._table("142.3"))
        assert rec["severity"] == "consistent"

    def test_a_genuine_disagreement_is_still_flagged(self):
        rec = reconcile_tables(self._table("142"), self._table("143"))
        assert rec["severity"] == "suspicious"


class TestReconcile:
    def _table(self, v):
        return parse_table(
            f"| M | c1 |\n|---|---|\n| rowA | {v} |\n", source_label="x"
        )

    def test_identical_agree(self):
        a = self._table("5.38 (1.17)")
        b = self._table("5.38 (1.17)")
        rec = reconcile_tables(a, b)
        assert rec["severity"] == "consistent" and rec["n_disagree"] == 0

    def test_disagreement_flagged(self):
        a = self._table("5.38 (1.17)")
        b = self._table("5.83 (1.17)")
        rec = reconcile_tables(a, b)
        assert rec["severity"] == "suspicious"
        assert rec["n_disagree"] == 1
        assert rec["disagreements"][0]["row_label"] == "rowA"
        assert "value" in rec["disagreements"][0]["kind"]

    def test_cross_check_via_parse_table(self):
        md = "| M | c1 |\n|---|---|\n| rowA | 5.38 (1.17) |\n"
        other = "| M | c1 |\n|---|---|\n| rowA | 9.99 (1.17) |\n"
        t = parse_table(md, source_label="md", cross_check=other)
        assert t["reconciliation"]["n_disagree"] == 1


class TestParseTableRendersNoVerdictOfItsOwn:
    """A parser is not a check. parse_table used to return top-level
    `consistent` on EVERY call (a dead `if warnings` branch overrode it back),
    so a table where nothing parsed read as a clean bill of health -- and,
    because severity_reconcile maps technique='reconcile' to this tool and reads
    the top-level severity, a correct text-vs-table mismatch finding was
    publicly stamped as an unexplained upgrade past a 'consistent' tool."""

    def test_no_cross_check_is_indeterminate_not_consistent(self):
        t = parse_table("| M | c1 |\n|---|---|\n| rowA | 5.38 (1.17) |\n")
        assert t["severity"] == "indeterminate"

    def test_a_table_that_did_not_parse_is_indeterminate(self):
        # A grid whose only numeric cell is refused for thousands ambiguity.
        t = parse_table("| M | c1 |\n|---|---|\n| rowA | 1,234 |\n")
        assert t["n_numeric_cells"] == 0
        assert t["severity"] == "indeterminate"

    def test_a_cross_check_disagreement_reaches_the_top_level(self):
        # The fix: the reconciliation verdict is lifted so consumers (and
        # severity_reconcile) see `suspicious`, not a false `consistent`.
        md = "| M | c1 |\n|---|---|\n| rowA | 5.38 (1.17) |\n"
        other = "| M | c1 |\n|---|---|\n| rowA | 9.99 (1.17) |\n"
        t = parse_table(md, source_label="md", cross_check=other)
        assert t["severity"] == "suspicious"

    def test_a_cross_check_agreement_is_consistent(self):
        md = "| M | c1 |\n|---|---|\n| rowA | 5.38 (1.17) |\n"
        t = parse_table(md, source_label="md", cross_check=md)
        assert t["severity"] == "consistent"
