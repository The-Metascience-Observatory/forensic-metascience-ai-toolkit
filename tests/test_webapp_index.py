"""The corpus index, and the states it must not collapse.

Every assertion here is about a distinction that a simpler data model would
lose. The measurements are from the two corpora in this checkout on
2026-08-17:

    high_value_pdfs_to_run_on              6 papers, 12 review directories
    cerebrolysin_papers (sibling repo)   421 papers
                                         370 ran the image detector
                                           1 retains its result
                                          44 were never fetched
                                         142 have an empty figmap/

A boolean `image_forensics: true/false` cannot express any row of that table
honestly.
"""
import json

import pytest

from forensic_metascience_ai_toolkit import webapp_index as W


def _paper(tmp_path, name="10.1234--demo", files=None, dirs=()):
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    for sub in dirs:
        (d / sub).mkdir(parents=True, exist_ok=True)
    for rel, content in (files or {}).items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content if isinstance(content, str) else json.dumps(content))
    return d


def _cross(matches, **top):
    """A `cross_paper_matches.json` body, shaped like the real writer's."""
    return {"schema_version": "1.0", "corpus_root": "/c", "paper_key": "p",
            "paper_dir": "/c/p", "adjudicated": False,
            "n_matches": len(matches), "matches": matches, **top}


def _side(paper_key="10.9999--other", root="/c"):
    return {"corpus_root": root, "paper_key": paper_key,
            "paper_dir": f"{root}/{paper_key}", "panel_uid": f"{paper_key}:x1",
            "panel_id": "x1", "image_relpath": "panels/x1.png",
            "image_unavailable_reason": "", "pages": [3],
            "figure_labels": ["Figure 2"], "doc_role": "main",
            "location_unknown_reason": "", "inlier_box": [1, 2, 3, 4],
            "panel_px": [100, 80]}


class TestTheCrossPaperChannelAsksADifferentQuestion:
    """A paper checked exhaustively against ITSELF has not been checked against
    anyone else, and until this channel existed the workbench reported those two
    identically -- `image_forensics: ran`, and nothing said otherwise.

    It is also the sharper of the two questions. A panel repeated inside one
    paper is often innocent; the same panel under two different authors' names
    is not, and it is the finding a reader cannot reach alone, because it is
    invisible from inside either paper.
    """

    def test_a_matches_file_is_ran_and_counts_the_other_papers(self, tmp_path):
        d = _paper(tmp_path, files={
            "panels/review/cross_paper_matches.json": _cross([
                {"kind": "cross_paper_image_reuse", "this_side": _side("me"),
                 "other_side": _side("10.1--a"), "adjudication": None},
                {"kind": "cross_paper_image_reuse", "this_side": _side("me"),
                 "other_side": _side("10.1--a"), "adjudication": None},
                {"kind": "cross_paper_image_reuse", "this_side": _side("me"),
                 "other_side": _side("10.2--b"), "adjudication": None},
            ])})
        ch = W.cross_paper_channel(d)
        assert ch["state"] == "ran"
        assert ch["n_matches"] == 3
        assert ch["n_other_papers"] == 2, "three matches, but only two partners"

    def test_the_partner_count_keys_on_root_and_path_not_on_the_id(self, tmp_path):
        """14 paper ids in this configuration live in TWO corpus roots, so two
        different papers can share a DOI slug. Counting distinct ids would merge
        them and report one partner where there are two."""
        d = _paper(tmp_path, files={
            "panels/review/cross_paper_matches.json": _cross([
                {"this_side": _side("me"),
                 "other_side": _side("10.1007--s004010051012", "/rootA")},
                {"this_side": _side("me"),
                 "other_side": _side("10.1007--s004010051012", "/rootB")},
            ])})
        assert W.cross_paper_channel(d)["n_other_papers"] == 2

    def test_unadjudicated_says_so_rather_than_reading_as_confirmed(self, tmp_path):
        d = _paper(tmp_path, files={
            "panels/review/cross_paper_matches.json": _cross([
                {"this_side": _side("me"), "other_side": _side(),
                 "adjudication": None}])})
        ch = W.cross_paper_channel(d)
        assert ch["n_adjudicated"] == 0
        assert "no innocuous explanation" in ch["detail"]

    def test_prose_only_runs_are_ran_but_say_they_cannot_be_drawn(self, tmp_path):
        """Runs predating the JSON writer found something real. The finding is
        not weaker -- it is unrenderable, which is a fact about us."""
        d = _paper(tmp_path, files={"cross_paper_image_reuse.md": "# reuse\n"})
        ch = W.cross_paper_channel(d)
        assert ch["state"] == "ran"
        assert ch["prose_only"] is True
        assert "cannot be drawn" in ch["detail"]

    def test_an_unparseable_file_is_unknown_not_a_clean_paper(self, tmp_path):
        d = _paper(tmp_path, files={
            "panels/review/cross_paper_matches.json": "{ this is not json"})
        assert W.cross_paper_channel(d)["state"] == "unknown"

    def test_descriptors_without_a_sweep_are_not_a_comparison(self, tmp_path):
        d = _paper(tmp_path, files={"panels/panels.json": {"panels": []}})
        assert W.cross_paper_channel(d)["state"] == "did_not_run"

    def test_nothing_at_all_is_did_not_run(self, tmp_path):
        assert W.cross_paper_channel(_paper(tmp_path))["state"] == "did_not_run"


@pytest.fixture
def cross_paper_on(monkeypatch):
    """The between-paper screen is OFF by default (2026-08-18), so a test of it
    must switch it on. Enabling it here rather than in the module keeps the
    default honest: if the flag stopped being read, these tests would still
    pass and the disabled state would be the thing nobody checked."""
    monkeypatch.setenv("METASCIENCE_CROSS_PAPER", "1")


class TestTheScreenIsOffByDefault:
    """Off means ABSENT, not empty. An empty cross-paper channel would say "we
    looked and found nothing"; the question is simply not being asked."""

    def test_the_channel_is_not_emitted(self, tmp_path):
        _paper(tmp_path, name="10.1--x", files={"paper.pdf": "x"})
        out = W.scan_corpus(tmp_path)
        assert "cross_paper" not in out["papers"][0]["channels"]

    def test_and_it_is_absent_from_the_totals_too(self, tmp_path):
        _paper(tmp_path, name="10.1--x", files={"paper.pdf": "x"})
        out = W.scan_corpus(tmp_path)
        assert "cross_paper" not in out["totals"]["channels"], (
            "a row of zeros in the totals reads as a screen that ran and found "
            "nothing")

    def test_the_flag_brings_it_back(self, tmp_path, cross_paper_on):
        _paper(tmp_path, name="10.1--x", files={"paper.pdf": "x"})
        out = W.scan_corpus(tmp_path)
        assert "cross_paper" in out["papers"][0]["channels"]


class TestAnUnsweptCorpusCannotClearAPaper:
    """THE ABSENCE ONLY THE CORPUS CAN EXPLAIN. The sweep writes into a paper
    only when it MATCHED, so a paper compared against four hundred others and
    found clean leaves the same trace as one never compared at all: nothing.

    Reporting the second as `did_not_run` would be defensible; reporting it the
    same as the first is not. A reader seeing four hundred `did_not_run` papers
    concludes the check is simply unused. A reader seeing four hundred papers
    that all say "no sweep has run over this corpus" knows what is missing and
    can fix it.
    """

    def test_an_unswept_root_reports_unknown_not_did_not_run(self, tmp_path, cross_paper_on):
        _paper(tmp_path, name="10.1--x", files={"paper.pdf": "x"})
        out = W.scan_corpus(tmp_path)
        ch = out["papers"][0]["channels"]["cross_paper"]
        assert ch["state"] == "unknown"
        assert "has not been asked" in ch["detail"]

    def test_a_swept_root_leaves_did_not_run_alone(self, tmp_path, cross_paper_on):
        """With the corpus report present the sweep DID run, so a paper with no
        match file genuinely has no cross-paper hit and may say so."""
        _paper(tmp_path, name="10.1--x", files={"paper.pdf": "x"})
        (tmp_path / "image_corpus_report.md").write_text("# Cross-paper\n")
        out = W.scan_corpus(tmp_path)
        assert out["papers"][0]["channels"]["cross_paper"]["state"] == "did_not_run"

    def test_a_real_match_survives_the_override(self, tmp_path, cross_paper_on):
        """The override must only touch `did_not_run`. A paper WITH matches in
        an unswept-looking root still ran."""
        _paper(tmp_path, name="10.1--x", files={
            "paper.pdf": "x",
            "panels/review/cross_paper_matches.json": _cross([
                {"this_side": _side("me"), "other_side": _side()}])})
        out = W.scan_corpus(tmp_path)
        assert out["papers"][0]["channels"]["cross_paper"]["state"] == "ran"


