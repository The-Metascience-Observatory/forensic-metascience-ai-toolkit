"""Extraction happens ONCE, UP FRONT, and NEVER inside a read path.

WHY THIS FILE EXISTS. `extraction/pdf.py` is docling-only and cache-only, so
every read path REFUSES on a PDF nobody has extracted yet and names the command
that fixes it. That refusal is correct and it is also useless in two places:

  - halfway through a paid sweep, where it costs the run;
  - inside `supplements.gate`, where the empty text it produces is read back as
    `text_available: False` and the paper is refused with "no PDF text layer".
    That sentence is TRUE OF US AND FALSE OF THE PAPER -- OUR missing cache
    written down as a property of the publication, which is the one thing this
    project may never do.

So `analyze` fills the cache before either can happen. These tests pin the
three properties that makes it worth having, and the one that makes it safe.

THE COST OF GETTING THE LAST ONE WRONG IS MEASURED, three times over: wiring
extraction into `prepass.paper_tables` took the suite from 260 s to 596 s and
raced xdist workers into one cache file; invalidating the cache for a new field
took it to 27 minutes; re-extracting inside `extract_text_with_tables` took it
to 2h10m and collapsed a worker. `TestExtractionStaysOutOfReadPaths` is the
tripwire for the fourth attempt.
"""
import json
from pathlib import Path

import pytest

from metascience_agent import supplements
from metascience_agent.agent import _pdfs_to_extract, ensure_paper_extracted
from metascience_agent.extraction import docling_tables as dl

#: An article this repository ships already extracted. Used for the "a present
#: cache costs nothing" property, which needs a REAL cache entry -- a synthetic
#: one would only prove that a file exists where the code looks.
CACHED_PAPER = Path("eval/ground_truth/papers/10.3349--ymj.2009.50.1.55")


def _write_pdf(path: Path, body: bytes = b"%PDF-1.4\nnot really a pdf\n") -> Path:
    """A file that passes `supplements` magic-byte check and nothing further.

    Enough to be enumerated and declared; deliberately NOT enough for docling,
    which is why every test using it stubs the converter.
    """
    path.write_bytes(body)
    return path


class _ExplodingConverter:
    """Stands in for docling when the test needs the extractor to FAIL."""

    def convert(self, _path):
        raise RuntimeError("simulated docling failure")


class _ForbiddenConverter:
    """Stands in for docling when the test needs it never to run at all."""

    def convert(self, _path):  # pragma: no cover -- the failure IS the assert
        raise AssertionError(
            "the layout model was started from a path that must never start it")


