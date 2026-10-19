"""Grok CLI backend: normalizer, argv, fail-closed MCP, budget refuse.

Fixtures on disk from the 2026-08-18 spike, previously unread by any test.
A normalizer that silently stops rewriting `use_tool` would make the ledger
report zero forensic checks -- our plumbing failure rendered as a clean paper.
"""
from __future__ import annotations

import dataclasses
import asyncio
import json
from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit import agent as A
from forensic_metascience_ai_toolkit.llm_backend import (
    CLAUDE,
    GROK,
    MCPUnavailable,
    BudgetUnsupported,
    check_doctor_payload,
    grok_deny_rules,
    normalize_event,
    off_stage_mcp_names,
    resolve_backend,
)
from forensic_metascience_ai_toolkit.usage_guard import UNSUPPORTED

DATA = Path(__file__).parent / "data"


def _events_from_fixture(name: str) -> list[dict]:
    path = DATA / name
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


class TestResolveBackend:
    def test_default_is_claude(self, monkeypatch):
        monkeypatch.delenv("METASCIENCE_LLM_CLI", raising=False)
        assert resolve_backend(None).name == "claude"

    def test_env_then_explicit(self, monkeypatch):
        monkeypatch.setenv("METASCIENCE_LLM_CLI", "grok")
        assert resolve_backend(None).name == "grok"
        assert resolve_backend("claude").name == "claude"

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="unknown LLM backend"):
            resolve_backend("cursor")


class TestNormalizerKnownPositive:
    def test_ledger_records_the_forensic_call(self):
        events = [normalize_event(e, GROK) for e in _events_from_fixture(
            "grok_use_tool_stream.jsonl")]
        from forensic_metascience_ai_toolkit.agent import STAGE1_TOOLS, _tool_call_ledger
        ledger = _tool_call_ledger(events, STAGE1_TOOLS)
        forensic = [r for r in ledger if r["surface"] == "forensic_mcp"]
        assert len(forensic) >= 1, (
            f"normalizer produced no forensic_mcp rows; surfaces="
            f"{[r['surface'] for r in ledger]} tools={[r['tool'] for r in ledger]}"
        )
        names = {r["tool_short"] for r in forensic}
        assert "grim_check" in names
        grim = next(r for r in forensic if r["tool_short"] == "grim_check")
        assert grim["validated"] is True
        payload = json.loads(grim["result"])
        assert payload.get("severity") == "consistent"

    def test_search_tool_is_harness_not_unvalidated(self):
        events = [normalize_event(e, GROK) for e in _events_from_fixture(
            "grok_use_tool_stream.jsonl")]
        from forensic_metascience_ai_toolkit.agent import STAGE1_TOOLS, _tool_call_ledger
        ledger = _tool_call_ledger(events, STAGE1_TOOLS)
        search = [r for r in ledger if r["tool_short"] == "search_tool"]
        assert search, "fixture contains a search_tool call"
        assert all(r["surface"] == "harness" for r in search)

    def test_read_file_rewrites_to_Read(self):
        events = [normalize_event(e, GROK) for e in _events_from_fixture(
            "grok_use_tool_stream.jsonl")]
        from forensic_metascience_ai_toolkit.agent import STAGE1_TOOLS, _tool_call_ledger
        ledger = _tool_call_ledger(events, STAGE1_TOOLS)
        reads = [r for r in ledger if r["tool_short"] == "Read"]
        assert reads
        assert all(r["surface"] == "builtin_allowed" for r in reads)

    def test_foreign_use_tool_stays_unvalidated(self):
        event = {
            "type": "assistant",
            "message": {"content": [{
                "type": "tool_use",
                "id": "x",
                "name": "use_tool",
                "input": {
                    "tool_name": "github__create_issue",
                    "tool_input": {"title": "nope"},
                },
            }]},
        }
        rewritten = normalize_event(event, GROK)
        block = rewritten["message"]["content"][0]
        assert block["name"] == "use_tool"
        from forensic_metascience_ai_toolkit.agent import STAGE1_TOOLS, _tool_call_ledger
        ledger = _tool_call_ledger([rewritten], STAGE1_TOOLS)
        assert ledger[0]["surface"] == "UNVALIDATED"

    def test_claude_is_identity(self):
        event = {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "mcp__forensic_metascience__grim_check",
             "id": "1", "input": {"mean": 1}}
        ]}}
        from forensic_metascience_ai_toolkit.llm_backend import CLAUDE
        assert normalize_event(event, CLAUDE) is event


