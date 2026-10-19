"""What gets animated, and why every absence is explained.

An animation is minutes of a reviewer's attention and megabytes on disk, so
the selection has to be defensible: a rotation, a zoom or a flip that survived
the LLM screen. MEASURED on the 909-paper Masliah sweep -- of 877 fired
`transformed_match` groups only 206 involve one of those, and 671 are
near-identity, where the animation shows two pictures sitting still.

The other half of this file is the rule that runs through the whole codebase:
a group with no artifact carries the REASON. A reviewer looking at a blank
pane cannot tell "there was nothing to show" from "we failed to draw it", and
the second is our fault.
"""

from __future__ import annotations

import json

import pytest

from metascience_observatory_image_analysis.image_forensics import review_media as RM


class TestWhichTransformsNeedAnimating:
    def test_a_rotation_qualifies(self):
        assert RM.transform_kind({"rotation_deg": 178.8, "scale": 1.63}) \
            == "rotation"

    def test_a_zoom_qualifies_in_either_direction(self):
        assert RM.transform_kind({"rotation_deg": 0.0, "scale": 1.63}) == "zoom"
        assert RM.transform_kind({"rotation_deg": 0.0, "scale": 0.5}) == "zoom"

    def test_a_FLIP_qualifies_on_its_own(self):
        """A mirrored copy at rotation 0 and scale 1.0 passes any
        rotation-or-scale test as 'nothing happened' -- and a mirror is
        exactly what a person cannot see in two stills and sees at once in
        motion."""
        assert RM.transform_kind(
            {"rotation_deg": 0.0, "scale": 1.0, "flip": True}) == "flip"

    def test_a_near_identity_transform_does_not(self):
        assert RM.transform_kind({"rotation_deg": 0.5, "scale": 1.02}) is None
        assert RM.transform_kind({}) is None


class TestTheThreeGates:
    def _g(self, **kw):
        g = {"kind": "transformed_match", "duplication_evidence": True,
             "match_stats": {"rotation_deg": 90.0, "scale": 1.6}}
        g.update(kw)
        return g

    def test_a_rotated_survivor_is_animated(self):
        want, why = RM.needs_animation(self._g())
        assert want is True and "rotation" in why

    def test_a_group_the_adjudicator_EXPLAINED_is_not(self):
        want, why = RM.needs_animation(self._g(duplication_evidence=False))
        assert want is False
        assert "non-finding" in why

    def test_a_byte_identity_group_is_not(self):
        """`identical_stream` has no recovered transform: nothing moved, so
        there is nothing to animate."""
        want, why = RM.needs_animation(
            self._g(kind="identical_stream", match_stats={}))
        assert want is False
        assert "no recovered transform" in why

    def test_a_near_identity_match_is_not(self):
        want, why = RM.needs_animation(
            self._g(match_stats={"rotation_deg": 0.2, "scale": 1.01}))
        assert want is False
        assert "rotation must exceed 30" in why


