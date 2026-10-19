"""review.json merge: two reviewers, one file, no silent overwrite."""
import json
import pytest

from metascience_agent.review_io import (
    empty_review, image_issue_decisions, load_review, merge_review,
    write_review,
)


def test_absent_file_is_unreviewed_not_withheld(tmp_path):
    r = load_review(tmp_path)
    assert r["paper"]["status"] == "unreviewed"
    assert r["issues"] == {}


def test_merge_does_not_drop_the_other_reviewers_issue(tmp_path):
    current = {
        "schema_version": "1.1",
        "paper": {"status": "in_progress"},
        "issues": {
            "numeric:1": {"decision": "correct", "reviewer": "Dan Elton"},
        },
    }
    merged = merge_review(current, {
        "issue_id": "image:IMGDUP-2",
        "decision": "false_positive_same_condition",
        "reviewer": "Other",
    })
    assert merged["issues"]["numeric:1"]["decision"] == "correct"
    assert merged["issues"]["image:IMGDUP-2"]["decision"] \
        == "false_positive_same_condition"


def test_unknown_decision_is_refused():
    merged = merge_review(empty_review(), {
        "issue_id": "numeric:1",
        "decision": "publish_it",
    })
    assert merged["issues"]["numeric:1"].get("decision") is None


def test_correct_splits_are_accepted_and_legacy_correct_survives():
    minor = merge_review(empty_review(), {
        "issue_id": "numeric:1",
        "decision": "correct_minor",
    })
    assert minor["issues"]["numeric:1"]["decision"] == "correct_minor"
    significant = merge_review(empty_review(), {
        "issue_id": "numeric:2",
        "decision": "correct_significant",
    })
    assert significant["issues"]["numeric:2"]["decision"] == \
        "correct_significant"
    legacy = merge_review(
        {"schema_version": "1.1",
         "paper": {"status": "in_progress"},
         "issues": {"numeric:1": {"decision": "correct"}}},
        {},
    )
    assert legacy["issues"]["numeric:1"]["decision"] == "correct"


def test_schema_1_0_findings_are_promoted():
    r = merge_review(
        {"schema_version": "1.0",
         "findings": {"3": {"decision": "correct", "reviewer": "x"}}},
        {},
    )
    assert "numeric:3" in r["issues"]
    assert r["paper"]["status"] == "in_progress"
    merged = merge_review(
        {"schema_version": "1.0", "findings": {"3": {"decision": "correct"}}},
        {"issue_id": "numeric:1", "decision": "correct"},
    )
    assert "findings" in merged, "1.0 keys must survive a 1.1 write"


def test_schema_1_0_imgdup_findings_are_image_issues():
    """113 Masliah image labels were stored as `findings.IMGDUP-N` with
    `false_positive`. Promoting them as `numeric:` showed the arithmetic
    buttons and left `n_human_reviewed` at 0."""
    r = merge_review(
        {"schema_version": "1.0",
         "findings": {
             "IMGDUP-2": {"decision": "false_positive",
                          "reviewer": "workbench"}}},
        {},
    )
    assert "image:IMGDUP-2" in r["issues"]
    assert "numeric:IMGDUP-2" not in r["issues"]
    assert r["issues"]["image:IMGDUP-2"]["decision"] == \
        "false_positive_other"


def test_complete_is_not_implied_by_one_label():
    merged = merge_review(empty_review(), {
        "issue_id": "numeric:1",
        "decision": "correct",
        "reviewer": "Dan Elton",
    })
    assert merged["paper"]["status"] == "in_progress"


def test_image_issue_decisions_reads_promoted_1_0_labels(tmp_path):
    paper = tmp_path / "10.1--x"
    paper.mkdir()
    (paper / "review.json").write_text(json.dumps({
        "schema_version": "1.0",
        "findings": {
            "IMGDUP-1": {"decision": "false_positive"},
            "3": {"decision": "correct"},
        },
    }))
    dec = image_issue_decisions(paper)
    assert dec == {"IMGDUP-1": "false_positive_other"}


def test_paper_level_pubpeer_survives_a_later_complete(tmp_path):
    """These five comments were paper-level posts. Completing the review
    must not drop the URL, and a javascript: href must not be stored."""
    paper = tmp_path / "10.1--x"
    paper.mkdir()
    write_review(paper, {
        "paper": {
            "submitted_to_pubpeer": True,
            "pubpeer_url": "https://pubpeer.com/publications/ABC#1",
            "pubpeer_note": "Eight duplicated numbers.",
        },
        "issue_id": "numeric:1",
        "decision": "correct",
        "submitted_to_pubpeer": True,
        "pubpeer_url": "javascript:alert(1)",
    })
    write_review(paper, {"paper": {"status": "complete",
                                   "reviewed_by": "Dan Elton",
                                   "reviewed_at": "2026-08-16T12:00:00Z"}})
    r = load_review(paper)
    assert r["paper"]["status"] == "complete"
    assert r["paper"]["submitted_to_pubpeer"] is True
    assert r["paper"]["pubpeer_url"] == "https://pubpeer.com/publications/ABC#1"
    assert r["paper"]["pubpeer_note"] == "Eight duplicated numbers."
    assert r["issues"]["numeric:1"]["submitted_to_pubpeer"] is True
    assert r["issues"]["numeric:1"]["pubpeer_url"] is None


