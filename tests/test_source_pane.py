"""The Source & extraction pane showed a wall of pipe characters by default,
could not sync from the rendered view at all, showed no tables, and rendered
only the first of a package's PDFs.

The pane exists to answer one question: did the extraction survive? Every
defect here is that question being answered badly or not at all.

- The rendered view is what answers it, and it was hidden behind a dropdown.
- Both directions of click-to-jump are character-offset arithmetic over
  `pre.textContent`. Rendering markdown destroys those offsets, so the rendered
  view could not participate and clicking in it did nothing. Each block now
  carries the offset it started at.
- The strip showed figures only, so on a paper with no figures it said "nothing
  was seen" while three correctly extracted grids sat unmentioned.
- `pdfs[0]` alone was rendered, and pages were addressed by a flat `pg{n}`, so
  a second document's page 1 would have collided with the paper's.
"""
from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit.bundle import (
    _blocks,
    _body_html,
    _ordered_pdfs,
    _table_records,
    render_all_pdfs,
)

def _has_paper_files(d) -> bool:
    """Is this a real paper directory, or a leftover shell?

    `d.exists()` is NOT the question. The corpus was removed from the repo on
    2026-08-09, but a working tree can still hold the DIRECTORY -- run outputs
    and `figures/` are written inside it and survive as untracked files -- while
    the PDF and XML the test actually reads are gone. Gating on the directory
    let the test run against an empty shell and FAIL, which is the same
    absence-read-as-presence mistake the toolkit polices in its own checks,
    appearing here in the harness.

    A suite that is red by default on every machine without the corpus teaches
    people to ignore it, so gate on the artefact rather than the folder.
    """
    return d.is_dir() and (any(d.glob("*.pdf")) or any(d.glob("*.xml")))


CORPUS = Path("tests/fixtures/papers/high_value_pdfs_to_run_on")
PAPER = CORPUS / "10.1002--mpr.70006"


class TestBlockOffsets:
    def test_each_block_reports_where_it_starts(self):
        text = "First para.\n\nSecond para.\n\nThird."
        got = _blocks(text)
        assert [t for _, t in got] == ["First para.", "Second para.", "Third."]
        for start, chunk in got:
            assert text[start:start + len(chunk)] == chunk

    def test_blank_blocks_are_dropped_without_shifting_the_rest(self):
        text = "One.\n\n\n\nTwo."
        got = _blocks(text)
        assert len(got) == 2
        for start, chunk in got:
            assert text[start:start + len(chunk)] == chunk

    def test_an_empty_document_yields_no_blocks(self):
        assert _blocks("") == []
        assert _blocks("   \n\n  ") == []

    def test_a_repeated_block_is_not_collapsed_onto_one_offset(self):
        """`str.find` from position 0 would give both copies the same offset,
        and every click on the second would jump to the first."""
        text = "Same.\n\nSame.\n\nDifferent."
        got = _blocks(text)
        assert len(got) == 3
        assert got[0][0] != got[1][0]


class TestBodyHtmlCarriesOffsets:
    def test_every_block_is_stamped(self, tmp_path):
        html = _body_html(tmp_path, "Alpha para.\n\nBeta para.")
        assert html.count("data-src-offset") == 2

    def test_the_offset_points_into_the_RAW_text_not_the_spliced_one(self, tmp_path):
        """The splice replaces a one-line placeholder with a whole grid. An
        offset computed after it would point into a document the raw pane is
        not showing."""
        text = "Intro para.\n\nSecond para is longer than the first one."
        html = _body_html(tmp_path, text)
        offsets = [int(s.split('"')[0])
                   for s in html.split('data-src-offset="')[1:]]
        assert offsets == [0, text.index("Second para")]

    def test_offsets_are_monotonic(self, tmp_path):
        html = _body_html(tmp_path, "\n\n".join(f"Para {i} of the body." for i in range(6)))
        offsets = [int(s.split('"')[0])
                   for s in html.split('data-src-offset="')[1:]]
        assert offsets == sorted(offsets)

    @pytest.mark.skipif(not _has_paper_files(PAPER), reason="corpus not present")
    def test_on_a_real_paper_every_offset_lands_inside_the_text(self):
        from forensic_metascience_ai_toolkit.extraction.jats import paper_text

        text = paper_text(PAPER)
        html = _body_html(PAPER, text)
        offsets = [int(s.split('"')[0])
                   for s in html.split('data-src-offset="')[1:]]
        assert len(offsets) > 20
        assert all(0 <= o < len(text) for o in offsets)


@pytest.mark.skipif(not _has_paper_files(PAPER), reason="corpus not present")
class TestTableRecords:
    def test_the_tables_reach_the_strip(self):
        got = _table_records(PAPER)
        assert len(got) == 3
        assert {r["label"] for r in got} == {"TABLE 1", "TABLE 2", "TABLE 3"}

    def test_each_card_carries_what_a_reader_needs_to_judge_extraction(self):
        for r in _table_records(PAPER):
            assert r["n_rows"] and r["width"]
            assert r["preview"], "a card with no cells shows nothing"

    def test_a_big_grid_is_trimmed_and_says_so(self):
        """40x7 in a 320px card is unreadable; the full grid is a click away."""
        big = next(r for r in _table_records(PAPER) if r["n_rows"] > 14)
        assert big["clipped"] is True
        assert len(big["preview"]) <= 14

    def test_a_paper_with_no_xml_returns_nothing_rather_than_raising(self, tmp_path):
        assert _table_records(tmp_path) == []


