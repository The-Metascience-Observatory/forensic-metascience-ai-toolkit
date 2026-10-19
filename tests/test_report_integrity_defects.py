"""Two failures of OURS that the report printed as facts about the paper.

DEFECT 8 -- three of the four funder-demo reports titled themselves with an
extraction failure. `head -1` on 2026-08-10:

    # Forensic review -- copy]                                (control_blinded)
    # Forensic review -- XML not present in XML article_meta   (control_blinded_r2)
    # Forensic review -- blinding] 2015                        (fraud_blinded)

The first and third are the TAIL of a redaction marker: the citation builder
took `.split()[-1]` of "[REDACTED - blinded copy]". The second is the
extractor's own error string promoted to the document heading, and it reached
the byline three more times in the same file.

DEFECT 14 -- "**NOTHING IN THE TABLES WAS CHECKED.**" printed over runs that
had checked a hundred cells. The counter behind it could see two tool-name
shapes and no others.

Both are the same failure: our own accounting or extraction failure, rendered
to the reader as a property of the paper.
"""

import json
import os

import pytest

from forensic_metascience_ai_toolkit import registry as R
from forensic_metascience_ai_toolkit.agent import _checkable_coverage
def _obj():
    return {
        "headline": {"severity": "suspicious", "statement": "A scale contradiction."},
        "verdict": "questionable", "confidence": "high", "findings": [],
        "not_checked": [], "limitations": [],
        "coverage_summary": {"stats_found": 3, "stats_checked": 3},
    }


def _ledger_messages(pairs):
    """(tool name, result payload) -> the message shape the counter reads."""
    msgs = []
    for i, (name, payload) in enumerate(pairs):
        tid = f"t{i}"
        msgs.append({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": name, "id": tid, "input": {}}]}})
        msgs.append({"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": tid,
             "content": json.dumps(payload)}]}})
    return msgs


PAPER = "eval/ground_truth/papers/10.1155--2016--2469521"   # 129 consumable cells


@pytest.mark.skipif(not os.path.isdir(PAPER), reason="corpus paper not present")
class TestTheCounterOverARealPaper:
    """End to end on a real table census, not a hand-built dict."""

    def test_the_counter_reads_the_registry_and_not_a_copy_of_it(self):
        """Every declared consumer must be counted -- including any added
        after this test was written."""
        pairs = [(f"mcp__forensic__{n}", {"severity": "consistent"})
                 for n in sorted(R.cell_consuming_tools())]
        cov = _checkable_coverage(PAPER, _ledger_messages(pairs))
        counted = set(cov.get("direct_check_tools") or {})
        # `check_table` is counted by the cell-id population instead. A batch
        # tool lands here only because these synthetic results carry no row
        # count -- which is the point: an uncountable batch call must not fall
        # out of every population.
        expected = {n for n in R.cell_consuming_tools()
                    if not n.endswith("check_table")}
        assert counted == expected


class TestOurCliFailureIsNotThePapersProperty:
    """The report told a reader a finding was "not independently reproducible as
    written" and pasted our CLI's stderr -- Rich panel, brace placeholders and
    all -- as the evidence. Every one of those failures is a defect in the
    command WE wrote. MEASURED: 461 of 801 archived reproduction commands
    (57.6%) fail validation."""

    def _clause(self, problem):
        from forensic_metascience_ai_toolkit.report_render import _repro_failure_clause
        return _repro_failure_clause({"reproduction_problem": problem})

    def test_no_raw_stderr_reaches_the_reader(self):
        raw = ("exited 2: Usage: metascience prop-from-normal [OPTIONS] "
               "{reported_proportion} {mean}\nTry 'metascience ...' for help.")
        out = self._clause(raw)
        for leak in ("Usage:", "{reported_proportion}", "exited 2", "Try '"):
            assert leak not in out, leak

    def test_it_names_whose_failure_it_is(self):
        assert "the review" in self._clause("exited 2: Usage: metascience x")

    def test_each_cause_is_distinguished(self):
        seen = {
            self._clause("No such option: --pdf-path"),
            self._clause("must invoke `metascience`, got 'No'"),
            self._clause("contains placeholder '<' -- not runnable as written"),
            self._clause("exited 1: Traceback (most recent call last)"),
            self._clause("exited 2: Usage: metascience x"),
        }
        assert len(seen) == 5, "distinct causes must not collapse to one clause"

    def test_an_unrecognised_problem_still_says_something_true(self):
        out = self._clause("something nobody anticipated")
        assert "no runnable command" in out and "the review" in out
