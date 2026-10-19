"""Compound-figure panel segmentation (waterfall tier 7).

The asymmetry under test: a missed split leaves the montage as one panel
(today's behavior, safe); a hallucinated split hands the duplication
detector crops that share texture BECAUSE they were cut from one image --
manufactured evidence. So the positive case must produce exact boxes, and
every ambiguous case must produce no split at all.
"""
from pathlib import Path

import numpy as np
import pytest

from metascience_observatory_image_analysis.image_forensics import panels as P

REPO = Path(__file__).resolve().parents[1]
SMOKE_PDF = (REPO / "tests/fixtures/papers/cerebrolysin_papers" / "10.1007--s004010051012"
             / "10.1007--s004010051012.pdf")


def _montage_2x2(bg=255, lo=0, hi=200, panel=150, gutter=20, margin=20,
                 seed=0):
    """4 noise panels on a uniform background with real gutters.

    Noise drawn from [lo, hi) so with bg=255 every panel pixel is ink
    (differs from background by > _SEG_INK_DELTA) -- the geometry is exact
    by construction, not probabilistically.
    """
    rng = np.random.default_rng(seed)
    side = 2 * margin + 2 * panel + gutter
    gray = np.full((side, side), bg, dtype=np.uint8)
    starts = (margin, margin + panel + gutter)
    boxes = []
    for r in starts:
        for c in starts:
            gray[r:r + panel, c:c + panel] = rng.integers(
                lo, hi, (panel, panel), dtype=np.uint8)
            boxes.append((r, c, r + panel, c + panel))
    return gray, boxes


# ---------------------------------------------------------------------------
# segment_gray: the positive case, exact
# ---------------------------------------------------------------------------


class TestAGridMontageSplitsIntoItsPanels:
    def test_2x2_on_white_yields_4_exact_boxes(self):
        gray, expected = _montage_2x2()
        seg = P.segment_gray(gray)
        assert seg["segmentation_uncertain"] is False
        assert sorted(seg["boxes"]) == sorted(expected)
        for r0, c0, r1, c1 in seg["boxes"]:
            assert (r1 - r0) == 150 and (c1 - c0) == 150

    def test_dark_background_micrograph_montage_also_splits(self):
        """Ink is defined against the BORDER shade, not against white: a
        dark-field montage has near-black gutters, and calling its bright
        panels 'background' would blind the splitter to exactly the figure
        class (confocal micrographs) this corpus is full of."""
        gray, expected = _montage_2x2(bg=10, lo=100, hi=256)
        seg = P.segment_gray(gray)
        assert seg["segmentation_uncertain"] is False
        assert sorted(seg["boxes"]) == sorted(expected)


# ---------------------------------------------------------------------------
# segment_gray: every ambiguous case refuses to split
# ---------------------------------------------------------------------------


class TestAmbiguityNeverSplits:
    def test_gradient_background_is_one_panel_and_not_uncertain(self):
        """A gradient's mid-shades sit near any single background estimate,
        so a naive profile finds a phantom 'gutter' down the middle. No
        single border shade exists here, and that absence must read as 'one
        panel', confidently -- not as a failed segmentation."""
        ramp = np.linspace(0, 255, 400).astype(np.uint8)
        gray = np.tile(ramp, (400, 1))
        seg = P.segment_gray(gray)
        assert seg["boxes"] == [(0, 0, 400, 400)]
        assert seg["segmentation_uncertain"] is False

    def test_a_faint_gutter_above_the_ink_floor_does_not_split(self):
        """Gutter rows carrying ~3% ink (annotation ticks, dust, bleed) are
        above the 1% floor: ambiguous, therefore not a gutter."""
        rng = np.random.default_rng(1)
        gray = np.full((360, 360), 255, dtype=np.uint8)
        gray[20:170, 20:340] = rng.integers(0, 200, (150, 320), dtype=np.uint8)
        gray[190:340, 20:340] = rng.integers(0, 200, (150, 320), dtype=np.uint8)
        band = gray[170:190, 20:340]
        band[rng.random(band.shape) < 0.03] = 0
        seg = P.segment_gray(gray)
        assert seg["boxes"] == [(0, 0, 360, 360)]
        assert seg["segmentation_uncertain"] is False

    def test_thin_gaps_below_the_run_minimum_do_not_split(self):
        """An 8-px gap is line spacing, not a gutter (minimum run is 12)."""
        rng = np.random.default_rng(2)
        gray = np.full((328, 360), 255, dtype=np.uint8)
        gray[20:170, 20:340] = rng.integers(0, 200, (150, 320), dtype=np.uint8)
        gray[178:328 - 20, 20:340] = rng.integers(0, 200, (130, 320),
                                                  dtype=np.uint8)
        seg = P.segment_gray(gray)
        assert len(seg["boxes"]) == 1
        assert seg["segmentation_uncertain"] is False