class TestEveryAbsenceIsExplained:
    def _result(self, **kw):
        group = {"kind": "transformed_match", "duplication_evidence": True,
                 "panels": ["d:xrefA", "d:xrefB"], "figure_labels": ["Figure 1"],
                 "sentence": "s",
                 "match_stats": {"rotation_deg": 180.0, "scale": 1.6,
                                 "n_inliers": 200}}
        group.update(kw)
        return {"paper_id": "p", "duplicate_groups": [group]}

    def test_a_missing_panel_png_is_NAMED(self, tmp_path):
        man = RM.render_review_media(tmp_path, self._result())
        entry = man["groups"][0]
        assert entry["exhibit_png"] is None
        assert "no PNG on disk" in entry["exhibit_reason"]
        assert "undrawn, not clean" in entry["exhibit_reason"]

    def test_moved_workspace_requires_document_scoped_suffix(self, tmp_path):
        panels = tmp_path / "panels"
        panels.mkdir()
        image = panels / "media_image3.tif.png"
        image.write_bytes(b"pixels")
        (panels / "panel_index.json").write_text(json.dumps({"panels": [{
            "uid": "supplement:media:image3.tif",
            "image_path": "/deleted/private/workspace/media_image3.tif.png",
        }]}))

        assert RM._panel_png(panels, "supplement:media:image3.tif") is None

    def test_a_single_panel_group_says_there_is_no_pair(self, tmp_path):
        man = RM.render_review_media(tmp_path, self._result(panels=["d:x"]))
        assert "no pair to draw" in man["groups"][0]["exhibit_reason"]

    def test_every_fired_group_appears_in_the_manifest(self, tmp_path):
        res = self._result()
        res["duplicate_groups"].append(
            {"kind": "identical_stream", "duplication_evidence": True,
             "panels": ["d:x1", "d:x2"], "match_stats": {}})
        man = RM.render_review_media(tmp_path, res)
        assert man["n_groups"] == 2 and len(man["groups"]) == 2

    def test_an_explained_group_is_not_listed_at_all(self, tmp_path):
        """`duplication_evidence: False` groups are context, already excluded
        from the finding count; drawing them would invite a reviewer to
        re-litigate a decision made for free."""
        res = self._result(duplication_evidence=False)
        assert RM.render_review_media(tmp_path, res)["n_groups"] == 0

    def test_the_manifest_lands_on_disk_for_the_webapp(self, tmp_path):
        RM.render_review_media(tmp_path, self._result())
        path = tmp_path / "panels" / "review" / RM.MANIFEST_NAME
        man = json.loads(path.read_text())
        assert man["groups"][0]["measurements"]["rotation_deg"] == 180.0
        assert "rotation >30 degrees or flip" in man["video_policy"]

    def test_a_bail_states_ONE_cause_in_both_places(self, tmp_path):
        """`video_reason` left as "rotation transform" while the exhibit says
        the PNG is missing tells a reviewer the video was a judgement call,
        when in fact nothing could be drawn at all."""
        man = RM.render_review_media(tmp_path, self._result())
        entry = man["groups"][0]
        assert entry["video_reason"] == entry["exhibit_reason"]

    def test_the_per_paper_cap_says_it_was_the_cap(self, tmp_path):
        """Not silence. A reviewer must know a stronger group took the slot.

        Real pixels, because the cap is only reached by groups that got far
        enough to render -- a fixture with no PNGs would exercise the bail
        path and pass while proving nothing.
        """
        cv2 = pytest.importorskip("cv2")
        import numpy as np
        panels = tmp_path / "panels"
        panels.mkdir(parents=True)
        # Upsampled low-frequency noise, not per-pixel noise: SIFT needs
        # structure at a scale it can key on, and the renderer's own r >= 0.5
        # floor correctly refuses a match built out of grain.
        rng = np.random.default_rng(5)
        small = rng.integers(0, 256, size=(40, 40), dtype=np.uint8)
        base = np.kron(small, np.ones((8, 8), dtype=np.uint8))
        for name, img in (("xrefA", base), ("xrefB", cv2.rotate(
                base, cv2.ROTATE_90_CLOCKWISE))):
            cv2.imwrite(str(panels / f"{name}.png"), img)
            cv2.imwrite(str(panels / f"{name}2.png"), img)
        res = self._result(match_stats={"rotation_deg": 90.0, "scale": 1.0, "n_inliers": 200})
        res["duplicate_groups"].append({
            "kind": "transformed_match", "duplication_evidence": True,
            "panels": ["d:xrefA2", "d:xrefB2"], "figure_labels": [],
            "sentence": "s",
            "match_stats": {"rotation_deg": 90.0, "scale": 1.0,
                            "n_inliers": 50}})
        man = RM.render_review_media(tmp_path, res, render_videos=True,
                                     max_videos=1)
        reasons = [g.get("video_reason") or "" for g in man["groups"]]
        assert any("cap of 1" in r and "ranked" in r for r in reasons), reasons


