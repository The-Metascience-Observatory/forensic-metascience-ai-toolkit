"""The figure extractor reported `success: true, n_figures: 6` on a paper
where three of the six crops were garbage.

Measured on `10.1002--hbm.26595`, before this fix:

- `Figure_2_p006.png` (4,760 B) and `Figure_5_p010.png` (4,812 B) held nothing
  but the running header. Their captions sit ABOVE their artwork, and the crop
  was hardcoded to take the band above the caption -- so it took the 52 points
  between the page edge and the caption. In the same document Figures 1, 3 and
  4 are captioned below, which is why the bug looked like it worked.
- `Figure_2a_p005.png` was body prose. An in-text cross-reference
  `(Figure 2a,b). For comparison...` broke across a block boundary, so the next
  block began `,b). For comparison`, matched the caption opener, and was long
  enough to pass the stub check.

Nothing in the output said any of this. That is the part being fixed: the crop
now comes from the artwork's real bounding box, and every figure carries a
`crop_confidence` a reader can act on.

A SECOND PASS, MEASURED ACROSS THE WHOLE CORPUS (405 PDFs, JATS `<fig>` counts
on the 97 papers that have XML, which is a count taken independently of the PDF
caption walk), found that "the artwork's real bounding box" was still not the
figure, in two directions.

MISSED. 176 of the 213 ground-truth figures were found; 11 papers with figures
returned zero. The caption filters were length-based -- `len(block) < 40` and
`len(body) < 15` -- and discarded 111 caption-shaped blocks corpus-wide,
including `Figure 1. Consort flow diagram.` (31 characters, and the only figure
in `10.1002--jia2.70057`) and the bare `Figure 1` labels Research Square prints
on its figure pages. Requiring a number after "Figure" discarded 43 more,
including every JAMA single-figure paper, which writes `Figure.`

CLIPPED. `get_drawings()` returns PATHS, and a chart's axis labels, panel
titles and legend are TEXT, so cropping to the paths cuts them off: 20.6% of
1,042 crops had label-shaped text still abutting them, and 10.5% had further
artwork within 40 points. And the artwork itself was often invisible -- a bar
chart is one small path per bar, all of them under the 50x20 filter.

The tests below are organised around those two, and each one names the paper it
was measured on.
"""
import re
from pathlib import Path

import pytest

from metascience_observatory_image_analysis.extraction.figures import (
    _artwork_for_caption,
    _cluster_rects,
    _column_walls,
    _figure_region,
    _merge_art,
    _parse_caption_block,
    _prose_flags,
    extract_figures,
    find_captions_in_blocks,
)

PDF = Path("tests/fixtures/papers/high_value_pdfs_to_run_on/10.1002--hbm.26595/10.1002--hbm.26595.pdf")


# --------------------------------------------------------------------------
# Geometry, on synthetic rectangles.
# --------------------------------------------------------------------------

class TestArtworkSelection:
    def test_artwork_above_the_caption_is_found(self):
        art, gap = _artwork_for_caption((45, 313, 550, 340), [(121, 52, 474, 299)])
        assert art == (121, 52, 474, 299)
        assert gap == pytest.approx(14)

    def test_artwork_below_the_caption_is_found(self):
        """The case that produced 4,760 bytes of running header."""
        art, gap = _artwork_for_caption((45, 460, 550, 478), [(46, 490, 398, 893)])
        assert art == (46, 490, 398, 893)
        assert gap == pytest.approx(12)

    def test_the_nearest_of_several_wins(self):
        art, _ = _artwork_for_caption(
            (45, 254, 550, 290),
            [(85, 52, 510, 240), (207, 355, 338, 401)],
        )
        assert art == (85, 52, 510, 240), "14 points above beats 65 below"

    def test_no_artwork_returns_nothing_rather_than_guessing(self):
        art, gap = _artwork_for_caption((45, 169, 550, 190), [])
        assert art is None
        assert gap == float("inf")


class TestArtworkMerging:
    def test_panels_with_hairline_gaps_become_one_figure(self):
        merged = _merge_art([(50, 100, 300, 200), (50, 205, 300, 300)])
        assert merged == [(50, 100, 300, 300)]

    def test_well_separated_artwork_stays_separate(self):
        merged = _merge_art([(50, 100, 300, 200), (50, 400, 300, 500)])
        assert len(merged) == 2

    def test_a_tall_drawing_does_not_swallow_the_page(self):
        """The old walk compared only against the most recent cluster, in y
        order, so one tall rectangle absorbed everything below it. On
        `10.2147--jn.s50114` p11 that turned three separately captioned figures
        into a single 71,28-558,649 cluster and gave all three the same crop."""
        merged = _merge_art([
            (50, 50, 550, 600),      # tall
            (60, 640, 200, 700),     # 40 pt below it, its own figure
        ])
        assert len(merged) == 2

    def test_columns_do_not_merge_across_the_gutter(self):
        merged = _merge_art([(50, 100, 280, 300), (310, 100, 540, 300)])
        assert len(merged) == 2, "no horizontal overlap, so not one figure"