class TestMultipleDocuments:
    def test_the_paper_sorts_first_even_when_alphabetically_later(self, tmp_path):
        """Findings anchor to document 0, so this ordering is load-bearing."""
        paper = tmp_path / "10.1002--zzz"
        paper.mkdir()
        (paper / "10.1002--zzz.pdf").write_bytes(b"%PDF-1.4\n")
        (paper / "appendix_a.pdf").write_bytes(b"%PDF-1.4\n")
        assert [p.name for p in _ordered_pdfs(paper)] == [
            "10.1002--zzz.pdf", "appendix_a.pdf"]

    def test_no_pdfs_is_not_an_error(self, tmp_path):
        assert _ordered_pdfs(tmp_path) == []
        assert render_all_pdfs([], tmp_path) == ([], [])

    @pytest.mark.skipif(not _has_paper_files(PAPER), reason="corpus not present")
    def test_each_document_gets_its_own_page_directory_and_id(self, tmp_path):
        pdfs = [PAPER / "10.1002--mpr.70006.pdf",
                CORPUS / "10.1002--hbm.26595" / "10.1002--hbm.26595.pdf"]
        pages, docs = render_all_pdfs(pdfs, tmp_path)
        assert [d["id"] for d in docs] == [0, 1]
        assert {p["doc"] for p in pages} == {0, 1}
        # Page 1 exists in both, and their images must not be the same file.
        first = {p["doc"]: p["img"] for p in pages if p["page"] == 1}
        assert first[0] != first[1]
        assert (tmp_path / "pages" / "1").is_dir()

    @pytest.mark.skipif(not _has_paper_files(PAPER), reason="corpus not present")
    def test_the_page_budget_is_reported_rather_than_silently_applied(self, tmp_path):
        """A reader seeing 3 of 14 pages must know the other 11 exist."""
        import forensic_metascience_ai_toolkit.bundle as B

        original = B._MAX_RENDERED_PAGES
        try:
            B._MAX_RENDERED_PAGES = 3
            _, docs = render_all_pdfs([PAPER / "10.1002--mpr.70006.pdf"], tmp_path)
        finally:
            B._MAX_RENDERED_PAGES = original
        assert docs[0]["pages"] == 3
        assert docs[0]["total_pages"] == 14
        assert docs[0]["truncated"] is True

    @pytest.mark.skipif(not _has_paper_files(PAPER), reason="corpus not present")
    def test_a_document_past_the_budget_is_still_declared(self, tmp_path):
        """It used to `break`, so a document past the budget vanished from the
        selector -- indistinguishable from one the package never contained."""
        import forensic_metascience_ai_toolkit.bundle as B

        pdfs = [PAPER / "10.1002--mpr.70006.pdf",
                CORPUS / "10.1002--hbm.26595" / "10.1002--hbm.26595.pdf"]
        original = B._MAX_RENDERED_PAGES
        try:
            B._MAX_RENDERED_PAGES = 2
            _, docs = render_all_pdfs(pdfs, tmp_path)
        finally:
            B._MAX_RENDERED_PAGES = original
        assert len(docs) == 2, "the second document must still be declared"
        assert docs[1]["pages"] == 0
        assert docs[1]["total_pages"] > 0
        assert docs[1]["truncated"] is True


IMAGE_TABLE_PAPER = CORPUS / "10.1186--s40352-024-00261-0"


@pytest.mark.skipif(not _has_paper_files(IMAGE_TABLE_PAPER), reason="corpus not present")
class TestATableThatIsAPicture:
    """Some publishers ship a table as an IMAGE. It has no cells, no check can
    reach a number in it, and rendering it as an empty grid is the worst
    available answer -- it reads as an extraction that failed rather than as a
    table nothing could ever check. Found at corpus scale, not in the sample.
    """

    def test_the_record_says_it_is_an_image(self):
        recs = {r["label"]: r for r in _table_records(IMAGE_TABLE_PAPER)}
        assert recs["Table 2."]["image_only"] is True
        assert recs["Table 2."]["preview"] == []

    def test_the_extractor_s_warning_is_carried_to_the_reader(self):
        recs = {r["label"]: r for r in _table_records(IMAGE_TABLE_PAPER)}
        assert any("image" in w for w in recs["Table 2."]["warnings"])

    def test_its_neighbours_still_come_back_with_cells(self):
        """The picture must not take the readable tables down with it."""
        recs = {r["label"]: r for r in _table_records(IMAGE_TABLE_PAPER)}
        assert recs["Table 1"]["preview"]
        assert recs["Table 3"]["preview"]

    def test_the_viewer_says_no_check_could_reach_it(self):
        from forensic_metascience_ai_toolkit.bundle import render_viewer
        html = render_viewer({"table_records": _table_records(IMAGE_TABLE_PAPER)})
        assert "This table is a PICTURE in the publisher XML" in html
        assert "reach a single number in it" in html