class TestTheManifestTravels:
    """A manifest is an artifact that moves -- to another machine, into a
    bundle, onto a Dropbox mount with a different root. The operator's home
    directory is not evidence about the paper, and the workbench's
    `/api/media` refuses an absolute path by design, so an absolute string
    becomes a 404 with no explanation."""

    def _paper_with_pixels(self, tmp_path):
        cv2 = pytest.importorskip("cv2")
        import numpy as np
        panels = tmp_path / "panels"
        panels.mkdir(parents=True)
        rng = np.random.default_rng(9)
        small = rng.integers(0, 256, size=(40, 40), dtype=np.uint8)
        base = np.kron(small, np.ones((8, 8), dtype=np.uint8))
        cv2.imwrite(str(panels / "xrefA.png"), base)
        cv2.imwrite(str(panels / "xrefB.png"), cv2.rotate(
            base, cv2.ROTATE_180))
        (tmp_path / "paper.pdf").write_bytes(b"%PDF-1.4")
        return {"paper_id": "p", "duplicate_groups": [{
            "kind": "transformed_match", "duplication_evidence": True,
            "panels": ["d:xrefA", "d:xrefB"], "figure_labels": ["Figure 4"],
            "sentence": "s",
            "placements": {"d:xrefA": [{"page": 7, "figure_label": "Figure 4"}],
                           "d:xrefB": [{"page": 7, "figure_label": "Figure 4"}]},
            "match_stats": {"rotation_deg": 180.0, "scale": 1.0,
                            "n_inliers": 200}}]}

    def test_artifact_paths_are_relative_to_the_paper(self, tmp_path):
        man = RM.render_review_media(tmp_path, self._paper_with_pixels(tmp_path))
        png = man["groups"][0]["exhibit_png"]
        assert png and not png.startswith("/")
        assert png.startswith("panels/review/")
        assert (tmp_path / png).exists(), "the relative path must resolve"

    def test_it_says_what_the_paths_are_relative_to(self, tmp_path):
        man = RM.render_review_media(tmp_path, self._paper_with_pixels(tmp_path))
        assert man["paths_are"] == "relative to paper_dir"

    def test_a_panel_carries_the_PDF_PAGE_it_was_printed_on(self, tmp_path):
        """A crop with no page is a picture with no claim attached: the
        caption is what a duplication contradicts, so a reviewer needs the
        page open beside the crop."""
        man = RM.render_review_media(tmp_path, self._paper_with_pixels(tmp_path))
        entry = man["groups"][0]
        assert entry["placements"]["d:xrefA"] == [
            {"page": 7, "figure_label": "Figure 4"}]
        assert man["pdfs"] == ["paper.pdf"]

    def test_a_group_with_no_placement_says_so_rather_than_inventing_one(
            self, tmp_path):
        res = self._paper_with_pixels(tmp_path)
        res["duplicate_groups"][0]["placements"] = {}
        man = RM.render_review_media(tmp_path, res)
        assert man["groups"][0]["placements"] == {"d:xrefA": [], "d:xrefB": []}


class TestThePaperAndWeUseDifferentCoordinates:
    """A caption says "(F, left)"; the prompt says "xref117-seg8".

    MEASURED on `10.1016--j.neuron.2010.10.020`: the adjudicator HAD the
    sentence "Higher-magnification images from 13-month-old mice ... are shown
    (F, left)", quoted it, and still returned `unexplained` -- because nothing
    in the bundle let it decide whether seg8 was panel F. That was a correct
    refusal on missing information, not a reasoning failure, and no amount of
    prompt wording could have fixed it.
    """

    def _index(self, tmp_path, boxes):
        panels = tmp_path / "panels"
        panels.mkdir(parents=True, exist_ok=True)
        (panels / "panel_index.json").write_text(json.dumps({
            "paper_id": "p",
            "panels": [{"panel_id": pid, "parent_panel_id": "xref9",
                        "crop_box": box, "image_path": ""}
                       for pid, box in boxes.items()],
        }))
        return panels

    def test_a_crop_knows_where_it_sits(self, tmp_path):
        panels = self._index(tmp_path, {
            "xref9-seg1": [0, 0, 50, 50],       # top-left of a 2x2
            "xref9-seg2": [0, 50, 50, 100],     # top-right
            "xref9-seg3": [50, 0, 100, 50],     # bottom-left
            "xref9-seg4": [50, 50, 100, 100],   # bottom-right
        })
        where = lambda p: RM.panel_position(panels, f"d:{p}")["where_in_figure"]
        assert where("xref9-seg1") == "top-left"
        assert where("xref9-seg2") == "top-right"
        assert where("xref9-seg3") == "bottom-left"
        assert where("xref9-seg4") == "bottom-right"

    def test_it_counts_the_figure_s_sub_panels(self, tmp_path):
        panels = self._index(tmp_path, {
            "xref9-seg1": [0, 0, 50, 100], "xref9-seg2": [50, 0, 100, 100]})
        assert RM.panel_position(panels, "d:xref9-seg1")["n_sub_panels"] == 2

    def test_a_whole_stream_panel_has_no_position(self, tmp_path):
        """It sits inside nothing, and inventing a position would be a claim."""
        panels = self._index(tmp_path, {"xref9-seg1": [0, 0, 50, 50]})
        assert RM.panel_position(panels, "d:xref9") is None

    def test_a_missing_index_returns_None_rather_than_guessing(self, tmp_path):
        assert RM.panel_position(tmp_path / "panels", "d:xref9-seg1") is None


# ---------------------------------------------------------------------------
# The unaligned control in the manifest (2026-09-08)
# ---------------------------------------------------------------------------