class TestDoctorFixtures:
    def test_healthy_passes(self):
        data = json.loads((DATA / "grok_mcp_doctor_healthy.json").read_text())
        check_doctor_payload(data)  # does not raise

    def test_untrusted_raises(self):
        data = json.loads((DATA / "grok_mcp_doctor_untrusted.json").read_text())
        with pytest.raises(MCPUnavailable, match="not healthy|untrusted"):
            check_doctor_payload(data)

    def test_foreign_server_raises(self):
        data = json.loads((DATA / "grok_mcp_doctor_healthy.json").read_text())
        data = json.loads(json.dumps(data))
        data["servers"].append({"name": "github", "healthy": True, "checks": []})
        with pytest.raises(MCPUnavailable, match="other server"):
            check_doctor_payload(data)

    def test_zero_tools_raises(self):
        data = {
            "servers": [{
                "name": "forensic_metascience",
                "healthy": True,
                "checks": [{"label": "0 tools discovered", "passed": True}],
            }],
        }
        with pytest.raises(MCPUnavailable, match="0 tools"):
            check_doctor_payload(data)


class TestDenyComplement:
    def test_derived_from_registry_not_a_hand_list(self):
        from forensic_metascience_ai_toolkit.agent import STAGE1_TOOLS, STAGE2_TOOLS
        from forensic_metascience_ai_toolkit.registry import (
            ADJUDICATOR, SPECS, TOOL_AGENT, stage_tools)
        s1 = set(off_stage_mcp_names(STAGE1_TOOLS))
        # By the role CONSTANTS, not string literals -- the literal "stage1"
        # is exactly the hand-list drift this test exists to forbid, and it
        # bit this very test at the role rename.
        expected = {s.name for s in SPECS} - set(stage_tools(TOOL_AGENT))
        assert s1 == expected
        s2 = set(off_stage_mcp_names(STAGE2_TOOLS))
        expected2 = {s.name for s in SPECS} - set(stage_tools(ADJUDICATOR))
        assert s2 == expected2
        rules = grok_deny_rules(STAGE1_TOOLS)
        assert all(r.startswith("MCPTool(forensic_metascience__") for r in rules)
        assert len(rules) == len(s1)


class TestBudgetRefuse:
    def test_analyze_paper_raises_before_subprocess(self, monkeypatch):
        launched = []

        async def fake_exec(*a, **kw):
            launched.append(a)
            raise AssertionError("must not spawn")

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
        with pytest.raises(BudgetUnsupported, match="no spend cap"):
            asyncio.run(A.analyze_paper(
                "/nonexistent", backend="grok", budget_usd=5,
            ))
        assert launched == []

    def test_build_invocation_raises(self):
        from forensic_metascience_ai_toolkit.agent import STAGE1_TOOLS, _build_claude_cmd
        with pytest.raises(BudgetUnsupported):
            _build_claude_cmd(
                system_prompt="s", allowed_tools=STAGE1_TOOLS,
                backend="grok", budget_usd=5,
            )


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
        # A double that cannot report `returncode` is not a stand-in for an
        # asyncio subprocess, which always can. `_run_stage`'s cleanup reads
        # it to decide whether the child is still alive.
        self.returncode = None

    async def wait(self):
        self.returncode = 0
        return 0

    def kill(self):
        self.killed = True


def _payload_from_events(events: list[dict]) -> bytes:
    return b"".join((json.dumps(e) + "\n").encode() for e in events)


@pytest.fixture
def grok_stage_env(tmp_path, monkeypatch):
    monkeypatch.setenv("METASCIENCE_GROK_SANDBOX_ROOT", str(tmp_path / "sb"))
    monkeypatch.setenv("METASCIENCE_GROK_SKIP_FOLDER_TRUST", "1")
    monkeypatch.setenv("METASCIENCE_SKIP_PREFLIGHT", "1")
    monkeypatch.setattr(A, "_assert_ready", lambda *a, **k: None)

    async def _no_guard(*a, **k):
        return None

    monkeypatch.setattr(A, "usage_guard", _no_guard)
    from forensic_metascience_ai_toolkit.llm_backend import Backend
    monkeypatch.setattr(Backend, "assert_mcp_live", lambda self, sandbox: None)
    return tmp_path