class TestEveryPdfTheReviewWillReadIsFound:
    """A file the sweep is told to read and the pre-flight never saw is exactly
    the file that hits a cache-only refusal mid-run."""

    def test_the_article_and_a_conventionally_named_supplement(self, tmp_path):
        d = tmp_path / "10.1234--x"
        d.mkdir()
        _write_pdf(d / "10.1234--x.pdf")
        _write_pdf(d / "10.1234--x_supplementary_1.pdf")

        found = {p.name: role for p, role in _pdfs_to_extract(str(d))}
        assert found == {"10.1234--x.pdf": "article",
                         "10.1234--x_supplementary_1.pdf": "supplement"}

    def test_jats_xml_skips_the_article_pdf_but_not_the_si(self, tmp_path):
        """XML is the source of record for numbers; docling the article PDF
        beside it is a worse source the model can waste the stage on."""
        d = tmp_path / "10.1234--xml"
        d.mkdir()
        _write_pdf(d / "10.1234--xml.pdf")
        _write_pdf(d / "10.1234--xml_supplementary_1.pdf")
        (d / "10.1234--xml.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<article><body><sec><title>Results</title>"
            '<table-wrap id="t1"><label>Table 1</label>'
            "<table><thead><tr><th>A</th></tr></thead>"
            "<tbody><tr><td>1.0 (0.2)</td></tr></tbody></table>"
            "</table-wrap></sec></body></article>",
            encoding="utf-8",
        )
        found = {p.name: role for p, role in _pdfs_to_extract(str(d))}
        assert "10.1234--xml.pdf" not in found
        assert found.get("10.1234--xml_supplementary_1.pdf") == "supplement"

    def test_a_declared_supplement_whose_name_says_nothing(self, tmp_path):
        """`_resolve_paper_sources` splits supplements off by a filename regex
        (`suppl`, `_si`, ...). `appendix.pdf` matches none of it, so only the
        operator's declaration knows what it is -- which is why both
        enumerators are unioned rather than one being picked."""
        d = tmp_path / "10.1234--y"
        d.mkdir()
        _write_pdf(d / "10.1234--y.pdf")
        _write_pdf(d / "appendix.pdf")
        supplements.write_declaration(d, supplements=["appendix.pdf"])

        found = {p.name: role for p, role in _pdfs_to_extract(str(d))}
        assert found["appendix.pdf"] == "supplement", (
            "a declared supplement was not queued for extraction, so the sweep "
            "would meet the cache-only refusal on it mid-run")

    def test_an_out_of_tree_supplement_supplied_on_the_command_line(self, tmp_path):
        """`--supplement` may point anywhere. Its cache is written beside the
        FILE, so it has to be extracted by path, not by directory scan."""
        d = tmp_path / "10.1234--z"
        d.mkdir()
        _write_pdf(d / "10.1234--z.pdf")
        elsewhere = _write_pdf(tmp_path / "loose_supplement.pdf")

        found = {p.name for p, _ in _pdfs_to_extract(str(d), extra=[elsewhere])}
        assert "loose_supplement.pdf" in found

    def test_a_paper_with_no_pdf_queues_nothing(self, tmp_path):
        """An XML or markdown paper needs no layout model. Queuing one anyway
        would put a multi-minute step in front of a run that cannot use it."""
        d = tmp_path / "10.1234--xmlonly"
        d.mkdir()
        (d / "body.md").write_text("# a paper\n")
        assert _pdfs_to_extract(str(d)) == []


class TestAPresentCacheCostsNothing:
    """Idempotence is what allows the pre-flight to be called twice -- once in
    `cli.analyze` before its own gate, once in `analyze_paper` because `batch`
    enters there instead."""

    @pytest.mark.skipif(
        not dl.cache_status(
            CACHED_PAPER / f"{CACHED_PAPER.name}.pdf")[0],
        reason="corpus paper has no usable cache (run `metascience extract-tables`)",
    )
    def test_a_cached_paper_does_not_start_the_model(self, monkeypatch):
        monkeypatch.setattr(dl, "_converter", _ForbiddenConverter)
        rec = ensure_paper_extracted(str(CACHED_PAPER))
        assert rec["n_extracted"] == 0
        # Either the article PDF cache was reused, or JATS XML is primary
        # and the article PDF was not queued for docling at all. Both
        # prove the layout model did not start.
        assert rec["n_cached"] == 1 or rec.get("skipped_article_pdf") == "xml_primary"
        assert rec["failed"] == []
        if rec["n_cached"]:
            assert [c["status"] for c in rec["checked"]] == ["cached"]


