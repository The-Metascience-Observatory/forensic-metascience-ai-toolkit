"""The disclaimer must reach every output channel.

This test exists because the disclaimer was designed, agreed, and then not
implemented for several days while the README claimed the tool "is not a fraud
detector" and no generated report said so. The README is read by people
evaluating the tool; the report is read by people acting on it.
"""
import json
import re

import pytest


def _flat(text: str) -> str:
    """Collapse whitespace before matching.

    The prose is hard-wrapped, so a phrase like "corresponding author" is split
    across a newline in the source. Asserting on the raw string makes the test
    fail whenever someone rewraps a paragraph.
    """
    return re.sub(r"\s+", " ", text).lower()

from forensic_metascience_ai_toolkit.core import prompts
from forensic_metascience_ai_toolkit.disclaimer import (
    ACTION_NOTE,
    DISCLAIMER_LONG,
    DISCLAIMER_SHORT,
    banner_markdown,
    closing_section_markdown,
)
def _minimal_report() -> dict:
    return {
        "headline": {"severity": "impossible", "statement": "A mean is impossible."},
        "verdict": "serious_problems",
        "confidence": "high",
        "findings": [],
        "not_checked": [],
        "limitations": [],
        "coverage_summary": {"stats_found": 1, "stats_checked": 1},
    }


class TestWording:
    def test_short_disclaimer_denies_fraud_detection(self):
        low = DISCLAIMER_SHORT.lower()
        assert "not" in low
        assert "fraud" in low

    def test_long_disclaimer_gives_a_base_rate(self):
        """A caveat without a number is ignorable boilerplate.

        The number is "half of the clean control papers carry at least one
        statcheck inconsistency", which is measured on our own ground-truth
        corpus and stated as such.

        The "1%" end-to-end precision figure is GONE and must stay gone.
        Written 2026-07-27, before most of the current pipeline existed, never
        sourced, and already flagged in the 2026-08 integrity-hardening
        notes as needing "a cited method or a
        reframing". It sat outside `prompts/`, so the dated-claims test never
        reached it, and this assertion held it in place. The qualitative claim
        that replaced it carries the same guard and is defensible.
        """
        assert "half" in DISCLAIMER_LONG.lower()
        assert "getting numbers off a PDF" in DISCLAIMER_LONG
        assert "1%" not in DISCLAIMER_LONG, (
            "an unsourced precision figure came back; measure it or leave it "
            "qualitative")

    def test_long_disclaimer_explains_indeterminate(self):
        assert "indeterminate" in DISCLAIMER_LONG.lower()

    def test_action_note_directs_to_the_author_not_the_public(self):
        low = _flat(ACTION_NOTE)
        assert "corresponding author" in low
        assert "public allegations" in low


class TestReportRendering:
    def test_banner_is_a_blockquote(self):
        assert banner_markdown().startswith("> ")

class TestOtherChannels:
    def test_findings_disclaimer_does_not_break_the_validator(self):
        from forensic_metascience_ai_toolkit.evaluation import deterministic

        obj = {
            "disclaimer": DISCLAIMER_SHORT,
            "findings": [],
            "coverage": {},
        }
        assert deterministic.check_findings_json(obj)["passed"]