class TestRunStageGrok:
    def test_normalizes_and_extracts_structured_output(self, grok_stage_env, monkeypatch):
        events = _events_from_fixture("grok_use_tool_stream.jsonl")
        payload = _payload_from_events(events)
        procs = []

        async def fake_exec(*a, **kw):
            p = _FakeProc(payload)
            procs.append(p)
            return p

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
        inv = A._build_claude_cmd(
            system_prompt="s", allowed_tools=A.STAGE1_TOOLS,
            model="grok-4.6", backend="grok",
        )
        stage = asyncio.run(A._run_stage(inv, "the prompt", stage_label="sweep"))
        parsed, path = A._extract_json(stage)
        assert path == "json_schema"
        assert parsed["grim_severity"] == "consistent"
        ledger = A._tool_call_ledger(stage["messages"], A.STAGE1_TOOLS)
        assert any(r["tool_short"] == "grim_check" and r["validated"] for r in ledger)
        # prompt-file: stdin is closed without the prompt; cleanup removes the dir
        assert procs[0].stdin.written == b""
        assert inv.workdir is None or not inv.workdir.exists()

    def test_init_without_our_server_aborts_before_assistant(
        self, grok_stage_env, monkeypatch
    ):
        events = [
            {"type": "system", "subtype": "init", "mcp_servers": []},
            {"type": "assistant", "message": {
                "id": "m", "content": [{"type": "text", "text": "I ran with no tools"}],
                "usage": {},
            }},
            {"type": "result", "result": "{}", "is_error": False, "usage": {}},
        ]
        seen_argv = []

        async def fake_exec(*a, **kw):
            seen_argv.append(a)
            return _FakeProc(_payload_from_events(events))

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
        inv = A._build_claude_cmd(
            system_prompt="s", allowed_tools=A.STAGE1_TOOLS,
            model="grok-4.6", backend="grok",
        )
        with pytest.raises(MCPUnavailable, match="no forensic_metascience"):
            asyncio.run(A._run_stage(inv, "p", stage_label="sweep"))

    def test_foreign_mcp_on_init_aborts(self, grok_stage_env, monkeypatch):
        events = [
            {"type": "system", "subtype": "init",
             "mcp_servers": [
                 {"name": "forensic_metascience", "status": "connected"},
                 {"name": "github", "status": "connected"},
             ]},
        ]

        async def fake_exec(*a, **kw):
            return _FakeProc(_payload_from_events(events))

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
        inv = A._build_claude_cmd(
            system_prompt="s", allowed_tools=A.STAGE1_TOOLS,
            model="grok-4.6", backend="grok",
        )
        with pytest.raises(MCPUnavailable, match="foreign"):
            asyncio.run(A._run_stage(inv, "p"))

    def test_cleanup_on_success(self, grok_stage_env, monkeypatch):
        events = [
            {"type": "system", "subtype": "init",
             "mcp_servers": [{"name": "forensic_metascience", "status": "connected"}]},
            {"type": "result", "result": "{}", "structured_output": {"ok": True},
             "is_error": False, "usage": {}, "total_cost_usd": 0},
        ]

        async def fake_exec(*a, **kw):
            return _FakeProc(_payload_from_events(events))

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
        inv = A._build_claude_cmd(
            system_prompt="s", allowed_tools=["Read"],
            model="grok-4.6", backend="grok",
        )
        workdir = inv.workdir
        asyncio.run(A._run_stage(inv, "p", stage_label="editorial"))
        assert workdir is not None and not workdir.exists()

    def test_zero_validated_stage1_raises(self):
        stage = {"messages": [
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Read", "id": "1", "input": {}},
            ]}},
        ]}
        with pytest.raises(A.ForensicToolsNeverRan) as ei:
            A._assert_forensic_tools_ran(stage, A.STAGE1_TOOLS, "sweep")
        assert ei.value.stage is stage, (
            "the refuse must carry the stage so a diagnostic can be written; "
            "a traceback alone left a 19s grok call with nothing on disk"
        )

    def test_cli_only_mcp_calls_do_not_satisfy_the_gate(self):
        """The observed Grok leak: sweep calls the two CLI-only wrappers
        and dumps empty findings. Those calls are validated arithmetic
        (off-list) but they are not the numeric sweep."""
        stage = {"messages": [
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use",
                 "name": "mcp__forensic_metascience__analyze_paper_images",
                 "id": "1", "input": {}},
                {"type": "tool_use",
                 "name": "mcp__forensic_metascience__detect_tortured_phrases",
                 "id": "2", "input": {}},
            ]}},
        ]}
        with pytest.raises(A.ForensicToolsNeverRan):
            A._assert_forensic_tools_ran(stage, A.STAGE1_TOOLS, "sweep")

    def test_one_on_list_call_satisfies_the_gate(self):
        stage = {"messages": [
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use",
                 "name": "mcp__forensic_metascience__grim_check",
                 "id": "1", "input": {}},
            ]}},
        ]}
        A._assert_forensic_tools_ran(stage, A.STAGE1_TOOLS, "sweep")

    def test_stage2_is_exempt(self):
        stage = {"messages": []}
        A._assert_forensic_tools_ran(stage, A.STAGE2_TOOLS, "editorial")

    def test_an_errored_stage_bypasses_the_gate(self):
        """An errored stage's ledger is empty BECAUSE the call failed; the
        error path carries the true diagnosis. Measured: an API-400 sweep
        was relabeled 'plumbing failure' by this gate, which crashed the
        both-stages-failed -> partial-report contract
        (test_stage_failure_paths sat red on exactly this)."""
        stage = {"messages": [], "is_error": True,
                 "error_subtype": "api_error"}
        A._assert_forensic_tools_ran(stage, A.STAGE1_TOOLS, "sweep")


