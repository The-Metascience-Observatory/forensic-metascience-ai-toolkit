"""Workbench issue list: stage 2 helps, Python is the order the reader sees."""
import json

from forensic_metascience_ai_toolkit.review_issues import (
    _image_where, collect_issues, issue_sort_key, sort_issues,
)


def _num(**kw):
    base = {
        "id": "numeric:1", "kind": "numeric", "title": "x", "plain": "",
        "severity": "suspicious", "consequence": None, "warrant": "logical",
        "rank": 1, "stage1_finding_ids": ["s1"],
    }
    base.update(kw)
    return base


def test_a_flip_outranks_a_harmless_typo_at_the_same_severity():
    issues = sort_issues([
        _num(id="numeric:typo", title="typo", rank=1,
             consequence={"flips_significance": False, "basis": "computed"}),
        _num(id="numeric:flip", title="flip", rank=2,
             consequence={"flips_significance": True, "basis": "computed"}),
    ])
    assert [i["title"] for i in issues] == ["flip", "typo"]
    assert "significance" in issues[0]["priority_reason"]


def test_severity_still_dominates_consequence():
    issues = sort_issues([
        _num(id="numeric:flip", title="flip", severity="suspicious",
             consequence={"flips_significance": True, "basis": "computed"}),
        _num(id="numeric:imp", title="impossible", severity="impossible",
             consequence={"flips_significance": False, "basis": "computed"}),
    ])
    assert issues[0]["title"] == "impossible"


def test_unbacked_field_norm_sorts_after_a_sweep_finding():
    issues = sort_issues([
        _num(id="numeric:norm", title="our norm", warrant="field_norm",
             stage1_finding_ids=[], rank=1),
        _num(id="numeric:tool", title="tool", warrant="logical",
             stage1_finding_ids=["s1"], rank=2),
    ])
    assert [i["title"] for i in issues] == ["tool", "our norm"]


def test_explained_image_sorts_last():
    issues = sort_issues([
        {"id": "image:1", "kind": "image", "title": "explained",
         "severity": "highly_suspicious", "duplication_evidence": False,
         "spans_figures": True, "rank": 1},
        _num(id="numeric:1", title="numeric", severity="suspicious"),
    ])
    assert issues[-1]["title"] == "explained"


def test_image_that_spans_figures_outranks_a_plain_suspicious():
    issues = sort_issues([
        _num(id="numeric:1", title="typo", severity="suspicious",
             consequence={"flips_significance": False, "basis": "computed"}),
        {"id": "image:2", "kind": "image", "title": "spans",
         "severity": None, "duplication_evidence": True,
         "spans_figures": True, "rank": 1},
    ])
    assert issues[0]["title"] == "spans"


def test_text_cannot_outrank_impossible_arithmetic():
    issues = sort_issues([
        {"id": "text:1", "kind": "text", "title": "tortured",
         "severity": "indeterminate", "rank": 1},
        _num(id="numeric:1", title="imp", severity="impossible"),
    ])
    assert issues[0]["title"] == "imp"


def test_collect_issues_reads_a_report(tmp_path):
    paper = tmp_path / "10.1--x"
    (paper / "forensic_review").mkdir(parents=True)
    (paper / "forensic_review" / "report.json").write_text(
        '{"verdict":"unresolved","findings":['
        '{"id":"F1","title":"typo","severity":"suspicious","rank":1,'
        '"plain":"A p-value is off by a digit.",'
        '"consequence":{"flips_significance":false,"basis":"computed"},'
        '"warrant":"logical","stage1_finding_ids":["s1"]},'
        '{"id":"F2","title":"flip","severity":"suspicious","rank":2,'
        '"plain":"The headline result moves.",'
        '"consequence":{"flips_significance":true,"basis":"computed"},'
        '"warrant":"logical","stage1_finding_ids":["s2"]}'
        ']}'
    )
    got = collect_issues(paper)
    assert [i["title"] for i in got["issues"]] == ["flip", "typo"]
    assert got["issues"][0]["id"] == "numeric:F2"
    assert got["latest_run"] == "forensic_review"


def test_sort_key_is_total_on_garbage():
    # Must never raise: a TypeError here blanks the review pane.
    issue_sort_key({})
    issue_sort_key({"kind": "numeric", "consequence": "nope"})


def test_image_where_same_figure_two_pages():
    where, pages = _image_where({
        "figure_labels": ["Figure 2"],
        "placements": {
            "pdf:xref308": [{"page": 5, "figure_label": "Figure 2"}],
            "pdf:xref370": [{"page": 17, "figure_label": "Figure 2"}],
        },
    })
    assert where == "Figure 2 on p. 5 and p. 17"
    assert pages == [5, 17]


def test_image_where_two_figures():
    where, pages = _image_where({
        "figure_labels": ["Figure 1", "Figure 4"],
        "placements": {
            "a": [{"page": 3, "figure_label": "Figure 1"}],
            "b": [{"page": 8, "figure_label": "Figure 4"}],
        },
    })
    assert where == "Figure 1 p. 3 vs Figure 4 p. 8"
    assert pages == [3, 8]