class TestPresenceIsNotUsability:
    """A cache file that exists but predates a field a reader needs is the
    subtlest form of the bug this whole pre-flight exists to kill: the operator
    is told the paper is ready, and `extract_pdf` -- the sweep's main way into a
    PDF -- answers `unreadable: True, num_pages: 0` in the middle of the run.

    MEASURED 2026-08-17 across this repository's 21 cache entries: 14 schema 2,
    1 schema 3, 4 unstamped, 2 schema 4. Nineteen of twenty-one carried no
    per-page text, including every paper in `high_value_pdfs_to_run_on`.
    """

    def _cache(self, pdf: Path, payload: dict) -> Path:
        c = dl._cache_path(pdf)
        c.parent.mkdir(parents=True, exist_ok=True)
        c.write_text(json.dumps(payload), encoding="utf-8")
        return c

    def test_a_cache_with_no_per_page_text_is_not_usable(self, tmp_path):
        pdf = _write_pdf(tmp_path / "10.1234--stale.pdf")
        self._cache(pdf, {"text": "body", "tables": [], "cache_schema": 2})
        usable, why = dl.cache_status(pdf)
        assert usable is False
        assert "extract_pdf" in why

    def test_a_cache_with_no_body_text_is_not_usable(self, tmp_path):
        pdf = _write_pdf(tmp_path / "10.1234--tablesonly.pdf")
        self._cache(pdf, {"text": "", "tables": [], "pages": [], "cache_schema": 2})
        usable, why = dl.cache_status(pdf)
        assert usable is False
        assert "tables only" in why

    def test_a_cache_from_before_header_depth_is_not_usable(self, tmp_path):
        """Schema 4 was written when every table got a one-row header, so on a
        stacked header its cells carry the SPANNING label instead of the
        column's own -- `Control` where the paper printed `Control / Saline`,
        `Control / Cu`, `Control / Ag`. Nothing in the payload marks which
        tables that hit, so it cannot be repaired on read, and a wrong column
        label is how a mean gets paired with another group's `n`."""
        pdf = _write_pdf(tmp_path / "10.1234--onerow.pdf")
        self._cache(pdf, {"text": "body", "tables": [],
                          "pages": [{"page_num": 1, "text": "body"}],
                          "num_pages": 1, "cache_schema": 4})
        usable, why = dl.cache_status(pdf)
        assert usable is False
        assert "stacked header" in why and "--force" in why

    def test_a_complete_cache_is_usable(self, tmp_path):
        pdf = _write_pdf(tmp_path / "10.1234--fresh.pdf")
        self._cache(pdf, {"text": "body", "tables": [],
                          "pages": [{"page_num": 1, "text": "body"}],
                          "num_pages": 1, "cache_schema": 7})
        assert dl.cache_status(pdf) == (True, "")

    def test_the_preflight_refreshes_a_stale_entry(self, tmp_path, monkeypatch):
        """Not merely re-read -- RE-EXTRACTED. `extract_pdf_tables` would serve
        the stale entry straight back on a cache hit, so the pre-flight has to
        pass `use_cache=False` or it reports success and changes nothing."""
        monkeypatch.setattr(dl, "available", lambda: (True, ""))
        d = tmp_path / "10.1234--stale"
        d.mkdir()
        pdf = _write_pdf(d / "10.1234--stale.pdf")
        self._cache(pdf, {"text": "body", "tables": [], "cache_schema": 2})

        seen: list = []

        def fake_extract(path, use_cache=True, allow_extract=True):
            seen.append(use_cache)
            return {"tables": [], "text": "body", "error": None, "n_tables": 0,
                    "n_text_chars": 4}

        monkeypatch.setattr(dl, "extract_pdf_tables", fake_extract)
        rec = ensure_paper_extracted(str(d))
        assert seen == [False], "a stale cache was served back instead of refreshed"
        assert rec["n_extracted"] == 1 and rec["n_cached"] == 0


class TestOneUnreadableFileDoesNotEndTheRun:
    """A supplement we could not open is a fact about US. Refusing the whole
    paper over it throws away the parts we CAN read; saying nothing lets 'we
    did not read it' be mistaken for 'the authors did not report it'."""

    @pytest.fixture
    def paper(self, tmp_path, monkeypatch):
        monkeypatch.setattr(dl, "available", lambda: (True, ""))
        monkeypatch.setattr(dl, "_converter", _ExplodingConverter)
        d = tmp_path / "10.1234--broken"
        d.mkdir()
        _write_pdf(d / "10.1234--broken.pdf")
        _write_pdf(d / "10.1234--broken_supplementary_1.pdf")
        return ensure_paper_extracted(str(d))

    def test_it_returns_rather_than_raising(self, paper):
        assert paper["failed"], "the failure was not recorded at all"

    def test_every_file_is_still_accounted_for(self, paper):
        """Not "we stopped at the first error": a run that reports two files
        and read neither must say so about both."""
        assert len(paper["checked"]) == 2
        assert {c["status"] for c in paper["checked"]} == {"failed"}

    def test_the_reason_travels(self, paper):
        assert all(c["error"] for c in paper["checked"])
        assert "simulated docling failure" in paper["checked"][0]["error"]

    def test_the_note_blames_us_and_not_the_authors(self, paper):
        """The cardinal rule: OUR gap is never recorded as the paper's."""
        note = paper["note"].lower()
        assert "unknown" in note
        assert "not checked and found absent" in note

    def test_a_missing_docling_is_named_as_an_environment_gap(
            self, tmp_path, monkeypatch):
        monkeypatch.setattr(dl, "available", lambda: (False, "ImportError: docling"))
        d = tmp_path / "10.1234--nodocling"
        d.mkdir()
        _write_pdf(d / "10.1234--nodocling.pdf")
        rec = ensure_paper_extracted(str(d))
        assert rec["failed"] == ["10.1234--nodocling.pdf"]
        assert "our environment" in rec["note"].lower()


