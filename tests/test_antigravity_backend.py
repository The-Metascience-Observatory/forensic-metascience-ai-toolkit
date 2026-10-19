"""Google Antigravity CLI (`agy`) backend: argv, per-run HOME, stream normalizer.

The fixture `tests/data/agy_stream.jsonl` is a REAL captured
`agy --output-format stream-json` stream (agy 1.4.2, gemini-3.8-flash-low,
2026-10-18; local paths scrubbed, the 34 KB schema echo dropped, `init.tools`
shortened): two `extract_pdf` calls through `call_mcp_tool` (the first with a
wrong argument name, which the tool refused), a `finish` call the schema
validator REJECTED (`schema_version` must be '2.0'), then an accepted one and
a `result` carrying `structured_output`.

What these tests pin, each measured live before it was written:

* the prompt never rides argv (`-p` takes its prompt as a value; the turn goes
  down stdin as one stream-json `user` event);
* the operator's ~/.gemini is never read: everything is under a per-run HOME,
  and the forensic server is handed the REAL home back (its receipts and
  caches would otherwise land in a directory deleted after the stage);
* the built-in surface is the custom agent's `tools:` list, which must carry
  `finish` -- without it `--json-schema` output never appears;
* a turn that ends without `finish` is the schema gate, not an empty review;
* a large MCP result arrives as `output: ""` and is read back from its spill
  file, so the ledger holds the real answer.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from metascience_agent import agent as A
from metascience_agent.llm_backend import (
    ANTIGRAVITY,
    ANTIGRAVITY_AGENT,
    ANTIGRAVITY_DENY_RULES,
    ANTIGRAVITY_WEB_TOOLS,
    AntigravityStreamNormalizer,
    BudgetUnsupported,
    antigravity_config_isolation_row,
    antigravity_model_args,
    antigravity_model_family,
    antigravity_resume_invocation,
    merge_resumed_stage,
    build_invocation,
    fatal_backend_reason,
    make_stream_normalizer,
    mcp_discovery_error,
    mcp_discovery_from_init,
    parse_agy_models,
    resolve_backend,
    sandbox_limitation_sentence,
)
from metascience_agent.usage_guard import parse_antigravity_usage

DATA = Path(__file__).parent / "data"
FORENSIC = "mcp__forensic_metascience__"


def _fixture_events() -> list[dict]:
    return [json.loads(line) for line in
            (DATA / "agy_stream.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _normalize(events, **kw) -> list[dict]:
    norm = AntigravityStreamNormalizer(**kw)
    out: list[dict] = []
    for e in events:
        out.extend(norm.feed(e))
    return out


def _blocks(events, kind):
    return [b for e in events if e.get("type") in ("assistant", "user")
            for b in (e.get("message") or {}).get("content") or []
            if b.get("type") == kind]


class TestResolveBackend:
    def test_name_alias_and_env(self, monkeypatch):
        monkeypatch.delenv("METASCIENCE_LLM_CLI", raising=False)
        assert resolve_backend("antigravity") is ANTIGRAVITY
        assert resolve_backend("agy") is ANTIGRAVITY
        monkeypatch.setenv("METASCIENCE_LLM_CLI", "antigravity")
        assert resolve_backend(None) is ANTIGRAVITY

    def test_error_names_every_backend(self):
        with pytest.raises(ValueError, match="'openrouter' or 'antigravity'"):
            resolve_backend("cursor")

    def test_capabilities(self):
        assert ANTIGRAVITY.binary == "agy"
        assert ANTIGRAVITY.supports_budget is False
        assert ANTIGRAVITY.supports_usage_probe is True   # free `/usage`
        assert ANTIGRAVITY.mcp_strategy == "home_config"
        assert ANTIGRAVITY.prompt_delivery == "stdin_stream_json"
        # The built-in surface is a true allowlist, so no weaker-sandbox line.
        assert sandbox_limitation_sentence(ANTIGRAVITY) is None


class TestModelSelector:
    """agy exits 1 on a full slug plus a DIFFERENT --effort (measured), and
    has no xhigh/max on any listed model."""

    def test_full_slug_is_sent_alone(self):
        assert antigravity_model_args("gemini-4-argon-high", "low") == [
            "--model", "gemini-4-argon-high"]

    def test_base_name_takes_the_effort(self):
        assert antigravity_model_args("gemini-4-argon", "medium") == [
            "--model", "gemini-4-argon", "--effort", "medium"]

    def test_effort_clamped_down_to_what_the_model_offers(self):
        assert antigravity_model_args("claude-opus-5-5", "max")[-1] == "high"
        assert antigravity_model_args("gemini-3.8-flash", "xhigh")[-1] == "high"
        # gpt-oss-120b offers only medium: high clamps down to it, and low
        # (below everything offered) takes the lowest offered.
        assert antigravity_model_args("gpt-oss-120b", "high")[-1] == "medium"
        assert antigravity_model_args("gpt-oss-120b", "low")[-1] == "medium"

    def test_unknown_base_passes_through_for_agy_to_refuse(self):
        assert antigravity_model_args("gemini-9-new", "max") == [
            "--model", "gemini-9-new", "--effort", "max"]

    def test_no_effort_no_flag(self):
        assert antigravity_model_args("gemini-4-argon", None) == [
            "--model", "gemini-4-argon"]

    def test_family(self):
        assert antigravity_model_family("gemini-4-argon-high") == "gemini"
        assert antigravity_model_family("claude-sonnet-5-5") == "third_party"
        assert antigravity_model_family("gpt-oss-120b-medium") == "third_party"
        assert antigravity_model_family(None) is None

    def test_agy_models_listing_is_parsed(self):
        text = ("Fetching available models...\n"
                "gemini-4-argon-medium\tGemini 4 Argon (Medium)\n"
                "\n"
                "gpt-oss-120b-medium\tGPT-OSS 120B (Medium)\n")
        assert parse_agy_models(text) == [
            ("gemini-4-argon-medium", "Gemini 4 Argon (Medium)"),
            ("gpt-oss-120b-medium", "GPT-OSS 120B (Medium)")]


class TestInvocation:
    SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}},
              "required": ["ok"]}

    @pytest.fixture
    def sandbox_root(self, tmp_path, monkeypatch):
        monkeypatch.setenv("METASCIENCE_ANTIGRAVITY_SANDBOX_ROOT",
                           str(tmp_path / "asb"))
        return tmp_path

    def _build(self, **kw):
        defaults = dict(
            system_prompt="SYSTEM " * 30_000,  # ~210 KB: over MAX_ARG_STRLEN
            allowed_tools=[f"{FORENSIC}grim_check", f"{FORENSIC}extract_pdf"],
            model="gemini-4-argon",
            effort="high",
            json_schema=self.SCHEMA,
        )
        defaults.update(kw)
        return build_invocation(ANTIGRAVITY, **defaults)

    @staticmethod
    def _home_files(inv):
        home = inv.config_home
        return (
            json.loads((home / ".gemini/config/mcp_config.json").read_text()),
            json.loads((home / ".gemini/antigravity-cli/settings.json").read_text()),
            (home / f".gemini/config/agents/{ANTIGRAVITY_AGENT}.md").read_text(),
        )

    def test_argv_shape(self, sandbox_root, tmp_path):
        inv = self._build(paper_dir=tmp_path / "paper")
        try:
            argv = inv.argv
            assert argv[0] == "agy" and "--print=" in argv
            assert argv[argv.index("--agent") + 1] == ANTIGRAVITY_AGENT
            assert argv[argv.index("--input-format") + 1] == "stream-json"
            assert argv[argv.index("--output-format") + 1] == "stream-json"
            assert "--disable-slash-commands" in argv
            assert argv[argv.index("--add-dir") + 1] == str(tmp_path / "paper")
            schema_path = Path(argv[argv.index("--json-schema") + 1])
            assert json.loads(schema_path.read_text()) == self.SCHEMA
            assert inv.prompt_delivery == "stdin_stream_json"
            assert inv.expects_schema is True
            assert inv.workdir.is_dir()
        finally:
            inv.cleanup()

    def test_prompt_never_on_argv_it_is_the_agent_body(self, sandbox_root):
        inv = self._build()
        try:
            assert not any("SYSTEM SYSTEM" in a for a in inv.argv)
            _, _, agent_md = self._home_files(inv)
            assert "SYSTEM " * 1000 in agent_md
            # The route note rides with every launch: how tools are called,
            # and that the answer counts only through `finish`.
            assert "`finish`" in agent_md and "call_mcp_tool" in agent_md
        finally:
            inv.cleanup()

    def test_home_isolation_env(self, sandbox_root):
        inv = self._build()
        try:
            assert inv.env_overlay["HOME"] == str(inv.config_home)
            assert inv.env_overlay["AGY_CLI_DISABLE_AUTO_UPDATE"] == "true"
            assert str(sandbox_root / "asb") in str(inv.config_home)
        finally:
            inv.cleanup()

    def test_agent_is_an_allowlist_with_finish(self, sandbox_root):
        inv = self._build()
        try:
            _, _, agent_md = self._home_files(inv)
            front = agent_md.split("---", 2)[1]
            assert "excludeDefaultComponents: true" in front
            assert "inheritCustomizations: false" in front
            assert "enable_mcp_tools: true" in front
            assert "  - view_file" in front and "  - finish" in front
            for web in ANTIGRAVITY_WEB_TOOLS:
                assert web not in front
        finally:
            inv.cleanup()

    def test_mcp_server_fenced_and_given_the_real_home(
            self, sandbox_root, tmp_path):
        inv = self._build(mcp_stage="tool_agent", run_slug="r1",
                          paper_dir=tmp_path / "p",
                          mcp_tools=["grim_check", "extract_pdf"])
        try:
            mcp, settings, _ = self._home_files(inv)
            srv = mcp["mcpServers"]["forensic_metascience"]
            assert srv["args"][0] == "-m"
            env = srv["env"]
            assert env["HOME"] == str(Path.home())
            assert env["HOME"] != inv.env_overlay["HOME"]
            assert env["METASCIENCE_MCP_STAGE"] == "tool_agent"
            assert env["METASCIENCE_RUN_SLUG"] == "r1"
            assert env["METASCIENCE_MCP_TOOLS"] == "grim_check,extract_pdf"
            assert env["METASCIENCE_PAPER_DIR"] == str(tmp_path / "p")
            assert srv["enabledTools"] == ["extract_pdf", "grim_check"]
            assert settings["permissions"]["allow"] == [
                "mcp(forensic_metascience/*)"]
            assert settings["permissions"]["deny"] == list(ANTIGRAVITY_DENY_RULES)
            assert str(inv.workdir) in settings["trustedWorkspaces"]
        finally:
            inv.cleanup()

    def test_internet_delta_is_the_web_pair_and_read_url(self, sandbox_root):
        off, on = self._build(), self._build(internet=True)
        try:
            # The argv is identical (bar the per-run schema path): the whole
            # delta lives in the agent's tools and the permission rules.
            def _bare(argv):
                return [a for a in argv if not a.endswith("schema.json")]
            assert _bare(off.argv) == _bare(on.argv)
            _, s_off, a_off = self._home_files(off)
            _, s_on, a_on = self._home_files(on)
            for web in ANTIGRAVITY_WEB_TOOLS:
                assert web in a_on and web not in a_off
            assert "read_url(*)" in s_on["permissions"]["allow"]
            assert "read_url(*)" not in s_on["permissions"]["deny"]
            assert "read_url(*)" in s_off["permissions"]["deny"]
            # The shell stays denied either way.
            assert "command(*)" in s_on["permissions"]["deny"]
        finally:
            off.cleanup()
            on.cleanup()

    def test_no_forensic_server_when_not_asked(self, sandbox_root):
        inv = self._build(forensic_mcp=False)
        try:
            mcp, settings, agent_md = self._home_files(inv)
            assert mcp == {"mcpServers": {}}
            assert settings["permissions"]["allow"] == []
            assert "enable_mcp_tools: false" in agent_md
            assert inv.forensic_mcp is False
        finally:
            inv.cleanup()

    def test_effort_clamp_reaches_argv(self, sandbox_root):
        inv = self._build(model="claude-opus-5-5", effort="max")
        try:
            assert inv.argv[inv.argv.index("--effort") + 1] == "high"
            assert inv.model == "claude-opus-5-5"
        finally:
            inv.cleanup()

    def test_max_turns_is_stamped_not_sent(self, sandbox_root):
        inv = self._build(max_turns=3)
        try:
            assert inv.max_turns_unsupported is True
            assert "--max-turns" not in inv.argv
        finally:
            inv.cleanup()

    def test_budget_raises(self, sandbox_root):
        with pytest.raises(BudgetUnsupported):
            self._build(budget_usd=1.0)

    def test_empty_manifest_is_refused(self, sandbox_root):
        with pytest.raises(ValueError, match="empty tool manifest"):
            self._build(mcp_tools=[])

    def test_cleanup_removes_the_run_dir(self, sandbox_root):
        inv = self._build()
        run_dir = inv.config_home.parent
        assert run_dir.exists()
        inv.cleanup()
        assert not run_dir.exists()

    def test_skill_access_is_refused(self, sandbox_root):
        with pytest.raises(ValueError, match="claude backend only"):
            self._build(permission_mode="dontAsk")


class TestNormalizerOnTheCapturedStream:
    def test_init_is_synthesized_and_registry_not_claimed(self):
        out = _normalize(_fixture_events())
        init = out[0]
        assert init["type"] == "system" and init["subtype"] == "init"
        assert init["session_id"]
        # init.tools is the whole registry even under --agent (measured), so
        # it must not be presented as the tools this model had.
        assert "tools" not in init and "agy_registry_tools" in init

    def test_forensic_calls_are_named_and_paired(self):
        out = _normalize(_fixture_events())
        uses = _blocks(out, "tool_use")
        results = _blocks(out, "tool_result")
        names = [u["name"] for u in uses]
        assert names.count(f"{FORENSIC}extract_pdf") == 2
        assert names.count("StructuredOutput") == 2   # the finish channel
        first = next(u for u in uses if u["name"] == f"{FORENSIC}extract_pdf")
        assert "file_path" in first["input"] and first["agy_tool"] == "call_mcp_tool"
        # Every call has exactly one result with its id.
        assert sorted(u["id"] for u in uses) == sorted(
            r["tool_use_id"] for r in results)
        # The rejected `finish` is an error result naming the schema problem.
        bad = [r for r in results if r.get("is_error")]
        assert len(bad) == 1 and "schema_version" in bad[0]["content"]

    def test_mcp_result_text_is_the_tool_json(self):
        out = _normalize(_fixture_events())
        by_id = {u["id"]: u["name"] for u in _blocks(out, "tool_use")}
        answers = [json.loads(r["content"]) for r in _blocks(out, "tool_result")
                   if by_id[r["tool_use_id"]] == f"{FORENSIC}extract_pdf"]
        # First call: wrong argument name, the tool's own structured refusal.
        assert answers[0]["severity"] == "indeterminate"
        assert "pdf_path" in answers[0]["error"]
        # Second: the paper has not been table-extracted -- said in words.
        assert answers[1]["unreadable"] is True
        assert "THIS IS NOT A PAPER WITHOUT TABLES" in answers[1]["text_extractor_note"]

    def test_result_has_structured_output_tokens_and_no_cost(self):
        out = _normalize(_fixture_events(), expects_schema=True)
        result = out[-1]
        assert result["type"] == "result"
        assert result["structured_output"]["schema_version"] == "2.0"
        assert not result.get("is_error")
        assert "total_cost_usd" not in result   # agy reports none
        assert result["usage"]["input_tokens"] == 45906
        assert result["usage"]["cache_read_input_tokens"] == 110759

    def test_ledger_validates_the_forensic_calls(self):
        out = _normalize(_fixture_events())
        allowed = [f"{FORENSIC}extract_pdf"]
        ledger = A._tool_call_ledger(out, allowed)
        rows = [r for r in ledger if r.get("tool_short") == "extract_pdf"]
        assert len(rows) == 2 and all(r["validated"] for r in rows)

    def test_factory_selects_this_normalizer(self):
        n = make_stream_normalizer(ANTIGRAVITY, expects_schema=True,
                                   config_home=Path("/tmp/x"))
        assert isinstance(n, AntigravityStreamNormalizer)
        assert n.expects_schema is True and n.config_home == Path("/tmp/x")


def _step(index, state, stype, conv="c1", **kw):
    return {"event": "step_update", "step_update": {
        "conversation_id": conv, "step_index": index, "state": state,
        "step_type": stype, **kw}}


def _mcp_info(tool, output=None, error=None, server="forensic_metascience"):
    info = {"name": "call_mcp_tool", "parameters": {
        "ServerName": server, "ToolName": tool, "Arguments": {"n": 30}}}
    if output is not None:
        info["output"] = output
    if error is not None:
        info["error"] = error
    return info


class TestNormalizerUnits:
    def test_text_deltas_join_into_one_assistant_message(self):
        out = _normalize([
            _step(1, "ACTIVE", "agent_response", text_delta="consis"),
            _step(1, "ACTIVE", "agent_response", text_delta="tent"),
            _step(1, "DONE", "agent_response", text_delta="\n",
                  usage={"input_tokens": 10, "output_tokens": 2,
                         "thinking_tokens": 5}),
        ])
        msgs = [e for e in out if e.get("type") == "assistant"]
        assert len(msgs) == 1
        assert msgs[0]["message"]["content"][0]["text"] == "consistent\n"
        usage = msgs[0]["message"]["usage"]
        assert usage["output_tokens"] == 7 and usage["thinking_tokens"] == 5

    def test_spilled_result_is_read_back(self, tmp_path):
        spill = (tmp_path / ".gemini/antigravity-cli/brain/c1/"
                 ".system_generated/steps/2/output.txt")
        spill.parent.mkdir(parents=True)
        spill.write_text('{"severity": "consistent", "big": true}')
        out = _normalize([
            _step(2, "ACTIVE", "tool", tool_info=_mcp_info("extract_xml")),
            _step(2, "DONE", "tool", tool_info=_mcp_info("extract_xml", output="")),
        ], config_home=tmp_path)
        res = _blocks(out, "tool_result")[0]
        assert res["agy_output_spilled"] is True
        assert json.loads(res["content"])["big"] is True

    def test_missing_spill_is_marked_not_passed_off_as_empty(self, tmp_path):
        out = _normalize([
            _step(2, "DONE", "tool", tool_info=_mcp_info("extract_xml", output="")),
        ], config_home=tmp_path)
        res = _blocks(out, "tool_result")[0]
        assert res["agy_output_spilled"] == "missing"
        # A DONE with no prior ACTIVE still yields the call, then the result.
        assert _blocks(out, "tool_use")[0]["name"] == f"{FORENSIC}extract_xml"

    def test_wrong_server_name_stays_unvalidated(self):
        out = _normalize([
            _step(3, "ERROR", "tool", tool_info=_mcp_info(
                "grim_check", server="forensic",
                error={"type": "TOOL_ERROR", "message": "not enabled"})),
        ])
        use = _blocks(out, "tool_use")[0]
        assert use["name"] == "mcp__forensic__grim_check"
        ledger = A._tool_call_ledger(out, [f"{FORENSIC}grim_check"])
        assert ledger and not ledger[0]["validated"]
        assert _blocks(out, "tool_result")[0]["is_error"] is True

    def test_builtin_names_map_to_the_claude_vocabulary(self):
        out = _normalize([
            _step(4, "ERROR", "tool", tool_info={
                "name": "run_command", "parameters": {"CommandLine": "ls"},
                "error": {"message": "Matches user-configured deny rule."}}),
            _step(5, "DONE", "tool", tool_info={
                "name": "view_file", "parameters": {"AbsolutePath": "/p/a.xml"},
                "output": "3 lines, 99 bytes"}),
        ])
        uses = _blocks(out, "tool_use")
        assert [u["name"] for u in uses] == ["Bash", "Read"]
        assert uses[0]["input"]["command"] == "ls"
        assert uses[1]["input"]["file_path"] == "/p/a.xml"

    def test_turn_without_finish_is_the_schema_gate(self):
        """MEASURED 2026-10-18: the model explored the filesystem, ended with
        `response: ""` and `status: SUCCESS`, and no document existed."""
        out = _normalize([{"event": "result", "result": {
            "conversation_id": "c1", "status": "SUCCESS", "response": "",
            "num_turns": 1, "usage": {"input_tokens": 1}}}],
            expects_schema=True)
        result = out[-1]
        assert result["is_error"] is True
        assert result["subtype"] == "error_max_structured_output_retries"
        assert result["agy_no_finish"] is True
        assert "finish" in result["errors"][0]

    def test_no_schema_no_gate(self):
        out = _normalize([{"event": "result", "result": {
            "status": "SUCCESS", "response": "OK\n", "num_turns": 1}}])
        assert not out[-1].get("is_error")
        assert out[-1]["result"] == "OK\n"

    def test_cli_error_status_is_an_error(self):
        out = _normalize([{"event": "result", "result": {
            "status": "ERROR", "response": "",
            "error": 'unknown agent "nosuch" (available: forensic)'}}])
        assert out[-1]["is_error"] is True
        assert out[-1]["subtype"] == "agy_error"
        assert "unknown agent" in out[-1]["errors"][0]

    def test_finish_done_without_tool_info_is_still_structured_output(self):
        """MEASURED on the first agy apple_cider eval (2026-10-18): a second `finish` arrived
        only as its DONE (`step_type: finish`, no tool_info), and the ledger
        recorded a tool named ""."""
        out = _normalize([_step(9, "DONE", "finish")])
        assert [u["name"] for u in _blocks(out, "tool_use")] == ["StructuredOutput"]

    def test_unknown_events_pass_through(self):
        ev = {"event": "something_new", "something_new": {}}
        assert _normalize([ev]) == [ev]


class TestDiscoveryUsageAndFatal:
    def test_init_declares_nothing_and_that_is_ok(self):
        disc = mcp_discovery_from_init({"type": "system"}, ANTIGRAVITY)
        assert disc["declared"] is None and disc["ok"] is True
        assert "agy" in disc["note"]
        assert mcp_discovery_error(disc) is None
        disc = mcp_discovery_from_init({"type": "system"}, ANTIGRAVITY,
                                       forensic_mcp=False)
        assert disc["ok"] is True

    PAYLOAD = {"status": "SUCCESS", "command": {"name": "usage", "data": {
        "groups": [
            {"name": "Gemini Models", "buckets": [
                {"window": "weekly", "remaining_fraction": 0.90},
                {"window": "5h", "remaining_fraction": 0.40}]},
            {"name": "Claude and GPT models", "buckets": [
                {"window": "weekly", "remaining_fraction": 0.02},
                {"window": "5h", "remaining_fraction": 1.0}]},
            {"name": "Gemini 4 Argon", "buckets": [
                {"window": "weekly", "remaining_fraction": 0.30}]},
        ]}}}

    def test_usage_counts_only_the_models_groups(self):
        # A Gemini Flash run must not stop on the spent Claude week.
        assert parse_antigravity_usage(self.PAYLOAD, "gemini-3.8-flash") == (60, 10)
        # Argon also draws on its own weekly bucket.
        assert parse_antigravity_usage(self.PAYLOAD, "gemini-4-argon-high") == (60, 70)
        assert parse_antigravity_usage(self.PAYLOAD, "claude-opus-5-5") == (0, 98)
        # Unknown model: the cautious reading, every group.
        assert parse_antigravity_usage(self.PAYLOAD, None) == (60, 98)

    def test_usage_unparseable_fails_open(self):
        assert parse_antigravity_usage({"status": "SUCCESS"}, None) == (None, None)

    @pytest.mark.parametrize("stderr", [
        "Error: authentication required. Run 'agy' to log in, then retry.",
        "Authentication expired. Please log back in.",
        "individual quota reached for this model",
        "Your AI credits balance is too low to continue.",
    ])
    def test_account_level_refusals_are_fatal(self, stderr):
        assert fatal_backend_reason(stderr) is not None

    def test_isolation_row_missing_binary(self, monkeypatch):
        import shutil
        monkeypatch.setattr(shutil, "which", lambda name: None)
        name, ok, detail = antigravity_config_isolation_row()
        assert ok is False and "not on PATH" in detail

    def test_isolation_row_names_foreign_servers(self, monkeypatch, tmp_path):
        import shutil
        monkeypatch.setattr(shutil, "which", lambda name: "/bin/agy")
        monkeypatch.setenv("HOME", str(tmp_path))
        cfg = tmp_path / ".gemini/config/mcp_config.json"
        cfg.parent.mkdir(parents=True)
        cfg.write_text(json.dumps({"mcpServers": {
            "github": {"command": "x"}, "off": {"command": "y", "disabled": True}}}))
        name, ok, detail = antigravity_config_isolation_row()
        assert ok is True and "github" in detail and "off" not in detail


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
        self.returncode = None

    async def wait(self):
        self.returncode = 0
        return 0

    def kill(self):
        pass


@pytest.fixture
def agy_stage_env(tmp_path, monkeypatch):
    monkeypatch.setenv("METASCIENCE_ANTIGRAVITY_SANDBOX_ROOT", str(tmp_path / "asb"))
    monkeypatch.setenv("METASCIENCE_SKIP_PREFLIGHT", "1")
    monkeypatch.setattr(A, "_assert_ready", lambda *a, **k: None)
    seen: list[dict] = []

    async def _guard(*a, **k):
        seen.append(k)

    monkeypatch.setattr(A, "usage_guard", _guard)
    from metascience_agent.llm_backend import Backend
    monkeypatch.setattr(Backend, "assert_mcp_live", lambda self, sandbox: None)
    return seen


class TestRunStageAntigravity:
    def test_end_to_end_fixture_stream(self, agy_stage_env, monkeypatch):
        payload = b"".join((json.dumps(e) + "\n").encode()
                           for e in _fixture_events())
        procs = []

        async def fake_exec(*a, **kw):
            p = _FakeProc(payload)
            # stdin is a pre-filled file (tests/test_prompt_stdin_race.py);
            # read it here, since _run_stage closes it once spawned.
            p.stdin.written = kw["stdin"].read()
            procs.append((a, kw, p))
            return p

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
        inv = A._build_claude_cmd(
            system_prompt="s", allowed_tools=A.STAGE1_TOOLS,
            model="gemini-3.8-flash-low", backend="antigravity",
            json_schema={"type": "object"},
        )
        run_dir = inv.config_home.parent
        stage = asyncio.run(A._run_stage(inv, "the prompt", stage_label="sweep"))
        assert stage["structured_output"]["schema_version"] == "2.0"
        assert stage["llm_backend"] == "antigravity"
        assert stage["cost_usd"] == 0.0 and stage["cost_reported"] is False
        assert stage["is_error"] is False
        assert stage["mcp_discovery"]["ok"] is True
        ledger = A._tool_call_ledger(stage["messages"], A.STAGE1_TOOLS)
        assert sum(1 for r in ledger if r["tool_short"] == "extract_pdf"
                   and r["validated"]) == 2
        # The turn went down stdin as ONE stream-json user event...
        argv, kw, proc = procs[0]
        line = proc.stdin.written.decode()
        assert line.endswith("\n") and line.count("\n") == 1
        assert json.loads(line) == {"event": "user",
                                    "message": {"content": "the prompt"}}
        assert "the prompt" not in " ".join(argv)
        # ...under the per-run HOME, from the run's own cwd.
        assert kw["env"]["HOME"] == str(inv.config_home)
        assert kw["cwd"] == str(inv.workdir)
        # The usage guard was told the model (per-family quota buckets).
        assert agy_stage_env[-1]["model"] == "gemini-3.8-flash-low"
        assert not run_dir.exists()


class TestServerImportsThisTree:
    """MEASURED 2026-10-18 in an eval-lane worktree: with `PYTHONPATH` set to
    `src/` alone, the server imported the editable install's (older)
    `copy_paste_detector`, died on import, and every stage refused."""

    def test_pythonpath_carries_both_source_roots(self):
        from metascience_agent.llm_backend import forensic_pythonpath
        import os
        parts = forensic_pythonpath().split(os.pathsep)
        src = Path(A.__file__).resolve().parent.parent
        assert parts[0] == str(src)
        detector = src.parent / "copy_paste_detector" / "src"
        if detector.is_dir():
            assert str(detector) in parts

    def test_every_backend_hands_the_server_both(self, tmp_path, monkeypatch):
        from metascience_agent.llm_backend import forensic_pythonpath
        monkeypatch.setenv("METASCIENCE_ANTIGRAVITY_SANDBOX_ROOT", str(tmp_path))
        inv = build_invocation(ANTIGRAVITY, system_prompt="s",
                               allowed_tools=[f"{FORENSIC}grim_check"],
                               model="gemini-4-argon", effort="high")
        try:
            mcp = json.loads((inv.config_home / ".gemini/config/mcp_config.json")
                             .read_text())
            assert (mcp["mcpServers"]["forensic_metascience"]["env"]["PYTHONPATH"]
                    == forensic_pythonpath())
        finally:
            inv.cleanup()
        claude = A._build_claude_cmd(system_prompt="s",
                                     allowed_tools=[f"{FORENSIC}grim_check"])
        cfg = json.loads(claude.argv[claude.argv.index("--mcp-config") + 1])
        assert (cfg["mcpServers"]["forensic_metascience"]["env"]["PYTHONPATH"]
                == forensic_pythonpath())


class TestRefusalBeforeLaunchCleansUp:
    """MEASURED 2026-10-18: an eval whose liveness probe refused left both
    analysts' run dirs in ~/.cache/metascience/antigravity-sandbox."""

    @pytest.mark.parametrize("where", ["preflight", "mcp_live", "usage_guard"])
    def test_sandbox_removed_when_a_gate_refuses(self, where, tmp_path, monkeypatch):
        from metascience_agent.llm_backend import Backend, MCPUnavailable
        monkeypatch.setenv("METASCIENCE_ANTIGRAVITY_SANDBOX_ROOT", str(tmp_path))

        def _refuse(*a, **k):
            raise MCPUnavailable("refused")

        async def _arefuse(*a, **k):
            raise MCPUnavailable("refused")

        async def _ok(*a, **k):
            return None

        monkeypatch.setattr(A, "_assert_ready",
                            _refuse if where == "preflight" else (lambda *a, **k: None))
        monkeypatch.setattr(Backend, "assert_mcp_live",
                            _refuse if where == "mcp_live" else (lambda self, s: None))
        monkeypatch.setattr(A, "usage_guard", _arefuse if where == "usage_guard" else _ok)
        inv = build_invocation(ANTIGRAVITY, system_prompt="s",
                               allowed_tools=[f"{FORENSIC}grim_check"],
                               model="gemini-4-argon", effort="high")
        run_dir = inv.config_home.parent
        assert run_dir.exists()
        with pytest.raises(MCPUnavailable):
            asyncio.run(A._run_stage(inv, "p", stage_label="s"))
        assert not run_dir.exists()


