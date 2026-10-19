"""The image adjudicator may only DOWNGRADE, and must show its work.

An LLM sits between a calibrated detector and a published report here, which
is exactly where a false accusation could enter the pipeline unmeasured. The
containment is structural rather than instructed: the applier reads a verdict
and nothing else from the model's output, so there is no field it could write
that raises a severity, adds a group, or lifts the quarantine. These tests pin
that, plus the two demotions that stop an explanation from being cheaper than
the evidence it claims.

The catalogue itself is calibrated against three papers measured this session
(2026-08-17): the fMRI template case, the stain-series case, and the genuine
rotated-enlargement case that must survive adjudication.
"""

from __future__ import annotations

import pytest

pytest.importorskip("metascience_observatory_image_analysis", reason="needs the image analysis package")

import json
from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit.core import prompts
from forensic_metascience_ai_toolkit.agent import (
    _apply_image_adjudication,
    _image_adjudication_prompt,
)


def _result(n_groups: int = 2) -> dict:
    """A detector result shaped like the real thing."""
    return {
        "paper_id": "10.1/x",
        "duplicate_groups": [
            {
                "kind": "transformed_match",
                "tier": 4,
                "duplication_evidence": True,
                "panels": [f"x.pdf:xref{10 + i}", f"x.pdf:xref{20 + i}"],
                "figure_labels": ["Figure 2", "Figure 3"],
                "spans_figures": True,
                "sentence": "Panel B matches panel A under a recovered transform.",
                "placements": {
                    f"x.pdf:xref{10 + i}": [{"page": 3, "figure_label": "Figure 2"}],
                    f"x.pdf:xref{20 + i}": [{"page": 4, "figure_label": "Figure 3"}],
                },
                "match_stats": {
                    "grain_residual_r": 0.61, "same_source": True,
                    "same_registration": False, "coverage_frac": 0.9,
                    "rotation_deg": 179.5, "scale": 1.63, "n_inliers": 171,
                    "overlay_split": {"backdrop_r": 0.65, "overlay_r": 0.22,
                                      "backdrop_shared_overlay_differs": True},
                },
            }
            for i in range(n_groups)
        ],
    }


def _verdict(idx=1, verdict="explained", **kw):
    v = {"group_index": idx, "verdict": verdict,
         "category": "shared_template_backdrop",
         "explanation": "SPM5 renders every group onto one template.",
         "evidence_quote": "", "images_read": ["panels/xref10.png"],
         "figures_reported": [
             {"figure": "Figure 2", "reports": "the saline arm at 6 months",
              "source": "caption"},
             {"figure": "Figure 3", "reports": "the CBE arm at 6 months",
              "source": "caption"}]}
    v.update(kw)
    return v


CAP2 = "Figure 2. Saline-treated cortex stained for GFAP at six months."
CAP3 = "Figure 3. CBE-treated cortex stained for GFAP at six months."
METHODS = ("Sections were immunostained with antibodies against GFAP "
           "(Millipore, 1:1000) and imaged on a confocal microscope.")


def _ctx(captions=("Figure 2", "Figure 3"), methods_located=True,
         mentions=None, tried=("JATS <fig>: 2 captions",)):
    """A `FigureContext.summary()` shaped like the real one."""
    caps = {}
    for key in captions:
        caps[key] = {"caption": CAP2 if key == "Figure 2" else CAP3,
                     "source": "JATS <fig>", "path": "/abs/x.xml", "page": None}
    return {
        "captions": caps,
        "caption_sources_tried": list(tried),
        "mentions": mentions or {},
        "mention_source": "JATS <xref ref-type=fig>",
        "methods": {"text": METHODS, "full_text": METHODS, "note": "",
                    "heading": "Methods", "path": "/abs/x.xml",
                    "located": methods_located,
                    "imaging_sentences": [], "imaging_note": ""},
        "sources": {"publisher XML": "/abs/x.xml"},
        "paper_text_source": "xml_publisher", "paper_text_chars": 1000,
        "gaps": [],
    }


class TestItCanOnlyDowngrade:
    def test_an_explained_group_leaves_the_severity_ladder(self):
        res = _result(1)
        _apply_image_adjudication(res, [_verdict()], {})
        g = res["duplicate_groups"][0]
        assert g["duplication_evidence"] is False
        assert g["adjudication"]["category"] == "shared_template_backdrop"

    def test_unexplained_changes_nothing(self):
        """The detector's verdict stands; the adjudicator only records why it
        could not explain it."""
        res = _result(1)
        _apply_image_adjudication(
            res, [_verdict(verdict="unexplained", category="none")], {})
        g = res["duplicate_groups"][0]
        assert g["duplication_evidence"] is True
        assert g["adjudication"]["verdict"] == "unexplained"

    def test_no_field_it_writes_can_raise_a_severity(self):
        """The applier reads a verdict and nothing else. A response stuffed
        with severities, extra groups and a lifted quarantine must move
        NOTHING except the one flag it is allowed to move."""
        res = _result(1)
        before = json.dumps(res["duplicate_groups"][0]["match_stats"],
                            sort_keys=True)
        _apply_image_adjudication(res, [_verdict(
            verdict="unexplained", category="none",
            severity="impossible", severity_before_quarantine="impossible",
            quarantined=False, duplication_evidence=True,
            match_stats={"grain_residual_r": 0.99},
            kind="fabrication")], {})
        g = res["duplicate_groups"][0]
        assert "severity" not in g and "quarantined" not in g
        assert g["kind"] == "transformed_match"
        assert json.dumps(g["match_stats"], sort_keys=True) == before
        assert g["duplication_evidence"] is True

    def test_it_cannot_invent_a_group(self):
        res = _result(1)
        applied = _apply_image_adjudication(
            res, [_verdict(idx=7), _verdict(idx=0), _verdict(idx="two")], {})
        assert applied == []
        assert len(res["duplicate_groups"]) == 1
        assert "adjudication" not in res["duplicate_groups"][0]