def _textured_pair(tmp_path, kind="dup"):
    """Two panel PNGs on disk plus the affine the detector would have
    recorded. `dup`: one field cropped twice. `lookalike`: two different
    fields under one grid."""
    from tests.image_fixtures import save_png, shifted_crop_pair, template_pair
    a, b, M = shifted_crop_pair() if kind == "dup" else template_pair()
    save_png(tmp_path / "panels" / "xrefA.png", a)
    save_png(tmp_path / "panels" / "xrefB.png", b)
    return a, b, M


def _control_result(M, **stats):
    st = {"rotation_deg": 0.0, "scale": 1.0, "n_inliers": 120, "inlier_ratio": 0.8,
          "affine": M, "inlier_box_a": [10, 10, 150, 100],
          "inlier_box_b": [10, 10, 150, 100], **stats}
    return {"paper_id": "p", "duplicate_groups": [
        {"kind": "transformed_match", "duplication_evidence": True,
         "panels": ["d:xrefA", "d:xrefB"], "figure_labels": ["Figure 1"],
         "sentence": "s", "match_stats": st}]}


class TestTheControlInTheManifest:
    def test_a_duplication_is_measured_boxed_and_says_passed(self, tmp_path):
        pytest.importorskip("cv2"); pytest.importorskip("scipy")
        _a, _b, M = _textured_pair(tmp_path, "dup")
        man = RM.render_review_media(tmp_path, _control_result(M))
        e = man["groups"][0]
        blk = e["measurements"]["control"]
        assert blk["note"] == "" and blk["lift"] > 0.25
        assert e["exhibit_gate"] == "passed"
        assert e["exhibit_png"] and e["exhibit_verified"] is True
        assert "recorded fit" in e["exhibit_reason"] and "UNALIGNED" in e["exhibit_reason"]
        assert e["findings_index"] == 1

    def test_a_lookalike_is_STILL_boxed_and_says_failed(self, tmp_path):
        """The gate annotates; it never removes the box."""
        pytest.importorskip("cv2"); pytest.importorskip("scipy")
        _a, _b, M = _textured_pair(tmp_path, "lookalike")
        man = RM.render_review_media(tmp_path, _control_result(M))
        e = man["groups"][0]
        assert e["exhibit_gate"] == "failed"
        assert e["exhibit_png"] and e["exhibit_verified"] is True
        assert "_unverified" not in e["exhibit_png"]

    def test_the_recorded_fit_is_used_and_estimate_match_is_NOT_called(self, tmp_path, monkeypatch):
        pytest.importorskip("cv2"); pytest.importorskip("scipy")
        _a, _b, M = _textured_pair(tmp_path, "dup")
        animator = RM._load_animator()
        called = []
        def refuse(*a, **k):
            called.append(1)
            raise SystemExit("no")
        monkeypatch.setattr(animator, "estimate_match", refuse)
        monkeypatch.setattr(RM, "_load_animator", lambda: animator)
        man = RM.render_review_media(tmp_path, _control_result(M))
        assert not called
        assert man["groups"][0]["exhibit_verified"] is True

    def test_no_affine_falls_back_and_a_refusal_is_the_plain_pair(self, tmp_path, monkeypatch):
        pytest.importorskip("cv2")
        _textured_pair(tmp_path, "dup")
        res = _control_result(None)
        del res["duplicate_groups"][0]["match_stats"]["affine"]
        animator = RM._load_animator()
        def refuse(*a, **k):
            raise SystemExit("REFUSING: nope")
        monkeypatch.setattr(animator, "estimate_match", refuse)
        monkeypatch.setattr(RM, "_load_animator", lambda: animator)
        man = RM.render_review_media(tmp_path, res)
        e = man["groups"][0]
        assert e["exhibit_verified"] is False
        assert e["exhibit_gate"] == "not_measured" and "control" not in e["measurements"]
        assert e["exhibit_png"].endswith("_unverified.png")

    def test_a_bail_path_is_not_verified(self, tmp_path):
        man = RM.render_review_media(tmp_path, _control_result([[1, 0, 0], [0, 1, 0]]))
        e = man["groups"][0]                       # no PNGs on disk at all
        assert e["exhibit_png"] is None and e["exhibit_verified"] is False
        assert e["exhibit_gate"] == "not_measured"

    def test_a_block_is_carried_forward_unless_the_code_moved(self, tmp_path, monkeypatch):
        pytest.importorskip("cv2"); pytest.importorskip("scipy")
        from metascience_observatory_image_analysis.image_forensics import match_control as MC
        _a, _b, M = _textured_pair(tmp_path, "dup")
        first = RM.render_review_media(tmp_path, _control_result(M))["groups"][0]["measurements"]["control"]
        second = RM.render_review_media(tmp_path, _control_result(M))["groups"][0]["measurements"]["control"]
        assert second["measured_at"] == first["measured_at"]          # carried
        monkeypatch.setattr(MC, "code_sha", lambda: "moved")
        third = RM.render_review_media(tmp_path, _control_result(M))["groups"][0]["measurements"]["control"]
        assert third["code_sha"] == "moved"                            # re-measured

    def test_the_block_is_PRESENT_after_a_render(self, tmp_path):
        """An annotator that raised and was swallowed must not be green."""
        pytest.importorskip("cv2"); pytest.importorskip("scipy")
        _a, _b, M = _textured_pair(tmp_path, "dup")
        man = RM.render_review_media(tmp_path, _control_result(M))
        path = tmp_path / "panels" / "review" / RM.MANIFEST_NAME
        on_disk = json.loads(path.read_text())
        assert "control" in on_disk["groups"][0]["measurements"]
        assert on_disk["groups"][0]["exhibit_gate"] in ("passed", "failed")


