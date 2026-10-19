"""An extractor must not invent tables out of running prose.

WHAT THIS USED TO TEST. pdfplumber's text-alignment fallback
(`vertical_strategy="text"`) infers columns from where words happen to line up,
so it never fails and returns something for anything. On
`10.1007--s00702-004-0248-2`, a fourteen-page paper, it produced TWELVE
"tables" -- one per page, the first being the title page, every one a single
column of running text. A gate (`_looks_tabular`, `_tabularity`) was built to
reject those on two measurements: numeric fraction separates a table from
prose, and cell LENGTH separates a table from a reference list, which is also
full of numbers.

THE GATE IS GONE, with pdfplumber and the fallback that needed it. Docling
reads ruled structure rather than guessing columns from alignment, so there is
no candidate to gate. The tests that exercised the gate's internals on
synthetic grids went with it; they described a mechanism that no longer exists.

THE PREMISE WAS WRONG, and fixing it is most of this file (2026-08-17).
This file called `10.1007--s00702-004-0248-2` a "prose paper" and asserted it
yields ZERO tables. It is not a prose paper. It declares, captions and cites
`Table 1. Selected demographic data and baseline disease characteristics` and
`Table 2. Patients with serious adverse events`, and docling reads both:
14 rows on page 6, 7 rows on page 9, 32 cells between them, with the numbers
you would expect (`Male 47 (60.3) / 38 (55.9)`, `All SAEs (deaths) 6 (6) /
7 (6)`). Twelve was wrong; zero is also wrong. Two is right.

The false premise survived because it was never actually exercised: this
paper's extraction cache was written by an older schema that stored TABLES
ONLY and no body text, so `extract_text_with_tables` reported it unreadable,
unreadable yields no tables, and "no tables were invented" passed VACUOUSLY.
The companion assertion -- that the paper is not reported unreadable -- is what
failed and exposed it. A skip guard that only checks the cache DIRECTORY exists
is what let a stale cache masquerade as a measurement, so `_extracted` now asks
`cache_status` whether the entry is USABLE.

WHAT SURVIVES is the property those internals served, and it is the one that
matters: the tables reported must be the tables the paper HAS. Inventing one
per page out of prose is the failure this file was built for, and asserting
against the invention SIGNATURE -- single-column grids of long running text --
keeps that property while letting the paper have the two tables it really has.
A forensic finding about a table that does not exist is among the worst outputs
this toolkit can produce, so this stays regardless of which extractor is
underneath.
"""
from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit.extraction.docling_tables import cache_status
from forensic_metascience_ai_toolkit.extraction.pdf import extract_text_with_tables

# Two real tables, on pages 6 and 9. Named for the defect it caught, not for a
# property of the paper -- see the module docstring on why "PROSE" was a lie.
TWO_TABLES = Path(
    "tests/fixtures/papers/cerebrolysin_papers/10.1007--s00702-004-0248-2/"
    "10.1007--s00702-004-0248-2.pdf"
)
LANDSCAPE = Path("tests/fixtures/papers/high_value_pdfs_to_run_on/10.1002--eat.24415/10.1002--eat.24415.pdf")


def _extracted(pdf: Path):
    """Skip unless the cache is USABLE, not merely present.

    Reads are cache-only now, so an unextracted or stale-schema paper returns
    `unreadable` -- and every "we found no bad tables" assertion below passes
    trivially against it. That is how a false premise sat here undetected. The
    skip names the command that fixes it; `cache_status` is the same usability
    test `analyze`'s pre-flight uses, so the two cannot drift.
    """
    if not pdf.exists():
        pytest.skip(f"{pdf.name} not present")
    usable, why_not = cache_status(pdf)
    if not usable:
        pytest.skip(
            f"{pdf.name} has no usable extraction ({why_not}); "
            f"run `metascience extract-tables --force {pdf.parent}`")
    return extract_text_with_tables(pdf, max_chars=1_000_000)


class TestTheTablesReportedAreTheTablesThePaperHas:
    """The fourteen-page paper that produced twelve tables. It has two."""

    def test_the_paper_is_not_reported_unreadable(self):
        """Returning no tables must mean "this paper has none", not "we could
        not read it". The two are opposite facts and the old extractor returned
        the same value for both. This is the assertion that caught the vacuous
        pass above it, so it runs first."""
        result = _extracted(TWO_TABLES)
        assert result["unreadable"] is False
        assert len(result["text"]) > 1000

    def test_the_two_real_tables_are_found_and_no_more(self):
        """MEASURED: pages 6 and 9. Twelve was pdfplumber inventing one per
        page; zero was this file's own false premise, unmasked by a stale
        cache. The paper captions exactly Table 1 and Table 2."""
        result = _extracted(TWO_TABLES)
        withdata = [t for t in result["tables"] if t.get("data")]
        assert len(withdata) == 2, (
            f"{len(withdata)} table(s) on a paper that captions two: "
            f"pages {[t.get('page') for t in withdata]}")
        assert {t.get("page") for t in withdata} == {6, 9}

    def test_no_table_is_a_column_of_running_prose(self):
        """THE INVENTION SIGNATURE, asserted directly rather than via a table
        count. Every one of pdfplumber's twelve was a SINGLE column whose cells
        were sentences; a real table is multi-column with short cells. Checking
        the shape rather than the tally is what lets this paper hold its two
        genuine tables without reopening the door to twelve fake ones."""
        for t in _extracted(TWO_TABLES)["tables"]:
            rows = t.get("data") or []
            assert max((len(r) for r in rows), default=0) > 1, (
                f"single-column grid on page {t.get('page')}: running text "
                f"read as a table")
            cells = [str(c).strip() for r in rows for c in r if str(c).strip()]
            longest = max((len(c) for c in cells), default=0)
            assert longest < 200, (
                f"page {t.get('page')} has a {longest}-character cell: that is "
                f"a paragraph, not a table cell")

    def test_the_grids_carry_the_numbers_a_forensic_check_would_read(self):
        """A table found but emptied is worse than one not found: a check that
        reads it silently gets nothing. These are the values on the page."""
        flat = {str(c).strip()
                for t in _extracted(TWO_TABLES)["tables"]
                for r in (t.get("data") or []) for c in r}
        assert "47 (60.3)" in flat   # Table 1, male, treatment arm
        assert "6 (6)" in flat       # Table 2, all SAEs (deaths), treatment arm


class TestRealTablesStillSurvive:
    """The other half of the trade. A gate tuned to reject prose is worthless
    if it also rejects the tables a forensic check needs, and this paper's four
    tables all sit on pages pdfplumber could not read at all."""

    def test_the_table_pages_still_return_tables(self):
        result = _extracted(LANDSCAPE)
        assert len(result["tables"]) >= 4
        assert {t.get("page") for t in result["tables"]} <= {20, 21, 22, 23, 24}

    def test_the_grids_carry_real_cells(self):
        """A table entry with an empty grid is a header we found and a body we
        did not, which is worse than reporting nothing."""
        result = _extracted(LANDSCAPE)
        for t in result["tables"]:
            assert t.get("data"), f"table on page {t.get('page')} has no rows"
            assert any(any(str(c).strip() for c in row) for row in t["data"])

    def test_the_strategy_is_recorded(self):
        """A consumer assembling a (mean, SD, n) triple out of a grid needs to
        know whether the columns were READ or INFERRED. Docling reads them; the
        field says so rather than leaving it to be assumed."""
        result = _extracted(LANDSCAPE)
        assert all(t.get("strategy") == "docling" for t in result["tables"])
