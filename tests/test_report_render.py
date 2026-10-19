"""Tests for markdown->PDF report rendering."""

import shutil
import pytest

from metascience_agent.report_render import markdown_to_html, render_markdown_to_pdf

SAMPLE_MD = (
    "# Forensic Review\n\n"
    "**Headline problem:** two independent samples share duplicate data.\n\n"
    "| Measure | S1 | S2 |\n|---|---|---|\n| PosAff | 2.37 (0.92) | 2.37 (0.92) |\n\n"
    "1. First finding\n2. Second finding\n\n"
    "```\nmetascience duplication-detect blocks.json\n```\n"
)


class TestHtmlConversion:
    def test_html_is_self_contained(self):
        html = markdown_to_html(SAMPLE_MD, title="T", meta_line="Paper: x")
        assert "<!DOCTYPE html>" in html
        assert "<style>" in html  # CSS inlined, no external assets
        assert "Paper: x" in html
        assert "<table>" in html  # tables extension active
        assert "<strong>" in html
        assert "<ol>" in html

    def test_empty_markdown(self):
        html = markdown_to_html("")
        assert "<body>" in html

    def test_fallback_when_markdown_missing(self, monkeypatch):
        # Simulate the markdown package being unavailable.
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *a, **k):
            if name == "markdown":
                raise ImportError("no markdown")
            return real_import(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        html = markdown_to_html("# hi\ntext")
        assert "<pre>" in html  # graceful degrade


class TestPdfRender:
    def test_render_returns_none_gracefully_without_renderer(self, tmp_path, monkeypatch):
        """UPDATED 2026-08-16: stubbing `shutil.which` no longer establishes
        "no renderer". WeasyPrint is driven through the LIBRARY rather than a
        console script -- precisely because pandoc could not resolve the script
        even with it on PATH -- so a which-only stub leaves a working backend in
        place, and this test would assert None against a successful render.
        """
        import builtins
        import metascience_agent.report_render as rr
        monkeypatch.setattr(rr.shutil, "which", lambda name: None)
        real = builtins.__import__

        def _blocked(name, *a, **k):
            if name.startswith("weasyprint"):
                raise ImportError("blocked for test")
            return real(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", _blocked)
        out = render_markdown_to_pdf(SAMPLE_MD, tmp_path / "r.pdf")
        assert out is None  # never raises

    @pytest.mark.skipif(not (shutil.which("wkhtmltopdf") or shutil.which("pandoc")),
                        reason="no wkhtmltopdf/pandoc")
    def test_render_produces_pdf(self, tmp_path):
        out = render_markdown_to_pdf(SAMPLE_MD, tmp_path / "r.pdf", title="Test")
        assert out is not None
        assert out.exists()
        assert out.read_bytes()[:4] == b"%PDF"


class TestStructuredReportRendering:
    """The document is built from schema fields, so 'headline first' and
    'severity ordered' are enforced properties, not prompt requests."""

    @staticmethod
    def _obj(**over):
        base = {
            "headline": {
                "statement": "A reported percentage is impossible for the stated denominator.",
                "severity": "impossible",
                "rests_on": "stated_constraint",
                "evidence": "Table 1: 12 (21.7%) of n=58.",
                "reproduction": "metascience grim 21.7 58",
            },
            "verdict": "unresolved",
            "confidence": "high",
            "findings": [],
            "not_checked": [],
            "limitations": [],
            "coverage_summary": {
                "stats_found": 10, "stats_checked": 5,
                "tools_run": ["grim"], "tables_checked": ["Table 1"],
            },
            "report_markdown": "Narrative body.",
        }
        base.update(over)
        return base

class TestVerifiedQuoteSurfacing:
    """An editorial finding's `reported` field is the model's restatement of the
    paper -- quote-shaped but never checked against the source. The finding block
    must also carry the sweep's VERIFIED verbatim quote (the one line a reader can
    go and check), and only when the verifier actually located it."""

    @staticmethod
    def _report(finding):
        return {
            "headline": {"statement": "x", "severity": "suspicious"},
            "verdict": "unresolved", "confidence": "high",
            "findings": [finding], "not_checked": [], "limitations": [],
            "coverage_summary": {"stats_found": 1, "stats_checked": 1},
        }

    @staticmethod
    def _finding(**over):
        base = {
            "title": "GRIM fail on baseline age", "severity": "suspicious",
            "confidence": "high", "location": "Table 1",
            "reported": "mean age 39.87 (SD 13.35)",
            "stage1_finding_ids": ["f1"],
        }
        base.update(over)
        return base

class TestHeadlineIsNotWeakerThanTheBody:
    """The headline may not understate the worst finding beneath it.

    Nothing tied the two fields together, and measured over the archived corpus
    5 of 16 reports headline a severity milder than a finding the same document
    goes on to make. The headline is printed first, in a blockquote, precisely
    so a reader who stops there still learns the most important thing -- so an
    understated one turns that design into a way to LOSE the finding.

    Scope: an ordering invariant on one field. It does not choose which finding
    becomes the headline and does not touch the severity-then-consequence
    ranking policy in `sort_findings`, which is the repo owner's call.
    """

    @staticmethod
    def _report(head_sev, finding_sevs):
        return {
            "headline": {"statement": "s", "severity": head_sev},
            "verdict": "unresolved", "confidence": "high",
            "findings": [{"rank": i + 1, "title": f"f{i}", "severity": s}
                         for i, s in enumerate(finding_sevs)],
            "not_checked": [], "limitations": [], "coverage_summary": {},
        }

class TestTheReportBodySpeaksTheCurrentVocabulary:
    """FOUND IN THE SHIPPED BUNDLE, 2026-08-13, not by reading the code.

    Romano's viewer chip read `unresolved` and the report body four inches
    below it read `Verdict: questionable`. One page, two vocabularies, and
    nothing on it tells a reader they are the same word.

    The cause is the shape this repository keeps producing: `verdicts.py` owns
    the vocabulary, defines `canonical()` and `is_legacy()`, has its own test
    file -- and had NO production consumer. The viewer mapped the value in its
    own JS (registered as a deliberate duplicate, since the page must be
    self-contained); this renderer printed it raw. Built, tested, consumed by
    nothing, in the one place where the cost is a reader mis-grading a paper.
    """

    @staticmethod
    def _obj(verdict):
        base = TestStructuredReportRendering._obj()
        base["verdict"] = verdict
        return base

    def test_the_vocabulary_module_has_a_production_consumer(self):
        """The guard against it going inert again. `lint-inert` cannot see this
        one: `verdicts.py` is reachable, well tested, and was imported by
        nothing outside `tests/`."""
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[1] / "src/metascience_agent"
        importers = [p.name for p in root.rglob("*.py")
                     if p.name != "verdicts.py"
                     and "import verdicts" in p.read_text(encoding="utf-8")]
        assert importers, "verdicts.py owns the vocabulary and nothing renders through it"