class TestTheImageChannelHasFiveStatesBecauseFourWouldLie:
    """`panel_index.json` is written by `analyze_paper_images` itself, so its
    presence PROVES the detector ran. 369 of the 370 papers carrying one retain
    no result.

    "Did not run" is false of them. "Ran" invites the reader to conclude the
    panels were examined and cleared, which is the false all-clear this whole
    codebase is organised against. So the middle case gets its own name.
    """

    def test_a_retained_result_is_ran(self, tmp_path):
        d = _paper(tmp_path, files={
            "10.1234--demo.pdf": "x",
            "image_duplication_findings.json": {
                "n_duplicate_groups": 2, "n_panels": 41, "severity": "indeterminate"},
        })
        ch = W.scan_paper(d)["channels"]["image_forensics"]
        assert ch["state"] == "ran"
        assert ch["n_duplicate_groups"] == 2

    def test_a_harvest_with_no_result_is_its_own_state(self, tmp_path):
        d = _paper(tmp_path, files={
            "10.1234--demo.pdf": "x",
            "panels/panel_index.json": {"paper_id": "x",
                                        "panels": [{"uid": "a"}, {"uid": "b"}]},
        })
        ch = W.scan_paper(d)["channels"]["image_forensics"]
        assert ch["state"] == "ran_result_discarded"
        assert ch["n_panels"] == 2
        assert "not recoverable" in ch["detail"]

    def test_that_state_is_neither_ran_nor_did_not_run(self, tmp_path):
        """Stated as its own test because it is the entire point."""
        d = _paper(tmp_path, files={
            "10.1234--demo.pdf": "x",
            "panels/panel_index.json": {"panels": []}})
        assert W.scan_paper(d)["channels"]["image_forensics"]["state"] \
            not in ("ran", "did_not_run")

    def test_corpus_describer_output_is_not_the_detector(self, tmp_path):
        """`panels.json` is written by `image_corpus.describe_paper`, which
        describes panels for the cross-paper sweep. It does not run the
        within-paper duplication tiers, so it clears nothing."""
        d = _paper(tmp_path, files={"10.1234--demo.pdf": "x",
                                    "panels/panels.json": {"panels": []}})
        ch = W.scan_paper(d)["channels"]["image_forensics"]
        assert ch["state"] == "did_not_run"
        assert "cross-paper" in ch["detail"]

    def test_a_recorded_refusal_keeps_its_subtype(self, tmp_path):
        """"No engine on this machine" is a property of the installation, not
        of the paper, and the workbench has to be able to say which."""
        d = _paper(tmp_path, files={
            "10.1234--demo.pdf": "x",
            "forensic_review/run_meta.json": {"stages": {"image_forensics": {
                "ran": False, "refusal_subtype": "engine_missing",
                "detail": "PyMuPDF is absent"}}},
        })
        ch = W.scan_paper(d)["channels"]["image_forensics"]
        assert ch["state"] == "refused"
        assert ch["subtype"] == "engine_missing"

    def test_nothing_at_all_is_did_not_run(self, tmp_path):
        d = _paper(tmp_path, files={"10.1234--demo.pdf": "x"})
        assert W.scan_paper(d)["channels"]["image_forensics"]["state"] == "did_not_run"


class TestAFailedFetchIsNotAnAbsence:
    """The first version of `looks_like_paper` required a PDF, an XML, a
    `body.md`, a `panels/` or a review directory -- all evidence that something
    WORKED. It dropped 50 of 423 directories, 44 of which are papers whose
    fetch failed: a `.landing.html`, a `.provenance.json`, and no PDF.

    A scanner that hides those reports a corpus of 373 harvested papers when
    the truth is 421 papers of which 44 were never obtained. That is our own
    failure rendered as an absence of findings -- committed by the tool whose
    job is making coverage visible.
    """

    def test_a_landing_page_only_directory_is_still_a_paper(self, tmp_path):
        d = _paper(tmp_path, files={
            "10.1234--demo.landing.html": "<html>Access denied</html>",
            "10.1234--demo.provenance.json": {"doi": "10.1234/demo"}})
        assert W.looks_like_paper(d)
        rec = W.scan_paper(d)
        assert rec["sources"]["state"] == "not_fetched"
        assert rec["sources"]["landing_page_only"] is True

    def test_not_fetched_is_distinct_from_never_attempted(self, tmp_path):
        """Only one of them is actionable, and by a different action."""
        failed = _paper(tmp_path, "a", files={"a.landing.html": "<html/>"})
        empty = _paper(tmp_path, "b", files={"notes.txt": "x"})
        assert W.scan_paper(failed)["sources"]["state"] == "not_fetched"
        assert W.scan_paper(empty)["sources"]["state"] == "empty"

    def test_an_empty_directory_is_not_a_paper(self, tmp_path):
        d = tmp_path / "hollow"
        d.mkdir()
        assert not W.looks_like_paper(d)

    def test_scaffolding_is_not_a_paper(self, tmp_path):
        for name in ("done", "logs", ".image_corpus_cache"):
            d = _paper(tmp_path, name, files={"x.pdf": "x"})
            assert not W.looks_like_paper(d), name

    def test_the_totals_count_what_we_do_not_hold(self, tmp_path):
        """A rate computed over papers we HAVE, presented as a rate over the
        corpus, is the wrong denominator."""
        _paper(tmp_path, "a", files={"a.pdf": "x"})
        _paper(tmp_path, "b", files={"b.landing.html": "<html/>"})
        t = W.scan_corpus(tmp_path)["totals"]
        assert t["sources"] == {"held": 1, "not_fetched": 1, "empty": 0}


class TestAPaperIsNotARun:
    """Papers here carry several review directories -- `forensic_review`,
    `forensic_review_current`, `forensic_review_warrant` -- which are different
    analyses of one paper, often across a version boundary CHANGELOG.md says
    makes them incomparable. A row showing "the" verdict picks one and hides
    the rest."""

    def _multi(self, tmp_path):
        return _paper(tmp_path, files={
            "10.1234--demo.pdf": "x",
            "forensic_review/report.json": {"verdict": "unresolved",
                                            "findings": [{"severity": "suspicious"}]},
            "forensic_review/run_meta.json": {"total_cost_usd": 3.0},
            "forensic_review_current/report.json": {
                "verdict": "does_not_reconcile",
                "findings": [{"severity": "impossible"}]},
            "forensic_review_current/run_meta.json": {"total_cost_usd": 5.0},
        })

    def test_every_run_is_listed(self, tmp_path):
        rec = W.scan_paper(self._multi(tmp_path))
        assert rec["n_runs"] == 2
        assert {r["name"] for r in rec["runs"]} == {
            "forensic_review", "forensic_review_current"}

    def test_a_bundle_directory_is_not_a_run(self, tmp_path):
        """`<review>_bundle/analysis/report.md` is a scrubbed COPY of a review
        that also exists in its own right. Counting it doubles every paper
        that has ever been bundled."""
        d = _paper(tmp_path, files={
            "10.1234--demo.pdf": "x",
            "forensic_review/report.json": {"verdict": "unresolved", "findings": []},
            "forensic_review_bundle/analysis/report.json": {"verdict": "unresolved",
                                                            "findings": []},
        })
        assert W.scan_paper(d)["n_runs"] == 1

    def test_the_headline_figures_come_from_the_newest_run(self, tmp_path):
        import os, time
        d = self._multi(tmp_path)
        newest = d / "forensic_review_current"
        os.utime(newest, (time.time() + 10, time.time() + 10))
        rec = W.scan_paper(d)
        assert rec["latest_run"] == "forensic_review_current"
        assert rec["verdict"] == "does_not_reconcile"
        assert rec["worst_severity"] == "impossible"


class TestVerdictsAreComparableAcrossTheRename:
    def test_a_legacy_verdict_is_canonicalised_for_filtering(self, tmp_path):
        """34 archived reports use the retired words. Left raw they form their
        own filter buckets, so a corpus screen filtered to
        `does_not_reconcile` silently omits every `untrustworthy` run."""
        d = _paper(tmp_path, files={
            "10.1234--demo.pdf": "x",
            "forensic_review/report.json": {"verdict": "untrustworthy",
                                            "findings": []}})
        run = W.scan_paper(d)["runs"][0]
        assert run["verdict"] == "does_not_reconcile"
        assert run["verdict_recorded"] == "untrustworthy"
        assert run["verdict_is_legacy"] is True


class TestAPartialRunIsNotAFailedOne:
    def test_a_report_that_errored_but_produced_a_report_is_partial(self, tmp_path):
        """`batch_analyze` had to learn this after filing a complete, paid-for
        review ($6.02, a verdict, four findings) into `failed.jsonl`."""
        d = _paper(tmp_path, files={
            "10.1234--demo.pdf": "x",
            "forensic_review/report.json": {"verdict": "unresolved", "findings": []},
            "forensic_review/run_meta.json": {"stages": {"sweep": {"is_error": True}}}})
        assert W.scan_paper(d)["runs"][0]["status"] == "partial"

    def test_an_error_with_no_report_is_failed(self, tmp_path):
        d = _paper(tmp_path, files={
            "10.1234--demo.pdf": "x",
            "forensic_review/run_meta.json": {"stages": {"sweep": {"is_error": True}}}})
        assert W.scan_paper(d)["runs"][0]["status"] == "failed"


