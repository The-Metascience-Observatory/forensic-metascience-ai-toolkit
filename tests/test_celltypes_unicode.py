"""A cell is not unreadable because of its typography.

`_NUM` accepts only ASCII `[-+]`, so a cell typeset with the real MINUS SIGN
U+2212 matched nothing in `celltypes` and came back `non_numeric` -- the same
answer the module gives for the word "none". The tools never saw the cell, and
the extraction reported the coverage anyway.

MEASURED over the RAW `<td>`/`<th>`/`<entry>` text of the 99 XML papers in
`high_value_pdfs_to_run_on/` (58,110 cells) -- raw, because that is what every
path which does not run `jats._normalise` hands to `parse_cell`: the PDF text
layer, the .docx/.xlsx/.csv supplement readers, and any direct caller. 2,850
cells carry U+2212, 2,789 an en dash, 162 an em dash. Mapping them retypes
1,590 cells that are `non_numeric` today, and removing digit-group spaces adds
56 more, for 1,646: 727 `ambiguous`, 445 `numeric`, 302 `estimate_ci`,
80 `count`, 68 `median_iqr`, 20 `mean_sd`, 4 `n_percent`.

The 302 estimate-plus-CI cells are the ones that matter. A negative effect
estimate with its interval is the highest-value cell on a clinical table, and
it was being deleted for the shape of its minus sign.
"""
import unicodedata

from forensic_metascience_ai_toolkit.tools.celltypes import parse_cell, parse_cells, repair_unicode

CI = "b (95% CI)"


class TestUnicodeMinus:
    def test_estimate_with_ci_survives_a_unicode_minus(self):
        cell = parse_cell("−1.42 (−1.87 to −1.08)", col_label=CI)
        assert cell.kind == "estimate_ci"
        assert (cell.value, cell.low, cell.high) == (-1.42, -1.87, -1.08)

    def test_a_bare_negative_number_is_numeric(self):
        assert parse_cell("−3.5").kind == "numeric"
        assert parse_cell("−3.5").value == -3.5

    def test_en_dash_as_a_sign(self):
        assert parse_cell("–0.31", col_label="Estimate").value == -0.31

    def test_en_dash_as_a_range_separator_is_unaffected(self):
        """It already read as a separator; mapping it to `-` must not change
        that, because `_INTERVAL_SEP` accepts both."""
        cell = parse_cell("0.82 (0.71–0.95)", col_label=CI)
        assert (cell.kind, cell.low, cell.high) == ("estimate_ci", 0.71, 0.95)

    def test_a_grouped_number_with_a_narrow_no_break_space(self):
        """The one place an exotic space changes the answer. Mapping it to an
        ASCII space would not have helped -- Python's `\\s` already matched it --
        so the digit-group separator is REMOVED, exactly as `jats` does."""
        assert parse_cell("1 234", col_label="n").value == 1234

    def test_a_space_between_two_separate_numbers_is_left_alone(self):
        """The lookahead is the guard: welding "5" and "10" into "510" would put
        a number into a finding that the paper never printed."""
        assert repair_unicode("5 10") == ("5 10", 0)


class TestWhatIsRecorded:
    def test_raw_is_the_text_as_printed(self):
        """The repair must be visible. `raw` is the record of what the paper
        actually contains, and a reader chasing a finding has to be able to
        find that string in the source."""
        printed = "−1.42 (−1.87 to −1.08)"
        cell = parse_cell(printed, col_label=CI)
        assert cell.raw == printed
        assert cell.unicode_repairs == 3
        assert cell.as_dict()["unicode_repaired"] == 3

    def test_an_untouched_cell_records_nothing(self):
        cell = parse_cell("45.2 (12.1)", col_label="Mean (SD)")
        assert cell.unicode_repairs == 0
        assert "unicode_repaired" not in cell.as_dict()

    def test_the_summary_counts_repairs_and_the_residue(self):
        """"Count what is still discarded" -- a repair that quietly improves
        coverage without saying how much is still unread is the same silence
        in a different place."""
        out = parse_cells([
            {"raw": "−1.42 (−1.87 to −1.08)", "col_label": CI},
            {"raw": "not done"},
        ])
        assert out["n_unicode_repaired"] == 1
        note = [w for w in out["warnings"] if "non-ASCII" in w]
        assert note and "1 cell(s) remain non_numeric" in note[0]


class TestNfkcIsNotUsed:
    """NFKC is the obvious answer and it is the wrong one.

    It does not fix the actual defect, and it breaks two things this module
    depends on. MEASURED: NFKC alters 345 of 48,588 parsed corpus cells and
    CHANGES THE PARSE of 75 of them.
    """

    def test_nfkc_would_not_have_fixed_the_minus_sign(self):
        assert unicodedata.normalize("NFKC", "−3.5") == "−3.5"

    def test_a_footnote_marker_stays_a_marker(self):
        """NFKC turns `12.3ᵃ` into `12.3a`, welding the marker onto the
        value where `_TRAILING_MARKER` can no longer separate it."""
        cell = parse_cell("12.3ᵃ")
        assert cell.value == 12.3
        assert cell.markers == ["ᵃ"]

    def test_an_exponent_is_still_refused(self):
        """`10^-3` must not parse to 10 -- a value 10,000x too large. NFKC
        rewrites `10⁻³` to `10−3`, undoing the rendering that
        makes the refusal possible."""
        assert parse_cell("10^-3").kind == "non_numeric"


class TestRepairHelper:
    def test_it_returns_the_count(self):
        assert repair_unicode("−a–b") == ("-a-b", 2)

    def test_clean_text_is_returned_unchanged(self):
        assert repair_unicode("45.2 (12.1)") == ("45.2 (12.1)", 0)

    def test_empty(self):
        assert repair_unicode("") == ("", 0)