class TestBarChartsAreVisibleAtAll:
    """A bar chart is many small paths, not one big one.

    Measured on `10.2147--jn.s50114` p6: the bars are 30 points wide and the
    axis rules 0 points tall, so a 50x20 filter applied per path left the page
    with one artwork rectangle -- a raster image belonging to a different
    figure -- and all four captions on the page were cropped to it.
    """

    def test_adjacent_bars_become_one_chart(self):
        bars = [(94, 69, 124, 191), (133, 125, 163, 191), (172, 103, 202, 191)]
        clustered = _cluster_rects(bars, 12.0)
        assert clustered == [(94, 69, 202, 191)]

    def test_two_charts_side_by_side_stay_apart(self):
        clustered = _cluster_rects(
            [(86, 60, 286, 191), (338, 60, 537, 190)], 12.0
        )
        assert len(clustered) == 2

    def test_a_cluster_may_close_around_one_caption_but_not_two(self):
        """Journals box a figure together WITH its caption, and stack those
        boxes with hairline gaps. On `10.4172--2155-9562.1000450` p6 the boxes
        for Figures 4, 5 and 6 merged into one rectangle before anything could
        object -- and because each box encloses a caption, no caption could
        bound the region either, so all three captions were handed a crop of all
        three figures."""
        boxes = [(43, 110, 567, 320), (43, 330, 567, 540)]
        caps = [(50, 280, 560, 310), (50, 500, 560, 530)]
        assert len(_cluster_rects(boxes, 12.0, caps)) == 2
        assert len(_cluster_rects(boxes, 12.0)) == 1, (
            "without captions there is nothing to object, which is the "
            "behaviour every other caller relies on"
        )


class TestProseIsTheWall:
    def test_stacked_body_lines_are_prose(self):
        """Journal PDFs return body text one block per LINE, so length alone
        cannot find a paragraph. These two are `10.1002--hbm.26595` p6."""
        blocks = [
            ((46, 508, 288, 516),
             "As described above, predicted BMI was correlated with observed"),
            ((46, 521, 288, 529),
             "BMI. Hence, we examined whether structural brain alteration follow-"),
        ]
        assert _prose_flags(blocks) == [True, True]

    def test_a_panel_title_is_not_prose(self):
        """10 words and 62 characters, and it is a panel heading -- exactly the
        shape of the body line above. Calling it a wall cut
        `10.1001--jamanetworkopen.2023.51752` p8 down to its top two panels."""
        blocks = [((75, 267, 247, 274),
                   "Diastolic blood pressure of mothers of children aged 12 years C")]
        assert _prose_flags(blocks) == [False]

    def test_a_y_axis_tick_column_is_not_prose(self):
        """Tall, narrow and numeric. Treating it as a paragraph walled Figure 2
        of `10.4103--1673-5374.175063` off from its own scale."""
        blocks = [((76, 413, 88, 526), "100\n90\n80\n70\n60\n50\n40\n30\n20\n10\n0")]
        assert _prose_flags(blocks) == [False]


class TestColumnWalls:
    """`10.2147--jn.s50114` p6 sets two bar charts side by side with their
    captions side by side under them. The gutter is blank, so no barrier
    separates the charts, and the right chart's y-axis title reaches 18 points
    into it -- close enough for the left chart's region to absorb it and chain
    on into the right chart. One region, two captions, one of them left with a
    photomicrograph from further down the page."""

    PAGE = (0.0, 0.0, 612.0, 792.0)

    def test_side_by_side_captions_put_a_wall_in_the_gutter(self):
        walls = _column_walls(
            [(54, 275, 290, 311), (305, 275, 541, 311)], self.PAGE
        )
        assert len(walls) == 1
        assert walls[0][0] == pytest.approx(297.0)
        assert (walls[0][1], walls[0][3]) == (0.0, 792.0)

    def test_full_measure_captions_produce_no_walls(self):
        """Two figures stacked, both captioned across the full measure. There is
        no gutter, and inventing one would cut every figure in half."""
        assert _column_walls(
            [(51, 242, 550, 270), (51, 550, 552, 579)], self.PAGE
        ) == []

    def test_one_caption_produces_no_walls(self):
        assert _column_walls([(54, 275, 290, 311)], self.PAGE) == []