_EMPTY_DUMP_EVENTS = [
    {"type": "system", "subtype": "init",
     "mcp_servers": [{"name": "forensic_metascience", "status": "connected"}],
     "tools": ["read_file", "search_tool", "use_tool"]},
    {"type": "assistant", "message": {
        "id": "m",
        "content": [{"type": "text", "text": (
            '{"schema_version":"1.0","paper_id":"x","findings":[],'
            '"coverage":{"stats_found":0,"tools_run":[]},'
            '"anatomy":{"studies":[],"variables":[],"tests":[]}}'
        )}],
        "usage": {"input_tokens": 100, "output_tokens": 173},
    }},
    {"type": "result",
     "result": (
         '{"schema_version":"1.0","paper_id":"x","findings":[],'
         '"coverage":{"stats_found":0,"tools_run":[]},'
         '"anatomy":{"studies":[],"variables":[],"tests":[]}}'
     ),
     "structured_output": {
         "schema_version": "1.0", "paper_id": "x", "findings": [],
         "coverage": {"stats_found": 0, "tools_run": []},
         "anatomy": {"studies": [], "variables": [], "tests": []},
     },
     "is_error": False, "usage": {}, "total_cost_usd": 0.01,
     "stop_reason": "end_turn", "num_turns": 1},
]

_ON_LIST_EVENTS = [
    {"type": "system", "subtype": "init",
     "mcp_servers": [{"name": "forensic_metascience", "status": "connected"}]},
    {"type": "assistant", "message": {"id": "m", "content": [
        {"type": "tool_use", "id": "1",
         "name": "mcp__forensic_metascience__grim_check", "input": {}},
    ]}},
    {"type": "result", "result": "{}", "structured_output": {"ok": True},
     "is_error": False, "usage": {}, "total_cost_usd": 0},
]


