"""Pipelines: which modules run, with which tools, and what a partial run may claim.

Phase 1 of the modular refactor. The contract tested here:

* `full` is the pipeline every pre-pipeline run was, byte for byte: same
  prompts, allowlists and provenance hash (`from_flags()` == `full.yaml`).
* Configuration errors are ERRORS -- unknown keys, modules and tools never
  run as something else.
* A restricted toolset is enforced in four places, not one: the allowlist,
  the MCP server (fail-closed manifest), `check_table`, and the harness.
* A partial run never stands as the paper's review: `run_kind`, the history
  component, corpus statistics and the batch skip all see it as partial.
"""

import asyncio
import json
from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit import agent, parallel
from forensic_metascience_ai_toolkit.core import prompts
from forensic_metascience_ai_toolkit import pipeline_config as pc
from tests.test_parallel_pipeline import _doc, _row, _stage, fakes, paper  # noqa: F401


def _cfg(*modules, **top):
    return pc.parse({"schema_version": 1, "name": top.pop("name", "t"),
                     "modules": list(modules), **top})


# ---------------------------------------------------------------------------
# loading and validation
# ---------------------------------------------------------------------------

class TestShippedPipelines:
    def test_every_shipped_pipeline_validates(self):
        names = pc.available()
        assert {"full", "tools_only", "tools_grim", "proofreading_only",
                "image_only", "no_adjudication"} <= set(names)
        for name in names:
            pc.load(name)

    def test_full_is_exactly_the_flag_default(self):
        assert pc.load("full").digest == pc.from_flags().digest
        assert pc.load("full").complete_review

    def test_only_full_and_its_access_variants_are_complete_reviews(self):
        """`full_brief`/`full_skill` are `full` with a different `tool_access`
        (Phase 3b): still complete reviews, but their own digests."""
        complete = {n for n in pc.available() if pc.load(n).complete_review}
        # `full_raw_data` (2026-10-15) is `full` plus the opt-in raw-data module.
        assert complete == {"full", "full_brief", "full_skill", "full_raw_data"}
        digests = {pc.load(n).digest for n in complete}
        assert len(digests) == 4

    def test_every_tool_agent_tool_is_reachable_by_some_toolset(self):
        sets = pc.load_toolsets()
        covered = set().union(*sets.values()) | pc.CORE_TOOLS | pc.FIGURE_TOOLS
        assert set(pc._tool_agent_tools()) <= covered


class TestValidation:
    @pytest.mark.parametrize("raw, fragment", [
        ({"schema_version": 1, "modules": ["tools_agent"], "budget": 3},
         "unknown key(s) ['budget']"),
        ({"schema_version": 2, "modules": ["tools_agent"]}, "schema_version"),
        ({"schema_version": 1, "modules": ["adjudicater"]}, "unknown module"),
        ({"schema_version": 1, "modules": []}, "non-empty list"),
        ({"schema_version": 1, "modules": ["tools_agent", "tools_agent"]},
         "listed twice"),
        ({"schema_version": 1, "modules": [
            {"use": "image_analysis", "options": {"ai_screening": "no"}}]},
         "expected true or false"),
        ({"schema_version": 1, "modules": [
            {"use": "tools_agent", "tools": ["grim_chek"]}]}, "unknown tool"),
        ({"schema_version": 1, "modules": [
            {"use": "tools_agent", "tools": {"exclude": ["check_table"]}}]},
         "always included"),
        ({"schema_version": 1, "modules": [
            {"use": "tools_agent", "tools": ["extract_figures"]}]},
         "figures: true"),
        ({"schema_version": 1, "modules": [
            {"use": "scientific_proofreading_agent", "tools": ["grim_check"]}]},
         "only tools_agent"),
        ({"schema_version": 1, "modules": [
            {"use": "tools_agent", "options": {"budget_share": 0.4}}]},
         "unknown key(s) ['budget_share']"),
        ({"schema_version": 1, "backend": {"name": "gemini"},
          "modules": ["tools_agent"]}, "unknown backend"),
    ])
    def test_mistakes_are_refused_by_name(self, raw, fragment):
        with pytest.raises(pc.PipelineConfigError, match=None) as exc:
            pc.parse(raw)
        assert fragment in str(exc.value)

    def test_unknown_pipeline_name_lists_the_shipped_ones(self):
        with pytest.raises(pc.PipelineConfigError) as exc:
            pc.load("no_such_pipeline")
        assert "full" in str(exc.value)


class TestToolsets:
    def test_readers_and_dispatch_are_always_included(self):
        tools = set(_cfg({"use": "tools_agent", "tools": ["grim_check"]}).toolset)
        assert tools == pc.CORE_TOOLS | {"grim_check"}

    def test_named_toolset_with_include_and_exclude(self):
        cfg = _cfg({"use": "tools_agent", "tools": {
            "toolset": "grim_family", "include": ["statcheck"],
            "exclude": ["sprite_reconstruct"]}})
        tools = set(cfg.toolset)
        assert {"grim_check", "statcheck"} <= tools
        assert "sprite_reconstruct" not in tools
        assert not cfg.full_toolset

    def test_all_excludes_figure_tools_unless_figures(self):
        assert "extract_figures" not in _cfg("tools_agent").toolset
        figs = _cfg({"use": "tools_agent", "options": {"figures": True}})
        assert "extract_figures" in figs.toolset and figs.figures

    def test_toolset_order_follows_the_registry(self):
        known = pc._tool_agent_tools()
        tools = list(_cfg({"use": "tools_agent", "tools": ["statcheck", "grim_check"]}).toolset)
        assert tools == [t for t in known if t in set(tools)]


class TestRecordRoundTrip:
    def test_from_record_rebuilds_the_same_digest(self):
        for name in pc.available():
            cfg = pc.load(name)
            assert pc.from_record(cfg.record()).digest == cfg.digest

    def test_a_pre_pipeline_run_has_no_record(self):
        assert pc.from_record(None) is None
        assert pc.from_record({"digest": "x"}) is None


class TestImageModule:
    def test_the_default_is_not_recorded(self):
        assert (_cfg({"use": "image_analysis", "options": {"ai_screening": True}}).digest
                == _cfg("image_analysis").digest)

    def test_screening_off_is_recorded(self):
        cfg = _cfg({"use": "image_analysis", "options": {"ai_screening": False}})
        assert cfg.module("image_analysis").options == {"ai_screening": False}
        assert cfg.digest != _cfg("image_analysis").digest

    @pytest.mark.parametrize("retired", ["image_detection", "image_review"])
    def test_the_retired_names_do_not_parse(self, retired):
        with pytest.raises(pc.PipelineConfigError, match="unknown module"):
            _cfg(retired)


# ---------------------------------------------------------------------------
# prompts
# ---------------------------------------------------------------------------