class TestTheSelfCheckDiscardsIncoherentSplits:
    def test_a_many_blob_texture_returns_unsplit_and_uncertain(self):
        """A 6x6 grid of blobs yields 36 'sub-panels' -- more than any
        credible figure grid. The FigSplit-style self-check throws the whole
        segmentation away and SAYS SO: coverage of this image is unknown,
        not 'one panel, checked'."""
        rng = np.random.default_rng(3)
        side = 7 * 20 + 6 * 110
        gray = np.full((side, side), 255, dtype=np.uint8)
        for i in range(6):
            for j in range(6):
                r = 20 + i * 130
                c = 20 + j * 130
                gray[r:r + 110, c:c + 110] = rng.integers(
                    0, 200, (110, 110), dtype=np.uint8)
        seg = P.segment_gray(gray)
        assert seg["boxes"] == [(0, 0, side, side)]
        assert seg["segmentation_uncertain"] is True
        assert seg["reason"]

    def test_low_coverage_returns_unsplit_and_uncertain(self):
        """Two small panels lost in a 500x500 field: whatever the profile
        found, sub-panels covering under 60% of the parent mean the split
        does not describe the image."""
        rng = np.random.default_rng(4)
        gray = np.full((500, 500), 255, dtype=np.uint8)
        gray[20:140, 20:140] = rng.integers(0, 200, (120, 120), dtype=np.uint8)
        gray[20:140, 200:320] = rng.integers(0, 200, (120, 120), dtype=np.uint8)
        seg = P.segment_gray(gray)
        assert seg["boxes"] == [(0, 0, 500, 500)]
        assert seg["segmentation_uncertain"] is True
        assert "cover" in seg["reason"]

    def test_a_non_image_input_refuses_without_raising(self):
        seg = P.segment_gray(np.zeros((3, 3, 3), dtype=np.uint8))
        assert seg["boxes"] == []
        assert seg["segmentation_uncertain"] is True
        assert seg["reason"]


# ---------------------------------------------------------------------------
# segment_panel: the crop record contract
# ---------------------------------------------------------------------------