class TestRegionGrowth:
    ART = ((100, 100, 400, 300), "art")

    def test_axis_labels_outside_the_paths_are_taken_in(self):
        """`get_drawings()` returns paths; a chart's tick labels are text and
        sit OUTSIDE the paths' bounding box. That is why 20.6% of crops had
        label-shaped text abutting them before this."""
        pool = [
            self.ART,
            ((80, 150, 98, 250), "text"),     # y-axis ticks, 2 pt to the left
            ((110, 306, 390, 314), "text"),   # x-axis labels, 6 pt below
        ]
        region, blocked = _figure_region((100, 100, 400, 300), pool, [])
        assert region == (80, 100, 400, 314)
        assert blocked == []

    def test_a_second_panel_row_is_reached_through_its_labels(self):
        """The rows are 52 points apart -- far past any merge gap -- but the
        labels in between chain them together."""
        pool = [
            self.ART,
            ((110, 306, 390, 314), "text"),   # row 1 x labels
            ((110, 336, 390, 344), "text"),   # row 2 panel titles
            ((100, 352, 400, 550), "art"),    # row 2
        ]
        region, _ = _figure_region((100, 100, 400, 300), pool, [])
        assert region == (100, 100, 400, 550)

    def test_a_paragraph_stops_the_growth_and_is_reported(self):
        wall = (100, 305, 400, 315)
        pool = [self.ART, ((100, 320, 400, 600), "art")]
        region, blocked = _figure_region((100, 100, 400, 300), pool, [wall])
        assert region == (100, 100, 400, 300)
        assert [k for _, k in blocked] == ["art"]

    def test_a_quiet_wall_stops_growth_without_crying_clipped(self):
        """A figure ENDS at a caption. Counting that as possible clipping put
        the flag on 13 of the 17 figures of `10.2147--jn.s50114`."""
        wall = (100, 305, 400, 315)
        pool = [self.ART, ((100, 320, 400, 600), "art")]
        region, blocked = _figure_region(
            (100, 100, 400, 300), pool, [wall], quiet={wall}
        )
        assert region == (100, 100, 400, 300)
        assert blocked == []


class TestCaptionRecognition:
    """The old filters were `len(block) < 40` and `len(body) < 15`. Across 405
    corpus PDFs they discarded 111 caption-shaped blocks, and requiring a number
    discarded 43 more."""

    @pytest.mark.parametrize("text,label", [
        ("Figure 1. Consort flow diagram.", "Figure 1"),          # 31 chars
        ("Fig. 1 Timeline of experimental design", "Figure 1"),
        ("Figure 1", "Figure 1"),                                  # bare label
        ("Figure. Distribution of Nurse-Family Partnership Treatment Effects",
         "Figure"),                                                # JAMA, no number
        # `A.1` is appendix A, figure 1: the canonical spelling is `Figure A1`
        # (`figure_context.figure_key` never keyed `Figure A.1` at all).
        ("Fig. A.1. The THC Unit by Product Category", "Figure A1"),
        ("FIGURE 3 The DIRECT-PLUS dataset (n = 216). Scatter plots.",
         "Figure 3"),                                              # opens with "The"
        ("Fig. 4a,b Laser scanning confocal studies of APP in NT2N cells.",
         "Figure 4"),                                              # panel list
        ("FIGURE 2 (a) 3D bone and cartilage mesh, (b) 3D bone mesh.",
         "Figure 2"),                                              # panel, not "a"
        ("Fig. 1 a Overview of the randomisation procedure.", "Figure 1"),
        ("Figure S1. Sensitivity analysis excluding three trials.", "Figure S1"),
    ])
    def test_real_captions_are_kept(self, text, label):
        parsed = _parse_caption_block(text)
        assert parsed is not None, text
        assert parsed[0] == label

    @pytest.mark.parametrize("text", [
        "Figure 2a,b). For comparison, on their test set, a subset of the UK",
        "Figure 1 for flow and retention.",
        "Figure; the additional outcomes are reported in eTables 5 and 6",
        "Fig.1showsthelevelsoflipidperoxidationproductsinthebrain of rats",
        "fig 1_bestsetConverted.png 2",
    ])
    def test_cross_references_and_junk_are_rejected(self, text):
        assert _parse_caption_block(text) is None

    def test_number_followed_only_by_nonbreaking_space_is_not_a_caption(self):
        assert _parse_caption_block("Figure 3.\u00a0") is None

    def test_a_continuation_is_labelled_as_one(self):
        """MDPI splits one figure across pages: `10.3390--nu16193425` prints
        `Figure 1. Cont.` six times. Each is real artwork worth cropping, and
        none of them is a seventh figure."""
        assert _parse_caption_block("Figure 1. Cont.") == ("Figure 1 (cont.)", "")