class TestAnExplanationMustCostSomething:
    def test_a_quote_that_is_not_in_the_paper_demotes_the_verdict(self):
        """A fabricated supporting sentence is worse than no explanation:
        it reads as sourced."""
        res = _result(1)
        hay = {"the paper's text": "We used FSL for preprocessing."}
        _apply_image_adjudication(res, [_verdict(
            evidence_quote="Images were rendered onto the SPM5 template.")],
            hay)
        adj = res["duplicate_groups"][0]["adjudication"]
        assert adj["verdict"] == "insufficient_evidence"
        assert "could not be located" in adj["demoted_because"]
        assert res["duplicate_groups"][0]["duplication_evidence"] is True

    def test_a_quote_that_is_in_the_paper_survives(self):
        res = _result(1)
        hay = {"the paper's text":
               "Data were processed with SPM5 and rendered onto the template."}
        _apply_image_adjudication(res, [_verdict(
            evidence_quote="rendered onto the template")], hay)
        adj = res["duplicate_groups"][0]["adjudication"]
        assert adj["verdict"] == "explained"
        assert adj["quote_verified"] in ("verbatim", "elided")
        assert res["duplicate_groups"][0]["duplication_evidence"] is False

    def test_clearing_a_group_without_opening_an_image_is_refused(self):
        """A group adjudicated unseen is not adjudicated."""
        res = _result(1)
        _apply_image_adjudication(res, [_verdict(images_read=[])], {})
        adj = res["duplicate_groups"][0]["adjudication"]
        assert adj["verdict"] == "insufficient_evidence"
        assert "unseen" in adj["demoted_because"]
        assert res["duplicate_groups"][0]["duplication_evidence"] is True


class TestAnOpenedImageMustExist:
    """MEASURED 2026-09-02: 29 of 1,190 `images_read` entries from a codex
    pass named files that do not exist -- a space inserted into a directory
    name, a component dropped -- every one the basename of a real exhibit.
    The guard used to test only that the list was non-empty."""

    def _paper(self, tmp_path):
        d = tmp_path / "10.1--x"
        (d / "panels" / "review").mkdir(parents=True)
        (d / "panels" / "review" / "group01_transformed_match.png").write_bytes(b"png")
        return d

    def test_a_mangled_directory_still_resolves_by_basename(self, tmp_path):
        d = self._paper(tmp_path)
        res = _result()
        mangled = str(d).replace("10.1--x", "10.1 --x") + "/panels/review/group01_transformed_match.png"
        _apply_image_adjudication(res, [_verdict(images_read=[mangled])], {},
                                  paper_dir=d)
        rec = res["duplicate_groups"][0]["adjudication"]
        assert rec["verdict"] == "explained"
        assert rec["images_verified"] == [str(d / "panels" / "review"
                                              / "group01_transformed_match.png")]
        assert "images_unresolved" not in rec

    def test_a_clear_citing_only_nonexistent_images_is_demoted(self, tmp_path):
        d = self._paper(tmp_path)
        res = _result()
        _apply_image_adjudication(
            res, [_verdict(images_read=["/nowhere/group99.png"])], {}, paper_dir=d)
        rec = res["duplicate_groups"][0]["adjudication"]
        assert rec["verdict"] == "insufficient_evidence"
        assert rec["images_verified"] == []
        assert rec["images_unresolved"] == ["/nowhere/group99.png"]
        assert "do not exist on disk" in rec["demoted_because"]
        assert res["duplicate_groups"][0].get("duplication_evidence") is not False

    def test_without_a_paper_dir_the_old_nonempty_test_stands(self):
        res = _result()
        _apply_image_adjudication(
            res, [_verdict(images_read=["/nowhere/group99.png"])], {})
        assert res["duplicate_groups"][0]["adjudication"]["verdict"] == "explained"


