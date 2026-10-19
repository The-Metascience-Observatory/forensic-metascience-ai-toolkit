"""
Tests for publisher-XML ingestion (`extraction/jats.py`).

The load-bearing tests here are the ones that stop the PARSER from inventing
evidence: a merged cell repeated into its continuations fabricates duplicate
(mean, SD) pairs, and a shifted column label hands GRIM a triple the paper never
reported. Those are asserted directly, not implied.
"""

import xml.etree.ElementTree as ET

import pytest

from metascience_agent.extraction.jats import (
    ELSEVIER,
    JATS,
    PMC_SET,
    _cell_text,
    _expand,
    _flatten_header,
    extract_xml_text_with_tables,
    find_body_md,
    find_xml,
    paper_text,
    paper_text_with_source,
    xml_flavour,
)
from metascience_agent.tools.celltypes import parse_cells
from metascience_agent.tools.tableparse import parse_cell


def _write(tmp_path, body, name="paper.xml"):
    path = tmp_path / name
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<article><front><article-meta><title-group>'
        f'<article-title>T</article-title></title-group></article-meta></front>'
        f'<body>{body}</body></article>',
        encoding="utf-8",
    )
    return path


def _table(tmp_path, inner, wrap_extra=""):
    return _write(
        tmp_path,
        f'<sec><title>Results</title><table-wrap id="t1"><label>Table 1</label>'
        f'<caption><p>Cap.</p></caption><table>{inner}</table>{wrap_extra}'
        f'</table-wrap></sec>',
    )


def _only_table(tmp_path, inner, wrap_extra=""):
    result = extract_xml_text_with_tables(_table(tmp_path, inner, wrap_extra), tables="full")
    assert result["n_tables"] == 1
    return result["tables"][0]


# ---------------------------------------------------------------------------
# Span expansion — the fabricated-duplication guard
# ---------------------------------------------------------------------------

def test_body_colspan_places_the_value_exactly_once():
    """
    A merged body value must NOT be repeated across the columns it covers.

    Repeating one `3.7 (0.30)` with colspan=4 yields four identical (mean, SD)
    pairs; `detect_duplication` escalates at three, so the parser alone would
    manufacture a `highly_suspicious` finding against an innocent paper.
    """
    rows = [
        [("Group", 1, 1, True), ("A", 1, 1, True), ("B", 1, 1, True),
         ("C", 1, 1, True), ("D", 1, 1, True)],
        [("Pooled", 1, 1, False), ("3.7 (0.30)", 4, 1, False)],
    ]
    grid, spans, _, _ = _expand(rows)
    flat = [c for row in grid for c in row]
    assert flat.count("3.7 (0.30)") == 1
    assert grid[1] == ["Pooled", "3.7 (0.30)", "", "", ""]
    assert spans[0]["colspan"] == 4 and spans[0]["repeated"] is False


def test_body_rowspan_places_the_value_exactly_once_but_repeats_the_label():
    """Vertical twin of the above; a row LABEL may repeat, a measurement may not."""
    rows = [
        [("Var", 1, 1, True), ("Val", 1, 1, True), ("p", 1, 1, True)],
        [("Age", 1, 3, False), ("1.1", 1, 1, False), ("0.04", 1, 3, False)],
        [("2.2", 1, 1, False)],
        [("3.3", 1, 1, False)],
    ]
    grid, _, _, _ = _expand(rows)
    flat = [c for row in grid for c in row]
    assert flat.count("0.04") == 1, "a merged p-value is one measurement"
    assert flat.count("Age") == 3, "a row label is not a measurement"
    assert grid[2] == ["Age", "2.2", ""]


def test_header_colspan_repeats_so_group_binding_survives():
    rows = [
        [("Characteristic", 1, 2, True), ("Weighted %", 2, 1, True)],
        [("Nonveteran", 1, 1, True), ("Veteran", 1, 1, True)],
    ]
    grid, _, _, _ = _expand(rows)
    assert grid[0] == ["Characteristic", "Weighted %", "Weighted %"]
    assert grid[1] == ["Characteristic", "Nonveteran", "Veteran"]
    assert _flatten_header(grid, 3) == [
        "Characteristic", "Weighted % | Nonveteran", "Weighted % | Veteran",
    ]


def test_rowspan_header_label_is_not_doubled():
    rows = [[("Var", 1, 2, True), ("A", 1, 1, True)], [("B", 1, 1, True)]]
    grid, _, _, _ = _expand(rows)
    assert _flatten_header(grid, 2)[0] == "Var", "not 'Var | Var'"


