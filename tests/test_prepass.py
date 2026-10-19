"""Checks aimed by the harness at every eligible target, not by a model at some.

FROM THE ROMANO VARIABILITY STUDY, 2026-08-11. Two runs of one paper at
byte-identical prompt and schema:

    checks with a unique, argument-free target    8 of 8 recurred  (100%)
    checks where the model picks the target
      or supplies an auxiliary assumption         0 of 10 recurred (0%)

`detect_duplication` ran in one run (960 comparisons, clean) and not the other
-- and the run that skipped it wrote "Whole paper, detect_duplication" into its
own `not_checked` list, so the system knew what it was skipping and skipped it
anyway. A check whose target is the whole paper has nothing to choose.

TWO PROPERTIES THIS FILE DEFENDS, and they pull in opposite directions.

  1. EXHAUSTIVE. Every eligible target is enumerated from the paper's own
     tables, so this slice of coverage is identical from run to run by
     construction. That is the only kind of coverage a detection-rate claim can
     rest on.

  2. NEVER ON INVENTED INPUTS. Exhaustive targeting multiplies whatever it does,
     so it must multiply refusals rather than assumptions. `dispatch.py` records
     the cost of getting this wrong: SPRITE, handed a count variable with no
     stated bounds, assumed a 1-7 Likert scale and returned `impossible` on a
     paper that was fine.

MEASURED OVER 11 ARCHIVED RUNS, and the second property dominates:

    mean_sd cells enumerated        501
      bound by name recovery         19
      CHECKED                         0
      refused, no declaration       482
      refused, bounds not stated     19

Zero checks, 501 correct refusals. The blocker is upstream of targeting:
`bounds_are_stated()` needs `confidence == "high"` plus a verified provenance
quote, and across 199 archived variable declarations that has never been
produced. Finding that is what the sweep bought.
"""
import glob
import json
from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit import prepass as P

REPO = Path(__file__).resolve().parents[1]
ROMANO = REPO / "tests/fixtures/papers/high_value_pdfs_to_run_on/10.1002--eat.24415"


def _tab(label, cells):
    return {"label": label, "cells": cells}


def _cell(raw, row_label, row=1):
    return {"raw": raw, "row": row, "row_label": row_label, "col_label": "M (SD)"}


def _unextracted(paper_dir: Path) -> list[str]:
    """`["file (role): why"]` for every PDF of this paper the sweep cannot read.

    ADDED 2026-08-17, when `extraction/pdf.py` became docling-only and
    CACHE-ONLY (Greg, 2026-08-16: pdfplumber "should never run *anywhere*").
    Before that, a supplement PDF nobody had extracted still came back as
    pdfplumber text; now it comes back `unreadable`, and the archive replay
    below cannot tell that from a paper with no tables.

    ASKS `cache_status`, NOT "is there a cache file". Presence is not
    usability, and the gap is the whole point here: MEASURED 2026-08-17, 13 of
    the 16 cache entries under `high_value_pdfs_to_run_on/` were written before
    per-page text existed, and `extract_text_with_tables` -- the only route a
    supplement PDF now has into this sweep -- refuses without it.

    Enumerated by `agent._pdfs_to_extract`, which is the list `analyze`'s
    pre-flight extracts, so the precondition asserted here is exactly "this
    paper has been through that pre-flight". A second list of the same files
    kept in this test would eventually be the more permissive one.
    """
    from forensic_metascience_ai_toolkit.agent import _pdfs_to_extract
    from forensic_metascience_ai_toolkit.extraction import docling_tables as _dl

    cold = []
    for pdf, role in _pdfs_to_extract(str(paper_dir)):
        usable, why = _dl.cache_status(pdf)
        if not usable:
            cold.append(f"{pdf.name} ({role}): {why}")
    return cold


