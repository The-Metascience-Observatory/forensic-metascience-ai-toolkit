"""The hand-off audit must not print "ok" over tables it could not read.

`prepass.paper_tables` returns a list SUBCLASS that carries `.problems` so a
caller can tell "no tables" from "could not read the tables". The one caller
that wanted them -- `handoff.audit` -- wrapped the result in `list(...)`,
which builds a plain list and drops the attribute, so `tbl_problems` was
always empty and the audit said "tables are enumerated: ok" regardless. Found
by the 2026-09-02 audit as an unused local (ruff F841); the unused local was
the symptom, the `list()` the cause.
"""
from __future__ import annotations

import pytest

from metascience_agent import handoff, prepass


@pytest.fixture
def paper(tmp_path):
    (tmp_path / "body.md").write_text("A paper with one table.\n")
    return tmp_path


def _rows(paper):
    return handoff.audit(paper).get("links") or handoff.audit(paper).get("rows") or []


class TestWalkerProblemsReachTheRow:
    def test_a_problem_is_named_and_the_link_is_not_ok(self, paper, monkeypatch):
        def broken_walk(base, include_supplements=False):
            return prepass._walked([], ["table 1 unreadable: ValueError: bad cell"])
        monkeypatch.setattr(prepass, "paper_tables", broken_walk)
        out = handoff.audit(paper)
        rows = [r for r in _iter_rows(out) if r.get("link") == "tables are enumerated"]
        assert rows, out
        row = rows[0]
        assert "table 1 unreadable" in (row.get("note") or ""), row
        assert row["ok"] is False

    def test_a_clean_walk_adds_no_complaint(self, paper, monkeypatch):
        monkeypatch.setattr(prepass, "paper_tables",
                            lambda base, include_supplements=False: prepass._walked([], []))
        out = handoff.audit(paper)
        rows = [r for r in _iter_rows(out) if r.get("link") == "tables are enumerated"]
        assert rows
        assert "problem(s) reported by the walker" not in (rows[0].get("note") or "")


def _iter_rows(out):
    """The audit's rows, wherever it keeps them."""
    for key in ("links", "rows", "handoffs"):
        v = out.get(key)
        if isinstance(v, list):
            return v
    for v in out.values():
        if isinstance(v, list) and v and isinstance(v[0], dict) and "link" in v[0]:
            return v
    return []
