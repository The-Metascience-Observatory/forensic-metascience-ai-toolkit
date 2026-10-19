"""Codex CLI backend: stream normalizer, argv, isolation, budget refuse.

The fixture `tests/data/codex_exec_stream.jsonl` is a REAL captured
`codex exec --json` stream (codex-cli 0.147.0, gpt-5.6-sol, 2026-09-01):
one MCP round-trip through the forensic server (`grim_check` on
mean=3.53/n=30, which IS consistent -- the GRIM invariant), two agent
messages, and a `turn.completed` with token usage and no cost figure.

A normalizer that stops mapping `mcp_tool_call` items would make the
ledger report zero forensic checks -- our plumbing failure rendered as a
clean paper. And the reason the approval config is pinned here at all:
without `default_tools_approval_mode="approve"` the MCP call FAILED and
the model then FABRICATED the tool's verdict in its final JSON (measured
2026-09-01 canary run).
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from metascience_agent import agent as A
from metascience_agent.llm_backend import (
    CLAUDE,
    CODEX,
    CODEX_DISABLED_FEATURES,
    CODEX_SKILLS_CONFIG,
    CODEX_NO_INTERNET_DOMAIN,
    GROK,
    BudgetUnsupported,
    CodexStreamNormalizer,
    MCPUnavailable,
    build_invocation,
    codex_config_isolation_row,
    codex_enabled_tools,
    make_stream_normalizer,
    mcp_discovery_error,
    mcp_discovery_from_init,
    resolve_backend,
    reset_mcp_live_cache,
    sandbox_limitation_sentence,
)
from metascience_agent.usage_guard import UNSUPPORTED

DATA = Path(__file__).parent / "data"


def _events_from_fixture(name: str) -> list[dict]:
    out = []
    for line in (DATA / name).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _normalize_all(events, *, expects_schema=True) -> list[dict]:
    norm = CodexStreamNormalizer(expects_schema=expects_schema)
    out: list[dict] = []
    for e in events:
        out.extend(norm.feed(e))
    return out


class TestResolveBackend:
    def test_codex_is_a_backend(self, monkeypatch):
        monkeypatch.delenv("METASCIENCE_LLM_CLI", raising=False)
        assert resolve_backend("codex") is CODEX
        monkeypatch.setenv("METASCIENCE_LLM_CLI", "codex")
        assert resolve_backend(None).name == "codex"

    def test_error_names_every_backend(self):
        with pytest.raises(ValueError, match="'claude', 'grok', 'codex', 'openrouter' or 'antigravity'"):
            resolve_backend("cursor")

    def test_capabilities(self):
        assert CODEX.supports_budget is False
        assert CODEX.supports_usage_probe is True  # app-server rateLimits
        assert CODEX.mcp_strategy == "config_overrides"
        assert CODEX.sandbox_weaker is True
        assert CODEX.prompt_delivery == "stdin"


class TestABareConstOrEnumGainsItsType:
    """MEASURED LIVE 2026-09-02, on the image adjudicator pointed at codex:
    the stage died with exit 1 and an EMPTY stderr, the 400 buried in its
    stdout stream -- "In context=('properties', 'schema_version'), schema
    must have a 'type' key". Draft-07 lets a `const` (and an `enum`) stand
    without a type; the strict validator does not. Four shipped schemas
    carry such a node, and the two-stage findings schemas do not, which is
    why a backend that had shipped still could not adjudicate an image.
    """

    def test_every_shipped_schema_survives_the_transform(self):
        import glob
        import json as _json

        from metascience_agent.llm_backend import codex_strict_schema

        def typeless(node, path=""):
            if isinstance(node, dict):
                keyed = ("const" in node or "enum" in node
                         or "properties" in node)
                if keyed and "type" not in node and not any(
                        k in node for k in ("anyOf", "oneOf", "allOf", "$ref")):
                    yield path or "/"
                for k, v in node.items():
                    yield from typeless(v, f"{path}/{k}")
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    yield from typeless(v, f"{path}[{i}]")

        here = Path(__file__).resolve().parent.parent
        schemas = sorted(glob.glob(
            str(here / "src/metascience_agent/schema/*.json")))
        assert schemas, "no schemas found"
        offenders = {}
        for path in schemas:
            hits = list(typeless(codex_strict_schema(
                _json.loads(Path(path).read_text()))))
            if hits:
                offenders[Path(path).name] = hits[:3]
        assert not offenders, offenders

    def test_the_implied_type_is_the_value_s_own(self):
        from metascience_agent.llm_backend import codex_strict_schema
        out = codex_strict_schema({
            "type": "object", "required": ["a", "b", "c", "d", "e"],
            "properties": {"a": {"const": "1.0"}, "b": {"const": 3},
                           "c": {"const": True},
                           "d": {"enum": ["x", "y"]},
                           "e": {"enum": ["x", None]}},
        })
        p = out["properties"]
        assert p["a"]["type"] == "string" and p["a"]["const"] == "1.0"
        assert p["b"]["type"] == "integer"
        # bool BEFORE int: True is an int in Python
        assert p["c"]["type"] == "boolean"
        assert p["d"]["type"] == "string"
        assert p["e"]["type"] == ["string", "null"]

    def test_a_declared_type_is_never_overwritten(self):
        from metascience_agent.llm_backend import codex_strict_schema
        out = codex_strict_schema({
            "type": "object", "required": ["a"],
            "properties": {"a": {"type": "string", "const": "1.0"}}})
        assert out["properties"]["a"]["type"] == "string"



class TestNormalizerKnownPositive:
    def test_ledger_records_the_forensic_call(self):
        events = _normalize_all(_events_from_fixture("codex_exec_stream.jsonl"))
        ledger = A._tool_call_ledger(events, A.STAGE1_TOOLS)
        rows = [r for r in ledger if r["tool_short"] == "grim_check"]
        assert rows and rows[0]["validated"]

    def test_init_synthesized_from_thread_started(self):
        events = _normalize_all(_events_from_fixture("codex_exec_stream.jsonl"))
        init = events[0]
        assert init["type"] == "system" and init["subtype"] == "init"
        assert init["session_id"]

    def test_result_usage_mapped_and_no_cost_key(self):
        events = _normalize_all(_events_from_fixture("codex_exec_stream.jsonl"))
        results = [e for e in events if e.get("type") == "result"]
        assert len(results) == 1
        usage = results[0]["usage"]
        # Real figures from the captured turn.completed; `cached_input_tokens`
        # maps to cache READS, `cache_write_input_tokens` to cache creation.
        assert usage["input_tokens"] == 28848
        assert usage["output_tokens"] == 727
        assert usage["cache_read_input_tokens"] == 13056
        assert usage["cache_creation_input_tokens"] == 0
        # No cost figure exists in a codex stream; a synthesized one would be
        # a fabrication. Its absence is what keeps stage cost at 0.0.
        assert "total_cost_usd" not in results[0]

    def test_structured_output_parsed_from_final_message(self):
        events = _normalize_all(_events_from_fixture("codex_exec_stream.jsonl"))
        result = [e for e in events if e.get("type") == "result"][0]
        assert result["structured_output"]["grim_severity"] == "consistent"

    def test_no_schema_no_structured_output(self):
        events = _normalize_all(
            _events_from_fixture("codex_exec_stream.jsonl"),
            expects_schema=False)
        result = [e for e in events if e.get("type") == "result"][0]
        assert "structured_output" not in result

    def test_completed_without_started_emits_call_and_result(self):
        norm = CodexStreamNormalizer()
        out = norm.feed({
            "type": "item.completed",
            "item": {"id": "x1", "type": "mcp_tool_call",
                     "server": "forensic_metascience", "tool": "grim_check",
                     "arguments": {"mean": 1.0},
                     "result": {"content": [{"type": "text", "text": "{}"}]},
                     "error": None, "status": "completed"},
        })
        assert [e["type"] for e in out] == ["assistant", "user"]
        block = out[0]["message"]["content"][0]
        assert block["name"] == "mcp__forensic_metascience__grim_check"
        assert block["input"] == {"mean": 1.0}
        assert out[1]["message"]["content"][0]["tool_use_id"] == "x1"

    def test_foreign_server_stays_unvalidated(self):
        norm = CodexStreamNormalizer()
        out = norm.feed({
            "type": "item.started",
            "item": {"id": "f1", "type": "mcp_tool_call",
                     "server": "codex_apps", "tool": "github_search",
                     "arguments": {}, "result": None, "error": None,
                     "status": "in_progress"},
        })
        name = out[0]["message"]["content"][0]["name"]
        assert name == "mcp__codex_apps__github_search"
        ledger = A._tool_call_ledger(out, A.STAGE1_TOOLS)
        assert all(not r["validated"] for r in ledger)

    def test_command_execution_maps_to_Bash(self):
        norm = CodexStreamNormalizer()
        out = norm.feed({
            "type": "item.completed",
            "item": {"id": "c1", "type": "command_execution",
                     "command": "echo hi", "aggregated_output": "hi\n",
                     "exit_code": 0, "status": "completed"},
        })
        assert out[0]["message"]["content"][0]["name"] == "Bash"
        assert out[0]["message"]["content"][0]["input"] == {"command": "echo hi"}
        assert out[1]["message"]["content"][0]["content"] == "hi\n"

    def test_web_search_maps_to_WebSearch(self):
        norm = CodexStreamNormalizer()
        out = norm.feed({
            "type": "item.started",
            "item": {"id": "w1", "type": "web_search", "query": "grim test"},
        })
        assert out[0]["message"]["content"][0]["name"] == "WebSearch"

    def test_mcp_error_result_is_flagged(self):
        # The measured failure mode this maps: an unapproved MCP call errors
        # and the model fabricates the verdict. The error must be VISIBLE as
        # an is_error tool_result, never dropped.
        norm = CodexStreamNormalizer()
        out = norm.feed({
            "type": "item.completed",
            "item": {"id": "e1", "type": "mcp_tool_call",
                     "server": "forensic_metascience", "tool": "grim_check",
                     "arguments": {}, "result": None,
                     "error": {"message": "MCP tool call requires approval"},
                     "status": "failed"},
        })
        block = out[-1]["message"]["content"][0]
        assert block["is_error"] is True
        assert "requires approval" in block["content"]

    def test_turn_failed_becomes_error_result(self):
        norm = CodexStreamNormalizer()
        out = norm.feed({"type": "turn.failed",
                         "error": {"message": "boom went the turn"}})
        assert out[0]["type"] == "result"
        assert out[0]["is_error"] is True
        assert out[0]["subtype"] == "codex_turn_failed"
        assert out[0]["errors"] == ["boom went the turn"]

    def test_unknown_events_pass_through(self):
        norm = CodexStreamNormalizer()
        raw = {"type": "turn.started"}
        assert norm.feed(raw) == [raw]

    def test_claude_and_grok_get_the_stateless_wrapper(self):
        for be in (CLAUDE, GROK):
            n = make_stream_normalizer(be)
            ev = {"type": "assistant", "message": {"content": []}}
            assert n.feed(ev) == [ev]
        assert isinstance(make_stream_normalizer(CODEX), CodexStreamNormalizer)


class TestCodexInvocation:
    @pytest.fixture
    def sandbox_root(self, tmp_path, monkeypatch):
        monkeypatch.setenv("METASCIENCE_CODEX_SANDBOX_ROOT",
                           str(tmp_path / "csb"))
        return tmp_path

    SCHEMA = {"type": "object",
              "properties": {"ok": {"type": "boolean"},
                             "note": {"type": "string"}},
              "required": ["ok"]}

    def _build(self, **kw):
        defaults = dict(
            system_prompt="SYSTEM " * 30_000,  # ~210 KB: over MAX_ARG_STRLEN
            allowed_tools=["mcp__forensic_metascience__grim_check",
                           "mcp__forensic_metascience__extract_pdf"],
            model="gpt-5.6-sol",
            effort="high",
            json_schema=self.SCHEMA,
        )
        defaults.update(kw)
        return build_invocation(CODEX, **defaults)

    def test_isolation_flags_always_present(self, sandbox_root):
        inv = self._build()
        try:
            for flag in ("--ignore-user-config", "--ephemeral", "--json",
                         "--skip-git-repo-check"):
                assert flag in inv.argv
            # CODEX_HOME must stay untouched: auth lives there.
            assert "CODEX_HOME" not in inv.env_overlay
        finally:
            inv.cleanup()

    def test_prompt_never_on_argv_it_is_in_AGENTS_md(self, sandbox_root):
        inv = self._build()
        try:
            assert max(len(a) for a in inv.argv) < 100_000
            assert inv.argv[-1] == "-"          # explicit stdin sentinel
            assert inv.prompt_delivery == "stdin"
            agents = (inv.workdir / "AGENTS.md").read_text(encoding="utf-8")
            assert agents.startswith("SYSTEM ")
            assert len(agents) > 200_000
        finally:
            inv.cleanup()

    def test_schema_is_a_strict_dialect_file_not_inline(self, sandbox_root):
        inv = self._build()
        try:
            i = inv.argv.index("--output-schema")
            schema_path = Path(inv.argv[i + 1])
            assert schema_path == inv.workdir / "schema.json"
            written = json.loads(schema_path.read_text())
            # The FILE carries the strict dialect (every key required,
            # additionalProperties false, optionals nullable); the
            # Invocation carries the ORIGINAL for restore_from_strict.
            assert written["additionalProperties"] is False
            assert set(written["required"]) == {"ok", "note"}
            assert written["properties"]["note"] == {
                "anyOf": [{"type": "string"}, {"type": "null"}]}
            assert inv.expects_schema is True
            assert inv.restore_schema == self.SCHEMA
        finally:
            inv.cleanup()

    def test_no_schema_no_output_flags(self, sandbox_root):
        inv = self._build(json_schema=None)
        try:
            assert "--output-schema" not in inv.argv
            assert inv.expects_schema is False
        finally:
            inv.cleanup()

    def test_enabled_tools_is_the_stage_allowlist(self, sandbox_root):
        inv = self._build()
        try:
            row = [a for a in inv.argv if "enabled_tools=[" in a]
            assert row == ['mcp_servers.forensic_metascience.enabled_tools='
                           '["extract_pdf", "grim_check"]']
        finally:
            inv.cleanup()

    def test_approve_mode_and_fence_env(self, sandbox_root, tmp_path):
        inv = self._build(paper_dir=tmp_path / "paper",
                          mcp_stage="tool_agent", run_slug="slug-1")
        try:
            joined = " ".join(inv.argv)
            # Without "approve" every MCP call fails and the model fabricates
            # the verdict (measured) -- this line is load-bearing.
            assert ('mcp_servers.forensic_metascience.'
                    'default_tools_approval_mode="approve"') in inv.argv
            assert 'METASCIENCE_MCP_STAGE = "tool_agent"' in joined
            assert 'METASCIENCE_RUN_SLUG = "slug-1"' in joined
            assert "METASCIENCE_PAPER_DIR" in joined
        finally:
            inv.cleanup()

    def test_internet_delta_is_exactly_the_web_search_value(self, sandbox_root):
        off = self._build(internet=False)
        on = self._build(internet=True)
        try:
            def _rows(inv):
                return [a for a in inv.argv if "web_search" in a]
            assert _rows(on) == ["tools.web_search=true"]
            # `false` alone does NOT block egress (measured); the sentinel
            # allowlist is what actually blocked the fetch.
            assert _rows(off) == [
                "tools.web_search={ enabled = false, allowed_domains = ["
                f'"{CODEX_NO_INTERNET_DOMAIN}"] }}'
            ]
            strip = {"-C"}
            a = [x for x in off.argv if str(off.workdir) not in x and x not in strip]
            b = [x for x in on.argv if str(on.workdir) not in x and x not in strip]
            delta = ({tuple(a)} ^ {tuple(b)})
            assert [x for x in a if x not in b] == [_rows(off)[0]]
            assert [x for x in b if x not in a] == ["tools.web_search=true"]
        finally:
            off.cleanup()
            on.cleanup()

    def test_capability_features_are_disabled(self, sandbox_root):
        inv = self._build()
        try:
            for feature in ("apps", "browser_use", "computer_use",
                            "shell_snapshot"):
                assert feature in CODEX_DISABLED_FEATURES
            disabled = [inv.argv[i + 1] for i, a in enumerate(inv.argv)
                        if a == "--disable"]
            assert disabled == list(CODEX_DISABLED_FEATURES)
        finally:
            inv.cleanup()

    def test_the_operators_skills_are_not_listed(self, sandbox_root):
        """MEASURED 2026-10-11: `--ignore-user-config` does not stop Codex
        listing ~/.agents/skills in the prompt, and a terra science agent read
        a synced SKILL.md as its first call. This key is what removes it."""
        inv = self._build()
        try:
            i = inv.argv.index(CODEX_SKILLS_CONFIG)
            assert inv.argv[i - 1] == "-c"
            assert CODEX_SKILLS_CONFIG == "skills.include_instructions=false"
        finally:
            inv.cleanup()

    def test_read_only_sandbox_and_never_approval(self, sandbox_root):
        inv = self._build()
        try:
            i = inv.argv.index("-s")
            assert inv.argv[i + 1] == "read-only"
            assert 'approval_policy="never"' in inv.argv
        finally:
            inv.cleanup()

    def test_max_turns_is_stamped_not_sent(self, sandbox_root):
        inv = self._build(max_turns=1)
        try:
            assert "--max-turns" not in inv.argv
            assert inv.max_turns_unsupported is True
            assert self._build().max_turns_unsupported is False
        finally:
            inv.cleanup()

    def test_budget_raises(self, sandbox_root):
        with pytest.raises(BudgetUnsupported):
            self._build(budget_usd=2.0)

    def test_cleanup_removes_the_run_dir(self, sandbox_root):
        inv = self._build()
        workdir = inv.workdir
        assert workdir.exists()
        inv.cleanup()
        assert not workdir.exists()

    def test_enabled_tools_helper_ignores_non_mcp(self):
        assert codex_enabled_tools(
            ["Read", "mcp__forensic_metascience__grim_check"]
        ) == ["grim_check"]


class TestStrictSchemaRoundTrip:
    """codex --output-schema hits OpenAI's STRICT validator (measured
    2026-09-01: rejected both a free-form `inputs` object and an optional
    `flips_significance`). The transform makes the contract expressible;
    the restore makes the parsed document identical to a Claude run's."""

    def test_every_object_is_closed_and_fully_required(self):
        from metascience_agent.llm_backend import codex_strict_schema
        from metascience_agent.core import prompts
        strict = codex_strict_schema(
            prompts.producer_findings_schema("tool_expert", figures=False))

        def check(node, path=""):
            if not isinstance(node, dict):
                return
            if node.get("type") == "object" or "properties" in node:
                assert node.get("additionalProperties") is False, path
                assert set(node.get("required") or []) == set(
                    (node.get("properties") or {}).keys()), path
            for k, v in node.items():
                if isinstance(v, dict):
                    check(v, f"{path}/{k}")
                elif isinstance(v, list):
                    for i, x in enumerate(v):
                        check(x, f"{path}/{k}[{i}]")

        check(strict)

    def test_freeform_objects_become_json_strings(self):
        from metascience_agent.llm_backend import codex_strict_schema
        strict = codex_strict_schema({
            "type": "object",
            "properties": {"inputs": {"type": "object",
                                      "additionalProperties": True}},
            "required": ["inputs"],
        })
        assert strict["properties"]["inputs"]["type"] == "string"
        assert "serialized" in strict["properties"]["inputs"]["description"]

    def test_restore_parses_strings_and_drops_standin_nulls(self):
        from metascience_agent.llm_backend import restore_from_strict
        original = {
            "type": "object",
            "properties": {
                "findings": {"type": "array", "items": {
                    "type": "object",
                    "properties": {
                        "slug": {"type": "string"},
                        "quote": {"type": "string"},        # optional
                        "inputs": {"type": "object",
                                   "additionalProperties": True},
                    },
                    "required": ["slug"],
                }},
            },
            "required": ["findings"],
        }
        strict_output = {"findings": [{
            "slug": "grim-1",
            "quote": None,                       # stand-in for absent
            "inputs": "{\"mean\": 3.53, \"n\": 30}",
        }]}
        restored = restore_from_strict(strict_output, original)
        assert restored == {"findings": [{
            "slug": "grim-1",
            "inputs": {"mean": 3.53, "n": 30},
        }]}

    def test_restore_keeps_a_null_the_original_allows(self):
        from metascience_agent.llm_backend import restore_from_strict
        original = {"type": "object",
                    "properties": {"dup": {"type": ["string", "null"]}},
                    "required": []}
        assert restore_from_strict({"dup": None}, original) == {"dup": None}

    def test_restore_leaves_unparseable_strings_alone(self):
        from metascience_agent.llm_backend import restore_from_strict
        original = {"type": "object",
                    "properties": {"inputs": {"type": "object"}},
                    "required": ["inputs"]}
        out = restore_from_strict({"inputs": "not json {"}, original)
        assert out == {"inputs": "not json {"}

    def test_normalizer_applies_the_restore(self):
        original = {"type": "object",
                    "properties": {"inputs": {"type": "object"},
                                   "opt": {"type": "string"}},
                    "required": ["inputs"]}
        norm = CodexStreamNormalizer(expects_schema=True,
                                     restore_schema=original)
        norm.feed({"type": "item.completed",
                   "item": {"id": "m", "type": "agent_message",
                            "text": json.dumps(
                                {"inputs": "{\"a\": 1}", "opt": None})}})
        out = norm.feed({"type": "turn.completed", "usage": {}})
        assert out[0]["structured_output"] == {"inputs": {"a": 1}}