class TestTheTableWalkIsSharedNotCopied:
    """Two walks would be two denominators, and this repo has already published
    one coverage figure computed against a different denominator from the one
    printed beside it."""

    def test_agent_uses_prepass_for_its_census(self):
        src = ((REPO / "src/forensic_metascience_ai_toolkit/agent.py").read_text(encoding="utf-8")
                + (REPO / "src/forensic_metascience_ai_toolkit/parallel.py").read_text(encoding="utf-8"))
        assert "_prepass.paper_tables(paper_dir" in src

    def test_the_census_and_the_sweeps_walk_the_same_tables(self):
        """RE-EXPRESSED 2026-08-13. The assertion above pinned the literal call
        `_prepass.paper_tables(paper_dir)`, so adding an `include_supplements`
        argument broke it while the property it guards was untouched.

        The property is not the spelling of the call. It is that the census and
        the exhaustive sweeps enumerate the SAME tables -- which is what stops
        two denominators existing for one paper, and is now checkable directly,
        because a flag decides the population."""
        import re
        agent = ((REPO / "src/forensic_metascience_ai_toolkit/agent.py").read_text(encoding="utf-8")
                + (REPO / "src/forensic_metascience_ai_toolkit/parallel.py").read_text(encoding="utf-8"))
        prep = (REPO / "src/forensic_metascience_ai_toolkit/prepass.py").read_text(encoding="utf-8")

        def _supplements_in_scope(src, pattern):
            m = re.search(pattern, src)
            assert m, f"no paper_tables call matched {pattern!r}"
            return "include_supplements=True" in m.group(0)

        census = _supplements_in_scope(
            agent, r"_prepass\.paper_tables\(paper_dir[^)]*\)")
        sweeps = _supplements_in_scope(
            prep, r"\n    tables = paper_tables\(paper_dir[^)]*\)")
        assert census == sweeps, (
            "the census and the exhaustive sweeps disagree about whether "
            "supplements are in scope, which is two denominators for one paper")

    def test_a_paper_with_no_xml_yields_no_tables(self, tmp_path):
        assert P.paper_tables(tmp_path) == []

    def test_the_real_paper_yields_its_tables(self):
        if not ROMANO.is_dir():
            pytest.skip("Romano not in this checkout")
        tabs = P.paper_tables(ROMANO)
        assert len(tabs) == 2
        assert sum(len(t["cells"]) for t in tabs) == 314, (
            "the census denominator; if this moves, every coverage figure moves")


class TestDuplicationAlwaysRuns:
    def test_it_runs_without_any_declaration(self):
        tabs = [_tab("T1", [_cell("10.0 (2.0)", "A", 1), _cell("11.0 (3.0)", "B", 2)])]
        out = P.sweep_duplication(tabs)
        assert out["ran"] is True
        assert out["targets_enumerated"] == 2

    def test_one_block_per_table(self):
        """Collapsing tables into one block would call two tables reporting the
        same cohort a duplication."""
        tabs = [_tab("T1", [_cell("10.0 (2.0)", "A")]),
                _tab("T2", [_cell("10.0 (2.0)", "B")])]
        assert P.sweep_duplication(tabs)["n_blocks"] == 2

    def test_no_pairs_is_a_refusal_not_a_clean_result(self):
        """"No duplication found" over zero comparisons is a statement about a
        search that never happened."""
        out = P.sweep_duplication([_tab("T1", [_cell("42", "A")])])
        assert out["ran"] is False
        assert out["severity"] == "indeterminate"
        assert "nothing to compare" in out["why_not"]

    def test_the_real_paper_is_swept(self):
        if not ROMANO.is_dir():
            pytest.skip("Romano not in this checkout")
        out = P.sweep_duplication(P.paper_tables(ROMANO))
        assert out["ran"] is True and out["targets_enumerated"] == 6