class TestUnreviewedIsNotWithheld:
    """A paper nobody has opened must never render as one someone declined to
    publish. A UI showing both as "not published" makes silence look like
    judgement."""

    def test_no_review_file_is_unreviewed(self, tmp_path):
        d = _paper(tmp_path, files={"10.1234--demo.pdf": "x"})
        r = W.scan_paper(d)["review"]
        assert r["reviewed"] is False
        assert r["publication"]["state"] == "unreviewed"

    def test_an_explicit_refusal_is_withheld(self, tmp_path):
        d = _paper(tmp_path, files={
            "10.1234--demo.pdf": "x",
            "review.json": {"publication": {"approved": False, "reviewer": "dan",
                                            "withheld_reason": "extraction error"}}})
        pub = W.scan_paper(d)["review"]["publication"]
        assert pub["state"] == "withheld"
        assert pub["reason"] == "extraction error"

    def test_the_two_gates_are_independent(self, tmp_path):
        """Publishing a review page and reporting a finding to PubPeer are
        different decisions; approving one must not imply the other."""
        d = _paper(tmp_path, files={
            "10.1234--demo.pdf": "x",
            "review.json": {"publication": {"approved": True, "reviewer": "dan"},
                            "reporting": {"approved": False}}})
        r = W.scan_paper(d)["review"]
        assert r["publication"]["state"] == "approved"
        assert r["reporting"]["state"] == "withheld"

    def test_no_review_file_has_no_pubpeer_submission(self, tmp_path):
        d = _paper(tmp_path, files={"10.1234--demo.pdf": "x"})
        r = W.scan_paper(d)["review"]
        assert r["submitted_to_pubpeer"] is None
        assert r["pubpeer_url"] is None

    def test_a_recorded_pubpeer_submission_is_counted(self, tmp_path):
        _paper(tmp_path / "proj", "p", files={
            "p.pdf": "x",
            "review.json": {
                "paper": {
                    "status": "complete",
                    "reviewed_by": "Dan Elton",
                    "submitted_to_pubpeer": True,
                    "pubpeer_url": "https://pubpeer.com/publications/ABC#1",
                    "pubpeer_note": "Two patients unaccounted for.",
                },
            },
        })
        ix = W.scan_projects(tmp_path)
        row = ix["projects"][0]
        assert row["n_human_reviewed"] == 1
        assert row["n_submitted_pubpeer"] == 1
        paper = row["corpus"]["papers"][0]
        assert paper["review"]["submitted_to_pubpeer"] is True
        assert paper["review"]["pubpeer_url"].endswith("ABC#1")

    def test_complete_without_a_submission_is_not_counted_as_submitted(
            self, tmp_path):
        _paper(tmp_path / "proj", "p", files={
            "p.pdf": "x",
            "review.json": {"paper": {"status": "complete",
                                      "reviewed_by": "Dan Elton"}},
        })
        ix = W.scan_projects(tmp_path)
        assert ix["projects"][0]["n_human_reviewed"] == 1
        assert ix["projects"][0]["n_submitted_pubpeer"] == 0


class TestTheQueueOrdersByWhatNeedsAHuman:
    def test_worst_first_then_unreviewed(self, tmp_path):
        papers = [
            {"paper_id": "clean", "worst_severity": "consistent", "review": {"reviewed": False}},
            {"paper_id": "bad", "worst_severity": "impossible", "review": {"reviewed": False}},
            {"paper_id": "bad-done", "worst_severity": "impossible", "review": {"reviewed": True}},
            {"paper_id": "nothing", "worst_severity": None, "review": {"reviewed": False}},
        ]
        assert [p["paper_id"] for p in W.sort_papers(papers)] == [
            "bad", "bad-done", "clean", "nothing"]

    def test_pubpeer_image_papers_sort_first(self):
        """The Masliah queue had 31 reviews and zero of them were the
        69 PubPeer image-integrity papers -- the index did not carry the
        label, so it could not be a sort key."""
        papers = [
            {"paper_id": "fp-swamp", "worst_severity": "suspicious",
             "review": {"reviewed": False},
             "pubpeer": {"has_entry": False, "is_image_integrity": False}},
            {"paper_id": "bik", "worst_severity": None,
             "review": {"reviewed": False},
             "pubpeer": {"has_entry": True, "is_image_integrity": True,
                         "figures": ["Figure 1C"]}},
        ]
        assert [p["paper_id"] for p in W.sort_papers(papers)] == [
            "bik", "fp-swamp"]


class TestItSurvivesTheCorpusOnDisk:
    """Synthetic fixtures cannot produce `ran_result_discarded` at scale; the
    real corpus does, on 369 papers."""

    def test_pubpeer_labels_are_stamped_from_the_corpus_file(self, tmp_path):
        _paper(tmp_path, "10.1--flagged", files={"10.1--flagged.pdf": "x"})
        _paper(tmp_path, "10.1--clean", files={"10.1--clean.pdf": "x"})
        (tmp_path / ".image_track").mkdir()
        (tmp_path / ".image_track" / "pubpeer_labels.json").write_text(
            json.dumps({
                "labels": {
                    "10.1/flagged": {
                        "paper_dir": "10.1--flagged",
                        "is_image_integrity": True,
                        "figures": ["Figure 1C"],
                        "total_comments": 4,
                        "url": "https://pubpeer.com/x",
                    }
                },
                "unknown_dois": [],
            }))
        ix = W.scan_corpus(tmp_path)
        by = {p["paper_id"]: p for p in ix["papers"]}
        assert by["10.1--flagged"]["pubpeer"]["is_image_integrity"] is True
        assert by["10.1--flagged"]["pubpeer"]["figures"] == ["Figure 1C"]
        assert by["10.1--flagged"]["pubpeer"]["url"] == "https://pubpeer.com/x"
        assert by["10.1--clean"]["pubpeer"]["has_entry"] is False
        assert ix["totals"]["n_pubpeer_image"] == 1

    def test_a_javascript_pubpeer_url_is_not_an_href(self, tmp_path):
        _paper(tmp_path, "10.1--flagged", files={"10.1--flagged.pdf": "x"})
        (tmp_path / ".image_track").mkdir()
        (tmp_path / ".image_track" / "pubpeer_labels.json").write_text(
            json.dumps({
                "labels": {
                    "10.1/flagged": {
                        "paper_dir": "10.1--flagged",
                        "is_image_integrity": True,
                        "figures": ["Figure 1C"],
                        "total_comments": 1,
                        "url": "javascript:alert(1)",
                    }
                },
                "unknown_dois": [],
            }))
        ix = W.scan_corpus(tmp_path)
        assert ix["papers"][0]["pubpeer"]["has_entry"] is True
        assert ix["papers"][0]["pubpeer"]["url"] is None

    def test_pubpeer_labels_match_a_paper_in_a_subfolder(self, tmp_path):
        d = tmp_path / "already_retracted"
        d.mkdir()
        _paper(d, "10.1--flagged", files={"10.1--flagged.pdf": "x"})
        (tmp_path / ".image_track").mkdir()
        (tmp_path / ".image_track" / "pubpeer_labels.json").write_text(
            json.dumps({
                "labels": {
                    "10.1/flagged": {
                        "paper_dir": "10.1--flagged",
                        "is_image_integrity": True,
                        "figures": ["Figure 2"],
                        "url": "https://pubpeer.com/publications/ABC",
                    }
                },
                "unknown_dois": [],
            }))
        ix = W.scan_corpus(tmp_path)
        hit = next(p for p in ix["papers"] if p["paper_id"] == "10.1--flagged")
        assert hit["dir"] == "already_retracted/10.1--flagged"
        assert hit["pubpeer"]["url"] == "https://pubpeer.com/publications/ABC"

    def test_a_malformed_paper_does_not_sink_the_corpus(self, tmp_path):
        _paper(tmp_path, "ok", files={"ok.pdf": "x"})
        bad = _paper(tmp_path, "bad", files={"bad.pdf": "x"})
        (bad / "forensic_review").mkdir()
        (bad / "forensic_review" / "report.json").write_text("{not json")
        ix = W.scan_corpus(tmp_path)
        assert ix["totals"]["n_papers"] == 2

    def test_a_missing_root_is_reported_not_raised(self, tmp_path):
        ix = W.scan_corpus(tmp_path / "nope")
        assert ix["papers"] == []
        assert ix["errors"]

    def test_every_channel_state_is_in_the_declared_vocabulary(self, tmp_path):
        d = _paper(tmp_path, files={"10.1234--demo.pdf": "x"})
        for rec in W.scan_paper(d)["channels"].values():
            assert rec["state"] in W.CHANNEL_STATES

    def test_severity_counts_show_every_rung_at_zero(self, tmp_path):
        """A missing key and a zero read differently in a UI, and only one of
        them is a claim. `0 impossible` says we looked."""
        counts = W.severity_counts([{"severity": "suspicious"}])
        assert counts["impossible"] == 0
        assert set(counts) == {"impossible", "highly_suspicious", "suspicious",
                               "indeterminate", "consistent"}


class TestVisualEvidenceIsCatalogued:
    """MEASURED on `cerebrolysin_papers`: 4 papers of 421 carry any visual
    evidence at all, and 35.6 MB of it sits on one. That is what you would
    expect of artifacts written by manual scripts nothing in the pipeline
    calls -- and it is why the index enumerates them: nobody finds four papers
    in four hundred by browsing.
    """

    def test_a_video_is_recognised_as_one(self, tmp_path):
        """`animate_panel_match.py` writes ~6 MB H.264 MP4s. This is the
        capability the offline bundle structurally cannot have: `bundle.py`
        inlines everything so the page opens from `file://`, and a 6 MB clip
        base64'd into HTML is an 8 MB page per clip."""
        d = _paper(tmp_path, files={
            "10.1234--demo.pdf": "x",
            "panels/review/fig3_h_i_match.mp4": "\0" * 64})
        assets = W.scan_paper(d)["evidence"]
        assert len(assets) == 1
        assert assets[0]["kind"] == "animation"
        assert assets[0]["is_video"] is True

    def test_each_producer_naming_convention_is_recognised(self, tmp_path):
        """Six producers, six conventions, never reconciled."""
        d = _paper(tmp_path, files={
            "10.1234--demo.pdf": "x",
            "panels/review/group01_transformed_match.png": "x",   # exhibit_fired_groups
            "panels/review/group_1_identical_stream.png": "x",    # cli --montage
            "panels/review/fig3_h_i_match.mp4": "x",              # animate_panel_match
            "panels/review/fig3_h_i_match_key_blink.png": "x",    #   its key frames
            "panels/review/fig3_e_f_pubpeer.png": "x",            # animate --pubpeer
            "duplication_review.png": "x",                        # render_review_figure
        })
        kinds = {a["name"]: a["kind"] for a in W.scan_paper(d)["evidence"]}
        assert kinds["group01_transformed_match.png"] == "exhibit"
        assert kinds["group_1_identical_stream.png"] == "exhibit"
        assert kinds["fig3_h_i_match.mp4"] == "animation"
        assert kinds["fig3_h_i_match_key_blink.png"] == "key_frame"
        assert kinds["fig3_e_f_pubpeer.png"] == "pubpeer_exhibit"
        assert kinds["duplication_review.png"] == "review_figure"

    def test_paths_are_relative_to_the_paper(self, tmp_path):
        """The index is read by a server that resolves them under a corpus
        root. An absolute path leaks the operator's home and breaks on any
        other machine -- the defect `scrub` exists to prevent, arriving by a
        different route."""
        d = _paper(tmp_path, files={"10.1234--demo.pdf": "x",
                                    "panels/review/group01_x.png": "x"})
        for a in W.scan_paper(d)["evidence"]:
            assert not a["path"].startswith("/")
            assert "\\" not in a["path"]
            assert a["path"] == "panels/review/group01_x.png"
            assert str(tmp_path) not in a["path"]

    def test_a_stray_image_beside_the_paper_is_not_evidence(self, tmp_path):
        """A figure a fetcher happened to save is not something a reviewer was
        asked to look at."""
        d = _paper(tmp_path, files={"10.1234--demo.pdf": "x",
                                    "cover_thumbnail.png": "x"})
        assert W.scan_paper(d)["evidence"] == []

    def test_the_corpus_totals_count_video_separately(self, tmp_path):
        """Byte size decides whether a screen can inline it, so the count that
        matters is not "assets" but "videos"."""
        _paper(tmp_path, "a", files={"a.pdf": "x",
                                     "panels/review/m.mp4": "x",
                                     "panels/review/group01_k.png": "x"})
        _paper(tmp_path, "b", files={"b.pdf": "x",
                                     "panels/review/group01_k.png": "x"})
        t = W.scan_corpus(tmp_path)["totals"]["evidence"]
        assert t == {"papers_with_evidence": 2, "papers_with_video": 1,
                     "n_assets": 3, "n_videos": 1}