class TestEmptyDumpRetry:
    def test_timeout_and_errors_are_not_the_empty_dump(self):
        assert not A._retryable_empty_forensic_dump(
            {"is_error": True, "error_subtype": "error_timeout"}, GROK)
        assert not A._retryable_empty_forensic_dump(
            {"is_error": True, "error_subtype": None}, GROK)
        assert not A._retryable_empty_forensic_dump(
            {"is_error": False}, CLAUDE)
        assert A._retryable_empty_forensic_dump(
            {"is_error": False, "error_subtype": None}, GROK)

    def test_grok_retries_once_then_keeps_a_tool_using_sweep(
        self, grok_stage_env, monkeypatch,
    ):
        A.reset_spend()
        payloads = [
            _payload_from_events(_EMPTY_DUMP_EVENTS),
            _payload_from_events(_ON_LIST_EVENTS),
        ]
        seen = []

        async def fake_exec(*a, **kw):
            seen.append(a)
            return _FakeProc(payloads.pop(0))

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

        def build_cmd():
            return A._build_claude_cmd(
                system_prompt="s", allowed_tools=A.STAGE1_TOOLS,
                model="grok-4.6", backend="grok",
            )

        stage = asyncio.run(A._run_stage_requiring_forensic_tools(
            build_cmd=build_cmd, prompt="p", allowed_tools=A.STAGE1_TOOLS,
            stage_label="sweep", backend=GROK, spend_label="stage1_sweep",
        ))
        assert len(seen) == 2
        assert stage.get("retried_after_empty_dump") == 1
        labels = [row["stage"] for row in A.spend_so_far()["stages"]]
        assert labels == ["stage1_sweep", "stage1_sweep_retry"]

    def test_grok_raises_after_retry_exhausted(self, grok_stage_env, monkeypatch):
        A.reset_spend()
        seen = []

        async def fake_exec(*a, **kw):
            seen.append(a)
            return _FakeProc(_payload_from_events(_EMPTY_DUMP_EVENTS))

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

        def build_cmd():
            return A._build_claude_cmd(
                system_prompt="s", allowed_tools=A.STAGE1_TOOLS,
                model="grok-4.6", backend="grok",
            )

        with pytest.raises(A.ForensicToolsNeverRan) as ei:
            asyncio.run(A._run_stage_requiring_forensic_tools(
                build_cmd=build_cmd, prompt="p",
                allowed_tools=A.STAGE1_TOOLS,
                stage_label="sweep", backend=GROK,
            ))
        assert len(seen) == 2
        assert len(ei.value.prior_stages) == 1
        assert ei.value.stage is not None
        assert ei.value.stage.get("num_turns") == 1
        assert ei.value.stage.get("stop_reason") == "end_turn"
        assert ei.value.stage.get("structured_output", {}).get("findings") == []

    def test_mcp_unavailable_is_not_retried(self, grok_stage_env, monkeypatch):
        seen = []
        events = [{"type": "system", "subtype": "init", "mcp_servers": []}]

        async def fake_exec(*a, **kw):
            seen.append(a)
            return _FakeProc(_payload_from_events(events))

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

        def build_cmd():
            return A._build_claude_cmd(
                system_prompt="s", allowed_tools=A.STAGE1_TOOLS,
                model="grok-4.6", backend="grok",
            )

        with pytest.raises(MCPUnavailable):
            asyncio.run(A._run_stage_requiring_forensic_tools(
                build_cmd=build_cmd, prompt="p",
                allowed_tools=A.STAGE1_TOOLS,
                stage_label="sweep", backend=GROK,
            ))
        assert len(seen) == 1

    def test_claude_does_not_retry(self, grok_stage_env, monkeypatch):
        seen = []

        async def fake_exec(*a, **kw):
            seen.append(a)
            return _FakeProc(_payload_from_events(_EMPTY_DUMP_EVENTS))

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

        def build_cmd():
            return A._build_claude_cmd(
                system_prompt="s", allowed_tools=A.STAGE1_TOOLS,
                model="sonnet", backend="claude",
            )

        with pytest.raises(A.ForensicToolsNeverRan):
            asyncio.run(A._run_stage_requiring_forensic_tools(
                build_cmd=build_cmd, prompt="p",
                allowed_tools=A.STAGE1_TOOLS,
                stage_label="sweep", backend=CLAUDE,
            ))
        assert len(seen) == 1

class TestUsageUnsupported:
    def test_grok_never_spawns_a_probe(self, monkeypatch):
        spawned = []

        async def fake_exec(*args, **kwargs):
            spawned.append(args)
            raise AssertionError("grok must not probe /usage")

        from forensic_metascience_ai_toolkit import usage_guard
        monkeypatch.setattr(usage_guard.asyncio, "create_subprocess_exec", fake_exec)
        result = asyncio.run(usage_guard.probe_usage(backend=GROK))
        assert result is UNSUPPORTED
        assert spawned == []


class TestExtractJsonPrefersStructuredOutput:
    def test_structured_output_wins(self):
        stage = {
            "structured_output": {"a": 1},
            "result": "not json",
            "text": "```json\n{\"a\": 2}\n```",
        }
        parsed, path = A._extract_json(stage)
        assert parsed == {"a": 1}
        assert path == "json_schema"


