"""Every v2 finding graded "reviewer reading", including the ones a tool computed.

`evidence_grade` walks a v1 chain: report finding -> `stage1_finding_ids` ->
sweep findings -> the technique behind each. v2 merged those two stages, so a v2
row carries NO `stage1_finding_ids`, `ids` came out empty, and every finding took
the `if not ids` branch.

MEASURED on the current ajcp run: all 34 graded `reading` with the chip
"reviewer reading", while `computed_by` records 5 as `registry_tool`. The grade
that exists to separate a validated computation from the model's own arithmetic
gave the weakest answer for every row -- understating our own evidence in the
same breath as it hid the rows that deserve the caution.
"""

from __future__ import annotations

import collections
import json
import pathlib

import pytest

from forensic_metascience_ai_toolkit.viewer_facts import evidence_grade

RUN = (pathlib.Path(__file__).resolve().parents[1] / "tests/fixtures/papers/high_value_pdfs_to_run_on"
       / "10.1002--ajcp.70049" / "forensic_review_gatetest2_2026-08-29"
       / "findings.v2.json")


class TestAV2FindingIsGradedFromItsOwnProvenance:
    @pytest.mark.parametrize("computed_by, grade", [
        ("registry_tool", "computed"),
        ("agent_code", "hand_computed"),
        ("model_reading", "reading"),
        ("model_knowledge", "reading"),
    ])
    def test_computed_by_decides_the_grade(self, computed_by, grade):
        out = evidence_grade({"computed_by": computed_by}, {})
        assert out["grade"] == grade
        assert out["graded_from"] == "computed_by"

    def test_the_chip_follows_the_grade(self):
        assert evidence_grade({"computed_by": "registry_tool"}, {})["chip"] \
            != evidence_grade({"computed_by": "model_reading"}, {})["chip"]

    def test_a_v1_row_still_walks_the_chain(self):
        """Archived runs carry no `computed_by` and must keep their behaviour."""
        sweep = {"s1": {"technique": "grim_check"}}
        out = evidence_grade({"stage1_finding_ids": ["s1"]}, sweep)
        assert out["grade"] == "computed"
        assert out.get("graded_from") != "computed_by"

    def test_a_v1_row_with_dangling_ids_is_still_reading(self):
        """A broken audit trail reads as nothing verified -- unchanged."""
        out = evidence_grade({"stage1_finding_ids": ["missing"]}, {})
        assert out["grade"] == "reading"

    def test_a_row_with_neither_is_reading(self):
        assert evidence_grade({}, {})["grade"] == "reading"


@pytest.mark.skipif(not RUN.is_file(), reason="reference run not present")
class TestOnTheRealRun:
    @pytest.fixture(scope="class")
    def findings(self):
        return json.loads(RUN.read_text(encoding="utf-8"))["findings"]

    def test_not_everything_is_reading_any_more(self, findings):
        grades = collections.Counter(
            evidence_grade(f, {})["grade"] for f in findings)
        assert grades["reading"] < len(findings)

    def test_the_grades_match_computed_by_exactly(self, findings):
        n_tool = sum(1 for f in findings
                     if f.get("computed_by") == "registry_tool")
        grades = collections.Counter(
            evidence_grade(f, {})["grade"] for f in findings)
        assert grades["computed"] == n_tool == 5
        assert grades["reading"] == 29


class TestTheLedgerReachesTheGradedFindings:
    """`evidence_grade` was fixed and could not reach the page.

    `evidence_ledger` iterates `report_obj.findings`, and `report_obj` comes
    from `report.json`, which the parallel path never writes. So on every v2 run
    the ledger graded NOTHING -- and the fix to `evidence_grade` was
    unreachable, because nothing was handed to it.

    Found by BUILDING the viewer and looking for the corrected grade in the
    output, not by trusting the unit test above, which calls `evidence_grade`
    directly.
    """

    @pytest.fixture(scope="class")
    def doc(self):
        if not RUN.is_file():
            pytest.skip("reference run not present")
        return json.loads(RUN.read_text(encoding="utf-8"))

    def test_the_ledger_grades_every_finding(self, doc):
        from forensic_metascience_ai_toolkit.viewer_facts import evidence_ledger
        led = evidence_ledger(doc)
        assert led["n"] == len(doc["findings"]) == 34
        assert len(led["per_finding"]) == 34

    def test_the_counts_match_computed_by(self, doc):
        from forensic_metascience_ai_toolkit.viewer_facts import evidence_ledger
        led = evidence_ledger(doc)
        assert led["counts"] == {"computed": 5, "hand_computed": 0,
                                 "reading": 29}

    def test_a_v1_payload_still_uses_report_obj(self):
        """The fallback must not override a real report_obj."""
        from forensic_metascience_ai_toolkit.viewer_facts import evidence_ledger
        payload = {"report_obj": {"findings": [{"title": "from report",
                                                "severity": "suspicious"}]},
                   "findings": [{"id": "s1", "title": "from sweep"}]}
        led = evidence_ledger(payload)
        assert led["n"] == 1
        assert led["per_finding"][0]["title"] == "from report"


class TestTheAccusatoryCountUnderstandsBothLadders:
    """`accusatory_without_a_validated_check` compared `str(severity)` against
    v1 STRINGS. `str(4)` is `"4"`, which matched nothing, so the number this
    ledger exists to surface read 0 on every v2 run -- the one its own docstring
    calls "the shape most likely to become a false accusation"."""

    @pytest.fixture(scope="class")
    def doc(self):
        if not RUN.is_file():
            pytest.skip("reference run not present")
        return json.loads(RUN.read_text(encoding="utf-8"))

    def test_it_matches_ground_truth_on_the_real_run(self, doc):
        from forensic_metascience_ai_toolkit.severity9 import ACCUSATORY_MIN
        from forensic_metascience_ai_toolkit.viewer_facts import evidence_ledger
        truth = [f for f in doc["findings"]
                 if isinstance(f.get("severity"), int)
                 and f["severity"] >= ACCUSATORY_MIN
                 and f.get("outcome") == "problem"
                 and f.get("computed_by") != "registry_tool"]
        assert evidence_ledger(doc)["accusatory_without_a_validated_check"] \
            == len(truth) == 2

    def test_a_numeric_severity_below_the_bar_does_not_count(self):
        from forensic_metascience_ai_toolkit.viewer_facts import evidence_ledger
        payload = {"findings": [{"severity": 2, "computed_by": "model_reading"}]}
        assert evidence_ledger(payload)[
            "accusatory_without_a_validated_check"] == 0

    def test_a_v1_string_severity_still_counts(self):
        from forensic_metascience_ai_toolkit.viewer_facts import evidence_ledger
        payload = {"report_obj": {"findings": [{"severity": "suspicious"}]}}
        assert evidence_ledger(payload)[
            "accusatory_without_a_validated_check"] == 1

    def test_a_tool_computed_accusation_is_not_counted(self):
        """The question is accusations WITHOUT a validated check."""
        from forensic_metascience_ai_toolkit.viewer_facts import evidence_ledger
        payload = {"findings": [{"severity": 5, "computed_by": "registry_tool"}]}
        assert evidence_ledger(payload)[
            "accusatory_without_a_validated_check"] == 0