class TestTheReviewManifestIsARetainedResult:
    """`exhibit_fired_groups.py` writes `panels/review/review_manifest.json`:
    one entry per fired group with the panel uids, the measurements, the
    adjudication verdict where there is one, and the artifact paths.

    Before this branch existed, a paper carrying one came back
    `ran_result_discarded` — the state added precisely so a discarded answer is
    not called a clean paper, misreporting a paper whose answer is on disk.
    Misreporting WHICH kind of absence is the entire failure the tri-state
    exists to prevent, so this is worse than not having the state.
    """

    MANIFEST = {
        "paper_id": "10.1234--demo", "n_groups": 2, "n_exhibits": 2,
        "n_videos": 1,
        "groups": [
            {"group_index": 1, "kind": "transformed_match",
             "panels": ["a.pdf:xref1", "a.pdf:xref2"],
             "figure_labels": ["Figure 3"], "sentence": "…",
             "measurements": {"n_inliers": 144, "grain_residual_r": 0.637,
                              "rotation_deg": 178.8, "scale": 1.63},
             "exhibit_png": "group01_transformed_match.png",
             "video_mp4": None,
             "video_reason": "near-identity transform, nothing would move"},
            {"group_index": 2, "kind": "transformed_match",
             "panels": ["a.pdf:xref5", "a.pdf:xref6"],
             "measurements": {"n_inliers": 280, "grain_residual_r": 0.693},
             "exhibit_png": "group02_transformed_match.png",
             "video_mp4": "group02_transformed_match.mp4",
             "video_reason": "rotation transform"},
        ],
    }

    def _paper_with_manifest(self, tmp_path, files=None):
        return _paper(tmp_path, files={
            "10.1234--demo.pdf": "x",
            "panels/panel_index.json": {"panels": [{"uid": "a"}]},
            "panels/review/review_manifest.json": self.MANIFEST,
            **(files or {}),
        })

    def test_a_manifest_beats_the_harvest_leavings(self, tmp_path):
        """`panel_index.json` is present too — the manifest must win."""
        ch = W.scan_paper(self._paper_with_manifest(tmp_path))["channels"]["image_forensics"]
        assert ch["state"] == "ran"
        assert ch["n_groups"] == 2
        assert ch["n_videos"] == 1

    def test_measurements_travel_with_the_picture(self, tmp_path):
        """A picture of two similar panels is persuasive in exactly the way
        these numbers exist to discipline. `grain_residual_r` runs BACKWARDS on
        shared chart templates, so a convincing-looking match with high grain
        may be a plot template — and only the number says so."""
        d = self._paper_with_manifest(tmp_path, {
            "panels/review/group01_transformed_match.png": "x",
            "panels/review/group02_transformed_match.png": "x",
            "panels/review/group02_transformed_match.mp4": "x",
        })
        by_name = {a["name"]: a for a in W.scan_paper(d)["evidence"]}
        g1 = by_name["group01_transformed_match.png"]["group"]
        assert g1["measurements"]["n_inliers"] == 144
        assert g1["measurements"]["grain_residual_r"] == 0.637
        assert by_name["group02_transformed_match.mp4"]["group"]["measurements"]["n_inliers"] == 280

    def test_a_doi_prefixed_video_still_joins_to_its_group(self, tmp_path):
        """Since 2026-09-08 the writer names videos
        `<doi-slug>_groupNN_<kind>.mp4`; the group number is still the join."""
        manifest = json.loads(json.dumps(self.MANIFEST))
        manifest["groups"][1]["video_mp4"] = "10.1234--demo_group02_transformed_match.mp4"
        d = self._paper_with_manifest(tmp_path, {
            "panels/review/review_manifest.json": manifest,
            "panels/review/10.1234--demo_group02_transformed_match.mp4": "x",
        })
        by_name = {a["name"]: a for a in W.scan_paper(d)["evidence"]}
        hit = by_name["10.1234--demo_group02_transformed_match.mp4"]
        assert hit["group"]["measurements"]["n_inliers"] == 280
        assert W._GROUP_STEM_RE.search("fig3_h_i_match.mp4") is None
        assert W._GROUP_STEM_RE.search("10.1152--ajpgi.00313.2020_group03_transformed_match.mp4").group(1) == "03"

    def test_a_group_with_no_picture_carries_the_reason(self, tmp_path):
        """A blank pane says nothing; "the animation would show nothing moving"
        is a fact about the match. Same distinction `ran_result_discarded`
        makes one level up."""
        d = self._paper_with_manifest(tmp_path)   # no artifact files on disk
        undrawn = [a for a in W.scan_paper(d)["evidence"]
                   if a["kind"] == "no_artifact"]
        assert len(undrawn) == 2
        assert any("nothing would move" in a["shows"] for a in undrawn)
        assert all(a["path"] is None for a in undrawn)

    def test_the_join_uses_the_filename_not_either_group_index(self, tmp_path):
        """The manifest's `group_index` is 1-based; `image_track`'s is 0-based.
        Two fields of the same name counting from different origins is a join
        waiting to go wrong, so the key is the number in the filename, which
        both writers agree on."""
        d = self._paper_with_manifest(tmp_path, {
            "panels/review/group01_transformed_match.png": "x"})
        hit = [a for a in W.scan_paper(d)["evidence"]
               if a["name"] == "group01_transformed_match.png"][0]
        # group_index 1 in the manifest -> group01 on disk, inliers 144.
        assert hit["group"]["measurements"]["n_inliers"] == 144

    def test_a_paper_with_no_manifest_is_unaffected(self, tmp_path):
        """Purely additive: the 368 papers still carrying only a panel index
        must keep saying so."""
        d = _paper(tmp_path, files={"10.1234--demo.pdf": "x",
                                    "panels/panel_index.json": {"panels": []}})
        assert W.scan_paper(d)["channels"]["image_forensics"]["state"] \
            == "ran_result_discarded"


class TestARecordedRefusalIsNotAMislaidAnswer:
    """`image_track_status.json` says the track DECLINED, and that outranks the
    harvest leavings.

    Without this branch a scan whose pages are the rasters falls through to
    `ran_result_discarded` -- "the detector ran and we lost the answer" -- which
    invites re-running a detector that will refuse again for the same unchanged
    reason. MEASURED on masliah: 95 of the 99 zero-panel papers are refusals
    (46 all_panels_withheld, 30 no_rasters, 19 scanned_pages), and every one of
    them read as a discarded answer before.
    """

    def test_a_recorded_refusal_wins_over_the_panel_index(self, tmp_path):
        d = _paper(tmp_path, files={
            "panels/panel_index.json": {"panels": [{"id": "x"}]},
            "panels/image_track_status.json": {
                "ran": False, "refusal_subtype": "scanned_pages",
                "detail": "the pages themselves are the rasters",
                "n_panels": 132, "n_eligible": 0},
        })
        ch = W.image_channel(d, [], [])
        assert ch["state"] == "refused"
        assert ch["subtype"] == "scanned_pages"
        assert ch["n_eligible"] == 0

    def test_a_status_that_says_it_RAN_does_not_become_a_refusal(self, tmp_path):
        d = _paper(tmp_path, files={
            "panels/panel_index.json": {"panels": [{"id": "x"}]},
            "panels/image_track_status.json": {"ran": True},
        })
        assert W.image_channel(d, [], [])["state"] == "ran_result_discarded"

    def test_a_retained_result_still_outranks_it(self, tmp_path):
        """Precedence: a kept answer is more specific than a refusal note."""
        d = _paper(tmp_path, files={
            "image_duplication_findings.json": {"n_duplicate_groups": 2,
                                                "n_panels": 9},
            "panels/image_track_status.json": {"ran": False,
                                               "refusal_subtype": "no_rasters"},
        })
        assert W.image_channel(d, [], [])["state"] == "ran"


