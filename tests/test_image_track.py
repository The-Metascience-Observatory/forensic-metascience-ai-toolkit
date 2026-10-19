"""The image track's containment contract, pinned as tests.

The design promise (plan, 2026-08-17): the image track can NEVER sink or
distort the paid text review. That decomposes into testable facts:

  * the parent-side client `_run_image_track` never raises -- a crashed,
    hung, missing, or garbage-emitting child becomes a status record;
  * no accusatory severity crosses the child->parent boundary, whatever the
    child claims -- the quarantine is enforced a second time at validation;
  * the child's refusal subtypes stay distinct: engine_missing (installation)
    != no_pdf (directory) != pdf_unreadable (file) != no_rasters (paper),
    because collapsing them writes a claim about the authors out of a missing
    package.
"""

from __future__ import annotations

import json
import os
import stat
import sys
import types
from pathlib import Path

import pytest

from metascience_observatory_image_analysis.image_forensics import image_track as IT
from metascience_agent.agent import (
    _run_image_track,
    _validate_image_track_output,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_ROW = {
    "id": "IMGDUP-1", "location": "Figure 2 (page 3)",
    "technique": "image_duplication", "consistent": False,
    "severity": "indeterminate",
    "reproduction": "metascience image-analysis x.pdf",
    "explanation": "QUARANTINED signal", "severity_before_quarantine": "suspicious",
    "quarantine_reason": "uncalibrated",
}

VALID_OUTPUT = {
    "schema_version": "1.0", "paper_id": "p",
    "status": {"ran": True, "refusal_subtype": None, "wall_seconds": 0.1,
               "detail": "1 duplicate group(s)"},
    "result": {}, "findings_rows": [VALID_ROW],
}


def _fake_child(tmp_path: Path, body: str) -> str:
    """A stand-in for the child interpreter: METASCIENCE_IMAGE_PYTHON points
    here and the bash script ignores its `-m ...` arguments. This tests the
    CLIENT against child behaviors (garbage, crash, hang) that the real child
    is specifically built never to exhibit on purpose."""
    script = tmp_path / "fake_python"
    script.write_text("#!/bin/bash\n" + body + "\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


def _stub_detector(monkeypatch, result: dict):
    """Install a stub image_forensics.image_analysis so run_track tests do not
    depend on the real detector (built separately)."""
    mod = types.ModuleType("metascience_observatory_image_analysis.image_forensics.image_analysis")
    mod.analyze_paper_images = lambda *a, **k: result
    monkeypatch.setitem(sys.modules, "metascience_observatory_image_analysis.image_forensics.image_analysis", mod)


# ---------------------------------------------------------------------------
# Parent-side validation: the second quarantine
# ---------------------------------------------------------------------------


class TestValidation:
    def test_a_valid_object_passes(self):
        status, rows = _validate_image_track_output(json.loads(json.dumps(VALID_OUTPUT)))
        assert status["ran"] is True
        assert rows == [VALID_ROW]

    def test_wrong_schema_version_is_rejected(self):
        bad = {**VALID_OUTPUT, "schema_version": "2.0"}
        with pytest.raises(ValueError):
            _validate_image_track_output(bad)

    def test_an_accusatory_severity_cannot_cross_the_boundary(self):
        """The quarantine, enforced at the boundary. Even a child that CLAIMS
        highly_suspicious delivers nothing."""
        row = {**VALID_ROW, "severity": "highly_suspicious"}
        bad = {**VALID_OUTPUT, "findings_rows": [row]}
        with pytest.raises(ValueError, match="accusatory"):
            _validate_image_track_output(bad)

    def test_a_wrong_technique_is_rejected(self):
        row = {**VALID_ROW, "technique": "grim"}
        bad = {**VALID_OUTPUT, "findings_rows": [row]}
        with pytest.raises(ValueError):
            _validate_image_track_output(bad)

    def test_a_row_missing_required_keys_is_rejected(self):
        row = {k: v for k, v in VALID_ROW.items() if k != "reproduction"}
        bad = {**VALID_OUTPUT, "findings_rows": [row]}
        with pytest.raises(ValueError):
            _validate_image_track_output(bad)


# ---------------------------------------------------------------------------
# Parent-side client: never raises, one fate per failure mode
# ---------------------------------------------------------------------------


class TestClientContainment:
    # Sync tests driving the async client via asyncio.run -- the house
    # pattern (see tests/test_usage_guard.py), because the suite runs with
    # plugin autoload disabled and no pytest-asyncio.
    def _run(self, tmp_path, monkeypatch, child_body, timeout_s=10.0):
        import asyncio
        monkeypatch.setenv("METASCIENCE_IMAGE_PYTHON",
                           _fake_child(tmp_path, child_body))
        return asyncio.run(_run_image_track(tmp_path, timeout_s=timeout_s))

    def test_valid_output_injects_rows(self, tmp_path, monkeypatch):
        rec = self._run(
            tmp_path, monkeypatch,
            f"echo '{json.dumps(VALID_OUTPUT)}'")
        assert rec["ran"] is True
        assert rec["error_subtype"] == "ran_findings"
        assert rec["is_error"] is False
        assert len(rec["findings_rows"]) == 1

    def test_garbage_output_is_track_output_invalid(self, tmp_path, monkeypatch):
        rec = self._run(tmp_path, monkeypatch, "echo 'not json at all'")
        assert rec["error_subtype"] == "track_output_invalid"
        assert rec["is_error"] is True
        assert rec["findings_rows"] == []
        assert "ZERO findings" in rec["detail"]

    def test_an_accusatory_row_invalidates_the_whole_output(self, tmp_path, monkeypatch):
        smuggle = {**VALID_OUTPUT,
                   "findings_rows": [{**VALID_ROW, "severity": "impossible"}]}
        rec = self._run(tmp_path, monkeypatch,
                        f"echo '{json.dumps(smuggle)}'")
        assert rec["error_subtype"] == "track_output_invalid"
        assert rec["findings_rows"] == []

    def test_a_crashing_child_is_track_crashed(self, tmp_path, monkeypatch):
        rec = self._run(tmp_path, monkeypatch,
                        "echo 'segfault-ish' >&2; exit 139")
        assert rec["error_subtype"] == "track_crashed"
        assert rec["is_error"] is True
        assert "segfault-ish" in rec["detail"]
        assert rec["findings_rows"] == []

    def test_a_hung_child_is_killed_and_recorded_as_timeout(self, tmp_path, monkeypatch):
        rec = self._run(tmp_path, monkeypatch, "sleep 30", timeout_s=0.5)
        assert rec["error_subtype"] == "track_timeout"
        assert rec["is_error"] is True
        assert rec["wall_seconds"] < 10
        assert "UNEXAMINED" in rec["detail"]

    def test_a_missing_interpreter_is_contained_not_raised(self, tmp_path, monkeypatch):
        import asyncio
        monkeypatch.setenv("METASCIENCE_IMAGE_PYTHON",
                           str(tmp_path / "does-not-exist"))
        rec = asyncio.run(_run_image_track(tmp_path, timeout_s=5.0))
        assert rec["error_subtype"] == "track_crashed"
        assert rec["is_error"] is True

    def test_a_refusing_child_is_not_an_error(self, tmp_path, monkeypatch):
        refusal = {"schema_version": "1.0", "paper_id": "p",
                   "status": {"ran": False, "refusal_subtype": "engine_missing",
                              "wall_seconds": 0.0,
                              "detail": "PyMuPDF is absent"},
                   "result": {}, "findings_rows": []}
        rec = self._run(tmp_path, monkeypatch,
                        f"echo '{json.dumps(refusal)}'")
        assert rec["ran"] is False
        assert rec["error_subtype"] == "engine_missing"
        assert rec["is_error"] is False


# ---------------------------------------------------------------------------
# The child: refusal subtypes are distinct facts
# ---------------------------------------------------------------------------


class TestChildRefusals:
    def test_no_pdf_directory(self, tmp_path):
        out = IT.run_track(tmp_path)
        assert out["status"]["ran"] is False
        assert out["status"]["refusal_subtype"] == "no_pdf"
        assert out["findings_rows"] == []

    def test_the_status_file_probes_the_model_the_run_was_given(
            self, tmp_path, monkeypatch):
        """`engine_status` used to probe only the environment variable, so a
        learned sweep (model passed by --panel-detector-onnx) wrote
        "no model configured" into every status file (2026-10-01)."""
        from metascience_observatory_image_analysis.image_forensics import panel_detector as PD
        monkeypatch.delenv(PD.ENV_VAR, raising=False)
        model = tmp_path / "panel_detector.onnx"
        model.write_bytes(b"x")
        paper = tmp_path / "10.1--nopdf"
        paper.mkdir()
        st = IT.run_track(paper, panel_detector_onnx=str(model))["status"]
        assert st["refusal_subtype"] == "no_pdf"
        row = next(e for e in st["engine_status"]["engines"]
                   if e["engine"] == "panel_detector")
        assert row["weights_path"] == str(model)
        assert "no panel-detector model configured" not in row["reason"]

    def test_engine_missing(self, tmp_path, monkeypatch):
        from metascience_observatory_image_analysis.image_forensics import panels
        monkeypatch.setattr(panels, "panel_engine_status",
                            lambda *a, **k: {"available": False,
                                     "transformed_tier_available": False,
                                     "engines": []})
        out = IT.run_track(tmp_path)
        assert out["status"]["refusal_subtype"] == "engine_missing"
        assert "installation" in out["status"]["detail"]

    def test_unreadable_pdf(self, tmp_path, monkeypatch):
        (tmp_path / f"{tmp_path.name}.pdf").write_bytes(b"not a pdf")
        _stub_detector(monkeypatch, {
            "success": False, "unreadable": True,
            "error": "cannot read x.pdf: panels are UNKNOWN, not absent",
            "n_panels": 0, "panels": []})
        out = IT.run_track(tmp_path)
        assert out["status"]["refusal_subtype"] == "pdf_unreadable"
        assert out["findings_rows"] == []

    def test_no_rasters_is_coverage_absence_not_cleanliness(self, tmp_path, monkeypatch):
        (tmp_path / f"{tmp_path.name}.pdf").write_bytes(b"%PDF-1.4 stub")
        _stub_detector(monkeypatch, {
            "success": True, "n_panels": 0, "n_eligible": 0,
            "n_duplicate_groups": 0, "panels": []})
        out = IT.run_track(tmp_path)
        assert out["status"]["refusal_subtype"] == "no_rasters"
        assert "nothing is cleared" in out["status"]["detail"]

    def test_ran_with_groups_builds_quarantined_rows(self, tmp_path, monkeypatch):
        (tmp_path / f"{tmp_path.name}.pdf").write_bytes(b"%PDF-1.4 stub")
        _stub_detector(monkeypatch, {
            "success": True, "n_panels": 5, "n_eligible": 4,
            "n_duplicate_groups": 1,
            "severity": "indeterminate",
            "severity_before_quarantine": "suspicious",
            "quarantined": True,
            "quarantine_reason": "unvalidated on ground truth",
            # The REAL group shape (pinned against the detector's records):
            # `panels` is uid STRINGS, `placements` a dict keyed by uid
            # (tiers 2-4; tier 1 uses the one panel's list), labels come
            # from `figure_labels`. The first CLI run crashed on a stub
            # shaped like the old dict-of-panels guess -- hence this pin.
            "duplicate_groups": [{
                "kind": "identical_stream",
                "tier": 2,
                "sentence": "two panels share identical stream bytes",
                "severity_before_quarantine": "suspicious",
                "panels": ["x.pdf:xref5", "x.pdf:xref9"],
                "figure_labels": ["Figure 1", "Figure 3"],
                "placements": {
                    "x.pdf:xref5": [{"page": 2, "figure_label": "Figure 1"}],
                    "x.pdf:xref9": [{"page": 4, "figure_label": "Figure 3"}],
                }}],
            "tiers_run": ["same_xref_reused", "identical_stream"],
            "tiers_not_run": []})
        out = IT.run_track(tmp_path)
        assert out["status"]["ran"] is True
        assert out["status"]["refusal_subtype"] is None
        rows = out["findings_rows"]
        assert len(rows) == 1
        row = rows[0]
        assert row["technique"] == "image_duplication"
        assert row["severity"] == "indeterminate"
        assert row["severity_before_quarantine"] == "suspicious"
        assert "QUARANTINED" in row["explanation"]
        assert "never" in row["explanation"] and "headline" in row["explanation"]
        assert "Figure 1" in row["location"] and "Figure 3" in row["location"]
        assert row["reproduction"].startswith("metascience image-analysis")
        # The parent-side validator must accept exactly what the child emits.
        _validate_image_track_output(out)

    def test_row_budget_overflow_is_announced_never_silent(self, tmp_path, monkeypatch):
        (tmp_path / f"{tmp_path.name}.pdf").write_bytes(b"%PDF-1.4 stub")
        groups = [{"kind": "identical_stream",
                   "sentence": f"group {i}",
                   "severity_before_quarantine": "suspicious",
                   "panels": []} for i in range(15)]
        _stub_detector(monkeypatch, {
            "success": True, "n_panels": 40, "n_eligible": 40,
            "n_duplicate_groups": 15, "duplicate_groups": groups,
            "quarantine_reason": "unvalidated"})
        out = IT.run_track(tmp_path)
        rows = out["findings_rows"]
        assert len(rows) == IT._MAX_FINDINGS_ROWS
        assert "further duplicate" in rows[-1]["explanation"]


class TestFindPdfs:
    def test_prefers_the_pdf_named_after_the_directory(self, tmp_path):
        (tmp_path / "supplement_big.pdf").write_bytes(b"x" * 5000)
        (tmp_path / f"{tmp_path.name}.pdf").write_bytes(b"x" * 10)
        main, si, _ = IT._find_pdfs(tmp_path)
        assert main.name == f"{tmp_path.name}.pdf"
        assert [p.name for p in si] == ["supplement_big.pdf"]

    def test_falls_back_to_the_largest(self, tmp_path):
        (tmp_path / "a.pdf").write_bytes(b"x" * 5000)
        (tmp_path / "b.pdf").write_bytes(b"x" * 10)
        main, si, _ = IT._find_pdfs(tmp_path)
        assert main.name == "a.pdf"

    def test_empty_directory(self, tmp_path):
        assert IT._find_pdfs(tmp_path) == (None, [], False)


class TestADuplicateDeliveryIsNotASupplement:
    """MEASURED on the cerebrolysin corpus: two paper directories hold a
    Dropbox "(Case Conflict)" copy of the article beside the article, same
    bytes, differing only in filename case. Swept as SI, the detector
    compares the paper against ITSELF -- every figure byte-identical to a
    figure -- and those two papers alone produced 29 of the corpus's 40
    `identical_stream` groups. The screen is on CONTENT, so any
    duplicate-delivery naming is caught, not just Dropbox's.
    """

    def _pdf(self, path, text="Figure 1."):
        import fitz
        doc = fitz.open()
        doc.new_page(width=595, height=842).insert_text((60, 80), text)
        doc.save(path)

    def test_a_byte_identical_copy_is_not_swept_as_si(self, tmp_path):
        import shutil
        from metascience_observatory_image_analysis.image_forensics.image_track import _find_pdfs
        paper = tmp_path / "10.1--x"
        paper.mkdir()
        self._pdf(paper / "10.1--x.pdf")
        shutil.copyfile(paper / "10.1--x.pdf",
                        paper / "10.1--X (Case Conflict).pdf")
        main, si, _ = _find_pdfs(paper)
        assert main == paper / "10.1--x.pdf"
        assert si == []

    def test_a_genuine_supplement_still_arrives(self, tmp_path):
        """The screen must drop copies and nothing else."""
        from metascience_observatory_image_analysis.image_forensics.image_track import _find_pdfs
        paper = tmp_path / "10.1--y"
        paper.mkdir()
        self._pdf(paper / "10.1--y.pdf")
        self._pdf(paper / "10.1--y_supplementary_info_1_mmc1.pdf",
                  text="Supplementary Figure S1.")
        main, si, _ = _find_pdfs(paper)
        assert [p.name for p in si] == ["10.1--y_supplementary_info_1_mmc1.pdf"]

    def test_two_unreadable_files_are_not_declared_the_same_document(
            self, tmp_path):
        """`None` is "could not hash", not a hash. Two files nobody could
        open are two unknowns, and dropping one would remove a document from
        the sweep on the strength of a failure to read it."""
        from metascience_observatory_image_analysis.image_forensics import image_track as IT
        paper = tmp_path / "10.1--z"
        paper.mkdir()
        self._pdf(paper / "10.1--z.pdf")
        (paper / "a.pdf").write_bytes(b"%PDF-1.4 a")
        (paper / "b.pdf").write_bytes(b"%PDF-1.4 b")
        real = IT._file_sha256
        IT._file_sha256 = lambda p: None if p.name in {"a.pdf", "b.pdf"} \
            else real(p)
        try:
            _, si, _ = IT._find_pdfs(paper)
        finally:
            IT._file_sha256 = real
        assert {p.name for p in si} == {"a.pdf", "b.pdf"}


class TestTheAdjudicatorGetsACaption:
    """`write_figures_json` was only ever called from the CLI, so a track run
    left no `figures/figures.json`.

    MEASURED 2026-08-18: 0 of 909 Masliah papers carried one, so EVERY
    adjudication verdict on that corpus was reached without a single figure
    caption -- while the catalogue needs one to reach
    `stated_representative_image`, `overview_and_detail` and most of the other
    innocuous readings. Generating them for the 82 papers under review took 33
    seconds and moved 12 whole papers out of the queue.
    """

    def _pdf(self, path, caption="Figure 1. Confocal images of cortex."):
        import fitz
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text((60, 700), caption, fontsize=10)
        doc.save(path)

    def test_a_track_run_leaves_captions_behind(self, tmp_path):
        from metascience_observatory_image_analysis.image_forensics.image_track import _write_figure_captions
        paper = tmp_path / "10.1--x"
        paper.mkdir()
        pdf = paper / "10.1--x.pdf"
        self._pdf(pdf)
        _write_figure_captions(paper, pdf)
        assert (paper / "figures" / "figures.json").exists()

    def test_an_existing_file_is_not_rewritten(self, tmp_path):
        """Re-running a sweep must not spend the extraction again, and must
        not clobber captions a CLI run produced."""
        from metascience_observatory_image_analysis.image_forensics.image_track import _write_figure_captions
        paper = tmp_path / "10.1--y"
        (paper / "figures").mkdir(parents=True)
        marker = paper / "figures" / "figures.json"
        marker.write_text('{"figures": [{"label": "Figure 1"}]}')
        pdf = paper / "10.1--y.pdf"
        self._pdf(pdf)
        _write_figure_captions(paper, pdf)
        assert "Figure 1" in marker.read_text()

    def test_an_unreadable_pdf_never_breaks_the_run(self, tmp_path):
        """A caption is CONTEXT. A paper whose figures cannot be located must
        still be adjudicable from the images and the measurements, and the
        prompt builder already names the gap for the model."""
        from metascience_observatory_image_analysis.image_forensics.image_track import _write_figure_captions
        paper = tmp_path / "10.1--z"
        paper.mkdir()
        bad = paper / "10.1--z.pdf"
        bad.write_bytes(b"not a pdf at all")
        _write_figure_captions(paper, bad)          # must not raise
        assert not (paper / "figures" / "figures.json").exists()


class TestWhichDocumentAPanelCameFrom:
    """`doc_role` is the reviewer's first question on a cross-figure match:
    one panel in the paper and one in the SI can be entirely proper, and the
    same pair inside one figure is not.

    It used to be unrecorded, so every consumer guessed from the filename --
    a substring match on "supplement" that is wrong for any publisher naming
    its files differently, and wrong silently.
    """

    def test_the_fallback_pick_is_unknown_not_main(self, tmp_path):
        """MEASURED on `10.1001--jamaneurol.2023.2560`: the paper ships its
        main text as XML and only its three supplements as PDFs, so the
        largest SUPPLEMENT became the fallback "main" and all 33 of its
        panels -- every one carrying an `eFigure` label -- were stamped
        main-document. A reviewer would have read the opposite of the truth.
        """
        from metascience_observatory_image_analysis.image_forensics.image_track import _find_pdfs
        d = tmp_path / "10.1001--x.1"
        d.mkdir()
        (d / "10.1001--x.1_supplementary_info_1.pdf").write_bytes(b"%PDF-1.4\n" + b"a" * 500)
        (d / "10.1001--x.1_supplementary_info_2.pdf").write_bytes(b"%PDF-1.4\n" + b"b" * 100)
        main, si, identified = _find_pdfs(d)
        assert main is not None
        assert identified is False, "a size-heuristic pick must not claim to be identified"
        assert len(si) == 1

    def test_the_directory_named_pdf_is_positively_identified(self, tmp_path):
        from metascience_observatory_image_analysis.image_forensics.image_track import _find_pdfs
        d = tmp_path / "10.1001--x.1"
        d.mkdir()
        (d / "10.1001--x.1.pdf").write_bytes(b"%PDF-1.4\n" + b"a" * 100)
        (d / "10.1001--x.1_supplementary_info_1.pdf").write_bytes(b"%PDF-1.4\n" + b"b" * 500)
        main, si, identified = _find_pdfs(d)
        assert identified is True
        assert main.name == "10.1001--x.1.pdf"
        assert [p.name for p in si] == ["10.1001--x.1_supplementary_info_1.pdf"]

    def test_no_pdfs_reports_not_identified(self, tmp_path):
        from metascience_observatory_image_analysis.image_forensics.image_track import _find_pdfs
        d = tmp_path / "10.1001--x.1"
        d.mkdir()
        assert _find_pdfs(d) == (None, [], False)


class TestHarvestedIsNotEligible:
    """A paper where every panel was WITHHELD reported as a clean run.

    `run_track` branched on `n_panels` -- what came out of the PDF -- and not on
    `n_eligible`, what survived the screens and was actually compared. So a scan
    sliced into 132 horizontal strips, every strip withheld as `tile_member`,
    returned `ran: True` with "0 duplicate group(s) across 132 harvested
    panel(s)". The detector compared NOTHING and it read as examined and clean.

    MEASURED on the last masliah sweep: 44 of the 486 papers that "ran" had
    `n_eligible == 0`. That is the same absence-conflation the module docstrings
    exist to prevent -- our inability to look, published as a fact about the
    paper.
    """

    @staticmethod
    def _track(monkeypatch, tmp_path, result):
        """Drive `run_track` with a canned `analyze_paper_images` result."""
        paper = tmp_path / "10.1--x"
        paper.mkdir(parents=True, exist_ok=True)
        (paper / "10.1--x.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
        # Patched on the SOURCE module: `run_track` imports it inside the
        # function body, so an attribute on `image_track` is never consulted.
        from metascience_observatory_image_analysis.image_forensics import image_analysis as IA
        monkeypatch.setattr(IA, "analyze_paper_images",
                            lambda *a, **k: dict(result))
        monkeypatch.setattr(IT, "_readable_body_chars",
                            lambda pdf: (4200, ""))
        monkeypatch.setattr(IT, "_write_figure_captions", lambda *a, **k: "")
        return IT.run_track(paper)["status"]

    def test_a_tiled_scan_is_a_named_refusal_not_a_clean_run(
            self, monkeypatch, tmp_path):
        st = self._track(monkeypatch, tmp_path, {
            "success": True, "n_panels": 132, "n_eligible": 0,
            "n_skipped": {"tile_member": 132}, "duplicate_groups": [],
            "n_duplicate_groups": 0, "severity": "consistent"})
        assert st["ran"] is False, "nothing was compared, so nothing ran"
        assert st["refusal_subtype"] == "scanned_pages"
        assert "132" in st["detail"] and "tile_member" in st["detail"]

    def test_a_stencil_scan_is_also_scanned_pages(self, monkeypatch, tmp_path):
        st = self._track(monkeypatch, tmp_path, {
            "success": True, "n_panels": 9, "n_eligible": 0,
            "n_skipped": {"stencil": 9}, "duplicate_groups": [],
            "n_duplicate_groups": 0, "severity": "consistent"})
        assert st["refusal_subtype"] == "scanned_pages"

    def test_an_ocrd_scan_is_still_a_scan(self, monkeypatch, tmp_path):
        """The first cut required NO readable body text and so never fired: the
        scans in this corpus are OCR'd and carry thousands of characters a page.
        Scan-shaped is a fact about the rasters, not about the text layer."""
        st = self._track(monkeypatch, tmp_path, {
            "success": True, "n_panels": 132, "n_eligible": 0,
            "n_skipped": {"tile_member": 132}, "duplicate_groups": [],
            "n_duplicate_groups": 0, "severity": "consistent"})
        assert st["refusal_subtype"] == "scanned_pages"
        assert st["readable_body_chars"] == 4200
        assert "OCR" in st["detail"]

    def test_a_scanned_page_count_is_scanned_pages(self, monkeypatch, tmp_path):
        """A one-page scanned abstract: one page image and one tiny mark. A
        tie with another reason is still a scan."""
        st = self._track(monkeypatch, tmp_path, {
            "success": True, "n_panels": 2, "n_eligible": 0,
            "n_skipped": {"scanned_page": 1, "tiny": 1}, "duplicate_groups": [],
            "n_duplicate_groups": 0, "severity": "consistent"})
        assert st["refusal_subtype"] == "scanned_pages"
        assert "one picture covering each page" in st["detail"]

    def test_every_page_one_full_sheet_raster_is_scanned_pages_end_to_end(
            self, monkeypatch, tmp_path):
        """THE INVARIANT, through the real harvest and detector: a document
        whose every page's only raster covers >= 90% of the sheet is a scan.
        MEASURED 2026-10-01: 10 masliah_subset scans were refused
        `all_panels_withheld` as "6 page_furniture" -- a paper of publisher
        adverts -- because the full-page furniture rule had lost its page
        count."""
        fitz = pytest.importorskip("fitz")
        import numpy as np
        paper = tmp_path / "10.1--scan"
        paper.mkdir()
        doc = fitz.open()
        for i in range(3):
            arr = np.kron(np.random.default_rng(90 + i).integers(
                0, 256, (66, 51), dtype=np.uint8), np.ones((4, 4), np.uint8))
            png = fitz.Pixmap(fitz.csGRAY, arr.shape[1], arr.shape[0],
                              arr.tobytes(), 0).tobytes("png")
            page = doc.new_page(width=612, height=792)
            # The measured shape: placed 0.24 pt off the sheet.
            page.insert_image(fitz.Rect(0, -0.24, 612, 791.76), stream=png,
                              keep_proportion=False)
        doc.save(paper / "10.1--scan.pdf")
        monkeypatch.setattr(IT, "_readable_body_chars", lambda pdf: (4200, ""))
        monkeypatch.setattr(IT, "_write_figure_captions", lambda *a, **k: "")
        st = IT.run_track(paper)["status"]
        assert st["refusal_subtype"] == "scanned_pages", st["detail"]
        # One reason per raster, summing to the rasters harvested.
        assert "(3 scanned_page)" in st["detail"], st["detail"]
        assert "never_displayed" not in st["detail"]

    def test_a_withheld_panel_is_counted_once_not_once_per_instrument(
            self, monkeypatch, tmp_path):
        """`excluded` holds a record for every panel `n_skipped` already
        counted; adding both printed "11 raster(s) ... (22 page_furniture,
        11 never_displayed)" -- 33 reasons for 11 rasters (2026-10-01)."""
        excluded = [{"panel": f"p.pdf:xref{i}", "scope": "all_tiers",
                     "reason": "page_furniture"} for i in range(11)]
        excluded += [{"panel": "p.pdf:xref99", "scope": "all_tiers",
                      "reason": "corpus_furniture"},
                     {"panel": "p.pdf:xref99", "scope": "perceptual_tiers",
                      "reason": "low_texture"}]
        st = self._track(monkeypatch, tmp_path, {
            "success": True, "n_panels": 12, "n_eligible": 0,
            "n_skipped": {"page_furniture": 11, "never_displayed": 0,
                          "inline_image": 2},
            "excluded": excluded, "duplicate_groups": [],
            "n_duplicate_groups": 0, "severity": "consistent"})
        assert st["refusal_subtype"] == "all_panels_withheld"
        assert ("(11 page_furniture, 2 inline_image, 1 corpus_furniture)"
                in st["detail"]), st["detail"]

    def test_all_furniture_is_a_different_refusal_than_a_scan(
            self, monkeypatch, tmp_path):
        """Publisher furniture and a scan both present as zero eligible panels.
        They are different facts and must not share a name."""
        st = self._track(monkeypatch, tmp_path, {
            "success": True, "n_panels": 11, "n_eligible": 0,
            "n_skipped": {"page_furniture": 11}, "duplicate_groups": [],
            "n_duplicate_groups": 0, "severity": "consistent"})
        assert st["refusal_subtype"] == "all_panels_withheld"
        assert "page_furniture" in st["detail"]

    def test_a_paper_with_eligible_panels_still_runs(self, monkeypatch, tmp_path):
        """The guard must not swallow the ordinary case."""
        st = self._track(monkeypatch, tmp_path, {
            "success": True, "n_panels": 11, "n_eligible": 11,
            "n_skipped": {}, "duplicate_groups": [], "n_duplicate_groups": 0,
            "severity": "consistent"})
        assert st["ran"] is True
        assert st["refusal_subtype"] is None

    def test_every_new_subtype_is_in_the_schema_enum(self):
        """An unlisted value is a hard schema rejection, not a soft one."""
        import json as _json
        from metascience_observatory_image_analysis import prompts
        schema = _json.loads(
            (Path(prompts.__file__).parent / "schema"
             / "image_track.schema.json").read_text(encoding="utf-8"))
        enum = (schema["properties"]["status"]["properties"]
                ["refusal_subtype"]["enum"])
        assert "scanned_pages" in enum and "all_panels_withheld" in enum
