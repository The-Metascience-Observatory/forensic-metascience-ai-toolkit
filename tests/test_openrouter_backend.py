"""Phase 3c: the OpenRouter backend is our own agent loop.

`openrouter_loop` is launched like a CLI and must speak Claude's stream-json,
so `_run_stage` reads it with no OpenRouter branch. These tests run the real
loop as a subprocess against a scripted chat-completions server and a real
(tiny) MCP server, and check what the runner gets back: the init event's
server list, tool_use/tool_result pairs, structured output, summed cost, and
the refusals (an off-list tool, a Read outside the paper directory, a schema
the model never satisfies, a missing API key).
"""

import asyncio
import json
import subprocess
import sys
import textwrap
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from metascience_agent import agent
from metascience_agent.llm_backend import (
    OPENROUTER,
    BudgetUnsupported,
    build_invocation,
    mcp_discovery_from_init,
    resolve_backend,
)

LOOP = "metascience_agent.openrouter_loop"
SCHEMA = {"type": "object", "properties": {"verdict": {"type": "string"}},
          "required": ["verdict"], "additionalProperties": False}

FAKE_MCP = textwrap.dedent('''
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("fake")

    @mcp.tool()
    def add(a: int, b: int) -> str:
        """Add two integers."""
        return f'{{"sum": {a + b}, "severity": "consistent"}}'

    @mcp.tool()
    def secret() -> str:
        """Must never be called: it is not on the stage's list."""
        raise SystemExit("secret was called")

    mcp.run()
''')


def _tool_call(cid, name, args):
    return {"id": cid, "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}


def _reply(content=None, calls=None, cost=0.01):
    msg = {"role": "assistant", "content": content}
    if calls:
        msg["tool_calls"] = calls
    return {"choices": [{"message": msg}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 10, "cost": cost}}


class _Scripted:
    """A chat-completions server that answers from a list and keeps every
    request body, so a test can see what the model was sent."""

    def __init__(self, replies):
        self.replies, self.bodies = list(replies), []
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers["Content-Length"])
                outer.bodies.append(json.loads(self.rfile.read(n)))
                body = json.dumps(outer.replies.pop(0)).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"

    def close(self):
        self.httpd.shutdown()


@pytest.fixture
def fake_mcp(tmp_path):
    script = tmp_path / "fake_mcp.py"
    script.write_text(FAKE_MCP)
    return json.dumps({"mcpServers": {"forensic_metascience": {"command": sys.executable,
                                               "args": [str(script)]}}})


def _run_loop(server, mcp_config, tmp_path, *, allowed, schema=SCHEMA, extra=(),
              env_key="test-key", prompt="check it"):
    import os
    sysprompt = tmp_path / "sys.md"
    sysprompt.write_text("You are a test analyst.")
    argv = [sys.executable, "-m", LOOP, "--model", "test/model", "--effort", "xhigh",
            "--mcp-config", mcp_config, "--allowedTools", ",".join(allowed),
            "--system-prompt-file", str(sysprompt), *extra]
    if schema is not None:
        sp = tmp_path / "schema.json"
        sp.write_text(json.dumps(schema))
        argv += ["--json-schema-file", str(sp)]
    env = {**os.environ, "OPENROUTER_BASE_URL": server.url if server else "http://127.0.0.1:9"}
    env.pop("OPENROUTER_API_KEY", None)
    if env_key:
        env["OPENROUTER_API_KEY"] = env_key
    proc = subprocess.run(argv, input=prompt, capture_output=True, text=True,
                          env=env, timeout=120)
    events = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    return proc, events


def _tool_results(events):
    return [b for e in events if e["type"] == "user"
            for b in e["message"]["content"] if b["type"] == "tool_result"]


