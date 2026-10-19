"""A footnote marker must not make a cell invisible -- nor invent a value.

`celltypes.parse_cell` matches with `fullmatch`, so one trailing marker sent
the whole cell to `non_numeric`: `12.3ᵃ`, `45.2 (12.1)ᵃ` and `0.19 (0.07,
0.51)***` were all "not a numeric cell". That is the second failure mode named
in the module's own docstring -- a cell the tools never see, reported as
coverage we did not have -- and it reached the typed path that stage 1 routes
every table through (`parse_cells_typed` -> `check_table`).

MEASURED over the 103 XML papers under `high_value_pdfs_to_run_on/` (49,777
typed cells): 924 `non_numeric` cells parse once a trailing marker comes off.

The other half of the fix is the refusal. A raised DIGIT after a number is an
exponent, not a marker, so `10⁻³` must stay unparsed -- reading it as 10 would
hand a checking tool a value 10,000x too large.
"""
import pytest

from forensic_metascience_ai_toolkit.tools.celltypes import parse_cell, parse_cells


class TestAMarkedCellReachesTheTools:
    @pytest.mark.parametrize("raw,row,col,kind,value", [
        ("12.3ᵃ", None, None, "numeric", 12.3),
        ("12.3*", None, None, "numeric", 12.3),
        ("45.2 (12.1)ᵃ", "Age", "Mean (SD)", "mean_sd", 45.2),
        ("142 (71.0)ᵃ", "Female", "n (%)", "n_percent", 142.0),
        ("0.19 (0.07, 0.51)***", "OR", "aOR (95% CI)", "estimate_ci", 0.19),
        ("5.4 ± 1.2*", "Score", "Mean (SD)", "mean_sd", 5.4),
    ])
    def test_a_trailing_marker_no_longer_hides_the_cell(self, raw, row, col, kind, value):
        pc = parse_cell(raw, row, col)
        assert pc.kind == kind
        assert pc.value == pytest.approx(value)

    def test_the_marker_is_recorded_not_dropped(self):
        """The marker points at a footnote, and a footnote is where a paper says
        'n=38 for this row' or 'log-transformed'. Discarding it would hand a tool
        a number the paper only conditionally asserted."""
        pc = parse_cell("45.2 (12.1)ᵃ", "Age", "Mean (SD)")
        assert pc.markers == ["ᵃ"]
        assert pc.as_dict()["markers"] == ["ᵃ"]

    def test_raw_still_carries_what_the_paper_printed(self):
        assert parse_cell("12.3*").raw == "12.3*"

    def test_a_repeated_star_stays_one_marker(self):
        """`*` and `***` are different p-value tiers; splitting per character
        would make them read the same."""
        assert parse_cell("0.5***").markers == ["***"]

    def test_distinct_letters_are_separate_footnotes(self):
        assert parse_cell("12.3ᵃᵇ").markers == ["ᵃ", "ᵇ"]

    def test_printed_precision_survives_the_strip(self):
        """Granularity checks size their rounding interval from this; the marker
        never changed how many decimals the paper printed."""
        pc = parse_cell("45.20 (12.1)ᵃ", "Age", "Mean (SD)")
        assert (pc.decimals_value, pc.decimals_sd) == (2, 1)


class TestTheStripRefusesWhereItCannotBeSure:
    @pytest.mark.parametrize("raw", ["10²", "10⁻³", "10^-3"])
    def test_a_raised_digit_is_an_exponent_and_stays_unparsed(self, raw):
        """`jats` renders true exponents as `10^-3` precisely so they do not
        parse. A strip rule that took `⁻³` for a marker would undo that and
        return 10 where the paper printed 0.001."""
        assert parse_cell(raw).kind == "non_numeric"

    def test_a_welded_ascii_letter_is_still_refused(self):
        """`12.3a` could be a unit (`a` = annum). Raising the marker to `12.3ᵃ`
        is what makes it decidable, and is the whole point of the `<sup>`
        conversion; the welded form stays a guess and is not made."""
        assert parse_cell("12.3a").kind == "non_numeric"

    @pytest.mark.parametrize("raw", ["n/a*", "***", "-"])
    def test_a_marker_alone_does_not_rescue_an_unreadable_cell(self, raw):
        assert parse_cell(raw).kind == "non_numeric"

    def test_an_ambiguous_cell_stays_ambiguous_with_its_marker_on(self):
        """Stripping recovers the FORMAT, never the meaning: a bare label leaves
        `X (Y)` ambiguous whether or not it carries a footnote."""
        pc = parse_cell("48.90 (14.46)ᵃ", "Age")
        assert pc.kind == "ambiguous"
        assert pc.markers == ["ᵃ"]

    def test_no_cell_that_already_typed_can_be_retyped(self):
        """The retry sits on the `non_numeric` path only, so this branch can add
        coverage and cannot move an existing verdict."""
        for raw, row, col in [("142 (71.0)", "Female", "n (%)"),
                              ("45.2 (12.1)", "Age", "Mean (SD)"),
                              ("48.90 (14.46)", "Age", None),
                              ("27.3 [24.1-31.2]", "Age", "Median [IQR]"),
                              ("12.3", None, None)]:
            assert not parse_cell(raw, row, col).markers


