"""The cross-paper adjudicator can only ever downgrade.

It is a SEPARATE pass from the single-paper image adjudicator, deliberately:
that one sees one paper and asks whether the paper explains showing a picture
twice; this one sees two papers, two texts and two bibliographic records, and
asks what the two documents are to each other. Their category enums barely
overlap, and merging them would hand each pass verdicts it cannot justify.

What is pinned here is the part that could hurt someone: a model that could
escalate would be a route to accusing two research groups of copying each
other, bypassing every screen the sweep applies.
"""
from pathlib import Path

import pytest

from metascience_agent.core import prompts
from metascience_agent import quotes as _q
from metascience_observatory_image_analysis.image_forensics.image_corpus import (
    _title_similarity,
    apply_cross_paper_adjudication,
    build_adjudication_prompt,
)


def _match(i=1, **kw):
    m = {
        "a": f"paperA:xref{i}", "b": f"paperB:xref{i}",
        "a_paper": "paperA", "b_paper": "paperB",
        "a_image": f"/tmp/a{i}.png", "b_image": f"/tmp/b{i}.png",
        "a_meta": {"page": 3, "pt": 300.0}, "b_meta": {"page": 4, "pt": 300.0},
        "flip": False,
        "match_stats": {"n_inliers": 120, "rotation_deg": 0.0, "scale": 0.58},
    }
    m.update(kw)
    return m


# `quotes.build_haystack` returns {source_name: text} per paper, so the
# cross-paper structure is one of those per paper -- named sources, not a
# concatenated blob, so a located quote can say WHERE it was found.
# NOTE the `normalise`: `build_haystack` stores normalised text and
# `classify` normalises only the quote, so a hand-built haystack that skips
# it fails every lookup -- which is exactly how a real bug in the driver's
# fallback path was caught here.
HAY = {"paperA": {"body.md": _q.normalise(
           "The animals were the same cohort described previously.")},
       "paperB": {"body.md": _q.normalise(
           "We reproduce Figure 2 from our earlier report.")}}


class TestItCanOnlyDowngrade:
    def test_explained_clears_the_match(self):
        m = [_match()]
        apply_cross_paper_adjudication(m, [{
            "match_index": 1, "verdict": "explained",
            "category": "preprint_or_postprint",
            "explanation": "same work", "images_read": ["/tmp/a1.png"]}], {})
        assert m[0]["reuse_evidence"] is False
        assert m[0]["adjudication"]["category"] == "preprint_or_postprint"

    def test_unexplained_changes_nothing_about_the_match(self):
        m = [_match()]
        before = dict(m[0]["match_stats"])
        apply_cross_paper_adjudication(m, [{
            "match_index": 1, "verdict": "unexplained",
            "category": "undisclosed_reuse", "explanation": "no account",
            "images_read": ["/tmp/a1.png"]}], {})
        assert "reuse_evidence" not in m[0]
        assert m[0]["match_stats"] == before

    def test_no_field_it_writes_can_raise_a_severity(self):
        """The escalation direction is not implemented, so a model asking for
        it changes nothing at all."""
        m = [_match()]
        apply_cross_paper_adjudication(m, [{
            "match_index": 1, "verdict": "explained", "category": "none",
            "explanation": "x", "images_read": ["/tmp/a1.png"],
            "severity": "highly_suspicious", "quarantined": False,
            "duplication_evidence": True, "reuse_evidence": True}], {})
        assert "severity" not in m[0]
        assert m[0].get("reuse_evidence") is False   # only ever downgraded
        assert set(m[0]["adjudication"]) <= {
            "verdict", "category", "explanation", "evidence_quote",
            "quoted_from", "images_read", "quote_verified", "quote_found_in",
            "demoted_because", "quote_check_failed", "quote_source",
            "quote_problem"}

    def test_it_cannot_invent_a_match(self):
        m = [_match()]
        applied = apply_cross_paper_adjudication(m, [
            {"match_index": 7, "verdict": "explained", "category": "none",
             "explanation": "x", "images_read": ["/tmp/a1.png"]},
            {"match_index": 0, "verdict": "explained", "category": "none",
             "explanation": "x", "images_read": ["/tmp/a1.png"]}], {})
        assert applied == []
        assert "adjudication" not in m[0]