class TestDonePapersAreNotDropped:
    """`done/` is scaffolding. The papers inside it are papers."""

    def test_a_paper_in_done_is_scanned_once(self, tmp_path):
        _paper(tmp_path, "top", files={"top.pdf": "x"})
        _paper(tmp_path / "done", "10.1--nested", files={"10.1--nested.pdf": "x"})
        ix = W.scan_corpus(tmp_path)
        dirs = sorted(p["dir"] for p in ix["papers"])
        assert dirs == ["done/10.1--nested", "top"]
        assert ix["totals"]["n_papers"] == 2
        assert ix["totals"]["n_pdf"] == 2

    def test_done_itself_is_still_not_a_paper(self, tmp_path):
        (tmp_path / "done").mkdir()
        (tmp_path / "done" / "readme.txt").write_text("x")
        assert W.scan_corpus(tmp_path)["totals"]["n_papers"] == 0


class TestPriorityPapersAreNotDropped:
    """`priority/` is a pre-run queue. Same contract as `done/`."""

    def test_a_paper_in_priority_is_scanned_once(self, tmp_path):
        _paper(tmp_path, "top", files={"top.pdf": "x"})
        _paper(tmp_path / "priority", "10.1--queued",
               files={"10.1--queued.pdf": "x"})
        ix = W.scan_corpus(tmp_path)
        dirs = sorted(p["dir"] for p in ix["papers"])
        assert dirs == ["priority/10.1--queued", "top"]
        assert ix["totals"]["n_papers"] == 2
        assert ix["totals"]["n_pdf"] == 2

    def test_priority_itself_is_still_not_a_paper(self, tmp_path):
        (tmp_path / "priority").mkdir()
        (tmp_path / "priority" / "readme.txt").write_text("x")
        assert W.scan_corpus(tmp_path)["totals"]["n_papers"] == 0

    def test_renamed_queue_folder_is_also_scaffolding(self, tmp_path):
        _paper(tmp_path / "prioritized_cerebrolysin_papers", "10.1--queued",
               files={"10.1--queued.pdf": "x"})
        ix = W.scan_corpus(tmp_path)
        dirs = sorted(p["dir"] for p in ix["papers"])
        assert dirs == ["prioritized_cerebrolysin_papers/10.1--queued"]
        assert ix["totals"]["n_papers"] == 1

    def test_already_retracted_is_scaffolding(self, tmp_path):
        _paper(tmp_path / "already_retracted", "10.1--dead",
               files={"10.1--dead.pdf": "x"})
        ix = W.scan_corpus(tmp_path)
        dirs = sorted(p["dir"] for p in ix["papers"])
        assert dirs == ["already_retracted/10.1--dead"]
        assert ix["totals"]["n_papers"] == 1

    def test_retracted_is_scaffolding(self, tmp_path):
        _paper(tmp_path / "retracted", "10.1--dead",
               files={"10.1--dead.pdf": "x"})
        ix = W.scan_corpus(tmp_path)
        dirs = sorted(p["dir"] for p in ix["papers"])
        assert dirs == ["retracted/10.1--dead"]
        assert ix["totals"]["n_papers"] == 1


class TestABatchSubfolderIsNotAPaper:
    """A run dumped into `project/grok_run/<slug>` is the same shape as
    `project/done/<slug>`: the folder is scaffolding, the children are
    papers. Hardcoding `grok_run` in the nest list would hide the next
    batch named anything else.
    """

    def test_papers_in_an_unnamed_run_folder_are_scanned(self, tmp_path):
        _paper(tmp_path, "top", files={"top.pdf": "x"})
        _paper(tmp_path / "grok_run", "10.1--nested",
               files={"10.1--nested.pdf": "x"})
        (tmp_path / "grok_run" / "batch_costs.jsonl").write_text("{}\n")
        (tmp_path / "grok_run" / "metadata.json").write_text("{}")
        ix = W.scan_corpus(tmp_path)
        dirs = sorted(p["dir"] for p in ix["papers"])
        assert dirs == ["grok_run/10.1--nested", "top"]
        assert "\\" not in dirs[0], "dir is a URL key; backslashes break WSL Node"
        assert ix["totals"]["n_papers"] == 2
        assert ix["totals"]["n_pdf"] == 2

    def test_the_run_folder_itself_is_not_a_paper(self, tmp_path):
        _paper(tmp_path / "grok_run", "10.1--nested",
               files={"10.1--nested.pdf": "x"})
        (tmp_path / "grok_run" / "metadata.json").write_text("{}")
        assert not W.looks_like_paper(tmp_path / "grok_run")
        assert W.looks_like_paper(tmp_path / "grok_run" / "10.1--nested")

    def test_any_batch_folder_name_works(self, tmp_path):
        _paper(tmp_path / "batch_2026_08_20", "10.1--a",
               files={"10.1--a.pdf": "x"})
        dirs = [p["dir"] for p in W.scan_corpus(tmp_path)["papers"]]
        assert dirs == ["batch_2026_08_20/10.1--a"]

    def test_a_paper_with_panels_is_still_a_paper(self, tmp_path):
        """panels/ and forensic_review/ live inside a paper. They must not
        make the paper look like a nest of papers."""
        d = _paper(tmp_path, "10.1--a", files={"10.1--a.pdf": "x"},
                   dirs=("panels", "figures", "forensic_review"))
        assert W.looks_like_paper(d)
        ix = W.scan_corpus(tmp_path)
        assert [p["dir"] for p in ix["papers"]] == ["10.1--a"]
        assert ix["totals"]["n_papers"] == 1

    def test_a_failed_fetch_inside_a_run_folder_is_still_a_paper(self, tmp_path):
        _paper(tmp_path / "grok_run", "10.1--miss", files={
            "10.1--miss.landing.html": "<html/>",
            "10.1--miss.provenance.json": {"doi": "10.1/miss"},
        })
        recs = W.scan_corpus(tmp_path)["papers"]
        assert [p["dir"] for p in recs] == ["grok_run/10.1--miss"]
        assert recs[0]["sources"]["state"] == "not_fetched"

    def test_failed_and_logs_are_still_not_descended(self, tmp_path):
        _paper(tmp_path / "failed", "10.1--x", files={"10.1--x.pdf": "x"})
        _paper(tmp_path / "logs", "10.1--y", files={"10.1--y.pdf": "x"})
        assert W.scan_corpus(tmp_path)["totals"]["n_papers"] == 0


class TestProjectScan:
    def test_each_child_is_a_project(self, tmp_path):
        _paper(tmp_path / "masliah_papers", "10.1--a",
               files={"10.1--a.pdf": "x", "10.1--a.xml": "<article/>"})
        _paper(tmp_path / "masliah_papers", "10.1--b",
               files={"10.1--b.landing.html": "<html/>"})
        (tmp_path / "masliah_papers" / "10.1--a" / "forensic_review").mkdir()
        (tmp_path / "masliah_papers" / "10.1--a" / "forensic_review"
         / "report.json").write_text('{"verdict":"unresolved","findings":[]}')
        _paper(tmp_path / "gino_paper" / "done", "10.2--c",
               files={"10.2--c.pdf": "x",
                      "review.json": '{"paper":{"status":"complete",'
                                     '"reviewed_by":"Dan Elton"}}'})
        ix = W.scan_projects(tmp_path)
        by = {p["name"]: p for p in ix["projects"]}
        assert by["masliah_papers"]["n_papers"] == 2
        assert by["masliah_papers"]["n_pdf"] == 1
        assert by["masliah_papers"]["n_xml"] == 1
        assert by["masliah_papers"]["n_agent_run"] == 1
        assert by["masliah_papers"]["n_not_fetched"] == 1
        assert by["gino_paper"]["n_papers"] == 1
        assert by["gino_paper"]["n_human_reviewed"] == 1
        assert ix["n_papers"] == 3

    def test_the_two_project_row_builders_agree(self, tmp_path):
        """`scan_projects` and `refresh_index_paper` both flatten `_totals`
        into a project row, from two literal key lists. A field added to one
        and not the other is present on a fresh scan and gone after the next
        click -- `n_viewed` rendered as `false` on the project header exactly
        this way, and the same class of second-copy bug is what `_totals`'s
        own docstring warns about for channels.
        """
        _paper(tmp_path / "corpus_a", "10.1--a", files={"10.1--a.pdf": "x"})
        ix = W.scan_projects(tmp_path)
        row = ix["projects"][0]
        scanned = {k: v for k, v in row.items() if k.startswith("n_")}
        patched = dict(row)
        W._apply_project_totals(patched, row["corpus"]["papers"])
        assert scanned == {k: v for k, v in patched.items()
                           if k.startswith("n_") and k in scanned}
        assert set(scanned) >= {"n_viewed", "n_viewed_unknown"}

    def test_the_header_count_of_viewed_papers_is_real(self, tmp_path):
        from forensic_metascience_ai_toolkit.views_io import record_view
        a = _paper(tmp_path / "corpus_a", "10.1--a",
                   files={"10.1--a.pdf": "x"})
        _paper(tmp_path / "corpus_a", "10.1--b", files={"10.1--b.pdf": "x"})
        record_view(a, viewer="Dan Elton", at="2026-08-22T10:00:00Z")
        row = W.scan_projects(tmp_path)["projects"][0]
        assert row["n_papers"] == 2
        assert row["n_viewed"] == 1
        assert row["n_viewed_unknown"] == 0

    def test_analysed_at_is_the_recorded_stamp(self, tmp_path):
        d = _paper(tmp_path, files={"x.pdf": "x"})
        (d / "forensic_review").mkdir()
        (d / "forensic_review" / "report.json").write_text(
            '{"verdict":"unresolved","findings":[]}')
        (d / "forensic_review" / "run_meta.json").write_text(
            '{"analysed_at":"2026-08-14 09:30 UTC"}')
        rec = W.scan_paper(d)
        assert rec["analysed_at"] == "2026-08-14 09:30 UTC"
        assert rec["analysed_at_source"] == "recorded"

    def test_analysed_at_falls_back_to_file_mtime_and_says_so(self, tmp_path):
        d = _paper(tmp_path, files={"x.pdf": "x"})
        (d / "forensic_review").mkdir()
        report = d / "forensic_review" / "report.json"
        report.write_text('{"verdict":"unresolved","findings":[]}')
        rec = W.scan_paper(d)
        assert rec["analysed_at"]
        assert rec["analysed_at_source"] == "file_mtime"
        assert rec["analysed_at"].endswith("UTC")

    def test_no_run_has_no_analysed_at(self, tmp_path):
        d = _paper(tmp_path, files={"x.pdf": "x"})
        rec = W.scan_paper(d)
        assert rec["analysed_at"] is None
        assert rec["analysed_at_source"] is None

    def test_complete_is_not_counted_from_a_half_written_file(self, tmp_path):
        _paper(tmp_path / "proj", "p", files={
            "p.pdf": "x",
            "review.json": '{"issues":{"numeric:1":{"decision":"correct"}}}'})
        ix = W.scan_projects(tmp_path)
        assert ix["projects"][0]["n_human_reviewed"] == 0
        assert ix["projects"][0]["n_in_progress"] == 1

    def test_discarded_image_runs_are_named_on_the_project_row(self, tmp_path):
        _paper(tmp_path / "proj", "kept", files={
            "kept.pdf": "x",
            "image_duplication_findings.json": {
                "n_duplicate_groups": 1, "n_panels": 2},
        })
        _paper(tmp_path / "proj", "discarded", files={
            "discarded.pdf": "x",
            "panels/panel_index.json": {"panels": [{"uid": "a"}]},
        })
        row = W.scan_projects(tmp_path)["projects"][0]
        assert row["n_image_run"] == 1
        assert row["n_image_discarded"] == 1
        assert row["n_image_run"] + row["n_image_discarded"] == 2


