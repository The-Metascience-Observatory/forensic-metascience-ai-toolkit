"""`SEVERITY_VALUES` / `VERDICT_VALUES` must not depend on the v1 schemas.

PREREQUISITE (a) FOR THE LEGACY DELETION. Both tuples were built at import time
by reading `findings.schema.json` and `report.schema.json` -- the two V1 files
the deletion removes -- and `evaluation/deterministic.py` reads both on the
LIVE eval path (`harness.py` calls it for parallel runs as well as legacy). So
deleting the v1 schemas would have broken current-pipeline evaluation, with an
error pointing at a file nobody thought was load-bearing.

They are now sourced from the vocabulary modules. While the v1 schemas still
exist, this file pins that the swap changed NO VALUE; once they are gone the
first two tests stand alone.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from metascience_agent import verdicts
from metascience_agent.core import prompts
from metascience_agent.tools import severity as tool_severity

SCHEMA_DIR = (pathlib.Path(__file__).resolve().parents[1]
              / "src" / "metascience_agent" / "schema")


class TestTheyComeFromTheVocabularyModules:
    def test_severity_values_is_the_tool_enum(self):
        assert prompts.SEVERITY_VALUES == tuple(tool_severity.SEVERITY_LEVELS)

    def test_verdict_values_is_the_verdict_vocabulary(self):
        assert prompts.VERDICT_VALUES == tuple(verdicts.VERDICTS)

    def test_neither_is_empty(self):
        """An empty tuple would make `deterministic.py`'s membership tests
        reject every severity a run produced, which reads as a malformed
        report rather than as a broken import."""
        assert prompts.SEVERITY_VALUES and prompts.VERDICT_VALUES


class TestTheSwapChangedNothing:
    """Deleted with the v1 schemas, not before: this is the evidence that
    re-sourcing was value-preserving."""

    def test_severity_matches_the_v1_schema(self):
        path = SCHEMA_DIR / "findings.schema.json"
        if not path.exists():
            pytest.skip("v1 findings schema deleted; the pin above stands alone")
        enum = (json.loads(path.read_text())["properties"]["findings"]
                ["items"]["properties"]["severity"]["enum"])
        assert prompts.SEVERITY_VALUES == tuple(enum)

    def test_verdict_matches_the_v1_schema(self):
        path = SCHEMA_DIR / "report.schema.json"
        if not path.exists():
            pytest.skip("v1 report schema deleted; the pin above stands alone")
        enum = json.loads(path.read_text())["properties"]["verdict"]["enum"]
        assert prompts.VERDICT_VALUES == tuple(enum)


class TestTheLiveEvalPathStillWorks:
    """The reason this prerequisite exists at all: `deterministic.py` reads
    both tuples, and `harness.py` calls it on PARALLEL runs, not only legacy
    ones. A tuple that silently emptied would reject every severity a run
    produced and read as a malformed report."""

    def test_a_valid_severity_is_accepted(self):
        from metascience_agent.evaluation import deterministic
        out = deterministic.check_findings_json({"findings": [{
            "id": "f1", "location": "Table 1", "technique": "grim",
            "reproduction": "metascience grim 3.5 30", "severity": "suspicious"}]})
        assert not any("invalid severity" in p for p in out["problems"]), out

    def test_an_invented_severity_is_still_rejected(self):
        from metascience_agent.evaluation import deterministic
        out = deterministic.check_findings_json({"findings": [{
            "id": "f1", "location": "Table 1", "technique": "grim",
            "reproduction": "x", "severity": "extremely_bad"}]})
        assert any("invalid severity" in p for p in out["problems"]), (
            "the severity vocabulary stopped being enforced")

    def test_the_verdict_check_still_reads_the_tuple(self):
        from metascience_agent.evaluation import deterministic
        assert deterministic.check_verdict(
            "does_not_reconcile", "does_not_reconcile")["valid_value"] is True
        assert deterministic.check_verdict(
            "made_up", "does_not_reconcile")["valid_value"] is False