class TestAClearMustRestOnText:
    """The caption-first step and the quote-location rule, in code.

    MEASURED 2026-09-02 (Masliah, 198 papers, 760 groups, codex): 188 of 465
    clears carried no quote at all, 129 explanations mentioned a caption and
    12 the Methods -- while the paper-wide haystack could not tell a caption
    from body text (0 quotes ever verified against "a figure caption"), so a
    rule phrased on ITS source names would have been inert. These rules run
    against the per-group haystack the prompt was built from.
    """

    def _apply(self, verdict, ctx=None, res=None):
        res = res or _result(1)
        _apply_image_adjudication(res, [verdict], {}, figure_context=ctx or _ctx())
        return res["duplicate_groups"][0]["adjudication"]

    # --- the caption-first step ---------------------------------------
    def test_a_clear_without_figures_reported_is_demoted(self):
        rec = self._apply(_verdict(figures_reported=[]))
        assert rec["verdict"] == "insufficient_evidence"
        assert "without saying what each figure reports" in rec["demoted_because"]

    def test_all_none_found_while_a_caption_was_supplied_is_demoted(self):
        rec = self._apply(_verdict(figures_reported=[
            {"figure": "Figure 2", "reports": "", "source": "none_found"},
            {"figure": "Figure 3", "reports": "", "source": "none_found"}]))
        assert rec["verdict"] == "insufficient_evidence"
        assert "none_found although the caption of Figure 2 was supplied" \
            in rec["demoted_because"]

    def test_none_found_is_accepted_when_the_bundle_had_no_caption(self):
        """Our gap is not the model's failure: with no caption on the page,
        `none_found` is the honest answer and the pixel category stands."""
        rec = self._apply(_verdict(category="plot_template",
                                   figures_reported=[
                                       {"figure": "Figure 2", "reports": "",
                                        "source": "none_found"}]),
                          ctx=_ctx(captions=()))
        assert rec["verdict"] == "explained"

    # --- the quote must be about THIS figure ---------------------------
    def test_a_text_category_with_no_quote_is_demoted(self):
        rec = self._apply(_verdict(category="same_field_different_channel",
                                   evidence_quote=""))
        assert rec["verdict"] == "insufficient_evidence"
        assert "no sentence from the paper was quoted" in rec["demoted_because"]
        assert rec["quote_context"] == "absent"

    def test_a_quote_in_the_involved_caption_survives(self):
        rec = self._apply(_verdict(category="same_field_different_channel",
                                   evidence_quote="stained for GFAP at six months"))
        assert rec["verdict"] == "explained"
        assert rec["quote_context"] == "the caption of Figure 2"

    def test_a_quote_in_the_methods_survives(self):
        rec = self._apply(_verdict(
            category="same_field_different_channel",
            evidence_quote="imaged on a confocal microscope"))
        assert rec["verdict"] == "explained"
        assert rec["quote_context"] == "the Methods section"

    def test_a_quote_in_a_citing_sentence_survives(self):
        ctx = _ctx(mentions={"Figure 2": [
            {"sentence": "The same field is shown in Figure 2 as a merged image.",
             "section": "Results", "source": "JATS xref", "panels": ""}]})
        rec = self._apply(_verdict(
            category="same_field_different_channel",
            evidence_quote="shown in Figure 2 as a merged image"), ctx=ctx)
        assert rec["verdict"] == "explained"
        assert rec["quote_context"] == "a sentence citing Figure 2"

    def test_a_quote_from_elsewhere_is_recorded_not_demoted(self):
        """MEASURED 2026-09-02: this rule demoted 35 groups, 32 of which had
        every caption -- so the miss read as the model's. It was ours. One
        paper had NO Methods section located, another a 607-character one,
        and both quotes were real protocol sentences. Our extraction cannot
        say a sentence found in the paper is not about this figure."""
        rec = self._apply(_verdict(
            category="same_field_different_channel",
            evidence_quote="Mice were housed under a 12-hour light cycle"))
        assert rec["verdict"] == "explained"
        assert rec["quote_context"] == "elsewhere in the paper"
        assert "not precise enough" in rec["text_basis_note"]

    # --- same_condition is decided by the two captions -----------------
    def test_same_condition_needs_two_figures(self):
        res = _result(1)
        res["duplicate_groups"][0]["figure_labels"] = ["Figure 2"]
        rec = self._apply(_verdict(category="same_condition_in_both_figures",
                                   evidence_quote="stained for GFAP at six months"),
                          res=res)
        assert rec["verdict"] == "insufficient_evidence"
        assert "names one figure (Figure 2)" in rec["demoted_because"]

    def test_same_condition_with_a_methods_quote_is_demoted(self):
        rec = self._apply(_verdict(category="same_condition_in_both_figures",
                                   evidence_quote="imaged on a confocal microscope"))
        assert rec["verdict"] == "insufficient_evidence"
        assert "decided by the two captions and nothing else" in rec["demoted_because"]

    def test_same_condition_with_a_caption_quote_survives(self):
        rec = self._apply(_verdict(category="same_condition_in_both_figures",
                                   evidence_quote="stained for GFAP at six months"))
        assert rec["verdict"] == "explained"

    # --- our own gap, named as ours ------------------------------------
    def test_no_caption_and_no_methods_names_our_gap(self):
        rec = self._apply(_verdict(category="same_field_different_channel",
                                   evidence_quote="anything at all"),
                          ctx=_ctx(captions=(), methods_located=False,
                                   tried=("JATS <fig>: absent",
                                          "figures/figures.json: absent")))
        assert rec["verdict"] == "insufficient_evidence"
        assert "no caption could be read for Figure 2, Figure 3" in rec["demoted_because"]
        assert "figures/figures.json: absent" in rec["demoted_because"]

    def test_a_missing_methods_heading_is_a_named_degradation_not_a_demotion(self):
        rec = self._apply(_verdict(category="same_field_different_channel",
                                   evidence_quote="stained for GFAP at six months"),
                          ctx=_ctx(methods_located=False))
        assert rec["verdict"] == "explained"
        assert rec["quote_context"] == "the caption of Figure 2"

    # --- the pixel categories keep their exemption ---------------------
    def test_a_pixel_category_may_rest_on_the_pixels(self):
        for cat in ("chart_furniture", "plot_template", "publisher_furniture",
                    "producer_tiling"):
            rec = self._apply(_verdict(category=cat, evidence_quote=""))
            assert rec["verdict"] == "explained", cat

    def test_a_backdrop_clear_may_rest_on_the_overlay_split(self):
        rec = self._apply(_verdict(category="shared_template_backdrop",
                                   evidence_quote=""))
        assert rec["verdict"] == "explained"
        assert rec["text_basis_satisfied_by"] == \
            "overlay_split.backdrop_shared_overlay_differs"

    def test_a_backdrop_clear_without_the_split_needs_a_quote(self):
        res = _result(1)
        res["duplicate_groups"][0]["match_stats"]["overlay_split"] = {}
        rec = self._apply(_verdict(category="shared_template_backdrop",
                                   evidence_quote=""), res=res)
        assert rec["verdict"] == "insufficient_evidence"

    # --- an exact contradiction with the detector's own kind -----------
    def test_one_stream_placed_twice_cannot_be_two_channels(self):
        res = _result(1)
        res["duplicate_groups"][0]["kind"] = "same_xref_reused"
        rec = self._apply(_verdict(category="same_field_different_channel",
                                   evidence_quote="stained for GFAP at six months"),
                          res=res)
        assert rec["verdict"] == "insufficient_evidence"
        assert "contradicts the detector's kind same_xref_reused" in rec["demoted_because"]

    # --- the legacy path -----------------------------------------------
    def test_without_a_context_nothing_is_demoted_and_it_says_so(self):
        res = _result(1)
        _apply_image_adjudication(res, [_verdict(
            category="same_field_different_channel", evidence_quote="")], {})
        rec = res["duplicate_groups"][0]["adjudication"]
        assert rec["verdict"] == "explained"
        assert rec["quote_context"] == "unchecked"
        assert rec["text_basis_checked"] is False

    def test_the_haystack_is_normalised_like_build_haystack(self):
        """`classify` normalises the quote and assumes the haystack already
        is; a raw haystack fails every lookup, and a failed lookup DEMOTES --
        so the guard would have demoted every honest clear."""
        from forensic_metascience_ai_toolkit.agent import _context_haystack
        ctx = _ctx()
        ctx["captions"]["Figure 2"]["caption"] = "Saline\u2010treated cortex"  # NB hyphen
        hay, _facts = _context_haystack(ctx, ["Figure 2"])
        # `normalise` folds case as well as typography, so compare folded.
        assert "saline-treated cortex" in hay["the caption of Figure 2"]

    def test_a_figure_the_detector_never_placed_is_recorded_not_demoted(self):
        rec = self._apply(_verdict(figures_reported=[
            {"figure": "Figure 2", "reports": "saline", "source": "caption"},
            {"figure": "Figure 3", "reports": "CBE", "source": "caption"},
            {"figure": "Figure 9", "reports": "invented", "source": "caption"}]))
        assert rec["verdict"] == "explained"
        assert rec["figures_unmatched"] == ["Figure 9"]


