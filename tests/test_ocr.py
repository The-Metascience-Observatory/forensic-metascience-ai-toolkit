"""
The OCR seam: what it refuses, how it rebuilds a grid, and where an OCR'd
number sits in the provenance ladder.

WHY THESE TESTS EXIST AT ALL WITH NO ENGINE INSTALLED. The engine is one
adapter function; the part that decides whether a supplementary table is read
CORRECTLY is the layout reconstruction above it -- turning word boxes into
columns. That is where a `48.90 (14.46)` gets split in half, or a row slides one
column left and hands GRIMMER a (mean, SD, n) triple the paper never printed. It
is fully exercisable on synthetic word boxes, so it is tested here regardless of
what is installed, and installing an engine changes nothing below the seam.

The other half is the honesty contract. "No OCR engine on this machine" and
"this file contains no tables" are opposite facts -- one is about our
installation, one is about the authors -- and a caller that cannot tell them
apart writes the second into a review. See task #129.
"""

import pytest

from forensic_metascience_ai_toolkit.extraction import ocr
from metascience_observatory_image_analysis.extraction.figures import (
    AS_PRINTED,
    MEASURED,
    OCR_TABLE,
    OCR_TEXT,
    RELIABILITY_TIER,
    TRANSCRIBED,
)


def W(text, x, y, w=None, h=10.0, conf=95.0):
    """One word box. Width defaults to 6px per character, a plausible 10pt face."""
    return ocr.OcrWord(text=text, x=float(x), y=float(y),
                       w=float(w if w is not None else 6 * len(text)),
                       h=float(h), conf=conf)


def three_column_table():
    """A `Variable | Mean (SD) | n` table with three body rows.

    Columns start at x=0, x=200 and x=400; word spacing inside a cell is 6px
    (one character), the gaps between columns are ~100px. This is the shape the
    reconstruction has to get right, and the `Mean (SD)` cell is the specific
    thing it must NOT split.
    """
    rows = [
        [("Variable", 0), ("Mean (SD)", 200), ("n", 400)],
        [("Age", 0), ("48.90 (14.46)", 200), ("49", 400)],
        [("BMI", 0), ("24.10 (3.20)", 200), ("49", 400)],
        [("Score", 0), ("5.51 (1.20)", 200), ("30", 400)],
    ]
    words = []
    for r, row in enumerate(rows):
        for text, x0 in row:
            cursor = x0
            for token in text.split():
                words.append(W(token, cursor, 20 + r * 30))
                cursor += 6 * len(token) + 6      # one space between words
    return words


class TestTheEngineSeamRefusesHonestly:
    def test_engine_status_names_every_engine_and_why_it_is_unusable(self):
        """A refusal an operator cannot act on is only half a refusal.

        Reporting "no OCR" without saying WHICH half is missing sends someone to
        `pip install pytesseract`, which installs a wrapper around a binary that
        is still absent. Each probe has to name its own gap.
        """
        st = ocr.engine_status()
        assert {e["engine"] for e in st["engines"]} == {
            "pytesseract", "rapidocr", "pymupdf"}
        for entry in st["engines"]:
            assert entry["available"] is not entry["reason"].__ne__("")
            if not entry["available"]:
                assert entry["reason"], f"{entry['engine']} refused with no reason"
                assert entry["install"], f"{entry['engine']} names no remedy"
        assert st["available"] is (st["engine"] is not None)

    def test_pytesseract_probe_separates_the_package_from_the_binary(self):
        """The commonest install mistake, and it fails silently otherwise."""
        reason = ocr._probe_pytesseract()
        if reason:
            assert "package" in reason or "BINARY" in reason

    def test_no_engine_is_reported_as_our_gap_not_the_documents(self):
        """THE CENTRAL DISTINCTION. An empty table list would read as a fact
        about the paper. This must read as a fact about the machine."""
        out = ocr.unavailable_result("figure_s1.jpg")
        assert out["ocr_unavailable"] is True
        assert "NOT of the document" in out["error"]
        assert "no tables found" in out["error"]
        assert out["tables"] == [] and out["n_tables"] == 0
        # And the remedy is stated, because the whole gap is one pip install.
        if not ocr.engine_status()["available"]:
            assert "rapidocr" in out["remedy"]

    def test_a_refusal_is_not_a_crash(self):
        """`ocr_words` on a machine with no engine returns the refusal shape
        rather than raising -- callers route a structured error into `unchecked`
        and would turn an exception into a lost supplement instead."""
        out = ocr.ocr_words("/nonexistent/image.png")
        if not ocr.engine_status()["available"]:
            assert out["ocr_unavailable"] is True


