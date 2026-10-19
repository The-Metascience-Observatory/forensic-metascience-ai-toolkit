"""A finding is capped by what its own tool returned (severity9.TOOL_VERDICT_CAPS).

MEASURED 2026-10-13: "the †/‡ marks on identical means 78.1 vs 78.1 are
impossible" was the Level-5 headline in 6 of 36 eval runs, with a validated
`indeterminate` tool verdict; the judge called it a false positive each time.
Replayed on all 767 kept rows: 19 capped, no gold finding below its range.
"""

from forensic_metascience_ai_toolkit import adjudicate
from forensic_metascience_ai_toolkit.findings_v2 import clamp_provisionals
from forensic_metascience_ai_toolkit.severity9 import TOOL_VERDICT_CAPS, clamp_provisional


def test_the_caps():
    assert TOOL_VERDICT_CAPS == {"consistent": 2, "indeterminate": 3}
    kw = dict(technique_is_tool=True, computed_by="registry_tool")
    assert clamp_provisional(5, tool_verdict="indeterminate", **kw) == 3
    assert clamp_provisional(5, tool_verdict="consistent", **kw) == 2
    assert clamp_provisional(5, tool_verdict="suspicious", **kw) == 5
    assert clamp_provisional(6, tool_verdict="impossible", **kw) == 6
    # Only a registered-tool technique computed by that tool.
    assert clamp_provisional(5, tool_verdict="indeterminate", technique_is_tool=False,
                             computed_by="registry_tool") == 5
    assert clamp_provisional(2, tool_verdict="indeterminate", **kw) == 2


def _d1_headline(**over):
    """D1's actual headline row (apple_cider, Claude Sonnet, 2026-10-13)."""
    row = {"finding_id": "f_d1", "slug": "t2_dagger_identical", "producer": "tool_expert",
           "technique": "recalc_independent_t", "outcome": "problem",
           "computed_by": "registry_tool", "provisional_severity": 5, "severity": 5,
           "title": "Table 2: weight 78.1 vs 78.1 (week 4) flagged as significantly different",
           "inputs": {"mean1": 78.1, "sd1": 26.5, "n1": 30, "mean2": 78.1, "sd2": 27.4, "n2": 30},
           "tool_verdict": {"severity": "indeterminate", "tool": "recalc_independent_t",
                            "validated": True, "quarantined_raw": None}}
    row.update(over)
    return row


def test_the_provisional_clamp_reads_the_rows_own_verdict():
    rows = [_d1_headline()]
    clamp_provisionals(rows)
    assert rows[0]["provisional_severity"] == 3
    assert rows[0]["provisional_severity_from"] == 5
    unvalidated = [_d1_headline(tool_verdict={"severity": "indeterminate", "validated": False})]
    clamp_provisionals(unvalidated)
    assert unvalidated[0]["provisional_severity"] == 5


def _adjudicate(rows, headline):
    out = {"verdicts": [{"finding_id": r["finding_id"], "action": "kept",
                         "severity": r["severity"], "category": "none",
                         "rationale": "kept after reading the paper"} for r in rows],
           "paper": {"verdict": "does_not_reconcile", "paper_severity": 5,
                     "confidence": "medium", "summary": "s" * 200,
                     "headline_finding_id": headline}}
    return adjudicate.apply(rows, out)


def test_the_final_severity_is_capped_and_it_cannot_headline():
    other = {"finding_id": "f_csf", "slug": "csf", "producer": "tool_expert",
             "technique": "csf_test", "outcome": "problem", "computed_by": "registry_tool",
             "provisional_severity": 4, "severity": 4, "inputs": {},
             "tool_verdict": {"severity": "suspicious", "tool": "csf_test", "validated": True}}
    findings, summary = _adjudicate([_d1_headline(), other], "f_d1")
    by = {f["finding_id"]: f for f in findings}
    assert by["f_d1"]["severity"] == 3
    assert summary["headline_finding_id"] == "f_csf"
    assert summary["n_headline_fallback"] == 1