class TestTheTextIsPairedToTheGroup:
    """A flat caption list for the whole paper made the judge find the right
    two captions itself, per group; on a 37-group paper it never did.
    MEASURED 2026-09-02: 129 of 760 explanations mentioned a caption at all.
    """

    def _ctx_obj(self, tmp_path, n_groups=2):
        """A real FigureContext over a real XML, not a stub."""
        from metascience_observatory_image_analysis.image_forensics.figure_context import (
            build_figure_context)
        (tmp_path / "p.xml").write_text(
            '<article><body>'
            '<sec><title>Methods</title><p>Sections were stained for GFAP '
            'and imaged as shown in <xref ref-type="fig" rid="F2">Figure 2</xref>.'
            '</p></sec>'
            # a section AFTER Methods, or the Methods window runs to the end
            # of the document and prints the captions a second time
            '<sec><title>Results</title><p>Spine density rose.</p></sec>'
            '<fig id="F2"><label>Figure 2</label><caption><p>'
            + " ".join(f"Saline cortex panel {n} of the series." for n in range(40))
            + '</p></caption></fig>'
            '<fig id="F3"><label>Figure 3</label><caption><p>'
            'CBE cortex at six months.</p></caption></fig>'
            '</body></article>', encoding="utf-8")
        return build_figure_context(tmp_path, {"Figure 2", "Figure 3"})

    def test_each_groups_captions_sit_inside_that_groups_block(self, tmp_path):
        ctx = self._ctx_obj(tmp_path)
        prompt = _image_adjudication_prompt(_result(2), tmp_path, {}, "",
                                            context_obj=ctx)
        blocks = prompt.split("## Group ")
        assert len(blocks) >= 3
        assert "Figure 2 -- caption" in blocks[1]
        assert "Figure 3 -- caption" in blocks[1]

    def test_a_caption_already_shown_points_back_instead_of_repeating(self, tmp_path):
        ctx = self._ctx_obj(tmp_path)
        prompt = _image_adjudication_prompt(_result(2), tmp_path, {}, "",
                                            context_obj=ctx)
        # a span that appears ONCE inside the caption, so a second printing
        # of the caption is the only way to see it twice
        body = "panel 30 of the series"
        assert ctx.captions["Figure 2"].caption.count(body) == 1
        assert prompt.count(body) == 1, "the full caption was printed twice"
        assert "at Group 1" in prompt.split("## Group ")[2]

    def test_the_per_paper_cap_announces_itself(self, tmp_path, monkeypatch):
        from metascience_observatory_image_analysis.image_forensics import figure_context as fc
        monkeypatch.setattr(fc, "CONTEXT_CHARS_PER_PAPER", 10)
        ctx = self._ctx_obj(tmp_path)
        prompt = _image_adjudication_prompt(_result(3), tmp_path, {}, "",
                                            context_obj=ctx)
        assert "context abbreviated for Group" in prompt
        assert "Read " in prompt.split("context abbreviated for Group")[1][:200]

    def test_a_missing_caption_is_named_with_the_sources_tried(self, tmp_path):
        from metascience_observatory_image_analysis.image_forensics.figure_context import (
            build_figure_context)
        ctx = build_figure_context(tmp_path, {"Figure 2", "Figure 3"})
        prompt = _image_adjudication_prompt(_result(1), tmp_path, {}, "",
                                            context_obj=ctx)
        assert "NOT FOUND" in prompt
        assert "sources tried" in prompt

    def test_the_legacy_flat_list_still_renders_without_a_context(self, tmp_path):
        prompt = _image_adjudication_prompt(
            _result(1), tmp_path, {"Figure 2": "Confocal images."}, "Methods.")
        assert "## Figure captions" in prompt
        assert "Confocal images." in prompt