class TestTheTwoNumberings:
    def _result(self):
        g = lambda k, ev: {"kind": k, "duplication_evidence": ev,
                           "panels": ["d:x1", "d:x2"], "match_stats": {"rotation_deg": 90.0, "scale": 1.6, "n_inliers": 9}}
        return {"paper_id": "p", "duplicate_groups": [g("transformed_match", False),
                                                      g("transformed_match", True)]}

    def test_findings_index_names_the_position_in_duplicate_groups(self, tmp_path):
        man = RM.render_review_media(tmp_path, self._result())
        assert len(man["groups"]) == 1
        e = man["groups"][0]
        assert e["group_index"] == 1 and e["findings_index"] == 2

    def test_video_todo_looks_for_the_name_the_writer_used(self, tmp_path):
        res = self._result()
        (tmp_path / "image_duplication_findings.json").write_text(json.dumps(res))
        RM.render_review_media(tmp_path, res)
        (tmp_path / "panels" / "review" / "group01_transformed_match.mp4").write_bytes(b"x")
        assert RM.video_todo(tmp_path) == {"eligible": 1, "missing": 0}

    def test_video_todo_accepts_the_doi_named_spelling(self, tmp_path):
        res = self._result()
        (tmp_path / "image_duplication_findings.json").write_text(json.dumps(res))
        RM.render_review_media(tmp_path, res)
        slug = RM.video_slug(tmp_path)          # no metadata here: the directory name
        assert slug == tmp_path.name
        (tmp_path / "panels" / "review" / f"{slug}_group01_transformed_match.mp4").write_bytes(b"x")
        assert RM.video_todo(tmp_path) == {"eligible": 1, "missing": 0}


class TestOneExhibitPerIndex:
    def test_a_boxed_render_removes_the_plain_fallback_it_replaces(self, tmp_path):
        pytest.importorskip("cv2"); pytest.importorskip("scipy")
        _a, _b, M = _textured_pair(tmp_path, "dup")
        stale = tmp_path / "panels" / "review" / "group01_unverified.png"
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_bytes(b"old")
        man = RM.render_review_media(tmp_path, _control_result(M))
        assert man["groups"][0]["exhibit_verified"] is True
        assert not stale.exists()


    def test_a_rerender_removes_the_previous_run_s_exhibits(self, tmp_path):
        """Two runs into one review dir. The second run's group 1 is a
        different pair than the first's, so the first run's PNGs under the
        same prefix are stale and must go -- a reader who globs the folder
        (as one did on 2026-09-14) otherwise judges the wrong figure. The
        manifest names what was removed; a reviewer's `labels.json` and any
        video stay."""
        pytest.importorskip("cv2"); pytest.importorskip("scipy")
        _a, _b, M = _textured_pair(tmp_path, "dup")
        review = tmp_path / "panels" / "review"
        review.mkdir(parents=True, exist_ok=True)
        old_run = [review / "group01_transformed_match.png",
                   review / "group02_near_duplicate_phash.png",
                   review / "group03_unverified.png"]
        for p in old_run:
            p.write_bytes(b"old run")
        (review / "labels.json").write_text("{}")
        (review / "group01_transformed_match.mp4").write_bytes(b"video")
        man = RM.render_review_media(tmp_path, _control_result(M))
        assert not any(p.exists() and p.read_bytes() == b"old run" for p in old_run)
        assert set(man["stale_exhibits_removed"]) >= {
            "panels/review/group02_near_duplicate_phash.png",
            "panels/review/group03_unverified.png"}
        assert (review / "labels.json").exists()
        assert (review / "group01_transformed_match.mp4").exists()
        # And the current exhibit is still there: pruning never touches
        # what the manifest just wrote.
        assert (tmp_path / man["groups"][0]["exhibit_png"]).exists()