class TestDiscoveryAndLimitation:
    def test_codex_init_discovery_is_honest_and_ok(self):
        disc = mcp_discovery_from_init(
            {"type": "system", "subtype": "init"}, CODEX)
        # The stream declares NOTHING about MCP servers: unknown is None,
        # never False, and it must not abort the stage.
        assert disc["declared"] is None
        assert disc["ok"] is True
        assert disc["status_is_live"] is False
        assert mcp_discovery_error(disc) is None

    def test_limitation_sentences_are_per_backend(self):
        codex_s = sandbox_limitation_sentence(CODEX)
        grok_s = sandbox_limitation_sentence(GROK)
        assert "read-only shell" in codex_s
        assert "search_tool" in grok_s
        assert sandbox_limitation_sentence(CLAUDE) is None


class TestLivenessProbe:
    def _fake_run(self, monkeypatch, stdout="", stderr="", returncode=0,
                  raise_exc=None):
        import subprocess as sp
        calls = []

        def fake(*a, **kw):
            calls.append((a, kw))
            if raise_exc is not None:
                raise raise_exc
            class R:
                pass
            r = R()
            r.stdout, r.stderr, r.returncode = stdout, stderr, returncode
            return r

        import metascience_agent.llm_backend as lb
        monkeypatch.setattr(lb.subprocess, "run", fake)
        return calls

    def test_tools_listed_passes(self, monkeypatch):
        from metascience_agent.llm_backend import _probe_mcp_stdio
        ok = json.dumps({"jsonrpc": "2.0", "id": 2,
                         "result": {"tools": [{"name": "grim_check"}]}})
        self._fake_run(monkeypatch, stdout=ok + "\n")
        _probe_mcp_stdio()  # does not raise

    def test_zero_tools_raises(self, monkeypatch):
        from metascience_agent.llm_backend import _probe_mcp_stdio
        empty = json.dumps({"jsonrpc": "2.0", "id": 2, "result": {"tools": []}})
        self._fake_run(monkeypatch, stdout=empty + "\n")
        with pytest.raises(MCPUnavailable, match="0 tools"):
            _probe_mcp_stdio()

    def test_no_response_raises(self, monkeypatch):
        from metascience_agent.llm_backend import _probe_mcp_stdio
        self._fake_run(monkeypatch, stdout="", stderr="ImportError: mcp",
                       returncode=1)
        with pytest.raises(MCPUnavailable, match="no tools/list response"):
            _probe_mcp_stdio()

    def test_assert_mcp_live_uses_the_stdio_probe_and_caches(self, monkeypatch):
        reset_mcp_live_cache()
        import metascience_agent.llm_backend as lb
        calls = []
        monkeypatch.setattr(lb, "_probe_mcp_stdio",
                            lambda *a, **k: calls.append(1))
        monkeypatch.delenv("METASCIENCE_SKIP_MCP_LIVE", raising=False)
        CODEX.assert_mcp_live(None)
        CODEX.assert_mcp_live(None)
        assert calls == [1]
        reset_mcp_live_cache()

    def test_liveness_probe_against_the_real_server(self):
        # Free and offline: spawns OUR OWN MCP server over stdio and requires
        # tools. This is the probe a real codex run performs before spend.
        from metascience_agent.llm_backend import _probe_mcp_stdio
        _probe_mcp_stdio()


