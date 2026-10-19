"""The `reassemble_tiles` flag reaches the answer, the stamp, and the child.

Modelled on `test_copy_move_wiring.py`: the `rendered_regions` flag was once
accepted by `run_track` and silently dropped, so every opt-in flag is pinned
end to end -- signature, argv, stamp -- not only in the module that uses it.
"""
from __future__ import annotations

import inspect

import pytest

from metascience_observatory_image_analysis.image_forensics import image_analysis as IA
from metascience_observatory_image_analysis.image_forensics import image_track as IT
from metascience_observatory_image_analysis.image_forensics import panels as P
from metascience_observatory_image_analysis.image_forensics import pipeline as PIPE
from metascience_observatory_image_analysis.image_forensics import retain as R
from metascience_observatory_image_analysis.image_forensics import sweep as S

_BASE = {"segment_montages": True, "include_supplements": False,
         "rendered_regions": False, "max_panels": 200, "emit_v2": True,
         "copy_move": False, "panel_detector": "gutter",
         "panel_detector_weights_sha256": "", "keypoint_mode": "plain", "low_texture_keypoints": False, "hires_pixels": False, "adjacent_caption_labels": False, "stencil_art": False}


class TestTheStampAndTheChildCarryTheFlag:
    def test_it_is_a_stamp_flag_and_the_harvest_is_fingerprinted(self):
        assert "reassemble_tiles" in R.STAMP_FLAGS
        assert "panels.py" in R.FINGERPRINT_FILES

    def test_the_stamp_differs_with_the_flag(self):
        on = R.make_stamp("s", {**_BASE, "reassemble_tiles": True})
        off = R.make_stamp("s", {**_BASE, "reassemble_tiles": False})
        assert on["flags"]["reassemble_tiles"] is True
        assert off["flags"]["reassemble_tiles"] is False
        assert on["flags"] != off["flags"]

    def test_a_stamp_without_the_flag_is_refused(self):
        with pytest.raises(ValueError, match="reassemble_tiles"):
            R.make_stamp("s", dict(_BASE))

    def test_the_child_argv_carries_it_only_when_on(self):
        on = {**_BASE, "reassemble_tiles": True}
        off = {**_BASE, "reassemble_tiles": False}
        assert "--reassemble-tiles" in S._child_args(on, None, R.make_stamp("s", on), True)
        assert "--reassemble-tiles" not in S._child_args(off, None, R.make_stamp("s", off), True)

    def test_the_sweep_id_names_it(self):
        assert S.default_sweep_id(True, reassemble_tiles=True).endswith("_tiles")
        assert not S.default_sweep_id(True).endswith("_tiles")

    def test_every_entry_point_accepts_it(self):
        for fn in (P.extract_panels, IA.analyze_paper_images, IA._harvest_pdf,
                   IT.run_track, S.run_sweep, PIPE.run_detection, PIPE.run):
            params = inspect.signature(fn).parameters
            assert "reassemble_tiles" in params, fn.__name__
            assert params["reassemble_tiles"].default is False, fn.__name__

    def test_run_track_hands_it_to_the_detector(self, monkeypatch, tmp_path):
        """`run_track(reassemble_tiles=True)` must reach
        `analyze_paper_images(reassemble_tiles=True)` -- the seam where
        `rendered_regions` was once dropped."""
        paper = tmp_path / "10.1000--x"
        paper.mkdir()
        import fitz
        doc = fitz.open()
        doc.new_page()
        doc.save(paper / "10.1000--x.pdf")
        doc.close()
        seen = {}

        def fake(*a, **k):
            seen.update(k)
            return {"success": True, "n_panels": 0, "n_eligible": 0,
                    "n_skipped": {}, "duplicate_groups": [],
                    "n_duplicate_groups": 0, "severity": "consistent",
                    "status": {"engines": []}, "warnings": [],
                    "tile_reassembly": {"mode": "on"}}

        monkeypatch.setattr(IA, "analyze_paper_images", fake)
        monkeypatch.setattr(IT, "_write_figure_captions", lambda *a, **k: "")
        IT.run_track(paper, reassemble_tiles=True)
        assert seen.get("reassemble_tiles") is True

    def test_the_child_parser_knows_the_flag(self):
        import argparse
        src = inspect.getsource(IT.main)
        assert '"--reassemble-tiles"' in src
        assert "reassemble_tiles=args.reassemble_tiles" in src

    def test_the_pipeline_records_the_flag(self):
        src = inspect.getsource(PIPE.run_detection)
        assert '"--reassemble-tiles"' in src
        assert '"reassemble_tiles": bool(reassemble_tiles)' in src


class TestTheHostThreadsIt:
    def test_analyze_paper_and_the_cli_accept_it(self):
        from forensic_metascience_ai_toolkit import agent, parallel
        assert "image_reassemble_tiles" in inspect.signature(agent.analyze_paper).parameters
        assert "image_reassemble_tiles" in inspect.signature(parallel.analyze_paper_parallel).parameters
        src = inspect.getsource(parallel)
        assert "reassemble_tiles=image_reassemble_tiles" in src
        from forensic_metascience_ai_toolkit import cli
        assert "image_reassemble_tiles=reassemble_tiles" in inspect.getsource(cli)