class TestEveryCallerPassesTheContext:
    """The rules are inert unless the production callers hand the applier the
    context the prompt was built from -- the shape of LESSONS #3."""

    def test_the_single_paper_path_passes_it(self, tmp_path, monkeypatch):
        import asyncio
        from forensic_metascience_ai_toolkit.agent import adjudicate_retained_findings
        seen = {}
        paper = tmp_path / "10.1--x"
        (paper / "panels").mkdir(parents=True)
        (paper / "panels" / "xref10.png").write_bytes(b"png")
        (paper / "image_duplication_findings.json").write_text(json.dumps(_result(1)))

        async def fake_stage(*_a, **_k):
            return {"adjudication": {"verdicts": [_verdict()]}, "cost_usd": 0.0,
                    "figure_context": {"captions": {}, "methods": {"located": False}}}

        real = _apply_image_adjudication

        def spy(*a, **kw):
            seen["figure_context"] = kw.get("figure_context")
            return real(*a, **kw)

        monkeypatch.setattr("metascience_observatory_image_analysis.legacy_adjudication._run_image_adjudication",
                            fake_stage)
        monkeypatch.setattr("metascience_observatory_image_analysis.legacy_adjudication._apply_image_adjudication", spy)
        asyncio.run(adjudicate_retained_findings(paper, model="sonnet",
                                                 render_media=False))
        assert isinstance(seen["figure_context"], dict)

    def test_the_corpus_driver_passes_it(self, tmp_path, monkeypatch):
        import asyncio
        from metascience_observatory_image_analysis.image_forensics import adjudicate as ADJ
        seen = {}
        paper = tmp_path / "10.1--x"
        (paper / "panels").mkdir(parents=True)
        (paper / "image_duplication_findings.json").write_text(json.dumps(_result(1)))

        async def fake_stage(*_a, **_k):
            return {"adjudication": {"verdicts": [_verdict()]}, "cost_usd": 0.0,
                    "figure_context": {"captions": {}, "methods": {"located": False}}}

        real = _apply_image_adjudication

        def spy(*a, **kw):
            seen["figure_context"] = kw.get("figure_context")
            return real(*a, **kw)

        monkeypatch.setattr("metascience_observatory_image_analysis.legacy_adjudication._run_image_adjudication",
                            fake_stage)
        monkeypatch.setattr("metascience_observatory_image_analysis.legacy_adjudication._apply_image_adjudication", spy)
        asyncio.run(ADJ.judge_once(paper, json.loads(
            (paper / "image_duplication_findings.json").read_text()),
            backend="claude", model="sonnet"))
        assert isinstance(seen["figure_context"], dict)