def test_image_where_pages_without_labels():
    where, pages = _image_where({
        "placements": {
            "a": [{"page": 5}],
            "b": [{"page": 17}],
        },
    })
    assert where == "p. 5 and p. 17"
    assert pages == [5, 17]


def test_image_where_no_pages_does_not_invent_page_one():
    where, pages = _image_where({
        "figure_labels": ["Figure 2"],
        "placements": {},
    })
    assert where == "Figure 2"
    assert pages == []


def test_image_where_true_is_not_page_one():
    where, pages = _image_where({
        "placements": {"a": [{"page": True, "figure_label": "Figure 2"}]},
    })
    assert pages == []
    assert where is None


def test_collect_issues_puts_pages_on_image_location(tmp_path):
    paper = tmp_path / "10.1016--j.cell.2013.11.009"
    man = paper / "panels" / "review"
    man.mkdir(parents=True)
    (man / "review_manifest.json").write_text(json.dumps({
        "groups": [{
            "group_index": 1,
            "kind": "near_duplicate_phash",
            "duplication_evidence": True,
            "severity": "suspicious",
            "sentence": "Near-identical phash of two Figure 2 panels.",
            "figure_labels": ["Figure 2"],
            "panels": ["pdf:xref308", "pdf:xref370"],
            "placements": {
                "pdf:xref308": [{"page": 5, "figure_label": "Figure 2",
                                 "bbox": [10, 20, 110, 120]}],
                "pdf:xref370": [{"page": 17, "figure_label": "Figure 2",
                                 "bbox": [12, 22, 112, 122]}],
            },
        }],
    }))
    got = collect_issues(paper)
    img = [i for i in got["issues"] if i["kind"] == "image"]
    assert len(img) == 1
    assert img[0]["location"] == "Figure 2 on p. 5 and p. 17"
    assert img[0]["extras"]["pages"] == [5, 17]


class TestV2RunsAreVisible:
    """A parallel run writes findings.v2.json and report.md but NO
    report.json -- and the reviewer's issue list only read report.json, so
    a fresh parallel run was INVISIBLE and the pane silently served an
    older legacy run (found surfacing the medicina rematch, 2026-08-21)."""

    def _paper(self, tmp_path):
        import json
        d = tmp_path / "forensic_review_parallel_x"
        d.mkdir(parents=True)
        doc = {"schema_version": "2.0", "paper_id": "p", "run_id": "r_" + "a" * 16,
               "adjudication": {"ran": True, "verdict": "does_not_reconcile",
                                "headline_finding_id": "f_" + "1" * 16},
               "findings": [
                   {"finding_id": "f_" + "1" * 16, "producer": "tool_expert",
                    "technique": "grim_check", "outcome": "problem",
                    "severity": 5, "impossible": True, "computed_by": "registry_tool",
                    "title": "the headline row", "description": "d" * 30,
                    "quote": "q", "anchors": [{"kind": "quote", "quote": "verbatim span"}]},
                   {"finding_id": "f_" + "2" * 16, "producer": "science_error",
                    "technique": "internal_contradiction", "outcome": "problem",
                    "severity": 2, "title": "a small one", "description": "d" * 30,
                    "adjudication": {"action": "kept"}},
                   {"finding_id": "f_" + "3" * 16, "producer": "tool_expert",
                    "technique": "grim_check", "outcome": "problem", "severity": None,
                    "title": "merged away", "description": "d" * 30,
                    "adjudication": {"action": "merged", "merged_into": "f_" + "1" * 16}},
                   {"finding_id": "f_" + "4" * 16, "producer": "image_track",
                    "technique": "image_duplication", "outcome": "problem",
                    "severity": 3, "title": "track copy", "description": "d" * 30},
               ]}
        (d / "findings.v2.json").write_text(json.dumps(doc))
        return tmp_path

    def test_a_parallel_run_reaches_the_reviewer(self, tmp_path):
        out = collect_issues(self._paper(tmp_path))
        assert out["latest_run"] == "forensic_review_parallel_x"
        ids = [i["id"] for i in out["issues"]]
        assert "f_" + "1" * 16 in ids, "the headline row must be reviewable"
        assert "f_" + "3" * 16 not in ids, "merged rows ride their parent"
        assert "f_" + "4" * 16 not in ids, \
            "v2 track copies are skipped; the paper-level track files own them"
        top = out["issues"][0]
        assert top["severity_9"] == 5 and top["impossible"] is True
        assert out["headline"]["statement"] == "the headline row"

    def test_run_picker_serves_the_named_run(self, tmp_path):
        root = self._paper(tmp_path)
        out = collect_issues(root, run="forensic_review_parallel_x")
        assert out["latest_run"] == "forensic_review_parallel_x"
        assert out["available_runs"] == ["forensic_review_parallel_x"]
        ghost = collect_issues(root, run="no_such_run")
        assert ghost["latest_run"] == "forensic_review_parallel_x", \
            "an unknown run name falls back rather than blanking the pane"


