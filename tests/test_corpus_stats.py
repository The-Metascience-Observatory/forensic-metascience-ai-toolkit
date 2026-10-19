"""corpus_stats: the denominator rules, tested on fixtures built to trip them."""

import json
from pathlib import Path

from metascience_agent import corpus_stats as CS


def _paper(root, name, findings, channels, journal="Journal of Testing",
           year=2020):
    p = root / name
    p.mkdir()
    (p / "findings.v2.json").write_text(json.dumps({
        "schema_version": "2.0", "paper_id": name, "run_id": f"r_{name}",
        "paper_metadata": {"journal_normalized": journal, "year": year},
        "channels": {k: {"state": v} for k, v in channels.items()},
        "findings": findings,
        "adjudication": {"ran": True},
        "analysed_at": "2026-08-21T00:00:00Z"}))
    return p


def _f(sev=5, outcome="problem", producer="tool_expert",
       technique="grim_check", action=None, impossible=False):
    row = {"finding_id": "f_" + "0" * 16, "producer": producer,
           "technique": technique, "outcome": outcome, "severity": sev,
           "impossible": impossible, "computed_by": "registry_tool"}
    if action:
        row["adjudication"] = {"action": action}
    return row


class TestDenominators:
    def test_ran_result_discarded_counts_as_ran(self, tmp_path):
        _paper(tmp_path, "a", [_f()], {"tool_expert": "ran"})
        _paper(tmp_path, "b", [], {"tool_expert": "ran_result_discarded"})
        _paper(tmp_path, "c", [], {"tool_expert": "refused"})
        stats = CS.compute(tmp_path)
        row = next(r for r in stats["per_technique"]
                   if r["technique"] == "grim_check")
        assert row["n_papers_ran"] == 2, \
            "a channel that ran and retained nothing STILL RAN"
        assert row["n_papers_fired"] == 1
        assert stats["channel_status"]["tool_expert"]["refused"] == 1

    def test_zero_finding_papers_stay_in_the_denominator(self, tmp_path):
        _paper(tmp_path, "a", [_f()], {"tool_expert": "ran"})
        for name in ("b", "c", "d"):
            _paper(tmp_path, name, [], {"tool_expert": "ran"})
        stats = CS.compute(tmp_path)
        row = stats["per_technique"][0]
        assert row["n_papers_ran"] == 4 and row["fire_rate"] == 0.25


class TestFireDiscipline:
    def test_discarded_rows_are_never_fires(self, tmp_path):
        _paper(tmp_path, "a",
               [_f(), _f(action="discarded")], {"tool_expert": "ran"})
        stats = CS.compute(tmp_path)
        row = stats["per_technique"][0]
        assert row["n_discarded_by_adjudicator"] == 1
        assert row["n_findings"]["problem"] == 2
        assert row["by_severity"] == {"5": 1}

    def test_screen_flags_are_a_funnel_not_fires(self, tmp_path):
        _paper(tmp_path, "a", [_f(producer="fast_screen", sev=4)],
               {"tool_expert": "ran"})
        stats = CS.compute(tmp_path)
        row = stats["per_technique"][0]
        assert row["n_papers_fired"] == 0
        assert row["n_screen_flags"] == 1

    def test_impossible_counts_per_technique(self, tmp_path):
        _paper(tmp_path, "a", [_f(impossible=True)], {"tool_expert": "ran"})
        stats = CS.compute(tmp_path)
        assert stats["per_technique"][0]["n_impossible"] == 1


class TestGrouping:
    def test_by_journal_uses_the_normalized_name(self, tmp_path):
        _paper(tmp_path, "a", [_f()], {"tool_expert": "ran"},
               journal="The Journal of Neuroscience")
        _paper(tmp_path, "b", [], {"tool_expert": "ran"},
               journal="The Journal of Neuroscience")
        stats = CS.compute(tmp_path)
        j = stats["by_journal"][0]
        assert j["journal_normalized"] == "The Journal of Neuroscience"
        assert j["n_papers"] == 2 and j["n_papers_fired"] == 1
        assert j["worst_severity"] == 5

    def test_current_doc_prefers_the_dated_run(self, tmp_path):
        p = tmp_path / "a"
        run1 = p / "forensic_review_old"
        run2 = p / "forensic_review_new"
        for run, when, sev in ((run1, "2026-01-01T00:00:00Z", 3),
                               (run2, "2026-08-01T00:00:00Z", 7)):
            run.mkdir(parents=True)
            (run / "findings.v2.json").write_text(json.dumps({
                "schema_version": "2.0", "paper_id": "a",
                "run_id": f"r_{run.name}", "analysed_at": when,
                "channels": {"tool_expert": {"state": "ran"}},
                "findings": [_f(sev=sev)], "adjudication": {"ran": True}}))
        stats = CS.compute(tmp_path)
        assert stats["per_technique"][0]["by_severity"] == {"7": 1}, \
            "stats must read the CURRENT run, not every run"
