"""The eval harness's findings-v2 slice: deterministic invariants + integer
severity intervals in the judge."""

from forensic_metascience_ai_toolkit.evaluation.deterministic import check_findings_json


def v2doc(findings, adj=None):
    return {"schema_version": "2.0", "paper_id": "p", "run_id": "r_1",
            "findings": findings,
            "adjudication": adj or {"ran": True, "n_discarded": 0}}


def row(**kw):
    r = {"finding_id": "f_" + "0" * 16, "slug": "s1", "producer": "tool_expert",
         "technique": "grim_check", "title": "a title long enough here",
         "description": "a description easily long enough to pass the bounds",
         "outcome": "problem", "severity": 5,
         "adjudication": {"action": "kept"}}
    r.update(kw)
    return r


class TestV2Dispatch:
    def test_v2_documents_take_the_v2_path(self):
        out = check_findings_json(v2doc([row()]))
        assert out["passed"] and out.get("schema") == "2.0"

    def test_v1_documents_keep_the_v1_path(self):
        out = check_findings_json({"findings": [], "coverage": {}})
        assert "schema" not in out


class TestV2Invariants:
    def test_severity_on_a_pass_row_fails(self):
        out = check_findings_json(v2doc([row(outcome="pass", severity=3)]))
        assert not out["passed"]
        assert any("carries a severity" in p for p in out["problems"])

    def test_impossible_requires_a_validated_tool_verdict(self):
        bad = row(impossible=True)
        out = check_findings_json(v2doc([bad]))
        assert any("without a validated impossible" in p
                   for p in out["problems"])
        good = row(impossible=True,
                   tool_verdict={"severity": "impossible", "tool": "grim_check",
                                 "validated": True})
        assert check_findings_json(v2doc([good]))["passed"]

    def test_discarded_rows_must_stay_and_stay_unranked(self):
        discarded = row(severity=None,
                        adjudication={"action": "discarded"})
        out = check_findings_json(v2doc([row(), discarded],
                                        adj={"ran": True, "n_discarded": 1}))
        assert out["passed"]
        lying = v2doc([row()], adj={"ran": True, "n_discarded": 3})
        out2 = check_findings_json(lying)
        assert any("must be RETAINED" in p for p in out2["problems"])

    def test_adjudicated_problem_rows_need_a_severity(self):
        out = check_findings_json(v2doc([row(severity=None)]))
        assert any("no severity" in p for p in out["problems"])

    def test_missing_adjudication_record_fails(self):
        out = check_findings_json({"schema_version": "2.0",
                                   "findings": [row()]})
        assert any("adjudication record" in p for p in out["problems"])

    def test_unrun_cross_check_must_be_provisional(self):
        stamped = row(cross_check="not_run", severity_is_provisional=False)
        out = check_findings_json(v2doc([stamped]))
        assert any("unrun cross-check" in p for p in out["problems"])


class TestJudgeIntegerIntervals:
    def _score(self, matched_sev):
        from forensic_metascience_ai_toolkit.evaluation.judge import score_judgement
        fixture = {"key_findings": [
            {"id": "k1", "weight": "major", "severity_expected": [3, 5]}]}
        parsed = {"per_finding": [
            {"id": "k1", "covered": True, "matched_finding_id": "s1"}],
            "false_positives": []}
        findings = v2doc([row(severity=matched_sev)])
        rec = score_judgement(fixture, parsed, findings)
        return next(e for e in rec["per_finding"] if e["id"] == "k1")

    def test_in_interval(self):
        e = self._score(4)
        assert e["severity_direction"] == "in"
        assert e["severity_in_interval"] is True
        assert e["matched_severity"] == 4

    def test_over_and_under(self):
        assert self._score(7)["severity_direction"] == "over"
        assert self._score(2)["severity_direction"] == "under"
