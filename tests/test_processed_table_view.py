"""A reader must be able to see what we made of a table, not just what it said.

GREG, 2026-08-12:

    "the user should be able to read the original and processed versions of
     whatever table the model had access to; this would reveal any gross
     parsing errors."

The ORIGINAL half already shipped -- `rows` carries every raw cell. The
PROCESSED half did not exist anywhere in the bundle: `dispatch.check_table`
computes `parse_cells(cells)` and returns only summary counts, so the typed
cells never reached the tool result, the ledger, or disk. An audit of a rendered
bundle found zero `kind` strings across 2.6 MB of HTML.

That gap is what makes this repo's oldest bug invisible: a table where every
cell fails to parse renders identically to a table with nothing checkable in it,
and the run then reports our failure as a property of the paper.

A PREREQUISITE CAME WITH IT. `_table_records` called `get_table` once, and
`get_table` WINDOWS `cells` while returning `data` whole. Measured across 188
corpus tables: the pane's cell list held 7,923 of 12,304 cells (64%), and 47
tables (25%) were short. Building a processed overlay on that would have drawn
our own truncation as the paper's parse holes -- the same bug, one layer up.
"""
import json
import pathlib

import pytest

from metascience_agent.bundle import _paged_table, _processed_cells, _table_records
from metascience_agent.extraction.jats import extract_xml_text_with_tables, get_table

REPO = pathlib.Path(__file__).resolve().parent.parent
PAPER = REPO / "tests/fixtures/papers/high_value_pdfs_to_run_on" / "10.1038--s41537-025-00576-3"
pytestmark = pytest.mark.skipif(not PAPER.exists(), reason="corpus paper absent")


def _xml():
    return str(next(PAPER.glob("*.xml")))


class TestThePagingPrerequisite:
    def test_get_table_windows_cells_but_not_data(self):
        """The asymmetry the viewer was built on top of without noticing."""
        w = get_table(_xml(), 2)
        assert w["found"]
        assert len(w["cells"]) < w["cells_total"], (
            "this test needs a table large enough to be windowed")
        assert w["data_is_complete"] is True, (
            "`data_is_complete` describes the GRID; it is true even when the "
            "cell list stops mid-table, which is exactly why it must never be "
            "read as 'I have the whole table'")

    def test_paged_table_reaches_the_end(self):
        w, p = get_table(_xml(), 2), _paged_table(_xml(), 2)
        assert len(p["cells"]) == p["cells_total"] > len(w["cells"])
        assert p["cells_short"] is False

    def test_a_short_walk_says_so_rather_than_looking_complete(self):
        """`cells_short` is the difference between a stated limitation and a
        false statement about the paper."""
        p = _paged_table(_xml(), 2, max_pages=1)
        assert p["cells_short"] is True
        assert len(p["cells"]) < p["cells_total"]

    def test_the_records_builder_uses_the_paged_list(self):
        recs = _table_records(PAPER)
        idx = extract_xml_text_with_tables(_xml())
        totals = {e["table_num"]: get_table(_xml(), e["table_num"]).get("cells_total")
                  for e in idx["tables"]}
        for rec, num in zip(recs, sorted(totals)):
            assert rec["processed"]["n"] == totals[num], (
                f"{rec['label']}: processed view built from "
                f"{rec['processed']['n']} of {totals[num]} cells")