# --------------------------------------------------------------------------
# Caption filtering.
# --------------------------------------------------------------------------

class _FakePage:
    def __init__(self, blocks):
        self._blocks = blocks

    def get_text(self, kind):
        return self._blocks


def _block(y0, text):
    return (45.0, y0, 550.0, y0 + 20.0, text, 0, 0)


class TestCrossReferencesAreNotCaptions:
    def test_a_fragment_starting_with_a_comma_is_rejected(self):
        """`(Figure 2a,b). For comparison...` split across blocks."""
        page = _FakePage([_block(169, "Figure 2a,b). For comparison, on their "
                                     "test set, a subset of the UK Biobank, "
                                     "they reported a similar correlation.")])
        assert find_captions_in_blocks(page) == []

    def test_a_real_caption_is_still_found(self):
        page = _FakePage([_block(313, "Figure 1. Study design and analysis "
                                      "overview. (a) The DIRECT-PLUS was an "
                                      "18-months lifestyle intervention.")])
        found = find_captions_in_blocks(page)
        assert len(found) == 1
        assert found[0][0] == "Figure 1"

    def test_the_caption_carries_its_own_rectangle(self):
        """So the caller stops re-finding it with `search_for`, which on page 6
        of the measured document returned a phantom rect 400 points wrong."""
        page = _FakePage([_block(313, "Figure 1. Study design and analysis "
                                      "overview. (a) The DIRECT-PLUS was an "
                                      "18-months lifestyle intervention.")])
        _, _, rect = find_captions_in_blocks(page)[0]
        assert rect == (45.0, 313.0, 550.0, 333.0)


# --------------------------------------------------------------------------
# The corpus case, end to end.
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def result(tmp_path_factory):
    return extract_figures(PDF, out_dir=tmp_path_factory.mktemp("figs"))


@pytest.mark.skipif(not PDF.exists(), reason="corpus PDF not present")
class TestFinkelsteinCrops:
    def test_the_cross_reference_is_no_longer_filed_as_a_figure(self, result):
        assert "Figure 2a" not in {f["label"] for f in result["figures"]}
        assert result["n_figures"] == 5

    @pytest.mark.parametrize("label", ["Figure 2", "Figure 5"])
    def test_the_two_header_slivers_are_now_real_crops(self, result, label):
        """Both were under 5 KB of running header; both are captioned above
        their artwork, which the old fixed band could not reach."""
        fig = next(f for f in result["figures"] if f["label"] == label)
        assert fig["crop_confidence"] == "high"
        assert Path(fig["image_path"]).stat().st_size > 50_000

    def test_the_one_that_worked_still_works(self, result):
        fig = next(f for f in result["figures"] if f["label"] == "Figure 4")
        assert fig["crop_confidence"] == "high"
        assert Path(fig["image_path"]).stat().st_size > 50_000

    def test_every_crop_is_confident_and_the_counts_agree(self, result):
        assert result["n_cropped"] == 5
        assert result["n_low_confidence"] == 0
        assert result["n_uncropped"] == 0

    def test_the_crop_is_the_artwork_not_a_fixed_band(self, result):
        """The old crop always ran the full page width from a computed top to
        the caption. The new one is the artwork's own box, so it is narrower
        than the page on at least one figure."""
        page_width = 595.0
        assert any(
            f["bbox"] and (f["bbox"][2] - f["bbox"][0]) < page_width - 20
            for f in result["figures"]
        )


# --------------------------------------------------------------------------
# The returned image must show the returned bbox.
# --------------------------------------------------------------------------
#
# Every test above runs into a FRESH temp dir, which is exactly why the
# following went unnoticed: the crop rectangle changed but the write was still
# guarded by `if not crop_png.exists()`, so on a directory holding crops from
# the older code the new bbox was returned alongside the OLD file, and
# `crop_confidence` was computed by stat()ing that old file.
#
# Measured on `10.1002--hbm.26595`, pre-existing `figures/` dir vs empty, same
# commit, IDENTICAL bbox in both:
#
#     Figure 1   high  123,818 B   vs   high  110,298 B
#     Figure 2   low     4,760 B   vs   high  191,636 B
#     Figure 3   high  502,234 B   vs   high  763,480 B
#     Figure 4   high  126,847 B   vs   high  115,859 B
#     Figure 5   low     4,812 B   vs   high  338,673 B
#
# Figures 1, 3 and 4 are the dangerous rows: `high`, no warning, wrong region.
#
# The oracle here is byte-exact rather than a size threshold. `bbox` fully
# determines the crop, so re-rendering the bbox reproduces the returned PNG
# byte for byte -- verified on all five figures. A size assertion would pass on
# any large image of the wrong region, which is the failure being tested.