class TestTheFigureAsPrinted:
    """The judge is shown the whole figure, so a caption's "(F, left)" can be
    paired with our `xref117-seg8`. And a PMC render's PNG lives at
    `panels/pmc/pmc_<file>.png`, which the composed `panels/<pid>.png` path
    missed -- 11 XML-only groups came back `insufficient_evidence` saying the
    images could not be opened (measured 2026-09-02)."""

    def test_the_whole_figure_crop_is_named(self, tmp_path):
        (tmp_path / "figures").mkdir()
        crop = tmp_path / "figures" / "Figure_2_p004.png"
        crop.write_bytes(b"png")
        (tmp_path / "figures" / "figures.json").write_text(json.dumps(
            {"figures": [{"label": "Figure 2", "page": 4, "caption": CAP2,
                          "image_path": str(crop), "crop_confidence": "high"}]}))
        prompt = _image_adjudication_prompt(_result(1), tmp_path, {}, "")
        assert f"figure as printed: Figure 2 (crop_confidence high): {crop}" in prompt
        assert "figure as printed: Figure 3: NOT AVAILABLE" in prompt

    def test_a_pmc_render_panel_is_shown_from_the_panel_index(self, tmp_path):
        pdir = tmp_path / "panels" / "pmc"
        pdir.mkdir(parents=True)
        png = pdir / "pmc_nihms1f1.jpg.png"
        png.write_bytes(b"png")
        (tmp_path / "panels" / "panel_index.json").write_text(json.dumps(
            {"panels": [{"uid": "pmc_figures:pmc:nihms1f1.jpg",
                         "image_path": str(png)}]}))
        res = _result(1)
        res["duplicate_groups"][0]["panels"] = ["pmc_figures:pmc:nihms1f1.jpg"]
        prompt = _image_adjudication_prompt(res, tmp_path, {}, "")
        assert f"image: {png}" in prompt
        assert "NOT AVAILABLE" not in prompt.split("- figures involved")[0]


class TestTheEvidenceBundle:
    def test_it_names_the_images_the_measurements_and_the_paper(self, tmp_path):
        prompt = _image_adjudication_prompt(
            _result(1), tmp_path, {"Figure 2": "Confocal images of cells."},
            "Methods. Data were processed with SPM5.")
        # The panels, named, so `Read` can reach them -- and when the PNG is
        # not on disk (as here) the prompt says NOT AVAILABLE rather than
        # printing a path that would fail to open. A panel silently omitted
        # is a panel judged unseen.
        assert "xref10" in prompt
        assert "NOT AVAILABLE" in prompt
        # the discriminating measurements, not just the verdict
        for key in ("grain_residual_r", "same_registration", "coverage_frac",
                    "backdrop_r", "overlay_r"):
            assert key in prompt
        # where the panels sit, the caption, and the paper's own words
        assert "Figure 2" in prompt and "page 3" in prompt
        assert "Confocal images of cells." in prompt
        assert "SPM5" in prompt

    def test_groups_already_explained_are_not_re_adjudicated(self, tmp_path):
        res = _result(2)
        res["duplicate_groups"][0]["duplication_evidence"] = False
        prompt = _image_adjudication_prompt(res, tmp_path, {}, "")
        assert "fired 1 group(s)" in prompt


