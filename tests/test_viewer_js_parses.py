"""The viewer's JavaScript must actually parse.

MEASURED 2026-08-18, on a change made in this very file's name: a comment was
added inside an ARRAY LITERAL using the dollar-brace interpolation form that is
valid only inside a template literal. The result was a JavaScript syntax error,
and a syntax error in this bundle does not degrade the page -- it BLANKS it,
because every section renders from one parsed payload.

What makes that worth a dedicated test is how thoroughly the existing checks
missed it:

  * `render_viewer` returned a 281 KB document with no error, because Python
    is only doing string interpolation and does not know what JavaScript is;
  * three separate string assertions for the new text PASSED, because the
    broken text was present in the output exactly as written;
  * the full Python suite would have gone green.

Only extracting the script and handing it to a real parser caught it. That is
the same lesson as task #158, which found three viewer defects by opening the
page rather than by grepping it: presence of a string is not evidence that a
reader can see it, and here it was not even evidence that the page loads.

The single most dangerous edit in `bundle.py` is a stray backtick or an
unbalanced brace in one of the section builders, since they are JS template
literals written inside Python strings. This is the cheapest possible guard
against that, and it runs in under a second.
"""
import re
import shutil
import subprocess

import pytest

from forensic_metascience_ai_toolkit.bundle import render_viewer

NODE = shutil.which("node")

#: Exercises the branches that carry the most template-literal machinery:
#: an editorial report AND sweep findings (so the Findings page renders both
#: universes), a headline (the verdict cell's conditional), and a cell census
#: whose `checked` exceeds its `runnable` (the reconciliation clause).
PAYLOAD = {
    "paper_id": "10.0000/parse-check",
    "paper_title": "A paper for parsing",
    "report_obj": {
        "verdict": "unresolved",
        "confidence": "moderate",
        "headline": {"severity": "suspicious", "statement": "A headline",
                     "evidence": "M = 4.20, SD = 0.21", "rests_on": "stated_constraint"},
        "findings": [{"title": "One", "severity": "suspicious",
                      "stage1_finding_ids": ["1"]}],
    },
    "findings": [
        {"id": "1", "severity": "suspicious", "technique": "grim",
         "quote": "P &lt; 0.05"},
        {"id": "2", "severity": "consistent", "technique": "grimmer"},
    ],
    "calls": [{"tool": "grim", "arguments": {"mean": 1.0}}],
    "coverage_summary": {"checkable_detail": {
        "n_cells": 920, "n_consumable": 497, "n_runnable": 0,
        "cells_checked_via_check_table": 21,
        "blocked_on_input": 352, "blocked_on_declaration": 124}},
}


def _scripts(html: str) -> list[str]:
    """Every executable script block. The JSON payload block is NOT one."""
    return [body for attrs, body in
            re.findall(r"<script([^>]*)>(.*?)</script>", html, re.S)
            if "json" not in attrs.lower()]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
class TestItParses:
    def test_the_rendered_viewer_javascript_parses(self, tmp_path):
        html = render_viewer(PAYLOAD)
        blocks = _scripts(html)
        assert blocks, "no executable script block in the viewer"
        for i, body in enumerate(blocks):
            f = tmp_path / f"block{i}.js"
            f.write_text(body, encoding="utf-8")
            r = subprocess.run([NODE, "--check", str(f)],
                               capture_output=True, text=True, timeout=60)
            assert r.returncode == 0, (
                f"viewer script block {i} does not parse -- the page would "
                f"render BLANK:\n{r.stderr[:2000]}")

    def test_an_empty_run_still_parses(self, tmp_path):
        """The no-findings branch takes different template paths."""
        html = render_viewer({"paper_id": "10.0000/empty"})
        for i, body in enumerate(_scripts(html)):
            f = tmp_path / f"empty{i}.js"
            f.write_text(body, encoding="utf-8")
            r = subprocess.run([NODE, "--check", str(f)],
                               capture_output=True, text=True, timeout=60)
            assert r.returncode == 0, r.stderr[:2000]


class TestTheGuardIsHonestAboutItself:
    def test_it_says_so_when_node_is_missing(self):
        """A skipped parse check must not read as a passed one. This test runs
        everywhere and records which of the two happened."""
        if NODE is None:
            pytest.skip("node absent: the JS in this build was NEVER PARSED. "
                        "That is not a pass -- install node to check it.")
        assert NODE
