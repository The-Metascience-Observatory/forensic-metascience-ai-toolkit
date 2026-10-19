"""Locators: a missing place is none, never page 1."""
from pathlib import Path

from metascience_agent.locators import (
    _locate, _locate_in_sections, candidates_for_issue, locate_issue,
    locators_for_paper, quoted_fragments,
)


def test_prose_quote_is_found_in_the_pdf_text():
    pages = ["", "the sample began with 68 pennsylvania and missouri coalitions", ""]
    got = _locate("The sample began with 68 Pennsylvania and Missouri coalitions",
                  pages, "")
    assert got["page"] == 2
    assert got["method"] == "quote_verbatim"


def test_empty_quote_is_not_page_one():
    assert _locate("", ["hello on page one"], "") == {}


def test_no_match_is_not_page_one():
    assert "page" not in _locate("zzz no such quote", ["hello"], "")


def test_xml_section_is_not_a_page():
    sections = [
        {"page_num": 1, "section": "Intro", "text": "background only"},
        {"page_num": 2, "section": "Results",
         "text": "the mean was 14.46 with n = 49"},
    ]
    got = _locate_in_sections("mean was 14.46 with n = 49", sections)
    assert got["section"] == "Results"
    assert got["section_index"] == 2
    assert "page" not in got


def test_image_without_placement_is_none():
    loc = locate_issue(
        {"id": "image:IMGDUP-1", "kind": "image",
         "extras": {"panels": ["p1"], "placements": {}}},
        Path("/no/such"),
        panel_boxes={},
    )
    assert loc["confidence"] == "none"
    assert loc["page"] is None


def test_image_bbox_is_bbox_confidence(tmp_path):
    loc = locate_issue(
        {"id": "image:IMGDUP-1", "kind": "image",
         "extras": {"panels": ["u1"], "placements": {}}},
        tmp_path,
        panel_boxes={"u1": [{"page": 4, "bbox": [10.0, 20.0, 30.0, 40.0]}]},
    )
    assert loc["confidence"] == "bbox"
    assert loc["page"] == 4
    assert loc["boxes"][0]["x0"] == 10.0


def test_image_two_pages_are_two_targets(tmp_path):
    loc = locate_issue(
        {"id": "image:IMGDUP-1", "kind": "image",
         "extras": {
             "panels": ["u1", "u2"],
             "placements": {
                 "u1": [{"page": 5, "bbox": [10.0, 20.0, 30.0, 40.0],
                         "figure_label": "Figure 2"}],
                 "u2": [{"page": 17, "bbox": [11.0, 21.0, 31.0, 41.0],
                         "figure_label": "Figure 2"}],
             },
         }},
        tmp_path,
    )
    pages = [t["page"] for t in loc["targets"]]
    assert pages == [5, 17]
    assert [t["label"] for t in loc["targets"]] == ["p. 5", "p. 17"]
    assert loc["targets"][0]["id"] == "image:IMGDUP-1:page:5"
    assert loc["targets"][1]["id"] == "image:IMGDUP-1:page:17"
    assert loc["page"] == 5
    assert loc["confidence"] == "bbox"
    assert {b["page"] for b in loc["boxes"]} == {5, 17}


def test_image_page_without_bbox_is_not_page_one(tmp_path):
    loc = locate_issue(
        {"id": "image:IMGDUP-1", "kind": "image",
         "extras": {
             "panels": ["u1"],
             "placements": {"u1": [{"page": 17, "figure_label": "Figure 2"}]},
         }},
        tmp_path,
    )
    assert loc["page"] == 17
    assert loc["confidence"] == "page"
    assert loc["targets"][0]["page"] == 17
    assert loc["targets"][0]["boxes"] == []


def test_locators_for_paper_without_pdf_or_xml(tmp_path):
    paper = tmp_path / "p"
    paper.mkdir()
    got = locators_for_paper(paper, [{"id": "numeric:1", "kind": "numeric",
                                      "quote": "anything"}])
    assert got["has_pdf"] is False
    assert got["locators"][0]["confidence"] == "none"
    assert got["locators"][0]["page"] is None


def test_supplement_pdf_is_located_in_that_file_not_the_article(tmp_path):
    """A finding about SI.pdf must not be searched in the main article PDF."""
    paper = tmp_path / "p"
    paper.mkdir()
    try:
        import fitz
    except ImportError:
        import pytest
        pytest.skip("PyMuPDF not installed")
    main = fitz.open()
    page = main.new_page()
    page.insert_text((72, 72), "this is the article body")
    main.save(paper / f"{paper.name}.pdf")
    main.close()
    si = fitz.open()
    page = si.new_page()
    page.insert_text((72, 72), "supplement table mean 14.46 n = 49")
    si.save(paper / "SI.pdf")
    si.close()
    got = locators_for_paper(paper, [{
        "id": "numeric:1",
        "kind": "numeric",
        "quote": "supplement table mean 14.46 n = 49",
        "artefacts": [{
            "kind": "pdf", "found": True,
            "relpath": "SI.pdf", "basename": "SI.pdf",
        }],
    }])
    loc = got["locators"][0]
    assert loc.get("file") == "SI.pdf"
    assert loc["page"] == 1
    assert loc["confidence"] in ("exact", "page")