class TestAMirroredMatchIsDrawnInBsOwnFrame:
    """The detector's recorded affine of a flip=True group maps A into the
    MIRRORED frame of B (measured by -d5 on three real groups, 2026-09-08).
    Drawing from it unchanged puts B's box on the wrong side."""

    def _flipped_pair(self):
        import numpy as np
        from tests.image_fixtures import noise_field
        field = noise_field((240, 320), seed=21)
        a = field[0:160, 0:200].copy()
        dx, dy = 40, 60
        b_in_flipped_frame = field[dy:dy + 160, dx:dx + 200]
        b = np.ascontiguousarray(np.fliplr(b_in_flipped_frame))   # what the paper printed
        M = [[1.0, 0.0, -float(dx)], [0.0, 1.0, -float(dy)]]     # a -> fliplr(b), as recorded
        return a, b, M

    def test_the_composed_affine_lands_on_the_real_panel(self):
        pytest.importorskip("cv2")
        import cv2, numpy as np
        a, b, M = self._flipped_pair()
        stats = {"affine": M, "flip": True, "n_inliers": 80, "inlier_ratio": 0.8,
                 "rotation_deg": 0.0, "scale": 1.0,
                 "inlier_box_a": [50, 70, 150, 150], "inlier_box_b": [10, 10, 110, 90]}
        m = RM._match_from_stats(RM._load_animator(), stats, a, b, None)
        warped = cv2.warpAffine(a, m.M, (b.shape[1], b.shape[0]))
        ones = cv2.warpAffine(np.ones(a.shape, np.uint8), m.M, (b.shape[1], b.shape[0])) > 0
        r = np.corrcoef(warped[ones].astype(float), b[ones].astype(float))[0, 1]
        assert r > 0.9, r
        assert m.pearson_r > 0.9
        # B's box mirrored into B's own frame: x -> wb - 1 - x
        xs = m.dst_pts[:, 0]
        assert xs.min() == pytest.approx(b.shape[1] - 1 - 110) and xs.max() == pytest.approx(b.shape[1] - 1 - 10)

    def test_a_flipped_group_is_not_measured_by_a_measurer_that_cannot_take_flip(self):
        def measurer_without_flip(a, b, affine, *, inlier_box_b=None):
            return {"note": "", "lift": 0.0, "agree_frac": 0.0}
        def measurer_with_flip(a, b, affine, *, inlier_box_b=None, flip=False):
            return {"flip": flip}
        st = {"affine": [[1, 0, 0], [0, 1, 0]], "flip": True}
        assert RM._measure_in_the_right_frame(measurer_without_flip, None, None, st) is None
        assert RM._measure_in_the_right_frame(measurer_with_flip, None, None, st) == {"flip": True}
        st["flip"] = False
        assert RM._measure_in_the_right_frame(measurer_without_flip, None, None, st) is not None


class TestAMirroredGroupIsMeasuredThroughTheCallSite:
    def test_flip_true_with_a_mirrored_panel_b_passes_the_gate(self, tmp_path):
        """Pins the plumbing: stats.flip reaches measure_control, so a real
        mirrored duplication is boxed and gated `passed`, not demoted."""
        pytest.importorskip("cv2"); pytest.importorskip("scipy")
        import numpy as np
        from tests.image_fixtures import save_png, shifted_crop_pair
        a, b, M = shifted_crop_pair()
        save_png(tmp_path / "panels" / "xrefA.png", a)
        save_png(tmp_path / "panels" / "xrefB.png", np.ascontiguousarray(np.fliplr(b)))
        res = _control_result(M, flip=True)
        man = RM.render_review_media(tmp_path, res)
        e = man["groups"][0]
        assert e["exhibit_gate"] == "passed", e["measurements"].get("control")
        assert e["measurements"]["control"]["flip"] is True
        assert e["exhibit_verified"] is True and e["transform"] == "flip"


