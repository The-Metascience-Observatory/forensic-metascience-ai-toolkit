"""run_meta must record which model ACTUALLY ran, not which was requested.

A verified case from this repo's own corpus. The run at
`tests/fixtures/papers/cerebrolysin_papers/done/10.1002--adbi.202300439/forensic_review_fable_07_17_2026`
records `model: fable` in run_meta.json for both stages, says "fable" in its
directory name, and is cited as "$22.01 on Fable" in this repo's own README.

The message logs say otherwise. Both stages emitted:

    model_refusal_fallback: claude-fable-5 -> claude-opus-4-8, category "bio"

and `modelUsage` shows $2.799 of the $2.807 was billed to claude-opus-4-8.
Fable did essentially none of that analysis.

Two consequences. Every cost and quality conclusion attributed to Fable from
that run is wrong -- including a figure quoted in the documentation. And the
refusal category is `bio` on a cerebrolysin mouse study, so this will RECUR
across a biomedical corpus rather than being a one-off.
"""
import json
import pathlib

import pytest

from forensic_metascience_ai_toolkit.agent import _resolved_models, _stage_meta

RUN = (pathlib.Path(__file__).parent.parent / "tests/fixtures/papers/cerebrolysin_papers" / "done"
       / "10.1002--adbi.202300439" / "forensic_review_fable_07_17_2026")


def _stage(name):
    path = RUN / f"messages.{name}.json"
    if not path.exists():
        pytest.skip("corpus run not present (git-lfs not pulled)")
    return json.loads(path.read_text())


class TestResolvedModels:
    def test_detects_the_fallback(self):
        r = _resolved_models(_stage("stage1"))
        assert r["model_switched"] is True
        assert "claude-opus-4-8" in r["models_resolved"]
        fb = r["fallbacks"][0]
        assert fb["original_model"] == "claude-fable-5"
        assert fb["fallback_model"] == "claude-opus-4-8"
        assert fb["api_refusal_category"] == "bio"

    def test_identifies_who_was_actually_billed(self):
        """modelUsage is authoritative: it is keyed by what was charged."""
        r = _resolved_models(_stage("stage1"))
        assert r["primary_billed_model"] == "claude-opus-4-8"
        assert r["model_usage"]["claude-opus-4-8"]["costUSD"] > 1.0

    def test_both_stages_fell_back(self):
        """Not a one-off: `bio` on a biomedical corpus will recur."""
        for name in ("stage1", "stage2"):
            assert _resolved_models(_stage(name))["primary_billed_model"] == "claude-opus-4-8"

    def test_a_clean_run_reports_no_switch(self):
        r = _resolved_models([
            {"type": "system", "model": "claude-sonnet-4-6"},
            {"type": "result", "modelUsage": {"claude-sonnet-4-6": {"costUSD": 1.0}}},
        ])
        assert r["model_switched"] is False
        assert r["primary_billed_model"] == "claude-sonnet-4-6"

    def test_empty_messages_do_not_crash(self):
        r = _resolved_models([])
        assert r["models_resolved"] == [] and r["primary_billed_model"] is None


class TestStageMetaCarriesIt:
    def test_requested_and_resolved_are_both_recorded_and_differ(self):
        meta = _stage_meta(
            {"messages": _stage("stage1"), "cost_usd": 1.68, "input_tokens": 23,
             "output_tokens": 14853, "return_code": 0, "is_error": False,
             "wall_seconds": 200.9},
            model="fable",
        )
        assert meta["model"] == "fable", "the requested alias must still be recorded"
        assert meta["primary_billed_model"] == "claude-opus-4-8"
        assert meta["model_switched"] is True, (
            "run_meta must make a silent model substitution visible; without this "
            "a report is attributed to a model that did not produce it"
        )


class TestSchemaAllowsWhatWeWrite:
    """findings.json must validate against the schema it was generated under.

    `_annotate_reproductions` injects `reproduction_valid` and, when false,
    `reproduction_problem`. The findings schema sets `additionalProperties:
    false` on finding items, so until those keys were declared, every
    findings.json we wrote violated its own schema.
    """

    def test_annotation_keys_are_declared(self):
        schema = json.loads(
            (pathlib.Path(__file__).parent.parent / "src" / "forensic_metascience_ai_toolkit"
             / "schema" / "findings.v2.schema.json").read_text())
        props = schema["properties"]["findings"]["items"]["properties"]
        assert "reproduction_valid" in props
        assert "reproduction_problem" in props