class TestTheLoop:
    def test_a_tool_call_then_structured_output(self, tmp_path, fake_mcp):
        server = _Scripted([
            _reply("Let me add.", [_tool_call("c1", "mcp__forensic_metascience__add", {"a": 2, "b": 3})]),
            _reply(None, [_tool_call("c2", "StructuredOutput", {"verdict": "fine"})], cost=0.02),
        ])
        try:
            proc, events = _run_loop(server, fake_mcp, tmp_path, allowed=["mcp__forensic_metascience__add"])
        finally:
            server.close()
        assert proc.returncode == 0, proc.stderr
        init = events[0]
        assert init["type"] == "system" and init["subtype"] == "init"
        assert init["mcp_servers"] == [{"name": "forensic_metascience", "status": "connected"}]
        assert init["tools"] == ["mcp__forensic_metascience__add", "StructuredOutput"]
        uses = [b for e in events if e["type"] == "assistant"
                for b in e["message"]["content"] if b["type"] == "tool_use"]
        assert uses[0] == {"type": "tool_use", "id": "c1", "name": "mcp__forensic_metascience__add",
                           "input": {"a": 2, "b": 3}}
        assert json.loads(_tool_results(events)[0]["content"])["sum"] == 5
        result = events[-1]
        assert result["type"] == "result" and result["is_error"] is False
        assert result["structured_output"] == {"verdict": "fine"}
        assert result["total_cost_usd"] == pytest.approx(0.03)
        assert result["num_turns"] == 2
        # What the model was sent: only the allowed tool plus the output tool,
        # our effort mapped onto OpenRouter's ladder, cost reporting on.
        body = server.bodies[0]
        assert [t["function"]["name"] for t in body["tools"]] == ["mcp__forensic_metascience__add", "StructuredOutput"]
        assert body["reasoning"] == {"effort": "high"}
        assert body["usage"] == {"include": True}
        assert body["messages"][0] == {"role": "system", "content": "You are a test analyst."}
        assert body["messages"][1] == {"role": "user", "content": "check it"}

    def test_a_tool_off_the_stage_list_is_refused_not_called(self, tmp_path, fake_mcp):
        server = _Scripted([
            _reply(None, [_tool_call("c1", "mcp__forensic_metascience__secret", {})]),
            _reply(None, [_tool_call("c2", "StructuredOutput", {"verdict": "ok"})]),
        ])
        try:
            proc, events = _run_loop(server, fake_mcp, tmp_path, allowed=["mcp__forensic_metascience__add"])
        finally:
            server.close()
        assert proc.returncode == 0, proc.stderr
        refused = _tool_results(events)[0]
        assert refused["is_error"] is True and "not available" in refused["content"]
        assert "mcp__forensic_metascience__secret" not in events[0]["tools"]

    def test_invalid_structured_output_is_retried_then_refused_by_name(self, tmp_path, fake_mcp):
        bad = _reply(None, [_tool_call("x", "StructuredOutput", {"wrong": 1})])
        server = _Scripted([bad, bad, bad, bad])
        try:
            proc, events = _run_loop(server, fake_mcp, tmp_path, allowed=[])
        finally:
            server.close()
        assert proc.returncode == 1
        result = events[-1]
        assert result["is_error"] is True
        assert result["subtype"] == "error_max_structured_output_retries"
        assert "Structured output rejected" in _tool_results(events)[0]["content"]

    def test_read_is_confined_to_the_paper_directory(self, tmp_path, fake_mcp):
        paper = tmp_path / "paper"
        paper.mkdir()
        (paper / "body.md").write_text("line one\nline two\n")
        server = _Scripted([
            _reply(None, [_tool_call("r1", "Read", {"file_path": "body.md"}),
                          _tool_call("r2", "Read", {"file_path": "../fake_mcp.py"})]),
            _reply(None, [_tool_call("s", "StructuredOutput", {"verdict": "ok"})]),
        ])
        try:
            proc, events = _run_loop(server, fake_mcp, tmp_path, allowed=["Read"],
                                     extra=["--paper-dir", str(paper)])
        finally:
            server.close()
        assert proc.returncode == 0, proc.stderr
        inside, outside = _tool_results(events)[:2]
        assert inside["content"] == "1\tline one\n2\tline two"
        assert outside["is_error"] is False and "outside the paper directory" in outside["content"]

    def test_no_api_key_refuses_out_loud_in_the_stream(self, tmp_path, fake_mcp):
        proc, events = _run_loop(None, fake_mcp, tmp_path, allowed=[], env_key=None)
        assert proc.returncode == 1
        assert events[-1]["is_error"] is True
        assert "OPENROUTER_API_KEY" in events[-1]["result"]

    def test_the_host_runner_reads_it_unchanged(self, tmp_path, fake_mcp, monkeypatch):
        """End to end through `agent._run_stage`: the result, structured output
        and cost arrive exactly as a Claude stage's would."""
        server = _Scripted([
            _reply("Adding.", [_tool_call("c1", "mcp__forensic_metascience__add", {"a": 1, "b": 1})]),
            _reply(None, [_tool_call("c2", "StructuredOutput", {"verdict": "done"})], cost=0.5),
        ])
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        monkeypatch.setenv("OPENROUTER_BASE_URL", server.url)
        monkeypatch.setenv("METASCIENCE_SKIP_PREFLIGHT", "1")
        monkeypatch.setenv("METASCIENCE_USAGE_GUARD", "0")
        inv = build_invocation(OPENROUTER, system_prompt="sys", allowed_tools=["mcp__forensic_metascience__add"],
                               model="test/model", effort="high", json_schema=SCHEMA,
                               mcp_config_json=fake_mcp, python_executable=sys.executable)
        try:
            stage = asyncio.run(agent._run_stage(inv, "go", timeout=120))
        finally:
            server.close()
            inv.cleanup()
        assert stage["is_error"] is False, stage
        assert stage.get("structured_output") == {"verdict": "done"}
        assert stage["cost_usd"] == pytest.approx(0.51)   # 0.01 + 0.5, summed per response