class TestThePromptCarriesItsGuards:
    """These sentences are the difference between an adjudicator and a second
    opinion that can accuse."""

    def _prompt(self):
        return prompts.image_adjudication_system_prompt()

    def test_it_states_the_downgrade_only_rule(self):
        assert "only DOWNGRADE" in self._prompt()

    def test_it_refuses_to_read_absence_as_guilt(self):
        p = self._prompt()
        assert "Absence of an innocuous explanation is NOT evidence" in p

    def test_it_requires_saying_so_when_the_images_could_not_be_read(self):
        assert "could not open the images" in self._prompt()

    def test_an_undisclosed_magnification_is_not_explained(self):
        """The exact case that survived adjudication on the 1999 paper."""
        p = " ".join(self._prompt().split())      # the sentence wraps
        assert "Without such a statement this is NOT explained" in p
        assert "undisclosed magnified crop presented as a separate field" in p

    def test_the_catalogue_covers_the_measured_cases(self):
        p = self._prompt()
        for category in ("shared_template_backdrop",
                         "same_condition_in_both_figures",
                         "same_field_different_channel",
                         "overview_and_detail",
                         "stated_representative_image",
                         "publisher_furniture",
                         "chart_furniture"):
            assert category in p

    def test_every_catalogue_category_is_in_the_schema_enum(self):
        """The schema is enforced with --json-schema, so a category the prompt
        offers and the enum omits is a HARD rejection of the whole response --
        not a soft fallback. The two must not drift."""
        import json
        from forensic_metascience_ai_toolkit.core import prompts
        enum = (prompts.image_adjudication_schema()["properties"]["verdicts"]
                ["items"]["properties"]["category"]["enum"])
        p = self._prompt()
        for category in enum:
            if category == "none":
                continue
            assert category in p, (
                f"{category} is in the schema enum but the prompt never names "
                "it, so the model cannot know when to use it")

    def test_the_adjudicator_is_told_to_compare_the_two_captions(self):
        """Dan, on the review queue: the adjudicator "needs to be able to read
        figure captions to understand when two figures show same condition /
        same thing, and its inoculous".

        The catalogue used to be one-directional. It said what made a shared
        panel damning -- "presented as different conditions" -- and never what
        made one ordinary, so on a cross-figure match the cheapest correct
        answer was `unexplained`."""
        p = " ".join(self._prompt().split())
        assert "same condition" in p.lower()
        assert "is expected and is not a finding" in p
        # ...and the rule must not become a skeleton key.
        assert "does not survive an undisclosed transform" in p.lower() or \
               "undisclosed transform" in p.lower()

    def test_it_carries_no_severity_vocabulary(self):
        """It issues no severity, so it is never shown the ladder -- that
        would be an invitation to reach for a verdict it must not reach for."""
        p = self._prompt()
        for word in ("highly_suspicious", "impossible"):
            assert word not in p

    def test_it_asks_for_figures_reported_as_an_output(self):
        p = self._prompt()
        assert "figures_reported" in p
        assert "This is an OUTPUT, not a note to yourself" in p
        assert "demoted in code" in p

    def test_it_names_which_categories_must_quote_the_paper(self):
        p = self._prompt()
        for cat in ("same_condition_in_both_figures", "same_field_different_channel",
                    "stated_representative_image", "overview_and_detail",
                    "paired_design", "shared_template_backdrop"):
            assert cat in p
        assert "the caption of a figure in this group, a sentence citing" in p
        assert "Four of them are reasons you can see" in p

    def test_same_condition_is_told_it_needs_two_captions(self):
        p = " ".join(self._prompt().split())   # the markdown wraps the line
        assert "decided by the two captions and nothing else" in p
        assert "a group naming one figure cannot use this category at all" in p

    def test_the_schema_requires_figures_reported(self):
        item = prompts.image_adjudication_schema()[
            "properties"]["verdicts"]["items"]
        assert "figures_reported" in item["required"]
        fr = item["properties"]["figures_reported"]["items"]
        assert fr["required"] == ["figure", "reports", "source"]
        assert fr["properties"]["source"]["enum"] == ["caption", "in_text", "none_found"]
        # every enum carries an explicit type: the codex strict dialect
        # rejects a bare one, and the stage dies with an EMPTY stderr.
        assert fr["properties"]["source"]["type"] == "string"

    def test_furniture_inside_a_figure_has_its_own_category(self):
        """MEASURED 2026-08-17: Sonnet correctly explained a legend key
        reused across the panels of one figure, but had to file it under
        `publisher_furniture`, whose own definition says "not inside a
        captioned figure". A category the model must contradict to use is a
        category that will eventually be used wrongly."""
        p = " ".join(prompts.image_adjudication_system_prompt().split())
        assert "chart_furniture" in p
        assert "sits INSIDE a captioned figure" in p
        assert "chart_furniture" in prompts.image_adjudication_schema()[
            "properties"]["verdicts"]["items"]["properties"]["category"]["enum"]

    def test_the_schema_forbids_a_severity_field(self):
        schema = prompts.image_adjudication_schema()
        item = schema["properties"]["verdicts"]["items"]
        assert item["additionalProperties"] is False
        assert "severity" not in item["properties"]
        assert item["properties"]["verdict"]["enum"] == [
            "explained", "unexplained", "insufficient_evidence"]