class TestIsolationRow:
    def test_missing_binary_is_not_ok(self, monkeypatch):
        import metascience_agent.llm_backend as lb
        monkeypatch.setattr(lb.shutil, "which", lambda name: None)
        name, ok, detail = codex_config_isolation_row()
        assert not ok and "not on PATH" in detail

    def test_present_binary_is_structurally_ok(self, monkeypatch):
        import metascience_agent.llm_backend as lb
        monkeypatch.setattr(lb.shutil, "which", lambda name: "/usr/bin/codex")

        def fake_run(*a, **kw):
            class R:
                stdout = json.dumps([{"name": "some_user_server"}])
                stderr = ""
                returncode = 0
            return R()

        monkeypatch.setattr(lb.subprocess, "run", fake_run)
        name, ok, detail = codex_config_isolation_row()
        assert ok
        assert "--ignore-user-config" in detail
        assert "some_user_server" in detail


class TestUsageIsProbedFromTheAppServer:
    """Codex used to be UNSUPPORTED here and ran unguarded into its 5-hour
    window. The probe is `codex app-server`'s account/rateLimits/read; a
    `claude -p /usage` probe of the OPERATOR's Claude account must never be
    what guards a codex run (that is the grok mistake of 2026-08-19)."""

    def test_codex_probes_its_own_app_server_not_claude(self, monkeypatch):
        from metascience_agent import usage_guard as ug
        spawned = []
        answer = (b'{"jsonrpc":"2.0","id":2,"result":{"rateLimits":{"primary":'
                  b'{"usedPercent":36},"secondary":{"usedPercent":28}}}}\n')

        class _Out:
            async def readline(self_):
                return spawned and answer if not getattr(self_, "sent", False) \
                    else b""

        class _Proc:
            stdin = _FakeStdin()
            def __init__(self):
                self.stdout = _Out()
            def kill(self): pass
            async def wait(self): return 0

        async def fake_exec(*a, **kw):
            spawned.append(a)
            return _Proc()

        monkeypatch.setattr(ug.asyncio, "create_subprocess_exec", fake_exec)
        snap = asyncio.run(ug.probe_usage(backend="codex"))
        assert snap == (36, 28)
        assert spawned and spawned[0][:2] == ("codex", "app-server")
        assert not any(a[0] == "claude" for a in spawned)


