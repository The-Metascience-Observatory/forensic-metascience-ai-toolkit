"""The viewer told a reader that NONE of 34 findings reached the report.

`_check_table`'s "in report" column and the Sankey's third column both derived
"kept" from `report.json`'s editorial list. `grep -c "report.json"
parallel.py` returns 0 -- the parallel path never writes that file. So
`report_obj` was `{}`, `editorial` was `[]`, and `[] is not None` slipped the
guard: `kept_ids` came out empty, every row read `kept: 0`, and the diagram's
only outcome node was `not reported (34)`.

MEASURED on the current ajcp run: the adjudicator RAN, kept 22 and merged 8, and
`report.md` carries FIFTEEN finding headings.

Two defects in one, and the second would have survived a fix to the first: the
match was on `id`, which no v2 row carries.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from metascience_agent.bundle import _check_table, _reported_ids, _sankey
from metascience_agent.report_v2 import reported_finding_ids

RUN = (pathlib.Path(__file__).resolve().parents[1] / "tests/fixtures/papers/high_value_pdfs_to_run_on"
       / "10.1002--ajcp.70049" / "forensic_review_gatetest2_2026-08-29"
       / "findings.v2.json")


def _row(fid, action, outcome="problem", severity=3):
    return {"finding_id": fid, "outcome": outcome, "severity": severity,
            "technique": "grim_check",
            "adjudication": {"action": action} if action else {}}


class TestTheRuleIsSharedWithTheRenderer:
    def test_bundle_and_report_agree_on_a_synthetic_document(self):
        """A second copy of the rule here would drift from the renderer's
        exactly as the `report.json` assumption did."""
        findings = [_row("f_1", "kept"), _row("f_2", "merged"),
                    _row("f_3", "discarded"), _row("f_4", "upgraded")]
        assert _reported_ids(findings, []) == reported_finding_ids(
            {"findings": findings})

    @pytest.mark.parametrize("action, reported", [
        ("kept", True), ("upgraded", True), ("downgraded", True),
        ("merged", False), ("discarded", False), (None, True),
    ])
    def test_each_action_lands_on_the_right_side(self, action, reported):
        """`None` is reported: a run whose adjudicator did not execute still
        prints its findings, and that must not read as `discarded`."""
        got = _reported_ids([_row("f_1", action)], [])
        assert ("f_1" in got) is reported

    def test_a_pass_row_is_never_in_the_report(self):
        assert _reported_ids([_row("f_1", "kept", outcome="pass")], []) == set()

    def test_an_editorial_list_still_wins_when_present(self):
        """v1 runs keep their existing behaviour."""
        findings = [{"id": "a", "outcome": "problem"}]
        got = _reported_ids(findings, [{"stage1_finding_ids": ["a"]}])
        assert got == {"a"}


@pytest.mark.skipif(not RUN.is_file(), reason="reference run not present")
class TestOnTheRealRun:
    @pytest.fixture(scope="class")
    def doc(self):
        return json.loads(RUN.read_text(encoding="utf-8"))

    def test_the_in_report_column_matches_report_md(self, doc):
        """15 is the number of `###` finding headings in that run's
        report.md."""
        rows = _check_table([], doc["findings"], [])
        assert sum(r["kept"] for r in rows) == 15

    def test_it_is_not_zero(self, doc):
        """The defect in one assertion: the column read 0 on every parallel
        run, at every severity, for every check."""
        rows = _check_table([], doc["findings"], [])
        assert sum(r["kept"] for r in rows) > 0

    def test_the_sankey_shows_both_outcomes(self, doc):
        out = _sankey([], doc["findings"], [])
        labels = {n["label"] for n in out["nodes"] if n.get("column") == 2}
        assert labels == {"reported", "not reported"}

    def test_the_sankey_flows_account_for_every_finding(self, doc):
        out = _sankey([], doc["findings"], [])
        flow = {}
        for link in out["links"]:
            if link["target"] in ("reported", "not reported"):
                flow[link["target"]] = flow.get(link["target"], 0) + link["value"]
        assert flow == {"reported": 15, "not reported": 19}
        assert sum(flow.values()) == len(doc["findings"])