class TestThePlacementKeepsItsBox:
    """`_placements` used to keep the page and the figure label only, so a
    viewer could open the page and nothing else, and the identity sidecar
    had no key to join on. The box, occurrence id, box kind and subfigure
    are carried WHEN RECORDED; a group with only a page still says only
    the page (the manifest never invents a box)."""

    def test_recorded_geometry_survives_into_the_manifest(self):
        group = {"placements": {"d:xrefA": [
            {"page": 7, "figure_label": "Figure 4", "bbox": [10.5, 20, 110.5, 220],
             "occurrence_id": "occ-1", "bbox_kind": "stream_exact",
             "subfigure": {"status": "observed", "raw": "A", "normalized": "A"},
             "transform": [100, 0, 0, 200, 10.5, 20], "visible": True}]}}
        assert RM._placements(group, "d:xrefA") == [
            {"page": 7, "figure_label": "Figure 4", "bbox": [10.5, 20, 110.5, 220],
             "occurrence_id": "occ-1", "bbox_kind": "stream_exact",
             "subfigure": {"status": "observed", "raw": "A", "normalized": "A"}}]

    def test_page_only_placements_stay_page_only(self):
        group = {"placements": {"d:xrefA": [{"page": 7, "figure_label": "Figure 4", "bbox": None}]}}
        assert RM._placements(group, "d:xrefA") == [{"page": 7, "figure_label": "Figure 4"}]

    def test_two_occurrences_on_one_page_are_two_placements(self):
        """Deduplication was on (page, label): two prints of one stream on
        one page collapsed into one. With the box carried they are two."""
        group = {"placements": {"d:xrefA": [
            {"page": 7, "figure_label": "Figure 4", "bbox": [10, 20, 110, 220], "occurrence_id": "o1"},
            {"page": 7, "figure_label": "Figure 4", "bbox": [300, 20, 400, 220], "occurrence_id": "o2"}]}}
        assert [p["occurrence_id"] for p in RM._placements(group, "d:xrefA")] == ["o1", "o2"]


class TestACropIsCutBeforeItIsCalledAbsent:
    """The pair branch must materialise its own crops, as the clone branch
    always has.

    MEASURED 2026-09-15 on the embargoed 2026-09 corpus: **16,367 of 18,073 groups
    (90.6%)** recorded `no PNG on disk for panel <uid>` while every file it
    named was present in `panels/` -- written by the harvest one to two
    SECONDS after the manifest. A crop_segment has no PNG until one is cut,
    the renderer walked the groups before that happened, and whether a paper
    got exhibits at all came down to which side of that second it landed on.
    66 of the 68 groups eligible for a video were lost the same way.

    The failure was silent in the worst way available: nothing raised, the
    findings were all correct, and the only trace was a per-group reason
    string that read like a statement about the paper.
    """

    def _pdf_with_one_montage(self, tmp_path):
        """A parent stream on disk and NO crop PNGs beside it -- the state a
        fresh run is in when the renderer reaches the groups."""
        import numpy as np
        panels = tmp_path / "panels"
        panels.mkdir()
        rng = np.random.default_rng(5)
        tile = (rng.random((120, 120)) * 255).astype("uint8")
        montage = np.zeros((120, 260), "uint8")
        montage[:, :120] = tile
        montage[:, 140:] = tile            # the same tile twice: a real match
        import fitz
        rgb = np.stack([montage] * 3, -1)
        pix = fitz.Pixmap(fitz.csRGB, montage.shape[1], montage.shape[0],
                          rgb.tobytes(), False)
        pix.save(str(panels / "xref1.png"))
        (panels / "panel_index.json").write_text(json.dumps({"paper_id": "p", "panels": [
            {"uid": "d:xref1", "panel_id": "xref1", "image_path": "",
             "acquisition": "embedded_stream"},
            {"uid": "d:xref1-seg1", "panel_id": "xref1-seg1", "image_path": "",
             "parent_panel_id": "xref1", "crop_box": [0, 0, 120, 120]},
            {"uid": "d:xref1-seg2", "panel_id": "xref1-seg2", "image_path": "",
             "parent_panel_id": "xref1", "crop_box": [0, 140, 120, 260]},
        ]}), encoding="utf-8")
        return panels

    def test_absent_crop_pngs_are_cut_from_the_parent_not_reported_missing(
            self, tmp_path, monkeypatch):
        panels = self._pdf_with_one_montage(tmp_path)
        assert not (panels / "xref1-seg1.png").exists(), "the premise: no crop yet"
        cut = []

        def fake_materialise(paper_dir, uids):
            # Stand in for the real cutter: the point under test is that the
            # pair branch ASKS, having never asked before this change.
            import fitz
            import numpy as np
            idx = json.loads((panels / "panel_index.json").read_text())
            recs = {r["uid"]: r for r in idx["panels"]}
            parent = fitz.Pixmap(str(panels / "xref1.png"))
            arr = np.frombuffer(parent.samples, "uint8").reshape(
                parent.height, parent.width, parent.n)
            for uid in uids:
                cut.append(uid)
                y0, x0, y1, x1 = recs[uid]["crop_box"]
                sub = np.ascontiguousarray(arr[y0:y1, x0:x1, :3])
                out = fitz.Pixmap(fitz.csRGB, sub.shape[1], sub.shape[0],
                                  sub.tobytes(), False)
                out.save(str(panels / f"{recs[uid]['panel_id']}.png"))
            return list(uids)

        monkeypatch.setattr(
            "metascience_observatory_image_analysis.image_forensics.review_media"
            ".materialise_crops", fake_materialise)
        result = {"paper_id": "p", "duplicate_groups": [{
            "kind": "transformed_match", "duplication_evidence": True,
            "panels": ["d:xref1-seg1", "d:xref1-seg2"],
            "figure_labels": ["Figure 1"], "sentence": "s",
            "match_stats": {"rotation_deg": 0.0, "scale": 1.0, "n_inliers": 200},
        }]}
        man = RM.render_review_media(tmp_path, result, render_videos=False)
        entry = man["groups"][0]
        assert sorted(cut) == ["d:xref1-seg1", "d:xref1-seg2"], (
            "both crops of the pair must be asked for, not just the first")
        assert "no PNG on disk" not in (entry.get("exhibit_reason") or ""), (
            entry.get("exhibit_reason"))

    def test_a_crop_that_cannot_be_cut_is_still_named_as_undrawn(
            self, tmp_path, monkeypatch):
        """The known negative. When the cut genuinely fails the group must
        still be reported undrawn -- absence of an exhibit is never silence,
        and it is never 'clean'."""
        self._pdf_with_one_montage(tmp_path)
        monkeypatch.setattr(
            "metascience_observatory_image_analysis.image_forensics.review_media"
            ".materialise_crops",
            lambda paper_dir, uids: (_ for _ in ()).throw(RuntimeError("no cutter")))
        result = {"paper_id": "p", "duplicate_groups": [{
            "kind": "transformed_match", "duplication_evidence": True,
            "panels": ["d:xref1-seg1", "d:xref1-seg2"],
            "figure_labels": ["Figure 1"], "sentence": "s",
            "match_stats": {"rotation_deg": 0.0, "scale": 1.0, "n_inliers": 200},
        }]}
        man = RM.render_review_media(tmp_path, result, render_videos=False)
        entry = man["groups"][0]
        assert entry["exhibit_png"] in (None, False)
        assert "could not be cut from its parent" in entry["exhibit_reason"]
        assert "undrawn, not clean" in entry["exhibit_reason"]