class TestCropRecordsCarryNoStreamIdentity:
    def _parent(self):
        return P.Panel(
            paper_id="paper1",
            panel_id="xref9",
            source="paper1.pdf",
            acquisition=P.EMBEDDED_STREAM,
            xref=9,
            content_sha256="f" * 64,
            placements=[{"page": 4, "bbox": [72.0, 100.0, 308.0, 336.0],
                         "mirrored": False, "rotation_deg": 0.0,
                         "figure_label": "Figure 3"}],
        ).as_dict()

    def test_record_shape(self):
        gray, _ = _montage_2x2()
        records = P.segment_panel(self._parent(), gray)
        assert len(records) == 4
        for i, rec in enumerate(records, start=1):
            assert rec["acquisition"] == P.CROP_SEGMENT
            assert rec["acquisition"] not in P.ORIGINAL_BYTES
            assert rec["content_sha256"] == ""      # no stream identity
            assert rec["xref"] is None
            assert rec["panel_id"] == f"xref9-seg{i}"
            assert rec["parent_panel_id"] == "xref9"
            assert rec["paper_id"] == "paper1"
            assert rec["width"] == 150 and rec["height"] == 150
            r0, c0, r1, c1 = rec["crop_box"]
            assert (r1 - r0, c1 - c0) == (150, 150)
            assert rec["skip_reason"] is None
            assert isinstance(rec["phash"], str) and len(rec["phash"]) == 16
            int(rec["phash"], 16)                   # valid hex
            assert rec["entropy_bits"] > 3          # noise crops are textured
            assert any("byte-identity" in w for w in rec["warnings"])
            assert len(rec["placements"]) == 1
            pl = rec["placements"][0]
            assert pl["page"] == 4
            assert "PARENT" in pl["note"]

    def test_identical_sub_panels_hash_identically(self):
        """The property the whole tier exists for: a duplicated sub-panel
        inside one stream becomes two crops with equal phash."""
        gray, boxes = _montage_2x2()
        r0, c0, r1, c1 = boxes[0]
        s0, t0, s1, t1 = boxes[3]
        gray[s0:s1, t0:t1] = gray[r0:r1, c0:c1]
        records = P.segment_panel(self._parent(), gray)
        assert len(records) == 4
        by_box = {tuple(r["crop_box"]): r for r in records}
        assert by_box[boxes[0]]["phash"] == by_box[boxes[3]]["phash"]
        others = {by_box[boxes[1]]["phash"], by_box[boxes[2]]["phash"]}
        assert by_box[boxes[0]]["phash"] not in others

    def test_an_unsplittable_image_yields_no_records(self):
        ramp = np.linspace(0, 255, 400).astype(np.uint8)
        records = P.segment_panel(self._parent(), np.tile(ramp, (400, 1)))
        assert records == []


# ---------------------------------------------------------------------------
# extract_panels wiring: opt-in, and inert when off
# ---------------------------------------------------------------------------


def _montage_pdf(tmp_path):
    """A one-page PDF embedding a 2x2 montage decoded at 472x472 px."""
    fitz = pytest.importorskip("fitz")
    gray, boxes = _montage_2x2(panel=200, gutter=24, margin=24)
    h, w = gray.shape
    png = fitz.Pixmap(fitz.csGRAY, w, h, gray.tobytes(), 0).tobytes("png")
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_image(fitz.Rect(72, 100, 72 + w / 2, 100 + h / 2), stream=png)
    out = tmp_path / "montage.pdf"
    doc.save(out)
    doc.close()
    return out, boxes


def _row_montage(panel=150, gutter=20, margin=20, n=4, seed=5):
    """A ONE-ROW montage: n textured panels side by side. Wide and short --
    under the old square 400-px gate on its short side."""
    rng = np.random.default_rng(seed)
    h = margin * 2 + panel
    w = margin * 2 + n * panel + (n - 1) * gutter
    gray = np.full((h, w), 255, np.uint8)
    for i in range(n):
        x0 = margin + i * (panel + gutter)
        gray[margin:margin + panel, x0:x0 + panel] = rng.integers(0, 200, (panel, panel), dtype=np.uint8)
    return gray


