"""The raw_data module: the copy-paste detector over a paper's spreadsheets.

Opt-in (`raw_data_only`, `full_raw_data`), deterministic, a child process,
and its rows are quarantined: one per (file, kind), never per group, capped,
never the headline. A paper with no spreadsheet is `did_not_run`, never clean.
"""

import asyncio
import json

from forensic_metascience_ai_toolkit import adjudicate, agent, raw_track
from forensic_metascience_ai_toolkit import pipeline_config as pc
from tests.test_parallel_pipeline import fakes, paper  # noqa: F401


def _csv_with_copied_rows() -> str:
    """80 rows of four-decimal values; rows 10-19 reappear as rows 50-59."""
    x, rows = 12345, []
    for _ in range(80):
        row = []
        for _ in range(6):
            x = (1103515245 * x + 12345) % 2 ** 31
            row.append(f"{x / 2 ** 31 * 100:.4f}")
        rows.append(row)
    for i in range(10):
        rows[50 + i] = list(rows[10 + i])
    return "id,a,b,c,d,e,f\n" + "\n".join(
        f"{i}," + ",".join(r) for i, r in enumerate(rows))


def _run(paper_dir, name="raw_data_only"):
    return asyncio.run(agent.analyze_paper(
        str(paper_dir), mode="parallel", pipeline=pc.load(name)))


class TestTheFiles:
    def test_top_level_and_allowlisted_folders_only(self, tmp_path):
        (tmp_path / "a.csv").write_text("x\n1\n")
        (tmp_path / "supplementary").mkdir()
        (tmp_path / "supplementary" / "b.xlsx").write_bytes(b"")
        (tmp_path / "forensic_review_x").mkdir()
        (tmp_path / "forensic_review_x" / "c.csv").write_text("x\n1\n")
        (tmp_path / ".hidden.csv").write_text("x\n1\n")
        (tmp_path / "notes.txt").write_text("x")
        got = [p.relative_to(tmp_path).as_posix()
               for p in raw_track.structured_files(tmp_path)]
        assert got == ["a.csv", "supplementary/b.xlsx"]


class TestTheRows:
    def _scan(self, tmp_path):
        (tmp_path / "data.csv").write_text(_csv_with_copied_rows())
        return raw_track.scan(tmp_path)

    def test_copied_rows_fire_and_are_one_row_per_file_and_kind(self, tmp_path):
        out = self._scan(tmp_path)
        assert out["result"]["n_row_pairs"] >= 10
        rows = raw_track.rows_v2(out, tmp_path)
        kinds = [(r["inputs"]["file"], r["inputs"]["kind"]) for r in rows]
        assert len(kinds) == len(set(kinds))
        assert ("data.csv", "row_pair") in kinds
        for r in rows:
            assert r["producer"] == "raw_data_track"
            assert r["quarantined"] is True and r["impossible"] is False
            assert r["provisional_severity"] <= 3
            assert r["finding_id"].startswith("f_")
            # groups, pairs and rows are separate counts, never folded
            assert {"n_groups_flagged", "paper_n_row_pairs",
                    "paper_n_rows_implicated"} <= set(r["inputs"])

    def test_non_accusatory_groups_file_no_rows(self, tmp_path):
        out = {"files": ["x.csv"], "result": {"duplicate_groups": [
            {"kind": "row_pair", "severity": "indeterminate", "cells": []}]}}
        assert raw_track.rows_v2(out, tmp_path) == []

    def test_a_raw_row_never_headlines(self):
        assert adjudicate._unscreened({"producer": "raw_data_track"})
        assert not adjudicate._unscreened({"producer": "tool_expert"})