class TestAnExplanationMustCostSomething:
    def test_a_quote_in_neither_paper_demotes_the_verdict(self):
        m = [_match()]
        apply_cross_paper_adjudication(m, [{
            "match_index": 1, "verdict": "explained",
            "category": "same_group_companion_paper",
            "evidence_quote": "The rats were purchased from a vendor in Oslo.",
            "explanation": "x", "images_read": ["/tmp/a1.png"]}], HAY)
        rec = m[0]["adjudication"]
        assert rec["verdict"] == "insufficient_evidence"
        assert "could not be located in either paper" in rec["demoted_because"]
        assert "reuse_evidence" not in m[0]

    def test_a_quote_present_in_one_paper_survives_and_names_it(self):
        """Two haystacks is the real cross-paper difference: an explanation
        may legitimately quote either document, and which one matters."""
        m = [_match()]
        apply_cross_paper_adjudication(m, [{
            "match_index": 1, "verdict": "explained",
            "category": "republished_with_attribution",
            "evidence_quote": "We reproduce Figure 2 from our earlier report.",
            "quoted_from": "paperB",
            "explanation": "x", "images_read": ["/tmp/a1.png"]}], HAY)
        rec = m[0]["adjudication"]
        assert rec["verdict"] == "explained"
        assert rec["quote_found_in"] == "paperB"
        assert m[0]["reuse_evidence"] is False

    def test_cleared_without_looking_is_demoted(self):
        m = [_match()]
        apply_cross_paper_adjudication(m, [{
            "match_index": 1, "verdict": "explained",
            "category": "stock_or_clip_art", "explanation": "clip art",
            "images_read": []}], {})
        rec = m[0]["adjudication"]
        assert rec["verdict"] == "insufficient_evidence"
        assert "unseen" in rec["demoted_because"]
        assert "reuse_evidence" not in m[0]


class TestTheEvidenceBundle:
    def _bundle(self, n=2):
        ev = {"paper": "paperA", "title": "A study", "journal": "J", "year": 2020,
              "authors": ["Smith, A"], "doi": "10.1/a", "abstract": "abs A",
              "methods": "We did things.", "methods_note": "", "captions":
              "p3 Figure 2: rat cortex", "findings_json": "",
              "text_for_quote_check": ""}
        evb = dict(ev, paper="paperB", title="A study", year=2022,
                   findings_json="/tmp/findings.json")
        return {"a": ev, "b": evb, "title_similarity": 1.0,
                "same_filename": False,
                "matches": [_match(i) for i in range(1, n + 1)]}

    def test_it_names_both_papers_images_and_the_measurements(self):
        p = build_adjudication_prompt(self._bundle())
        assert "/tmp/a1.png" in p and "/tmp/b2.png" in p
        assert "rotation 0.0 deg" in p and "scale 0.58" in p
        assert "120 consistent keypoints" in p
        assert "match_index 1" in p and "match_index 2" in p

    def test_it_says_when_a_paper_has_no_findings_json(self):
        """Most corpus papers have never been reviewed -- measured, 4 of 37.
        A prompt implying a review exists would invite the model to invent
        one."""
        p = build_adjudication_prompt(self._bundle())
        assert "has not been through a forensic review" in p
        assert "/tmp/findings.json" in p          # the one that does have it

    def test_it_carries_both_papers_text_and_captions(self):
        p = build_adjudication_prompt(self._bundle())
        assert p.count("We did things.") == 2     # Methods of both
        assert "p3 Figure 2: rat cortex" in p
        assert "Title similarity" in p

    def test_a_same_named_pair_is_flagged_as_one_paper_filed_twice(self):
        b = self._bundle()
        b["same_filename"] = True
        assert "SAME paper filed twice" in build_adjudication_prompt(b)


class TestTitleSimilarityIsComputedNotAsked:
    def test_identical_titles_score_one(self):
        t = "Efficacy of Cerebrolysin as Add-On Therapy to Thrombectomy"
        assert _title_similarity(t, t) == 1.0

    def test_unrelated_titles_score_low(self):
        assert _title_similarity(
            "Cerebrolysin in ischaemic stroke recovery",
            "Iron oxide nanoparticles for tumour imaging") < 0.2