class TestLinesAndColumns:
    def test_words_on_one_baseline_become_one_line(self):
        words = [W("Age", 0, 20), W("48.90", 200, 21), W("49", 400, 19)]
        lines = ocr.group_lines(words)
        assert len(lines) == 1
        assert [w.text for w in lines[0]] == ["Age", "48.90", "49"]

    def test_lines_come_back_in_reading_order(self):
        lines = ocr.group_lines(three_column_table())
        assert [ln[0].text for ln in lines] == ["Variable", "Age", "BMI", "Score"]

    def test_a_column_break_needs_support_from_several_lines(self):
        """One line's wide gap is not a column. This is what stops a spanning
        title or a footnote shredding the grid into invented columns."""
        words = three_column_table()
        # A caption spanning the full width, with ordinary word spacing.
        cursor = 0
        for token in "Table S1 Baseline characteristics of the sample".split():
            words.append(W(token, cursor, -30))
            cursor += 6 * len(token) + 6
        cuts = ocr.column_cuts(ocr.group_lines(words))
        assert len(cuts) == 2, cuts

    def test_a_mean_and_its_sd_stay_in_one_cell(self):
        """THE ERROR THAT MATTERS MOST. Splitting `48.90 (14.46)` into two cells
        puts the SD under the next heading, and every value to its right shifts
        by one column. A shifted row is a (mean, SD, n) triple the paper never
        reported, and the granularity family would then call it impossible."""
        got = ocr.words_to_grid(three_column_table())
        assert got["grid"][1] == ["Age", "48.90 (14.46)", "49"]
        assert got["grid"][2] == ["BMI", "24.10 (3.20)", "49"]

    def test_the_header_row_survives_as_the_header(self):
        got = ocr.words_to_grid(three_column_table())
        assert got["grid"][0] == ["Variable", "Mean (SD)", "n"]

    def test_no_recurring_gap_means_no_columns_rather_than_a_guess(self):
        """Prose has no column structure, and inventing one for it is how an
        extractor manufactures a table. One column is the honest answer."""
        cursor = 0
        words = []
        for token in ("the patients were followed for twelve months and "
                      "assessed at each visit").split():
            words.append(W(token, cursor, 0))
            cursor += 6 * len(token) + 6
        got = ocr.words_to_grid(words)
        assert got["n_cuts"] == 0
        assert all(len(row) == 1 for row in got["grid"])

    def test_a_word_crossing_a_column_boundary_is_counted_not_hidden(self):
        """Evidence AGAINST the grid we just built, and it has to survive to the
        caller: a straddling word means that row's columns may be shifted."""
        words = three_column_table()
        # A long token starting inside column 1 and running into column 2.
        words.append(W("continuation" * 8, 150, 140))
        got = ocr.words_to_grid(words)
        assert got["straddled"] >= 1

    def test_empty_input_is_not_a_grid(self):
        got = ocr.words_to_grid([])
        assert got["grid"] == [] and got["n_lines"] == 0


class TestConfidenceGate:
    def test_a_cell_read_below_the_floor_is_blanked_not_kept(self):
        """A blank is a visible gap someone can go and fill. A confidently wrong
        numeral is a finding against an honest paper, and warnings do not stop
        it: the grid is consumed by `parse_cells_typed`, which reads cells."""
        grid = [["Age", "48.90"], ["BMI", "24.10"]]
        conf = [[95.0, 12.0], [95.0, 90.0]]
        out, dropped, median = ocr._gate_confidence(grid, conf)
        assert out[0][1] == ""
        assert out[1][1] == "24.10"
        assert dropped and dropped[0]["text"] == "48.90"
        assert dropped[0]["confidence"] == 12.0

    def test_an_engine_reporting_no_confidence_is_not_treated_as_certain(self):
        """`None` means unknown. Substituting 100 would silently pass every cell
        through a gate that exists precisely for the unknown ones."""
        out, dropped, median = ocr._gate_confidence([["5.51"]], [[None]])
        assert out == [["5.51"]] and dropped == [] and median is None


