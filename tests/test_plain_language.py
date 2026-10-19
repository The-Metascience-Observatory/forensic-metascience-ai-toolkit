"""A second reader, who is not a statistician.

The review is read by two people and must serve both without compromising for
either: a methodologist who wants the statistic and the reproduction command,
and someone with no statistical training -- a journalist, a clinician, an
editor, a patient -- who wants to know whether the paper's claim survives.

Averaging the two registers produces something that serves neither, so the
technical fields stay exactly as they were and a `plain` field runs alongside
them. It is a TRANSLATION, not a hedge.
"""
import json
from pathlib import Path

import pytest

SCHEMA = Path("src/metascience_agent/schema/report.schema.json")


def _report(**kw):
    base = {
        "headline": {"severity": "suspicious", "statement": "Fourteen tests, no correction.",
                     "plain": "The authors ran fourteen tests and treated each as the only one.",
                     "rests_on": "stated_constraint", "evidence": "p = .026",
                     "reproduction": "metascience multiplicity ..."},
        "verdict": "unresolved", "confidence": "high",
        "findings": [{
            "rank": 1, "title": "Fourteen indirect effects, no correction for multiplicity",
            "plain": "The authors ran fourteen separate tests and treated each as if it "
                     "were the only one. Two of the results they call significant would "
                     "not survive the usual correction for that.",
            "severity": "suspicious", "confidence": "high", "location": "Table 2",
            "reported": "24 indirect effects", "computed": "2 lost to BH",
            "assumptions": "family = the six MSEMs",
            # The paper declares its own alpha and its own family of models, so
            # the obligation to correct is one it took on itself.
            "warrant": "paper_commitment",
            "reproduction": "metascience multiplicity ...", "stage1_finding_ids": ["f1"],
        }],
        "not_checked": [], "limitations": [], "coverage_summary": {},
    }
    base.update(kw)
    return base


class TestFigureClassification:
    SCHEMA1 = Path("src/metascience_agent/schema/findings.v2.schema.json")

    def test_the_schema_asks_for_it(self):
        s = json.loads(self.SCHEMA1.read_text())
        props = s["properties"]["figures"]["items"]["properties"]
        for field in ("is_data_figure", "n_panels", "panels",
                      "carries_unique_values", "error_bars"):
            assert field in props, field

    def test_a_figure_must_say_whether_it_is_a_data_figure(self):
        s = json.loads(self.SCHEMA1.read_text())
        assert "is_data_figure" in s["properties"]["figures"]["items"]["required"]

    def test_unique_values_is_described_as_the_one_that_matters(self):
        """It converts "we could not see the figures" from a generic caveat
        into a specific, locatable hole."""
        s = json.loads(self.SCHEMA1.read_text())
        desc = (s["properties"]["figures"]["items"]["properties"]
                 ["carries_unique_values"]["description"])
        assert "NOT also printed" in desc


class TestTheSupplementIsNotBlamedOnThePaper:
    def test_the_subject_of_the_warning_is_this_review(self):
        """It opened "THIS ANALYSIS WAS RUN ON AN INCOMPLETE PAPER", which reads
        as a charge against the authors however carefully the rest of the
        paragraph attributes it to the operator."""
        from metascience_agent.supplements import OVERRIDE_WARNING
        first = OVERRIDE_WARNING.split("\n")[0]
        assert "THIS REVIEW" in first
        assert "INCOMPLETE PAPER" not in first

    def test_it_says_whose_fault_it_is_not(self):
        from metascience_agent.supplements import OVERRIDE_WARNING
        assert "not a fault of the publication" in OVERRIDE_WARNING