def test_every_expanded_row_is_rectangular():
    rows = [
        [("h", 1, 1, True), ("i", 2, 1, True)],
        [("a", 1, 1, False)],
        [("b", 1, 1, False), ("c", 1, 1, False), ("d", 1, 1, False)],
    ]
    grid, _, _, _ = _expand(rows)
    assert len({len(r) for r in grid}) == 1


def test_ragged_flag_is_only_set_for_rows_short_in_the_source():
    """
    Anchor-only expansion leaves blanks in well-formed rows, so testing for
    blanks rather than for source-shortness flags a third of all tables and
    makes the signal worthless.
    """
    rows = [
        [("h", 1, 1, True), ("i", 1, 1, True), ("j", 1, 1, True)],
        [("lbl", 1, 1, False), ("1.1", 2, 1, False)],   # blanks, but not short
        [("x", 1, 1, False), ("2.2", 1, 1, False)],     # genuinely short
    ]
    _, _, _, padded = _expand(rows)
    assert padded == [False, False, True]


# ---------------------------------------------------------------------------
# Header handling
# ---------------------------------------------------------------------------

def test_multirow_header_becomes_composite_labels(tmp_path):
    table = _only_table(tmp_path, (
        "<thead>"
        '<tr><th rowspan="2">Var</th><th colspan="2">Weighted %</th></tr>'
        "<tr><th>Non</th><th>Vet</th></tr>"
        "</thead>"
        "<tbody><tr><td>Age</td><td>50.1</td><td>61.2</td></tr></tbody>"
    ))
    assert table["n_header_rows"] == 2
    assert table["headers"] == ["Var", "Weighted % | Non", "Weighted % | Vet"]
    assert table["header_rows"][0][1] == "Weighted %"


def test_no_thead_does_not_promote_a_body_row(tmp_path):
    table = _only_table(
        tmp_path, "<tbody><tr><td>a</td><td>1</td></tr></tbody>")
    assert table["n_header_rows"] == 0
    assert table["headers"] == ["", ""]
    assert any("no <thead>" in w for w in table["warnings"])


def test_column_with_no_header_text_gets_no_invented_label():
    assert _flatten_header([["A", ""]], 2) == ["A", ""]


# ---------------------------------------------------------------------------
# Inline markup — every case here can synthesise a number the paper never had
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("markup,expected", [
    ("<td><italic>M</italic> (SD)</td>", "M (SD)"),
    ('<td>2022<xref ref-type="bibr">1</xref></td>', "2022[1]"),
    ("<td>10<sup>-3</sup></td>", "10^-3"),
    ("<td>12.3<break/>4.5</td>", "12.3 4.5"),
    ("<td>12.3<sup>a</sup></td>", "12.3ᵃ"),
    ("<td>kg/m<sup>2</sup></td>", "kg/m²"),
    ("<td>Serious adverse event<sup>1</sup></td>", "Serious adverse event¹"),
    ("<td>12.3<sup>*</sup></td>", "12.3*"),
    ("<td>−3.5</td>", "-3.5"),
    ("<td>18–65</td>", "18–65"),
    ("<td>226 150 662</td>", "226150662"),
    ("<td>  spaced   out  </td>", "spaced out"),
])
def test_cell_text_flattening(markup, expected):
    assert _cell_text(ET.fromstring(markup)) == expected


def test_citation_xref_does_not_glue_into_a_new_number():
    assert _cell_text(ET.fromstring(
        '<td>2022<xref ref-type="bibr">1</xref></td>')) != "20221"


def test_superscript_exponent_does_not_glue():
    assert _cell_text(ET.fromstring("<td>10<sup>-3</sup></td>")) != "103"


def test_true_minus_becomes_parseable_and_keeps_its_sign():
    assert parse_cell(_cell_text(ET.fromstring("<td>−3.5</td>")))["value"] == -3.5


def test_en_dash_range_is_left_alone():
    """`–` is ambiguous between minus and range; `celltypes` reads it as a range."""
    assert "–" in _cell_text(ET.fromstring("<td>18–65</td>"))


def test_mathml_tokens_are_not_concatenated():
    text = _cell_text(ET.fromstring(
        "<td><inline-formula><math><mn>0.05</mn><mn>3</mn></math>"
        "</inline-formula></td>"))
    assert "0.053" not in text


def test_footnote_marker_survives_as_an_extra(tmp_path):
    table = _only_table(tmp_path, (
        "<tbody><tr><td>Age</td><td>12.3<sup>a</sup></td></tr></tbody>"))
    parsed = parse_cell(table["rows"][0][1])
    assert parsed["value"] == 12.3
    assert "ᵃ" in parsed["extras"], "raised, so it cannot be read as part of 12.3"


