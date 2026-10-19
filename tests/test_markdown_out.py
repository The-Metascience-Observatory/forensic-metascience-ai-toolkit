"""The paper as markdown, in one place an agent can find, and safe to hand it.

MEASURED 2026-08-22 over 1,293 paper directories: 980 (76%) held no markdown
this repo could read. `fetchpdf --to-markdown` writes `<stem>_from_xml.md`
(418 of them) and `<stem>_from_html.md` (37), which appear nowhere in this
repo's source, while `paper_text_with_source` looks for `body.md` and
`<stem>_from_pdf_body.md`.

The agents went looking anyway and paid for it: on the 2026-08-22 biomedical
batch the adjudicator failed 66% of its tool calls -- `read_file body.md`,
`paper/body.md`, `paper.md`, names it guessed -- and one paper stalled
mid-thrash and held a worker for 70 minutes.

Adopting fetchpdf's files was the wrong fix: 152 of those 418 (36%) declare
fewer tables than the XML holds, dissolving the rows into prose as undelimited
digit runs while their own front matter certifies `tables: 0`.
"""
from __future__ import annotations

import json

import pytest

from metascience_agent.extraction import markdown_out as M


@pytest.fixture()
def paper(tmp_path, monkeypatch):
    d = tmp_path / "10.1234--demo"
    d.mkdir()
    monkeypatch.setattr(
        "metascience_agent.extraction.jats.paper_text_with_source",
        lambda p: ("## Results\n\n[Table 1: Baseline — 4 rows x 3 cols]\n\n"
                   "t(28) = 2.10, p = .04.\n", "xml_publisher"))
    return d


class TestTheFolderIsWritten:
    def test_body_and_provenance_land_together(self, paper):
        out = M.materialise(paper)
        assert out["action"] == "written"
        assert M.body_path(paper).is_file()
        meta = json.loads(M.source_path(paper).read_text())
        assert meta["source_channel"] == "xml_publisher"
        assert meta["markdown_schema"] == M.MARKDOWN_SCHEMA
        assert meta["n_table_placeholders"] == 1

    def test_it_is_idempotent(self, paper):
        M.materialise(paper)
        assert M.materialise(paper)["action"] == "current"

    def test_a_changed_source_regenerates(self, paper, monkeypatch):
        M.materialise(paper)
        monkeypatch.setattr(
            "metascience_agent.extraction.jats.paper_text_with_source",
            lambda p: ("## Results\n\nrewritten entirely.\n", "xml_publisher"))
        assert M.materialise(paper)["action"] == "written"
        assert "rewritten" in M.body_path(paper).read_text()

    def test_a_schema_bump_regenerates(self, paper, monkeypatch):
        M.materialise(paper)
        monkeypatch.setattr(M, "MARKDOWN_SCHEMA", M.MARKDOWN_SCHEMA + 1)
        assert M.materialise(paper)["action"] == "written"


class TestItRefusesToAssertThingsItDoesNotKnow:
    def test_no_text_writes_nothing(self, paper, monkeypatch):
        """"" is UNKNOWN, never "this paper says nothing". An empty body.md
        would turn our failure to read into an artifact asserting the paper is
        blank -- the substitution this whole toolkit exists to catch."""
        monkeypatch.setattr(
            "metascience_agent.extraction.jats.paper_text_with_source",
            lambda p: ("", None))
        out = M.materialise(paper)
        assert out["action"] == "skipped"
        assert not M.body_path(paper).exists()
        assert "blank" in out["reason"]

    def test_a_missing_directory_is_reported_not_raised(self, tmp_path):
        out = M.materialise(tmp_path / "nope")
        assert out["action"] == "skipped" and "not a directory" in out["reason"]

    def test_an_unwritable_directory_never_ends_the_run(self, paper, monkeypatch):
        """A read-only corpus mount degrades to "no folder", never an abort:
        this is a convenience artifact, and the run has the text in memory."""
        def boom(*a, **k):
            raise PermissionError("read-only file system")
        monkeypatch.setattr("metascience_agent.atomicio.atomic_write_text", boom)
        out = M.materialise(paper)
        assert out["action"] == "failed" and "PermissionError" in out["error"]

    def test_unreadable_provenance_is_none_not_empty(self, paper):
        M.materialise(paper)
        M.source_path(paper).write_text("{ this is not json")
        assert M.read_source(paper) is None


