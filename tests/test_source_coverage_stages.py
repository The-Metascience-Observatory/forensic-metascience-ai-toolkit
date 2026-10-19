"""The quotation caveat must count every stage, and it counted one.

FOUND BY THE RUN-INCOHERENCE SWEEP, 2026-08-11, over three archived runs of
`10.1002--eat.24415`.

WHAT WAS WRONG. `report.md` and `source_coverage.json` sit in the same bundle
and disagreed in every run that had a stage 2:

    report.md              "Traceable to the page: 11 of 11 ... 4 quoted
                            passages are ours, not the paper's"
    source_coverage.json    16 checks, 10 located, 6 ours

`_sweep_source_coverage` took a bare stage-1 ledger and hardcoded
`{"stage1": ...}`; `write_review_outputs` wrote the JSON later from BOTH
stages. Two files, one bundle, different populations, no marker of which was
which.

WHY THIS ONE AND NOT ANOTHER MISCOUNT. The under-reported number is the count
of quoted passages the REVIEW assembled rather than lifted from the paper. It
is the caveat that stops a reader treating a stitched sentence as the authors'
own words, and stitched quotations are how a fair check becomes an unfair
accusation. Under-disclosing it fails in the direction this project treats as
the worst available outcome. Two such passages were handed to the reader of
the clamped run with no caveat over them.

WHAT THE FIX IS NOT. It is not "render report.md later". Rendering is where a
paid analysis is most easily lost, and moving it was the larger change. The
renderer already accepted a stage-keyed mapping -- it summed over
`.values()` all along -- so only the caller was wrong.
"""
import json
from pathlib import Path

import pytest

from metascience_agent.agent import _sweep_source_coverage
REPO = Path(__file__).resolve().parents[1]
RUN = REPO / "tests/fixtures/papers/high_value_pdfs_to_run_on/10.1002--eat.24415/forensic_review_clamped"
PAPER = REPO / "tests/fixtures/papers/high_value_pdfs_to_run_on/10.1002--eat.24415"


class TestItAcceptsEveryStage:
    def test_a_mapping_of_two_ledgers_yields_two_summaries(self):
        led = {"stage1": [{"tool_short": "grim", "source_quote": "M = 1.0"}],
               "stage2": [{"tool_short": "grimmer", "source_quote": "SD = 2.0"}]}
        got = _sweep_source_coverage(led, PAPER)
        if got is None:
            pytest.skip("paper text not readable in this checkout")
        assert sorted(got) == ["stage1", "stage2"]

    def test_a_bare_list_is_still_read_as_stage_one(self):
        """Archived callers pass a list. Breaking them would trade a
        disagreement for a crash."""
        got = _sweep_source_coverage(
            [{"tool_short": "grim", "source_quote": "M = 1.0"}], PAPER)
        if got is None:
            pytest.skip("paper text not readable in this checkout")
        assert sorted(got) == ["stage1"]

    def test_an_empty_stage_does_not_create_an_empty_summary(self):
        """A stage that made no calls must be absent, not present and zeroed --
        `0 of 0 traceable` reads as a failure of the review."""
        got = _sweep_source_coverage({"stage1": [{"tool_short": "grim"}],
                                      "stage2": []}, PAPER)
        if got is None:
            pytest.skip("paper text not readable in this checkout")
        assert "stage2" not in got

    def test_no_paper_still_yields_none_not_a_zeroed_summary(self):
        assert _sweep_source_coverage({"stage1": [{"tool_short": "g"}]}, None) is None

class TestTheArchivedRunThatReportedIt:
    """Replayed against the bundle the sweep found it in. The ledgers are on
    disk, so this is the real disagreement, not a reconstruction of it."""

    @pytest.fixture(scope="class")
    def ledgers(self):
        if not (RUN / "toolcalls.stage2.json").exists():
            pytest.skip("clamped Romano run not in this checkout")
        return {k: json.loads((RUN / f"toolcalls.{k}.json").read_text("utf-8"))
                for k in ("stage1", "stage2")}

    def test_the_merged_summary_matches_the_shipped_json(self, ledgers):
        """The JSON was always right. The renderer was fed less than it.

        THE VERDICT FIELDS ARE NO LONGER PINNED TO THE SHIPPED NUMBERS, and
        deliberately. This test's subject is WHICH CALLS are counted -- the bug
        was a population, one stage where there were two -- and `calls`,
        `eligible`, `with_quote` and `without_quote` say that completely. The
        verbatim/stitched split says something else: how much of the paper our
        MATCHER could find on the day, which is a moving number by design.

        It moved on 2026-08-12: `quotes.fold_rendering` began folding the
        renderer before comparing, and the six passages this run labelled
        "assembled by the review" turned out to be one sentence -- the table
        footnote "Bold text is used to reflect significant effects, defined as
        p < 0.05" -- which the extractor the model read had handed it as
        `p &lt; 0.05`. Verified by hand against the paper's XML. The caveat was
        false, and pinning it here would have made removing it a test failure.

        The verdict fields are still checked for INTERNAL consistency, which is
        the property that cannot drift.
        """
        merged = _sweep_source_coverage(ledgers, PAPER)
        if merged is None:
            pytest.skip("paper text not readable in this checkout")
        shipped = json.loads((RUN / "source_coverage.json").read_text("utf-8"))
        assert sorted(merged) == sorted(shipped)
        population = ("calls", "eligible", "with_quote", "without_quote", "checked")
        for stage, want in shipped.items():
            got = merged[stage]
            for field in population:
                assert got.get(field) == want.get(field), f"{stage}.{field}"
            assert (got["verbatim"] + got["elided"] + got["stitched"]
                    + got["unverified"]) == got["with_quote"], stage

    def test_the_shipped_report_md_still_carries_the_old_number(self):
        """NOT a failure to fix -- a record. The archived bundle is evidence and
        is not rewritten. Delete this test only when the run is re-run."""
        md = (RUN / "report.md")
        if not md.exists():
            pytest.skip("clamped Romano run not in this checkout")
        text = md.read_text("utf-8")
        assert ("4 quoted passages are ours" in text
                or "6 quoted passages are ours" in text)