class TestExtractPanelsSegmentMontages:
    def test_a_one_row_montage_is_split(self, tmp_path):
        """`10.1038--nn.3070` Figure 5a is 6 x 2 micrographs in 1420 x 371 px
        and Figure 4c is 1 x 4 in 994 x 179: montages under the square
        400-px gate on their short side, never split (2026-09-14), two of the
        reuses PubPeer documents between their sub-panels. A montage is
        attempted when its LONG side clears the gate and its short side
        clears `_SEG_MIN_MONTAGE_SHORT_SIDE`."""
        fitz = pytest.importorskip("fitz")
        gray = _row_montage()
        h, w = gray.shape
        assert h < P._SEG_MIN_MONTAGE_SIDE < w and h > P._SEG_MIN_MONTAGE_SHORT_SIDE
        png = fitz.Pixmap(fitz.csGRAY, w, h, gray.tobytes(), 0).tobytes("png")
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)
        page.insert_image(fitz.Rect(72, 100, 72 + w / 2, 100 + h / 2), stream=png)
        out = tmp_path / "row.pdf"
        doc.save(out)
        doc.close()
        res = P.extract_panels(out, out_dir=tmp_path / "panels", segment_montages=True)
        assert res["n_segments"] == 4, [p["panel_id"] for p in res["panels"]]

    def test_a_partially_visible_montage_s_visible_crop_is_split(self, tmp_path):
        """A figure placed under a hairline clip is `visible_crops_only`: the
        stream is withheld and its renderer-verified visible crop is
        compared -- and until 2026-09-14 the crop was never split, so a 3 x 5
        montage was ONE panel that could match nothing inside itself
        (`10.1038--nn.3070` Figures 1a, 4a, 4c, 5a; six of fourteen PubPeer
        reuses between their sub-panels). The crop takes the same pass."""
        fitz = pytest.importorskip("fitz")
        gray, boxes = _montage_2x2(panel=200, gutter=24, margin=24)
        h, w = gray.shape
        png = fitz.Pixmap(fitz.csGRAY, w, h, gray.tobytes(), 0).tobytes("png")
        source = fitz.open()
        spage = source.new_page(width=612, height=792)
        spage.insert_image(fitz.Rect(72, 100, 72 + w, 100 + h), stream=png)
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)
        # Show the source page clipped one point inside the image on the
        # left: a partial placement, hence a visible crop.
        page.show_pdf_page(fitz.Rect(0, 0, 612, 792), source, 0,
                           clip=fitz.Rect(73, 0, 612, 792))
        out = tmp_path / "clipped.pdf"
        doc.save(out)
        doc.close()
        res = P.extract_panels(out, out_dir=tmp_path / "panels", segment_montages=True)
        parent = next(p for p in res["panels"] if p["skip_reason"] == "visible_crops_only")
        crop = next(p for p in res["panels"] if p["panel_id"] == f"{parent['panel_id']}-visible1")
        segs = [p for p in res["panels"] if p.get("parent_panel_id") == crop["panel_id"]]
        assert len(segs) == 4, [p["panel_id"] for p in res["panels"]]
        assert crop["segmenter"] is not None or all(s["segmenter"] for s in segs)

    def test_flag_on_appends_segments(self, tmp_path):
        pdf, boxes = _montage_pdf(tmp_path)
        res = P.extract_panels(pdf, out_dir=tmp_path / "panels",
                               segment_montages=True)
        assert res["success"] is True
        assert res["n_panels"] == 1          # stream count is segment-blind
        assert res["n_segments"] == 4
        streams = [p for p in res["panels"]
                   if p["acquisition"] == P.EMBEDDED_STREAM]
        crops = [p for p in res["panels"]
                 if p["acquisition"] == P.CROP_SEGMENT]
        assert len(streams) == 1 and len(crops) == 4
        parent = streams[0]
        assert {c["parent_panel_id"] for c in crops} == {parent["panel_id"]}
        assert all(c["content_sha256"] == "" for c in crops)
        assert sorted(tuple(c["crop_box"]) for c in crops) == sorted(boxes)
        # decode conversion may shift pixel values, never geometry
        assert all(c["width"] == 200 and c["height"] == 200 for c in crops)

    def test_flag_off_is_inert(self, tmp_path):
        pdf, _ = _montage_pdf(tmp_path)
        out_dir = tmp_path / "panels"
        res_off = P.extract_panels(pdf, out_dir=out_dir)
        assert "n_segments" not in res_off
        assert all(p["acquisition"] != P.CROP_SEGMENT
                   for p in res_off["panels"])
        assert res_off["n_panels"] == 1
        res_on = P.extract_panels(pdf, out_dir=out_dir,
                                  segment_montages=True)
        streams_on = [p for p in res_on["panels"]
                      if p["acquisition"] == P.EMBEDDED_STREAM]
        assert streams_on == res_off["panels"]  # parents byte-identical

    def test_a_tripped_self_check_is_announced_by_extract_panels(self,
                                                                 tmp_path):
        """The many-blob pathology (36 'sub-panels') through the wiring, not
        just through `segment_gray`: the self-check discards the split, so no
        crop records exist to carry the flag, and the ONLY place the failure
        can still be told is the harvest. It used to be told nowhere -- the
        montage silently stayed one panel and read as 'one panel, checked'.
        """
        fitz = pytest.importorskip("fitz")
        rng = np.random.default_rng(3)
        side = 7 * 20 + 6 * 110          # 800 px: past the 400 px floor
        gray = np.full((side, side), 255, dtype=np.uint8)
        for i in range(6):
            for j in range(6):
                r, c = 20 + i * 130, 20 + j * 130
                gray[r:r + 110, c:c + 110] = rng.integers(
                    0, 200, (110, 110), dtype=np.uint8)
        png = fitz.Pixmap(fitz.csGRAY, side, side,
                          gray.tobytes(), 0).tobytes("png")
        doc = fitz.open()
        doc.new_page(width=612, height=792).insert_image(
            fitz.Rect(72, 100, 472, 500), stream=png)
        pdf = tmp_path / "manyblob.pdf"
        doc.save(pdf)
        doc.close()

        res = P.extract_panels(pdf, out_dir=tmp_path / "panels",
                               segment_montages=True)
        assert res["success"] is True
        assert res["n_segments"] == 0            # the split was discarded
        panel = res["panels"][0]
        for bucket in (panel["warnings"], res["warnings"]):
            assert any("segmentation self-check failed" in w
                       and "coverage of this montage is unknown" in w
                       for w in bucket), bucket
        assert any(panel["panel_id"] in w for w in res["warnings"])

    def test_a_clean_split_adds_no_self_check_warning(self, tmp_path):
        pdf, _ = _montage_pdf(tmp_path)
        res = P.extract_panels(pdf, out_dir=tmp_path / "panels",
                               segment_montages=True)
        assert res["n_segments"] == 4
        assert not any("self-check failed" in w for w in res["warnings"])
        assert not any("self-check failed" in w
                       for p in res["panels"] for w in p["warnings"])

    def test_a_small_raster_is_never_segmented(self, tmp_path):
        """Eligibility is the DECODED size (> 400 px both sides), so an
        ordinary single micrograph never reaches the splitter at all."""
        fitz = pytest.importorskip("fitz")
        gray, _ = _montage_2x2()                 # 360x360: below the floor
        h, w = gray.shape
        png = fitz.Pixmap(fitz.csGRAY, w, h, gray.tobytes(), 0).tobytes("png")
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)
        page.insert_image(fitz.Rect(72, 100, 432, 460), stream=png)
        pdf = tmp_path / "small.pdf"
        doc.save(pdf)
        doc.close()
        res = P.extract_panels(pdf, out_dir=tmp_path / "panels",
                               segment_montages=True)
        assert res["n_segments"] == 0
        assert all(p["acquisition"] != P.CROP_SEGMENT
                   for p in res["panels"])