class TestTheProcessedOverlay:
    def test_every_table_record_carries_one(self):
        for rec in _table_records(PAPER):
            assert "processed" in rec
            assert rec["processed"]["n"] > 0

    def test_cells_are_positioned_on_the_grid_the_viewer_draws(self):
        """Slots are `row,col` into `rows`. A wrong slot is worse than a gap, so
        a cell whose column heading is not in `headers` is DROPPED and counted
        rather than guessed at."""
        for rec in _table_records(PAPER):
            grid, proc = rec["rows"], rec["processed"]
            for key in proc["cells"]:
                r, c = (int(x) for x in key.split(","))
                assert 0 <= r < len(grid), f"{rec['label']} slot {key} off-grid"
                assert 0 <= c < max(len(row) for row in grid)

    def test_almost_every_cell_places(self):
        for rec in _table_records(PAPER):
            p = rec["processed"]
            placed = len(p["cells"])
            assert placed / p["n"] >= 0.95, (
                f"{rec['label']}: only {placed} of {p['n']} cells positioned")

    def test_it_reports_the_kinds_and_the_coverage(self):
        rec = _table_records(PAPER)[0]
        p = rec["processed"]
        assert p["kind_counts"] and sum(p["kind_counts"].values()) == p["n"]
        assert 0.0 <= p["coverage"] <= 1.0

    def test_an_unread_cell_is_present_and_marked_rather_than_absent(self):
        """The whole point. A `non_numeric` cell must appear in the overlay --
        rendered struck out -- because a HOLE in the grid is the thing a reader
        can see, and a missing entry is the thing they cannot."""
        found = False
        for rec in _table_records(PAPER):
            for slot in rec["processed"]["cells"].values():
                if slot["kind"] == "non_numeric":
                    found = True
                    assert "value" not in slot
        assert found, "no unread cell in this paper; the test needs one"

    def test_the_shape_clusters_ride_along(self):
        """A systematic failure is one sentence, not N silent cells."""
        recs = _table_records(PAPER)
        clustered = [c for r in recs for c in r["processed"]["unparsed"]
                     if c.get("numeric_shaped")]
        assert clustered, "expected at least one numeric-shaped unread cluster"
        assert all("shape" in c and "n" in c for c in clustered)

    def test_it_survives_a_table_with_no_cells(self):
        assert _processed_cells({"cells": [], "headers": []}, [])["n"] == 0


class TestItReachesTheRenderedPage:
    """Facts in Python and presentation in JS is a named failure mode here."""

    @pytest.fixture(scope="class")
    def built(self, tmp_path_factory):
        """Bundles a COPY of the archived run, never the corpus in place.

        `build_bundle` builds the derived `tables/` package beside the paper
        it bundles. Pointed at the corpus, this test rewrote the TRACKED
        `tables/` of `10.1001--jamanetworkopen.2023.37679`: harmlessly where
        `.extraction_cache` exists (same bytes back), destructively in a fresh
        checkout, where the walker finds nothing extracted and 289 lines of
        the three-table package became an empty stub (found 2026-09-29)."""
        import glob
        import hashlib
        import shutil

        from metascience_agent import bundle
        runs = sorted(glob.glob(str(REPO / "tests/fixtures/papers/high_value_pdfs_to_run_on" / "*"
                                    / "forensic_review*" / "report.json")))
        if not runs:
            pytest.skip("no archived run to bundle")
        review = pathlib.Path(runs[0]).parent
        paper = review.parent

        def corpus_state():
            # Everything the bundle could write beside the paper; the review
            # folders and old bundles are outside that reach.
            return {str(p.relative_to(paper)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(paper.rglob("*")) if p.is_file()
                    and not p.relative_to(paper).parts[0].startswith("forensic_review")}

        before = corpus_state()
        # Sources, extraction cache and the one run being bundled; not the
        # other runs or old bundles (most of the folder's 18 MB).
        copy = tmp_path_factory.mktemp("corpus") / paper.name
        shutil.copytree(paper, copy, ignore=lambda d, names: [
            n for n in names if pathlib.Path(d) == paper
            and n.startswith("forensic_review") and n != review.name])
        out = tmp_path_factory.mktemp("bundle") / "b"
        bundle.build_bundle(str(copy / review.name), str(out))
        assert corpus_state() == before, "building the bundle wrote into the corpus"
        return (out / "viewer.html").read_text(encoding="utf-8")

    def test_the_payload_carries_the_processed_cells(self, built):
        import re
        blocks = re.findall(r"<script[^>]*>(.*?)</script>", built, re.S)
        payload = next(json.loads(b) for b in blocks if b.strip().startswith("{"))
        recs = payload.get("table_records") or []
        assert recs, "no table records in the built bundle"
        assert all(r.get("processed", {}).get("n") for r in recs)

    def test_the_toggle_and_its_styles_are_rendered(self, built):
        assert "toggleProcessed(this)" in built, "no control to switch views"
        assert "function toggleProcessed" in built, "control with no handler"
        assert ".showproc .rawcell{display:none}" in built.replace("\n", "")
        assert "prcell" in built
