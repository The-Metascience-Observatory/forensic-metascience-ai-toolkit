"""`metascience agreement` reads findings-v2 runs only.

It once looked only for the serial pipeline's `findings.json`, and on a paper
carrying runs of both kinds published a pass@1 bracket about a pipeline that no
longer existed (measured on 10.1002--ajcp.70049: three runs used, all schema
1.0). The v1 layout is no longer read at all, so the two can no longer mix.
"""

from __future__ import annotations

import json
import pathlib

from forensic_metascience_ai_toolkit.evaluation.agreement import find_runs, from_review_dirs

ROW = {"slug": "s", "title": "t" * 10, "description": "d" * 30,
       "location": "Table 1", "severity": "suspicious"}


def _run(root: pathlib.Path, name: str, filename: str) -> pathlib.Path:
    d = root / name
    d.mkdir(parents=True)
    (d / filename).write_text(json.dumps({"paper_id": "p", "findings": [ROW]}))
    return d


class TestItReadsTheCurrentSchemaOnly:
    def test_a_v2_run_is_found(self, tmp_path):
        _run(tmp_path, "review_a", "findings.v2.json")
        assert [d.name for d in find_runs(tmp_path)] == ["review_a"]

    def test_a_v1_findings_file_is_not_a_run(self, tmp_path):
        _run(tmp_path, "old_a", "findings.json")
        _run(tmp_path, "new_a", "findings.v2.json")
        assert [d.name for d in find_runs(tmp_path)] == ["new_a"]

    def test_a_v1_directory_given_by_hand_is_skipped_and_said(self, tmp_path):
        a = _run(tmp_path, "old_a", "findings.json")
        b = _run(tmp_path, "new_a", "findings.v2.json")
        out = from_review_dirs([a, b])
        assert out["runs_used"] == ["new_a"]
        assert "no readable findings.v2.json" in out["note"]

    def test_runs_of_one_paper_are_compared(self, tmp_path):
        a = _run(tmp_path, "v2_a", "findings.v2.json")
        b = _run(tmp_path, "v2_b", "findings.v2.json")
        out = from_review_dirs([a, b])
        assert out.get("error") is None
        assert "pass_at_1_bracket" in out