# ---------------------------------------------------------------------------
# Footnotes, captions, image-only
# ---------------------------------------------------------------------------

def test_footnotes_are_captured_with_their_markers(tmp_path):
    table = _only_table(
        tmp_path,
        "<tbody><tr><td>a</td><td>1</td></tr></tbody>",
        wrap_extra=("<table-wrap-foot><fn><label><sup>a</sup></label>"
                    "<p>Values are n (%).</p></fn></table-wrap-foot>"),
    )
    assert {"marker": "a", "text": "Values are n (%)."} in table["footnotes"]
    assert table["label"] == "Table 1"
    assert table["caption"] == "Cap."


def test_image_only_table_reports_no_cells(tmp_path):
    """
    An empty grid that still *looks* like a table is the dishonest failure —
    it reads as "checked and clean".
    """
    path = _write(tmp_path, (
        '<sec><title>R</title><table-wrap id="t9"><label>Table 9</label>'
        '<graphic xlink:href="tbl9.jpg" '
        'xmlns:xlink="http://www.w3.org/1999/xlink"/></table-wrap></sec>'))
    result = extract_xml_text_with_tables(path, tables="full")
    table = result["tables"][0]
    assert table["image_only"] is True
    assert table["data"] == [] and table["cells"] == []
    assert table["graphic_href"] == "tbl9.jpg"
    assert result["n_tables_image_only"] == 1
    assert any("image" in w for w in result["warnings"])


# ---------------------------------------------------------------------------
# Cells offered to the typing chain
# ---------------------------------------------------------------------------

def test_cells_bind_each_value_to_its_composite_column_label(tmp_path):
    """
    The test that actually protects GRIM: it pins the value -> column-label
    binding end to end. A one-column shift would put a mean under the wrong
    group and hand the granularity checks a triple the paper never reported.
    """
    table = _only_table(tmp_path, (
        "<thead>"
        '<tr><th rowspan="2">Var</th><th colspan="2">Weighted %</th></tr>'
        "<tr><th>Non</th><th>Vet</th></tr>"
        "</thead>"
        "<tbody><tr><td>Age</td><td>50.1</td><td>61.2</td></tr></tbody>"
    ))
    by_value = {c["raw"]: c for c in table["cells"]}
    assert by_value["50.1"]["col_label"] == "Weighted % | Non"
    assert by_value["61.2"]["col_label"] == "Weighted % | Vet"
    assert by_value["61.2"]["row_label"] == "Age"


def test_estimate_ci_cells_survive_to_the_typing_chain(tmp_path):
    """
    `parse_table` drops any cell `parse_cell` cannot read, which silently
    discards every `estimate (CI)` cell -- the highest-yield check on clinical
    papers. The cells we publish must reach `parse_cells_typed` intact.
    """
    table = _only_table(tmp_path, (
        "<thead><tr><th>Var</th><th>% (95% CI)</th></tr></thead>"
        "<tbody><tr><td>None</td><td>96.2 (95.7-96.7)</td></tr></tbody>"
    ))
    typed = parse_cells(table["cells"])["cells"]
    assert typed[0]["kind"] == "estimate_ci"
    assert (typed[0]["value"], typed[0]["low"], typed[0]["high"]) == (96.2, 95.7, 96.7)


def test_empty_row_label_inherits_the_previous_one(tmp_path):
    table = _only_table(tmp_path, (
        "<thead><tr><th>Var</th><th>V</th></tr></thead>"
        "<tbody><tr><td>Age</td><td>1</td></tr>"
        "<tr><td></td><td>2</td></tr></tbody>"
    ))
    assert [c["row_label"] for c in table["cells"]] == ["Age", "Age"]


# ---------------------------------------------------------------------------
# Flavours
# ---------------------------------------------------------------------------

def test_pmc_articleset_is_unwrapped(tmp_path):
    path = tmp_path / "p.xml"
    path.write_text(
        '<pmc-articleset><article><body><sec><title>R</title>'
        '<table-wrap><label>Table 1</label><table><tbody>'
        "<tr><td>a</td><td>1</td></tr></tbody></table></table-wrap>"
        "</sec></body></article></pmc-articleset>",
        encoding="utf-8",
    )
    result = extract_xml_text_with_tables(path, tables="full")
    assert result["source_format"] == PMC_SET
    assert result["n_tables"] == 1