def test_refresh_index_paper_picks_up_a_completed_review(tmp_path):
    root = tmp_path / "papers"
    proj = root / "cerebrolysin_papers"
    paper = _paper(proj, "10.1--x", files={"x.pdf": "x"})
    snap = tmp_path / "index.json"
    snap.write_text(json.dumps(W.scan_projects(root)))
    assert json.loads(snap.read_text())["projects"][0]["corpus"]["papers"][0][
        "review"]["paper_status"] == "unreviewed"
    (paper / "review.json").write_text(json.dumps({
        "schema_version": "1.1",
        "paper": {"status": "complete", "reviewed_by": "Dan Elton",
                  "reviewed_at": "2026-08-19T00:00:00Z"},
        "issues": {},
    }))
    W.refresh_index_paper(paper, index_path=snap)
    row = json.loads(snap.read_text())["projects"][0]["corpus"]["papers"][0]
    assert row["review"]["paper_status"] == "complete"
    assert json.loads(snap.read_text())["projects"][0]["n_human_reviewed"] == 1


def test_refresh_index_paper_fills_n_findings_after_a_run(tmp_path):
    """The table reads the snapshot. A finished run must appear in it."""
    root = tmp_path / "papers"
    proj = root / "cerebrolysin_papers"
    paper = _paper(proj, "10.1--x", files={"x.pdf": "x"})
    idx = W.scan_projects(root)
    assert idx["projects"][0]["corpus"]["papers"][0]["n_findings"] is None
    snap = tmp_path / "index.json"
    snap.write_text(json.dumps(idx))
    (paper / "forensic_review_grok-4-6_08_19_2026").mkdir()
    (paper / "forensic_review_grok-4-6_08_19_2026" / "report.json").write_text(
        json.dumps({"verdict": "unresolved",
                    "findings": [{"severity": "suspicious"},
                                 {"severity": "suspicious"},
                                 {"severity": "indeterminate"}]}))
    got = W.refresh_index_paper(paper, index_path=snap)
    assert got["updated"] is True
    assert got["n_findings"] == 3
    after = json.loads(snap.read_text())
    row = after["projects"][0]["corpus"]["papers"][0]
    assert row["n_findings"] == 3
    assert row["n_runs"] == 1
    assert after["projects"][0]["n_agent_run"] == 1


def test_image_finding_count_is_none_when_nothing_was_kept(tmp_path):
    d = _paper(tmp_path, files={"x.pdf": "x",
                                "panels/panel_index.json": {"panels": [{}, {}]}})
    assert W.scan_paper(d)["n_image_findings"] is None


# Detector/legacy verdicts alone never satisfy mandatory AI publication.
@pytest.mark.usefixtures("image_package")
def test_image_finding_count_reads_a_retained_detector_file(tmp_path):
    d = _paper(tmp_path, files={
        "x.pdf": "x",
        "image_duplication_findings.json": {
            "n_duplicate_groups": 2,
            "duplicate_groups": [{"kind": "a"}, {"kind": "b"}],
        },
    })
    rec = W.scan_paper(d)
    assert rec["n_image_findings"] == 0
    assert rec["n_findings"] is None, "image-only run is not a numeric sweep"


def test_image_finding_count_ignores_an_orphan_manifest(tmp_path):
    """A leftover exhibit is not a detector result.

    55 Masliah papers had Aug-18 `review_manifest.json` and no
    `image_duplication_findings.json`. Counting the manifest put 264
    groups on the table from a pass the current detector never kept.
    """
    d = _paper(tmp_path, files={
        "x.pdf": "x",
        "panels/review/review_manifest.json": {
            "groups": [{"group_index": 1}, {"group_index": 2}],
        },
    })
    assert W.scan_paper(d)["n_image_findings"] is None


@pytest.mark.usefixtures("image_package")
def test_image_finding_count_sets_furniture_aside(tmp_path):
    """Furniture rows live in `duplicate_groups` and are not duplication.

    (Renamed 2026-09-08: the groups LIST now wins over the
    `n_duplicate_groups` scalar whenever it is present, because only the
    list carries adjudication verdicts. The scalar remains the fallback —
    see test_image_finding_count_scalar_is_the_fallback.)"""
    d = _paper(tmp_path, files={
        "x.pdf": "x",
        "image_duplication_findings.json": {
            "n_duplicate_groups": 1,
            "duplicate_groups": [
                {"kind": "identical_stream", "duplication_evidence": True},
                {"kind": "chart_furniture", "duplication_evidence": False},
                {"kind": "chart_furniture", "duplication_evidence": False},
            ],
        },
        "panels/review/review_manifest.json": {
            "groups": [{}, {}, {}],
        },
    })
    assert W.scan_paper(d)["n_image_findings"] == 0


@pytest.mark.usefixtures("image_package")
def test_image_finding_count_zero_is_a_kept_empty_result(tmp_path):
    d = _paper(tmp_path, files={
        "x.pdf": "x",
        "image_duplication_findings.json": {
            "n_duplicate_groups": 0, "duplicate_groups": [],
        },
    })
    assert W.scan_paper(d)["n_image_findings"] == 0


@pytest.mark.usefixtures("image_package")
def test_image_finding_count_is_verdict_aware(tmp_path):
    """The column answers "what did the adjudicator leave suspicious", not
    "what is still standing". Measured 2026-09-08 on the fully-adjudicated
    discovery corpus: the standing count showed 834 groups on 180 papers
    where only 344 on 128 were `unexplained` — the rest were
    `insufficient_evidence`, which stands but is not an accusation. Dan:
    "it seems wrong right now."
    """
    d = _paper(tmp_path, files={
        "x.pdf": "x",
        "image_duplication_findings.json": {
            # The scalar counts ALL standing groups (3) and must NOT win.
            "n_duplicate_groups": 3,
            "duplicate_groups": [
                {"kind": "transformed_match",
                 "adjudication": {"verdict": "unexplained"}},
                # Nobody judged this one: it counts. "Nobody looked"
                # rendered as 0 is absence read as evidence.
                {"kind": "identical_stream"},
                # Couldn't judge: stands, but leaves the headline number
                # and is reported separately.
                {"kind": "near_duplicate_phash",
                 "adjudication": {"verdict": "insufficient_evidence"}},
                # Cleared: gone from both numbers.
                {"kind": "transformed_match", "duplication_evidence": False,
                 "adjudication": {"verdict": "explained"}},
            ],
        },
    })
    rec = W.scan_paper(d)
    assert rec["n_image_findings"] == 0
    assert rec["n_image_undecided"] == 0


@pytest.mark.usefixtures("image_package")
def test_image_finding_count_scalar_is_the_fallback(tmp_path):
    """An older retained file may carry only the scalar; it cannot see
    verdicts, so it stands in for the suspicious count rather than
    reporting None (which would read as "nothing was kept")."""
    d = _paper(tmp_path, files={
        "x.pdf": "x",
        "image_duplication_findings.json": {"n_duplicate_groups": 4},
    })
    rec = W.scan_paper(d)
    assert rec["n_image_findings"] == 0
    assert rec["n_image_undecided"] == 0


def test_image_finding_undecided_is_none_when_nothing_was_kept(tmp_path):
    d = _paper(tmp_path, files={"x.pdf": "x"})
    rec = W.scan_paper(d)
    assert rec["n_image_findings"] is None
    assert rec["n_image_undecided"] is None


def test_n_findings_is_none_when_there_is_no_run(tmp_path):
    d = _paper(tmp_path, files={"x.pdf": "x"})
    assert W.scan_paper(d)["n_findings"] is None


def test_n_findings_zero_is_a_count_not_an_absence(tmp_path):
    d = _paper(tmp_path, files={"x.pdf": "x"})
    (d / "forensic_review").mkdir()
    (d / "forensic_review" / "report.json").write_text(
        '{"verdict":"unresolved","findings":[]}')
    assert W.scan_paper(d)["n_findings"] == 0