# --- the database fallback: a run pushed from another machine -------------

def _db_hit(label_corpus="fmt-derik-flagged", matched_by="doi"):
    rec = {"finding_id": "f_1", "outcome": "problem", "severity": 3,
           "producer": "tool_expert", "technique": "check_count_percent",
           "title": "Wear-time weeks: 278 of 324 vs 336",
           "computed_by": "registry_tool",
           "anchors": [{"quote": "278 of 324 weeks", "passage_id": "a",
                        "role": "said"}]}
    merged = {"finding_id": "f_2", "outcome": "problem", "severity": 2,
              "producer": "science_error", "technique": "internal_contradiction",
              "title": "folded into f_1",
              "adjudication": {"action": "merged"}}
    return {"state": "hit", "detail": "1 run(s)", "runs": [{
        "corpus": label_corpus, "dir": "10.1002--jfa2.70171",
        "name": "forensic_review_opus_v1.12.0", "run_uid": "r_b2b1",
        "matched_by": matched_by, "analysed_at": "2026-09-01T12:28:42+00:00",
        "pipeline_version": "1.12.0",
        "doc": {"run_id": "r_b2b1", "findings": [rec, merged],
                "adjudication": {"ran": True, "verdict": "does_not_reconcile",
                                 "paper_severity": 3}}}]}


def test_collect_issues_falls_back_to_the_database(tmp_path, monkeypatch):
    from forensic_metascience_ai_toolkit import db_push
    paper = tmp_path / "FMT-reports_derik-flagged_2026-09-01" / "10.1002--jfa2.70171"
    paper.mkdir(parents=True)
    asked = []
    monkeypatch.setattr(db_push, "fetch_paper_runs",
                        lambda p, **kw: asked.append(p) or _db_hit())
    out = collect_issues(paper)
    assert asked == [paper]
    assert out["source"]["kind"] == "database"
    assert out["source"]["database"]["state"] == "hit"
    # the DOI-matched run is labelled with the corpus it came from
    assert out["latest_run"] == "fmt-derik-flagged/forensic_review_opus_v1.12.0"
    assert out["available_runs"] == [out["latest_run"]]
    assert out["n_runs"] == 1
    # same mapping as the file branch: merged rows fold away, anchors -> passages
    assert [i["title"] for i in out["issues"]] == ["Wear-time weeks: 278 of 324 vs 336"]
    iss = out["issues"][0]
    assert iss["run"] == out["latest_run"]
    assert iss["severity_9"] == 3 and iss["kind"] == "numeric"
    assert iss["passages"][0]["quote"] == "278 of 324 weeks"
    assert iss["stage1_finding_ids"] == ["f_1"]
    run = out["source"]["database"]["runs"][0]
    assert run["verdict"] == "does_not_reconcile" and run["n_findings"] == 2


def test_collect_issues_dir_match_keeps_plain_run_name(tmp_path, monkeypatch):
    from forensic_metascience_ai_toolkit import db_push
    paper = tmp_path / "fmt-derik-flagged" / "10.1002--jfa2.70171"
    paper.mkdir(parents=True)
    monkeypatch.setattr(db_push, "fetch_paper_runs",
                        lambda p, **kw: _db_hit(matched_by="dir"))
    out = collect_issues(paper)
    # review.json scopes verdicts by this name, and db-push's mirror joins
    # it to runs.name -- so an own-corpus run keeps its bare name
    assert out["latest_run"] == "forensic_review_opus_v1.12.0"


def test_collect_issues_reports_an_unreachable_database_in_words(tmp_path, monkeypatch):
    from forensic_metascience_ai_toolkit import db_push
    paper = tmp_path / "corpus" / "10.1002--jfa2.70171"
    paper.mkdir(parents=True)
    monkeypatch.setattr(db_push, "fetch_paper_runs", lambda p, **kw: {
        "state": "unavailable", "detail": "no database URL: set ...", "runs": []})
    out = collect_issues(paper)
    assert out["issues"] == []
    assert out["latest_run"] is None
    assert out["source"] == {"kind": "none", "database": {
        "state": "unavailable", "detail": "no database URL: set ...", "runs": []}}


def test_collect_issues_disk_run_wins_and_skips_the_database(tmp_path, monkeypatch):
    from forensic_metascience_ai_toolkit import db_push
    paper = tmp_path / "corpus" / "p"
    run = paper / "forensic_review"
    run.mkdir(parents=True)
    (run / "findings.v2.json").write_text(json.dumps({"findings": [
        {"finding_id": "f_disk", "outcome": "problem", "severity": 4,
         "producer": "tool_expert", "technique": "grim_check", "title": "disk"}],
        "adjudication": {"ran": True}}))
    monkeypatch.setattr(db_push, "fetch_paper_runs",
                        lambda p, **kw: (_ for _ in ()).throw(AssertionError("db asked")))
    out = collect_issues(paper)
    assert out["source"] == {"kind": "disk", "database": None}
    assert [i["title"] for i in out["issues"]] == ["disk"]
    assert out["latest_run"] == "forensic_review"