class _FakeStdin:
    def __init__(self):
        self.written = b""

    def write(self, data: bytes) -> None:
        self.written += data

    def close(self) -> None:
        pass

    async def drain(self) -> None:
        pass


class _FakeProc:
    def __init__(self, payload: bytes):
        self.stdout = asyncio.StreamReader()
        self.stdout.feed_data(payload)
        self.stdout.feed_eof()
        self.stderr = asyncio.StreamReader()
        self.stderr.feed_eof()
        self.stdin = _FakeStdin()
        self.killed = False
        self.returncode = None

    async def wait(self):
        self.returncode = 0
        return 0

    def kill(self):
        self.killed = True


def _payload_from_events(events: list[dict]) -> bytes:
    return b"".join((json.dumps(e) + "\n").encode() for e in events)


@pytest.fixture
def codex_stage_env(tmp_path, monkeypatch):
    monkeypatch.setenv("METASCIENCE_CODEX_SANDBOX_ROOT", str(tmp_path / "csb"))
    monkeypatch.setenv("METASCIENCE_SKIP_PREFLIGHT", "1")
    monkeypatch.setattr(A, "_assert_ready", lambda *a, **k: None)

    async def _no_guard(*a, **k):
        return None

    monkeypatch.setattr(A, "usage_guard", _no_guard)
    from metascience_agent.llm_backend import Backend
    monkeypatch.setattr(Backend, "assert_mcp_live", lambda self, sandbox: None)
    return tmp_path