class TestPrompts:
    @pytest.mark.parametrize("figures", [False, True])
    @pytest.mark.parametrize("grok", [False, True])
    def test_full_toolset_prompt_is_byte_identical(self, figures, grok):
        cfg = _cfg({"use": "tools_agent", "options": {"figures": figures}},
                   "scientific_proofreading_agent", "adjudicator")
        historical = prompts.tool_expert_system_prompt(
            figures=figures, grok_mcp_route=grok)
        assert prompts.tool_expert_system_prompt(
            figures=figures, grok_mcp_route=grok, tools=cfg.toolset) == historical
        assert prompts.system_prompt_for(
            cfg, "tools_agent", grok_mcp_route=grok) == historical

    def test_complete_review_prompt_blob_is_the_historical_trio(self):
        historical = (prompts.tool_expert_system_prompt(figures=False)
                      + "\x00" + prompts.science_error_system_prompt()
                      + "\x00" + prompts.adjudication_system_prompt())
        assert prompts.prompt_blob(pc.from_flags()) == historical
        assert prompts.prompt_blob(pc.load("full")) == historical

    def test_one_tool_prompt_names_only_what_it_has(self):
        cfg = pc.load("tools_grim")
        text = prompts.system_prompt_for(cfg, "tools_agent")
        assert "## Tools available in this run" in text
        assert "This is a PARTIAL pipeline" in text
        assert "No adjudicator runs" in text
        # The step-3 bullet for GRIM survives; SPRITE's does not.
        assert "- `grim_check` / `grim_percentage`" in text
        assert "- `sprite_reconstruct` — reconstruct" not in text
        # The CLI map no longer advertises tools the run cannot call.
        cli_map = text.split("## Tools available in this run")[0]
        assert "sprite_reconstruct ->" not in cli_map.replace("`", "")

    def test_partial_note_names_the_absent_colleague(self):
        note = prompts.system_prompt_for(pc.load("proofreading_only"),
                                         "scientific_proofreading_agent")
        assert "No tools agent runs" in note
        assert "No adjudicator runs" in note

    def test_the_user_turn_drops_disabled_tool_instructions(self):
        sentence = parallel._USER_PROMPT_TOOL_SENTENCES["statcheck"][0]
        prompt = "Run `extract_xml` on x. " + sentence + " Then more."
        assert parallel._restrict_user_prompt(prompt, None) == prompt
        assert sentence not in parallel._restrict_user_prompt(
            prompt, frozenset({"grim_check"}))
        assert parallel._restrict_user_prompt(
            prompt, frozenset({"statcheck"})) == prompt

    def test_the_producer_schema_never_offers_the_pipeline_block(self):
        schema = prompts.producer_findings_schema("tool_expert")
        assert "pipeline" not in schema["properties"]
        assert "pipeline" in prompts.findings_schema_v2()["properties"]


# ---------------------------------------------------------------------------
# enforcement: allowlist, MCP manifest, check_table, harness
# ---------------------------------------------------------------------------

class TestFences:
    def test_allowlist_is_read_plus_the_toolset(self):
        tools = parallel.tool_agent_tools(False, frozenset(pc.load("tools_grim").toolset))
        assert tools[0] == "Read"
        assert {t.split("__")[-1] for t in tools[1:]} == set(pc.load("tools_grim").toolset)

    def test_no_toolset_keeps_the_historical_allowlist(self):
        assert parallel.tool_agent_tools(False, None) == parallel.tool_agent_tools(False)

    def test_manifest_narrows_the_role(self):
        from forensic_metascience_ai_toolkit import mcp_server
        served = mcp_server._manifest_tools({"grim_check", "check_table"}, "tool_agent")
        assert {t.name for t in served} == {"grim_check", "check_table"}

    @pytest.mark.parametrize("enabled, stage, fragment", [
        ({"grim_check"}, "", "without"),
        ({"grim_check"}, "no_such_role", "unknown role"),
        ({"grim_chek"}, "tool_agent", "unknown tool"),
        # An off-role tool cannot widen the role, and alone it leaves nothing.
        ({"run_python_script"}, "tool_agent", "nothing to serve"),
    ])
    def test_manifest_fails_closed(self, enabled, stage, fragment):
        from forensic_metascience_ai_toolkit import mcp_server
        with pytest.raises(mcp_server.ToolManifestError) as exc:
            mcp_server._manifest_tools(enabled, stage)
        assert fragment in str(exc.value)

    def test_mcp_config_carries_the_manifest_only_when_restricted(self):
        full = json.loads(agent._build_mcp_config("/p", mcp_stage="tool_agent"))
        env = full["mcpServers"]["forensic_metascience"]["env"]
        assert pc.MCP_TOOLS_ENV not in env
        narrowed = json.loads(agent._build_mcp_config(
            "/p", mcp_stage="tool_agent", mcp_tools=["grim_check", "check_table"]))
        env = narrowed["mcpServers"]["forensic_metascience"]["env"]
        assert env[pc.MCP_TOOLS_ENV] == "grim_check,check_table"

    def test_check_table_refuses_tools_the_pipeline_disabled(self, monkeypatch):
        from forensic_metascience_ai_toolkit.dispatch import NOT_ENABLED_REASON, check_table
        likert = {"id": "y", "family": "likert_item", "lower_bound": 1,
                  "upper_bound": 7, "confidence": "high"}
        cells = [{"raw": "5.51 (1.20)", "row_label": "S", "n": 30}]
        monkeypatch.setenv(pc.MCP_TOOLS_ENV, "grim_check,check_table")
        r = check_table(cells, [likert], {"S": "y"})
        assert set(r["tools_run"]) == {"grim_check"}
        refused = {t for e in r["not_run"] if e["reason"] == NOT_ENABLED_REASON
                   for t in e["tools"]}
        assert refused == {"grimmer_check", "sprite_reconstruct"}

    def test_harness_sweeps_follow_the_toolset(self, monkeypatch):
        from forensic_metascience_ai_toolkit import prepass
        monkeypatch.setattr(prepass, "paper_tables",
                            lambda *a, **k: [{"id": "T1", "cells": []}])
        called = []
        monkeypatch.setattr(prepass, "sweep_duplication",
                            lambda t: called.append("dup") or {"severity": "consistent"})
        monkeypatch.setattr(prepass, "sweep_sd_range",
                            lambda *a: called.append("sd") or {"severity": None, "results": []})
        monkeypatch.setattr(prepass, "_sweep_claims",
                            lambda f: called.append("claims") or None)
        out = prepass.run_exhaustive("/p", {}, enabled=frozenset({"check_sd_range"}))
        assert called == ["sd"]
        assert out["duplication"]["not_run"] == prepass.NOT_ENABLED
        called.clear()
        prepass.run_exhaustive("/p", {})
        assert called == ["claims", "dup", "sd"]


# ---------------------------------------------------------------------------
# the orchestrator, on faked stages
# ---------------------------------------------------------------------------

def _run(paper, config, **kw):
    return asyncio.run(agent.analyze_paper(str(paper), mode="parallel",
                                           pipeline=config, **kw))