def test_elsevier_cals_spans_and_alt_text(tmp_path):
    path = tmp_path / "e.xml"
    path.write_text(
        '<full-text-retrieval-response '
        'xmlns:ce="http://www.elsevier.com/xml/common/dtd">'
        "<originalText><ce:sections><ce:section>"
        "<ce:section-title>Results</ce:section-title>"
        "<ce:table><ce:label>Table 1</ce:label>"
        "<ce:alt-text>SHOULD NOT LEAK</ce:alt-text>"
        '<tgroup cols="3">'
        '<colspec colname="col1"/><colspec colname="col2"/><colspec colname="col3"/>'
        "<thead><row>"
        "<entry>Var</entry>"
        '<entry namest="col2" nameend="col3">Group</entry>'
        "</row></thead>"
        "<tbody>"
        '<row><entry morerows="1">Age</entry><entry>1.1</entry><entry>2.2</entry></row>'
        "<row><entry>3.3</entry><entry>4.4</entry></row>"
        "</tbody></tgroup></ce:table>"
        "</ce:section></ce:sections></originalText>"
        "</full-text-retrieval-response>",
        encoding="utf-8",
    )
    result = extract_xml_text_with_tables(path, tables="full")
    assert result["source_format"] == ELSEVIER
    table = result["tables"][0]
    assert table["headers"] == ["Var", "Group", "Group"]
    assert table["rows"][0] == ["Age", "1.1", "2.2"]
    assert table["rows"][1] == ["Age", "3.3", "4.4"], "morerows=1 means rowspan 2"
    assert all("SHOULD NOT LEAK" not in c for row in table["data"] for c in row)


def test_flavour_detection():
    assert xml_flavour(ET.fromstring("<article/>")) == JATS
    assert xml_flavour(ET.fromstring("<pmc-articleset/>")) == PMC_SET
    assert xml_flavour(
        ET.fromstring("<full-text-retrieval-response/>")) == ELSEVIER


# ---------------------------------------------------------------------------
# Document level
# ---------------------------------------------------------------------------

def test_table_content_is_not_inlined_into_the_text(tmp_path):
    """
    One representation of a table, and it is the grid. If the prose carried the
    numbers, the model could transcribe from text that already lost the column
    alignment -- the exact failure this module exists to remove.
    """
    path = _table(tmp_path, (
        "<thead><tr><th>Var</th><th>V</th></tr></thead>"
        "<tbody><tr><td>Age</td><td>99.123</td></tr></tbody>"))
    result = extract_xml_text_with_tables(path, tables="full")
    assert "## Results" in result["text"]
    assert "Table 1" in result["text"]
    assert "99.123" not in result["text"]


def test_tables_outside_body_are_collected(tmp_path):
    path = tmp_path / "f.xml"
    path.write_text(
        "<article><body><sec><title>R</title><p>x</p></sec></body>"
        "<floats-group><table-wrap><label>Table 2</label><table><tbody>"
        "<tr><td>a</td><td>1</td></tr></tbody></table></table-wrap>"
        "</floats-group></article>",
        encoding="utf-8",
    )
    assert extract_xml_text_with_tables(path, tables="full")["n_tables"] == 1


def test_truncation_caps_text_but_never_tables(tmp_path):
    body = "".join(
        f'<sec><title>S{i}</title><p>{"word " * 200}</p>'
        f"<table-wrap><label>Table {i}</label><table><tbody>"
        f"<tr><td>a</td><td>{i}</td></tr></tbody></table></table-wrap></sec>"
        for i in range(3)
    )
    result = extract_xml_text_with_tables(_write(tmp_path, body), max_chars=200, tables="full")
    assert result["truncated"] is True
    assert len(result["tables"]) == 3, "tables are the point of the tool"


def test_missing_file_raises_and_malformed_xml_returns_an_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        extract_xml_text_with_tables(tmp_path / "nope.xml", tables="full")

    bad = tmp_path / "bad.xml"
    bad.write_text("<article><body><sec>unclosed", encoding="utf-8")
    result = extract_xml_text_with_tables(bad, tables="full")
    assert "error" in result
    assert result["tables"] == [] and result["text"] == ""


def test_page_is_always_none(tmp_path):
    table = _only_table(tmp_path, "<tbody><tr><td>a</td><td>1</td></tr></tbody>")
    assert table["page"] is None, "XML has no pages; a page number would be invented"


def test_normalizations_are_reported_not_silent(tmp_path):
    path = _table(tmp_path, (
        "<tbody><tr><td>a</td><td>−3.5</td></tr></tbody>"))
    assert extract_xml_text_with_tables(path, tables="full")["normalizations"][
        "true_minus_to_ascii"] == 1