class TestExtractionStaysOutOfReadPaths:
    """THE TRIPWIRE. Every read path must answer an unextracted PDF with a
    legible refusal, never by starting the layout model -- whatever the cost of
    the refusal looks like locally, the alternative has been measured three
    times and it is minutes per call across the whole suite."""

    @pytest.fixture
    def unextracted(self, tmp_path, monkeypatch):
        monkeypatch.setattr(dl, "available", lambda: (True, ""))
        monkeypatch.setattr(dl, "_converter", _ForbiddenConverter)
        d = tmp_path / "10.1234--unextracted"
        d.mkdir()
        return _write_pdf(d / "10.1234--unextracted.pdf")

    def test_extract_text_refuses_instead_of_extracting(self, unextracted):
        from metascience_agent.extraction.pdf import extract_text

        with pytest.warns(UserWarning, match="has not been extracted"):
            assert extract_text(unextracted) == ""

    def test_extract_text_with_tables_refuses_instead_of_extracting(self, unextracted):
        from metascience_agent.extraction.pdf import extract_text_with_tables

        out = extract_text_with_tables(unextracted)
        assert out["unreadable"] is True
        assert "extract-tables" in (out["text_extractor_note"] or "")

    def test_paper_text_refuses_instead_of_extracting(self, unextracted):
        """The one that matters most: `paper_text` is called by the supplement
        gate, the quote haystack and the glyph scan, on every paper."""
        from metascience_agent.extraction.jats import paper_text

        with pytest.warns(UserWarning, match="has not been extracted"):
            assert paper_text(unextracted.parent) == ""

    def test_the_enumerator_refuses_instead_of_extracting(self, unextracted):
        r = dl.extract_pdf_tables(unextracted, allow_extract=False)
        assert r["tables"] == []
        assert "THIS IS NOT A PAPER WITHOUT TABLES" in r["error"]


class TestTheCliRunsItBeforeItsOwnGate:
    """Order is the whole point. `supplements.gate` reads the paper through the
    docling cache; run first, it refuses a perfectly readable PDF-only paper
    with 'no PDF text layer' -- MEASURED on `10.1136--jnnp.66.1.64`, which goes
    from `proceed=False, text_available=False` to `proceed=True, missing=False`
    across the pre-flight and nothing about the file changes."""

    def test_the_preflight_precedes_the_supplement_gate(self):
        import inspect

        from metascience_agent import cli

        src = inspect.getsource(cli.analyze)
        assert "ensure_paper_extracted" in src, (
            "cli.analyze no longer pre-extracts, so an unextracted paper reads "
            "as one with no text layer")
        assert src.index("ensure_paper_extracted(") < src.index("_supplement_gate("), (
            "the supplement gate runs before the cache is filled, so OUR "
            "missing extraction is reported as the paper having no text")

    def test_batch_pre_extracts_before_its_gate(self):
        """The analyze ordering was right; batch still gated on cold caches.

        MEASURED 2026-08-20 on nina_mazar/grok_test: 5 of 7 PDF-only papers
        were labelled 'scanned or corrupt' because `batch_cmd` called
        `_supp_gate` before `ensure_paper_extracted`, and empty cache-miss
        text is `text_available: False`.
        """
        import inspect

        from metascience_agent import cli

        src = inspect.getsource(cli.batch_cmd)
        assert "ensure_paper_extracted(" in src
        assert src.index("ensure_paper_extracted(") < src.index(
            "gates = {p: _supp_gate(p)"), (
            "batch must fill the docling cache before the unreadability gate")