class TestOrchestration:
    def test_tools_only_runs_one_analyst_and_no_adjudicator(self, paper, fakes):
        r = _run(paper, pc.load("tools_only"))
        assert fakes["calls"] == ["tool_agent"]
        doc = r["findings_v2"]
        assert doc["pipeline"]["complete_review"] is False
        assert doc["channels"]["science_error"]["state"] == "did_not_run"
        assert "not configured" in doc["channels"]["science_error"]["detail"]
        assert doc["adjudication"]["ran"] is False
        assert "not configured" in doc["adjudication"]["skipped_reason"]
        assert all(f["severity_is_provisional"] for f in doc["findings"]
                   if f.get("outcome") == "problem")
        assert r["is_error"] is False
        assert r["run_meta"]["pipeline"]["name"] == "tools_only"

    def test_proofreading_only(self, paper, fakes):
        r = _run(paper, pc.load("proofreading_only"))
        assert fakes["calls"] == ["science_agent"]
        assert r["findings_v2"]["channels"]["tool_expert"]["state"] == "did_not_run"
        assert r["is_error"] is False

    def test_a_failed_sole_analyst_still_raises(self, paper, fakes):
        fakes["tool"] = RuntimeError("boom")
        with pytest.raises(agent.StageError, match="the analysis agent failed"):
            _run(paper, pc.load("tools_only"))

    @pytest.mark.usefixtures("image_package")
    def test_no_analysts_is_not_a_stage_error(self, paper, fakes, monkeypatch):
        from metascience_observatory_image_analysis.image_forensics import pipeline as ip

        async def fake_image(*a, **k):
            return {**ip.disabled_record(), "execution_status": "complete",
                    "ran": True, "detail": "faked"}
        monkeypatch.setattr(ip, "run", fake_image)
        r = _run(paper, pc.load("image_only"))
        assert fakes["calls"] == []
        assert r["findings_v2"]["pipeline"]["complete_review"] is False
        assert r["is_error"] is False
        # No analyst ran, so there is no analyst figure scope to declare.
        assert not any("figure values were not extracted" in x
                       for x in r["limitations"])

    def test_one_tool_run_sends_the_manifest(self, paper, fakes, monkeypatch):
        seen = {}
        real = agent._build_claude_cmd

        def spy(*a, **k):
            if k.get("mcp_stage") == "tool_agent":
                seen.update(allowed=k["allowed_tools"], tools=k.get("mcp_tools"))
            return real(*a, **k)
        monkeypatch.setattr(agent, "_build_claude_cmd", spy)
        _run(paper, pc.load("tools_grim"))
        assert seen["tools"] == sorted(pc.load("tools_grim").toolset)
        assert {t.split("__")[-1] for t in seen["allowed"] if t != "Read"} \
            == set(pc.load("tools_grim").toolset)

    def test_full_pipeline_matches_the_flag_default(self, paper, fakes, monkeypatch):
        sent = []
        real = agent._build_claude_cmd

        def spy(*a, **k):
            sent.append((k.get("mcp_stage"), k.get("system_prompt"),
                         tuple(k.get("allowed_tools") or ()), k.get("mcp_tools")))
            return real(*a, **k)
        monkeypatch.setattr(agent, "_build_claude_cmd", spy)
        flags = asyncio.run(agent.analyze_paper(
            str(paper), mode="parallel", image_forensics=False, text_forensics=False))
        first, sent[:] = list(sent), []
        cfg = pc.parse({"schema_version": 1, "name": "full", "modules": [
            "tools_agent", "scientific_proofreading_agent", "adjudicator"]})
        piped = _run(paper, cfg)
        assert sent == first
        assert all(t is None for _, _, _, t in sent)
        assert piped["run_meta"]["prompt_sha256"] == flags["run_meta"]["prompt_sha256"]
        assert piped["findings_v2"]["pipeline"]["complete_review"] is True


# ---------------------------------------------------------------------------
# readers: what a partial run may stand for
# ---------------------------------------------------------------------------

class TestReaders:
    def _doc(self, config, tool_ran=True):
        return {"pipeline": config.record() if config else None,
                "channels": {"tool_expert": {"state": "ran" if tool_ran else "did_not_run"},
                             "image_forensics": {"state": "ran"}}}

    def test_run_kind(self):
        from forensic_metascience_ai_toolkit.discovery import run_kind
        assert run_kind(self._doc(pc.load("full"))) == "full_review"
        assert run_kind(self._doc(None)) == "full_review"
        assert run_kind(self._doc(pc.load("tools_grim"))) == "partial_review"
        assert run_kind(self._doc(pc.load("no_adjudication"))) == "partial_review"
        assert run_kind(self._doc(pc.load("image_only"), tool_ran=False)) == "image_track"

    def _review(self, paper_dir, name, config):
        d = paper_dir / name
        d.mkdir()
        (d / "report.md").write_text("r")
        meta = {"pipeline": config.record()} if config else {}
        (d / "run_meta.json").write_text(json.dumps(meta))
        return d

    def test_batch_skip_ignores_partial_runs_for_a_full_batch(self, tmp_path):
        self._review(tmp_path, "forensic_review_tools_grim_opus_v1", pc.load("tools_grim"))
        assert agent.completed_review(tmp_path) is None
        legacy = self._review(tmp_path, "forensic_review_opus_v1", None)
        assert agent.completed_review(tmp_path) == legacy

    def test_batch_skip_for_a_partial_pipeline_is_per_experiment(self, tmp_path):
        grim = pc.load("tools_grim")
        self._review(tmp_path, "forensic_review_opus_v1", None)
        assert agent.completed_review(tmp_path, pipeline=grim) is None
        mine = self._review(tmp_path, "forensic_review_tools_grim_opus_v1", grim)
        assert agent.completed_review(tmp_path, pipeline=grim) == mine

    def _engine(self, d, backend, model, resolved=()):
        meta = json.loads((d / "run_meta.json").read_text())
        meta.update({"llm_backend": backend, "model": model,
                     "stages": {"tool_agent": {"models_resolved": list(resolved)}}})
        (d / "run_meta.json").write_text(json.dumps(meta))
        return d

    def test_a_different_model_is_a_new_run_not_a_redo(self, tmp_path):
        """2026-10-18: a Grok tools_only batch would have skipped every paper a
        Sonnet tools_only batch had finished, because only the pipeline was
        compared."""
        tools = pc.load("tools_only")
        d = self._engine(self._review(tmp_path, "forensic_review_tools_only_sonnet", tools),
                         "claude", "sonnet", ["claude-sonnet-5-5"])
        assert agent.completed_review(tmp_path, pipeline=tools,
                                      backend="grok", model="grok-4.6") is None
        assert agent.completed_review(tmp_path, pipeline=tools,
                                      backend="claude", model="opus") is None
        assert agent.completed_review(tmp_path, pipeline=tools,
                                      backend="claude", model="sonnet") == d
        # The resolved model name matches as well as the alias.
        assert agent.completed_review(tmp_path, pipeline=tools,
                                      backend="claude", model="claude-sonnet-5-5") == d

    def test_complete_reviews_match_on_backend_and_model_too(self, tmp_path):
        d = self._engine(self._review(tmp_path, "forensic_review_sonnet_v1", pc.load("full")),
                         "claude", "sonnet")
        full = pc.load("full")
        assert agent.completed_review(tmp_path, pipeline=full,
                                      backend="grok", model="grok-4.6") is None
        assert agent.completed_review(tmp_path, pipeline=full,
                                      backend="claude", model="sonnet") == d

    def test_a_run_that_recorded_no_engine_still_counts(self, tmp_path):
        """Pre-record runs keep protecting spend: old corpora are not re-paid."""
        legacy = self._review(tmp_path, "forensic_review_opus_v1", None)
        assert agent.completed_review(tmp_path, backend="grok", model="grok-4.6") == legacy

    def test_no_engine_asked_is_the_old_rule(self, tmp_path):
        d = self._engine(self._review(tmp_path, "forensic_review_sonnet_v1", pc.load("full")),
                         "claude", "sonnet")
        assert agent.completed_review(tmp_path) == d

    def test_any_complete_review_protects_spend(self, tmp_path):
        no_image = pc.from_flags(image_forensics=False)
        d = self._review(tmp_path, "forensic_review_opus_v1", no_image)
        assert agent.completed_review(tmp_path, pipeline=pc.load("full")) == d

    def test_build_identity_is_configuration_aware(self):
        from forensic_metascience_ai_toolkit import runs
        default = runs.build_fingerprint()
        assert default == runs.build_fingerprint(pc.from_flags())
        grim = runs.build_fingerprint(pc.load("tools_grim"))
        assert grim["prompt_sha256"] != default["prompt_sha256"]
        assert grim["registry_sha256"] == default["registry_sha256"]

    def test_partial_review_directory_names_itself(self):
        from forensic_metascience_ai_toolkit.cli import _versioned_review_dirname
        assert "tools_grim" not in _versioned_review_dirname("opus", pc.load("full"))
        assert _versioned_review_dirname("opus", pc.load("tools_grim")).startswith(
            "forensic_review_tools-grim_opus_v")