# ---------------------------------------------------------------------------
# Directory helpers
# ---------------------------------------------------------------------------

def test_find_xml_prefers_the_stem_matching_the_directory(tmp_path):
    paper = tmp_path / "10.1234--x"
    paper.mkdir()
    (paper / "other.xml").write_text("<article/>", encoding="utf-8")
    (paper / "10.1234--x.xml").write_text("<article/>", encoding="utf-8")
    assert find_xml(paper).name == "10.1234--x.xml"


def test_paper_text_falls_back_to_xml_when_body_md_is_gone(tmp_path):
    paper = tmp_path / "10.1234--y"
    paper.mkdir()
    (paper / "10.1234--y.xml").write_text(
        "<article><body><sec><title>Results</title><p>Hello.</p></sec>"
        "</body></article>",
        encoding="utf-8",
    )
    assert "Hello." in paper_text(paper)


def test_harvest_from_pdf_body_is_body_text(tmp_path):
    """The harvest writes `{stem}_from_pdf_body.md`, never `body.md`."""
    paper = tmp_path / "10.1002--bdm.1794"
    paper.mkdir()
    (paper / "10.1002--bdm.1794_from_pdf_body.md").write_text(
        "# Body\nSee Supplementary Table 1.\n", encoding="utf-8")
    assert "Supplementary Table 1" in paper_text(paper)
    assert find_body_md(paper).name == "10.1002--bdm.1794_from_pdf_body.md"


def test_literal_body_md_wins_over_harvest(tmp_path):
    paper = tmp_path / "p"
    paper.mkdir()
    (paper / "body.md").write_text("literal", encoding="utf-8")
    (paper / "p_from_pdf_body.md").write_text("harvest", encoding="utf-8")
    assert paper_text(paper) == "literal"
    assert find_body_md(paper).name == "body.md"


def test_xml_wins_over_harvest_markdown(tmp_path):
    """XML preserves tables; harvest markdown is a PDF transcription."""
    paper = tmp_path / "p"
    paper.mkdir()
    (paper / "p.xml").write_text(
        "<article><body><sec><p>From xml.</p></sec></body></article>",
        encoding="utf-8",
    )
    (paper / "p_from_pdf_body.md").write_text("From harvest.", encoding="utf-8")
    assert "From xml." in paper_text(paper)
    assert "From harvest." not in paper_text(paper)


def test_paper_text_still_prefers_body_md_when_present(tmp_path):
    paper = tmp_path / "p"
    paper.mkdir()
    (paper / "body.md").write_text("From markdown.", encoding="utf-8")
    (paper / "p.xml").write_text(
        "<article><body><sec><p>From xml.</p></sec></body></article>",
        encoding="utf-8",
    )
    assert paper_text(paper) == "From markdown."


# ---------------------------------------------------------------------------
# The PDF branch -- what makes the supplement gate able to see a PDF-only
# paper at all.
#
# MEASURED: with only the main PDF in a clean directory, `paper_text` returned
# 0 characters for 7 of 7 PDF-only ground-truth papers and `supplements.gate`
# PROCEEDED on all 7, because `find_references("")` finds nothing. Corpus-wide
# the same run was 97 of 97 papers passing the gate with 0 detected as citing a
# supplement; with the PDF branch it is 70 of 97 detected and 26 passing.
#
# WHAT CHANGED, 2026-08-16/17. This branch used to be a pdfplumber FALLBACK
# that read the file live. pdfplumber is gone -- Greg: "I never want to use
# pdfplumber again"; "it should never run *anywhere*" -- and `extract_text` is
# now CACHE-ONLY: it serves docling's text if `metascience extract-tables` has
# already run on the paper, and otherwise returns "" with a reason naming that
# command. It does not start the layout model, because `paper_text` is called
# per paper by the supplement gate, the quote haystack and the glyph scan, and
# extracting there took the suite from 5 minutes to over 30.
#
# So the branch survives; only its source of text changed, from "read the PDF
# now, badly" to "read what docling already stored, or say we have not read
# it". `cli.analyze` fills the cache for the article AND its supplements up
# front so the refusal never surfaces mid-run (asserted in
# tests/test_preextraction.py).
#
# These tests therefore come in pairs: with a cache, the text arrives and the
# gate can do its job; without one, the answer is a legible refusal and "" that
# every caller must read as UNKNOWN. Both halves are needed -- a suite holding
# only the refusal half would not notice if the PDF branch were deleted
# outright, and a PDF-only paper would go back to silently passing the gate.
# ---------------------------------------------------------------------------