class TestASubPanelCanActuallyBeSeen:
    """A montage sub-panel has no PNG of its own -- the segmentation contract
    is "re-croppable from the parent's saved PNG", and nothing wrote it out.

    MEASURED 2026-08-17 on the Masliah corpus: 1,744 of 1,744 segment image
    paths printed into adjudication prompts pointed at files that did not
    exist, i.e. ALL of them. A model told to open those correctly answers
    `insufficient_evidence` every time, so the entire segmented run was
    unreviewable while looking reviewable -- and would have cost ~$83 to be
    told so 1,346 times.
    """

    def _paper(self, tmp_path):
        """A parent panel PNG plus an index describing one crop of it."""
        import numpy as np
        cv2 = pytest.importorskip("cv2")
        panels = tmp_path / "panels"
        panels.mkdir(parents=True)
        rng = np.random.default_rng(3)
        parent = rng.integers(0, 256, size=(200, 300, 3), dtype=np.uint8)
        cv2.imwrite(str(panels / "xref9.png"), parent)
        (panels / "panel_index.json").write_text(json.dumps({
            "paper_id": "p", "panels": [
                {"uid": "d:xref9", "panel_id": "xref9", "image_path":
                    str(panels / "xref9.png"), "crop_box": None,
                 "parent_panel_id": None},
                {"uid": "d:xref9-seg1", "panel_id": "xref9-seg1",
                 "image_path": "", "crop_box": [10, 20, 110, 160],
                 "parent_panel_id": "xref9"},
            ]}))
        return tmp_path

    def test_a_crop_is_written_from_its_parent(self, tmp_path):
        import cv2
        from metascience_observatory_image_analysis.image_forensics.image_analysis import materialise_crops
        paper = self._paper(tmp_path)
        out = materialise_crops(paper, ["d:xref9-seg1"])
        assert out["failed"] == []
        written = paper / "panels" / "xref9-seg1.png"
        assert written.exists()
        img = cv2.imread(str(written))
        assert img.shape[:2] == (100, 140)      # the crop_box region

    def test_the_prompt_points_at_a_file_that_exists(self, tmp_path):
        paper = self._paper(tmp_path)
        res = {"paper_id": "p", "duplicate_groups": [{
            "kind": "transformed_match", "duplication_evidence": True,
            "panels": ["d:xref9-seg1", "d:xref9"], "placements": {},
            "sentence": "s", "match_stats": {"n_inliers": 99}}]}
        prompt = _image_adjudication_prompt(res, paper, {}, "")
        for line in prompt.splitlines():
            if line.strip().startswith("image:"):
                path = line.split("image:", 1)[1].strip()
                assert path.startswith("NOT AVAILABLE") or Path(path).exists()
        assert "xref9-seg1.png" in prompt

    def test_a_crop_that_cannot_be_written_is_NAMED_not_omitted(self,
                                                                tmp_path):
        """"There is no image here" and "we could not produce the image" are
        different facts, and only the second is our fault. A reviewer told the
        first will judge a panel it never saw."""
        panels = tmp_path / "panels"
        panels.mkdir(parents=True)
        (panels / "panel_index.json").write_text(json.dumps({
            "paper_id": "p", "panels": [
                {"uid": "d:xref9-seg1", "panel_id": "xref9-seg1",
                 "image_path": "", "crop_box": [0, 0, 50, 50],
                 "parent_panel_id": "xref9"}]}))   # parent PNG absent
        res = {"paper_id": "p", "duplicate_groups": [{
            "kind": "transformed_match", "duplication_evidence": True,
            "panels": ["d:xref9-seg1"], "placements": {}, "sentence": "s",
            "match_stats": {}}]}
        prompt = _image_adjudication_prompt(res, tmp_path, {}, "")
        assert "NOT AVAILABLE" in prompt
        assert "could not be read" in prompt
        assert "only from the measurements" in prompt

    def test_an_unreadable_index_refuses_by_name(self, tmp_path):
        from metascience_observatory_image_analysis.image_forensics.image_analysis import materialise_crops
        out = materialise_crops(tmp_path)
        assert out["written"] == []
        assert "could not be read" in out["failed"][0]["reason"]


class TestAdjudicateRetainedFindings:
    def test_missing_file_is_skipped(self, tmp_path):
        import asyncio
        from forensic_metascience_ai_toolkit.agent import adjudicate_retained_findings
        out = asyncio.run(adjudicate_retained_findings(
            tmp_path / "nope", model="sonnet", render_media=False))
        assert out["skipped"] == "no_retained_findings"

    def test_explained_verdict_is_written_back(self, tmp_path, monkeypatch):
        import asyncio
        from forensic_metascience_ai_toolkit.agent import adjudicate_retained_findings
        paper = tmp_path / "10.1--x"
        paper.mkdir()
        payload = _result(1)
        (paper / "image_duplication_findings.json").write_text(
            json.dumps(payload))
        # The verdict claims to have opened panels/xref10.png; a clear
        # citing a file that does not exist is demoted, so it must exist.
        (paper / "panels").mkdir()
        (paper / "panels" / "xref10.png").write_bytes(b"png")

        async def fake_stage(*_a, **_k):
            return {
                "adjudication": {"verdicts": [_verdict()]},
                "cost_usd": 0.12,
            }

        monkeypatch.setattr(
            "metascience_observatory_image_analysis.legacy_adjudication._run_image_adjudication", fake_stage)
        out = asyncio.run(adjudicate_retained_findings(
            paper, model="sonnet", render_media=False))
        saved = json.loads(
            (paper / "image_duplication_findings.json").read_text())
        assert saved["duplicate_groups"][0]["duplication_evidence"] is False
        assert saved["n_duplicate_groups"] == 0
        assert out["n_groups_explained"] == 1
        assert out["backend"] == "claude"


class TestGrokAdjudicationCommand:
    def test_grok_adjudicator_is_read_only(self, tmp_path, monkeypatch):
        monkeypatch.setenv("METASCIENCE_GROK_SANDBOX_ROOT", str(tmp_path / "sb"))
        monkeypatch.setenv("METASCIENCE_GROK_SKIP_FOLDER_TRUST", "1")
        from forensic_metascience_ai_toolkit.agent import BUILTIN_TOOLS, _build_claude_cmd
        paper = tmp_path / "p"
        paper.mkdir()
        inv = _build_claude_cmd(
            system_prompt="s",
            allowed_tools=list(BUILTIN_TOOLS),
            model="grok-4.6",
            backend="grok",
            json_schema={"type": "object"},
            paper_dir=paper,
        )
        try:
            assert inv.argv[0] == "grok"
            assert inv.backend.name == "grok"
            tools = inv.argv[inv.argv.index("--tools") + 1]
            assert tools == "read_file"
            denied = inv.argv[inv.argv.index("--disallowed-tools") + 1]
            assert "run_terminal_cmd" in denied
            denies = [inv.argv[i + 1] for i, x in enumerate(inv.argv)
                      if x == "--deny"]
            assert denies, "forensic MCP tools must be denied for adjudication"
            assert all(d.startswith("MCPTool(forensic_metascience__")
                       for d in denies)
        finally:
            inv.cleanup()