class TestThePipeline:
    def test_raw_data_only_files_quarantined_rows(self, paper, fakes):
        (paper / "data.csv").write_text(_csv_with_copied_rows())
        res = _run(paper)
        rows = res["findings_v2"]["findings"]
        assert rows and {r["producer"] for r in rows} == {"raw_data_track"}
        assert res["findings_v2"]["channels"]["raw_data"]["state"] == "ran"
        assert res["is_error"] is False
        assert res["run_meta"]["stages"]["raw_data"]["ran"] is True
        assert fakes["calls"] == [], "no model is called"

    def test_no_spreadsheet_is_did_not_run_not_clean_and_not_an_error(
            self, paper, fakes):
        res = _run(paper)
        ch = res["findings_v2"]["channels"]["raw_data"]
        assert ch["state"] == "did_not_run" and ".csv" in ch["detail"]
        assert res["findings_v2"]["findings"] == []
        assert res["is_error"] is False

    def test_the_history_component_records_what_ran(self, paper, fakes):
        (paper / "data.csv").write_text(_csv_with_copied_rows())
        res = _run(paper)
        root = res["history_root"]
        from forensic_metascience_ai_toolkit.analysis_runs import read
        from pathlib import Path
        runs = read(Path(root) / ".analysis_runs" / "index.json",
                    {"runs": {}})["runs"].values()
        cp = [r for r in runs if r.get("component") == "copy_paste"]
        assert cp and cp[-1]["status"] == "completed"

    def test_the_default_run_does_not_carry_the_channel(self, paper, fakes):
        res = asyncio.run(agent.analyze_paper(
            str(paper), mode="parallel", image_forensics=False,
            text_forensics=False))
        assert "raw_data" not in res["findings_v2"]["channels"]

    def test_full_raw_data_is_a_complete_review(self):
        assert pc.load("full_raw_data").complete_review
        assert not pc.load("raw_data_only").complete_review

    def test_the_record_is_json(self, paper, fakes):
        (paper / "data.csv").write_text(_csv_with_copied_rows())
        res = _run(paper)
        json.dumps(res["run_meta"]["stages"]["raw_data"])


class TestTheRunVerb:
    """`metascience run PIPELINE PAPER` is `analyze PAPER --pipeline PIPELINE`,
    with every further analyze option passed through."""

    def test_it_runs_the_named_pipeline_and_passes_options_through(
            self, paper, fakes, monkeypatch):
        from typer.testing import CliRunner

        from forensic_metascience_ai_toolkit.cli import _analyze_out_dir, app
        monkeypatch.setattr(agent, "ensure_paper_extracted",
                            lambda *a, **k: {"failed": []})
        (paper / "data.csv").write_text(_csv_with_copied_rows())
        result = CliRunner().invoke(app, [
            "run", "raw_data_only", str(paper), "--no-usage-guard",
            "--no-pdf", "--no-bundle"])
        assert result.exit_code == 0, (result.output, result.exception)
        out, _ = _analyze_out_dir(paper, None, "opus", pc.load("raw_data_only"))
        doc = json.loads((out / "findings.v2.json").read_text())
        assert doc["pipeline"]["name"] == "raw_data_only"
        assert {f["producer"] for f in doc["findings"]} == {"raw_data_track"}
        assert fakes["calls"] == []


class TestPartialCoverageReachesTheReport:
    def test_a_partial_scan_says_so_in_the_limitations(self, paper, fakes,
                                                       monkeypatch):
        from forensic_metascience_ai_toolkit.modules.raw_data import module as raw_mod

        async def partial(paper_dir, timeout_s=None):
            return {"ran": True, "is_error": False,
                    "execution_status": "incomplete", "wall_seconds": 0.1,
                    "detail": "1 file(s), 0 group(s), coverage partial",
                    "output": {"files": ["d.csv"], "result": {
                        "duplicate_groups": [],
                        "coverage": {"status": "partial"}}}}
        monkeypatch.setattr(raw_mod, "run_raw_track", partial)
        res = _run(paper)
        assert any("PARTIAL" in l and "raw-data" in l
                   for l in res["limitations"]), res["limitations"]

    def test_a_timeout_is_named(self, paper, fakes, monkeypatch):
        from forensic_metascience_ai_toolkit.modules.raw_data import module as raw_mod

        async def timed_out(paper_dir, timeout_s=None):
            return {"ran": False, "is_error": True, "execution_status": "failed",
                    "wall_seconds": 900.0, "output": {},
                    "detail": "raw-data track timed out after 900 s; the "
                              "spreadsheets are UNSCREENED"}
        monkeypatch.setattr(raw_mod, "run_raw_track", timed_out)
        res = _run(paper)
        assert any("UNSCREENED" in l for l in res["limitations"])
        assert res["findings_v2"]["channels"]["raw_data"]["state"] == "refused"
        assert res["is_error"] is True      # the sole module failed