def test_quoted_fragments_ignore_short_tokens():
    text = ("Abstract: 'QALY'. Results: 'a mean increment in QALYs between "
            "0.01-0.015, depending on the valuation technique (Table 2)'. "
            "Discussion: 'Aggregated QALYs for the Cerebrolysin group were "
            "higher than those for the placebo group (0.051 average difference "
            "across the three health state valuation models)'.")
    frags = quoted_fragments(text)
    assert len(frags) == 2
    assert any("0.01-0.015" in f for f in frags)
    assert any("0.051" in f for f in frags)
    assert not any(f == "QALY" for f in frags)


def test_possessive_apostrophe_is_not_a_quoted_fragment():
    text = ("n = 193 in the final analytic sample (100 Cerebrolysin, "
            "93 placebo), each row presumed an independent patient's "
            "SF-36-derived utility and QALY values.")
    assert quoted_fragments(text) == []


def test_candidates_prefer_passages_over_prose():
    issue = {
        "quote": "ignored whole paragraph",
        "reported": "also ignored",
        "passages": [
            {"id": "a", "quote": "first verbatim span of eight words or more here",
             "label": "Abstract"},
            {"id": "b", "quote": "second verbatim span of eight words or more here",
             "label": "Table 2"},
        ],
    }
    cands = candidates_for_issue(issue)
    assert [c["id"] for c in cands] == ["a", "b"]
    assert cands[0]["label"] == "Abstract"


def test_candidates_do_not_split_on_vs():
    issue = {"quote": "Results say 0.013 vs Discussion 0.051 without quotes"}
    cands = candidates_for_issue(issue)
    assert len(cands) == 1
    assert "vs" in cands[0]["quote"]


def test_two_quotes_become_two_xml_targets(tmp_path):
    paper = tmp_path / "p"
    paper.mkdir()
    sections = [
        {"page_num": 1, "section": "Results",
         "text": "a mean increment in QALYs between 0.01-0.015, depending on the valuation technique"},
        {"page_num": 3, "section": "Discussion",
         "text": "Aggregated QALYs for the Cerebrolysin group were higher than those for the placebo group (0.051 average difference across the three health state valuation models)"},
    ]
    loc = locate_issue(
        {"id": "numeric:1", "kind": "numeric",
         "reported": (
             "Results: 'a mean increment in QALYs between 0.01-0.015, "
             "depending on the valuation technique'. Discussion: "
             "'Aggregated QALYs for the Cerebrolysin group were higher "
             "than those for the placebo group (0.051 average difference "
             "across the three health state valuation models)'.")},
        paper,
        sections=sections,
    )
    xmls = [t for t in loc["targets"] if t["kind"] == "xml_text"]
    assert len(xmls) == 2
    assert {t["confidence"] for t in xmls} == {"exact"}
    assert {t["section_index"] for t in xmls} == {1, 3}
    assert loc["page"] is None


def test_xml_numeric_tokens_are_not_a_highlight(tmp_path):
    loc = locate_issue(
        {"id": "numeric:1", "kind": "numeric",
         "quote": "values 14.46 and 49 together"},
        tmp_path,
        sections=[{"page_num": 2, "section": "Results",
                   "text": "the mean was 14.46 with n = 49"}],
    )
    xmls = [t for t in loc["targets"] if t["kind"] == "xml_text"]
    assert xmls
    assert xmls[0]["confidence"] == "section"
    assert xmls[0]["method"] == "numeric_tokens"


def test_sheet_cells_are_targets(tmp_path):
    loc = locate_issue(
        {"id": "numeric:1", "kind": "numeric", "quote": "",
         "artefacts": [{
             "kind": "xlsx", "found": True, "relpath": "cars.xlsx",
             "basename": "cars.xlsx", "sheet": "QALY",
             "cells": [{"sheet": "QALY", "row": 76, "col": 1}],
         }]},
        tmp_path,
    )
    sheets = [t for t in loc["targets"] if t["kind"] == "sheet_cell"]
    assert len(sheets) == 1
    assert sheets[0]["confidence"] == "exact"
    assert sheets[0]["cells"][0]["row"] == 76