class TestAViewIsNotAReview:
    """Opening a paper is not judging it.

    The workbench records a view on every page open. Nothing about that may
    move the human-review state: not the status, not the decision count, not
    the corpus totals, and NOT the work queue -- `sort_papers` ranks
    unreviewed before reviewed off `review.reviewed`, which is True merely
    because `review.json` exists. That coupling is why the view record lives
    in its own `views.json` and never inside the decision file.
    """

    def _viewed(self, tmp_path, **kw):
        from forensic_metascience_ai_toolkit.views_io import record_view
        d = _paper(tmp_path, files={"x.pdf": "x"})
        record_view(d, at="2026-08-22T10:00:00Z", **kw)
        return d

    def test_a_view_is_recorded_with_its_viewer(self, tmp_path):
        rec = W.scan_paper(self._viewed(tmp_path, viewer="Dan Elton"))
        assert rec["viewed"] == {"viewed": True, "n_views": 1,
                                 "first_at": "2026-08-22T10:00:00Z",
                                 "last_at": "2026-08-22T10:00:00Z",
                                 "viewers": ["Dan Elton"],
                                 "source": "recorded"}

    def test_an_anonymous_view_still_counts(self, tmp_path):
        # "Anyone who opens it" was the requirement; a session with no name
        # set is still somebody looking.
        rec = W.scan_paper(self._viewed(tmp_path))
        assert rec["viewed"]["viewed"] is True
        assert rec["viewed"]["viewers"] == [None]

    def test_a_view_does_not_make_a_paper_reviewed(self, tmp_path):
        rec = W.scan_paper(self._viewed(tmp_path, viewer="Dan Elton"))
        assert rec["review"]["reviewed"] is False
        assert rec["review"]["paper_status"] == "unreviewed"
        assert rec["review"]["n_decisions"] == 0
        T = W._totals([rec])
        assert T["human_review"]["complete"] == 0
        assert T["human_review"]["in_progress"] == 0
        assert T["human_review"]["unreviewed"] == 1
        assert T["n_viewed"] == 1

    def test_a_view_does_not_reorder_the_work_queue(self, tmp_path):
        # `sort_papers` puts unreviewed first. A paper somebody merely opened
        # must not be demoted past the papers nobody has touched.
        from forensic_metascience_ai_toolkit.views_io import record_view
        a = _paper(tmp_path, name="10.1234--a", files={"x.pdf": "x"})
        b = _paper(tmp_path, name="10.1234--b", files={"x.pdf": "x"})
        before = [p["dir"] for p in
                  W.sort_papers([W.scan_paper(a), W.scan_paper(b)])]
        record_view(a, viewer="Dan Elton", at="2026-08-22T10:00:00Z")
        after = [p["dir"] for p in
                 W.sort_papers([W.scan_paper(a), W.scan_paper(b)])]
        assert before == after

    def test_a_paper_nobody_opened_is_false_not_unknown(self, tmp_path):
        d = _paper(tmp_path, files={"x.pdf": "x"})
        assert W.scan_paper(d)["viewed"] == {
            "viewed": False, "n_views": 0, "first_at": None, "last_at": None,
            "viewers": [], "source": "none"}
        assert W._totals([W.scan_paper(d)])["n_viewed"] == 0

    def test_a_reviewed_paper_was_open_even_with_no_view_on_file(self,
                                                                tmp_path):
        # MEASURED 2026-08-22: 20 papers in the corpora are marked complete
        # and view tracking did not exist when they were reviewed. Reporting
        # those as never-opened states our missing record as a fact about the
        # work.
        d = _paper(tmp_path, files={
            "x.pdf": "x",
            "review.json": {"schema_version": "2.0",
                            "paper": {"status": "complete",
                                      "reviewed_by": "Dan Elton",
                                      "reviewed_at": "2026-08-01T09:00:00Z"}}})
        v = W.scan_paper(d)["viewed"]
        assert v["viewed"] is True
        assert v["source"] == "inferred_from_review"
        assert v["viewers"] == ["Dan Elton"]
        assert v["last_at"] == "2026-08-01T09:00:00Z"
        # Not a view count -- we know it was open, not how often.
        assert v["n_views"] == 0

    def test_a_recorded_view_outranks_the_inference(self, tmp_path):
        from forensic_metascience_ai_toolkit.views_io import record_view
        d = _paper(tmp_path, files={
            "x.pdf": "x",
            "review.json": {"schema_version": "2.0",
                            "paper": {"status": "complete",
                                      "reviewed_by": "Dan Elton"}}})
        record_view(d, viewer="Someone Else", at="2026-08-22T10:00:00Z")
        v = W.scan_paper(d)["viewed"]
        assert v["source"] == "recorded"
        assert v["viewers"] == ["Someone Else"]

    def test_an_unreadable_record_is_unknown_not_unviewed(self, tmp_path):
        d = _paper(tmp_path, files={"x.pdf": "x", "views.json": "{ torn"})
        v = W.scan_paper(d)["viewed"]
        assert v["source"] == "unreadable"
        # None, never False: a torn file read as "nobody looked" is the
        # substitution this toolkit exists to catch.
        assert v["viewed"] is None
        assert v["n_views"] is None
        T = W._totals([W.scan_paper(d)])
        assert T["n_viewed"] == 0
        assert T["n_viewed_unknown"] == 1


class TestTheNonImageCountIsNotTheTotal:
    """The project table shows image findings in their own column, so the
    other column must not count them again.

    MEASURED 2026-08-21 across the paper corpora in the sibling repo: of
    masliah_papers' 311 retained problem findings, 310 came from the image
    track. `Findings` and `Image findings` were the same number twice, and a
    reader scanning the table read two independent signals where there was
    one.
    """

    def _v2(self, tmp_path, findings):
        d = _paper(tmp_path, dirs=("forensic_review",))
        (d / "forensic_review" / "findings.v2.json").write_text(json.dumps({
            "schema_version": "2.0", "findings": findings,
            "adjudication": {"ran": True, "verdict": "unresolved"}}))
        return d

    def test_an_image_track_finding_is_counted_in_the_total_not_the_column(
            self, tmp_path):
        d = self._v2(tmp_path, [
            {"technique": "analyze_paper_images", "producer": "image_track",
             "outcome": "problem", "severity": 5},
            {"technique": "grim_check", "producer": "tool_expert",
             "outcome": "problem", "severity": 6},
        ])
        rec = W.scan_paper(d)
        assert rec["n_findings"] == 2
        assert rec["n_non_image_findings"] == 1

    def test_an_image_only_paper_reports_zero_non_image_findings(self, tmp_path):
        d = self._v2(tmp_path, [
            {"technique": "analyze_paper_images", "producer": "image_track",
             "outcome": "problem", "severity": 4},
        ])
        rec = W.scan_paper(d)
        assert rec["n_findings"] == 1
        # Zero, not None: the run happened and found nothing OUTSIDE the
        # images. An absent count would read as "not checked".
        assert rec["n_non_image_findings"] == 0

    def test_the_producer_is_believed_over_a_migrated_technique_name(self,
                                                                    tmp_path):
        # A migrated record calls it `analyze_paper_images`; a v1 report row
        # calls the same thing `image_duplication`. Both are the image track.
        d = self._v2(tmp_path, [
            {"technique": "image_duplication", "outcome": "problem",
             "severity": 3},
        ])
        assert W.scan_paper(d)["n_non_image_findings"] == 0

    def test_a_report_row_is_traced_through_the_ids_it_merged(self, tmp_path):
        # v1 report findings carry no `technique` at all.
        d = _paper(tmp_path, dirs=("forensic_review",))
        (d / "forensic_review" / "report.json").write_text(json.dumps({
            "verdict": "unresolved", "findings": [
                {"title": "panels repeat", "severity": "suspicious",
                 "stage1_finding_ids": ["IMGDUP-1", "IMGDUP-2"]},
                {"title": "a mean is impossible", "severity": "impossible",
                 "stage1_finding_ids": ["S1-4"]},
                {"title": "an image finding the sweep also numbered",
                 "severity": "suspicious",
                 "stage1_finding_ids": ["IMGDUP-3", "S1-9"]},
            ]}))
        rec = W.scan_paper(d)
        assert rec["n_findings"] == 3
        # The mixed row says something about the NUMBERS too, so it stays in
        # the non-image count; only the image-only row leaves.
        assert rec["n_non_image_findings"] == 2

    def test_no_run_leaves_the_count_absent(self, tmp_path):
        d = _paper(tmp_path, files={"x.pdf": "x"})
        assert W.scan_paper(d)["n_non_image_findings"] is None


class TestTheIndexNamesTheVersionThatProducedTheRun:
    """Two reviews across a MINOR boundary are not comparable (CHANGELOG.md),
    so the table has to be able to say which release it is showing."""

    def test_the_release_reaches_the_paper_record(self, tmp_path):
        d = _paper(tmp_path, dirs=("forensic_review",))
        (d / "forensic_review" / "report.json").write_text(
            '{"verdict":"unresolved","findings":[]}')
        (d / "forensic_review" / "run_meta.json").write_text(
            '{"version": "1.3.0", "analysed_at": "2026-08-21 10:00 UTC"}')
        assert W.scan_paper(d)["pipeline_version"] == "1.3.0"

    def test_a_run_that_recorded_no_version_is_none_not_a_guess(self, tmp_path):
        d = _paper(tmp_path, dirs=("forensic_review",))
        (d / "forensic_review" / "report.json").write_text(
            '{"verdict":"unresolved","findings":[]}')
        assert W.scan_paper(d)["pipeline_version"] is None

    def test_no_run_at_all_is_none(self, tmp_path):
        d = _paper(tmp_path, files={"x.pdf": "x"})
        assert W.scan_paper(d)["pipeline_version"] is None