#: Enough text that the page reads as a page.
#:
#: This fixture was one line of 53 characters, which `readable_body_chars` now
#: scores as unreadable. On a ONE-PAGE document, furniture cannot be identified
#: by repetition, so that case alone falls back to raw length -- and 53
#: characters is two orders of magnitude under a real page (measured median
#: 4,743 characters per page across `high_value_pdfs_to_run_on`).
#:
#: Worth recording why this mattered beyond the one red test. The very next
#: test asserts the supplement gate REFUSES this paper, and it kept passing --
#: but for the wrong reason: refusing because the text was unreadable, rather
#: than because the paper cites a supplement we do not hold. A fixture too thin
#: to be a paper turns a specific assertion into a vacuous one.
_PAGE_BODY = (
    "Results. See Supplementary Table 1 for the full model. Participants were "
    "randomly assigned to one of two conditions and completed the task in a "
    "counterbalanced order. Reaction times were log-transformed prior to "
    "analysis, and trials faster than 200 ms were excluded. The interaction "
    "between condition and block was reliable, F(1, 38) = 7.21, p = .011, "
    "with an estimated effect size of eta-squared = .16."
)


def _pdf(path, text=_PAGE_BODY):
    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    page = doc.new_page()
    # insert_textbox wraps. insert_text would run one long line off the right
    # edge and lose most of the characters this fixture exists to supply.
    page.insert_textbox(fitz.Rect(72, 90, 520, 700), text, fontsize=10)
    doc.save(str(path))
    doc.close()
    return path


def _extracted(pdf, text=_PAGE_BODY):
    """Stand in for a completed `metascience extract-tables` on `pdf`.

    Writes the schema-4 cache entry docling would have written, keyed by the
    same content hash the reader uses, so `paper_text` takes its PDF branch and
    gets text. The suite cannot run the real extractor -- one paper is minutes
    of layout model, and doing it inside a read path is the regression that
    took this suite from 5 minutes to over 30 -- and the cache is the ONLY
    thing `extract_text` consults now, so writing it is the whole of the setup.

    `text` defaults to the same body inserted into the fixture PDF, so the
    stand-in says what docling would have said rather than something the file
    does not contain.
    """
    import json

    from metascience_agent.extraction import docling_tables as dl

    cache = dl._cache_path(pdf)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(
        json.dumps({
            "text": text, "tables": [], "error": None, "n_tables": 0,
            "n_text_chars": len(text),
            "pages": [{"page_num": 1, "text": text}], "num_pages": 1,
            "source_format": "pdf", "extractor": "docling", "cache_schema": 4,
        }),
        encoding="utf-8",
    )
    return pdf


def test_paper_text_reads_the_pdf_when_there_is_no_md_or_xml(tmp_path):
    """The PDF branch still exists and is still reached -- it just reads
    docling's stored text now instead of running pdfplumber live.

    Was `test_paper_text_falls_back_to_the_pdf_when_there_is_no_md_or_xml`,
    which asserted the pdfplumber fallback by name; that mechanism is deleted.
    The property it protected is unchanged: a paper with nothing but a PDF is
    not treated as a paper with no text. Its refusal half is the next test.
    """
    paper = tmp_path / "10.1234--z"
    paper.mkdir()
    _extracted(_pdf(paper / "10.1234--z.pdf"))
    assert "Supplementary Table 1" in paper_text(paper)


def test_an_unextracted_pdf_yields_a_refusal_not_silent_text(tmp_path):
    """The other half, and the reason the retarget above was needed at all.

    With no cache there is no text, and the honest answer is to say so: ""
    plus a warning naming the command that fixes it. "" here means UNKNOWN --
    we have not read this paper -- and never "this paper says nothing"; the
    caller that acts on the distinction is `supplements.audit`, which fails
    closed on empty text (`missing=None`, asserted below).

    Reading the PDF anyway is not the alternative it looks like. Live
    extraction in this path is minutes per paper, and the text pdfplumber used
    to return in its place was measurably worse -- table recall 60.4% vs 95.8%,
    operators rendered as `(cid:N)`, two-column layouts fused into sentences
    neither column contains -- so the two readers disagreed on the same
    document, 36,016 characters against 38,879.
    """
    from metascience_agent.supplements import audit

    paper = tmp_path / "10.1234--z"
    paper.mkdir()
    _pdf(paper / "10.1234--z.pdf")

    with pytest.warns(UserWarning) as record:
        assert paper_text(paper) == ""
    said = "\n".join(str(w.message) for w in record)
    assert "extract-tables" in said, f"no actionable reason given: {said}"

    # UNKNOWN, not "no supplement is cited". `missing is None` is the
    # three-valued answer; `False` here would be the gate clearing a paper it
    # never read. `text_status` must say this is a cache miss, not a scan --
    # the batch plan used to print "scanned or corrupt" for that case.
    assert audit(paper)["missing"] is None
    assert audit(paper)["text_status"] == "not_extracted"
    assert paper_text_with_source(paper)[1] == "pdf_not_extracted"


