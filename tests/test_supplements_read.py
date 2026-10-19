"""
Tests for supplementary-material readers (`extraction/supplements_read.py`).

Two things matter here beyond "it opens the file":

* a merged cell must not be duplicated (python-docx repeats one by default,
  which would fabricate identical (mean, SD) pairs), and
* an unreadable format must REFUSE by name rather than return nothing, so the
  sweep records a coverage gap instead of treating the supplement as absent.
"""

import csv

import pytest

from metascience_agent.extraction.supplements_read import (
    UNREADABLE,
    extract_supplement,
)
from metascience_agent.tools.celltypes import parse_cells

docx = pytest.importorskip("docx")
openpyxl = pytest.importorskip("openpyxl")


def _docx(tmp_path, rows, merge=None):
    document = docx.Document()
    table = document.add_table(rows=len(rows), cols=len(rows[0]))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            table.cell(r, c).text = value
    if merge:
        (r, c1), (r2, c2) = merge
        table.cell(r, c1).merge(table.cell(r2, c2))
    path = tmp_path / "si.docx"
    document.save(str(path))
    return path


def _xlsx(tmp_path, rows, name="Sheet1"):
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = name
    for row in rows:
        sheet.append(row)
    path = tmp_path / "si.xlsx"
    book.save(str(path))
    return path


# ---------------------------------------------------------------------------
# docx
# ---------------------------------------------------------------------------

def test_docx_tables_become_a_grid_with_cells(tmp_path):
    path = _docx(tmp_path, [["Var", "Mean (SD)"], ["Age", "45.6 (10.3)"]])
    result = extract_supplement(path)
    assert result["n_tables"] == 1
    table = result["tables"][0]
    assert table["headers"] == ["Var", "Mean (SD)"]
    assert table["rows"] == [["Age", "45.6 (10.3)"]]
    # `row` is the 1-based index into `data` (`[header] + body`), so a cell and
    # the grid row it came from share ONE coordinate. `get_table` needs that to
    # window both views on a single cursor.
    # `col` is the 0-based physical column, so `data[row - 1][col]` is the cell.
    # It is here because `col_label` is NOT an address: a stacked header can
    # give several columns one label, and on a table whose header repeats a
    # span that is the ordinary case, not the exotic one.
    assert table["cells"] == [
        {"raw": "45.6 (10.3)", "row": 2, "col": 1, "row_label": "Age",
         "col_label": "Mean (SD)"}
    ]


def test_docx_merged_cell_is_not_duplicated(tmp_path):
    """
    python-docx returns a merged cell once per grid position it covers. Keeping
    those copies would turn one measurement into several identical (mean, SD)
    pairs and trip `detect_duplication` at three -- a finding invented by the
    reader, against a paper that did nothing wrong.
    """
    # The second cell is empty, as a real merged span is: Word concatenates the
    # text of every cell it merges, so seeding both would test our own fixture.
    path = _docx(
        tmp_path,
        [["Var", "A", "B"], ["Pooled", "3.7 (0.30)", ""]],
        merge=((1, 1), (1, 2)),
    )
    table = extract_supplement(path)["tables"][0]
    flat = [c for row in table["data"] for c in row]
    assert flat.count("3.7 (0.30)") == 1
    assert table["rows"][0] == ["Pooled", "3.7 (0.30)", ""]


def test_docx_cell_newlines_do_not_glue_numbers(tmp_path):
    """A cell holding "12.3\\n4.5" must not read as one number."""
    path = _docx(tmp_path, [["Var", "V"], ["Age", "12.3\n4.5"]])
    assert extract_supplement(path)["tables"][0]["rows"][0][1] == "12.3 4.5"


def test_docx_cells_feed_the_typing_chain(tmp_path):
    path = _docx(tmp_path, [["Var", "% (95% CI)"], ["None", "96.2 (95.7-96.7)"]])
    typed = parse_cells(extract_supplement(path)["tables"][0]["cells"])["cells"]
    assert typed[0]["kind"] == "estimate_ci"
    assert typed[0]["value"] == 96.2


# ---------------------------------------------------------------------------
# xlsx
# ---------------------------------------------------------------------------

def test_xlsx_sheet_becomes_a_table(tmp_path):
    path = _xlsx(tmp_path, [["id", "score"], [1, 4.5], [2, 5.5]], name="Raw")
    result = extract_supplement(path)
    table = result["tables"][0]
    assert table["label"] == "Raw"
    assert table["headers"] == ["id", "score"]
    assert table["n_rows"] == 2


