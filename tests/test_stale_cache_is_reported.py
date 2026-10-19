"""A cheap cache-only read must SAY it is reading pre-fix data.

`agent.ensure_paper_extracted` asks `docling_tables.cache_status` and
re-extracts anything cached below schema 5 -- that guard is correct and has
been there the whole time. But the cache-only walk that `values.build_from_paper`
uses skips the pre-flight entirely, by design: it is the fast path, and paying
docling's 24-140 s per file to rebuild a register would make measurement
unaffordable.

MEASURED 2026-08-20, and this is why the test exists. Every register figure
reported for PDF supplements that day was computed from caches written at
17:41 on 2026-08-19 -- 94 minutes BEFORE `cbf197f` taught docling to read its
own `column_header` flags. The numbers looked current and were not. Refreshing
the five supplements moved duplicate-labelled columns from 32.7% to 18.6% and
stacked headers detected from 0 to 15.

Reading a stale cache is legitimate. Returning its numbers with no indication
that they predate the fix is the absence-as-knowledge failure this codebase
exists to prevent, pointed at its own cache.
"""
import pathlib
import pytest

from metascience_agent import prepass

CORPUS = pathlib.Path("tests/fixtures/papers/high_value_pdfs_to_run_on")


class TestTheWalkerNamesAStaleCache:
    def test_a_stale_cache_is_reported_as_a_problem(self, tmp_path):
        """A schema-4 entry beside a PDF must produce a named problem."""
        import json
        pdf = tmp_path / "10.1234--x.pdf"
        pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
        from metascience_agent.extraction import docling_tables as dl
        cache = tmp_path / dl.CACHE_DIRNAME
        cache.mkdir()
        (cache / f"{pdf.stem}.{dl._digest(pdf)}.tables.json").write_text(
            json.dumps({"cache_schema": 4, "text": "x", "pages": [{"text": "x"}],
                        "tables": []}), encoding="utf-8")
        found = prepass.paper_tables(tmp_path, include_supplements=True)
        problems = list(getattr(found, "problems", None) or [])
        assert any("schema" in p.lower() for p in problems), (
            f"a pre-fix cache must be named, got {problems}")

    def test_the_problem_says_what_is_wrong_with_it(self, tmp_path):
        """Naming the file is not enough -- the reader needs the consequence."""
        import json
        pdf = tmp_path / "10.1234--y.pdf"
        pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
        from metascience_agent.extraction import docling_tables as dl
        cache = tmp_path / dl.CACHE_DIRNAME
        cache.mkdir()
        (cache / f"{pdf.stem}.{dl._digest(pdf)}.tables.json").write_text(
            json.dumps({"cache_schema": 4, "text": "x", "pages": [{"text": "x"}],
                        "tables": []}), encoding="utf-8")
        found = prepass.paper_tables(tmp_path, include_supplements=True)
        joined = " ".join(getattr(found, "problems", None) or [])
        assert "header depth" in joined or "column label" in joined

    @pytest.mark.skipif(not CORPUS.is_dir(), reason="corpus not in this checkout")
    def test_a_fresh_corpus_paper_reports_nothing(self):
        """The guard must stay quiet when the cache IS current, or it becomes
        noise every caller learns to ignore."""
        d = CORPUS / "10.1001--jamanetworkopen.2023.37679"
        if not d.is_dir():
            pytest.skip("paper not present")
        found = prepass.paper_tables(d, include_supplements=True)
        stale = [p for p in (getattr(found, "problems", None) or [])
                 if "schema" in p.lower()]
        assert not stale, f"this paper was re-extracted at schema 5: {stale}"