class TestTheBackend:
    def test_it_is_a_named_backend(self):
        assert resolve_backend("openrouter") is OPENROUTER
        assert OPENROUTER.supports_budget is False
        assert OPENROUTER.supports_usage_probe is False

    def test_invocation_puts_prompts_in_files_and_cleans_up(self, tmp_path):
        big = "x" * 200_000                      # over MAX_ARG_STRLEN on argv
        inv = build_invocation(OPENROUTER, system_prompt=big, allowed_tools=["mcp__a__b"],
                               model="m/x", effort="medium", json_schema=SCHEMA,
                               mcp_config_json='{"mcpServers": {"forensic_metascience": {}}}',
                               paper_dir=tmp_path, internet=True, max_turns=7,
                               python_executable="/py")
        argv = inv.argv
        assert argv[:3] == ["/py", "-m", LOOP]
        assert all(len(a) < 100_000 for a in argv)
        sp = Path(argv[argv.index("--system-prompt-file") + 1])
        assert sp.read_text() == big
        assert json.loads(Path(argv[argv.index("--json-schema-file") + 1]).read_text()) == SCHEMA
        assert argv[argv.index("--allowedTools") + 1] == "mcp__a__b,Read"
        assert "--internet" in argv and argv[argv.index("--max-turns") + 1] == "7"
        assert inv.prompt_delivery == "stdin" and inv.forensic_mcp is True
        inv.cleanup()
        assert not sp.exists()

    def test_a_budget_is_refused(self):
        with pytest.raises(BudgetUnsupported):
            build_invocation(OPENROUTER, system_prompt="s", allowed_tools=[], model="m",
                             effort="high", budget_usd=1.0)

    def test_discovery_status_is_live(self):
        ok = mcp_discovery_from_init(
            {"mcp_servers": [{"name": "forensic_metascience", "status": "connected"}]}, OPENROUTER)
        assert ok["ok"] is True and ok["status_is_live"] is True
        failed = mcp_discovery_from_init(
            {"mcp_servers": [{"name": "forensic_metascience", "status": "failed: boom"}]}, OPENROUTER)
        assert failed["ok"] is False

    def test_preflight_names_the_missing_key(self, monkeypatch):
        from metascience_agent import preflight
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        rows = preflight.fatal_checks(refresh=True, backend="openrouter")
        name, ok, detail = rows[0]
        assert name == "OpenRouter API key" and ok is False and "OPENROUTER_API_KEY" in detail
        monkeypatch.setenv("OPENROUTER_API_KEY", "k")
        assert preflight.fatal_checks(refresh=True, backend="openrouter")[0][1] is True
