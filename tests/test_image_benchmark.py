"""`metascience image-benchmark` / `image-labels`: scoring a retained sweep
against PubPeer labels, with a known positive the scorer MUST find
(LESSONS.md #4: a guard that cannot fail is worse than none).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

fitz = pytest.importorskip("fitz")
cv2 = pytest.importorskip("cv2")

from metascience_observatory_image_analysis.image_forensics import benchmark as B  # noqa: E402
from metascience_observatory_image_analysis.image_forensics import labels as L  # noqa: E402
from metascience_observatory_image_analysis.image_forensics import retain as R  # noqa: E402
from metascience_observatory_image_analysis.image_forensics import sweep as S  # noqa: E402

SRC = Path(__file__).resolve().parent.parent / "src" / "forensic_metascience_ai_toolkit"



IMAGE_SRC = __import__("pathlib").Path(__import__("metascience_observatory_image_analysis").__file__).parent
def _texture(seed: int, w: int = 256, h: int = 192) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return cv2.GaussianBlur(rng.integers(0, 256, (h, w), dtype=np.uint8), (0, 0), 1.2)


def _png(gray: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", gray)
    assert ok
    return buf.tobytes()


def _two_fig_pdf(d: Path) -> None:
    png = _png(_texture(1))
    doc = fitz.open()
    for cap in ("Figure 1. Confocal images of treated cells.",
                "Figure 2. Confocal images of control cells."):
        page = doc.new_page(width=612, height=792)
        page.insert_text((72, 80), cap, fontsize=10)
        pix = fitz.Pixmap(png)
        page.insert_image(fitz.Rect(72, 100, 72 + pix.width, 100 + pix.height), stream=png)
    doc.save(d / f"{d.name}.pdf")
    doc.close()


def _label(doi, paper_dir, figures, positive=True, **extra):
    return {"doi": doi, "paper_dir": paper_dir, "in_corpus": paper_dir is not None,
            "url": f"https://pubpeer.com/publications/{doi}", "title": doi,
            "total_comments": 1, "users": "Elisabeth M Bik", "n_comments_parsed": 1,
            "comment_images": [], "is_image_integrity": positive,
            "figures": figures, "n_comments_matched": 1 if positive else 0,
            "comment_ids": [1] if positive else [], "n_comment_images": 0, **extra}


@pytest.fixture
def swept(tmp_path):
    root = tmp_path / "corpus"
    a = root / "10.1--a"
    a.mkdir(parents=True)
    _two_fig_pdf(a)
    (a / "metadata.json").write_text(json.dumps({"doi": "10.1/a", "title": "A"}))
    b = root / "10.1--b"
    b.mkdir()
    (b / "metadata.json").write_text("{}")
    S.run_sweep(root, jobs=2, progress=False, log=lambda s: None,
                sweep_id="t1", furniture_pass=False)
    labels = {
        "corpus": str(root), "n_papers": 2, "n_with_pubpeer_entry": 4,
        "n_image_integrity": 4, "n_unknown": 1, "unknown_dois": ["10.1/u"],
        "lookup_refusals": [], "caveat": L.CAVEAT,
        "labels": {
            "10.1/a": _label("10.1/a", "10.1--a", ["Figure 1"],
                             figure_kinds={"Figure 1": "micrograph"},
                             figure_kinds_source="heuristic"),
            "10.1/b": _label("10.1/b", "10.1--b", ["Figure 3"]),
            "10.1/c": _label("10.1/c", "10.1--c", ["Figure 2B"]),
            "10.1/d": _label("10.1/d", None, []),
            "10.1/e": _label("10.1/e", "10.1--a", [], positive=False),
        },
    }
    lp = root / "labels.json"
    lp.write_text(json.dumps(labels))
    return root, lp



class TestTheScorecardSaysWhatAClearRestedOn:
    """v1.17.0 records `quote_context`, `figures_reported` and
    `demoted_because` on every verdict; the scorecard must READ them, or the
    fields are written by us and consumed by nobody (LESSONS #3). A verdict
    written before that has none of them, and absent must read
    `not recorded` -- never zero, which would report old clears as unquoted
    ones (LESSONS #1)."""

    ADJ = {
        "papers_adjudicated": 1, "models": {"codex:gpt-5.6-luna": 2},
        "by_model_set": {"codex:gpt-5.6-luna": {
            "papers": 1, "groups": 2, "cleared": 1, "clear_rate": 0.5,
            "papers_fully_cleared": 0}},
        "groups_cleared": 1, "groups_standing": 1,
        "positives_fully_cleared": 0, "positives_fully_cleared_papers": [],
        "positives_fired_pre": 1, "note": "n",
        "text_basis": {
            "same_field_different_channel": {"the caption of Figure 2": 1,
                                             "elsewhere in the paper": 1},
            "plot_template": {"not recorded": 1}},
        "demotions": {"the quote is in the paper but not in the caption": 1},
        "figures_reported_source": {"caption": 3, "not recorded": 1},
    }

    def test_the_markdown_prints_the_basis_the_sources_and_the_demotions(self, swept):
        root, lp = swept
        card = dict(B.score(root, lp), adjudication=self.ADJ)
        md = B.render_markdown(card)
        assert "### What each verdict rested on" in md
        assert "| same_field_different_channel | the caption of Figure 2 | 1 |" in md
        assert "| plot_template | not recorded | 1 |" in md
        assert "caption 3" in md and "not recorded 1" in md
        assert "### Demoted, and why" in md
        assert "not in the caption" in md

    def test_a_scorecard_without_the_fields_still_renders(self, swept):
        """Every consumer tolerates a corpus adjudicated before v1.17.0."""
        root, lp = swept
        old = {k: v for k, v in self.ADJ.items()
               if k not in ("text_basis", "demotions", "figures_reported_source")}
        md = B.render_markdown(dict(B.score(root, lp), adjudication=old))
        assert "## Adjudicator audit" in md
        assert "### What each verdict rested on" not in md

    def test_a_legacy_verdict_is_counted_as_not_recorded(self, swept):
        """The scorer itself, not a hand-built card: a group adjudicated
        before the fields existed must land in `not recorded`."""
        root, lp = swept
        res_path = root / "10.1--a" / "image_duplication_findings.json"
        res = json.loads(res_path.read_text())
        for g in res.get("duplicate_groups") or []:
            g["adjudication"] = {"verdict": "explained", "category": "plot_template",
                                 "explanation": "x", "images_read": ["a.png"]}
            g["duplication_evidence"] = False
        res_path.write_text(json.dumps(res))
        card = B.score(root, lp)
        basis = (card.get("adjudication") or {}).get("text_basis") or {}
        assert basis.get("plot_template", {}).get("not recorded")
        assert (card["adjudication"]["figures_reported_source"]
                .get("not recorded"))


class TestAKnownPositiveIsFound:
    def test_attribution_buckets_and_both_denominators(self, swept):
        root, lp = swept
        card = B.score(root, lp)
        assert card["miss_attribution"] == {
            "hit": 1, "not_in_corpus": 2, "refused:no_pdf": 1}
        assert sum(card["miss_attribution"].values()) == card["populations"]["positives"] == 4
        rf = card["recall"]["figure_level_PRIMARY"]
        assert (rf["numerator"], rf["denominator_examined_named"],
                rf["denominator_all_named"]) == (1, 1, 3)
        rp = card["recall"]["paper_level"]
        assert (rp["numerator"], rp["denominator_examined"], rp["denominator_all"]) == (1, 1, 4)
        assert card["populations"]["unknown_pubpeer_status"] == 1
        assert card["fire_rate"]["ran"] == 1 and card["fire_rate"]["fired"] == 1
        assert card["fire_rate"]["any_alarm"] is False, "1 paper is not a rate"
        assert card["recall_by_kind"]["micrograph"]["numerator"] == 1
        assert card["recall_by_kind"]["kind_source_counts"] == {"heuristic": 1, "none": 2}
        assert card["undiscussed_fired"]["count"] == 0
        assert card["mixed_stamps"] is False and card["sweep_ids_seen"] == ["t1"]
        assert card["detector"]["fingerprint"] == R.detector_fingerprint()

    def test_the_rendered_sentence_and_the_pinned_keys(self, swept, tmp_path):
        root, lp = swept
        card = B.score(root, lp, sweep_id="t1")
        assert set(card) == set(B.SCORECARD_KEYS)
        md = B.render_markdown(card)
        assert "1 of 1 examined positives with a named figure = 100.0%" in md
        assert "of ALL 3 positives with a named figure = 33.3%" in md
        assert "| refused:no_pdf | 1 |" in md
        paths = B.write_scorecard(card, tmp_path / "out")
        assert paths["json"].exists() and paths["md"].exists()
        assert paths["dated"].name.endswith("_t1.json")
        assert "T" in paths["dated"].name and "Z_" in paths["dated"].name, (
            "the dated copy must carry the time, or two runs on one day overwrite")
        assert json.loads(paths["json"].read_text())["sweep_id"] == "t1"

    def test_an_unknown_sweep_id_makes_every_paper_not_run_this_sweep(self, swept):
        root, lp = swept
        card = B.score(root, lp, sweep_id="other")
        assert card["miss_attribution"] == {"not_in_corpus": 2, "not_run_this_sweep": 2}
        assert card["populations"]["stamp_mismatch"] == 2

    def test_a_resumed_sweep_owns_the_answers_it_skipped(self, swept):
        """Sweep t2 ran nothing (everything was done under t1). Its stamp is
        equivalent, so scoring by t2 must score every paper -- the earlier
        id on disk is resume working, not a different answer."""
        root, lp = swept
        s2 = S.run_sweep(root, jobs=2, progress=False, log=lambda s: None,
                         sweep_id="t2", furniture_pass=False)
        assert s2["n_rows"] == 0
        assert sorted(s2["selection"]["skipped_done_papers"]) == ["10.1--a", "10.1--b"]
        card = B.score(root, lp, sweep_id="t2")
        assert card["miss_attribution"] == {"hit": 1, "not_in_corpus": 2,
                                            "refused:no_pdf": 1}
        assert card["mixed_stamps"] is False
        # and a sweep with DIFFERENT flags is not equivalent
        S.run_sweep(root, jobs=2, progress=False, log=lambda s: None,
                    sweep_id="t3", furniture_pass=False, max_panels=50)
        card = B.score(root, lp, sweep_id="t1")
        assert card["populations"]["stamp_mismatch"] == 2

    def test_an_alleged_figure_whose_panels_were_all_excluded_is_named(self, swept):
        root, lp = swept
        rows = B.load_retained(root)
        row = rows["10.1--a"]
        # Pretend every panel under Figure 1 was withheld as a blot and
        # nothing fired: the bucket must say so, not "no fire".
        res = row["result"]
        res["duplicate_groups"] = []
        idx = json.loads((root / "10.1--a" / "panels" / "panel_index.json").read_text())
        res["excluded"] = [{"panel": p["uid"], "reason":
                            "low_texture_blot_channel_uncalibrated"}
                           for p in idx["panels"]]
        row["groups"] = []
        rec = json.loads(lp.read_text())["labels"]["10.1/a"]
        assert B.attribute(rec, row, True) == \
            "alleged_figure_panels_excluded:low_texture_blot_channel_uncalibrated"
        rec2 = dict(rec, figures=["Figure 9"])
        assert B.attribute(rec2, row, True) == "alleged_figure_not_harvested"


class TestTheImgdupJoin:
    def test_ids_follow_the_row_builder_not_the_group_list(self, swept):
        """The old scorer numbered ALL groups; a context group first shifted
        every human label onto the wrong group."""
        root, lp = swept
        row = B.load_retained(root)["10.1--a"]
        groups = row["result"]["duplicate_groups"]
        assert groups
        context = dict(groups[0], duplication_evidence=False, kind="chart_furniture")
        row["result"]["duplicate_groups"] = [context] + groups
        row["groups"] = row["result"]["duplicate_groups"]
        ids = B.imgdup_ids(row)
        assert 0 not in ids
        assert ids[1] == "IMGDUP-1"

    def test_precision_reads_workbench_decisions(self, swept):
        from forensic_metascience_ai_toolkit.review_io import write_review
        root, lp = swept
        # An UNSCOPED (legacy) label must be counted and NOT joined ...
        write_review(root / "10.1--a",
                     {"issues": {"image:IMGDUP-1": {"decision": "false_positive_other"}}})
        card = B.score(root, lp, reviews=True)
        pr = card["precision"]
        assert pr["labelled_groups"] == 0
        assert pr["unscoped_legacy_labels"] == 1
        assert pr["precision"] is None
        # ... while one scoped to the image sweep's own run joins.
        write_review(root / "10.1--a",
                     {"run": R.V2_DIRNAME,
                      "issues": {"image:IMGDUP-1": {"decision": "true_issue"}}})
        card = B.score(root, lp, reviews=True)
        pr = card["precision"]
        assert pr["labelled_groups"] == 1 and pr["true_issue"] == 1
        assert pr["precision"] == 1.0
        assert pr["unscoped_legacy_labels"] == 1
        md = B.render_markdown(card)
        assert "true issue" in md and "NOT joined: 1" in md


class TestAnUnfamiliarKindIsReportedNotFatal:
    def test_a_kind_outside_the_vocabulary_lands_in_the_table(self, swept):
        """The first real review pass used `autoradiograph` and the scorer
        died with a KeyError -- a crash where a row was wanted."""
        root, lp = swept
        d = root / "review"
        d.mkdir(exist_ok=True)
        (d / "10.1--a.json").write_text(json.dumps({
            "doi": "10.1/a", "paper_dir": "10.1--a", "reviewer": "t",
            "figures": {"Figure 1": {"kind": "autoradiograph",
                                     "mechanism": "cross_panel_within_paper",
                                     "confidence": "high", "note": ""}}}))
        card = B.score(root, lp, image_review=d)
        assert card["recall_by_kind"]["autoradiograph"]["numerator"] == 1
        assert "autoradiograph" in B.render_markdown(card)


class TestScopeFromTheVisualReview:
    """The regex labels cannot say WHAT was alleged, and that decides
    whether a panel-pair detector could ever find it. Measured on the first
    two Masliah positives: of five alleged figures, two were cross-panel
    duplications, two were regions cloned inside ONE panel, and one matched
    a different publication."""

    def _review(self, root, mechanism):
        d = root / "review"
        d.mkdir(exist_ok=True)
        (d / "10.1--a.json").write_text(json.dumps({
            "doi": "10.1/a", "paper_dir": "10.1--a", "reviewer": "test",
            "n_images_read": 1, "n_images_unreadable": 0,
            "figures": {"Figure 1": {"kind": "micrograph",
                                     "mechanism": mechanism,
                                     "detectable_by_panel_pairs": True,
                                     "confidence": "high", "note": "n"}},
            "paper_note": ""}))
        return d

    def test_an_in_scope_positive_counts_in_both_denominators(self, swept):
        root, lp = swept
        card = B.score(root, lp, image_review=self._review(root, "cross_panel_within_paper"))
        sc = card["scope"]
        assert (sc["reviewed"], sc["in_scope"], sc["out_of_scope"]) == (1, 1, 0)
        assert sc["mechanisms"] == {"cross_panel_within_paper": 1}
        r = card["recall"]["paper_level_in_scope"]
        assert (r["numerator"], r["denominator_examined"], r["denominator_all"]) == (1, 1, 1)
        assert "In scope" in B.render_markdown(card)

    def test_an_out_of_scope_miss_is_not_counted_as_a_detector_miss(self, swept):
        root, lp = swept
        # the detector no longer fires, and the allegation is an intra-panel clone
        p = root / "10.1--a" / R.RESULT_NAME
        res = json.loads(p.read_text())
        res["duplicate_groups"] = []
        res["n_duplicate_groups"] = 0
        p.write_text(json.dumps(res))
        card = B.score(root, lp, image_review=self._review(root, "intra_panel_clone"))
        sc = card["scope"]
        assert (sc["in_scope"], sc["out_of_scope"]) == (0, 1)
        assert card["recall"]["paper_level_in_scope"] is None
        assert any(k.startswith("out_of_scope:intra_panel_clone")
                   for k in card["miss_attribution"]), card["miss_attribution"]
        assert card["miss_attribution"].get("examined_no_fire", 0) == 0

    def test_detectability_is_derived_not_trusted(self, swept):
        """A reviewer that ticks detectable on a cross_paper figure is
        overruled: the two must not be able to disagree."""
        root, lp = swept
        d = root / "review"
        d.mkdir(exist_ok=True)
        (d / "10.1--a.json").write_text(json.dumps({
            "doi": "10.1/a", "paper_dir": "10.1--a", "reviewer": "test",
            "figures": {"Figure 1": {"kind": "blot", "mechanism": "cross_paper",
                                     "detectable_by_panel_pairs": True,
                                     "confidence": "low", "note": ""}}}))
        payload = L.load_labels(lp)
        L.apply_review(payload, d)
        rec = payload["labels"]["10.1/a"]
        assert L.figure_mechanism(rec, "Figure 1") == ("cross_paper", False)
        assert L.paper_in_scope(rec) is False
        assert rec["figures_from_text"] == ["Figure 1"]


class TestHumanScreenedLabels:
    """The Berrio 2025 set (2026-09-28) carries what PubPeer never can:
    papers a human screened and did NOT flag. A fire there is an upper bound
    on a false positive, and a positive whose figure the publisher since
    replaced cannot be a miss either way."""

    def _write(self, root, labels):
        lp = root / "berrio_labels.json"
        lp.write_text(json.dumps({
            "corpus": str(root), "n_papers": len(labels), "n_with_pubpeer_entry": 0,
            "n_image_integrity": sum(v["is_image_integrity"] for v in labels.values()),
            "n_unknown": 0, "unknown_dois": [], "lookup_refusals": [],
            "caveat": L.CAVEAT, "labels": labels}))
        return lp

    def test_a_masliah_style_label_set_has_no_negative_block(self, swept):
        root, lp = swept
        card = B.score(root, lp, sweep_id="t1")
        assert card["screened_negatives"] is None
        assert card["recall_by_label_field"] is None
        assert card["populations"]["positives_corrected_in_place"] == 0

    def test_a_fire_on_a_screened_clean_paper_is_counted_as_one(self, swept):
        root, _ = swept
        lp = self._write(root, {
            "10.1/a": _label("10.1/a", "10.1--a", [], positive=False,
                             screened_clean=True, status="screened_clean", split="dev"),
            "10.1/x": _label("10.1/x", None, [], positive=False, screened_clean=True,
                             status="screened_clean", split="holdout",
                             not_obtained_reason="nothing"),
            "10.1/u": _label("10.1/u", "10.1--b", [], positive=False, status="uncertain"),
            "10.1/c": _label("10.1/c", "10.1--c", ["Figure 2"], split="dev",
                             bik_type="II", spreadsheet_blot=True),
        })
        card = B.score(root, lp, sweep_id="t1")
        sn = card["screened_negatives"]
        assert (sn["papers"], sn["examined"], sn["fired"]) == (2, 1, 1)
        assert sn["fire_rate"] == 1.0
        assert sn["not_examined_by_reason"] == {"not_obtained:nothing": 1}
        assert sn["excluded"]["uncertain"] == 1
        assert sn["by_split"]["dev"] == {"papers": 1, "examined": 1, "fired": 1,
                                         "fire_rate": 1.0}
        assert sn["fired_papers"][0]["paper"] == "10.1--a"
        # A screened negative has no PubPeer entry: a fire on it IS undiscussed.
        assert card["undiscussed_fired"]["count"] == 1
        md = B.render_markdown(card)
        assert "1 of 1 examined screened-clean papers fired = 100.0%" in md
        assert "UPPER BOUND" in md

    def test_recall_is_split_by_the_label_fields_present(self, swept):
        root, _ = swept
        lp = self._write(root, {
            "10.1/a": _label("10.1/a", "10.1--a", ["Figure 1"], split="dev",
                             bik_type="II", spreadsheet_blot=False),
            "10.1/b": _label("10.1/b", "10.1--b", ["Figure 3"], split="holdout",
                             bik_type="III", spreadsheet_blot=True),
            "10.1/d": _label("10.1/d", None, [], split="holdout",
                             bik_type="III", spreadsheet_blot=True),
        })
        card = B.score(root, lp, sweep_id="t1")
        rb = card["recall_by_label_field"]
        assert set(rb) == {"split", "bik_type", "spreadsheet_blot"}
        assert rb["split"]["dev"]["paper_hits"] == 1
        assert rb["split"]["dev"]["figure_hits"] == 1
        # b was refused (no PDF) and d was never obtained: in the ALL
        # denominator, never in the examined one.
        assert (rb["bik_type"]["III"]["paper_examined"], rb["bik_type"]["III"]["paper_all"]) == (0, 2)
        assert "## Recall by label field" in B.render_markdown(card)

    def test_a_positive_corrected_in_place_is_not_a_miss_or_a_hit(self, swept):
        root, _ = swept
        p = root / "10.1--a" / R.RESULT_NAME
        res = json.loads(p.read_text())
        res["duplicate_groups"] = []
        res["n_duplicate_groups"] = 0
        p.write_text(json.dumps(res))
        lp = self._write(root, {
            "10.1/a": _label("10.1/a", "10.1--a", ["Figure 1"]),
            "10.1/c": _label("10.1/c", "10.1--c", ["Figure 2"]),
        })
        d = root / "review"
        d.mkdir()
        (d / "10.1--a.json").write_text(json.dumps({
            "doi": "10.1/a", "paper_dir": "10.1--a", "reviewer": "test",
            "figure_state": "corrected",
            "figures": {"Figure 1": {"kind": "blot", "mechanism": "cross_panel_within_paper",
                                     "confidence": "high", "note": ""}}}))
        card = B.score(root, lp, sweep_id="t1", image_review=d)
        assert card["miss_attribution"].get("corrected_in_place") == 1
        assert card["populations"]["positives_corrected_in_place"] == 1
        rp = card["recall"]["paper_level"]
        assert (rp["numerator"], rp["denominator_examined"], rp["denominator_all"]) == (0, 0, 1)

    def test_an_unstated_figure_state_is_unknown_not_original(self, swept):
        root, lp = swept
        d = root / "review"
        d.mkdir()
        (d / "10.1--a.json").write_text(json.dumps({
            "doi": "10.1/a", "paper_dir": "10.1--a", "reviewer": "test",
            "figures": {"Figure 1": {"kind": "blot", "mechanism": "cross_panel_within_paper"}}}))
        payload = L.load_labels(lp)
        L.apply_review(payload, d)
        assert payload["labels"]["10.1/a"]["figure_state"] == "unknown"


class TestAdjudicationAudit:
    def test_a_cleared_positive_is_a_false_clear_candidate(self, swept):
        root, lp = swept
        card0 = B.score(root, lp)
        assert card0["adjudication"] is None
        assert card0["recall"]["paper_level_pre_adjudication"] == card0["recall"]["paper_level"]
        # simulate an adjudicator that explained every group away
        p = root / "10.1--a" / R.RESULT_NAME
        res = json.loads(p.read_text())
        for g in res["duplicate_groups"]:
            if g.get("duplication_evidence") is not False:
                g["adjudication"] = {"verdict": "explained", "category": "x",
                                     "explanation": "y", "images_read": ["a.png"],
                                     "combined": {"models": ["claude:sonnet"]}}
                g["duplication_evidence"] = False
        res["n_duplicate_groups"] = 0
        p.write_text(json.dumps(res))
        card = B.score(root, lp)
        adj = card["adjudication"]
        assert adj["papers_adjudicated"] == 1 and adj["groups_cleared"] >= 1
        assert adj["positives_fully_cleared_papers"] == ["10.1--a"]
        assert card["recall"]["paper_level"]["numerator"] == 0
        assert card["recall"]["paper_level_pre_adjudication"]["numerator"] == 1
        assert card["miss_attribution"]["examined_no_fire"] == 1
        md = B.render_markdown(card)
        assert "PubPeer positives fully cleared: 1 of 1" in md
        by = adj["by_model_set"]
        assert list(by) == ["claude:sonnet"]
        assert by["claude:sonnet"]["clear_rate"] == 1.0
        assert by["claude:sonnet"]["papers_fully_cleared"] == 1
        assert "| claude:sonnet | 1 |" in md


class TestKinds:
    @pytest.mark.parametrize("text,kind", [
        ("The western blot bands in Figure 3A look duplicated", "blot"),
        ("Confocal images in Figure 2 appear identical", "micrograph"),
        ("Nice paper", "unknown"),
        ("bar chart error bars are identical", "graph"),
    ])
    def test_kind_from_comment_text(self, text, kind):
        assert L.kind_from_comment_text(text)[0] == kind

    def test_figure_kinds_from_comments_ignores_non_image_comments(self):
        comments = [{"text": "Figure 1 is a lovely graph", "inner_id": 1},
                    {"text": "Figure 2A blot lanes look duplicated", "inner_id": 2}]
        assert L.figure_kinds_from_comments(comments) == {"Figure 2A": "blot"}

    def test_human_sidecar_overrides_and_is_stamped(self, swept):
        root, lp = swept
        payload = L.load_labels(lp)
        n = L.apply_figure_kinds(payload, {"10.1/a": {"Figure 1": "blot"}})
        assert n == 1
        assert L.figure_kind(payload["labels"]["10.1/a"], "Figure 1") == ("blot", "human")
        # "photo" IS a kind (the review pass found gross-specimen images);
        # a value outside the vocabulary still refuses.
        L.apply_figure_kinds(payload, {"10.1/a": {"Figure 1": "photo"}})
        with pytest.raises(ValueError):
            L.apply_figure_kinds(payload, {"10.1/a": {"Figure 1": "hologram"}})

    def test_build_labels_offline_with_a_stubbed_pubpeer(self, tmp_path, monkeypatch):
        from forensic_metascience_ai_toolkit import pubpeer as PP
        root = tmp_path / "c"
        (root / "10.1--a").mkdir(parents=True)
        (root / "10.1--a" / "metadata.json").write_text("{}")
        monkeypatch.setattr(PP, "lookup", lambda dois, cache=None, **k: {
            "records": {"10.1/a": {"url": "https://pubpeer.com/publications/X",
                                   "title": "A", "total_comments": 1,
                                   "users": "Elisabeth M Bik"}},
            "refusals": []})
        monkeypatch.setattr(PP, "fetch_comments", lambda url, cache=None, **k: {
            "ok": True, "images": [],
            "comments": [{"text": "Figure 3A western blot bands appear duplicated",
                          "inner_id": 1, "images": []}]})
        payload = L.build_labels(root, out=tmp_path / "labels.json", images=False,
                                 log=lambda s: None)
        rec = payload["labels"]["10.1/a"]
        assert rec["paper_dir"] == "10.1--a" and rec["is_image_integrity"]
        assert rec["figures"] == ["Figure 3A"]
        assert rec["figure_kinds"] == {"Figure 3A": "blot"}
        assert (tmp_path / "labels.json").exists()


class TestItSpendsNothing:
    def test_benchmark_launches_nothing_and_imports_no_paid_path(self):
        src = (IMAGE_SRC / "image_forensics" / "benchmark.py").read_text()
        for bad in ("llm_backend", "resolve_backend", "subprocess",
                    "_run_forensic_track", "_image_track_command",
                    "adjudicate_retained_findings"):
            assert bad not in src, bad
        src = (IMAGE_SRC / "image_forensics" / "labels.py").read_text()
        for bad in ("llm_backend", "resolve_backend", "subprocess"):
            assert bad not in src, bad


def test_cross_paper_review_block_reads_the_ledger(tmp_path):
    """A pair has two homes; the ledger is where it is counted once. An empty
    ledger is a stated zero, and the block is a tally, not a recall."""
    from metascience_observatory_image_analysis.image_forensics.benchmark import cross_paper_review_block
    blk = cross_paper_review_block(tmp_path)
    assert blk["decided_pairs"] == 0 and blk["precision"] is None
    led = tmp_path / ".image_track"
    led.mkdir()
    rows = [
        {"item": "cross:a:b:1", "decision": "unsure", "reviewer": "r"},
        {"item": "cross:a:b:1", "decision": "true_issue", "reviewer": "r"},   # last record wins
        {"item": "cross:c:d:2", "decision": "false_positive_same_condition", "reviewer": "r"},
        {"item": "within:a:IMGDUP-1", "decision": "true_issue", "reviewer": "r"},  # not a pair
    ]
    (led / "image_review.jsonl").write_text(
        "\n".join(__import__("json").dumps(r) for r in rows) + "\n", encoding="utf-8")
    blk = cross_paper_review_block(tmp_path)
    assert blk["decided_pairs"] == 2
    assert blk["true_issue"] == 1 and blk["false_positive"] == 1 and blk["unsure"] == 0
    assert blk["precision"] == 0.5
    assert blk["true_issue_pairs"] == ["cross:a:b:1"]


def test_content_diagnostics_preserve_retained_population_and_figure_recall(swept, tmp_path):
    """Additional sidecars cannot change either the hits or their denominator."""
    from metascience_observatory_image_analysis.image_forensics import content_support as diagnostics
    root, labels = swept
    image = tmp_path/'diagnostic-source.png'
    image.write_bytes(_png(_texture(22)))
    packet = tmp_path/'diagnostic-packet.json'
    packet.write_text(json.dumps({'id':'within:10.1--a:diagnostic',
        'panels':[{'uid':side,'path':str(image),'sha256':diagnostics.file_sha(image)} for side in ('a','b')],
        'measurements':{'affine':[[1,0,0],[0,1,0]]}}))
    paths = [p for p in root.rglob('*') if p.is_file()]
    before_bytes = {p: diagnostics.file_sha(p) for p in paths}
    before = B.score(root, labels, sweep_id='t1')
    assert before['recall']['figure_level_PRIMARY']['numerator'] > 0
    diagnostics.generate(packet, root/'.image_track/content_support')
    after = B.score(root, labels, sweep_id='t1')
    for key in ('recall','recall_by_kind','populations','miss_attribution'):
        assert after[key] == before[key]
    assert {p: diagnostics.file_sha(p) for p in paths} == before_bytes


# ---------------------------------------------------------------------------
# Tier-aware scope: an opt-in tier's allegations are only in the recall
# denominator when that tier actually ran, and a tier never inherits another
# tier's hits.
# ---------------------------------------------------------------------------

class TestWhichMechanismsASweepCouldReach:
    def test_no_stamp_fails_closed_to_the_pairwise_tiers(self):
        """An absent flag is not evidence that a tier ran. Assuming tier 5 ran
        would move every clone allegation into the denominator and score the
        detector as missing figures nobody asked it to look for."""
        for flags in (None, "not a dict", 17):
            mechs, basis = L.reachable_mechanisms(flags)
            assert mechs == frozenset({L.IN_SCOPE_MECHANISM})
            assert basis == "assumed_pairwise_only"

    def test_the_clone_tier_is_reachable_only_when_copy_move_ran(self):
        off, basis = L.reachable_mechanisms({"copy_move": False, "emit_v2": True})
        assert basis == "sweep_flags"
        assert "intra_panel_clone" not in off
        on, _ = L.reachable_mechanisms({"copy_move": True})
        assert "intra_panel_clone" in on
        # the pairwise tiers are never gated -- they run in every sweep
        assert L.IN_SCOPE_MECHANISM in off and L.IN_SCOPE_MECHANISM in on

    def test_cross_paper_is_reachable_under_no_flag(self):
        """Matching a DIFFERENT publication needs the cross-paper corpus pass,
        not a per-paper sweep, so no per-paper flag may make it in-scope."""
        for flags in ({}, {"copy_move": True}, {"cross_paper": True}):
            assert "cross_paper" not in L.reachable_mechanisms(flags)[0]

    def test_the_stored_pairwise_field_keeps_its_meaning(self):
        """`detectable_by_panel_pairs` answers a different question and must
        not be widened by the sweep-aware one."""
        rec = {"figure_review": {
            "Figure 1": {"mechanism": "intra_panel_clone",
                         "detectable_by_panel_pairs": False},
        }}
        # no `reachable` -> the stored, pairwise-only answer, unchanged
        assert L.figure_mechanism(rec, "Figure 1") == ("intra_panel_clone", False)
        assert L.paper_in_scope(rec) is False
        # with a sweep that ran tier 5 -> reachable, without touching the field
        reach, _ = L.reachable_mechanisms({"copy_move": True})
        assert L.figure_mechanism(rec, "Figure 1", reach) == ("intra_panel_clone", True)
        assert L.paper_in_scope(rec, reach) is True
        assert rec["figure_review"]["Figure 1"]["detectable_by_panel_pairs"] is False

    def test_an_unreviewed_figure_stays_unknown_not_out_of_scope(self):
        rec = {"figure_review": {}}
        reach, _ = L.reachable_mechanisms({"copy_move": True})
        assert L.figure_mechanism(rec, "Figure 9", reach) == ("unreviewed", None)
        assert L.paper_in_scope(rec, reach) is None


class TestATierDoesNotInheritAnotherTiersHits:
    def test_figures_named_by_tiers_filters_by_kind(self):
        row = {"groups": [
            {"kind": "transformed_match", "figure_labels": ["Figure 2"]},
            {"kind": "intra_panel_clone", "figure_labels": ["Figure 5"]},
        ]}
        pair = B.TIERS_FOR_MECHANISM["cross_panel_within_paper"]
        clone = B.TIERS_FOR_MECHANISM["intra_panel_clone"]
        assert B.figures_named_by_tiers(row, pair) == {"Figure 2"}
        assert B.figures_named_by_tiers(row, clone) == {"Figure 5"}
        # and the unfiltered helper pools them, which is why the filter exists
        assert B.figures_named(row) == {"Figure 2", "Figure 5"}

    def test_a_dead_clone_tier_scores_zero_beside_a_working_pairwise_tier(self):
        """The regression this whole block exists to prevent: a pooled recall
        number let a tier that found NOTHING ride on another tier's hits."""
        row = {"groups": [{"kind": "transformed_match", "figure_labels": ["Figure 2"]}]}
        clone = B.TIERS_FOR_MECHANISM["intra_panel_clone"]
        assert B.figures_named_by_tiers(row, clone) == set()