class TestRunStageCodex:
    def test_end_to_end_fixture_stream(self, codex_stage_env, monkeypatch):
        payload = _payload_from_events(
            _events_from_fixture("codex_exec_stream.jsonl"))
        procs = []

        async def fake_exec(*a, **kw):
            p = _FakeProc(payload)
            # stdin is a pre-filled file (tests/test_prompt_stdin_race.py);
            # read it here, since _run_stage closes it once spawned.
            p.stdin.written = kw["stdin"].read()
            procs.append((a, p))
            return p

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
        inv = A._build_claude_cmd(
            system_prompt="s", allowed_tools=A.STAGE1_TOOLS,
            model="gpt-5.6-sol", backend="codex",
            json_schema={"type": "object"},
        )
        workdir = inv.workdir
        stage = asyncio.run(A._run_stage(inv, "the prompt",
                                         stage_label="sweep"))
        parsed, path = A._extract_json(stage)
        assert path == "json_schema"
        assert parsed["grim_severity"] == "consistent"
        ledger = A._tool_call_ledger(stage["messages"], A.STAGE1_TOOLS)
        assert any(r["tool_short"] == "grim_check" and r["validated"]
                   for r in ledger)
        assert stage["llm_backend"] == "codex"
        assert stage["cost_usd"] == 0.0           # degraded, never fabricated
        assert stage["cost_reported"] is False    # ...and says it is unknown
        assert stage["input_tokens"] == 28848
        assert stage["cache_read_input_tokens"] == 13056
        assert stage["usage_guard"] is None       # codex IS guarded now
        assert stage["max_turns_unsupported"] is None
        assert stage["mcp_discovery"]["ok"] is True
        assert stage["mcp_discovery"]["declared"] is None
        # The prompt went down stdin, and cleanup removed the sandbox.
        assert procs[0][1].stdin.written == b"the prompt"
        assert not workdir.exists()

    def test_heartbeat_snapshots_during_silent_reasoning(
        self, codex_stage_env, monkeypatch
    ):
        """Codex reasons silently between tool calls (MEASURED: a healthy
        stage went 6.5 minutes with no mapped event on the 2026-09-01
        apple_cider run). Every stream event must produce a progress
        snapshot, reasoning must render as "thinking" (current_tool None),
        and codex snapshots must stamp live_tokens False so the display
        drops the permanently-zero token counters."""
        events = _events_from_fixture("codex_exec_stream.jsonl")
        # A reasoning item between the tool round-trip and the final message
        # -- the stretch that used to emit nothing.
        events.insert(5, {"type": "item.completed",
                          "item": {"id": "r1", "type": "reasoning",
                                   "text": "considering the tables"}})

        async def fake_exec(*a, **kw):
            return _FakeProc(_payload_from_events(events))

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
        snapshots = []
        inv = A._build_claude_cmd(
            system_prompt="s", allowed_tools=A.STAGE1_TOOLS,
            model="gpt-5.6-sol", backend="codex",
        )
        asyncio.run(A._run_stage(inv, "p", stage_label="sweep",
                                 on_progress=snapshots.append))
        # More snapshots than assistant events alone: the tool_result and
        # the reasoning passthrough each produced one.
        assert len(snapshots) >= 6
        assert all(s.get("live_tokens") is False for s in snapshots)
        # After the grim_check tool_use the label was the tool; the
        # reasoning event reset it to None ("thinking").
        tools = [s.get("current_tool") for s in snapshots]
        # `_live_tool_name` stores the short form (status line never shows
        # the MCP prefix).
        assert "grim_check" in tools
        assert None in tools[tools.index("grim_check"):]

    def test_claude_snapshots_do_not_carry_the_stamp(
        self, codex_stage_env, monkeypatch
    ):
        events = [
            {"type": "system", "subtype": "init",
             "mcp_servers": [{"name": "forensic_metascience",
                              "status": "connected"}]},
            {"type": "assistant", "message": {
                "id": "m1", "usage": {"input_tokens": 5},
                "content": [{"type": "text", "text": "hi"}]}},
            {"type": "result", "result": "{}", "usage": {},
             "total_cost_usd": 0.01},
        ]

        async def fake_exec(*a, **kw):
            return _FakeProc(_payload_from_events(events))

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
        snapshots = []
        inv = A._build_claude_cmd(
            system_prompt="s", allowed_tools=["Read"], backend="claude",
        )
        asyncio.run(A._run_stage(inv, "p", stage_label="sweep",
                                 on_progress=snapshots.append))
        assert snapshots
        assert all("live_tokens" not in s for s in snapshots)

    def test_turn_failed_reaches_the_payload(self, codex_stage_env, monkeypatch):
        events = [
            {"type": "thread.started", "thread_id": "t1"},
            {"type": "turn.failed",
             "error": {"message": "output does not conform to schema"}},
        ]

        async def fake_exec(*a, **kw):
            return _FakeProc(_payload_from_events(events))

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
        inv = A._build_claude_cmd(
            system_prompt="s", allowed_tools=["Read"],
            model="gpt-5.6-sol", backend="codex",
        )
        stage = asyncio.run(A._run_stage(inv, "p"))
        assert stage["is_error"] is True
        assert stage["schema_errors"] == ["output does not conform to schema"]

    def test_max_turns_stamp_reaches_the_payload(self, codex_stage_env,
                                                 monkeypatch):
        events = [{"type": "thread.started", "thread_id": "t1"},
                  {"type": "turn.completed", "usage": {}}]

        async def fake_exec(*a, **kw):
            return _FakeProc(_payload_from_events(events))

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
        inv = A._build_claude_cmd(
            system_prompt="s", allowed_tools=["Read"],
            model="gpt-5.6-sol", backend="codex", max_turns=1,
        )
        stage = asyncio.run(A._run_stage(inv, "p"))
        assert stage["max_turns_unsupported"] is True
