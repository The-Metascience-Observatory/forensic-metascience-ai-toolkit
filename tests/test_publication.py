"""The public site's gate and snapshot (publication.py). Offline: rows in, files out."""
import json

import pytest

from forensic_metascience_ai_toolkit import publication as P

RNG = {"slug": "tables-rng", "title": "Tables: RNG", "tool": "rngdetect", "sort_order": 0,
       "publish_policy": "ai_triaged", "description": None, "corpus": None, "papers_screened": 10}
IMG = {"slug": "images", "title": "Image reuse", "tool": "images", "sort_order": 1,
       "publish_policy": "human_approved", "description": None, "corpus": None, "papers_screened": None}


def pub(project, doi, state="draft", ai=False, **kw):
    return {"project_slug": project, "doi": doi, "state": state, "ai_eligible": ai,
            "citation": {"title": f"T {doi}", "year": 2020}, "one_line": "x", **kw}


def ev(doi, kind, day, **kw):
    return {"doi": doi, "kind": kind, "occurred_on": day, "project_slug": None, **kw}


class TestGate:
    @pytest.mark.parametrize("policy,state,ai,shown", [
        ("ai_triaged", "draft", True, True),
        ("ai_triaged", "draft", False, False),       # category A, artefact, likely innocent
        ("ai_triaged", "withdrawn", True, False),    # a person's veto beats the AI
        ("ai_triaged", "published", False, True),
        ("human_approved", "draft", True, False),    # AI eligibility never publishes an image paper
        ("human_approved", "published", False, True),
        ("human_approved", "withdrawn", True, False),
    ])
    def test_gate(self, policy, state, ai, shown):
        assert P.is_public(policy, state, ai) is shown


class TestSnapshot:
    def files(self):
        pubs = [pub("tables-rng", "10.1234/a", ai=True), pub("tables-rng", "10.1234/b", ai=False),
                pub("images", "10.1234/c", ai=True), pub("images", "10.1234/a", state="published"),
                pub("tables-rng", "10.1234/d", state="withdrawn", ai=True)]
        events = [ev("10.1234/a", "authors_emailed", "2026-11-03"), ev("10.1234/a", "ai_reviewed", "2026-11-01"),
                  ev("10.1234/a", "pubpeer_submitted", "2026-11-02", voided_at="2026-11-05"),
                  ev("10.1234/b", "ai_reviewed", "2026-11-01"), ev("10.1234/c", "authors_emailed", "2026-11-01")]
        return P.build_snapshot([RNG, IMG], pubs, events, generated_at="t")

    def test_only_gated_papers_get_a_page(self):
        f = self.files()
        assert sorted(k for k in f if k.startswith("papers/")) == ["papers/10.1234--a.json"]
        assert [r["doi"] for r in f["projects/tables-rng.json"]["papers"]] == ["10.1234/a"]
        assert [r["doi"] for r in f["projects/images.json"]["papers"]] == ["10.1234/a"]
        text = json.dumps(f)
        for hidden in ("10.1234/b", "10.1234/c", "10.1234/d"):
            assert hidden not in text

    def test_counts_match_the_lists(self):
        cards = {c["slug"]: c for c in self.files()["projects.json"]["projects"]}
        assert cards["tables-rng"]["papers_with_findings"] == 1
        assert cards["tables-rng"]["papers_screened"] == 10

    def test_timeline_is_dated_and_skips_voided(self):
        page = self.files()["papers/10.1234--a.json"]
        assert [(e["kind"], e["date"]) for e in page["timeline"]] == [
            ("ai_reviewed", "2026-11-01"), ("authors_emailed", "2026-11-03")]
        assert {e["project"] for e in page["entries"]} == {"tables-rng", "images"}

    def test_review_label(self):
        f = self.files()
        assert f["projects/images.json"]["papers"][0]["review"] == "human"
        only_ai = P.build_snapshot([RNG], [pub("tables-rng", "10.1234/a", ai=True)], [], "t")
        assert only_ai["projects/tables-rng.json"]["papers"][0]["review"] == "ai"


class TestWrite:
    def test_removes_stale_pages_and_ignores_a_new_timestamp(self, tmp_path):
        one = P.build_snapshot([RNG], [pub("tables-rng", "10.1234/a", ai=True)], [], "t1")
        assert P.write_files(one, tmp_path)["added"] == 3
        (tmp_path / "keep.txt").write_text("mine")
        again = P.build_snapshot([RNG], [pub("tables-rng", "10.1234/a", ai=True)], [], "t2")
        assert P.write_files(again, tmp_path) == {"added": 0, "changed": 0, "removed": 0, "unchanged": 3}
        assert json.loads((tmp_path / "projects.json").read_text())["generated_at"] == "t1"
        none = P.build_snapshot([RNG], [pub("tables-rng", "10.1234/a", state="withdrawn", ai=True)], [], "t3")
        counts = P.write_files(none, tmp_path)
        assert counts["removed"] == 1 and not (tmp_path / "papers/10.1234--a.json").exists()
        assert (tmp_path / "keep.txt").exists()


def test_doi_forms():
    assert P.norm_doi("https://doi.org/10.1002/ECE3.10748") == "10.1002/ece3.10748"
    assert P.paper_id("doi:10.1155/2014/198015") == "10.1155--2014--198015"
    with pytest.raises(ValueError):
        P.norm_doi("PMC123")