class TestThePromptCarriesItsGuards:
    def _p(self):
        return prompts.cross_paper_adjudication_system_prompt()

    def test_downgrade_only_is_stated(self):
        assert "You may only DOWNGRADE" in self._p()

    def test_absence_of_an_explanation_is_not_evidence(self):
        assert "NOT evidence of misconduct" in self._p()

    def test_it_must_admit_when_it_could_not_look(self):
        assert "could not open the images" in self._p()

    def test_it_carries_no_severity_vocabulary(self):
        """Same reasoning as its single-paper sibling: this pass issues no
        severity, so the vocabulary would only be an invitation."""
        p = self._p().lower()
        for word in ("highly_suspicious", "impossible", "indeterminate"):
            assert word not in p

    def test_the_schema_cannot_express_an_escalation(self):
        s = prompts.cross_paper_adjudication_schema()
        item = s["properties"]["verdicts"]["items"]
        assert item["additionalProperties"] is False
        assert "severity" not in item["properties"]
        assert item["properties"]["verdict"]["enum"] == [
            "explained", "unexplained", "insufficient_evidence"]

    def test_undisclosed_reuse_is_the_only_non_innocuous_category(self):
        cats = prompts.cross_paper_adjudication_schema()[
            "properties"]["verdicts"]["items"]["properties"]["category"]["enum"]
        assert "undisclosed_reuse" in cats and "none" in cats
        # the innocuous ones this corpus actually produced
        for c in ("preprint_or_postprint", "shared_atlas_or_template",
                  "stock_or_clip_art", "publisher_furniture"):
            assert c in cats


class TestTheDriverRunsAndFailsOpen:
    """The async path, proven without a paid call.

    `adjudicate_matches` imports `_run_stage` at call time, so patching
    `agent._run_stage` is enough to stand in for the model -- the same seam
    `tests/test_stage_failure_paths.py` uses.
    """

    def _run(self, monkeypatch, stub, matches=None):
        import asyncio
        import json as _json

        from metascience_observatory_image_analysis import runtime as A
        from metascience_observatory_image_analysis.image_forensics import image_corpus as IC

        monkeypatch.setattr(A, "_run_stage", stub)
        m = matches if matches is not None else [_match(1), _match(2)]
        # two matches, ONE pair -> must be ONE call
        res = asyncio.run(IC.adjudicate_matches(
            m, Path("/tmp/nonexistent-corpus"), {}, model="sonnet",
            progress=lambda *_a, **_k: None))
        return m, res

    def test_one_call_per_pair_not_per_match(self, monkeypatch, tmp_path):
        calls = []
        # A clear must cite an exhibit that exists on disk (the guard
        # resolves images_read), so the stub cites a real file.
        img = tmp_path / "a1.png"
        img.write_bytes(b"png")

        async def stub(cmd, prompt, **kw):
            calls.append(prompt)
            return {"result": '{"schema_version":"1.0","verdicts":['
                              '{"match_index":1,"verdict":"explained",'
                              '"category":"stock_or_clip_art",'
                              '"explanation":"clip art",'
                              f'"images_read":["{img}"]}}]}}',
                    "text": "", "cost_usd": 0.01}

        m, res = self._run(monkeypatch, stub)
        assert len(calls) == 1, "two matches in one pair must cost one call"
        assert res["n_verdicts"] == 1 and res["n_cleared"] == 1
        assert m[0]["reuse_evidence"] is False
        assert "reuse_evidence" not in m[1]      # untouched, still reported

    def test_a_crash_leaves_every_match_reported_and_unadjudicated(
            self, monkeypatch):
        async def boom(cmd, prompt, **kw):
            raise TimeoutError("model unavailable")

        m, res = self._run(monkeypatch, boom)
        assert res["n_verdicts"] == 0
        assert all("adjudication" not in h for h in m)
        assert all("reuse_evidence" not in h for h in m)
        assert res["stages"][0]["error_subtype"] == "adjudication_failed"

    def test_unparseable_output_is_recorded_not_guessed(self, monkeypatch):
        async def junk(cmd, prompt, **kw):
            return {"result": "sorry, I could not do that", "text": "",
                    "cost_usd": 0.01}

        m, res = self._run(monkeypatch, junk)
        assert res["n_verdicts"] == 0
        assert all("adjudication" not in h for h in m)
        assert res["stages"][0]["error_subtype"] == "adjudication_unparseable"

    def test_it_asks_for_sonnet(self, monkeypatch):
        seen = {}

        async def stub(cmd, prompt, **kw):
            seen["cmd"] = cmd
            return {"result": '{"schema_version":"1.0","verdicts":[]}',
                    "text": "", "cost_usd": 0.0}

        self._run(monkeypatch, stub)
        # `_build_claude_cmd` returns an Invocation now (the llm_backend
        # merge), not a bare argv -- same two contract points, read off the
        # Invocation: the model, and `Read` as the ONLY tool (no MCP
        # forensic tool may reach this pass).
        inv = seen["cmd"]
        assert "sonnet" in inv.argv
        assert tuple(inv.allowed_tools) == ("Read",)
        tools = inv.argv[inv.argv.index("--tools") + 1]
        assert tools == "Read"
