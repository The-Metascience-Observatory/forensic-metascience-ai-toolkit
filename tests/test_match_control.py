"""The unaligned control for a duplication match (`match_control`).

Every fixture here is TEXTURED (see `tests/image_fixtures.py`): on a flat
panel no correlation can pass, and a suite that only ever fed the gate flat
panels would stay green while the measurement was broken.

The gate is `agree_share >= 0.20 AND lift_in_blob >= 0.25`: the largest
CONNECTED agreeing region as a share of the overlap, and the aligned-minus-
unaligned r measured INSIDE that region. Three other designs were measured
and rejected on 2026-09-08 -- whole-overlap correlation (dilutes a real
duplication inside a row strip to r 0.09), a connected-region share with no
lift (passes a shared grid over two different fields at share 0.95, lift
0.00), and an inlier-box region (`inlier_box_b` is in panel B's FLIPPED frame
on a mirrored match, so it measures the wrong pixels there). The first two
live in this file as tests, so that neither can come back without the number
that ruled it out. `agree_frac`, `region` and `control_region` are still
reported and still tested; they are not the gate.
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("cv2")
pytest.importorskip("scipy")

from metascience_observatory_image_analysis.image_forensics import match_control as MC  # noqa: E402
from metascience_observatory_image_analysis.image_forensics import retain as R  # noqa: E402
from tests.image_fixtures import (  # noqa: E402
    independent_pair, noise_field, shifted_crop_pair, template_pair,
)


class TestTheThreeShapes:
    def test_one_field_cropped_twice_PASSES(self):
        a, b, M = shifted_crop_pair()
        blk = MC.measure_control(a, b, M)
        assert blk["note"] == ""
        assert MC.gate_state(blk) == "passed", blk
        assert blk["lift"] > MC.LIFT_MIN and blk["agree_frac"] > MC.AGREE_FRAC_MIN
        assert blk["overlap_r"] > 0.9 and abs(blk["control_r"]) < 0.3
        assert MC.gate_reason(blk) is None

    def test_two_independent_fields_FAIL(self):
        a, b, M = independent_pair()
        blk = MC.measure_control(a, b, M)
        assert MC.gate_state(blk) == "failed"
        assert abs(blk["lift"]) < MC.LIFT_MIN
        assert blk["agree_frac"] < MC.AGREE_FRAC_MIN

    def test_a_shared_grid_over_two_different_fields_is_a_LOOKALIKE(self):
        """The chart-furniture confound. Aligned r is high on the grid alone
        -- and so is the unaligned r, which is the whole point of measuring
        it. A connected-region share reads this as a 95% duplication."""
        a, b, M = template_pair()
        blk = MC.measure_control(a, b, M)
        assert blk["overlap_r"] > 0.5, blk
        assert blk["control_r"] > 0.5, blk
        assert blk["lift"] < MC.LIFT_MIN
        assert blk["agree_share"] > 0.5      # what a share-only gate would see
        assert blk["lift_in_blob"] < MC.LIFT_MIN   # what the shipped gate sees
        assert MC.gate_state(blk) == "failed"
        assert "unaligned" in MC.gate_reason(blk) or "coherent" in MC.gate_reason(blk)


class TestTheReportedRegion:
    def test_a_band_inside_a_much_larger_source_is_measured_where_it_matched(self):
        """The `10.3390--ijms13078514` shape: the source segment is a whole
        montage row, the target one sub-panel. Over the whole overlap the
        REPORTED correlations are diluted; inside the inlier box they are the
        whole story. (The gate itself reads the connected blob, which does
        not depend on the box -- see the module docstring.)"""
        a, b, M = shifted_crop_pair(seed=5, shift=(30, 70), size=(120, 150))
        pad = noise_field((120, 200), seed=77)
        a_wide = np.hstack([pad, a, pad])            # unrelated tissue both sides
        M_wide = [[1.0, 0.0, M[0][2] - 200.0], [0.0, 1.0, M[1][2]]]
        box_b = [0, 0, 150 - 30, 120 - 70]           # roughly the shared band
        boxed = MC.measure_control(a_wide, b, M_wide, inlier_box_b=box_b)
        plain = MC.measure_control(a_wide, b, M_wide)
        assert boxed["region"] == "inlier_box" and plain["region"] == "overlap"
        assert MC.gate_state(boxed) == "passed", boxed
        assert boxed["agree_frac"] >= plain["agree_frac"]

    def test_a_box_too_small_to_measure_falls_back_to_the_overlap_and_says_so(self):
        a, b, M = shifted_crop_pair()
        blk = MC.measure_control(a, b, M, inlier_box_b=[5, 5, 20, 20])
        assert blk["region"] == "overlap" and blk["note"] == ""

    def test_the_control_names_its_region(self):
        a, b, M = shifted_crop_pair()
        assert MC.measure_control(a, b, M)["control_region"] in ("same_position", "common_window")


class TestRefusalsAreNamedNeverZero:
    def test_a_tiny_overlap_is_not_measured_and_not_failed(self):
        blk = MC.measure_control(noise_field((40, 40), 1), noise_field((40, 40), 2),
                                 [[1, 0, 0], [0, 1, 0]])
        assert blk["note"] and blk["lift"] is None and blk["agree_frac"] is None
        assert MC.gate_state(blk) == "not_measured"
        assert MC.gate_reason(blk).startswith("not measured")

    def test_no_affine_is_not_measured(self):
        blk = MC.measure_control(noise_field(), noise_field(), None)
        assert MC.gate_state(blk) == "not_measured" and "affine" in blk["note"]

    def test_a_flat_panel_has_no_correlation_to_report(self):
        flat = np.full((200, 200), 128, np.uint8)
        blk = MC.measure_control(flat, noise_field((200, 200)), [[1, 0, 0], [0, 1, 0]])
        assert MC.gate_state(blk) == "not_measured" and "variance" in blk["note"]

    def test_absent_is_the_same_state_as_unmeasurable(self):
        """LESSONS.md #1: the test that has to exist before any consumer."""
        assert MC.gate_state(None) == "not_measured"
        assert MC.gate_state({}) == "not_measured"
        assert MC.gate_state({"agree_frac": 0.9}) == "not_measured"   # no lift
        assert "control" in MC.gate_reason(None)
        assert MC.control_sentence(None) == ""

    def test_every_block_carries_its_provenance(self):
        a, b, M = shifted_crop_pair()
        for blk in (MC.measure_control(a, b, M), MC.measure_control(a, b, None)):
            assert blk["code_sha"] == MC.code_sha() and blk["measured_at"]
            assert blk["window"] == MC.NCC_WINDOW and blk["ncc_min"] == MC.AGREE_NCC

    def test_stale_reads_a_foreign_sha_and_absence_as_stale(self):
        assert MC.stale(None) and MC.stale({"code_sha": "nope"})
        assert not MC.stale({"code_sha": MC.code_sha()})