class TestTheProvenanceDecision:
    """An OCR'd numeral is printed IN KIND and unverified IN CHANNEL.

    Recorded here because the reasoning is the deliverable, not the constant:
    `printed_table` asserts a transcription we cannot vouch for, and
    `measured_raster` states a reason that is false of an OCR'd digit (it HAS a
    last printed digit). The third channel keeps both statements true.
    """

    def test_ocr_is_neither_as_printed_nor_measured(self):
        assert not (TRANSCRIBED & AS_PRINTED)
        assert not (TRANSCRIBED & MEASURED)
        assert TRANSCRIBED == {OCR_TABLE, OCR_TEXT}

    def test_ocr_sits_at_the_tier_that_bars_exact_arithmetic(self):
        """Tier 2 with the measured values, so every gate that already refuses
        tier 2 refuses these -- no new gate to remember to add."""
        assert RELIABILITY_TIER[OCR_TABLE] == 2
        assert RELIABILITY_TIER[OCR_TEXT] == 2

    def test_the_registry_gate_refuses_an_exact_check_on_an_ocr_value(self):
        from forensic_metascience_ai_toolkit import registry as R

        spec = next(s for s in R.SPECS if s.name == "grim_check")
        out = spec.call({"mean": 5.19, "n": 28, "decimals": 2,
                         "data_type": "likert", "lower_bound": 1,
                         "upper_bound": 7, "provenance": "ocr_table"})
        assert out["severity"] == "indeterminate"
        assert out["applicable"] is False

    def test_the_refusal_names_transcription_and_not_measurement(self):
        """A reader who is given the wrong reason cannot audit the refusal, and
        an operator who wants to lift it does the wrong thing: an OCR'd value
        needs re-READING, not re-measuring."""
        from forensic_metascience_ai_toolkit import registry as R

        spec = next(s for s in R.SPECS if s.name == "grim_check")
        out = spec.call({"mean": 5.19, "n": 28, "decimals": 2,
                         "data_type": "likert", "lower_bound": 1,
                         "upper_bound": 7, "provenance": "ocr_table"})
        assert "TRANSCRIBED" in out["error"]
        assert "no last printed digit" not in out["error"]
        assert "did print a last digit" in out["error"]
        assert "printed_table" in out["explanation"]     # the promotion path
        assert out["transcribed_params"]

    def test_a_measured_value_keeps_its_own_reason(self):
        """The two refusals must not converge on one sentence: they have
        different remedies, and only one of them has a remedy at all."""
        from forensic_metascience_ai_toolkit import registry as R

        spec = next(s for s in R.SPECS if s.name == "grim_check")
        out = spec.call({"mean": 5.19, "n": 28, "decimals": 2,
                         "data_type": "likert", "lower_bound": 1,
                         "upper_bound": 7, "provenance": "measured_raster"})
        assert "no last printed digit" in out["error"]
        assert "TRANSCRIBED" not in out["error"]
        assert out["measured_params"]

    def test_a_printed_value_still_runs(self):
        """The gate must not have swallowed the ordinary case."""
        from forensic_metascience_ai_toolkit import registry as R

        spec = next(s for s in R.SPECS if s.name == "grim_check")
        out = spec.call({"mean": 5.19, "n": 28, "decimals": 2,
                         "data_type": "likert", "lower_bound": 1,
                         "upper_bound": 7, "provenance": "printed_table"})
        assert out["severity"] != "indeterminate" or out.get("applicable") is not False

    def test_check_table_refuses_transcribed_cells_on_the_table_path(self):
        """The path a scanned supplement actually travels. `dispatch.check_table`
        held its own literal copy of the measured set, so adding the OCR channel
        to the registry alone would have left the table path judging the very
        cells the per-cell path refuses."""
        from forensic_metascience_ai_toolkit.dispatch import check_table

        cells = [{"raw": "5.19 (1.20)", "row_label": "Score", "n": 28}]
        variables = [{"id": "s", "family": "likert_item", "lower_bound": 1,
                      "upper_bound": 7, "confidence": "high"}]
        out = check_table(cells, variables=variables, bindings={"Score": "s"},
                          provenance="ocr_table")
        verdicts = [r.get("severity") for r in (out.get("results") or [])]
        assert all(v == "indeterminate" for v in verdicts), verdicts