def _rerender(pdf: Path, page_no: int, bbox, dpi: int = 150) -> bytes:
    """The PNG the returned bbox describes, rendered independently."""
    import fitz

    with fitz.open(pdf) as doc:
        page = doc[page_no - 1]
        zoom = dpi / 72.0
        return page.get_pixmap(
            matrix=fitz.Matrix(zoom, zoom), clip=fitz.Rect(*bbox)
        ).tobytes("png")


def _junk_png(path: Path) -> int:
    """A tiny valid PNG, standing in for a crop left by the older code.

    Under `_THIN_CROP_BYTES` (8,000) on purpose: the real stale files were
    4,760 and 4,812 bytes of running header, and their size is what dragged
    `crop_confidence` down to `low` on figures whose actual crops are 191,636
    and 338,673 bytes.
    """
    import fitz

    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 8, 8))
    pix.clear_with(255)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pix.tobytes("png"))
    return path.stat().st_size


@pytest.mark.skipif(not PDF.exists(), reason="corpus PDF not present")
class TestStaleFilesDoNotSurvive:
    def test_a_pre_existing_crop_is_replaced_not_reused(self, tmp_path):
        """The reported bug, in one assertion per figure."""
        fresh = extract_figures(PDF, out_dir=tmp_path / "fresh")

        stale_dir = tmp_path / "stale"
        stale_dir.mkdir()
        for f in fresh["figures"]:
            _junk_png(stale_dir / Path(f["image_path"]).name)
        after = extract_figures(PDF, out_dir=stale_dir)

        by_label = {f["label"]: f for f in fresh["figures"]}
        assert by_label, "fixture produced no figures to stale"
        for f in after["figures"]:
            expected = by_label[f["label"]]
            assert f["bbox"] == expected["bbox"]
            assert (
                Path(f["image_path"]).read_bytes()
                == Path(expected["image_path"]).read_bytes()
            ), f"{f['label']}: the junk file survived"

    def test_the_returned_image_is_exactly_the_returned_bbox(self, tmp_path):
        """Re-derive rather than threshold: `bbox` determines the crop, so the
        returned file must be reproducible from it byte for byte."""
        stale_dir = tmp_path / "stale"
        stale_dir.mkdir()
        first = extract_figures(PDF, out_dir=stale_dir)
        for f in first["figures"]:
            _junk_png(Path(f["image_path"]))          # corrupt every crop
        result = extract_figures(PDF, out_dir=stale_dir)

        for f in result["figures"]:
            assert f["bbox"] is not None, f"{f['label']} lost its bbox"
            assert Path(f["image_path"]).read_bytes() == _rerender(
                PDF, f["page"], f["bbox"]
            ), f"{f['label']}: image and bbox describe different regions"

    def test_confidence_describes_the_file_that_is_returned(self, tmp_path):
        """`crop_confidence` used to be stat()ed off whatever sat at the path.
        A 4,760-byte stale file reported `low` for Figure 2, whose real crop is
        191,636 bytes -- and, worse, `high` for Figures 1, 3 and 4."""
        stale_dir = tmp_path / "stale"
        stale_dir.mkdir()
        first = extract_figures(PDF, out_dir=stale_dir)
        for f in first["figures"]:
            assert _junk_png(Path(f["image_path"])) < 8_000
        result = extract_figures(PDF, out_dir=stale_dir)

        for f in result["figures"]:
            size = Path(f["image_path"]).stat().st_size
            assert f["crop_confidence"] == ("low" if size < 8_000 else "high")
            assert f["crop_confidence"] == "high", f["label"]
        assert result["n_low_confidence"] == 0
        assert result["n_cropped"] == 5

    def test_a_page_render_at_the_wrong_dpi_is_replaced(self, tmp_path):
        """`page_NNN.png` carries no dpi, so the same guard served a 150-dpi
        render to a caller asking for 300 -- 1241x1630 px where 2481x3260 was
        requested. Same defect, different file."""
        import fitz

        extract_figures(PDF, out_dir=tmp_path, dpi=150)
        small = fitz.open(tmp_path / "page_003.png")[0].rect
        extract_figures(PDF, out_dir=tmp_path, dpi=300)
        big = fitz.open(tmp_path / "page_003.png")[0].rect

        assert big.width == pytest.approx(small.width * 2, rel=0.01)
        assert big.height == pytest.approx(small.height * 2, rel=0.01)

    def test_page_renders_keep_the_name_bundle_matches(self, tmp_path):
        """`bundle.py` splits page renders from figures with
        `^page[_-]?\\d+\\.(png|jpg|jpeg|webp)$` when counting. A dpi or bbox
        component in the name would have every page render counted as a
        figure, which is one reason the cache key was not fixed in the
        filename."""
        result = extract_figures(PDF, out_dir=tmp_path)
        renders = sorted(p.name for p in tmp_path.glob("page*"))
        assert renders
        assert all(re.fullmatch(r"page_\d{3}\.png", n) for n in renders)
        assert not any(
            re.fullmatch(r"page[_-]?\d+\.png", Path(f["image_path"]).name)
            for f in result["figures"]
        ), "a crop is named like a page render and would be miscounted"