def test_text_channel_counts_findings_rows_not_a_missing_top_level_key(tmp_path):
    d = _paper(tmp_path, dirs=("forensic_review",), files={
        "forensic_review/text_forensics.json": {
            "schema_version": "1.0",
            "findings_rows": [{"id": "TP-1"}, {"id": "TP-2"}],
            "result": {"matches": [{}, {}, {}, {}]},
        },
    })
    ch = W.text_channel(d, W.review_dirs(d))
    assert ch["state"] == "ran"
    assert ch["n_rows"] == 2
    assert "2 tortured-phrase row(s)" == ch["detail"]
    assert "0 fingerprint" not in ch["detail"]


def test_text_channel_falls_back_to_result_matches(tmp_path):
    d = _paper(tmp_path, dirs=("forensic_review",), files={
        "forensic_review/text_forensics.json": {
            "result": {"matches": [{}, {}]},
        },
    })
    ch = W.text_channel(d, W.review_dirs(d))
    assert ch["n_rows"] == 2
    assert "fingerprint match(es)" in ch["detail"]


def test_figures_beside_the_paper_count_without_a_review_dir(tmp_path):
    d = _paper(tmp_path, dirs=("figures",), files={"x.pdf": "x"})
    assert W.figures_channel(d, [])["state"] == "ran"


class TestPhysicalPaperCopiesDedupe:
    """A batch script left a physical copy of a paper in grok_run/ beside
    the top-level original (masliah, measured 2026-08-21); counting both
    doubled every one of its findings in the denominators, and
    corpus-stats --verify caught file mode disagreeing with the database
    by exactly one paper's rows."""

    def _mk(self, root, rel, when):
        import json
        d = root / rel
        (d / "forensic_review").mkdir(parents=True)
        (d / "forensic_review" / "run_meta.json").write_text(
            json.dumps({"analysed_at": when}))
        (d / "some.pdf").write_text("x")
        return d

    def test_the_newer_copy_wins_wherever_it_sits(self, tmp_path):
        self._mk(tmp_path, "10.1--x", "2026-08-01 00:00 UTC")
        newer = self._mk(tmp_path, "grok_run/10.1--x", "2026-08-20 00:00 UTC")
        got = W.iter_paper_dirs(tmp_path)
        assert [d for d in got if d.name == "10.1--x"] == [newer], (
            "the copy whose newest run is newest is the one the DB's "
            "current-run view would serve; file mode must pick the same")

    def test_a_tie_prefers_the_top_level_copy(self, tmp_path):
        top = self._mk(tmp_path, "10.2--y", "2026-08-10 00:00 UTC")
        self._mk(tmp_path, "grok_run/10.2--y", "2026-08-10 00:00 UTC")
        got = W.iter_paper_dirs(tmp_path)
        assert [d for d in got if d.name == "10.2--y"] == [top]

    def test_distinct_names_are_untouched(self, tmp_path):
        self._mk(tmp_path, "10.3--a", "2026-08-01 00:00 UTC")
        self._mk(tmp_path, "done/10.4--b", "2026-08-01 00:00 UTC")
        names = {d.name for d in W.iter_paper_dirs(tmp_path)}
        assert {"10.3--a", "10.4--b"} <= names


@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize("export_suffix", ["_images", "_figures"])
def test_fetchpdf_image_directories_do_not_hide_papers(tmp_path, nested, export_suffix):
    """Batch2's first smoke run selected 1/4 papers after image extraction."""
    root = tmp_path / "grok_run" if nested else tmp_path
    slug = "10.1038--s41598-019-56545-1"
    paper = _paper(root, slug, files={f"{slug}.pdf": "pdf", "metadata.json": {}},
                   dirs=(f"{slug}{export_suffix}", f"{slug}_supplementary_info_1_images", "pmc_figures"))
    assert W.iter_paper_dirs(tmp_path) == [paper]
    assert W.looks_like_paper(paper)
    assert not W._has_paper_children(paper)
    assert all(not W.looks_like_paper(child) for child in paper.iterdir() if child.is_dir())


class TestStubPdfVisibility:
    """MEASURED 2026-08-22: `10.1016--j.neuroscience.2024.05.006` holds a
    1.9 MB ONE-page ScienceDirect preview stub beside a full-text XML, and
    the workbench said `pdf: yes` -- inviting the reader to believe the
    figures were available to every image check. Page count, not file size,
    is the tell."""

    def _pdf_bytes(self, n_pages):
        fitz = pytest.importorskip("fitz")
        doc = fitz.open()
        for _ in range(n_pages):
            doc.new_page()
        data = doc.tobytes()
        doc.close()
        return data

    def _paper_with_pdf(self, tmp_path, n_pages, with_xml=True):
        d = _paper(tmp_path, files={"body.md": "text"})
        (d / "p.pdf").write_bytes(self._pdf_bytes(n_pages))
        if with_xml:
            (d / "p.xml").write_text("<article/>")
        return d

    def test_a_one_page_pdf_beside_xml_is_a_suspect_stub(self, tmp_path):
        src = W.scan_paper(self._paper_with_pdf(tmp_path, 1))["sources"]
        assert src["pdf_suspect_stub"] is True
        assert src["main_pdf_pages"] == 1

    def test_a_full_pdf_is_not_flagged(self, tmp_path):
        src = W.scan_paper(self._paper_with_pdf(tmp_path, 9))["sources"]
        assert "pdf_suspect_stub" not in src
        assert src["main_pdf_pages"] == 9

    def test_no_xml_means_no_page_probe(self, tmp_path):
        # Without an XML the stub-ness is neither decidable as a stub-of-a-
        # held-paper nor actionable (nothing proves full text exists), and
        # probing every PDF would slow the whole corpus scan.
        src = W.scan_paper(
            self._paper_with_pdf(tmp_path, 1, with_xml=False))["sources"]
        assert "main_pdf_pages" not in src
        assert "pdf_suspect_stub" not in src

    def test_missing_fitz_reports_unknown_not_a_claim(self, tmp_path,
                                                      monkeypatch):
        import builtins
        d = self._paper_with_pdf(tmp_path, 1)
        real_import = builtins.__import__

        def no_fitz(name, *a, **k):
            if name == "fitz":
                raise ImportError("no fitz")
            return real_import(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", no_fitz)
        src = W.scan_paper(d)["sources"]
        assert src["main_pdf_pages"] is None
        assert "pdf_suspect_stub" not in src


class TestStubProbeIsShared:
    """One probe, three surfaces (scanner, pre-spend warning, run
    limitation) -- so they cannot drift into answering 'was the paper
    actually here' differently."""

    def test_sources_delegates_to_the_probe(self, tmp_path, monkeypatch):
        d = _paper(tmp_path, files={"body.md": "t", "p.xml": "<a/>"})
        (d / "p.pdf").write_bytes(b"%PDF-fake")
        monkeypatch.setattr(W, "probe_main_pdf_stub",
                            lambda *a, **k: {"main_pdf_pages": 1,
                                             "pdf_suspect_stub": True})
        src = W.scan_paper(d)["sources"]
        assert src["pdf_suspect_stub"] is True
        assert src["main_pdf_pages"] == 1

    def test_probe_is_none_without_pdf_or_xml(self, tmp_path):
        d = _paper(tmp_path, files={"body.md": "t", "p.xml": "<a/>"})
        assert W.probe_main_pdf_stub(d) is None      # xml, no pdf
        d2 = _paper(tmp_path, name="10.1234--two", files={"body.md": "t"})
        (d2 / "p.pdf").write_bytes(b"%PDF-fake")
        assert W.probe_main_pdf_stub(d2) is None     # pdf, no xml


def test_author_sessions_are_distinct_projects_without_workspace_recursion(tmp_path):
    author = tmp_path / 'author'
    _paper(author, 'source', files={'p.pdf': 'x'})
    session = author / 'analysis_sessions' / 'checked'
    session.mkdir(parents=True)
    (session / 'population.json').write_text('{}')
    _paper(session / 'corpus', 'selected', files={'p.pdf': 'x'})
    _paper(session / 'corpus' / '.analysis_runs' / 'work', 'hidden', files={'p.pdf': 'x'})
    rows = {r['name']: r for r in W.scan_projects(tmp_path)['projects']}
    assert set(rows) == {'author', 'author__checked'}
    assert [p['dir'] for p in rows['author__checked']['corpus']['papers']] == ['selected']
    assert rows['author__checked']['root'] == str(session / 'corpus')


def test_project_discovery_does_not_rebuild_image_evidence(tmp_path,monkeypatch):
    _paper(tmp_path/'author','paper',files={'p.pdf':'x','image_duplication_findings.json':{'duplicate_groups':[]}})
    def forbidden(*args,**kwargs):
        raise AssertionError('Discovery must not reconstruct publication evidence')
    monkeypatch.setattr(W,'image_finding_counts',forbidden)
    monkeypatch.setattr(W,'evidence_assets',forbidden)
    result=W.scan_projects(tmp_path)
    assert not result['projects'][0]['corpus']['errors']
    assert result['projects'][0]['corpus']['papers'][0]['n_image_findings'] is None


class TestAnUnreportedCostIsNotFree:
    """Codex reports tokens only, so a gpt-5.6-terra review recorded
    total_cost_usd 0.0 (2026-10-11). Unknown is not $0.00."""

    def test_named_unreported_stages_make_the_cost_unknown(self):
        assert W._recorded_cost({"total_cost_usd": 1.2, "llm_backend": "claude",
                                 "cost_unreported_stages": ["tool_agent"]}) is None

    def test_an_older_codex_run_with_a_zero_is_unknown(self):
        assert W._recorded_cost({"total_cost_usd": 0.0,
                                 "llm_backend": "codex"}) is None

    def test_a_reported_cost_passes_through(self):
        assert W._recorded_cost({"total_cost_usd": 1.77,
                                 "llm_backend": "grok"}) == 1.77
        assert W._recorded_cost({"total_cost_usd": 0.0,
                                 "llm_backend": "claude"}) == 0.0
