"""drafts: transport mocked, refusals named, never posts."""

import json
from pathlib import Path
from types import SimpleNamespace

from metascience_agent import drafts as D


def _paper(tmp_path):
    paper = tmp_path / "10.1234--x"
    run = paper / "forensic_review"
    run.mkdir(parents=True)
    (run / "findings.v2.json").write_text(json.dumps({
        "schema_version": "2.0", "paper_id": "10.1234--x",
        "run_id": "r_" + "a" * 16,
        "paper_metadata": {"title": "T", "doi": "10.1234/x"},
        "channels": {"tool_expert": {"state": "ran"}},
        "adjudication": {"ran": True, "summary": "s" * 200},
        "findings": [
            {"finding_id": "f_" + "1" * 16, "slug": "grim1",
             "producer": "tool_expert", "technique": "grim_check",
             "title": "an impossible percentage", "description": "d" * 30,
             "outcome": "problem", "severity": 5, "impossible": True,
             "quote": "81.3%", "reproduction": "metascience grim 81.3 79",
             "adjudication": {"action": "kept"}},
            {"finding_id": "f_" + "2" * 16, "slug": "gone",
             "producer": "tool_expert", "technique": "grim_check",
             "title": "a discarded row here", "description": "d" * 30,
             "outcome": "problem", "severity": None,
             "adjudication": {"action": "discarded"}},
        ]}))
    return paper


def ok_cli(argv, text):
    return SimpleNamespace(returncode=0, stderr="",
                           stdout=json.dumps({"result": "Dear authors, ..."}))


class TestGenerate:
    def test_draft_is_persisted_with_front_matter(self, tmp_path):
        paper = _paper(tmp_path)
        rec = D.generate(paper, "pubpeer", run_cli=ok_cli)
        assert rec["ok"] and rec["n_findings"] == 1, \
            "discarded rows never enter a draft by default"
        body = Path(rec["path"]).read_text()
        assert body.startswith("---\n")
        assert "Dear authors" in body
        assert D.list_drafts(paper)[0]["kind"] == "pubpeer"

    def test_finding_selection_accepts_slugs(self, tmp_path):
        rec = D.generate(_paper(tmp_path), "letter",
                         finding_ids=["grim1"], run_cli=ok_cli)
        assert rec["ok"] and rec["n_findings"] == 1

    def test_no_findings_doc_is_a_named_refusal(self, tmp_path):
        rec = D.generate(tmp_path, "pubpeer", run_cli=ok_cli)
        assert rec["ok"] is False and "findings.v2.json" in rec["error"]

    def test_cli_failure_is_a_named_refusal(self, tmp_path):
        def dead(argv, text):
            return SimpleNamespace(returncode=3, stderr="boom", stdout="")
        rec = D.generate(_paper(tmp_path), "pubpeer", run_cli=dead)
        assert rec["ok"] is False and "exited 3" in rec["error"]

    def test_the_module_never_posts(self):
        import inspect
        src = inspect.getsource(D)
        for banned in ("requests", "urllib", "httpx", "pubpeer.com/api"):
            assert banned not in src
