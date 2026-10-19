"""The disclaimer overstated the corpus and pointed at a section that was not there.

Two defects in the paragraph whose entire job is to bound what this toolkit has
been tested on, in a document that tells readers to distrust unverified numbers.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from forensic_metascience_ai_toolkit import scope
from forensic_metascience_ai_toolkit.disclaimer import DISCLAIMER_LONG, closing_section_markdown

RUN = (pathlib.Path(__file__).resolve().parents[1] / "tests/fixtures/papers/high_value_pdfs_to_run_on"
       / "10.1002--ajcp.70049" / "forensic_review_gatetest2_2026-08-29"
       / "findings.v2.json")


class TestTheCorpusSizeIsDerivedNotTyped:
    """It said "at least 37 runs over 19 papers" while `scope.ARCHIVE_RUNS`
    said 35. `scope.py`'s own comment records correcting that figure twice
    already, which is what a literal in a second file guarantees."""

    def test_the_number_matches_the_module_that_counts_it(self):
        assert f"{scope.ARCHIVE_RUNS} runs" in DISCLAIMER_LONG

    def test_the_retracted_number_is_gone(self):
        assert "37 runs" not in DISCLAIMER_LONG

    def test_no_placeholder_survives_into_the_published_text(self):
        assert "{TESTED_ON}" not in DISCLAIMER_LONG

    def test_it_tracks_scope_rather_than_restating_it(self):
        """The property that stops it drifting again: the sentence comes from
        `scope.tested_on_sentence`."""
        head = scope.tested_on_sentence().split(", almost all")[0].rstrip(".")
        assert head in DISCLAIMER_LONG


class TestTheDocumentContainsWhatItPointsAt:
    def test_the_disclaimer_promises_a_breakdown(self):
        # Whitespace-normalised: the phrase wraps across a line in the source
        # literal, so a raw substring test fails on a document that does
        # contain it.
        import re
        flat = re.sub(r"\s+", " ", DISCLAIMER_LONG)
        assert "What this has been tested on" in flat

    def test_the_closing_section_supplies_it(self):
        import re
        flat = re.sub(r"\s+", " ", "\n".join(closing_section_markdown()))
        assert "What this has been tested on" in flat

    def test_the_closing_section_carries_the_action_note(self):
        """The single most important sentence for a reader who has just been
        shown an accusation."""
        joined = "\n".join(closing_section_markdown())
        assert "verify the number by hand" in joined


@pytest.mark.skipif(not RUN.is_file(), reason="reference run not present")
class TestTheRenderedReport:
    @pytest.fixture(scope="class")
    def md(self):
        from forensic_metascience_ai_toolkit.report_v2 import render_report_v2
        return render_report_v2(json.loads(RUN.read_text(encoding="utf-8")))

    def test_it_renders_the_section_the_disclaimer_points_at(self, md):
        """`report_v2` imported `DISCLAIMER_LONG` alone, so the document said
        "the full breakdown is below" and there was no below."""
        import re
        assert "What this has been tested on" in re.sub(r"\s+", " ", md)

    def test_it_renders_the_action_note(self, md):
        assert "verify the number by hand" in md

    def test_it_does_not_publish_the_overstated_corpus(self, md):
        assert "37 runs" not in md
        assert f"{scope.ARCHIVE_RUNS} runs" in md