class TestSandboxIsNotRemovedUnderALiveChild:
    """MEASURED 2026-08-22, `10.1016--j.ynstr.2021.100304` on grok-4.6.

    The batch parent was killed while a stage was mid-flight. `_run_stage`'s
    `finally` ran `inv.cleanup()` -- `shutil.rmtree(run_dir)` -- and nothing
    killed the child, so the grok CLI was reparented to init and kept
    streaming for another 15 minutes against a `(deleted)` cwd, holding its
    own MCP grandchild. The paper's two finished analyst stages were lost with
    no `forensic_review*/`, no cost row, and no failure row: no record it had
    been attempted at all.
    """

    def _cancelling_stage(self, grok_stage_env, monkeypatch):
        order: list[str] = []
        procs: list = []

        class _HangingProc(_FakeProc):
            def __init__(self):
                super().__init__(b"")

            async def wait(self):
                await asyncio.sleep(3600)

            def kill(self):
                order.append("kill")
                super().kill()
                self.returncode = -9

        async def fake_exec(*a, **kw):
            p = _HangingProc()
            procs.append(p)
            return p

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
        monkeypatch.setattr(
            A, "_kill_subprocess_group", lambda proc: proc.kill())
        inv = A._build_claude_cmd(
            system_prompt="s", allowed_tools=A.STAGE1_TOOLS,
            model="grok-4.6", backend="grok",
        )
        real_cleanup = inv.cleanup

        def _traced_cleanup():
            order.append("cleanup")
            real_cleanup()

        inv = dataclasses.replace(inv, cleanup=_traced_cleanup)
        return inv, order, procs

    def test_cancelling_a_stage_kills_the_child_before_rmtree(
            self, grok_stage_env, monkeypatch):
        inv, order, procs = self._cancelling_stage(grok_stage_env, monkeypatch)
        sandbox = inv.workdir
        assert sandbox is not None and sandbox.exists()

        async def _run_then_cancel():
            task = asyncio.ensure_future(
                A._run_stage(inv, "p", stage_label="sweep"))
            # Until the child exists: the pre-spawn gates yield to the loop
            # (the MCP probe runs in a worker thread).
            for _ in range(500):
                if procs:
                    break
                await asyncio.sleep(0.01)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        asyncio.run(_run_then_cancel())

        assert procs and procs[0].killed, "the child was left running"
        # ORDER IS THE POINT, not just that both happened: rmtree under a live
        # child is what produced the `(deleted)` cwd.
        assert order == ["kill", "cleanup"], order
        assert not sandbox.exists()

    def test_a_stage_that_finished_normally_is_not_killed(
            self, grok_stage_env, monkeypatch):
        events = _events_from_fixture("grok_use_tool_stream.jsonl")
        payload = _payload_from_events(events)
        procs = []

        async def fake_exec(*a, **kw):
            p = _FakeProc(payload)
            procs.append(p)
            return p

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
        inv = A._build_claude_cmd(
            system_prompt="s", allowed_tools=A.STAGE1_TOOLS,
            model="grok-4.6", backend="grok",
        )
        asyncio.run(A._run_stage(inv, "p", stage_label="sweep"))
        assert procs and not procs[0].killed