class TestResumeTheUnfinishedConversation:
    """MEASURED 2026-10-18 (apple_cider, gemini-3.8-flash-medium): the tools
    agent declared its tables and ended without `finish`, before any check;
    the schema-gate retry could not continue its work. Now the sandbox is
    kept and the retry resumes the conversation (`--conversation <id>`,
    measured to keep context)."""

    NO_FINISH = [
        {"event": "init", "conversation_id": "conv-1", "init": {"cwd": "/w"}},
        {"event": "step_update", "step_update": {
            "conversation_id": "conv-1", "step_index": 2, "state": "DONE",
            "step_type": "tool", "tool_info": {
                "name": "call_mcp_tool", "output": '{"severity": "consistent"}',
                "parameters": {"ServerName": "forensic_metascience",
                               "ToolName": "declare_table", "Arguments": {}}}}},
        {"event": "result", "result": {"conversation_id": "conv-1",
                                       "status": "SUCCESS", "response": "",
                                       "num_turns": 1}},
    ]
    DOC = {"schema_version": "2.0", "findings": [{"title": "x"}], "unchecked": []}

    def _finished(self):
        return [
            {"event": "init", "conversation_id": "conv-1", "init": {"cwd": "/w"}},
            {"event": "step_update", "step_update": {
                "conversation_id": "conv-1", "step_index": 5, "state": "DONE",
                "step_type": "tool", "tool_info": {
                    "name": "call_mcp_tool", "output": '{"severity": "suspicious"}',
                    "parameters": {"ServerName": "forensic_metascience",
                                   "ToolName": "csf_test", "Arguments": {}}}}},
            {"event": "result", "result": {"conversation_id": "conv-1",
                                           "status": "SUCCESS", "response": "{}",
                                           "num_turns": 2,
                                           "structured_output": self.DOC}},
        ]

    def _inv(self, tmp_path, monkeypatch):
        monkeypatch.setenv("METASCIENCE_ANTIGRAVITY_SANDBOX_ROOT", str(tmp_path))
        return build_invocation(ANTIGRAVITY, system_prompt="s",
                                allowed_tools=[f"{FORENSIC}csf_test"],
                                model="gemini-3.8-flash-medium", effort="medium",
                                json_schema={"type": "object"})

    def test_no_finish_keeps_the_sandbox_and_marks_the_result(
            self, tmp_path, monkeypatch):
        from metascience_agent.llm_backend import stage_resumable_conversation
        inv = self._inv(tmp_path, monkeypatch)
        out = _normalize(self.NO_FINISH, expects_schema=True,
                         resume_state=inv.resume_state)
        assert out[-1]["agy_resume"] == {"conversation_id": "conv-1"}
        assert stage_resumable_conversation({"messages": out}) == "conv-1"
        run_dir = inv.config_home.parent
        inv.cleanup()
        assert run_dir.exists()                      # kept for the resume
        resume = antigravity_resume_invocation({"messages": out})
        assert resume.argv[-2:] == ["--conversation", "conv-1"]
        assert resume.config_home == inv.config_home
        assert resume.env_overlay["HOME"] == inv.env_overlay["HOME"]
        resume.cleanup()
        assert not run_dir.exists()                  # removed after it
        assert antigravity_resume_invocation({"messages": out}) is None

    def test_a_finished_turn_is_not_kept(self, tmp_path, monkeypatch):
        inv = self._inv(tmp_path, monkeypatch)
        _normalize(self._finished(), expects_schema=True,
                   resume_state=inv.resume_state)
        run_dir = inv.config_home.parent
        inv.cleanup()
        assert not run_dir.exists()

    def test_merge_carries_the_whole_conversation(self):
        first = {"messages": _normalize(self.NO_FINISH, expects_schema=True,
                                        resume_state={"keep": False}),
                 "tool_calls": 1}
        second = {"messages": _normalize(self._finished(), expects_schema=True),
                  "tool_calls": 1, "structured_output": self.DOC}
        merged = merge_resumed_stage(first, second)
        results = [e for e in merged["messages"] if e.get("type") == "result"]
        assert len(results) == 1 and results[0].get("structured_output")
        names = [b["name"] for b in _blocks(merged["messages"], "tool_use")]
        assert names == [f"{FORENSIC}declare_table", f"{FORENSIC}csf_test"]
        assert merged["tool_calls"] == 2
        assert merged["resumed_from_conversation"] == "conv-1"

    def test_retry_if_empty_resumes_instead_of_restarting(
            self, agy_stage_env, tmp_path, monkeypatch):
        from types import SimpleNamespace
        from metascience_agent.modules import _analyst
        payloads = [self.NO_FINISH, self._finished()]
        spawned = []

        async def fake_exec(*a, **kw):
            p = _FakeProc(b"".join((json.dumps(e) + "\n").encode()
                                   for e in payloads[len(spawned)]))
            p.stdin.written = kw["stdin"].read()     # the pre-filled prompt file
            spawned.append((a, p))
            return p

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
        inv = A._build_claude_cmd(system_prompt="s",
                                  allowed_tools=[f"{FORENSIC}csf_test"],
                                  model="gemini-3.8-flash-medium",
                                  backend="antigravity",
                                  json_schema={"type": "object"})
        first = asyncio.run(A._run_stage(inv, "sweep", stage_label="tool_agent"))
        assert first["error_subtype"] == "error_max_structured_output_retries"

        def _never():
            raise AssertionError("a resumable stage must not restart or recover")

        limitations: list[str] = []
        ctx = SimpleNamespace(verbose=False, timeout=None, on_progress=None, src=None)
        stage, doc = asyncio.run(_analyst.retry_if_empty(
            ctx, SimpleNamespace(name="antigravity"), first, None, "tool_agent",
            "tool_expert", _never, "sweep", limitations, recover_cmd=_never))
        assert doc == self.DOC
        argv, proc = spawned[1]
        assert list(argv[-2:]) == ["--conversation", "conv-1"]
        assert json.loads(proc.stdin.written)["message"]["content"].startswith(
            "Your previous turn ended without calling `finish`")
        assert any("RESUMED the same agy conversation" in l for l in limitations)
        assert stage["resumed_from_conversation"] == "conv-1"
        assert not inv.config_home.parent.exists()