# --------------------------------------------------------------------------
# The whole-figure cases, end to end. Each is a class of failure that the
# corpus measurement turned up, pinned to the paper it was measured on.
# --------------------------------------------------------------------------

def _corpus(rel):
    for root in ("tests/fixtures/papers/high_value_pdfs_to_run_on", "tests/fixtures/papers/cerebrolysin_papers"):
        p = Path(root) / rel / f"{rel}.pdf"
        if p.exists():
            return p
    return None


UNNUMBERED = _corpus("10.1001--jamanetworkopen.2023.51752")
OUTLINED = _corpus("10.1016--j.scitotenv.2019.05.070")
BOXED = _corpus("10.3389--fphar.2023.1288718")
FOUR_UP = _corpus("10.2147--jn.s50114")


@pytest.mark.skipif(UNNUMBERED is None, reason="corpus PDF not present")
def test_an_unnumbered_figure_is_found_and_cropped_whole(tmp_path):
    """A paper with one figure calls it `Figure.` -- 0 found before. And its six
    panels are three rows separated by ~50 points of tick labels, so a merge gap
    alone reached only the top row."""
    result = extract_figures(UNNUMBERED, out_dir=tmp_path, render_pages=False)
    figs = [f for f in result["figures"] if f["page"] == 8]
    assert [f["label"] for f in figs] == ["Figure"]
    x0, y0, x1, y1 = figs[0]["bbox"]
    assert y1 - y0 > 500, "the crop stops short of the lower panel rows"
    assert x1 - x0 > 450, "the crop is missing a column of panels"


@pytest.mark.skipif(OUTLINED is None, reason="corpus PDF not present")
def test_labels_converted_to_outlines_are_inside_the_crop(tmp_path):
    """The chart body is a raster at 130.9,54.7-479.7,285.4 and every label --
    title, category names, legend, data labels -- is outlined vector below the
    artwork size floor, invisible to `get_text` as well. Cropping to the raster
    cut all of them off."""
    result = extract_figures(OUTLINED, out_dir=tmp_path, render_pages=False)
    fig = next(f for f in result["figures"] if f["page"] == 6)
    x0, _, x1, _ = fig["bbox"]
    assert x0 < 130.9, (
        f"the crop is still the raster's own box (x0={x0}); the title "
        "`Aschworth >2` and the category labels start to the left of it"
    )
    assert x1 >= 479.7


@pytest.mark.skipif(BOXED is None, reason="corpus PDF not present")
def test_a_box_that_encloses_its_caption_stops_there(tmp_path):
    """Frontiers draws one rectangle around figure AND caption, so the caption
    cannot bound the region from inside it. Growth ran past the caption and the
    Figure 3 crop came back holding Table 4 in full."""
    result = extract_figures(BOXED, out_dir=tmp_path, render_pages=False)
    fig = next(f for f in result["figures"] if f["label"] == "Figure 3")
    assert fig["bbox"][3] < 500, "the crop runs past the caption into the table"


@pytest.mark.skipif(FOUR_UP is None, reason="corpus PDF not present")
def test_four_captions_on_one_page_get_four_different_figures(tmp_path):
    """Three of these four are bar charts whose every path is under the size
    floor, so only one rectangle was visible on the page and all four captions
    were cropped to it."""
    result = extract_figures(FOUR_UP, out_dir=tmp_path, render_pages=False)
    figs = [f for f in result["figures"] if f["page"] == 6]
    assert len(figs) == 4
    boxes = {tuple(f["bbox"]) for f in figs}
    assert len(boxes) == 4, "captions on this page share a crop"
    assert all(f["crop_confidence"] == "high" for f in figs)


