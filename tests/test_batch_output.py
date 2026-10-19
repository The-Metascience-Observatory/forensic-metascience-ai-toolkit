"""What `metascience batch` prints must describe THIS run, and say so.

Four defects seen watching the GRIM ground-truth dev set (`--pipeline
tools_only`, ten papers, three batches) on 2026-10-18:

1. "Batch cost: $26.47" on a batch whose papers cost $9.53: the summary summed
   every `batch_costs.jsonl` row for this batch's paper NAMES, and the ledger
   held all three batches of the same ten papers.
2. The plan table rendered an empty boxed header row (blank column titles).
3. The toolkit's own `.analysis_runs/` folder was counted as a paper with no
   full text: "papers found 11", "SKIP .analysis_runs".
4. Each per-paper line on a tools_only run said "(verdict: -, ...)".

Nothing here spends money: `analyze_paper` is faked and the backend probe is
blocked by the conftest guard (it fails open).
"""
import json
import re
from pathlib import Path

from typer.testing import CliRunner

from forensic_metascience_ai_toolkit import adjudicate
from forensic_metascience_ai_toolkit import batch as batch_mod
from forensic_metascience_ai_toolkit.cli import app
from forensic_metascience_ai_toolkit.pipeline_config import load as load_pipeline

runner = CliRunner()


def _corpus(tmp_path, n=2, empty=(), archive=True):
    """`n` readable papers, `empty` named folders with nothing to read, and
    (by default) the `.analysis_runs/` archive a previous batch leaves behind."""
    root = tmp_path / "corpus"
    root.mkdir()
    for i in range(n):
        d = root / f"10.1234--paper{i:03d}"
        d.mkdir()
        (d / "body.md").write_text(f"# body of paper {i}")
    for name in empty:
        (root / name).mkdir()
    if archive:
        (root / ".analysis_runs" / "runs").mkdir(parents=True)
        (root / ".analysis_runs" / "index.json").write_text('{"runs": {}}')
    return root


def _fake_result(cost):
    return {
        "mode": "parallel",
        "report": "# ok",
        "findings_v2": {"schema_version": "2.0", "paper_id": "p", "findings": [],
                        "adjudication": adjudicate.apply_skip(
                            [], skipped_reason="adjudication not configured "
                            "in pipeline 'tools_only'")[1]},
        "is_error": False,
        "verdict": None,
        "total_cost_usd": cost,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_wall_seconds": 1.0,
        "run_meta": {"stages": {}},
    }


def _patch_live(monkeypatch, cost_by_paper):
    async def fake_analyze(path, **kwargs):
        return _fake_result(cost_by_paper[Path(path).name])

    async def no_guard(*a, **k):
        return None

    monkeypatch.setattr(batch_mod, "analyze_paper", fake_analyze)
    monkeypatch.setattr(batch_mod, "write_parallel_outputs", lambda *a, **k: None)
    monkeypatch.setattr(batch_mod, "usage_guard", no_guard)


_BARS = "│┃|"


def _empty_table_rows(output: str) -> list[str]:
    """Lines that are a table row with nothing in any cell. Rich draws the
    header row with HEAVY bars (┃), body rows with light ones (│); counting
    only the light bar passed on the very header row this exists to catch."""
    rows = []
    for line in output.splitlines():
        if sum(line.count(b) for b in _BARS) >= 2 and not line.strip(
                _BARS + " "):
            rows.append(line)
    return rows


