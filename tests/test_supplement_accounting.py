"""Supplementary material is part of the paper's claims, so it is part of its
accounting.

`prepass.paper_tables` and `completeness._read_body` both read
`glob("*.xml")[0]` -- the main article, and nothing else. Every table and every
reported statistic in a supplementary file was therefore absent from the
completeness manifest, which is the worst shape a gap can take: those items were
not counted as unchecked, they were INVISIBLE, and the smaller denominator made
coverage look better than it was.

MEASURED when this was fixed, 2026-08-12:

    paper                                  before   after   supplement share
    10.1001--jamanetworkopen.2023.37679       474     757             37.4%
    10.1001--jamanetworkopen.2023.51752       586  13,367             95.6%
    10.1002--ajcp.70049                       166     241             31.1%

The middle row is not an extraction artifact: that paper's eAppendix is a 1.1 MB
PDF carrying 62 tables and 12,052 cells, checked by hand.

READABILITY IS NOW A STATED PRECONDITION, NOT AN ACCIDENT (2026-08-17). These
counts always assumed the supplements could be read; until now that was free,
because `extraction.pdf.extract_text_with_tables` fell back to pdfplumber
whenever the docling cache was missing or old. pdfplumber is gone (Greg,
2026-08-16: it "should never run *anywhere*"), so that function is cache-only
and the assumption has to be checked instead of inherited.

MEASURED on this fixture, 2026-08-17. Its eAppendix was cached at
`cache_schema: 2` -- 9 tables and 67,710 characters of text, but no per-page
split -- so `docling_tables.cache_status` returns

    (False, 'cached at schema 2, before per-page text existed, which
             `extract_pdf` needs')

and `extract_text_with_tables` reports `unreadable: True, num_pages: 0`. That
sends `supplements_read.extract_pdf_tables` down its scanned-document branch,
which renders and OCRs all 11 pages of a born-digital PDF. A run of this file
was killed at 12 minutes still inside that OCR; the two tests here that touch
no PDF finish in 17 s.

So `_manifest` now REFUSES rather than pays, and names the command that fixes
it. Asserting the counts above against an OCR reconstruction would be a hollow
pass: the numbers in the table were measured on the extracted document, and OCR
of the same file is a different document.

The property is unchanged and is the one in `_supplement_items`' docstring --
the count must never quietly absorb a document we failed to open. What changed
is where it is enforced: a supplement we cannot open now stops the test with a
reason, instead of being silently re-read by a lower-fidelity route.
"""

from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit import completeness as C

REPO = Path(__file__).resolve().parents[1]
WITH_SUPP = REPO / "tests/fixtures/papers/high_value_pdfs_to_run_on" / "10.1001--jamanetworkopen.2023.37679"


def _unextracted_supplements() -> list[str]:
    """Supplement PDFs this checkout cannot open, each with the reason why.

    Only PDFs are asked about. A .docx/.xlsx/.csv supplement is parsed directly
    by `supplements_read` with no layout model in the way, so its readability
    never depended on pdfplumber and does not depend on the cache now.
    """
    from forensic_metascience_ai_toolkit import supplements as _supp
    from forensic_metascience_ai_toolkit.extraction import docling_tables as _dl

    bad = []
    for name in _supp.present_files(WITH_SUPP) or []:
        p = WITH_SUPP / name
        if p.suffix.lower() != ".pdf":
            continue
        ok, why = _dl.cache_status(p)
        if not ok:
            bad.append(f"{p.name}: {why}")
    return bad


def _manifest():
    if not WITH_SUPP.exists():
        pytest.skip("paper with supplements not in this checkout")
    stale = _unextracted_supplements()
    if stale:
        # ACTIONABLE, because the alternative is a 12-minute OCR of a PDF that
        # has a perfectly good text layer. `--force` is required, not optional:
        # without it `extract-tables` treats a schema-2 entry as a hit and
        # leaves it exactly as it found it.
        pytest.skip(
            "supplement PDFs are not extracted, so these counts would be "
            "measured against an OCR reconstruction rather than the document. "
            f"Run `metascience extract-tables {WITH_SUPP} --force`. "
            + "; ".join(stale))
    return C.build_manifest(WITH_SUPP)


class TestSupplementsAreCounted:
    def test_supplement_items_reach_the_manifest(self):
        m = _manifest()
        assert m["n_supplement_items"] > 0, (
            "a supplement is present and contributed nothing; the manifest is "
            "back to counting only the article")

    def test_the_counts_partition_the_total(self):
        m = _manifest()
        assert (m["n_table_items"] + m["n_body_items"]
                + m["n_supplement_items"]) == m["n_items"]

    def test_supplement_table_and_body_split_is_reported(self):
        m = _manifest()
        assert (m["n_supplement_table_items"] + m["n_supplement_body_items"]
                == m["n_supplement_items"])

    def test_an_item_names_the_file_it_came_from(self):
        m = _manifest()
        supp = [i for i in m["items"] if i["where"].startswith("supplement ")]
        assert supp
        # A reader must be able to tell eTable 3 from Table 3 of the article.
        assert all(len(i["where"].split()) >= 3 for i in supp)

    def test_ids_do_not_collide_with_the_article(self):
        m = _manifest()
        ids = [i["id"] for i in m["items"]]
        assert len(ids) == len(set(ids)), (
            "row 2 of 'Table 1' in a supplement must not share an id with row 2 "
            "of 'Table 1' in the paper")


class TestAnUnreadableSupplementIsRecordedNotDropped:
    """"Present but unreadable" and "not provided" are different facts about a
    paper. Silently skipping the first rebuilds the invisibility this fix
    removed, one level down."""

    def test_a_failure_to_enumerate_is_a_problem_not_a_silence(self, monkeypatch):
        problems = []
        monkeypatch.setattr(
            "forensic_metascience_ai_toolkit.supplements.present_files",
            lambda *_a, **_k: (_ for _ in ()).throw(OSError("disk gone")))
        out = C._supplement_items(Path("."), problems)
        assert out == []
        assert problems and "NO supplement item is counted" in problems[0]
        assert "our failure" in problems[0]

    def test_an_unreadable_file_says_so_and_yields_nothing(self, monkeypatch):
        problems = []
        monkeypatch.setattr("forensic_metascience_ai_toolkit.supplements.present_files",
                            lambda *_a, **_k: ["broken.pdf"])
        monkeypatch.setattr(
            "forensic_metascience_ai_toolkit.extraction.supplements_read.extract_supplement_full",
            lambda *_a, **_k: {"error": "unsupported format"})
        out = C._supplement_items(Path("."), problems)
        assert out == []
        assert any("present but unreadable" in p for p in problems)
        assert any("absent from this manifest" in p for p in problems)