def test_folded_xml_quote_hits_pdf_page():
    """An XML minus-sign quote must still find the PDF's ASCII hyphen page."""
    pages = ["intro", "the difference was -0.051 on the primary outcome scale"]
    got = _locate("the difference was −0.051 on the primary outcome scale",
                  [_fold_page(p) for p in pages], "")
    assert got.get("page") == 2
    assert got["method"] == "quote_verbatim"


def _fold_page(text):
    from metascience_agent.locators import _fold
    return _fold(text)


# --- a quote naming a table cell must anchor in the XML -----------------------
#
# Table text is never inlined into a section's `text` (that invariant is what
# stops a grid being poured into prose with its columns lost), so the grids
# live in `sec["tables"][i]["data"]`. Searching only `text` left every
# table-cell quote unanchorable in XML while it anchored fine against the PDF.
# MEASURED over 92 papers / 369 quotes: 247 exact -> 288.

def _sections_with_table():
    return [{
        "page_num": 3,
        "section": "Floats",
        "text": "[Table 2: Outcomes by group - 3 rows x 5 cols]",
        "tables": [{
            "table_num": 2,
            "data": [
                ["", "Baseline", "Week 12"],
                ["Group", "F (1.29) = 37.3", "F (1.29) = 24.8"],
                ["Placebo", "F (1.29) = 11.2", "F (1.29) = 9.4"],
            ],
        }],
    }]


def test_table_cell_quote_anchors_exactly_and_names_its_row():
    from metascience_agent.locators import _locate_in_sections
    got = _locate_in_sections(
        "| Group | F (1.29) = 37.3 | F (1.29) = 24.8 |", _sections_with_table())
    assert got["method"] == "table_verbatim"
    assert got["table_num"] == 2
    assert got["row_index"] == 1


def test_a_table_hit_is_labelled_by_its_table_not_by_Floats():
    """The containing section is often literally named "Floats"."""
    from metascience_agent.locators import _xml_target
    t = _xml_target(
        {"id": "f_1:a", "quote": "| Group | F (1.29) = 37.3 |", "label": ""},
        _sections_with_table())
    assert t["confidence"] == "exact"
    assert t["label"] == "Table 2"
    assert t["table_num"] == 2


def test_prose_wins_over_a_table_row_for_the_same_quote():
    from metascience_agent.locators import _locate_in_sections
    secs = _sections_with_table()
    secs.insert(0, {"page_num": 1, "section": "Results",
                    "text": "Group F (1.29) = 37.3 was observed.", "tables": []})
    got = _locate_in_sections("Group F (1.29) = 37.3", secs)
    assert got["method"] == "quote_verbatim"
    assert got["section"] == "Results"


def test_a_token_hit_on_two_rows_is_not_a_location():
    """Grids collide far more readily than prose: two candidate rows is a
    region, not a place, and a mark drawn on the wrong row is an accusation."""
    from metascience_agent.locators import _locate_in_sections
    secs = [{
        "page_num": 2, "section": "Floats", "text": "",
        "tables": [{"table_num": 1, "data": [
            ["arm", "12.5", "3.4"],
            ["other", "12.5", "3.4"],
        ]}],
    }]
    got = _locate_in_sections("values of 12.5 and 3.4 were seen", secs)
    assert got.get("table_num") is None


def test_a_unique_token_row_does_locate():
    from metascience_agent.locators import _locate_in_sections
    secs = [{
        "page_num": 2, "section": "Floats", "text": "",
        "tables": [{"table_num": 1, "data": [
            ["arm", "12.5", "3.4"],
            ["other", "99.9", "8.1"],
        ]}],
    }]
    got = _locate_in_sections("values of 12.5 and 3.4 were seen", secs)
    assert got["method"] == "table_numeric_tokens"
    assert got["row_index"] == 0


def test_one_quote_yields_one_candidate_with_a_unique_id():
    """A target id is `{cand_id}:xml`, so two candidates sharing an id mint two
    targets the viewer cannot tell apart. MEASURED: 101 of 260 issues carried
    the same quote twice under the same id."""
    from metascience_agent.locators import candidates_for_issue
    got = candidates_for_issue({"passages": [
        {"id": "a", "quote": "the mean was 3.53"},
        {"id": "a", "quote": "the  mean   was 3.53"},   # same, re-rendered
        {"id": "b", "quote": "the SD was 1.20"},
    ]})
    assert [c["quote"] for c in got] == ["the mean was 3.53", "the SD was 1.20"]
    assert len(set(c["id"] for c in got)) == len(got)


def test_two_passages_that_collide_on_id_but_not_on_quote_both_survive():
    from metascience_agent.locators import candidates_for_issue
    got = candidates_for_issue({"passages": [
        {"id": "a", "quote": "the mean was 3.53"},
        {"id": "a", "quote": "the SD was 1.20"},
    ]})
    assert len(got) == 2
    assert len(set(c["id"] for c in got)) == 2