class TestTheSummaryReportsTheMarkers:
    def test_marked_cells_are_counted_and_named_once(self):
        """One aggregate warning, not one per cell: 924 of 49,777 corpus cells
        carry a marker, and per-cell warnings would bury the ambiguity warnings
        that mean a tool must NOT run."""
        out = parse_cells([{"raw": "12.3ᵃ"}, {"raw": "0.5**"}, {"raw": "7.1"}])
        assert out["n_footnote_marked"] == 2
        marker_warnings = [w for w in out["warnings"] if "footnote marker" in w]
        assert len(marker_warnings) == 1
        assert "ᵃ" in marker_warnings[0] and "**" in marker_warnings[0]

    def test_an_unmarked_table_says_nothing_about_markers(self):
        out = parse_cells([{"raw": "7.1"}, {"raw": "12"}])
        assert out["n_footnote_marked"] == 0
        assert not any("footnote marker" in w for w in out["warnings"])

    def test_recovered_cells_raise_coverage(self):
        """The measurement that motivates the change: these cells counted as
        table we did not understand."""
        cells = [{"raw": "12.3ᵃ"}, {"raw": "4.5*"}, {"raw": "n/a"}, {"raw": "6.7"}]
        assert parse_cells(cells)["coverage"] == 0.75


class TestASignificanceSubscriptAfterABracket:
    """`5.38 (1.17)a` -- the format psychology tables use for "means not sharing
    a subscript differ at P < 0.05" -- typed as `non_numeric` until 2026-08-11.

    WHY THE OLD RULE WAS RIGHT AND STILL INCOMPLETE. Welded ASCII after a BARE
    number is genuinely ambiguous: `12.3a` could be `12.3 annum`, and this
    module refuses to guess units. But a unit does not attach to the far side of
    a closing bracket, so `5.38 (1.17)a` carries no such ambiguity.

    MEASURED, and it is why this is not cosmetic. In the SI of
    10.1073/pnas.1523586113 -- the Kouchaki & Gino paper whose duplicated affect
    rows are on PubPeer, and our best demonstration case -- EVERY ONE of the 153
    `mean (SD)` cells in Tables S1 and S2 carries a subscript. All 153 typed
    `non_numeric`. A table in which every cell fails to parse was being counted
    as a table with nothing checkable in it: our failure recorded as the paper's
    property.

    ROUTE-SPECIFIC, and worth stating so the small corpus number is not
    misread. JATS raises `<sup>a</sup>` to `ᵃ`, which the superscript rule
    already caught, so only 24 cells in 1 paper across the archived XML are
    recovered here. The Gino tables arrive through the pdf2mdjson markdown
    route, which flattens the superscript to baseline ASCII. This rule is for
    that route -- the same one every supplement uses.
    """

    def _p(self, raw, col="M (SD)"):
        from forensic_metascience_ai_toolkit import census as C
        return C.parse_cells([{"raw": raw, "row": 1,
                               "row_label": "Clarity", "col_label": col}])["cells"][0]

    def test_a_single_subscript_no_longer_kills_the_cell(self):
        p = self._p("5.38 (1.17)a")
        assert p["kind"] == "mean_sd" and p["value"] == 5.38 and p["sd"] == 1.17

    def test_two_subscripts_are_two_markers_not_three_tokens(self):
        assert self._p("1.25 (0.37) b,c")["markers"] == ["b", "c"]

    def test_a_space_before_the_subscript_is_fine(self):
        assert self._p("2.37 (0.92) a")["kind"] == "mean_sd"

    def test_square_brackets_too(self):
        assert self._p("6.58 [.52]a")["kind"] == "mean_sd"

    def test_the_original_text_survives_for_the_reader(self):
        """A reader must still be able to find the footnote the marker points
        at, so `raw` keeps what the paper printed."""
        assert self._p("5.38 (1.17)a")["raw"] == "5.38 (1.17)a"

    def test_a_letter_after_a_BARE_number_is_still_refused(self):
        """THE PROTECTION THAT MUST NOT ERODE. `12.3a` could be annum. The new
        rule is scoped to the position where that reading is impossible."""
        assert self._p("12.3a")["kind"] == "non_numeric"
        assert self._p("12.3 a")["kind"] == "non_numeric"

    def test_a_marker_does_not_rescue_an_unreadable_cell(self):
        assert self._p("n/a a")["kind"] == "non_numeric"

    def test_an_unknown_DELIMITER_is_still_refused(self):
        """A format question is not a marker question. `{1.17}` stays
        unparsed rather than being guessed at -- see the module note."""
        assert self._p("5.38 {1.17}a")["kind"] == "non_numeric"

    def test_the_gino_tables_now_parse_end_to_end(self):
        import pathlib
        import re

        from forensic_metascience_ai_toolkit import census as C
        si = pathlib.Path("/mnt/c/Users/gregs/_excised_from_forensic_repo/"
                          "gino_paper_excised_2026-07-25/10.1073--pnas.1523586113/"
                          "10.1073--pnas.1523586113_SUPPLEMENTARY_INFO.md")
        if not si.exists():
            pytest.skip("the excised Gino supplement is not on this machine")
        vals = re.findall(r"\|\s*([0-9]+\.[0-9]+ \([0-9]+\.[0-9]+\)[^|]*?)\s*(?=\|)",
                          si.read_text(encoding="utf-8"))
        assert len(vals) > 100, "the SI tables moved"
        cells = [{"raw": v.strip(), "row": i, "row_label": "x",
                  "col_label": "M (SD)"} for i, v in enumerate(vals)]
        kinds = {c["kind"] for c in C.parse_cells(cells)["cells"]}
        assert kinds == {"mean_sd"}, (
            f"the Gino SI cells type as {kinds}; all 153 were non_numeric before "
            "this rule, which is why the duplicated affect rows were invisible "
            "to every census-based count")