class TestTextFreeStills:
    def test_verified_and_unverified_small_panels_have_no_generated_text(self, tmp_path, monkeypatch):
        import cv2
        import numpy as np
        animator = RM._load_animator()
        a = np.full((80, 100), 80, np.uint8)
        b = np.full((60, 120), 150, np.uint8)
        ac = np.full((80, 100, 3), (25, 75, 180), np.uint8)
        bc = np.full((60, 120, 3), (180, 75, 25), np.uint8)
        match = animator.Match(M=np.array([[1., 0., 0.], [0., 1., 0.]]),
            n_inliers=4, n_ratio_matches=4, flip=False, rotation_deg=0.,
            scale=1., pearson_r=0.9, overlap_frac=0.5,
            src_pts=np.array([[20, 20], [60, 20], [60, 40], [20, 40]]),
            dst_pts=np.array([[20, 20], [60, 20], [60, 40], [20, 40]]))

        def no_text(*args, **kwargs):
            pytest.fail("Still comparison images must not rasterize generated text")

        monkeypatch.setattr(cv2, 'putText', no_text)
        verified = tmp_path / 'verified.png'
        animator.pubpeer_figure(a, b, match, 'Figure 1', 'Figure 2', 'Long title '*30,
            '10.1/test', verified, a_color=ac, b_color=bc, extra_lines=['Explanation '*100])
        image = cv2.imread(str(verified))
        assert image.shape == (104, 262, 3)
        np.testing.assert_array_equal(image[22, 22], ac[10, 10])
        np.testing.assert_array_equal(image[22, 140], bc[10, 10])
        assert np.any(np.all(image == animator.TARGET_BORDER, axis=2))
        assert np.any(np.all(image == animator.SHARED_BORDER, axis=2))
        plain = tmp_path / 'plain.png'
        RM._plain_pair(ac, bc, 'A'*100, 'B'*100, 'Unverified '*100, plain)
        image = cv2.imread(str(plain))
        assert image.shape == (104, 262, 3)
        np.testing.assert_array_equal(image[12:92, 12:112], ac)
        np.testing.assert_array_equal(image[12:72, 130:250], bc)