class TestTheFolderIsNeverOurOwnInput:
    def test_paper_text_does_not_read_it_back(self):
        """The folder is written FOR AGENTS. Reading it back would make it its
        own input and reintroduce a staleness class we cannot close: it
        invalidates on the source FILES changing, not on the extractor
        changing -- and the extractor moved twice in two days (dc4306f,
        d5d8604), adding thousands of characters per paper, with the XML
        untouched both times. A fresh resolve costs 4.4 ms/paper."""
        import inspect
        from metascience_agent.extraction.jats import paper_text_with_source
        params = inspect.signature(paper_text_with_source).parameters
        assert "use_markdown_dir" not in params, \
            "the read-back was removed deliberately; see the comment in jats.py"
        assert not hasattr(M, "cached_body"), \
            "no reader belongs in this module -- it writes for agents only"

    def test_find_body_md_still_points_at_it(self, paper):
        """A pointer for prompts and callers is not a text source."""
        from metascience_agent.extraction.jats import find_body_md
        M.materialise(paper)
        assert find_body_md(paper) == M.body_path(paper)


class TestFetchpdfMarkdownIsNeverASource:
    def test_from_xml_md_is_not_read(self, tmp_path):
        """418 of these sit in the corpora. 152 (36%) declare fewer tables than
        their XML holds, with the rows dissolved into the prose."""
        from metascience_agent.extraction.jats import (
            _FETCHPDF_MARKDOWN_IS_NOT_A_SOURCE, find_body_md,
            paper_text_with_source)
        d = tmp_path / "10.1234--trap"
        d.mkdir()
        (d / "10.1234--trap_from_xml.md").write_text(
            "---\ntables: 0\n---\n\nB5.111.870.232.730.007\n" * 50)
        assert find_body_md(d) is None
        text, channel = paper_text_with_source(d)
        assert "5.111.870" not in text
        assert channel != "from_xml"
        assert "_from_xml.md" in _FETCHPDF_MARKDOWN_IS_NOT_A_SOURCE


class TestTheGuaranteeIsMeasuredNotAsserted:
    """`tables_are_placeholders_not_inlined` was hardcoded True.

    It is the property that makes this file safe to hand a model, and the
    comment above it says to state it "as a number rather than a promise" --
    while the next line stated a promise. It is wrong whenever the text did not
    come from `jats.py`, which is where the placeholder is emitted.
    """

    def _write(self, tmp_path, text):
        from metascience_agent.extraction import markdown_out as M
        return M.write_markdown(tmp_path, text, "pdf")

    def test_a_pipe_table_in_the_text_makes_the_flag_false(self, tmp_path):
        meta = self._write(tmp_path, "Prose.\n\n| a | b |\n| 1 | 2 |\n")
        assert meta["n_inlined_table_rows"] == 2
        assert meta["tables_are_placeholders_not_inlined"] is False

    def test_placeholders_alone_keep_the_flag_true(self, tmp_path):
        meta = self._write(tmp_path, "Prose.\n\n[Table 1: Baseline -- 4 rows x 3 cols]\n")
        assert meta["n_table_placeholders"] == 1
        assert meta["n_inlined_table_rows"] == 0
        assert meta["tables_are_placeholders_not_inlined"] is True

    def test_a_paper_with_no_tables_at_all_is_still_true(self, tmp_path):
        meta = self._write(tmp_path, "Just prose, no tables anywhere.")
        assert meta["tables_are_placeholders_not_inlined"] is True

    def test_a_lone_pipe_in_prose_is_not_a_table_row(self, tmp_path):
        """A regex in a methods section, or a units header, carries one `|`."""
        meta = self._write(tmp_path, "We matched /foo|bar/ against the corpus.")
        assert meta["n_inlined_table_rows"] == 0
        assert meta["tables_are_placeholders_not_inlined"] is True

    def test_both_counts_are_reported_so_a_mixed_file_is_legible(self, tmp_path):
        meta = self._write(tmp_path,
                           "[Table 1: A -- 2 rows x 2 cols]\n\n| a | b |\n| 1 | 2 |\n")
        assert meta["n_table_placeholders"] == 1
        assert meta["n_inlined_table_rows"] == 2
        assert meta["tables_are_placeholders_not_inlined"] is False, (
            "one placeholder does not excuse a second table left inline")

    def test_the_real_apple_cider_body_is_reported_honestly(self, tmp_path):
        """The run that motivated this: 3 tables, 0 placeholders, and a
        source.json claiming the tables were not inlined."""
        from pathlib import Path
        from metascience_agent.extraction import markdown_out as M
        body = Path("benchmarks/paper_reviews/runs/apple_cider/paper/body.md")
        if not body.is_file():
            import pytest
            pytest.skip("eval fixture not present")
        text = body.read_text(encoding="utf-8", errors="replace")
        assert M._count_inlined_table_rows(text) > 0
        assert len(M._PLACEHOLDER.findall(text)) == 0
