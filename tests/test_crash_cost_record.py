"""A run that crashes must still say what it cost.

`run_meta.json` is written at the END of a successful analysis, so any
exception before that point left real money spent and nothing recording it.
Measured on 2026-08-09: a paper carrying a 2.1 MB .docx supplement died at
`subprocess.Popen` AFTER a 22-minute stage-1 sweep. The sweep had been paid
for; the only evidence it had cost anything was a wall-clock gap in a log.

Silent loss of a cost record is the accounting cousin of the failure pattern
this codebase keeps finding elsewhere: something goes wrong on our side and the
output does not say so.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit.agent import record_spend, reset_spend, spend_so_far

REPO = Path(__file__).resolve().parent.parent


class TestTheSpendLedger:
    def setup_method(self):
        reset_spend()

    def test_it_starts_empty(self):
        assert spend_so_far() == {"total_cost_usd": 0.0, "stages": []}

    def test_it_accumulates_across_stages(self):
        record_spend("stage1_sweep", {"cost_usd": 4.31, "wall_seconds": 1320})
        record_spend("stage2_editorial", {"cost_usd": 2.08, "wall_seconds": 300})
        s = spend_so_far()
        assert s["total_cost_usd"] == pytest.approx(6.39)
        assert [x["stage"] for x in s["stages"]] == ["stage1_sweep", "stage2_editorial"]

    def test_a_stage_with_no_cost_field_does_not_crash_the_ledger(self):
        """The ledger runs on the failure path, so it must not add a failure."""
        record_spend("stage1_sweep", {})
        assert spend_so_far()["total_cost_usd"] == 0.0

    def test_reset_prevents_one_paper_being_billed_to_the_next(self):
        record_spend("stage1_sweep", {"cost_usd": 4.31})
        reset_spend()
        assert spend_so_far()["total_cost_usd"] == 0.0

    def test_the_snapshot_is_a_copy_not_the_live_ledger(self):
        """A caller writing the crash record must not be able to mutate it."""
        record_spend("stage1_sweep", {"cost_usd": 1.0})
        snap = spend_so_far()
        snap["stages"].append({"stage": "forged"})
        assert len(spend_so_far()["stages"]) == 1


class TestAnalyzeDoesNotDumpTheReport:
    """The report is the file. The terminal summary is verdict, counts,
    runtime -- not the markdown, not the paths, not the cost.
    """

    def test_analyze_does_not_print_the_report_markdown(self):
        import inspect

        from forensic_metascience_ai_toolkit.cli import analyze

        src = inspect.getsource(analyze)
        assert "Markdown(result[\"report\"])" not in src
        assert "Markdown(result['report'])" not in src
        assert "Review written to" not in src
        assert "_print_analyze_summary" in src


class TestAnalyzeSummary:
    def test_counts_every_rung_including_zeros(self):
        from forensic_metascience_ai_toolkit.cli import _finding_counts

        counts = _finding_counts({
            "report_obj": {"findings": [
                {"severity": "impossible"},
                {"severity": "suspicious"},
                {"severity": "suspicious"},
            ]},
        })
        assert counts == {
            "impossible": 1, "highly_suspicious": 0, "suspicious": 2,
            "indeterminate": 0, "consistent": 0,
        }

    def test_a_failed_editorial_falls_back_to_the_sweep(self):
        """Five zeros on a sweep that found things would read as a clean paper."""
        from forensic_metascience_ai_toolkit.cli import _finding_counts

        counts = _finding_counts({
            "report_obj": None,
            "findings": {"findings": [
                {"severity": "highly_suspicious"},
                {"severity": "consistent"},
            ]},
        })
        assert counts["highly_suspicious"] == 1
        assert counts["consistent"] == 1

    def test_an_unrecognised_severity_is_not_dumped_into_indeterminate(self):
        from forensic_metascience_ai_toolkit.cli import _finding_counts

        counts = _finding_counts({
            "report_obj": {"findings": [{"severity": "not-a-rung"}]},
        })
        assert counts["indeterminate"] == 0

    def test_runtime_format(self):
        from forensic_metascience_ai_toolkit.cli import _fmt_runtime

        assert _fmt_runtime(None) == "not recorded"
        assert _fmt_runtime(12.34) == "12.3s"
        assert _fmt_runtime(125) == "2m 5s"
        assert _fmt_runtime(3665) == "1h 1m 5s"
        assert _fmt_runtime(7323) == "2h 2m 3s"

    def test_summary_prints_verdict_counts_runtime_only(self, capsys):
        from forensic_metascience_ai_toolkit.cli import _print_analyze_summary

        _print_analyze_summary({
            "verdict": "does_not_reconcile",
            "confidence": "high",
            "total_wall_seconds": 90.2,
            "total_cost_usd": 4.97,
            "report_obj": {"findings": [
                {"severity": "impossible"},
                {"severity": "consistent"},
            ]},
        })
        text = " ".join(capsys.readouterr().out.split())
        assert "does not reconcile" in text.lower() or "does_not_reconcile" in text
        assert "1 impossible" in text
        assert "1 consistent" in text
        assert "0 highly_suspicious" in text
        assert "1m 30s" in text
        assert "4.97" not in text
        assert "confidence" not in text.lower()