def test_the_supplement_gate_can_see_an_extracted_pdf_only_paper(tmp_path):
    """The whole point of the PDF branch. A gate that cannot read the paper is
    not a gate.

    Now asserts WHY it refuses, which the cache-only change made necessary.
    Once `extract_text` stopped reading PDFs live this test kept passing on an
    unextracted paper -- but for the opposite reason: the gate was failing
    closed on text it could not read (`missing=None`) rather than detecting the
    "Supplementary Table 1" this fixture cites. Same verdict, no longer any
    evidence that the paper was read. `text_available` is the discriminator.
    """
    from metascience_agent.supplements import gate
    paper = tmp_path / "10.1234--z"
    paper.mkdir()
    _extracted(_pdf(paper / "10.1234--z.pdf"))
    result = gate(paper)
    # Since 2026-10-18 a missing supplement warns and runs; what matters here
    # is that the gate READ the paper and found the citation.
    assert result["proceed"] is True
    assert result["audit"]["text_available"] is True
    assert result["audit"]["missing"] is True


def test_xml_still_wins_over_the_pdf(tmp_path):
    """The XML carries the real grid; the PDF text is the last resort.

    The PDF is given a cache so its text is genuinely available. Without one
    this test still passed, but vacuously -- "From pdf." was absent because
    nothing could read the PDF at all, not because the XML won.
    """
    paper = tmp_path / "p"
    paper.mkdir()
    (paper / "p.xml").write_text(
        "<article><body><sec><p>From xml.</p></sec></body></article>",
        encoding="utf-8",
    )
    _extracted(_pdf(paper / "p.pdf", "From pdf."), "From pdf.")
    text = paper_text(paper)
    assert "From xml." in text and "From pdf." not in text


def test_find_pdf_prefers_the_stem_matching_the_directory(tmp_path):
    from metascience_agent.extraction.jats import find_pdf
    paper = tmp_path / "10.1234--x"
    paper.mkdir()
    _pdf(paper / "other.pdf")
    _pdf(paper / "10.1234--x.pdf")
    assert find_pdf(paper).name == "10.1234--x.pdf"


def test_find_pdf_skips_a_supplement(tmp_path):
    """Reading an appendix as though it were the paper would let the gate find
    its own citations inside it and clear itself."""
    from metascience_agent.extraction.jats import find_pdf
    paper = tmp_path / "p"
    paper.mkdir()
    _pdf(paper / "p_supplementary.pdf")
    assert find_pdf(paper) is None


def test_an_unreadable_pdf_yields_no_text_rather_than_raising(tmp_path):
    """And "" must be read as UNKNOWN -- `supplements.audit` fails closed on it
    for exactly this reason.

    The mechanism moved with the docling-only change: nothing opens these bytes
    any more, so the "" comes from the cache-only read rather than from a
    parser giving up on them. What must not change is that a file we cannot
    turn into text ends as a refusal a caller can act on, and never as an
    exception thrown out of a read path that runs on every paper.
    """
    paper = tmp_path / "p"
    paper.mkdir()
    (paper / "p.pdf").write_bytes(b"%PDF-1.4 not really")
    with pytest.warns(UserWarning, match="extract-tables"):
        assert paper_text(paper) == ""


# ---------------------------------------------------------------------------
# Superscripts: raised, except where raising them would invent a number
# ---------------------------------------------------------------------------

def test_a_unit_exponent_is_raised_not_flattened():
    """`kg/m2` reads as a number 2 beside the unit; `kg/m²` does not."""
    assert _cell_text(ET.fromstring("<td>kg/m<sup>2</sup></td>")) == "kg/m²"


def test_a_footnote_marker_stops_welding_itself_to_the_label():
    got = _cell_text(ET.fromstring("<td>Serious adverse event<sup>1</sup></td>"))
    assert got.endswith("¹")
    assert "event1" not in got


