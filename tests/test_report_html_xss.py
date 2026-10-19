"""The markdown renderer passed raw HTML straight into the page.

`_report_html` renders the model-written report.md, and `_body_html` renders
the paper's own extracted text, both through the Python `markdown` library --
which passes inline HTML through untouched. Both inputs are attacker-influenced:
report.md is composed by the model FROM the paper, and body_html IS the paper.

A hostile author who knows their paper will be run through this tool can plant a
script in their abstract; it rides the model's quotation into report.md; the
viewer inlines report_html into the DOM, and it executes when the reviewer -- or
the accused author the bundle is forwarded to -- opens viewer.html from disk.

Reproduced: `_report_html("<script>alert(1)</script>")` returned that script
verbatim and live. The fix neutralises a `<` that opens a tag before markdown
sees it, which leaves every markdown construct working -- headers, tables,
bold, lists, and blockquotes (which depend on `>`).
"""
import re
import tempfile
from pathlib import Path

from forensic_metascience_ai_toolkit.bundle import _body_html, _report_html

LIVE_TAG = re.compile(r"<(script|img|iframe|svg|object|embed|link|style|body)\b", re.I)

ATTACKS = [
    "<script>alert(document.domain)</script>",
    "text <img src=x onerror=alert(1)> more",
    "<iframe src=javascript:alert(1)></iframe>",
    "<svg onload=alert(1)>",
    "<body onload=alert(1)>",
    "</script><script>alert(1)</script>",
]


class TestReportHtmlNeutralisesTags:
    def test_no_attack_survives_as_live_markup(self):
        for atk in ATTACKS:
            out = _report_html("## Findings\n\n" + atk + "\n")
            assert not LIVE_TAG.search(out), "live tag survived: " + repr(atk)

    def test_the_paper_body_path_is_covered_too(self):
        td = Path(tempfile.mkdtemp())
        for atk in ATTACKS:
            out = _body_html(td, "## Abstract\n\n" + atk + "\n")
            assert not LIVE_TAG.search(out), "live tag survived in body: " + repr(atk)


class TestMarkdownStillRenders:
    """The neutraliser must not be so broad it breaks the report's own
    formatting -- that would trade a security hole for an unreadable report."""

    def test_headers_bold_and_italic(self):
        out = _report_html("## Header\n\n**bold** and *italic*\n")
        assert "<h2>Header</h2>" in out
        assert "<strong>bold</strong>" in out
        assert "<em>italic</em>" in out

    def test_tables(self):
        out = _report_html("| a | b |\n|---|---|\n| 1 | 2 |\n")
        assert "<table>" in out and "<th>a</th>" in out

    def test_blockquotes_survive_because_gt_is_untouched(self):
        out = _report_html("> a quoted line\n")
        assert "<blockquote>" in out

    def test_less_than_in_prose_is_escaped_not_dropped(self):
        """'p < 0.05' is the single most common place a `<` appears in a
        statistics report, and it must render as text, not vanish."""
        out = _report_html("The threshold was p < 0.05 throughout.\n")
        assert "p &lt; 0.05" in out

    def test_lists(self):
        out = _report_html("- one\n- two\n")
        assert "<li>one</li>" in out
