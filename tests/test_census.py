"""Coverage against what was CHECKABLE, not against what was attempted.

Every coverage number this pipeline produced before this module used a
denominator of effort. `tables_checked` listed the tables a call was made
against, whether or not one cell inside them ran, so a run that submitted three
tables and had all 79 cells refused reported the same thing as a run that
checked all 79 and found them clean.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from metascience_agent.census import CONSUMABLE_KINDS, cell_census, render, summarise

LIKERT = [{"id": "v1", "name": "declared", "family": "likert_item",
           "lower_bound": 0, "upper_bound": 66}]


def cells(*specs):
    return [{"raw": raw, "row": i, "row_label": lab, "col_label": col}
            for i, (raw, lab, col) in enumerate(specs)]


class TestTheThreeNestedPopulations:
    def test_a_bare_number_is_not_consumable(self):
        e = cell_census(cells(("142", "count row", "x")))[0]
        assert not e["consumable"]
        assert "not a checkable cell kind" in e["missing"][0]

    def test_an_estimate_ci_runs_with_no_declaration_at_all(self):
        e = cell_census(cells(("1.42 (1.10-1.83)", "OR", "OR (95% CI)")))[0]
        assert (e["consumable"], e["routable"], e["runnable"]) == (True, True, True)

    def test_a_declared_mean_sd_is_routable_but_blocked_on_n(self):
        e = cell_census(cells(("4.20 (1.15)", "declared", "C")),
                        variables=LIKERT, bindings={"declared": "v1"})[0]
        assert (e["consumable"], e["routable"], e["runnable"]) == (True, True, False)
        assert e["missing"] == ["n"]

    def test_supplying_n_makes_it_runnable(self):
        c = cells(("4.20 (1.15)", "declared", "C"))
        c[0]["n"] = 59
        e = cell_census(c, variables=LIKERT, bindings={"declared": "v1"})[0]
        assert e["runnable"] and e["missing"] == []

    def test_an_undeclared_x_y_cell_counts_as_checkable_and_names_the_blocker(self):
        """It types `ambiguous` alone and `mean_sd` once a family is declared.

        Excluding it from the denominator would hide the largest single thing a
        declaration buys, and 76 of this corpus paper's 79 checkable cells are
        exactly this case.
        """
        e = cell_census(cells(("4.20 (1.15)", "undeclared", "C")))[0]
        assert e["kind"] == "ambiguous"
        assert e["consumable"] and not e["routable"]
        assert "variable declaration" in e["missing"][0]

    def test_resolvability_is_asked_of_the_resolver_not_assumed(self):
        """`_resolve_ambiguous` declines some readings, and a cell no family can
        rescue must not be counted as checkable."""
        e = cell_census(cells(("not a number at all", "x", "y")))[0]
        assert not e["consumable"]


class TestItMirrorsTheDispatcher:
    """A census that restates the routing rules instead of reusing them drifts
    from them, and then reports a denominator the checker does not share."""

    @pytest.mark.parametrize("raw,label", [
        ("4.20 (1.15)", "declared"),
        ("1.42 (1.10-1.83)", "declared"),
        ("25 (42.4)", "declared"),
    ])
    def test_runnable_agrees_with_check_table_actually_running(self, raw, label):
        from metascience_agent.dispatch import check_table
        c = cells((raw, label, "C (n = 59)"))
        c[0]["n"] = 59
        kw = dict(variables=LIKERT, bindings={label: "v1"})
        ran = check_table(cells=c, **kw)["n_checks_run"] > 0
        assert cell_census(c, **kw)[0]["runnable"] is ran

    def test_consumable_kinds_are_derived_from_dispatch_not_listed(self):
        from metascience_agent.dispatch import DISPATCH
        for kind in CONSUMABLE_KINDS:
            assert any(DISPATCH.get((k, dt)) for (k, dt) in DISPATCH if k == kind)


class TestTheSummaryDoesNotDoubleCount:
    def test_a_declaration_blocker_is_not_also_an_input_blocker(self):
        s = summarise(cell_census(
            cells(("4.20 (1.15)", "undeclared", "C"),
                  ("4.20 (1.15)", "declared", "C")),
            variables=LIKERT, bindings={"declared": "v1"}))
        assert s["blocked_on_declaration"] == 1
        assert s["blocked_on_input"] == 1
        assert s["missing_inputs"] == {"n": 1}

    def test_never_submitted_is_reported_separately_from_refused(self):
        c = cells(("1.42 (1.10-1.83)", "a", "x"), ("2.10 (1.50-2.90)", "b", "x"))
        s = summarise(cell_census(c), n_checked=1)
        assert s["n_runnable"] == 2 and s["never_submitted"] == 1

    def test_zero_checkable_is_reported_as_a_fact_about_the_tables(self):
        text = render(summarise(cell_census(cells(("n/a", "x", "y"))), n_checked=0))
        assert "nothing was checkable" in text
        assert "not a clean result" in text

    def test_coverage_is_none_rather_than_one_when_there_is_no_denominator(self):
        assert summarise(cell_census(cells(("n/a", "x", "y"))), n_checked=0)["coverage"] is None


class TestTheRealPaper:
    """The count this module exists to produce, on the paper that motivated it."""

    @pytest.fixture(scope="class")
    def entries(self):
        from metascience_agent.extraction.jats import (
            extract_xml_text_with_tables,
            get_table,
        )
        root = Path(__file__).resolve().parents[1]
        pdir = root / "tests/fixtures/papers/cerebrolysin_run_2026-08-09" / "10.3390--jpm11060545"
        xmls = list(pdir.glob("*.xml")) if pdir.exists() else []
        if not xmls:
            pytest.skip("cerebrolysin run corpus not present in this checkout")
        idx = extract_xml_text_with_tables(str(xmls[0]), max_chars=5000)
        out = []
        for t in range(1, (idx.get("n_tables") or 0) + 1):
            tab = get_table(str(xmls[0]), t)
            if not tab.get("found"):
                continue
            got = tab.get("cells") or []
            while tab.get("cells_total") and len(got) < tab["cells_total"]:
                nxt = get_table(str(xmls[0]), t, first_row=got[-1]["row"] + 1)
                more = nxt.get("cells") or []
                if not more:
                    break
                got += more
                tab = nxt
            out += cell_census(got, table=tab.get("label"))
        return out

    def test_it_finds_the_seventy_eight_checkable_cells(self, entries):
        """Originally 79, independently derived by the architecture audit; two
        measurements agreeing is the point of pinning it.

        79 -> 78 on 2026-08-12, and the lost cell is the whole reason for the
        change: Table 1 prints `0.817` in a `p-Value` COLUMN on an
        `MEP response (n (%))` ROW, and the row label won alone, typing a
        p-value of 0.817 as 81.7 PERCENT. It was `consumable` only under a
        reading that was false, and it was one of three cells this census
        counted as merely "blocked on input" -- i.e. waiting for an `n` so
        GRIM could be run against a p-value.

        A denominator that includes a mistyped cell overstates what could
        honestly have been checked, so 78 is the more accurate number and 79
        was never quite right.
        """
        assert summarise(entries)["n_consumable"] == 78

    def test_the_gap_is_overwhelmingly_declarations_not_missing_numbers(self, entries):
        s = summarise(entries, n_checked=0)
        assert s["blocked_on_declaration"] == 76
        # 3 -> 2: the third was the mistyped p-value above, which is no longer
        # consumable at all rather than consumable-and-waiting-for-an-n.
        assert s["blocked_on_input"] == 2
        assert s["coverage"] == 0.0


class TestItIsActuallyWiredIn:
    """A census nothing reads is the pattern this repo keeps finding.

    `not_run` was machine-generated per cell, documented, correct, and consumed
    by zero call sites for its entire existence. These tests exist so the census
    cannot join it.
    """

    def test_the_report_pass_computes_it_from_a_paper_directory(self):
        from metascience_agent.agent import _checkable_coverage
        root = Path(__file__).resolve().parents[1]
        pdir = root / "tests/fixtures/papers/cerebrolysin_run_2026-08-09" / "10.3390--jpm11060545"
        if not pdir.exists():
            pytest.skip("cerebrolysin run corpus not present in this checkout")
        out = _checkable_coverage(str(pdir), [])
        # 79 -> 78, 2026-08-12: see the fixture test above. The dropped cell is
        # a p-value that was typing as a percentage.
        assert out["n_consumable"] == 78
        assert out["cells_checked_via_check_table"] == 0
        assert "78 checkable cells" in out["note"]

    def test_a_paper_with_no_xml_returns_none_rather_than_a_misleading_zero(self, tmp_path):
        """Zero checkable cells and no tables to survey are different claims,
        and a zero here would read as the former."""
        from metascience_agent.agent import _checkable_coverage
        assert _checkable_coverage(str(tmp_path), []) is None

    def test_a_broken_paper_directory_never_breaks_a_paid_run(self):
        from metascience_agent.agent import _checkable_coverage
        assert _checkable_coverage("/nonexistent/path/xyz", []) is None


class TestTheRendererGetsTheFieldsItReads:
    """`_render_checkable_detail` read three keys the payload never carried.

    `agent._checkable_coverage` called `summarise` TWICE: the result WITHOUT
    `n_checked` was the one published, and the complete one was computed on the
    very next line and discarded except for its prose. So `n_checked`,
    `coverage` and `never_submitted` never reached `coverage_summary.checkable`,
    and the renderer's `never_submitted` branch has never printed on a real run.

    An inverse of this repo's usual defect -- here the CONSUMER existed and the
    producer silently withheld -- and the field it withheld is the one the
    census exists for: cells that could have run as they stand and were never
    submitted, i.e. available work the model skipped, as opposed to work it
    attempted and the dispatcher refused.
    """

    def _entries(self):
        from metascience_agent.census import cell_census
        cells = [{"raw": "12.34 (5.6)", "row_label": "Age", "col_label": "A", "n": 40},
                 {"raw": "8.10 (2.2)", "row_label": "Age", "col_label": "B", "n": 40}]
        variables = [{"id": "age", "family": "count", "bounds_are_stated": True,
                      "scale_min": 0, "scale_max": 120}]
        return cell_census(cells, variables=variables, bindings={"Age": "age"})

    def test_every_key_the_renderer_reads_is_produced(self):
        """Parsed out of the renderer rather than hand-listed, so a key added
        there without a producer fails here instead of rendering nothing."""
        import inspect, re
        from metascience_agent import census, report_render
        src = inspect.getsource(report_render._render_checkable_detail)
        read = set(re.findall(r"""c\.get\(["'](\w+)["']""", src))
        read |= set(re.findall(r"""c\[["'](\w+)["']\]""", src))
        produced = set(census.summarise(self._entries(), n_checked=1))
        produced.add("cells_checked_via_check_table")  # stamped by the caller
        missing = sorted(read - produced)
        assert not missing, (
            f"_render_checkable_detail reads {missing}, which summarise() does "
            "not produce. Either produce them or stop reading them."
        )

    def test_never_submitted_is_populated_and_prints(self):
        from metascience_agent import census
        from metascience_agent.report_render import _render_checkable_detail
        s = census.summarise(self._entries(), n_checked=0)
        assert "never_submitted" in s, "the field the census exists to report"
        s["cells_checked_via_check_table"] = 0
        out = "\n".join(_render_checkable_detail({"checkable": s}))
        if s["never_submitted"]:
            assert "never submitted to a check" in out

    def test_the_published_summary_carries_n_checked(self):
        """The exact regression: the payload lacked what the second, discarded
        call had computed."""
        from metascience_agent import census
        s = census.summarise(self._entries(), n_checked=2)
        assert s["n_checked"] == 2
        assert "coverage" in s


class TestThePredictorAdmitsWhenItIsWrong:
    """`_summarise` records `predictor_disagrees` and its comment says "It is
    now recorded". It was recorded and read by nothing.

    `never_submitted` is clamped at zero, so a NEGATIVE shortfall left no trace
    in the prose, and the reader got an arithmetic impossibility instead. From a
    real shipped report: "Coverage: 8 of 24 checkable cells were checked (33%).
    24 are waiting on a variable declaration." Eight plus twenty-four is
    thirty-two, out of twenty-four -- with the field explaining it sitting
    unread in the same JSON.
    """

    BASE = {"n_consumable": 24, "n_checked": 8, "coverage": 8 / 24,
            "n_cells": 40, "blocked_on_declaration": 24, "blocked_on_input": 0,
            "missing_inputs": {}, "never_submitted": 0}

    def test_the_contradiction_is_explained_in_the_prose(self):
        from metascience_agent.census import render

        text = render({**self.BASE, "predictor_disagrees": {
            "predicted_runnable": 0, "actually_checked": 8}})
        assert "do not add up" in text
        assert "the fault is ours" in text
        assert "0 cell(s) could run" in text and "checked 8" in text

    def test_it_names_which_number_to_believe(self):
        """A reader handed numbers that disagree needs to know which is the
        fact, not merely that they disagree."""
        from metascience_agent.census import render

        text = render({**self.BASE, "predictor_disagrees": {
            "predicted_runnable": 0, "actually_checked": 8}})
        assert "LOWER BOUND" in text

    def test_a_consistent_census_says_nothing_extra(self):
        """An audit that fires on every clean run teaches its reader to skip
        it, and is then worse than absent."""
        from metascience_agent.census import render

        text = render({**self.BASE, "n_checked": 20, "coverage": 20 / 24})
        assert "do not add up" not in text
