"""score_judgement: interval-based severity calibration, no LLM in the loop.

The judge only NAMES the matched finding; severity is read deterministically
from findings.json. These tests pin the directional semantics: over-severity
(accusation beyond the label) and under-severity (a miss) are counted
separately, the signed bias exposes systematic drift, low-confidence labels
are excluded from aggregates, and an empty sweep is flagged rather than
scored as coverage.
"""

from __future__ import annotations

from forensic_metascience_ai_toolkit.evaluation.judge import score_judgement


def _fixture(**kf_extra):
    kf = {
        "id": "baseline",
        "weight": "critical",
        "description": "baseline uniformity",
        "reachable": True,
        "severity_expected": ["suspicious", "highly_suspicious"],
        "confidence": "high",
    }
    kf.update(kf_extra)
    return {"key_findings": [kf]}


def _parsed(covered=True, matched="f1"):
    return {"per_finding": [{
        "id": "baseline", "covered": covered,
        "evidence_quote": "…", "matched_finding_id": matched,
    }], "false_positives": []}


def _findings(severity="suspicious"):
    return {"findings": [{"id": "f1", "severity": severity}]}


class TestIntervalScoring:
    def test_in_interval(self):
        out = score_judgement(_fixture(), _parsed(), _findings("suspicious"))
        cal = out["severity_calibration"]
        assert cal["n_scored"] == 1 and cal["n_in_interval"] == 1
        assert cal["n_over_severity"] == cal["n_under_severity"] == 0
        row = out["per_finding"][0]
        assert row["severity_in_interval"] is True
        assert row["matched_severity"] == "suspicious"

    def test_interval_endpoints_are_inclusive(self):
        out = score_judgement(_fixture(), _parsed(), _findings("highly_suspicious"))
        assert out["severity_calibration"]["n_in_interval"] == 1

    def test_over_severity_is_an_over_accusation(self):
        out = score_judgement(_fixture(), _parsed(), _findings("impossible"))
        cal = out["severity_calibration"]
        assert cal["n_over_severity"] == 1 and cal["n_under_severity"] == 0
        assert out["per_finding"][0]["severity_direction"] == "over"
        assert cal["severity_bias"] > 0

    def test_under_severity_is_a_miss(self):
        out = score_judgement(_fixture(), _parsed(), _findings("consistent"))
        cal = out["severity_calibration"]
        assert cal["n_under_severity"] == 1 and cal["n_over_severity"] == 0
        assert cal["severity_bias"] < 0

    def test_signed_bias_detects_systematic_hedging(self):
        # Two findings both one tier below their intervals: bias is negative
        # and its magnitude is the sum of the drifts.
        fixture = {"key_findings": [
            {"id": "a", "weight": "major", "reachable": True,
             "severity_expected": ["highly_suspicious", "highly_suspicious"],
             "confidence": "high"},
            {"id": "b", "weight": "major", "reachable": True,
             "severity_expected": ["highly_suspicious", "highly_suspicious"],
             "confidence": "high"},
        ]}
        parsed = {"per_finding": [
            {"id": "a", "covered": True, "matched_finding_id": "fa"},
            {"id": "b", "covered": True, "matched_finding_id": "fb"},
        ], "false_positives": []}
        findings = {"findings": [
            {"id": "fa", "severity": "suspicious"},
            {"id": "fb", "severity": "suspicious"},
        ]}
        cal = score_judgement(fixture, parsed, findings)["severity_calibration"]
        assert cal["severity_bias"] == -2.0
        assert cal["n_under_severity"] == 2

    def test_low_confidence_excluded_from_aggregates(self):
        out = score_judgement(
            _fixture(confidence="low"), _parsed(), _findings("impossible"))
        cal = out["severity_calibration"]
        assert cal["n_scored"] == 0 and cal["n_over_severity"] == 0
        assert cal["n_excluded_low_confidence"] == 1
        # ... but the row itself still reports what happened.
        assert out["per_finding"][0]["severity_direction"] == "over"

    def test_covered_in_prose_only_is_unmatched_not_guessed(self):
        out = score_judgement(_fixture(), _parsed(matched=""), _findings())
        cal = out["severity_calibration"]
        assert cal["n_scored"] == 0
        assert cal["n_covered_but_unmatched"] == 1
        assert out["per_finding"][0]["severity_in_interval"] is None

    def test_unknown_matched_id_is_unmatched(self):
        out = score_judgement(_fixture(), _parsed(matched="nope"), _findings())
        assert out["severity_calibration"]["n_covered_but_unmatched"] == 1

    def test_allow_undecided_accepts_a_matched_undecided_row(self):
        """Fixture v2: allow_undecided says outcome-undecided is a legitimate
        landing. A matched REAL finding carrying no severity scores as
        allowed (excluded from aggregates), not as covered-but-unmatched."""
        findings = {"findings": [{"slug": "f1", "finding_id": "f_" + "a" * 16,
                                  "outcome": "undecided"}]}
        out = score_judgement(
            _fixture(severity_expected=[2, 3], allow_undecided=True),
            _parsed(matched="f1"), findings)
        cal = out["severity_calibration"]
        assert cal["n_covered_but_unmatched"] == 0
        assert cal["n_excluded_low_confidence"] == 1
        assert cal["n_scored"] == 0
        assert out["per_finding"][0]["severity_direction"] == "undecided_allowed"

    def test_allow_undecided_does_not_bless_an_unknown_id(self):
        """A matched id that names NO real finding is still unmatched --
        allow_undecided is about a genuine undecided row, not about the
        judge inventing an id."""
        out = score_judgement(
            _fixture(severity_expected=[2, 3], allow_undecided=True),
            _parsed(matched="ghost"), _findings())
        assert out["severity_calibration"]["n_covered_but_unmatched"] == 1

    def test_without_allow_undecided_a_severity_less_match_is_unmatched(self):
        findings = {"findings": [{"slug": "f1", "outcome": "undecided"}]}
        out = score_judgement(
            _fixture(severity_expected=[2, 3]),
            _parsed(matched="f1"), findings)
        assert out["severity_calibration"]["n_covered_but_unmatched"] == 1

    def test_finding_without_interval_is_untouched(self):
        fixture = {"key_findings": [{
            "id": "baseline", "weight": "critical", "reachable": True,
        }]}
        out = score_judgement(fixture, _parsed(), _findings())
        assert "severity_expected" not in out["per_finding"][0]
        assert out["severity_calibration"]["n_scored"] == 0


class TestRecallUnchanged:
    def test_weighted_recall_still_computed(self):
        out = score_judgement(_fixture(), _parsed(), _findings())
        assert out["recall_weighted"] == 1.0

    def test_uncovered_finding_scores_zero(self):
        out = score_judgement(_fixture(), _parsed(covered=False), _findings())
        assert out["recall_weighted"] == 0.0
        assert out["severity_calibration"]["n_scored"] == 0


class TestStarvation:
    def test_empty_sweep_is_flagged(self):
        out = score_judgement(_fixture(), _parsed(covered=False), {"findings": []})
        assert out["no_findings_produced"] is True

    def test_none_findings_is_flagged(self):
        out = score_judgement(_fixture(), _parsed(covered=False), None)
        assert out["no_findings_produced"] is True

    def test_nonempty_sweep_is_not_flagged(self):
        out = score_judgement(_fixture(), _parsed(), _findings())
        assert out["no_findings_produced"] is False
