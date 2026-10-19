"""Phase 2: modules are folders, the core schedules them, merge order is fixed.

The contract (docs/specs/modules.md): a module is `modules/<name>/MODULE.md`
+ `module.py`; producers start when what they `need` has FINISHED (not
succeeded), with no layer barriers; results merge in canonical order, never
completion order; a module that raises (and did not catch it itself)
propagates; every task is registered for cleanup before anything is
awaited; a module can run on its own backend.
"""

import asyncio
import json

import pytest

from forensic_metascience_ai_toolkit import agent, modules
from forensic_metascience_ai_toolkit import pipeline_config as pc
from forensic_metascience_ai_toolkit.core import scheduler
from forensic_metascience_ai_toolkit.modules import ModuleResult
from forensic_metascience_ai_toolkit.modules.base import Module, ModuleDef
from tests.test_parallel_pipeline import _doc, _row, _stage, fakes, paper  # noqa: F401


def _cfg(*mods, **top):
    return pc.parse({"schema_version": 1, "name": top.pop("name", "t"),
                     "modules": list(mods), **top})


class TestRegistry:
    def test_every_module_folder_declares_itself(self):
        defs = modules.definitions()
        assert list(defs) == ["tools_agent", "scientific_proofreading_agent",
                              "image_analysis",
                              "text_forensics", "raw_data", "adjudicator"]
        assert [d.order for d in defs.values()] == sorted(d.order for d in defs.values())
        assert pc.MODULES == defs

    def test_stored_producers_are_unchanged(self):
        defs = modules.definitions()
        assert defs["tools_agent"].producer == "tool_expert"
        assert defs["scientific_proofreading_agent"].producer == "science_error"

    def test_every_module_loads_with_its_contract(self):
        for name, d in modules.definitions().items():
            m = modules.load(name)
            assert m.definition is d
            if d.kind == "finalizer":
                assert hasattr(m, "finalize")
            else:
                assert type(m).run is not Module.run, name

    @pytest.mark.parametrize("front, fragment", [
        ("name: x\nkind: agent\nproducer: p\nlabel: l\n", "missing ['order']"),
        ("name: x\nkind: agent\nproducer: p\nlabel: l\norder: 1\ncolour: red\n",
         "unknown ['colour']"),
        ("name: y\nkind: agent\nproducer: p\nlabel: l\norder: 1\n", "must match"),
        ("name: x\nkind: wizard\nproducer: p\nlabel: l\norder: 1\n", "kind must be"),
    ])
    def test_a_malformed_module_md_is_refused(self, tmp_path, front, fragment):
        d = tmp_path / "x"
        d.mkdir()
        (d / "MODULE.md").write_text(f"---\n{front}---\nbody\n")
        with pytest.raises(modules.ModuleDefinitionError) as exc:
            modules._parse(d / "MODULE.md")
        assert fragment in str(exc.value)


class _Fake(Module):
    def __init__(self, name, needs=(), delay=0.0, log=None, fail=False):
        self.definition = ModuleDef(name, "deterministic", None, name,
                                    needs=tuple(needs))
        self.delay, self.log, self.fail = delay, log, fail

    async def run(self, ctx, needed):
        self.log.append(("start", self.name, sorted(needed)))
        await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError(f"{self.name} broke")
        self.log.append(("end", self.name))
        return ModuleResult(self.name, limitations=[f"{self.name} ran"])


class _Spec:
    def __init__(self, module):
        self.use, self.definition = module.name, module.definition


def _schedule(mods, background=None):
    background = [] if background is None else background
    specs = [_Spec(m) for m in mods]
    return asyncio.run(scheduler.run_producers(
        None, specs, {m.name: m for m in mods}, background)), background


class TestScheduler:
    def test_independent_modules_start_together(self):
        log = []
        a, b = _Fake("a", delay=0.05, log=log), _Fake("b", delay=0.05, log=log)
        _schedule([a, b])
        assert [e[:2] for e in log[:2]] == [("start", "a"), ("start", "b")]

    def test_a_module_waits_only_for_what_it_needs_and_receives_it(self):
        log = []
        slow = _Fake("slow", delay=0.05, log=log)
        dep = _Fake("dep", needs=["slow"], log=log)
        free = _Fake("free", log=log)
        results, _ = _schedule([slow, dep, free])
        order = [e[:2] for e in log]
        assert order.index(("end", "slow")) < order.index(("start", "dep"))
        assert order.index(("end", "free")) < order.index(("end", "slow"))
        assert ("start", "dep", ["slow"]) in log
        assert set(results) == {"slow", "dep", "free"}

    def test_an_uncaught_failure_propagates_and_every_task_is_registered(self):
        log, background = [], []
        a = _Fake("a", fail=True, log=log)
        b = _Fake("b", delay=0.01, log=log)
        with pytest.raises(RuntimeError, match="a broke"):
            _schedule([a, b], background)
        assert len(background) == 2