def test_absent_pubpeer_flag_is_not_false():
    """No record is not a decision that nothing was submitted."""
    r = empty_review()
    assert "submitted_to_pubpeer" not in r["paper"]
    merged = merge_review(r, {"paper": {"status": "complete"}})
    assert "submitted_to_pubpeer" not in merged["paper"]


def test_write_is_atomic_and_readable(tmp_path):
    paper = tmp_path / "10.1--x"
    paper.mkdir()
    write_review(paper, {"issue_id": "numeric:1", "decision": "correct",
                         "reviewer": "Dan Elton"})
    on_disk = json.loads((paper / "review.json").read_text())
    assert on_disk["issues"]["numeric:1"]["decision"] == "correct"
    assert not (paper / "review.json.tmp").exists()
    # Second write merges.
    write_review(paper, {"paper": {"status": "complete",
                                   "reviewed_by": "Dan Elton",
                                   "reviewed_at": "2026-08-19T00:00:00Z"}})
    again = load_review(paper)
    assert again["paper"]["status"] == "complete"
    assert again["issues"]["numeric:1"]["decision"] == "correct"


class TestRunScopedReviews20:
    """Multi-report review (webapp_db.md s15): verdicts are RUN-scoped;
    legacy flat verdicts land in the UNSCOPED bucket, never guessed onto a
    run; the flat `issues` key survives as a regenerated compat view."""

    def test_run_scoped_patch_lands_in_its_run(self):
        from metascience_agent.review_io import merge_review
        merged = merge_review({}, {"issue_id": "numeric:3",
                                   "decision": "false_positive",
                                   "run": "forensic_review_v15"})
        assert merged["runs"]["forensic_review_v15"]["issues"][
            "numeric:3"]["decision"] == "false_positive"
        assert merged["issues"]["numeric:3"]["decision"] == "false_positive"

    def test_two_runs_hold_independent_verdicts(self):
        from metascience_agent.review_io import merge_review
        merged = merge_review({}, {"issue_id": "f_1", "decision":
                                   "false_positive", "run": "run_v12"})
        merged = merge_review(merged, {"issue_id": "f_1",
                                       "decision": "correct_significant",
                                       "run": "run_v15"})
        assert merged["runs"]["run_v12"]["issues"]["f_1"][
            "decision"] == "false_positive"
        assert merged["runs"]["run_v15"]["issues"]["f_1"][
            "decision"] == "correct_significant"

    def test_legacy_flat_issues_become_the_unscoped_bucket(self):
        from metascience_agent.review_io import UNSCOPED_RUN, merge_review
        legacy = {"schema_version": "1.1",
                  "issues": {"image:IMGDUP-1": {"decision": "true_issue"}}}
        merged = merge_review(legacy, {})
        assert merged["runs"][UNSCOPED_RUN]["issues"][
            "image:IMGDUP-1"]["decision"] == "true_issue"
        assert merged["issues"]["image:IMGDUP-1"]["decision"] == "true_issue"

    def test_run_scoped_wins_the_compat_view_over_unscoped(self):
        from metascience_agent.review_io import merge_review
        legacy = {"issues": {"numeric:3": {"decision": "correct"}}}
        merged = merge_review(legacy, {"issue_id": "numeric:3",
                                       "decision": "false_positive",
                                       "run": "run_v15"})
        assert merged["issues"]["numeric:3"]["decision"] == "false_positive"

    def test_run_status_is_per_run(self):
        from metascience_agent.review_io import merge_review
        merged = merge_review({}, {"run": "run_v15",
                                   "run_status": "complete"})
        assert merged["runs"]["run_v15"]["status"] == "complete"


def test_a_view_lives_outside_the_decision_file(tmp_path):
    """A view must never end up inside review.json.

    `review_state` answers `reviewed: True` because the file EXISTS, and
    `sort_papers` ranks the work queue off that answer -- so a view written
    here would silently demote every paper anyone merely opened. Pinned so a
    later "tidy up, one file per paper" patch cannot undo the separation
    without failing a test that says why.
    """
    from metascience_agent.views_io import record_view

    write_review(tmp_path, {"issue_id": "numeric:1",
                            "decision": "correct_minor"})
    record_view(tmp_path, viewer="Dan Elton", at="2026-08-22T10:00:00Z")
    on_disk = json.loads((tmp_path / "review.json").read_text())
    assert "views" not in on_disk
    assert "viewers" not in on_disk
    assert on_disk["issues"]["numeric:1"]["decision"] == "correct_minor"
    assert (tmp_path / "views.json").is_file()


@pytest.mark.usefixtures("image_package")
@pytest.mark.parametrize("decision", ["false_positive", "false_positive_scale_bar", "false_positive_channels", "false_positive_logo"])
def test_generic_image_false_positive_survives_save_and_reload(tmp_path, decision):
    from metascience_agent.review_io import IMAGE_DECISIONS
    from metascience_observatory_image_analysis.image_forensics.benchmark import FP_DECISIONS
    assert decision in IMAGE_DECISIONS
    assert decision in FP_DECISIONS
    write_review(tmp_path, {
        "issue_id": "image:IMGDUP-1",
        "decision": decision,
        "reviewer": "Bulk reviewer",
    })
    assert image_issue_decisions(tmp_path) == {"IMGDUP-1": decision}
