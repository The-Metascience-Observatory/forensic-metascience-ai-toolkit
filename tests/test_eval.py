"""Tests for the evaluation harness.

The deterministic checks and fixture loading run offline and free. The full
live eval (real claude calls, real cost) is gated behind RUN_EVAL=1.
"""

import json
import os
from pathlib import Path

import pytest

from metascience_agent.core import prompts
from metascience_agent.evaluation import deterministic
from metascience_agent.evaluation.harness import load_fixtures, repo_root

FIXTURES_DIR = repo_root() / "benchmarks" / "paper_reviews" / "fixtures"


class TestFixtures:
    def test_fixtures_load_and_are_well_formed(self):
        fixtures = load_fixtures(FIXTURES_DIR)
        assert {f["paper"] for f in fixtures} == {
            "apple_cider", "airforce", "wound_healing", "cerebrolysin_flow"
        }
        for f in fixtures:
            # Against the SCHEMA's enum, not a literal triple. This line held a
            # hardcoded copy of the retired vocabulary and so failed the moment
            # the words were renamed -- a test asserting that a rename had not
            # happened, in a file about whether fixtures are well formed.
            assert f["verdict_expected"] in prompts.VERDICT_VALUES
            assert (repo_root() / f["pdf"]).exists(), f["pdf"]
            # gold_review is optional: cerebrolysin_flow is a REGRESSION
            # fixture labeled from a validated pipeline run, not a human
            # gold review.
            if f.get("gold_review"):
                assert (repo_root() / f["gold_review"]).exists(), \
                    f["gold_review"]
            for kf in f["key_findings"]:
                assert kf["weight"] in ("critical", "major", "minor")
                assert kf["id"] and kf["description"]
                # Fixture format v2: severity intervals are integers on the
                # 1-9 ladder. A stray 5-enum string here would make the
                # judge report incomparable_eras on every row.
                for bound in kf.get("severity_expected", []):
                    assert isinstance(bound, int) and 1 <= bound <= 9, \
                        (f["paper"], kf["id"], bound)
            # every fixture pins the single most important finding as critical
            assert any(kf["weight"] == "critical" for kf in f["key_findings"])

    def test_must_not_say_patterns_compile(self):
        import re
        for f in load_fixtures(FIXTURES_DIR):
            for pattern in f.get("must_not_say", []):
                re.compile(pattern)

    def test_must_not_say_catches_historical_failure(self):
        """The apple-cider fixture must catch the actual failure text from the
        old agent report ('no suspicious uniformity ... CONSISTENT')."""
        fixture = load_fixtures(FIXTURES_DIR, only="apple_cider")[0]
        bad_report = (
            "## Finding 6\nCSF test shows no suspicious uniformity (p=0.91) "
            "- CONSISTENT"
        )
        result = deterministic.check_must_not_say(
            bad_report, fixture["must_not_say"]
        )
        assert result["passed"] is False


class TestDeterministicChecks:
    def test_findings_json_valid(self):
        findings = {
            "schema_version": "1.0",
            "paper_id": "x",
            "findings": [{
                "id": "a", "location": "Table 1", "technique": "grim",
                "consistent": False, "severity": "impossible",
                "reproduction": "metascience grim 3.51 30",
            }],
            "coverage": {"stats_found": 1, "tools_run": ["grim"]},
        }
        result = deterministic.check_findings_json(findings)
        assert result["passed"], result["problems"]

    def test_findings_json_bad_severity(self):
        findings = {
            "findings": [{
                "id": "a", "location": "x", "technique": "grim",
                "severity": "IMPOSSIBLE",  # wrong case
                "reproduction": "cmd",
            }],
            "coverage": {},
        }
        result = deterministic.check_findings_json(findings)
        assert not result["passed"]
        assert any("invalid severity" in p for p in result["problems"])

    def test_preamble_detected(self):
        for bad in (
            "Now I have all the data needed for the full report. Here it is:",
            "The SPRITE analysis fails because the standard deviations are impossible",
            "Let me compile the findings into a report.",
            "Here is the full report:",
        ):
            assert deterministic.check_no_preamble(bad)["passed"] is False, bad

    def test_clean_report_passes(self):
        good = (
            "# Forensic review: Apple cider vinegar RCT\n\n"
            "This is a forensic review of a randomized trial of apple cider "
            "vinegar for weight loss."
        )
        assert deterministic.check_no_preamble(good)["passed"] is True

    def test_empty_report_fails(self):
        assert deterministic.check_no_preamble("")["passed"] is False

    def test_verdict_check(self):
        assert deterministic.check_verdict("untrustworthy", "untrustworthy")["passed"]
        assert not deterministic.check_verdict("trustworthy", "untrustworthy")["passed"]
        assert not deterministic.check_verdict(None, "untrustworthy")["passed"]


class TestJudgeScoring:
    def test_weights(self):
        from metascience_agent.evaluation.judge import WEIGHTS
        assert WEIGHTS == {"critical": 3, "major": 2, "minor": 1}

    def test_judge_schema_is_valid_json_schema_shape(self):
        from metascience_agent.evaluation.judge import JUDGE_SCHEMA
        assert JUDGE_SCHEMA["type"] == "object"
        assert "per_finding" in JUDGE_SCHEMA["properties"]


@pytest.mark.eval
@pytest.mark.skipif(
    os.environ.get("RUN_EVAL") != "1",
    reason="live eval costs money; set RUN_EVAL=1 to run",
)
class TestLiveEval:
    def test_full_eval(self):
        from metascience_agent.evaluation.harness import main

        rc = main(["--max-budget-usd", os.environ.get("EVAL_BUDGET", "3.0")])
        scorecard_path = repo_root() / "benchmarks" / "paper_reviews" / "runs" / "scorecard.json"
        assert scorecard_path.exists()
        scorecards = json.loads(scorecard_path.read_text())
        # Acceptance target: apple-cider baseline uniformity is covered and
        # the verdict matches on all three papers.
        apple = next(s for s in scorecards if s["paper"] == "apple_cider")
        baseline = next(
            f for f in apple["judge"]["per_finding"]
            if f["id"] == "baseline_uniformity"
        )
        assert baseline["covered"], "baseline uniformity finding was missed"
        assert rc == 0, "verdict mismatch or deterministic failure (see scorecard)"