@pytest.mark.skipif(not SMOKE_PDF.exists(),
                    reason="corpus smoke paper not present on this machine")
class TestSmokePaper:
    def test_segmentation_does_not_disturb_the_harvest(self, tmp_path):
        """The smoke paper has 22 embedded rasters (verified 2026-08-17);
        segmentation may or may not find montages among them, but the
        stream inventory and every crop's no-stream-identity contract must
        hold either way."""
        pytest.importorskip("fitz")
        res = P.extract_panels(SMOKE_PDF, out_dir=tmp_path / "panels",
                               segment_montages=True)
        assert res["success"] is True
        assert res["n_panels"] == 22
        streams = [p for p in res["panels"]
                   if p["acquisition"] == P.EMBEDDED_STREAM]
        crops = [p for p in res["panels"]
                 if p["acquisition"] == P.CROP_SEGMENT]
        assert len(streams) == 22
        assert res["n_segments"] == len(crops)
        stream_ids = {p["panel_id"] for p in streams}
        # A crop's parent is a stream, or (since 2026-09-14) a stream's
        # renderer-verified visible crop -- itself a crop of a stream.
        visible_ids = {p["panel_id"] for p in crops
                       if p["panel_id"].endswith("-visible1")
                       and p["parent_panel_id"] in stream_ids}
        for c in crops:
            assert c["content_sha256"] == ""
            assert c["parent_panel_id"] in stream_ids | visible_ids


