"""The sandbox audit's headline must count v2 rows, and only real ones.

Two defects, fixed together on purpose. Measured on the ten litvak control
runs: `sandbox_audit.json` read "clean: every tool call was on the validated
forensic surface" with `n_unbacked_findings: 0`, while stage records in the
same runs said `BREACH (unbacked): 8` and `BREACH (unbacked): 14`.
"""
from forensic_metascience_ai_toolkit.agent import _unbacked_findings
from forensic_metascience_ai_toolkit.core.prompts import NON_TOOL_TECHNIQUES

LEDGER = [{"tool_short": "grim_check", "validated": True}]


class TestIdentityIsReadFromTheV2Row:
    def test_a_v2_row_reports_its_finding_id(self):
        # `f.get("id")` gave None on every v2 row, so the headline counted 0.
        out = _unbacked_findings(LEDGER, [{
            "finding_id": "f_abc123", "technique": "statcheck",
            "severity": 3, "location": "Table 2"}])
        assert len(out) == 1
        assert out[0]["id"] == "f_abc123", "identity must survive to the audit"

    def test_the_severity_survives_too(self):
        out = _unbacked_findings(LEDGER, [{
            "finding_id": "f_x", "technique": "statcheck",
            "provisional_severity": 4, "location": "p3"}])
        assert out[0]["severity"] == 4, "a producer row carries provisional_severity"


class TestANonToolTechniqueIsNotUnbacked:
    def test_the_v2_non_tool_techniques_are_skipped(self):
        # The docstring names `manual` as the honest label; v2 deleted it.
        # These are its replacements and none has a candidate tool.
        rows = [{"finding_id": f"f_{t}", "technique": t, "severity": 3}
                for t in NON_TOOL_TECHNIQUES]
        assert _unbacked_findings(LEDGER, rows) == [], (
            "a technique that cannot have a tool is not an unbacked one")

    def test_a_real_tool_technique_with_no_call_is_still_caught(self):
        # THE DIRECTION THAT MATTERS: skipping non-tool techniques must not
        # blind the audit to the thing it exists for -- a finding naming a
        # real check that never ran.
        out = _unbacked_findings(LEDGER, [{
            "finding_id": "f_real", "technique": "sprite_reconstruct",
            "severity": 4}])
        assert [o["technique"] for o in out] == ["sprite_reconstruct"]

    def test_a_technique_whose_tool_did_run_is_not_flagged(self):
        assert _unbacked_findings(LEDGER, [{
            "finding_id": "f_ok", "technique": "grim_check", "severity": 3}]) == []