class TestSdRangeRefusesRatherThanAssumes:
    BOUNDED = {"id": "v1", "name": "Mood", "family": "likert_composite",
               "lower_bound": 1, "upper_bound": 5, "confidence": "high"}

    def test_an_undeclared_variable_is_skipped_and_counted(self):
        tabs = [_tab("T1", [_cell("3.0 (1.0)", "Mood")])]
        out = P.sweep_sd_range(tabs, [], {})
        assert out["targets_enumerated"] == 1
        assert out["n_checked"] == 0 and out["n_skipped_undeclared"] == 1

    def test_bounds_that_are_not_stated_are_skipped_and_counted(self):
        """THE LINE THAT MUST NOT MOVE. Bounds we supplied make the check a
        statement about our assumption, not about the paper."""
        tabs = [_tab("T1", [_cell("3.0 (1.0)", "Mood")])]
        out = P.sweep_sd_range(tabs, [self.BOUNDED], {"Mood": "v1"})
        assert out["n_checked"] == 0
        assert out["n_skipped_unstated_bounds"] == 1

    def test_a_variable_with_no_bounds_at_all_is_skipped(self):
        v = {"id": "v1", "name": "Age", "family": "continuous", "confidence": "high"}
        tabs = [_tab("T1", [_cell("39.9 (13.4)", "Age")])]
        out = P.sweep_sd_range(tabs, [v], {"Age": "v1"})
        assert out["n_checked"] == 0 and out["n_skipped_unstated_bounds"] == 1

    def test_every_target_is_counted_even_when_none_can_run(self):
        """A refusal that is not counted is indistinguishable from a target
        nobody looked at, and that distinction is the whole point."""
        tabs = [_tab("T1", [_cell("3.0 (1.0)", "A", 1), _cell("4.0 (1.0)", "B", 2)])]
        out = P.sweep_sd_range(tabs, [], {})
        assert out["targets_enumerated"] == 2
        assert (out["n_checked"] + out["n_skipped_undeclared"]
                + out["n_skipped_unstated_bounds"]) == 2


class TestTheNameBindingIsPreciseAndThin:
    """`bindings` is a per-call argument to `parse_cells_typed`; the anatomy
    block written to findings.json carries variables and NO row-label map, so a
    harness reading it has declarations it cannot reach. Recovered by exact
    normalised name match: 19 of 501 archived cells (4%), ZERO ambiguous."""

    def test_an_exact_name_match_binds(self):
        v = {"id": "v1", "name": "Baseline age", "family": "continuous"}
        tabs = [_tab("T1", [_cell("39.9 (13.4)", "Baseline age")])]
        out = P.sweep_sd_range(tabs, [v], None)
        assert out.get("n_bound_by_name") == 1

    def test_punctuation_and_case_do_not_block_it(self):
        v = {"id": "v1", "name": "Baseline BMI", "family": "continuous"}
        tabs = [_tab("T1", [_cell("25.0 (4.0)", "baseline  bmi")])]
        assert P.sweep_sd_range(tabs, [v], None).get("n_bound_by_name") == 1

    def test_two_variables_with_one_name_bind_to_neither(self):
        """Binding a row to the wrong variable re-reads the cell against bounds
        that were never its own. Ambiguity is skipped, not resolved."""
        vs = [{"id": "a", "name": "Score"}, {"id": "b", "name": "Score"}]
        tabs = [_tab("T1", [_cell("3.0 (1.0)", "Score")])]
        out = P.sweep_sd_range(tabs, vs, None)
        assert not out.get("n_bound_by_name")
        assert out["n_skipped_undeclared"] == 1

    def test_an_explicit_binding_wins_over_the_derived_one(self):
        vs = [{"id": "a", "name": "Score"}, {"id": "b", "name": "Other"}]
        tabs = [_tab("T1", [_cell("3.0 (1.0)", "Score")])]
        out = P.sweep_sd_range(tabs, vs, {"Score": "b"})
        assert not out.get("n_bound_by_name"), "the model's own map is authoritative"

    def test_it_is_not_a_fuzzy_match(self):
        """The 89%-failure location join in `weight_finding_severity` is what
        free-text similarity buys."""
        v = {"id": "v1", "name": "Baseline age at intake"}
        tabs = [_tab("T1", [_cell("39.9 (13.4)", "Baseline age")])]
        assert not P.sweep_sd_range(tabs, [v], None).get("n_bound_by_name")


