"""The p-value benchmark scorer's matching rules (benchmarks/pvalue/score.py)."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("pvalue_score", ROOT / "benchmarks/pvalue/score.py")
score = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(score)


@pytest.mark.parametrize("text, keys, expected", [
    ("t(94) = −1.64, p < .001 is inconsistent", [["1.64"], [".001"]], True),
    ("OR 0.87 (0.59–1.29) printed with p = 0.049", [["0.59"], ["1.29"], ["0.049"]], True),
    ("value 1.640", [["1.64"]], True),             # trailing zero is the same number
    ("F = 12.34", [["2.34"]], False),               # not a substring of a larger number
    ("p = 0.0049", [[".049"]], False),
    ("value 1.6401", [["1.64"]], False),
    ("three of 19 versus 0 of 23; p = 0.048", [["0.048"], ["infection", "three of 19"]], True),
    ("p = 0.048 only", [["0.048"], ["infection", "3/19"]], False),  # every group must match
])
def test_key_matching(text, keys, expected):
    assert score._matches(text, keys) is expected


def test_labels_file_is_well_formed():
    rows = [json.loads(line) for line in
            (ROOT / "benchmarks/pvalue/labels_working_set.jsonl").read_text().splitlines() if line.strip()]
    assert len({r["id"] for r in rows}) == len(rows)
    assert len({r["paper_id"] for r in rows}) == 20
    for r in rows:
        assert r["tier"] in {"A", "B"} and r["kind"] in {"stat", "ci", "counts"}
        assert r["keys"] and all(r["keys"])
        # the value used to match tool calls must itself be one of the finding keys' numbers
        assert score._key_pattern(r["value"]).search(score._norm(r["raw"])), r["id"]


def test_discarded_finding_is_dismissed_not_reported(tmp_path):
    review = tmp_path / "p1" / "forensic_review_x"
    review.mkdir(parents=True)
    (review / "run_meta.json").write_text(json.dumps({"analysed_at": "2026-10-18T00:00:00Z"}))
    (review / "findings.v2.json").write_text(json.dumps({"findings": [
        {"finding_id": "f1", "title": "t(35) = 1.82 does not give p = .049", "severity": 4, "outcome": "problem",
         "adjudication": {"action": "discarded"}}]}))
    label = {"id": "l1", "paper_id": "p1", "tier": "A", "kind": "stat", "raw": "t(35) = 1.82, p = .049",
             "value": "1.82", "keys": [["1.82"], [".049"]]}
    res = score.score([label], tmp_path, "forensic_review_*")
    row = res["labels"][0]
    assert row["dismissed"] and not row["reported"]
    assert score.summarise(res)["findings"]["by_action"] == {"discarded": 1}


def test_pass_finding_does_not_report_and_merge_follows_target(tmp_path):
    review = tmp_path / "p1" / "forensic_review_x"
    review.mkdir(parents=True)
    (review / "run_meta.json").write_text(json.dumps({"analysed_at": "2026-10-18T00:00:00Z"}))
    (review / "findings.v2.json").write_text(json.dumps({"findings": [
        # a pass that prints the numbers says they reconcile: not a report
        {"finding_id": "f1", "outcome": "pass", "title": "F(1,248) = 11.01 matches p < 0.001"},
        # merged into a discarded finding: gone
        {"finding_id": "f2", "outcome": "problem", "title": "t(35) = 1.82 vs p = .049",
         "adjudication": {"action": "merged", "merged_into": "f3"}},
        {"finding_id": "f3", "outcome": "problem", "title": "summary", "adjudication": {"action": "discarded"}}]}))
    labels = [{"id": "a", "paper_id": "p1", "tier": "B", "kind": "stat", "raw": "F (1,248) = 11.01, p < 0.001",
               "value": "11.01", "keys": [["11.01"], ["0.001"]]},
              {"id": "b", "paper_id": "p1", "tier": "B", "kind": "stat", "raw": "t(35) = 1.82, p = .049",
               "value": "1.82", "keys": [["1.82"], [".049"]]}]
    rows = {r["id"]: r for r in score.score(labels, tmp_path, "forensic_review_*")["labels"]}
    assert not rows["a"]["reported"] and not rows["a"]["dismissed"]
    assert not rows["b"]["reported"] and rows["b"]["dismissed"]


def test_keys_must_be_near_each_other():
    far = "F(1,248) = 11.01 is fine. " + "x" * 300 + " SEM chi-square reported as p < 0.001"
    assert not score._matches(far, [["11.01"], ["0.001"]])
    assert score._matches("F(1,248) = 11.01, p < 0.001", [["11.01"], ["0.001"]])


def test_duplicates_and_quarantined_rows_are_not_final_findings(tmp_path):
    review = tmp_path / "p1" / "forensic_review_x"
    review.mkdir(parents=True)
    (review / "run_meta.json").write_text(json.dumps({"analysed_at": "2026-10-18T00:00:00Z"}))
    (review / "findings.v2.json").write_text(json.dumps({"findings": [
        {"finding_id": "f1", "outcome": "problem", "severity": 3, "title": "t(35) = 1.82 vs p = .049"},
        {"finding_id": "f2", "outcome": "problem", "severity": 3, "title": "t(35) = 1.82 vs p = .049",
         "duplicate_of": "f1"},
        {"finding_id": "f3", "outcome": "problem", "severity": 4, "title": "panel reuse",
         "quarantined": True},
        {"finding_id": "f4", "outcome": "problem", "severity": 2, "title": "t(35) = 1.82 again, p = .049"}]}))
    label = {"id": "a", "paper_id": "p1", "tier": "A", "kind": "stat", "raw": "t(35) = 1.82, p = .049",
             "value": "1.82", "keys": [["1.82"], [".049"]]}
    summ = score.summarise(score.score([label], tmp_path, "forensic_review_*"))
    f = summ["findings"]
    assert f["final"] == 2 and f["deduplicated"] == 1 and f["quarantined"] == 1
    assert f["final_sev3plus"] == 1
    assert summ["duplicate_reports"] == 1  # f1 and f4 both report it; f2 is a dedup copy
