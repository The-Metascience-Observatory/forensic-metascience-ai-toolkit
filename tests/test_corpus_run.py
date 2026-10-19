"""The producer that had no consumer, joined to the consumer that had no producer.

`blinding.py` (403 lines) had ZERO importers, so every "blinded" run was
unblinded. `evaluation/corpus.py`, the preregistered scorer, reads a
`cells.jsonl` that NOTHING IN THE REPO PRODUCED. Both were written in the same
week, in the same package, and could not reach each other.

These tests hold the connection, and hold the refusals honest: the value of this
runner is not what it checks but what it declines to check, by name and with a
reason, rather than checking it on a guessed declaration.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit.evaluation import corpus, corpus_run

MANIFEST_TOOLS = set(corpus.TOOLS)


@pytest.fixture
def paper(tmp_path):
    src = tmp_path / "10.1234--x"
    src.mkdir()
    (src / "body.md").write_text(
        "Participants improved, t(48) = 2.31, p = .04, and the effect held.\n")
    return src


class TestOnePaperProducesOneRowPerTool:
    def test_every_manifest_tool_gets_a_row(self, paper, tmp_path):
        rows = corpus_run.run_paper("10.1234/x", paper, tmp_path / "b")
        assert {r["tool"] for r in rows} == MANIFEST_TOOLS

    def test_rows_load_into_the_scorer_without_complaint(self, paper, tmp_path):
        """The join that did not exist: this runner's output must be exactly
        what the preregistered scorer reads."""
        rows = corpus_run.run_paper("10.1234/x", paper, tmp_path / "b")
        p = tmp_path / "cells.jsonl"
        p.write_text("".join(json.dumps(r) + "\n" for r in rows))
        loaded = corpus.load_cells(p)
        assert len(loaded) == len(rows)


class TestTheRefusalsAreTheDeliverable:
    def test_every_declaration_dependent_tool_refuses_with_a_reason(self, paper, tmp_path):
        rows = {r["tool"]: r for r in
                corpus_run.run_paper("10.1234/x", paper, tmp_path / "b")}
        for tool in ("grim", "grimmer", "sprite", "debit",
                     "baseline_similarity", "duplication"):
            assert rows[tool]["evaluated"] is False, tool
            assert len(rows[tool]["note"]) > 40, tool

    def test_digit_preference_says_the_tool_does_not_exist(self, paper, tmp_path):
        """Not 'unevaluated' -- UNSCOREABLE. The manifest's vocabulary names a
        technique this toolkit has never implemented, and my own
        pre-registration counted cells for it without checking."""
        from forensic_metascience_ai_toolkit.registry import BY_NAME
        assert not [k for k in BY_NAME if "digit" in k or "benford" in k.lower()]
        row = {r["tool"]: r for r in
               corpus_run.run_paper("10.1234/x", paper, tmp_path / "b")}["digit_preference"]
        assert row["evaluated"] is False
        assert "NOT IMPLEMENTED" in row["note"]

    def test_no_refusal_is_recorded_as_a_clean_pass(self, paper, tmp_path):
        """A refusal scored as `consistent` would be a false all-clear, which the
        severity ladder ranks second-worst after a false accusation."""
        for r in corpus_run.run_paper("10.1234/x", paper, tmp_path / "b"):
            if not r["evaluated"]:
                assert r["max_severity"] is None, r


class TestStatcheckIsTheOnlyThingThatCanRunUnaided:
    def test_it_runs_and_reports_a_severity(self, paper, tmp_path):
        row = {r["tool"]: r for r in
               corpus_run.run_paper("10.1234/x", paper, tmp_path / "b")}["statcheck"]
        assert row["evaluated"] is True
        assert row["max_severity"] in {"consistent", "suspicious", "highly_suspicious"}

    def test_it_never_reaches_impossible(self, paper, tmp_path):
        """statcheck cannot see rounding conventions, one- vs two-tailed, or a
        correction applied silently, so it has no route to the top of the
        ladder."""
        row = {r["tool"]: r for r in
               corpus_run.run_paper("10.1234/x", paper, tmp_path / "b")}["statcheck"]
        assert row["max_severity"] != "impossible"

    def test_a_paper_with_no_machine_readable_text_refuses(self, tmp_path):
        """Blinding ships no PDF -- page watermarks are unscrubbable pixels -- so
        a PDF-only paper arrives empty. That must read as a refusal, never as a
        paper with nothing wrong."""
        src = tmp_path / "10.9/pdfonly"
        src.mkdir(parents=True)
        (src / "paper.pdf").write_bytes(b"%PDF-1.4 not extractable")
        row = {r["tool"]: r for r in
               corpus_run.run_paper("10.9/pdfonly", src, tmp_path / "b")}["statcheck"]
        assert row["evaluated"] is False
        assert "no machine-readable text" in row["note"]

    def test_a_crash_is_a_refusal_not_a_pass(self, paper, tmp_path, monkeypatch):
        from forensic_metascience_ai_toolkit.registry import BY_NAME

        class Boom:  # ToolSpec is frozen; swap the registry entry, not the spec
            def call(self, *_a, **_k):
                raise RuntimeError("boom")

        monkeypatch.setitem(BY_NAME, "statcheck", Boom())
        row = {r["tool"]: r for r in
               corpus_run.run_paper("10.1234/x", paper, tmp_path / "b")}["statcheck"]
        assert row["evaluated"] is False and "RuntimeError" in row["note"]


class TestBlindingIsActuallyApplied:
    def test_the_runner_calls_the_blinder(self, tmp_path):
        """The whole point: blinding.py had no importer, so nothing was blinded."""
        src = tmp_path / "10.5--retracted-thing"
        src.mkdir()
        (src / "body.md").write_text(
            "This article has been retracted. t(48) = 2.31, p = .04.\n")
        rows = corpus_run.run_paper("10.5/x", src, tmp_path / "b")
        blinded = tmp_path / "b" / rows[0]["paper_id"]
        assert blinded.exists()
        text = "".join(p.read_text() for p in blinded.rglob("*") if p.is_file())
        assert "has been retracted" not in text
        assert "2.31" in text, "blinding must not destroy the numbers"

    def test_a_blinding_failure_evaluates_nothing(self, tmp_path, monkeypatch):
        """A paper we could not blind must not be scored -- PREREGISTRATION.md
        section 3.2 records it as a blinding failure, not as a tool result."""
        src = tmp_path / "10.6--x"
        src.mkdir()
        (src / "body.md").write_text("t(10) = 2.0, p = .07\n")

        real = corpus_run.blinding.materialize

        def fake(source, root, paper_id=None):
            bp = real(source, root, paper_id)
            bp.residual = ["PATH something-retracted"]
            return bp

        monkeypatch.setattr(corpus_run.blinding, "materialize", fake)
        rows = corpus_run.run_paper("10.6/x", src, tmp_path / "b")
        assert {r["tool"] for r in rows} == MANIFEST_TOOLS
        assert all(r["evaluated"] is False for r in rows)
        assert all("blinding failure" in r["note"] for r in rows)


class TestTheWholeLoop:
    def test_run_corpus_writes_cells_the_scorer_can_read(self, tmp_path):
        papers = tmp_path / "papers"
        (papers / "10.1--a").mkdir(parents=True)
        (papers / "10.1--a" / "body.md").write_text("F(2, 40) = 3.1, p = .05\n")
        manifest = tmp_path / "m.csv"
        manifest.write_text(
            "doi,label,notes,expected_statistical_signature,can_validate_tools,"
            "cannot_validate_tools\n"
            "10.1/a,control,,none,\"grim,statcheck\",\n")
        summary = corpus_run.run_corpus(manifest, papers, tmp_path / "out")
        assert summary["papers"] == 1 and summary["cells"] == len(MANIFEST_TOOLS)
        result = corpus.score(corpus.load_manifest(manifest),
                              corpus.load_cells(Path(summary["cells_path"])))
        assert result["E1"].n > 0

    def test_a_paper_absent_from_disk_is_named_not_skipped(self, tmp_path):
        papers = tmp_path / "papers"
        papers.mkdir()
        manifest = tmp_path / "m.csv"
        manifest.write_text(
            "doi,label,notes,expected_statistical_signature,can_validate_tools,"
            "cannot_validate_tools\n10.1/ghost,control,,none,grim,\n")
        summary = corpus_run.run_corpus(manifest, papers, tmp_path / "out")
        assert summary["papers_missing_on_disk"] == ["10.1/ghost"]


class TestCaseDoesNotDecidePresence:
    """A DOI's letter case must never decide whether its paper is found.

    `eval/ground_truth/tools/fetch_paper.py:slug` lowercases when it CREATES
    each directory; three consumers resolved the manifest DOI without
    lowercasing. That disagreed only for DOIs a publisher prints with capitals,
    and the corpus has exactly two -- `10.2147/TCRM.S15812` and
    `10.2147/TCRM.S43811`, both `fraud`, both with full-text XML. So 2 of 30
    fraud papers and 2 of 15 fraud XMLs silently left every corpus measurement,
    while the run still described itself as covering the corpus. DOIs are
    case-insensitive by specification (ISO 26324); the case carries no
    information and must not be load-bearing.
    """

    def test_an_uppercase_doi_finds_its_lowercase_directory(self, tmp_path):
        (tmp_path / "10.2147--tcrm.s15812").mkdir()
        got = corpus_run.resolve_paper_dir(tmp_path, "10.2147/TCRM.S15812")
        assert got is not None and got.name == "10.2147--tcrm.s15812"

    def test_a_case_preserved_directory_still_resolves(self, tmp_path):
        """The fix must not merely swap which convention breaks."""
        (tmp_path / "10.2147--TCRM.S15812").mkdir()
        got = corpus_run.resolve_paper_dir(tmp_path, "10.2147/TCRM.S15812")
        assert got is not None and got.name == "10.2147--TCRM.S15812"

    def test_a_genuinely_absent_paper_is_still_absent(self, tmp_path):
        """Case-insensitivity must not manufacture a paper that is not there."""
        assert corpus_run.resolve_paper_dir(tmp_path, "10.1/ghost") is None

    def test_the_real_corpus_resolves_every_manifest_row(self):
        """The measurement, against the files themselves."""
        import csv

        from forensic_metascience_ai_toolkit.evaluation.harness import repo_root

        root = repo_root() / "eval" / "ground_truth"
        rows = list(csv.DictReader(open(root / "manifest.csv", encoding="utf-8")))
        missing = [r["doi"] for r in rows
                   if corpus_run.resolve_paper_dir(root / "papers", r["doi"]) is None]
        assert missing == [], missing
        assert len(rows) == 78