def test_xlsx_participant_level_data_is_flagged(tmp_path):
    """
    Row-per-participant data supports checks a summary table cannot, so the
    reader says so rather than leaving it to be noticed.
    """
    rows = [["id", "score"]] + [[i, i / 3] for i in range(250)]
    table = extract_supplement(_xlsx(tmp_path, rows))["tables"][0]
    assert any("participant-level" in w for w in table["warnings"])


def test_xlsx_empty_rows_are_dropped_not_padded_into_data(tmp_path):
    path = _xlsx(tmp_path, [["a", "b"], [None, None], [1, 2]])
    table = extract_supplement(path)["tables"][0]
    assert table["rows"] == [["1", "2"]]


# ---------------------------------------------------------------------------
# csv
# ---------------------------------------------------------------------------

def test_csv_is_read(tmp_path):
    path = tmp_path / "si.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows([["Var", "V"], ["Age", "12.3"]])
    table = extract_supplement(path)["tables"][0]
    assert table["rows"] == [["Age", "12.3"]]


# ---------------------------------------------------------------------------
# Refusals — the honesty contract
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("suffix", sorted(UNREADABLE))
def test_unreadable_formats_refuse_by_name(tmp_path, suffix):
    """
    The refusal IS the result. Returning an empty table instead would let a
    review read as though the supplement had been checked.
    """
    path = tmp_path / f"si{suffix}"
    path.write_bytes(b"\x00\x01binary")
    result = extract_supplement(path)
    assert result["error"]
    assert suffix in result["error"]
    assert result["tables"] == []
    assert result["unreadable_format"] == suffix


def test_legacy_doc_is_distinguished_from_docx(tmp_path):
    path = tmp_path / "si.doc"
    path.write_bytes(b"\xd0\xcf\x11\xe0legacy")
    assert "legacy binary" in extract_supplement(path)["error"]


def test_image_supplement_says_there_is_no_ocr(tmp_path):
    path = tmp_path / "fig.jpg"
    path.write_bytes(b"\xff\xd8\xff")
    assert "OCR" in extract_supplement(path)["error"]


def test_corrupt_file_returns_an_error_rather_than_raising(tmp_path):
    path = tmp_path / "si.docx"
    path.write_bytes(b"not really a docx")
    result = extract_supplement(path)
    assert result["error"] and result["tables"] == []


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        extract_supplement(tmp_path / "nope.docx")


# ---------------------------------------------------------------------------
# Ragged rows -- the alignment claim this reader was making without looking
#
# `_finish` right-pads every short row and then set `alignment_uncertain:
# False` unconditionally: a POSITIVE assertion that the columns line up, made
# without checking. `jats._expand` keeps exactly the fact needed to answer it
# (which rows were short IN THE SOURCE) and `jats._build_table` acts on it;
# this path threw it away.
#
# A .docx or .csv row that runs short is padded on the RIGHT, so every value in
# it after the gap sits one or more columns left of its heading. A (mean, sd,
# n) triple read out of that is a triple the supplement never reported, and
# GRIM/GRIMMER would call it impossible -- against authors whose file was
# merely ragged.
# ---------------------------------------------------------------------------

def _csv(tmp_path, rows, name="si.csv"):
    path = tmp_path / name
    path.write_text("\n".join(",".join(str(c) for c in r) for r in rows) + "\n",
                    encoding="utf-8")
    return path


def test_a_short_numeric_row_is_reported_as_uncertain(tmp_path):
    path = _csv(tmp_path, [["Group", "Mean", "SD", "N"],
                           ["A", "5.1", "1.2", "30"],
                           ["B", "6.2", "1.4"]])
    table = extract_supplement(path)["tables"][0]
    assert table["alignment_uncertain"] is True
    assert any("ragged row" in w for w in table["warnings"])


def test_the_warning_matches_the_jats_wording(tmp_path):
    """One vocabulary for one fact. A reader should not have to learn that
    "ragged" from a supplement means what "ragged" from an XML table means."""
    path = _csv(tmp_path, [["Group", "Mean", "SD", "N"],
                           ["B", "6.2", "1.4"]])
    warning = extract_supplement(path)["tables"][0]["warnings"][0]
    assert "column labels may be shifted" in warning
    assert "reconcile against" in warning


def test_a_rectangular_table_is_not_flagged(tmp_path):
    """A flag that fires on correct tables is worse than no flag."""
    path = _csv(tmp_path, [["Group", "Mean", "SD"],
                           ["A", "5.1", "1.2"],
                           ["B", "6.2", "1.4"]])
    table = extract_supplement(path)["tables"][0]
    assert table["alignment_uncertain"] is False
    assert table["warnings"] == []


def test_a_one_cell_section_label_row_stays_silent(tmp_path):
    """A section heading inside a table is short and benign. Same rule as
    `jats`: it takes TWO numbers in a short row to raise the flag."""
    path = _csv(tmp_path, [["Group", "Mean", "SD"],
                           ["Cohort 1"],
                           ["A", "5.1", "1.2"]])
    assert extract_supplement(path)["tables"][0]["alignment_uncertain"] is False