CAPTIONLESS = _corpus("10.1111--acer.15521")


@pytest.mark.skipif(CAPTIONLESS is None, reason="corpus PDF not present")
def test_a_paper_with_no_machine_readable_captions_says_so(tmp_path):
    """The one failure that was completely silent. This paper's JATS lists a
    figure; the only figure-shaped string in the PDF's text layer is the
    cross-reference `(Figure 1). Of the 408 women`, because the caption is part
    of the image. Nothing can be cropped, and `n_figures: 0` with no warning
    reads as `this paper has no figures`."""
    result = extract_figures(CAPTIONLESS, out_dir=tmp_path, render_pages=False)
    assert result["n_figures"] == 0
    assert any("NO FIGURE CAPTION" in w for w in result["warnings"])


@pytest.mark.skipif(PDF.exists() is False, reason="corpus PDF not present")
def test_a_paper_whose_figures_were_found_gets_no_such_warning(tmp_path):
    result = extract_figures(PDF, out_dir=tmp_path, render_pages=False)
    assert not any("NO FIGURE CAPTION" in w for w in result["warnings"])


#: Two captions on one page can reduce to the same filename, and in an EMPTY
#: directory the second crop was skipped by the old `exists()` guard so both
#: Figure records pointed at the first file -- one reporting a 750x328 px bbox
#: against a 1008x231 px image, `crop_confidence: high` on both.
#:
#: This used to be exercised on `10.1177--20552076241242328`, which produced
#: "Figure 5" twice on p15. That second "Figure 5" was not a figure: it was a
#: caption-shaped block inside Figure 5's own artwork, and the paper's JATS
#: lists 5 figures where the extractor reported 6. Rejecting it is a fix, so the
#: collision is built here instead of borrowed from a corpus accident -- the
#: guard has to hold whether or not any PDF on disk happens to trip it.
def _two_captions_one_page(path: Path) -> Path:
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    for top in (60, 430):
        page.draw_rect(fitz.Rect(60, top, 400, top + 200),
                       color=(0, 0, 0), fill=(0.35, 0.45, 0.75))
        page.insert_textbox(
            fitz.Rect(60, top + 208, 520, top + 240),
            "Figure 1. Outcome by treatment group, with 95% confidence "
            "intervals shown as vertical bars.",
            fontsize=9,
        )
    doc.save(path)
    doc.close()
    return path


@pytest.fixture(scope="module")
def colliding(tmp_path_factory):
    return _two_captions_one_page(
        tmp_path_factory.mktemp("collide") / "two_figure_ones.pdf"
    )


class TestTwoCaptionsOnOnePageDoNotShareAFile:
    def test_both_captions_are_found(self, colliding, tmp_path):
        result = extract_figures(colliding, out_dir=tmp_path)
        assert [f["label"] for f in result["figures"]] == ["Figure 1", "Figure 1"]

    def test_each_figure_gets_its_own_image(self, colliding, tmp_path):
        result = extract_figures(colliding, out_dir=tmp_path)
        cropped = [f for f in result["figures"] if f["bbox"]]
        paths = [f["image_path"] for f in cropped]
        assert len(paths) == 2
        assert len(paths) == len(set(paths)), "two figures share one crop file"

    def test_each_image_still_matches_its_own_bbox(self, colliding, tmp_path):
        result = extract_figures(colliding, out_dir=tmp_path)
        for f in result["figures"]:
            if not f["bbox"]:
                continue
            assert Path(f["image_path"]).read_bytes() == _rerender(
                colliding, f["page"], f["bbox"]
            ), f"{f['label']} p{f['page']}: image and bbox disagree"

    def test_the_disambiguated_name_still_parses_as_label_and_page(
        self, colliding, tmp_path
    ):
        """The suffix goes inside the label part because `bundle.py` recovers a
        crop's label and page with `(?P<label>.+?)_p(?P<page>\\d+)$`, anchored
        at the end -- `Figure_5_p015_2` would parse as neither."""
        result = extract_figures(colliding, out_dir=tmp_path)
        names = [Path(f["image_path"]).name for f in result["figures"] if f["bbox"]]
        assert any(re.match(r"Figure_\d+_\d+_p\d+\.png$", n) for n in names), (
            "expected a disambiguated crop"
        )
        for name in names:
            m = re.match(r"(?P<label>.+?)_p(?P<page>\d+)$", Path(name).stem)
            assert m, f"{name} is unreadable to bundle.py"
            assert int(m.group("page")) > 0


