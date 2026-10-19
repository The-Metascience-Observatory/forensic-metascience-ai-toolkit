"""Landscape tables: the text must come back READABLE, not mirrored.

WHAT THIS USED TO TEST, and why it is not deleted. Under pdfplumber the text of
a landscape page came back MIRRORED rather than missing, which is worse: a
caller sees plausible characters and cannot tell they are reversed. Page 23 of
`10.1002--eat.24415` began `nosreP-neewteB` -- "Between-Person" backwards -- and
the model reading it noticed only because it also had the XML to compare
against. `page.rotation` was 0 on every page of that document, because the
rotation lives in each glyph's text matrix rather than the page's `/Rotate`
key, so the obvious check saw nothing wrong.

The machinery that answered it -- `page_is_sideways`, `_uprighted`, and a
`grid_unreliable` caveat stamped on anything it touched -- is GONE, along with
pdfplumber itself (Greg, 2026-08-16: it "should never run *anywhere*").

THE PROPERTY SURVIVES THE MECHANISM. What mattered was never "we detect
rotation"; it was "a rotated page's content reaches the reader intact". Docling
handles rotation natively -- MEASURED on this document, 12/12 distinctive words
from each of the five landscape pages present, full verbatim lines surviving at
12/15 and 13/16 on the two table-heavy ones -- so these tests now assert the
outcome directly, and would fail just as loudly if a future extractor started
mirroring text again.
"""
from pathlib import Path

import pytest

from metascience_agent.extraction.pdf import extract_text_with_tables

PDF = Path("tests/fixtures/papers/high_value_pdfs_to_run_on/10.1002--eat.24415/10.1002--eat.24415.pdf")
CACHE = PDF.parent / ".extraction_cache"

#: pdfplumber called these five sideways. They are where this paper's tables are.
LANDSCAPE_PAGES = (20, 21, 22, 23, 24)

pytestmark = pytest.mark.skipif(
    not PDF.exists() or not CACHE.is_dir(),
    reason="corpus PDF not extracted (run `metascience extract-tables`)",
)


@pytest.fixture(scope="module")
def extracted():
    return extract_text_with_tables(PDF, max_chars=1_000_000)


class TestTheRotatedPagesAreRead:
    def test_every_page_is_present(self, extracted):
        """A rotated page must not go missing. The old failure mode was worse
        than absence, but absence is what a reroute is likeliest to cause."""
        assert extracted["num_pages"] == 24
        got = {p["page_num"] for p in extracted["pages"]}
        assert set(LANDSCAPE_PAGES) <= got

    def test_the_tables_on_them_are_found(self, extracted):
        """All four of this paper's tables sit on landscape pages. Under the old
        extractor the ruled pass returned zero for every one of pages 20-24, and
        only a text-alignment fallback reached them at all."""
        pages_with_tables = {t.get("page") for t in extracted["tables"]}
        assert pages_with_tables, "no tables found at all"
        assert pages_with_tables <= set(LANDSCAPE_PAGES), (
            f"tables reported on non-landscape pages: {pages_with_tables}")
        assert len(extracted["tables"]) >= 4

    def test_the_text_is_not_mirrored(self, extracted):
        """The original defect, asserted directly. `nosreP-neewteB` is what a
        mirrored read of "Between-Person" looks like; a reversed run of letters
        that long is the signature."""
        text = extracted["text"]
        assert "nosreP" not in text
        assert "neewteB" not in text
        assert "Between" in text or "between" in text

    def test_the_document_is_not_reported_unreadable(self, extracted):
        """A 24-page paper coming back `unreadable` is our extraction failing,
        recorded as a property of the paper. That happened during the reroute,
        from a cache written before per-page text existed."""
        assert extracted["unreadable"] is False
        assert extracted["text_extractor"] == "docling"


class TestPageSlicingStillWorks:
    def test_a_landscape_range_can_be_requested(self):
        r = extract_text_with_tables(PDF, first_page=20, last_page=22)
        assert [p["page_num"] for p in r["pages"]] == [20, 21, 22]
        assert r["pages_extracted"] == [20, 22]