# ---------------------------------------------------------------------------
# the verb
# ---------------------------------------------------------------------------

class TestAnalyzeVerb:
    def _invoke(self, paper, monkeypatch, *args):
        from typer.testing import CliRunner

        from forensic_metascience_ai_toolkit.cli import app
        monkeypatch.setattr(agent, "ensure_paper_extracted",
                            lambda *a, **k: {"failed": []})
        return CliRunner().invoke(app, [
            "analyze", str(paper), "--backend", "claude", "--model", "opus",
            "--no-usage-guard", "--no-pdf", "--no-bundle", *args])

    def test_a_partial_pipeline_writes_its_own_named_review(
            self, paper, fakes, monkeypatch):
        from forensic_metascience_ai_toolkit.cli import _analyze_out_dir
        result = self._invoke(paper, monkeypatch, "--pipeline", "tools_only")
        assert result.exit_code == 0, (result.output, result.exception)
        out, _ = _analyze_out_dir(paper, None, "opus", pc.load("tools_only"))
        assert "tools-only" in out.name
        doc = json.loads((out / "findings.v2.json").read_text())
        assert doc["pipeline"]["name"] == "tools_only"
        assert doc["adjudication"]["ran"] is False
        meta = json.loads((out / "run_meta.json").read_text())
        assert set(meta["pipeline"]["system_prompt_sha256"]) == {"tool_agent"}
        # ...and it is not the paper's review for a later full batch.
        assert agent.completed_review(paper) is None

    @pytest.mark.parametrize("flag", ["--figures", "--no-image-forensics",
                                      "--no-text-forensics", "--segment-montages"])
    def test_module_flags_cannot_be_mixed_with_a_pipeline(
            self, paper, fakes, monkeypatch, flag):
        result = self._invoke(paper, monkeypatch, "--pipeline", "tools_only", flag)
        assert result.exit_code == 2
        assert fakes["calls"] == []

    def test_an_invalid_pipeline_stops_before_any_spend(self, paper, fakes,
                                                        monkeypatch, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("schema_version: 1\nmodules:\n  - use: adjudicater\n")
        result = self._invoke(paper, monkeypatch, "--pipeline", str(bad))
        assert result.exit_code == 2
        assert "unknown module" in result.output
        assert fakes["calls"] == []


class TestReviewFixes:
    """Found by GPT-6 Astra's review of the Phase 1 diff."""

    @pytest.mark.usefixtures("image_package")
    def test_an_image_only_run_records_the_hash_build_matches_expects(
            self, paper, fakes, monkeypatch):
        from metascience_observatory_image_analysis.image_forensics import pipeline as ip

        from forensic_metascience_ai_toolkit import runs

        async def fake_image(*a, **k):
            return {**ip.disabled_record(), "execution_status": "complete",
                    "ran": True, "detail": "faked"}
        monkeypatch.setattr(ip, "run", fake_image)
        cfg = pc.load("image_only")
        r = _run(paper, cfg)
        assert (r["run_meta"]["prompt_sha256"]
                == runs.build_fingerprint(cfg)["prompt_sha256"])

    def test_the_index_never_takes_a_partial_run_as_the_papers_review(self, tmp_path):
        from forensic_metascience_ai_toolkit import webapp_index as wi
        from tests.test_webapp_index import _paper
        d = _paper(tmp_path, dirs=("forensic_review_opus_v1",
                                   "forensic_review_tools-grim_opus_v1"))
        full = pc.load("full").record()
        grim = pc.load("tools_grim").record()
        for name, block, verdict in (
                ("forensic_review_opus_v1", full, "reconciles"),
                ("forensic_review_tools-grim_opus_v1", grim, None)):
            (d / name / "findings.v2.json").write_text(json.dumps({
                "schema_version": "2.0", "pipeline": block,
                "channels": {"tool_expert": {"state": "ran"}},
                "findings": [], "adjudication": {"ran": verdict is not None,
                                                 "verdict": verdict}}))
        # The partial run is the NEWER one, and still does not win.
        import os
        import time
        later = time.time() + 60
        os.utime(d / "forensic_review_tools-grim_opus_v1", (later, later))
        rec = wi.scan_paper(d)
        assert rec["latest_run"] == "forensic_review_opus_v1"
        assert rec["verdict"] is not None

    def test_a_partial_report_says_so_first(self):
        from forensic_metascience_ai_toolkit.report_v2 import render_report_v2
        doc = {"paper_id": "p", "findings": [], "adjudication": {"ran": False},
               "pipeline": pc.load("tools_grim").record()}
        text = render_report_v2(doc)
        head = text.split("**Verdict")[0]
        assert "PARTIAL PIPELINE (`tools_grim`)" in head
        assert "grim_check" in head
        full = {**doc, "pipeline": pc.load("full").record()}
        assert "PARTIAL PIPELINE" not in render_report_v2(full)
        assert "PARTIAL PIPELINE" not in render_report_v2({**doc, "pipeline": None})


class TestAstraPhase1Findings:
    """Regression tests for GPT-6 Astra's review of 63ae7a61, one per finding."""

    # 1 -- workbench default review leaves partial runs out
    def test_workbench_default_selection_excludes_partial_runs(self, tmp_path):
        from forensic_metascience_ai_toolkit.workbench.catalog import Catalog
        from forensic_metascience_ai_toolkit.workbench.repository import Repository
        from tests.test_workbench_catalog import seed
        c = Catalog(tmp_path / "cache.sqlite3")
        seed(c)
        try:
            rows = [{"id": 10, "run_uid": "r_full", "paper_id": 2,
                     "component": "comprehensive", "status": "complete",
                     "execution_status": "completed", "analysed_at": "2026-04-01",
                     "execution_uid": "e_full"},
                    {"id": 11, "run_uid": "r_part", "paper_id": 2,
                     "component": "partial_review", "status": "partial",
                     "execution_status": "completed", "analysed_at": "2026-05-01",
                     "execution_uid": "e_part"}]
            c.apply_changes([("runs", json.dumps([r["id"]]), r) for r in rows], 2)
            r = Repository(c)
            r.refresh()
            uids = {x["run_uid"] for x in r.selected_runs("project", paper=2)}
            assert "r_full" in uids and "r_part" not in uids
            assert [x["run_uid"] for x in r.selected_runs(
                "project", kind="partial_review", paper=2)] == ["r_part"]
        finally:
            c.close()

    # 1b -- but a paper whose only run is partial shows it, provisional, and
    # its findings open (2026-10-18: "No run recorded" / "Finding not in
    # this project" on every tools_only paper)
    def test_workbench_shows_partial_runs_and_their_finding_detail(self, tmp_path):
        from forensic_metascience_ai_toolkit.workbench.catalog import Catalog
        from forensic_metascience_ai_toolkit.workbench.service import Service
        from tests.test_workbench_catalog import seed
        c = Catalog(tmp_path / "cache.sqlite3")
        seed(c)
        try:
            pipeline = {"name": "tools_only", "complete_review": False}
            part = {"id": 11, "run_uid": "r_part", "paper_id": 2,
                    "component": "partial_review", "status": "complete",
                    "execution_status": "completed", "analysed_at": "2026-05-01",
                    "execution_uid": "e_part", "pipeline_version": "1.80.0",
                    "history_record": {"provenance": {"parameters": {"pipeline": pipeline}}}}
            record = {"finding_id": "f_p", "producer": "tool_expert",
                      "technique": "grim_check", "outcome": "problem",
                      "severity": 4, "severity_is_provisional": True,
                      "title": "Mean not attainable with n=29",
                      "tool_verdict": {"tool": "grim_check", "severity": "impossible"}}
            summary = {"id": 12, "run_id": 11, "paper_id": 2,
                       **{k: v for k, v in record.items() if k != "tool_verdict"},
                       "tool_basis": {"tool_verdict": "grim_check", "backing_call": None,
                                      "reproduction_source": None, "reproduction": None}}
            c.apply_changes([("runs", "[11]", part), ("findings", "[12]", summary)], 2)
            c.save_detail("findings", "[12]", {"record": record},
                          c.record_token("findings", "[12]"))
            s = Service(c, background=False)
            got = s.handle("paper", {"project": "project", "dir": "other/paper"})["issues"]
            assert got["latest_run"] == "r_part"
            assert got["source"]["partial_fallback"] is True
            assert got["source"]["detail"] is None
            assert got["source"]["pipeline"]["label"] == "tools only · provisional"
            [issue] = got["issues"]
            assert issue["id"] == "f_p" and issue["severity_is_provisional"]
            assert (issue["tool"], issue["tool_source"]) == ("grim_check", "tool_verdict")
            option = next(o for o in got["run_options"] if o["id"] == "r_part")
            assert option["pipeline"]["label"] == "tools only · provisional"
            # A complete review arrives: `latest` is it again, the partial run
            # is reached only by name -- and its detail only with its run.
            full = {"id": 13, "run_uid": "r_full", "paper_id": 2,
                    "component": "comprehensive", "status": "complete",
                    "execution_status": "completed", "analysed_at": "2026-04-01",
                    "execution_uid": "e_full"}
            c.apply_changes([("runs", "[13]", full)], 3)
            got = s.handle("paper", {"project": "project", "dir": "other/paper"})["issues"]
            assert got["latest_run"] == "r_full" and got["issues"] == []
            assert got["source"]["partial_fallback"] is False
            got = s.handle("paper", {"project": "project", "dir": "other/paper",
                                     "run": "r_part"})["issues"]
            assert got["latest_run"] == "r_part"
            assert [i["id"] for i in got["issues"]] == ["f_p"]
            detail = s.handle("issue_detail", {"project": "project", "finding": "12",
                                               "run": "r_part"})["issue"]
            assert detail["id"] == "f_p" and detail["detail_loaded"]
            assert detail["tool"] == "grim_check"
            assert detail["pipeline"]["label"] == "tools only · provisional"
            with pytest.raises(LookupError, match="not in this project"):
                s.handle("issue_detail", {"project": "project", "finding": "12"})
        finally:
            c.close()

    # 2 -- JSON repair of a partial run carries no tools
    def test_partial_repair_is_tool_free_on_every_backend(self, monkeypatch, tmp_path):
        seen = []

        async def fake_run_stage(cmd, prompt, *a, **k):
            seen.append(cmd)
            return _stage({"findings": []})
        monkeypatch.setattr(agent, "_run_stage", fake_run_stage)
        # Never write the operator's ~/.grok/trusted_folders.toml.
        monkeypatch.setenv("METASCIENCE_GROK_SKIP_FOLDER_TRUST", "1")
        monkeypatch.setenv("METASCIENCE_GROK_SANDBOX_ROOT", str(tmp_path / "g"))
        monkeypatch.setenv("METASCIENCE_CODEX_SANDBOX_ROOT", str(tmp_path / "c"))
        for backend in ("claude", "codex", "grok"):
            asyncio.run(agent._repair_json("{", {"type": "object"}, "m", False,
                                           None, backend=backend, tool_free=True))
        claude, codex, grok = seen
        assert claude[claude.index("--tools") + 1] == ""
        assert "--strict-mcp-config" in claude
        # A config the CLI accepts: `{}` was rejected ("mcpServers: expected
        # record, received undefined"), failing every partial-pipeline repair.
        assert json.loads(claude[claude.index("--mcp-config") + 1]) == {"mcpServers": {}}
        for inv in (codex, grok):
            text = " ".join(inv.argv)
            files = " ".join(f.read_text() for f in Path(inv.workdir).rglob("*")
                             if f.is_file()) if inv.workdir else ""
            for module in ("forensic_metascience_ai_toolkit.mcp_server",
                           "metascience_agent.mcp_server"):  # old name, still importable
                assert module not in text + files

    def test_a_failed_repair_is_swallowed_not_raised(self, monkeypatch):
        """runtime.StageError IS agent.StageError, so `_repair_json` returns None
        on a failed repair instead of failing the paper (2026-10-18)."""
        from forensic_metascience_ai_toolkit import runtime

        assert agent.StageError is runtime.StageError

        async def failing_run_stage(cmd, prompt, *a, **k):
            raise runtime.StageError("`claude` CLI exited with code 1")
        monkeypatch.setattr(agent, "_run_stage", failing_run_stage)
        assert asyncio.run(agent._repair_json("{", {"type": "object"}, "m", False,
                                              None, backend="claude",
                                              tool_free=True)) is None

    # 3 -- reproductions of disabled tools are not executed
    def test_reproductions_of_disabled_tools_are_not_run(self, monkeypatch):
        def must_not_run(*a, **k):
            raise AssertionError("executed a disabled tool's reproduction")
        monkeypatch.setattr(agent, "_run_repro_cached", must_not_run)
        monkeypatch.setattr(agent.shutil, "which", lambda name: "/bin/metascience")
        entry = {"producer": "tool_expert", "technique": "check_count_percent",
                 "reproduction": "metascience check-count-percent --decimals 0 10 50 30"}
        result = {"findings": {"findings": [entry]}}
        summary = agent._annotate_reproductions(
            result, paper_dir=None,
            disabled_verbs=parallel._disabled_verbs(frozenset(pc.load("tools_grim").toolset)))
        assert entry.get("reproduction_not_executed") == "tool not enabled in this pipeline"
        assert summary["n_not_executed_disabled"] == 1

    # 4 -- a failed sole module is an error and not a finished experiment
    @pytest.mark.usefixtures("image_package")
    def test_a_failed_image_only_run_is_an_error(self, paper, fakes, monkeypatch, tmp_path):
        from metascience_observatory_image_analysis.image_forensics import pipeline as ip

        async def failed_image(*a, **k):
            return {**ip.disabled_record(), "ran": False, "is_error": True,
                    "execution_status": "failed", "detail": "boom"}
        monkeypatch.setattr(ip, "run", failed_image)
        r = _run(paper, pc.load("image_only"))
        assert r["is_error"] is True
        assert r["run_meta"]["pipeline"]["outcome"] == "error"
        d = tmp_path / "pp"
        d.mkdir()
        rd = d / "forensic_review_image-only_opus_v1"
        rd.mkdir()
        (rd / "report.md").write_text("r")
        (rd / "run_meta.json").write_text(json.dumps(r["run_meta"]))
        assert agent.completed_review(d, pipeline=pc.load("image_only")) is None

    # 5 -- the index's worst severity ignores partial runs
    def test_index_worst_severity_ignores_partial_runs(self, tmp_path):
        from forensic_metascience_ai_toolkit import webapp_index as wi
        from tests.test_webapp_index import _paper
        d = _paper(tmp_path, dirs=("forensic_review_opus_v1",
                                   "forensic_review_tools-grim_opus_v1"))
        for name, cfg, sev in (("forensic_review_opus_v1", "full", 3),
                               ("forensic_review_tools-grim_opus_v1", "tools_grim", 9)):
            (d / name / "findings.v2.json").write_text(json.dumps({
                "schema_version": "2.0", "pipeline": pc.load(cfg).record(),
                "channels": {"tool_expert": {"state": "ran"}},
                "findings": [{"finding_id": f"f_{sev}", "producer": "tool_expert",
                              "technique": "grim_check", "outcome": "problem",
                              "severity": sev}],
                "adjudication": {"ran": cfg == "full", "verdict": "reconciles"}}))
        assert wi.scan_paper(d)["worst_severity_9"] == 3

    # 7 -- drafts come from a complete review unless a partial one is named
    def test_drafts_default_to_the_complete_review(self, tmp_path):
        from forensic_metascience_ai_toolkit import drafts
        for name, cfg, fid in (("forensic_review_opus_v1", "full", "f_full"),
                               ("forensic_review_tools-grim_opus_v1", "tools_grim",
                                "f_part")):
            (tmp_path / name).mkdir()
            (tmp_path / name / "findings.v2.json").write_text(json.dumps({
                "paper_id": "p", "pipeline": pc.load(cfg).record(),
                "findings": [{"finding_id": fid, "outcome": "problem",
                              "title": "t"}]}))
        payload = drafts._findings_payload(tmp_path, None)
        assert [f["finding_id"] for f in payload["findings"]] == ["f_full"]
        assert "pipeline_scope" not in payload
        named = drafts._findings_payload(tmp_path, ["f_part"])
        assert [f["finding_id"] for f in named["findings"]] == ["f_part"]
        assert "PARTIAL PIPELINE" in named["pipeline_scope"]

    def test_drafts_refuse_a_partial_only_paper_unless_named(self, tmp_path):
        from forensic_metascience_ai_toolkit import drafts
        (tmp_path / "forensic_review_x").mkdir()
        (tmp_path / "forensic_review_x" / "findings.v2.json").write_text(json.dumps({
            "paper_id": "p", "pipeline": pc.load("tools_grim").record(),
            "findings": [{"finding_id": "f1", "outcome": "problem"}]}))
        out = drafts.generate(tmp_path, run_cli=lambda *a: None)
        assert out["ok"] is False and "partial-pipeline" in out["error"]

    # 8 -- unreadable run_meta cannot promote a partial run
    def test_a_partial_run_without_run_meta_is_still_partial(self, tmp_path):
        d = tmp_path / "forensic_review_tools-grim_opus_v1"
        d.mkdir()
        (d / "report.md").write_text("r")
        (d / "run_meta.json").write_text("{not json")
        (d / "findings.v2.json").write_text(json.dumps(
            {"pipeline": pc.load("tools_grim").record()}))
        assert agent.completed_review(tmp_path) is None

    # 9 -- the adjudicator hears which harness sweeps did not run
    def test_restricted_sweeps_say_what_did_not_run(self, monkeypatch):
        from forensic_metascience_ai_toolkit import prepass
        monkeypatch.setattr(prepass, "paper_tables", lambda *a, **k: [{"id": "T1"}])
        monkeypatch.setattr(prepass, "sweep_sd_range",
                            lambda *a: {"severity": None, "results": []})
        out = prepass.run_exhaustive("/p", {}, enabled=frozenset({"check_sd_range"}))
        assert out["not_run"] == ["detect_duplication", "grim sweep", "claim sweep"]
        assert "NOT run" in out["why"] and "every eligible target" not in out["why"]

    # 10 -- one precedence rule, applied by the API too
    def test_backend_precedence(self):
        cfg = _cfg("tools_agent", backend={"name": "grok", "model": "grok-4.6",
                                           "effort": "low"})
        assert pc.resolve_backend_settings(cfg) == ("grok", "grok-4.6", "low")
        assert pc.resolve_backend_settings(cfg, "claude") == ("claude", None, "low")
        assert pc.resolve_backend_settings(cfg, None, "m", "max") == ("grok", "m", "max")
        assert pc.resolve_backend_settings(None) == (None, None, None)

    def test_the_api_honours_the_pipeline_backend(self, paper, fakes, monkeypatch):
        seen = {}
        real = agent._build_claude_cmd

        def spy(*a, **k):
            seen.setdefault("backend", k.get("backend"))
            seen.setdefault("effort", k.get("effort"))
            return real(*a, **k)
        monkeypatch.setattr(agent, "_build_claude_cmd", spy)
        cfg = _cfg("tools_agent", backend={"name": "claude", "model": "sonnet",
                                           "effort": "low"})
        r = _run(paper, cfg)
        assert seen == {"backend": "claude", "effort": "low"}
        assert r["run_meta"]["model"] == "sonnet"

    # 11 -- an empty manifest is a manifest, and it is refused
    def test_an_empty_manifest_fails_closed(self, monkeypatch):
        from forensic_metascience_ai_toolkit import mcp_server
        monkeypatch.setenv(pc.MCP_TOOLS_ENV, "  ")
        assert pc.enabled_tools_from_env() == frozenset()
        monkeypatch.setenv("METASCIENCE_MCP_STAGE", "tool_agent")
        with pytest.raises(mcp_server.ToolManifestError):
            mcp_server._stage_filtered_tools()
        with pytest.raises(ValueError):
            agent._build_mcp_config("/p", mcp_stage="tool_agent", mcp_tools=[])

    # 14 -- options are booleans, not truthy strings
    def test_option_values_must_be_booleans(self):
        with pytest.raises(pc.PipelineConfigError, match="expected true or false"):
            _cfg({"use": "tools_agent", "options": {"figures": "false"}})

    # 15 -- prompt filtering keeps wrapped bullets and every statcheck layout
    def test_a_wrapped_bullet_lead_keeps_its_enabled_tool(self):
        cfg = _cfg({"use": "tools_agent", "tools": ["recalc_f_to_p"]})
        text = prompts.system_prompt_for(cfg, "tools_agent")
        assert "`recalc_f_to_p` — verify reported test statistics" in text

    def test_no_user_prompt_layout_keeps_a_disabled_statcheck(self, tmp_path):
        p = tmp_path / "x"
        layouts = [dict(xml=p), dict(html=p), dict(body_md=p, main_pdf=p),
                   dict(body_md=p)]
        grim = frozenset(pc.load("tools_grim").toolset)
        for kw in layouts:
            body_md = kw.pop("body_md", None)
            pdf = kw.pop("main_pdf", None)
            text = agent._build_sweep_prompt(body_md, pdf, "p", si_pdfs=[], **kw)
            assert "statcheck" in text, kw
            assert "statcheck" not in parallel._restrict_user_prompt(text, grim), kw

    # 6 -- the shareable viewer names the pipeline too
    def test_bundle_run_facts_name_a_partial_pipeline(self, tmp_path):
        from forensic_metascience_ai_toolkit import bundle
        rows = bundle._run_facts(tmp_path, {"pipeline": pc.load("tools_grim").record()})
        fact = next(r for r in rows if r["fact"] == "Pipeline")
        assert "PARTIAL" in fact["value"] and "tools_agent" in fact["detail"]
        rows = bundle._run_facts(tmp_path, {"pipeline": pc.load("full").record()})
        assert "complete review" in next(r for r in rows if r["fact"] == "Pipeline")["value"]


class TestAstraVerificationFindings:
    """Gaps GPT-6 Astra found while verifying 5bd965c1."""

    @pytest.mark.usefixtures("image_package")
    def test_a_screening_exception_fails_an_image_only_run(self, paper, fakes,
                                                           monkeypatch):
        from metascience_observatory_image_analysis.image_forensics import pipeline as ip

        async def screening_crashed(*a, **k):
            # Detection ran; screening raised: `ran` true, status incomplete.
            return {**ip.disabled_record(), "ran": True, "is_error": True,
                    "execution_status": "incomplete", "detail": "screen boom"}
        monkeypatch.setattr(ip, "run", screening_crashed)
        r = _run(paper, pc.load("image_only"))
        assert r["is_error"] is True
        assert r["run_meta"]["pipeline"]["outcome"] == "error"

    @pytest.mark.usefixtures("image_package")
    def test_an_incomplete_but_clean_image_only_run_is_incomplete_not_error(
            self, paper, fakes, monkeypatch):
        from metascience_observatory_image_analysis.image_forensics import pipeline as ip

        async def unresolved(*a, **k):
            return {**ip.disabled_record(), "ran": True, "is_error": False,
                    "execution_status": "incomplete", "detail": "2 unresolved"}
        monkeypatch.setattr(ip, "run", unresolved)
        r = _run(paper, pc.load("image_only"))
        assert r["is_error"] is False
        assert r["run_meta"]["pipeline"]["outcome"] == "incomplete"

    @pytest.mark.parametrize("tool, phrase", [
        ("check_regression", "Use `check_regression` only for a single"),
        ("check_summation", "Use `check_summation` only for a single"),
    ])
    def test_body_named_tools_keep_their_guidance(self, tool, phrase):
        text = prompts.system_prompt_for(
            _cfg({"use": "tools_agent", "tools": [tool]}), "tools_agent")
        assert phrase in text

    def test_rows_filed_under_disabled_tools_are_not_merged(self, paper, fakes):
        fakes["tool"] = _stage(_doc([_row("t1"), _row("t2", technique="sprite_reconstruct")]))
        r = _run(paper, pc.load("tools_grim"))
        techniques = {f.get("technique") for f in r["findings_v2"]["findings"]}
        assert "sprite_reconstruct" not in techniques and "grim_check" in techniques
        assert any("not enabled in this pipeline" in x and "sprite_reconstruct" in x
                   for x in r["limitations"])

    def test_a_failed_text_only_run_is_an_error(self, paper, fakes, monkeypatch):
        async def text_failed(*a, **k):
            return {"ran": False, "detail": "no text source", "error_subtype": "x"}
        monkeypatch.setattr(agent, "_run_text_track", text_failed)
        r = _run(paper, _cfg("text_forensics"))
        assert r["is_error"] is True
        assert r["run_meta"]["pipeline"]["outcome"] == "error"

    def test_malformed_run_meta_cannot_promote_a_partial_run(self, tmp_path):
        d = tmp_path / "forensic_review_tools-grim_opus_v1"
        d.mkdir()
        (d / "report.md").write_text("r")
        (d / "run_meta.json").write_text(json.dumps({"pipeline": {}}))
        (d / "findings.v2.json").write_text(json.dumps(
            {"pipeline": pc.load("tools_grim").record()}))
        assert agent.completed_review(tmp_path) is None

    def test_the_emitted_docket_says_which_sweeps_did_not_run(self, paper, fakes,
                                                              monkeypatch):
        from forensic_metascience_ai_toolkit import prepass
        monkeypatch.setattr(prepass, "paper_tables", lambda *a, **k: [{"id": "T1"}])
        monkeypatch.setattr(prepass, "sweep_sd_range",
                            lambda *a: {"severity": None, "results": []})
        dockets = []
        real = fakes  # the fixture answers the adjudicator from the docket
        from tests import test_parallel_pipeline as tpp

        async def capture_adjudicator(cmd, prompt, *a, **kw):
            if kw.get("stage_label") == "adjudicator":
                dockets.append(prompt)
                return _stage(tpp._fake_adjudicator_output(prompt))
            raise AssertionError(kw.get("stage_label"))
        monkeypatch.setattr(agent, "_run_stage", capture_adjudicator)
        _run(paper, _cfg({"use": "tools_agent", "tools": ["grim_check", "check_sd_range"]},
                         "adjudicator"))
        assert real is fakes and dockets
        assert "detect_duplication" in dockets[0] and "NOT run" in dockets[0]
        assert "every eligible target in the paper's tables was enumerated" not in dockets[0]

    @pytest.mark.usefixtures("image_package")
    def test_an_emitted_image_only_run_matches_its_build(self, paper, fakes,
                                                         monkeypatch, tmp_path):
        from metascience_observatory_image_analysis.image_forensics import pipeline as ip

        from forensic_metascience_ai_toolkit import runs

        async def fake_image(*a, **k):
            return {**ip.disabled_record(), "execution_status": "completed",
                    "ran": True, "detail": "faked"}
        monkeypatch.setattr(ip, "run", fake_image)
        r = _run(paper, pc.load("image_only"))
        d = tmp_path / "rev"
        d.mkdir()
        (d / "run_meta.json").write_text(json.dumps({**r["run_meta"], "git_dirty": False}))
        ok, why = runs.build_matches(d)
        assert ok, why

    def test_an_annotated_finding_still_validates(self, monkeypatch):
        import jsonschema
        monkeypatch.setattr(agent.shutil, "which", lambda name: "/bin/metascience")
        schema = prompts.findings_schema_v2()
        item = schema["properties"]["findings"]["items"]
        defs = {k: v for k, v in schema.items() if k in ("$defs", "definitions")}
        entry = {"producer": "tool_expert", "technique": "check_count_percent",
                 "reproduction": "metascience check-count-percent --decimals 0 10 50 30"}
        agent._annotate_reproductions(
            {"findings": {"findings": [entry]}}, paper_dir=None,
            disabled_verbs=parallel._disabled_verbs(frozenset(pc.load("tools_grim").toolset)))
        annotated = {k: entry[k] for k in ("reproduction_not_executed",)}
        props = item["properties"]
        assert "reproduction_not_executed" in props
        jsonschema.validate(annotated["reproduction_not_executed"],
                            {**props["reproduction_not_executed"], **defs})
        assert "reproduction_not_executed" not in (
            prompts.producer_findings_schema("tool_expert")["properties"]["findings"]
            ["items"]["properties"])

    def test_a_corrupt_older_review_does_not_block_drafting(self, tmp_path):
        from forensic_metascience_ai_toolkit import drafts
        (tmp_path / "forensic_review_a").mkdir()
        (tmp_path / "forensic_review_a" / "findings.v2.json").write_text("{corrupt")
        (tmp_path / "forensic_review_b").mkdir()
        (tmp_path / "forensic_review_b" / "findings.v2.json").write_text(json.dumps({
            "paper_id": "p", "pipeline": pc.load("full").record(),
            "findings": [{"finding_id": "f1", "outcome": "problem"}]}))
        payload = drafts._findings_payload(tmp_path, None)
        assert [f["finding_id"] for f in payload["findings"]] == ["f1"]

    @pytest.mark.parametrize("backend, repaired", [("claude", True),
                                                   ("codex", False), ("grok", False)])
    def test_partial_repair_fails_closed_where_tools_cannot_be_dropped(
            self, paper, fakes, monkeypatch, tmp_path, backend, repaired):
        monkeypatch.setenv("METASCIENCE_GROK_SKIP_FOLDER_TRUST", "1")
        monkeypatch.setenv("METASCIENCE_GROK_SANDBOX_ROOT", str(tmp_path / "g"))
        monkeypatch.setenv("METASCIENCE_CODEX_SANDBOX_ROOT", str(tmp_path / "c"))
        calls = []

        async def fake_repair(raw, schema, model, verbose, timeout, **kw):
            calls.append(kw)
            return None
        monkeypatch.setattr(agent, "_repair_json", fake_repair)
        fakes["tool"] = _stage(None, text="this is not json at all")
        cfg = _cfg("tools_agent", "scientific_proofreading_agent")
        r = _run(paper, cfg, backend=backend)
        if repaired:
            assert calls and calls[0].get("tool_free") is True
        else:
            assert calls == []
            assert any("NOT repaired" in x and backend in x for x in r["limitations"])


class TestBudgetSplitFollowsThePipeline:
    """The per-paper budget is split over the paid stages a pipeline RUNS.

    2026-10-18: a `tools_only` run capped its only agent at 40% of
    `--max-budget-usd`; two GRIM dev papers were cut off at ~$1.25 of $3."""

    def _share(self, name, fraction):
        from forensic_metascience_ai_toolkit.modules._analyst import stage_budget_share
        return stage_budget_share(pc.load(name), fraction)

    def test_the_full_pipeline_is_unchanged(self):
        from forensic_metascience_ai_toolkit import parallel
        assert self._share("full", parallel.TOOL_BUDGET_FRACTION) == pytest.approx(0.40)
        assert self._share("full", parallel.SCIENCE_BUDGET_FRACTION) == pytest.approx(0.25)

    def test_a_lone_tools_agent_gets_the_whole_budget(self):
        from forensic_metascience_ai_toolkit import parallel
        for name in ("tools_only", "tools_grim"):
            assert self._share(name, parallel.TOOL_BUDGET_FRACTION) == pytest.approx(1.0)

    def test_a_lone_proofreading_agent_gets_the_whole_budget(self):
        from forensic_metascience_ai_toolkit import parallel
        assert self._share("proofreading_only",
                           parallel.SCIENCE_BUDGET_FRACTION) == pytest.approx(1.0)

    def test_without_the_adjudicator_the_analysts_share_it(self):
        from forensic_metascience_ai_toolkit import parallel
        tools = self._share("no_adjudication", parallel.TOOL_BUDGET_FRACTION)
        science = self._share("no_adjudication", parallel.SCIENCE_BUDGET_FRACTION)
        assert tools + science == pytest.approx(1.0)
        assert tools > science

    def test_the_analyst_cap_uses_it(self):
        from types import SimpleNamespace

        from forensic_metascience_ai_toolkit import modules
        tools = modules.load("tools_agent")
        ctx = SimpleNamespace(budget_usd=3.0, config=pc.load("tools_only"))
        assert tools.budget(ctx) == pytest.approx(3.0)
        ctx = SimpleNamespace(budget_usd=3.0, config=pc.load("full"))
        assert tools.budget(ctx) == pytest.approx(1.2)