class TestBatchCostIsThisRun:
    def test_earlier_batches_of_the_same_papers_are_not_summed(
            self, tmp_path, monkeypatch):
        """KNOWN POSITIVE: the GRIM dev corpus shape -- the same papers'
        names already in the ledger from earlier batches."""
        root = _corpus(tmp_path, 2)
        earlier = "".join(
            json.dumps({"paper": f"10.1234--paper{i:03d}", "model": "sonnet",
                        "total_cost_usd": 5.0}) + "\n"
            for _ in range(2) for i in range(2))
        (root / "batch_costs.jsonl").write_text(earlier)
        _patch_live(monkeypatch, {"10.1234--paper000": 0.25,
                                  "10.1234--paper001": 0.5})
        r = runner.invoke(app, ["batch", str(root), "--workers", "1",
                                "--backend", "claude", "--no-move-to-done"])
        assert r.exit_code == 0, r.output
        assert "Batch cost (this run): $0.75" in r.output, r.output
        # The corpus total survives, labelled as the whole history.
        out = r.output
        assert "Usage for this corpus (all recorded runs)" in out
        row = next(l for l in out.splitlines()
                   if "API-equivalent cost, all runs" in l)
        assert "$20.75" in row, row
        row = next(l for l in out.splitlines() if "paper runs recorded" in l)
        assert "6" in row and "2 distinct papers" in row, row

    def test_a_refused_paper_is_billed_to_this_run(self, tmp_path, monkeypatch):
        """A ForensicToolsNeverRan refusal is written to the ledger with its
        spend; leaving it out of this run's total understated the batch."""
        from forensic_metascience_ai_toolkit.llm_backend import ForensicToolsNeverRan
        root = _corpus(tmp_path, 2)

        async def fake_analyze(path, **kwargs):
            if Path(path).name == "10.1234--paper001":
                raise ForensicToolsNeverRan(
                    "no tools", stage={"cost_usd": 0.125, "messages": []})
            return _fake_result(0.25)

        async def no_guard(*a, **k):
            return None

        monkeypatch.setattr(batch_mod, "analyze_paper", fake_analyze)
        monkeypatch.setattr(batch_mod, "write_parallel_outputs",
                            lambda *a, **k: None)
        monkeypatch.setattr(batch_mod, "usage_guard", no_guard)
        r = runner.invoke(app, ["batch", str(root), "--workers", "1",
                                "--backend", "claude", "--no-move-to-done"])
        assert "Batch cost (this run): $0.38" in r.output, r.output


class TestTablesHaveNoEmptyHeader:
    def test_plan_table(self, tmp_path):
        r = runner.invoke(app, ["batch", str(_corpus(tmp_path)), "--dry-run",
                                "--backend", "claude"])
        assert r.exit_code == 0, r.output
        assert "Batch plan" in r.output
        assert not _empty_table_rows(r.output), r.output

    def test_usage_table(self, tmp_path):
        root = _corpus(tmp_path)
        (root / "batch_costs.jsonl").write_text(
            json.dumps({"paper": "a", "total_cost_usd": 1.0}) + "\n")
        r = runner.invoke(app, ["usage", str(root)])
        assert r.exit_code == 0, r.output
        assert "paper runs recorded" in r.output
        assert not _empty_table_rows(r.output), r.output


class TestInternalFoldersAreNotPapers:
    def test_pick_papers_skips_dot_folders_and_keeps_empty_papers(self, tmp_path):
        root = _corpus(tmp_path, 2, empty=("10.1234--no-text",))
        (root / ".extraction_cache").mkdir()
        names = [p.name for p in batch_mod.pick_papers(root, 100, None)]
        assert names == ["10.1234--no-text", "10.1234--paper000",
                         "10.1234--paper001"]

    def test_plan_counts_real_papers_and_still_names_the_one_without_text(
            self, tmp_path):
        """KNOWN POSITIVE: the GRIM dev corpus after its first batch -- ten
        papers plus `.analysis_runs/`, which read as "papers found 11"."""
        root = _corpus(tmp_path, 2, empty=("10.1234--no-text",))
        r = runner.invoke(app, ["batch", str(root), "--dry-run",
                                "--backend", "claude"])
        assert r.exit_code == 0, r.output
        assert ".analysis_runs" not in r.output, r.output
        row = next(l for l in r.output.splitlines() if "papers found" in l)
        assert re.search(r"\b3\b", row), row
        # A real paper with nothing to read is still counted AND named.
        assert "no full text" in r.output
        assert "SKIP  10.1234--no-text" in r.output
        row = next(l for l in r.output.splitlines() if "to run" in l)
        assert re.search(r"\b2\b", row), row