class TestADensePageFinishes:
    """`10.1073--pnas.2317690121` p5 carries 299,465 vector paths. Above
    `_MAX_PRIMITIVES` the clustering was skipped -- correctly, it is
    quadratic -- and the raw paths were handed on to `_figure_region`, which
    is quadratic too. Four papers timed out at 1,800 s in three consecutive
    sweeps of the embargoed 2026-09 corpus on that path (2026-09-14, faulthandler
    stacks all in `_figure_region`). A guard that protects one loop by
    feeding the next is not a guard."""

    def _dense_page(self, path: Path, n: int = 4_000) -> Path:
        import fitz
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        # A 'heat map': n tiny cells tiled over a 300 x 300 block, each its
        # own drawing (one Shape commit per cell -- a single Shape holding
        # them all is ONE drawing to `get_drawings`, and under the cap).
        side = int(n ** 0.5)
        step = 300.0 / side
        for i in range(side):
            for j in range(side):
                x, y = 100 + i * step, 80 + j * step
                page.draw_rect(fitz.Rect(x, y, x + step * 0.9, y + step * 0.9),
                               color=(0, 0, 0), fill=(0.5, 0.5, 0.5), width=0)
        page.insert_textbox(fitz.Rect(100, 400, 500, 430),
                            "Figure 1. A dense vector heat map.", fontsize=9)
        doc.save(path)
        return path

    def test_page_ink_hands_on_a_bounded_pool(self, tmp_path):
        import fitz
        from metascience_observatory_image_analysis.extraction import figures as F
        pdf = self._dense_page(tmp_path / "dense.pdf")
        with fitz.open(pdf) as doc:
            page = doc[0]
            n_prims = len(page.get_drawings())
            art, small, _ = F._page_ink(page)
        assert n_prims > F._MAX_PRIMITIVES, "the fixture must be over the cap"
        assert len(art) + len(small) <= F._MAX_PRIMITIVES
        # And the heat map is seen as ARTWORK, not as a dust of ink that can
        # only be absorbed: the coalesced cells cluster into one figure.
        assert any(r[2] - r[0] >= 250 and r[3] - r[1] >= 250 for r in art)

    def test_extract_figures_finishes_and_finds_the_figure(self, tmp_path):
        import time
        from metascience_observatory_image_analysis.extraction import figures as F
        pdf = self._dense_page(tmp_path / "dense.pdf")
        t = time.monotonic()
        out = F.extract_figures(pdf, out_dir=tmp_path / "figs")
        elapsed = time.monotonic() - t
        assert elapsed < 30, f"dense page took {elapsed:.0f}s"
        assert out["n_figures"] == 1

    def test_the_growth_loop_rewrite_decides_exactly_as_before(self):
        """The O(1)-removal loop against the original, on random pools with
        walls: same region, same blocked list, every time."""
        import random
        from metascience_observatory_image_analysis.extraction import figures as F

        def reference(seed, pool, barriers, quiet=frozenset()):
            region = tuple(seed)
            remaining = [c for c in pool if not F._contains(region, c[0])]
            walls = [b for b in barriers if not F._overlaps(b, region)]
            blocked = []
            changed = True
            while changed:
                changed = False
                for cand in list(remaining):
                    rect = cand[0]
                    if F._contains(region, rect):
                        remaining.remove(cand)
                        continue
                    if F._gap(rect, region) > F._REGION_PAD:
                        continue
                    grown = (min(region[0], rect[0]), min(region[1], rect[1]),
                             max(region[2], rect[2]), max(region[3], rect[3]))
                    hit = [w for w in walls if F._overlaps(w, grown)]
                    if hit:
                        if any(w not in quiet for w in hit):
                            blocked.append(cand)
                        remaining.remove(cand)
                        continue
                    region = grown
                    remaining.remove(cand)
                    changed = True
            return region, blocked

        rng = random.Random(14)
        for _ in range(200):
            def rect():
                x, y = rng.uniform(0, 500), rng.uniform(0, 700)
                return (x, y, x + rng.uniform(1, 80), y + rng.uniform(1, 40))
            seed = rect()
            pool = [(rect(), rng.choice(["art", "text", "ink"])) for _ in range(rng.randint(0, 60))]
            barriers = [rect() for _ in range(rng.randint(0, 6))]
            quiet = set(rng.sample(barriers, k=min(len(barriers), rng.randint(0, 3))))
            assert F._figure_region(seed, pool, barriers, quiet=quiet) == \
                reference(seed, pool, barriers, quiet=quiet)
