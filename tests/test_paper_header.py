"""The report must say which paper it is about.

Reports were titled with the directory slug alone -- "Forensic review --
10.1002--ajcp.70049" -- which does not identify a paper to a human reader. The
bibliographic detail was already being captured into findings.json by the sweep
and simply never crossed into the report: it lives on the stage-1 object, and
the renderer only ever received the editorial object plus a paper_id.
"""
import pytest

META = {
    "authors": "Wells, R., Ranjit, N., & Brown, L. D.",
    "year": "2026",
    "journal": "American Journal of Community Psychology, 77, 590-601",
    "doi": "10.1002/ajcp.70049",
    "study_design": "Observational analysis nested within a cluster-randomized trial",
}
TITLE = "Associations between inclusive coalition leadership and use of EBPs"


def _obj():
    return {
        "headline": {"severity": "suspicious", "statement": "A scale contradiction."},
        "verdict": "unresolved", "confidence": "high", "findings": [],
        "not_checked": [], "limitations": [],
        "coverage_summary": {"stats_found": 3, "stats_checked": 3},
    }