class TestTheArchiveReplayed:
    """The measurement the module documents. A ratchet: the sweep may check
    MORE as bounds provenance improves, never fewer targets.

    GATED ON EXTRACTION SINCE 2026-08-17, and not in order to make it pass. A
    supplement PDF reaches this replay through `extract_text_with_tables`,
    which is now docling-only and CACHE-ONLY, so an unextracted supplement
    comes back `unreadable` -- whereupon `supplements_read.extract_pdf_tables`
    does the only other thing it can and renders every page at 300 dpi for OCR.
    MEASURED: the fixture stopped returning. On
    `10.1001--jamanetworkopen.2023.37679` it was still inside `rapidocr` after
    180 s on the first supplement it reached, and a `pytest` run of this file
    was killed at 1800 s without the fixture ever finishing.

    THE COUNTS WOULD BE WRONG EVEN IF IT FINISHED. With both
    supplement-carrying papers unreadable, the nine runs that still replay
    enumerate 231 `mean_sd` cells (2026-08-17) against the 501 this module
    documents. That is not an enumeration that shrank, it is a corpus nobody
    extracted -- OUR gap, and booking it as a fact about the sweep is the
    mistake this repository keeps a standing rule against.

    So the precondition is checked FIRST and named, and a partial replay is not
    offered: a subset of the archive is a different denominator from the 501
    the threshold below is calibrated on, and one quantity with two
    denominators is the defect this module exists to prevent."""

    @pytest.fixture(scope="class")
    def swept(self):
        """The archive replayed -- over a corpus that has been extracted, or
        not at all.

        THE CHECK RUNS BEFORE THE FIRST REPLAY, because what it prevents is not
        an exception that a later assertion could catch. It is a 300 dpi OCR
        pass over every page of an unextracted supplement, which does not come
        back; see the class docstring for the measurement.
        """
        files = sorted(glob.glob(str(
            REPO / "tests/fixtures/papers/high_value_pdfs_to_run_on/*/forensic_review*/findings.json")))
        papers: list[Path] = []
        for f in files:
            d = Path(f).parent.parent
            if d not in papers:
                papers.append(d)
        cold = [(p, _unextracted(p)) for p in papers]
        cold = [(p, why) for p, why in cold if why]
        if cold:
            detail = "\n".join(
                f"  {p.name}\n" + "\n".join(f"    {w}" for w in why)
                for p, why in cold)
            pytest.skip(
                "the archive replay needs every corpus PDF read by docling, "
                f"and {len(cold)} of the {len(papers)} papers it replays are "
                f"not extracted:\n{detail}\n"
                "Run `metascience extract-tables <paper_dir> --force` on each, "
                "then re-run this file. Replaying only the extracted subset is "
                "deliberately NOT offered: it would be a different denominator "
                "from the 501 cells this ratchet is calibrated on.")
        runs = []
        for f in files:
            d = Path(f)
            try:
                fj = json.loads(d.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            out = P.run_exhaustive(d.parent.parent, fj)
            if out:
                runs.append(out)
        if not runs:
            pytest.skip("no archived runs with tables in this checkout")
        return runs

    def test_duplication_runs_on_every_paper_that_has_pairs(self, swept):
        ran = [s for s in swept if s["duplication"]["ran"]]
        assert ran, "the always-run check ran nowhere"

    def test_every_sd_target_is_accounted_for(self, swept):
        for s in swept:
            r = s["sd_range"]
            assert (r["n_checked"] + r["n_skipped_undeclared"]
                    + r["n_skipped_unstated_bounds"]) == r["targets_enumerated"]

    def test_the_enumeration_has_not_shrunk(self, swept):
        tot = sum(s["sd_range"]["targets_enumerated"] for s in swept)
        assert tot >= 400, (
            f"only {tot} mean_sd cells enumerated, down from the measured 501. "
            "Exhaustive targeting that quietly stopped being exhaustive is the "
            "one failure this module cannot tolerate.")

    def test_nothing_ran_on_unstated_bounds(self, swept):
        """The invariant, across the whole archive. If a check ever runs here,
        it must be because a variable finally EARNED `bounds_are_stated`."""
        for s in swept:
            for res in s["sd_range"]["results"]:
                assert res["bounds"][0] is not None
                assert res["bounds"][1] is not None


class TestProvenGlyphRepairOnTableCells:
    """Table cells carry the same font damage the prose does. MEASURED over the
    211 cached Zotero extractions: 195 of 24,112 cells (0.81%) hold a raw
    control character, 178 of them in EPIVI7B3 -- the paper whose own text
    proves `\\x06` is `±`. Repairing it there moves cell coverage from 0.440 to
    0.698, with 124 cells going `non_numeric` -> `mean_sd` and nothing moving
    the other way."""

    def _paper(self, tmp_path, body: str):
        d = tmp_path / "10.9999--demo"
        d.mkdir()
        (d / "body.md").write_text(body, encoding="utf-8")
        return d

    def test_a_proven_document_gets_its_cells_back(self, tmp_path):
        from forensic_metascience_ai_toolkit.tools.celltypes import parse_cells
        d = self._paper(tmp_path, "# Body\n\nValues are mean \x06 SD throughout.\n")
        tabs = [{"label": "T1", "cells": [
            {"raw": "65 \x06 1.17", "row": 1, "row_label": "Age", "col_label": "A"}]}]
        probs: list = []
        P._repair_proven_glyphs(d, tabs, probs)
        assert tabs[0]["cells"][0]["raw"] == "65 ± 1.17"
        typed = parse_cells(tabs[0]["cells"])["cells"][0]
        assert typed["kind"] == "mean_sd" and typed["value"] == 65.0
        assert any("repaired 1 table cell" in p for p in probs)

    def test_an_unproven_glyph_in_the_same_cell_keeps_it_refused(self, tmp_path):
        """EPIVI7B3 spells MINUS as `\\x00`, which nothing proves. A cell
        reading `\\x00 3.5 \\x06 7.6` becomes `\\x00 3.5 ± 7.6` and still will
        not type -- correctly, because its sign is still missing. Repairing what
        is proven must not imply the rest is now safe."""
        from forensic_metascience_ai_toolkit.tools.celltypes import parse_cells
        d = self._paper(tmp_path, "# Body\n\nValues are mean \x06 SD throughout.\n")
        tabs = [{"label": "T1", "cells": [
            {"raw": "\x00 3.5 \x06 7.6", "row": 1, "col_label": "A"}]}]
        P._repair_proven_glyphs(d, tabs, [])
        assert parse_cells(tabs[0]["cells"])["cells"][0]["kind"] == "non_numeric"

    def test_an_unproven_document_is_left_alone_and_says_so(self, tmp_path):
        d = self._paper(tmp_path, "# Body\n\nP < 0\x0605 and 1.89±0.21 elsewhere.\n")
        tabs = [{"label": "T1", "cells": [
            {"raw": "65 \x06 1.17", "row": 1, "col_label": "A"}]}]
        probs: list = []
        P._repair_proven_glyphs(d, tabs, probs)
        assert tabs[0]["cells"][0]["raw"] == "65 \x06 1.17"
        assert any("does not prove" in p for p in probs)

    def test_a_clean_paper_costs_nothing(self, tmp_path):
        """The scan for a control character happens before the paper text is
        read at all: 99.2% of papers have none."""
        d = self._paper(tmp_path, "# Body\n\nordinary text\n")
        tabs = [{"label": "T1", "cells": [{"raw": "65 ± 1.17", "row": 1}]}]
        probs: list = []
        P._repair_proven_glyphs(d, tabs, probs)
        assert tabs[0]["cells"][0]["raw"] == "65 ± 1.17"
        assert probs == []