class TestAMontageWithNoEstimableBackground:
    """`_border_shade` samples the border ring, so a figure carrying a
    coloured banner or coloured panel labels around its edge reports a
    background spread too wide to threshold against and stays ONE panel.

    MEASURED on `10.1007--s12035-017-0742-9`: a six-panel figure refused with
    `border shade spans 68 levels`, and the three duplications hiding between
    its sub-panels were therefore invisible to every tier. The gutters in that
    case are unambiguous even though the background is not, so a regular
    white-gutter grid is accepted on its own.
    """

    def _montage(self, rows, cols, panel=200, gutter=24, banner=60):
        """Panels of random texture on white, under a saturated banner.

        The banner is separated from the panels by a gutter, as a real figure
        separates its title from its artwork -- a header touching the panels
        would be ONE row band containing both, and the column projection
        inside it could not find a gutter, which is correct: nothing there
        says where the panels start.
        """
        rng = np.random.default_rng(4)
        h = banner + gutter + rows * panel + (rows - 1) * gutter
        w = cols * panel + (cols - 1) * gutter
        img = np.full((h, w), 255, np.uint8)
        # The banner is what breaks background estimation: dark ink in the
        # border ring, spanning many levels.
        img[:banner] = rng.integers(0, 120, size=(banner, w), dtype=np.uint8)
        for r in range(rows):
            for c in range(cols):
                y = banner + gutter + r * (panel + gutter)
                x = c * (panel + gutter)
                img[y:y + panel, x:x + panel] = rng.integers(
                    0, 256, size=(panel, panel), dtype=np.uint8)
        return img

    def test_a_regular_grid_splits_despite_the_banner(self):
        img = self._montage(2, 3)
        seg = P.segment_gray(img)
        assert len(seg["boxes"]) == 6
        assert seg["segmentation_uncertain"] is False
        assert "gutters alone" in seg["reason"]

    def test_an_irregular_split_is_still_refused(self):
        """Regularity, not the mere presence of white lines, is what licenses
        a split when the background could not be estimated. Bands of wildly
        different widths are texture, not a figure's panel grid."""
        rng = np.random.default_rng(5)
        h, w = 700, 900
        img = np.full((h, w), 255, np.uint8)
        img[:60] = rng.integers(0, 120, size=(60, w), dtype=np.uint8)
        # 140px band and a 600px band: no figure lays panels out like this.
        for x0, x1 in ((0, 140), (200, 800)):
            img[100:600, x0:x1] = rng.integers(0, 256, size=(500, x1 - x0),
                                               dtype=np.uint8)
        seg = P.segment_gray(img)
        assert len(seg["boxes"]) == 1
        assert "do not form a regular grid" in seg["reason"]

    def test_a_single_photograph_is_still_one_panel(self):
        """The fallback must not invent a grid in a plain image."""
        rng = np.random.default_rng(6)
        img = rng.integers(0, 256, size=(600, 800), dtype=np.uint8)
        img[:50] = rng.integers(0, 120, size=(50, 800), dtype=np.uint8)
        assert len(P.segment_gray(img)["boxes"]) == 1