class TestOrchestration:
    def test_merge_order_is_canonical_not_completion_order(self, paper, fakes,
                                                           monkeypatch):
        real_requiring = agent._run_stage_requiring_forensic_tools

        async def slow_tool(**kw):
            await asyncio.sleep(0.05)       # the science analyst finishes first
            return await real_requiring(**kw)
        monkeypatch.setattr(agent, "_run_stage_requiring_forensic_tools", slow_tool)
        r = asyncio.run(agent.analyze_paper(
            str(paper), mode="parallel", pipeline=_cfg(
                "tools_agent", "scientific_proofreading_agent")))
        producers = [f["producer"] for f in r["findings_v2"]["findings"]]
        assert producers == sorted(producers, key=["tool_expert", "science_error"].index)
        assert fakes["calls"][:2] == ["science_agent", "tool_agent"]

    def test_a_failed_analyst_does_not_sink_the_other(self, paper, fakes):
        fakes["tool"] = RuntimeError("tool boom")
        r = asyncio.run(agent.analyze_paper(
            str(paper), mode="parallel", pipeline=_cfg(
                "tools_agent", "scientific_proofreading_agent")))
        assert any("tool_agent stage failed" in x for x in r["limitations"])
        assert {f["producer"] for f in r["findings_v2"]["findings"]} == {"science_error"}


class TestPerModuleBackend:
    def test_backend_only_on_modules_that_call_a_model(self):
        with pytest.raises(pc.PipelineConfigError, match="calls no model"):
            _cfg({"use": "text_forensics", "backend": {"name": "grok"}})

    def test_a_module_runs_on_its_own_backend(self, paper, fakes, monkeypatch,
                                              tmp_path):
        monkeypatch.setenv("METASCIENCE_GROK_SKIP_FOLDER_TRUST", "1")
        monkeypatch.setenv("METASCIENCE_GROK_SANDBOX_ROOT", str(tmp_path / "g"))
        seen = {}
        real = agent._build_claude_cmd

        def spy(*a, **k):
            seen.setdefault(k.get("mcp_stage"), (k.get("backend"), k.get("model")))
            return real(*a, **k)
        monkeypatch.setattr(agent, "_build_claude_cmd", spy)
        cfg = _cfg({"use": "tools_agent", "backend": {"name": "grok"}},
                   "scientific_proofreading_agent", "adjudicator",
                   backend={"name": "claude", "model": "opus"})
        r = asyncio.run(agent.analyze_paper(str(paper), mode="parallel", pipeline=cfg))
        assert seen["tool_agent"] == ("grok", "grok-4.6")
        assert seen["science_agent"] == ("claude", "opus")
        assert seen["adjudicator"] == ("claude", "opus")
        assert r["run_meta"]["stages"]["tool_agent"]["llm_backend"] == "grok"
        assert "llm_backend" not in r["run_meta"]["stages"]["science_agent"]
        rec = pc.from_record(json.loads(json.dumps(r["run_meta"]["pipeline"])))
        assert rec.module("tools_agent").backend == {"name": "grok"}

    def test_a_budget_needs_every_model_module_to_support_one(self, paper, fakes):
        from forensic_metascience_ai_toolkit.llm_backend import BudgetUnsupported
        cfg = _cfg({"use": "tools_agent", "backend": {"name": "codex"}},
                   backend={"name": "claude"})
        with pytest.raises(BudgetUnsupported, match="tools_agent runs on codex"):
            asyncio.run(agent.analyze_paper(str(paper), mode="parallel",
                                            pipeline=cfg, budget_usd=5.0))


class TestPromptsLiveWithTheirModules:
    """2026-10-15: each agent's system prompt is `modules/<name>/prompt.md`,
    the shared text `core/prompts/`. Every scanner of prompt text reads
    `prompts.prompt_files()`; a glob of `prompts/` alone would have silently
    stopped seeing the moved files (handoff's second_look check and
    test_prompt_contract's `_md` both did, until fixed with the move)."""

    def test_every_named_prompt_exists_where_the_table_says(self):
        from forensic_metascience_ai_toolkit.core import prompts
        for name, path in prompts.PROMPT_FILES.items():
            assert path.is_file(), name
            assert prompts.prompt_path(name) == path
        for mod in ("tools_agent", "scientific_proofreading_agent", "adjudicator"):
            assert modules.definitions()[mod].prompt == "prompt.md"
            assert (prompts._PKG / "modules" / mod / "prompt.md").is_file()

    def test_the_scanner_list_covers_every_prompt(self):
        from forensic_metascience_ai_toolkit.core import prompts
        files = set(prompts.prompt_files())
        assert set(prompts.PROMPT_FILES.values()) <= files

    def test_the_old_prompts_package_is_gone(self):
        """`metascience_agent/prompts/` was retired on 2026-10-18: the loader
        is `core/prompts/__init__.py`, the schemas `forensic_metascience_ai_toolkit/schema/`.
        A file put back there would be read by nothing."""
        from forensic_metascience_ai_toolkit.core import prompts
        assert not (prompts._PKG / "prompts").exists()
        shared = {p for p in prompts.PROMPTS_DIR.glob("*.md")}
        assert shared <= set(prompts.PROMPT_FILES.values())