def test_an_unlabelled_column_is_not_given_an_invented_name(tmp_path):
    """The header ran short, so those columns have NO label in the file.
    `col2` reads as a column identity the source established; it did not."""
    path = _csv(tmp_path, [["Group", "Mean"],
                           ["A", "5.1", "1.2", "30"]])
    table = extract_supplement(path)["tables"][0]
    labels = [c["col_label"] for c in table["cells"]]
    assert "col2" not in labels
    assert "(unlabelled column 2)" in labels


def test_a_short_header_is_itself_reported(tmp_path):
    path = _csv(tmp_path, [["Group", "Mean"], ["A", "5.1", "1.2", "30"]])
    table = extract_supplement(path)["tables"][0]
    assert table["alignment_uncertain"] is True
    assert any("header row was shorter" in w for w in table["warnings"])


def test_a_labelled_column_keeps_its_own_label(tmp_path):
    path = _csv(tmp_path, [["Group", "Mean"], ["A", "5.1"]])
    table = extract_supplement(path)["tables"][0]
    assert [c["col_label"] for c in table["cells"]] == ["Mean"]


def test_jats_tables_keep_their_col_fallback(tmp_path):
    """`col{i}` stays right for a JATS grid, which is rectangular by
    construction: there the position IS the column identity. Only the padded
    path needs the stronger wording."""
    from metascience_agent.extraction.jats import _cells_from_grid
    cells = _cells_from_grid(["Var", ""], [["Age", "12.3"]])
    assert cells[0]["col_label"] == "col1"


# ---------------------------------------------------------------------------
# A CONTINUATION TABLE HAS NO HEADER, AND MUST NOT BORROW ITS FIRST DATA ROW
#
# MEASURED 2026-09-05 on Stern 2014's Supplementary Table S1. Word splits a
# long table across two elements and does not repeat the header on the second,
# so that table's first row is `CFC - IGF-IIR | 7-9 | % Freezing | ... | 43.83`
# -- and all 1,704 of its cells were labelled with it, `43.83` and `IgG/Veh`
# read as COLUMN NAMES. A mean paired with the wrong denominator is the
# documented route from a coverage win to a false accusation (`25e2f9f`).
#
# `jats._reads_as_measurements` already told the two rows apart correctly; it
# was only ever asked whether to PROMOTE a second header row, never whether the
# first was a header at all. Cost of asking, over every fast-format supplement
# held at the time: 293 tables carry a header, exactly ONE trips this.
# ---------------------------------------------------------------------------

def test_a_data_first_row_does_not_become_the_column_labels(tmp_path):
    path = _csv(tmp_path, [["CFC", "7-9", "43.83", "3.64"],
                           ["CFC", "7-9", "41.20", "2.90"],
                           ["CFC", "8-9", "39.10", "3.11"]])
    table = extract_supplement(path)["tables"][0]
    labels = {c["col_label"] for c in table["cells"]}
    assert "43.83" not in labels
    assert any(str(l).startswith("(unlabelled column") for l in labels)


def test_that_first_row_is_kept_as_data_rather_than_deleted(tmp_path):
    """Refusing the labels must not cost the measurements. A header that
    swallows a data row deletes it from every check -- the worse error, and the
    one this module's other brakes exist to prevent."""
    path = _csv(tmp_path, [["CFC", "7-9", "43.83", "3.64"],
                           ["CFC", "7-9", "41.20", "2.90"],
                           ["CFC", "8-9", "39.10", "3.11"]])
    table = extract_supplement(path)["tables"][0]
    assert "43.83" in {str(c["raw"]).strip() for c in table["cells"]}


def test_the_refusal_says_why(tmp_path):
    path = _csv(tmp_path, [["CFC", "7-9", "43.83", "3.64"],
                           ["CFC", "7-9", "41.20", "2.90"],
                           ["CFC", "8-9", "39.10", "3.11"]])
    table = extract_supplement(path)["tables"][0]
    assert any("reads as measurements" in w for w in table["warnings"])


def test_a_real_header_is_still_a_header(tmp_path):
    """The brake must not fire on the ordinary case, or it buys correctness by
    deleting every column label in the corpus."""
    path = _csv(tmp_path, [["Test", "n", "Mean", "s.e.m."],
                           ["CFC", "7-9", "43.83", "3.64"],
                           ["CFC", "8-9", "39.10", "3.11"]])
    table = extract_supplement(path)["tables"][0]
    assert [c["col_label"] for c in table["cells"]][:3] == ["n", "Mean", "s.e.m."]