class TestTheModelIsToldTheValueExists:
    def test_the_provenance_help_names_the_ocr_channel(self):
        """A gate the model cannot address is a gate it will route around: it
        would pass `printed_table` for an OCR'd cell and the refusal never
        fires. The help string IS the MCP schema, so this is what it sees."""
        from forensic_metascience_ai_toolkit.registry import PROVENANCE_HELP

        assert "ocr_table" in PROVENANCE_HELP
        assert "misread" in PROVENANCE_HELP


class TestPreflightSaysWhetherThisMachineCanReadImages:
    """An operator who never sees the row does not know a whole class of
    supplement went unread here, and does not know one install changes it.

    Same reasoning as the python-docx / openpyxl rows added after 56 supplements
    read as empty in billed runs -- except that this one is NOT fatal, because a
    paper with a text layer never touches it and because the result already
    refuses in a way nothing downstream can mistake for "no tables".
    """

    ROW = "OCR engine (image supplements)"

    def _row(self):
        """THE CHECK ITSELF, NOT THE SOURCE TEXT OF `cli.py` (2026-08-11).

        This used to read `cli.py` and split on `def preflight_cmd`, which was
        always an approximation: it asserted a string was PRESENT, not that a
        check RAN. Dan then moved every preflight row into `preflight.py` so the
        command and the automatic pre-spend gate render from one definition and
        cannot drift (73c1b13), and made the same correction to the
        supplement-dependency tests. A source-grep would now pass or fail on
        where the string happens to live, which is not the property worth
        testing."""
        from forensic_metascience_ai_toolkit.preflight import optional_checks
        rows = [r for r in optional_checks() if r[0] == self.ROW]
        assert rows, f"`{self.ROW}` is not among the preflight checks at all"
        return rows[0]

    def test_the_row_exists(self):
        assert self._row()[0] == self.ROW

    def test_it_is_advisory_rather_than_fatal(self):
        """Membership in `optional_checks` IS the non-fatal property now --
        `assert_ready` raises on `fatal_checks` alone."""
        from forensic_metascience_ai_toolkit.preflight import fatal_checks
        assert self.ROW not in [r[0] for r in fatal_checks(refresh=True)], (
            "a paper with a text layer never touches OCR; blocking on it would "
            "refuse work that is still valid")

    def test_it_names_the_remedy(self):
        """A capability report an operator cannot act on is half a report."""
        _name, available, detail = self._row()
        status = ocr.engine_status()
        if available:
            assert status["engine"] and status["engine"] in detail
        else:
            assert status["smallest_install"] in detail
            assert "rapidocr-onnxruntime" in status["smallest_install"]

    def test_it_says_what_an_unread_image_is_reported_as(self):
        """The row's whole purpose: an absent engine means UNREAD, not empty,
        and an operator who reads 'no tables' as a fact about the document has
        been misled about their own machine."""
        _name, available, detail = self._row()
        if not available:
            assert "UNREAD" in detail


@pytest.mark.skipif(not ocr.engine_status()["available"],
                    reason="no OCR engine installed on this machine")
def test_a_real_engine_produces_word_boxes(tmp_path):
    """Only runs where an engine exists. Kept so that installing one is a
    one-command change with a test already waiting for it."""
    from PIL import Image, ImageDraw

    img = tmp_path / "t.png"
    im = Image.new("RGB", (400, 100), "white")
    ImageDraw.Draw(im).text((10, 40), "Age 48.90 49", fill="black")
    im.save(img)
    got = ocr.ocr_words(img)
    assert got.get("words") is not None