class TestTheKernel:
    def test_is_deterministic(self):
        a, b, M = shifted_crop_pair()
        x, y = MC.measure_control(a, b, M), MC.measure_control(a, b, M)
        strip = lambda d: {k: v for k, v in d.items() if k != "measured_at"}
        assert strip(x) == strip(y)

    def test_agrees_with_copy_move_s_kernel_on_a_translated_patch(self):
        """Two copies of one uniform-filter identity: the fingerprinted one in
        `copy_move` and this one. Pinned equal at the same window so they
        cannot drift apart unnoticed."""
        from metascience_observatory_image_analysis.image_forensics import copy_move as CM
        hi = noise_field((160, 200), 9).astype(np.float64)
        dy, dx = 12, 7
        _mask, theirs = CM._match_mask(hi, dy, dx)
        ours = MC._local_ncc(hi[dy:160, dx:200], hi[0:160 - dy, 0:200 - dx],
                             CM._NCC_WINDOW)
        m = 2 * CM._NCC_WINDOW
        assert np.allclose(theirs[dy + m:160 - m, dx + m:200 - m], ours[m:-m, m:-m],
                           atol=1e-6)

    def test_agree_boxes_lie_inside_their_panels(self):
        a, b, M = shifted_crop_pair()
        blk = MC.measure_control(a, b, M)
        assert blk["agree_box_b"] is not None
        x0, y0, x1, y1 = blk["agree_box_b"]
        assert 0 <= x0 < x1 <= b.shape[1] and 0 <= y0 < y1 <= b.shape[0]
        x0, y0, x1, y1 = blk["agree_box_a"]
        assert 0 <= x0 < x1 <= a.shape[1] and 0 <= y0 < y1 <= a.shape[0]


class TestTheSentences:
    def test_the_passing_sentence_names_both_correlations(self):
        a, b, M = shifted_crop_pair()
        s = MC.control_sentence(MC.measure_control(a, b, M))
        assert "UNALIGNED" in s and "lift" in s and "specific" in s

    def test_the_failing_sentence_names_the_failing_number(self):
        a, b, M = template_pair()
        s = MC.control_sentence(MC.measure_control(a, b, M))
        assert "UNALIGNED" in s and ("resemble" in s or "coherent" in s)


class TestItStaysOutsideTheDetectorFingerprint:
    """The whole reason the block carries `code_sha`. Editing a fingerprinted
    file re-stamps every retained paper stale (a ~900-paper re-sweep and a
    paid re-adjudication); this measurement must never do that."""

    def test_neither_this_module_nor_the_renderer_is_fingerprinted(self):
        assert "match_control.py" not in R.FINGERPRINT_FILES
        assert "review_media.py" not in R.FINGERPRINT_FILES

    def test_detector_changes_invalidate_the_fingerprint(self, monkeypatch):
        """Detector edits are now intentional; they must change the stamp.

        Review-only code remains excluded by the preceding test. Comparing the
        whole working tree to HEAD incorrectly forbade deliberate detector fixes.
        """
        before = R.detector_fingerprint()
        read = Path.read_bytes
        def changed(path):
            data = read(path)
            return data + b"\n# detector changed" if path.name == "image_analysis.py" else data
        monkeypatch.setattr(Path, "read_bytes", changed)
        assert R.detector_fingerprint.__wrapped__() != before


class TestAMirroredMatch:
    def test_a_mirrored_match_is_measured_in_the_frame_the_affine_lives_in(self):
        """The detector matched a against fliplr(b_real) and recorded M in
        that frame. Measured with `flip=True` the pair passes; measured as if
        unflipped it reads as a lookalike -- the class triage scores +2 for,
        demoted on our own frame error. (Test contributed by -d5.)"""
        a, b, M = shifted_crop_pair()
        b_real = np.ascontiguousarray(np.fliplr(b))     # the detector saw fliplr(b_real) == b
        ref = MC.measure_control(a, b, M)
        right = MC.measure_control(a, b_real, M, flip=True)
        wrong = MC.measure_control(a, b_real, M, flip=False)
        assert MC.gate_state(right) == "passed" and MC.gate_state(wrong) == "failed"
        assert right["flip"] is True and abs(right["agree_share"] - ref["agree_share"]) < 0.02
        wb = b.shape[1]
        x0, y0, x1, y1 = ref["agree_box_b"]
        assert right["agree_box_b"] == [round(wb - x1, 1), y0, round(wb - x0, 1), y1]