class TestVerdictLabel:
    def test_tools_only_says_it_was_not_adjudicated(self):
        label = batch_mod._verdict_label(_fake_result(0.1),
                                         load_pipeline("tools_only"))
        assert "no adjudicator" in label and "provisional" in label
        assert label != "-"

    def test_an_adjudicated_verdict_is_printed_as_is(self):
        result = {**_fake_result(0.1), "verdict": "does_not_reconcile"}
        assert batch_mod._verdict_label(result, None) == "does_not_reconcile"

    def test_a_skipped_adjudicator_in_the_full_pipeline(self):
        result = _fake_result(0.1)
        result["findings_v2"]["adjudication"] = adjudicate.apply_skip(
            [], failure="adjudicator crashed")[1]
        assert "adjudicator failed" in batch_mod._verdict_label(result, None)

    def test_the_per_paper_line_on_a_tools_only_batch(self, tmp_path,
                                                       monkeypatch):
        root = _corpus(tmp_path, 1)
        _patch_live(monkeypatch, {"10.1234--paper000": 0.76})
        r = runner.invoke(app, ["batch", str(root), "--workers", "1",
                                "--backend", "claude", "--pipeline",
                                "tools_only", "--no-move-to-done"])
        assert r.exit_code == 0, r.output
        line = next(l for l in r.output.splitlines() if "(verdict:" in l)
        assert "verdict: -" not in line, line
        assert "no adjudicator" in line and "$0.76" in line, line


class TestBatchBuildsTheViewer:
    """`analyze` (and so `run`) builds the offline viewer by default; a paper
    reviewed by `batch` used to get only the machine's notes."""

    def _record_bundles(self, monkeypatch, fail=False):
        calls = []

        def fake_build(out_dir, paper):
            calls.append((Path(out_dir), Path(paper)))
            return "OSError: disk full" if fail else None

        monkeypatch.setattr(batch_mod, "_build_viewer", fake_build)
        return calls

    def test_each_finished_paper_gets_a_viewer(self, tmp_path, monkeypatch):
        root = _corpus(tmp_path, 2)
        _patch_live(monkeypatch, {"10.1234--paper000": 0.1,
                                  "10.1234--paper001": 0.1})
        calls = self._record_bundles(monkeypatch)
        r = runner.invoke(app, ["batch", str(root), "--workers", "1",
                                "--backend", "claude", "--no-move-to-done"])
        assert r.exit_code == 0, r.output
        assert sorted(p.name for _, p in calls) == [
            "10.1234--paper000", "10.1234--paper001"]
        # Built from the review folder that paper's run just wrote.
        assert all(out.parent == paper for out, paper in calls)

    def test_no_bundle_skips_it(self, tmp_path, monkeypatch):
        root = _corpus(tmp_path, 1)
        _patch_live(monkeypatch, {"10.1234--paper000": 0.1})
        calls = self._record_bundles(monkeypatch)
        r = runner.invoke(app, ["batch", str(root), "--workers", "1",
                                "--backend", "claude", "--no-move-to-done",
                                "--no-bundle"])
        assert r.exit_code == 0, r.output
        assert calls == []

    def test_a_failed_viewer_does_not_fail_the_paper(self, tmp_path,
                                                     monkeypatch):
        root = _corpus(tmp_path, 1)
        _patch_live(monkeypatch, {"10.1234--paper000": 0.1})
        self._record_bundles(monkeypatch, fail=True)
        r = runner.invoke(app, ["batch", str(root), "--workers", "1",
                                "--backend", "claude", "--no-move-to-done"])
        assert r.exit_code == 0, r.output
        assert "viewer bundle failed" in r.output
        assert "metascience bundle" in r.output
        assert "OK ->" in r.output
        assert not (root / "failed.jsonl").exists()

    def test_the_real_builder_reports_rather_than_raises(self, tmp_path):
        err = batch_mod._build_viewer(tmp_path / "missing", tmp_path)
        assert err and "missing" in err

    def test_the_standalone_parser_defaults_on(self):
        p = batch_mod.build_parser()
        assert p.parse_args(["c"]).bundle is True
        assert p.parse_args(["c", "--no-bundle"]).bundle is False