def test_an_exponent_keeps_the_caret_because_unicode_would_invent_a_value():
    """`10^-3` refuses to parse. `10⁻³` parses to 10 -- the paper printed
    0.001, so the Unicode form would manufacture a number 10,000 times too
    large. Refusing is the honest answer."""
    from metascience_agent.tools.tableparse import parse_cell as _tp
    assert _cell_text(ET.fromstring("<td>10<sup>-3</sup></td>")) == "10^-3"
    assert _tp("10^-3")["value"] is None
    assert _tp("10⁻³")["value"] == 10.0, "which is why the caret is kept"


def test_a_marker_unicode_cannot_raise_is_left_alone_rather_than_half_raised():
    """There is no superscript asterisk, and `*ᵃ` would be worse than `*a`."""
    assert _cell_text(ET.fromstring("<td>12.3<sup>*</sup></td>")) == "12.3*"
    assert _cell_text(ET.fromstring("<td>12.3<sup>*a</sup></td>")) == "12.3*a"


def test_the_rewrite_is_counted_like_every_other_normalisation():
    from metascience_agent.extraction.jats import _Counter, _collect
    counts = _Counter()
    buf: list[str] = []
    _collect(ET.fromstring("<td>kg/m<sup>2</sup></td>"), buf, counts)
    assert counts["superscript_unicode"] == 1


def test_a_bare_comma_between_footnote_markers_is_not_an_exponent():
    """`Patel[22]<sup>,</sup><sup>c</sup>` rendered `Patel[22]^,c` because the
    numeric pattern `[\\d.,]+` matches a comma with no digit in it."""
    assert _cell_text(ET.fromstring("<td>x<sup>,</sup></td>")) == "x,"


# --- captions and structured abstracts reach the text ------------------------
#
# Both were lost the same way: the code that emitted them read only DIRECT
# children of a section, and publishers park floats and structured-abstract
# prose one level down. MEASURED 2026-08-22: 316 of 550 <fig> elements have a
# non-<sec> parent, and 114 of 195 papers' first <abstract> has no direct <p>.

_FLOATS_XML = """<article>
  <front><article-meta>
    <abstract><sec><title>Background</title>
      <p>Stroke burden is rising.</p></sec>
      <sec><title>Results</title><p>The mean was 3.53.</p></sec></abstract>
    <abstract abstract-type="key-points"><p>One key point.</p></abstract>
  </article-meta></front>
  <body><sec><title>Methods</title><p>We did things.</p></sec></body>
  <floats-group>
    <fig id="f1"><label>Figure 1</label>
      <caption><p>Acceptability curve, highlighting probability.</p></caption>
    </fig>
  </floats-group>
</article>"""


def _extract(tmp_path, xml_text):
    from metascience_agent.extraction.jats import extract_xml_text_with_tables
    p = tmp_path / "a.xml"
    p.write_text(xml_text, encoding="utf-8")
    return extract_xml_text_with_tables(p, tables="full", max_chars=2_000_000)


def test_a_figure_outside_any_section_still_reaches_the_text(tmp_path):
    text = _extract(tmp_path, _FLOATS_XML)["text"]
    assert "Acceptability curve, highlighting probability." in text
    assert "[Figure 1:" in text


def test_a_caption_is_emitted_once_not_twice(tmp_path):
    """The sweep must not repeat a figure a section already claimed."""
    xml = _FLOATS_XML.replace("<floats-group>", "<floats-group-unused>") \
                     .replace("</floats-group>", "</floats-group-unused>") \
                     .replace("<body><sec><title>Methods</title><p>We did things.</p></sec>",
                              "<body><sec><title>Methods</title><p>We did things.</p>"
                              "<fig id=\"f2\"><label>Figure 9</label>"
                              "<caption><p>Inside a section.</p></caption></fig></sec>")
    text = _extract(tmp_path, xml)["text"]
    assert text.count("Inside a section.") == 1


def test_a_structured_abstract_is_not_dropped(tmp_path):
    """Prose nested in <sec> used to leave the abstract empty, so `add()`
    discarded the section and the paper's headline claim with it."""
    text = _extract(tmp_path, _FLOATS_XML)["text"]
    assert "Stroke burden is rising." in text
    assert "The mean was 3.53." in text


def test_every_abstract_is_kept_and_labelled_by_type(tmp_path):
    """JAMA Network Open ships key-points, teaser and the abstract proper;
    taking `[0]` published whichever came first."""
    text = _extract(tmp_path, _FLOATS_XML)["text"]
    assert "One key point." in text
    assert "## Abstract (key-points)" in text