class TestTheSchemaRejectionReachesTheStagePayload:
    """MEASURED 2026-08-22 by pyflakes, after the field had already shipped:

        agent.py:1589:25: local variable 'schema_errors' is assigned to but
                          never used

    `schema_errors` is declared in `_run_stage` and ASSIGNED inside the nested
    `_read_stdout`, which was missing it from its `nonlocal` list -- so Python
    bound a fresh local, the outer list stayed `[]`, and `_stage_payload`
    always emitted an empty one. The adjudicator retry that was supposed to
    quote the rejection back at the model silently fell through to its generic
    paragraph on every run.

    THE TEST HAS TO GO THROUGH `_run_stage`. The unit test on the formatter
    (`_schema_gate_correction`) passed the whole time, because it was handed a
    hand-built dict -- it proved the formatter worked and said nothing about
    whether anything ever filled the field.
    """

    def _stage(self, monkeypatch, events):
        async def fake_exec(*a, **kw):
            return _FakeProc(_payload_from_events(events))

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
        inv = A._build_claude_cmd(
            system_prompt="s", allowed_tools=A.STAGE1_TOOLS,
            model="grok-4.6", backend="grok",
        )
        return asyncio.run(A._run_stage(inv, "p", stage_label="adjudicator"))

    def test_the_cli_errors_list_survives_into_the_payload(
            self, grok_stage_env, monkeypatch):
        """The real rejection from `10.15585--mmwr.mm6923e2`."""
        rejection = ('output does not match the required schema: "placeholder '
                     'text that is long enough to meet the two hundred '
                     'character minimum requirement for the paper summary '
                     'field as specified in the schema." is shorter than 200 '
                     'characters')
        stage = self._stage(monkeypatch, [
            {"type": "result", "subtype": "error_max_structured_output_retries",
             "is_error": True, "result": "", "usage": {},
             "errors": [rejection]},
        ])
        assert stage["schema_errors"] == [rejection]

    def test_the_correction_actually_quotes_it_end_to_end(
            self, grok_stage_env, monkeypatch):
        """The whole point of the field: the retry says what was rejected."""
        from forensic_metascience_ai_toolkit.parallel import _schema_gate_correction
        stage = self._stage(monkeypatch, [
            {"type": "result", "subtype": "error_max_structured_output_retries",
             "is_error": True, "result": "", "usage": {},
             "errors": ["is shorter than 200 characters"]},
        ])
        assert "is shorter than 200 characters" in _schema_gate_correction(stage)

    def test_a_clean_run_carries_an_empty_list_not_a_missing_key(
            self, grok_stage_env, monkeypatch):
        """[] means the CLI reported no per-error detail. It is not the same
        fact as the stage not having errored -- `is_error` says that."""
        stage = self._stage(monkeypatch, [
            {"type": "result", "result": "{}", "is_error": False, "usage": {}},
        ])
        assert stage["schema_errors"] == []
        assert stage["is_error"] is False

    def test_at_most_five_are_kept(self, grok_stage_env, monkeypatch):
        stage = self._stage(monkeypatch, [
            {"type": "result", "is_error": True, "result": "", "usage": {},
             "errors": [f"e{i}" for i in range(20)]},
        ])
        assert stage["schema_errors"] == ["e0", "e1", "e2", "e3", "e4"]


class TestFolderTrustIsDisabledForTheSandbox:
    """MEASURED 2026-09-02, grok 1.0.13: all six eval runs died before spend
    with `MCPUnavailable: folder untrusted: repo-local (project-scoped) server
    not started for an untrusted folder`, although the sandbox ROOT was in
    `~/.grok/trusted_folders.toml` exactly as `_ensure_sandbox_root_trusted`
    writes it. Grok's docs: a trust grant covers subdirectories "of the same
    repository", and the sandbox root is not a git repository. With
    `GROK_FOLDER_TRUST=0` in the subprocess env, `grok mcp doctor` in the same
    run dir reported handshake OK and the stage's 17 tools discovered. The
    v1.3.0 eval runs (grok 1.0.5) needed none of this: trust cascaded then.
    """

    def test_the_run_invocation_carries_the_switch(self, tmp_path, monkeypatch):
        monkeypatch.setenv("METASCIENCE_GROK_SANDBOX_ROOT", str(tmp_path / "sb"))
        monkeypatch.setenv("METASCIENCE_GROK_SKIP_FOLDER_TRUST", "1")
        from forensic_metascience_ai_toolkit.agent import STAGE1_TOOLS, _build_claude_cmd
        inv = _build_claude_cmd(
            system_prompt="s", allowed_tools=STAGE1_TOOLS, backend="grok")
        try:
            assert inv.env_overlay["GROK_FOLDER_TRUST"] == "0"
        finally:
            inv.cleanup()

    def test_the_doctor_probe_is_gated_the_same_way_as_the_run(self):
        """A probe that is gated differently from the run it vouches for
        proves nothing about that run."""
        import inspect
        from forensic_metascience_ai_toolkit import llm_backend as B
        src = inspect.getsource(B._probe_mcp_doctor)
        assert "GROK_FOLDER_TRUST_ENV" in src
        assert B.GROK_FOLDER_TRUST_ENV == {"GROK_FOLDER_TRUST": "0"}

    def test_the_root_trust_entry_is_still_written(self, tmp_path, monkeypatch):
        """Kept for grok versions where the cascade still works; the env
        switch is the belt, this is the braces."""
        from forensic_metascience_ai_toolkit import llm_backend as B
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("METASCIENCE_GROK_SKIP_FOLDER_TRUST", raising=False)
        root = tmp_path / "sb"
        root.mkdir()
        B._ensure_sandbox_root_trusted(root)
        store = (tmp_path / ".grok" / "trusted_folders.toml").read_text()
        assert f'folders."{root.resolve()}"' in store
