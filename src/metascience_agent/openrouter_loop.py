"""A small agent loop over the OpenRouter chat-completions API.

Phase 3c of the modular refactor (docs/specs/modules.md). The three CLI
backends (Claude Code, Codex, Grok Build) each run their own agent loop;
this module is ours, so any OpenRouter model can run an analyst or the
adjudicator. It is launched as a subprocess exactly like a CLI
(``llm_backend.OPENROUTER``) and it SPEAKS THE CLAUDE STREAM-JSON DIALECT on
stdout, so `runtime._run_stage`, the tool ledger, the transcript writers and
`normalize_event` need no OpenRouter branch:

  system/init -> assistant (text + tool_use blocks) -> user (tool_result
  blocks) -> ... -> result (result, structured_output, total_cost_usd, usage)

Tools reach the model through MCP: the loop starts the servers named in
``--mcp-config`` (the same JSON a Claude launch receives, so the forensic
server gets the same role fence, toolset manifest and paper directory) and
offers only the tools in ``--allowedTools``. A tool the model names outside
that list is refused in the transcript, never called. ``Read`` is offered
when listed and reads files under the paper directory only.

Structured output follows Claude Code's mechanism: a ``StructuredOutput``
tool whose parameters ARE the schema. A call that does not validate is
answered with the validation error and counts against
``MAX_STRUCTURED_RETRIES``; exhausting it ends the run with the same subtype
Claude uses, ``error_max_structured_output_retries``.

Cost is OpenRouter's own per-response ``usage.cost``, summed. There is no
spend cap (``supports_budget=False``): the run records what it cost.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

BASE_URL_ENV = "OPENROUTER_BASE_URL"
API_KEY_ENV = "OPENROUTER_API_KEY"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
STRUCTURED_TOOL = "StructuredOutput"
READ_TOOL = "Read"
MAX_STRUCTURED_RETRIES = 3
#: A tool result longer than this is cut, and the cut is SAID in the text the
#: model receives -- a silent truncation reads as a short table.
MAX_TOOL_RESULT_CHARS = 120_000
HTTP_RETRIES = 5
HTTP_TIMEOUT_S = 600
#: OpenRouter's reasoning effort takes low/medium/high; our ladder is wider.
EFFORT_MAP = {"low": "low", "medium": "medium", "high": "high",
              "xhigh": "high", "max": "high"}


def emit(event: dict) -> None:
    sys.stdout.write(json.dumps(event) + "\n")
    sys.stdout.flush()


class LoopError(RuntimeError):
    def __init__(self, subtype: str, message: str):
        super().__init__(message)
        self.subtype = subtype


# ---------------------------------------------------------------- tools

def _function_tool(name: str, description: str, schema: dict) -> dict:
    params = schema if isinstance(schema, dict) and schema else {"type": "object", "properties": {}}
    return {"type": "function",
            "function": {"name": name, "description": description or "", "parameters": params}}


def _read_tool() -> dict:
    return _function_tool(READ_TOOL, "Read a text file inside the paper directory.", {
        "type": "object",
        "properties": {"file_path": {"type": "string"},
                       "offset": {"type": "integer", "minimum": 0},
                       "limit": {"type": "integer", "minimum": 1}},
        "required": ["file_path"]})


def read_file(args: dict, root: Path | None) -> str:
    """`Read` confined to the paper directory (resolved, so `..` and symlinks
    out of it are refused by name)."""
    if root is None:
        return "Read refused: no paper directory was configured for this run."
    raw = str(args.get("file_path") or "")
    path = (root / raw).resolve() if not os.path.isabs(raw) else Path(raw).resolve()
    if path != root and root not in path.parents:
        return f"Read refused: {raw} is outside the paper directory."
    if not path.is_file():
        return f"Read refused: {raw} is not a file."
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start = int(args.get("offset") or 0)
    stop = start + int(args.get("limit") or 2000)
    return "\n".join(f"{i + 1}\t{line}" for i, line in enumerate(lines[start:stop], start))


def _validate(doc: Any, schema: dict) -> str | None:
    try:
        import jsonschema
    except ImportError:  # pragma: no cover - a dependency of mcp
        return None if isinstance(doc, dict) else "structured output must be an object"
    try:
        jsonschema.validate(doc, schema)
    except jsonschema.ValidationError as exc:
        where = "/".join(str(p) for p in exc.absolute_path) or "(root)"
        return f"{where}: {exc.message}"
    return None


def _cut(text: str) -> str:
    if len(text) <= MAX_TOOL_RESULT_CHARS:
        return text
    return (text[:MAX_TOOL_RESULT_CHARS]
            + f"\n[result truncated by the OpenRouter loop: {len(text) - MAX_TOOL_RESULT_CHARS}"
            " more characters were not delivered; request a narrower range]")


# ---------------------------------------------------------------- MCP

class McpHub:
    """The MCP servers of one run, keyed by the model-facing tool name
    (`mcp__<server>__<tool>`, the Claude naming the ledger already reads)."""

    def __init__(self) -> None:
        self.stack = contextlib.AsyncExitStack()
        self.sessions: dict[str, Any] = {}
        self.tools: dict[str, tuple[str, str, dict]] = {}   # name -> (server, tool, decl)
        self.status: list[dict] = []

    async def start(self, config: dict) -> None:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        servers = (config or {}).get("mcpServers") or {}
        for server, spec in servers.items():
            params = StdioServerParameters(
                command=spec["command"], args=list(spec.get("args") or []),
                env={**os.environ, **(spec.get("env") or {})})
            try:
                read, write = await self.stack.enter_async_context(stdio_client(params))
                session = await self.stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                listed = await session.list_tools()
            except Exception as exc:  # the init event records it; the gate aborts
                self.status.append({"name": server, "status": f"failed: {exc}"})
                continue
            self.sessions[server] = session
            self.status.append({"name": server, "status": "connected"})
            for tool in listed.tools:
                name = f"mcp__{server}__{tool.name}"
                self.tools[name] = (server, tool.name, {
                    "description": tool.description or "",
                    "schema": tool.inputSchema or {"type": "object", "properties": {}}})

    async def call(self, name: str, args: dict) -> tuple[str, bool]:
        server, tool, _ = self.tools[name]
        result = await self.sessions[server].call_tool(tool, args)
        text = "".join(getattr(part, "text", "") or "" for part in (result.content or []))
        return text, bool(getattr(result, "isError", False))

    async def close(self) -> None:
        with contextlib.suppress(Exception):
            await self.stack.aclose()


# ---------------------------------------------------------------- HTTP

async def complete(client, body: dict) -> dict:
    """One chat-completions call; 429/5xx retried with backoff, everything
    else raised as `error_during_execution` with the provider's message."""
    delay = 2.0
    for attempt in range(HTTP_RETRIES + 1):
        try:
            resp = await client.post("/chat/completions", json=body)
        except Exception as exc:  # network
            if attempt == HTTP_RETRIES:
                raise LoopError("error_during_execution", f"OpenRouter unreachable: {exc}")
            await asyncio.sleep(delay)
            delay *= 2
            continue
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and data.get("error"):
                raise LoopError("error_during_execution",
                                f"OpenRouter error: {json.dumps(data['error'])[:500]}")
            return data
        if resp.status_code in (429, 500, 502, 503, 504) and attempt < HTTP_RETRIES:
            await asyncio.sleep(delay)
            delay *= 2
            continue
        raise LoopError("error_during_execution",
                        f"OpenRouter HTTP {resp.status_code}: {resp.text[:500]}")
    raise LoopError("error_during_execution", "OpenRouter retries exhausted")


# ---------------------------------------------------------------- loop

async def run(args, prompt: str) -> dict:
    import httpx

    key = (os.environ.get(API_KEY_ENV) or "").strip()
    if not key:
        raise LoopError("error_during_execution",
                        f"{API_KEY_ENV} is not set; the openrouter backend cannot run")
    system_prompt = Path(args.system_prompt_file).read_text(encoding="utf-8") \
        if args.system_prompt_file else ""
    schema = json.loads(Path(args.json_schema_file).read_text(encoding="utf-8")) \
        if args.json_schema_file else None
    allowed = [t for t in (args.allowed_tools or "").split(",") if t]
    root = Path(args.paper_dir).resolve() if args.paper_dir else None

    hub = McpHub()
    t0 = time.time()
    session_id = str(uuid.uuid4())
    try:
        await hub.start(json.loads(args.mcp_config or "{}"))
        offered = [n for n in allowed if n in hub.tools]
        tools = [_function_tool(n, hub.tools[n][2]["description"], hub.tools[n][2]["schema"])
                 for n in offered]
        if READ_TOOL in allowed:
            tools.append(_read_tool())
        if schema is not None:
            tools.append(_function_tool(
                STRUCTURED_TOOL,
                "Submit your final answer. Its parameters are the required output schema; "
                "call it exactly once, when you are done.", schema))
        emit({"type": "system", "subtype": "init", "session_id": session_id,
              "model": args.model, "mcp_servers": hub.status,
              "tools": [t["function"]["name"] for t in tools],
              "backend": "openrouter"})

        body_base: dict = {"model": args.model, "usage": {"include": True}}
        effort = EFFORT_MAP.get((args.effort or "").lower())
        if effort:
            body_base["reasoning"] = {"effort": effort}
        if args.internet:
            body_base["plugins"] = [{"id": "web"}]
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        cost = 0.0
        cost_seen = False
        tokens_in = tokens_out = 0
        turns = 0
        structured = None
        structured_failures = 0
        final_text = ""
        async with httpx.AsyncClient(
                base_url=os.environ.get(BASE_URL_ENV, DEFAULT_BASE_URL),
                headers={"Authorization": f"Bearer {key}",
                         "X-Title": "forensic-metascience-ai-toolkit"},
                timeout=HTTP_TIMEOUT_S) as client:
            while True:
                if args.max_turns is not None and turns >= args.max_turns:
                    raise LoopError("error_max_turns", f"reached --max-turns {args.max_turns}")
                turns += 1
                body = {**body_base, "messages": messages}
                if tools:
                    body["tools"] = tools
                data = await complete(client, body)
                usage = data.get("usage") or {}
                if usage.get("cost") is not None:
                    cost += float(usage["cost"])
                    cost_seen = True
                tokens_in += int(usage.get("prompt_tokens") or 0)
                tokens_out += int(usage.get("completion_tokens") or 0)
                choice = (data.get("choices") or [{}])[0]
                message = choice.get("message") or {}
                text = message.get("content") or ""
                calls = message.get("tool_calls") or []
                blocks: list[dict] = []
                if text:
                    blocks.append({"type": "text", "text": text})
                    final_text = text
                parsed_calls = []
                for call in calls:
                    fn = call.get("function") or {}
                    try:
                        call_args = json.loads(fn.get("arguments") or "{}")
                    except json.JSONDecodeError as exc:
                        call_args = {"_unparseable_arguments": str(exc)}
                    cid = call.get("id") or f"call_{uuid.uuid4().hex[:12]}"
                    parsed_calls.append((cid, fn.get("name") or "", call_args))
                    blocks.append({"type": "tool_use", "id": cid, "name": fn.get("name") or "",
                                   "input": call_args})
                emit({"type": "assistant", "session_id": session_id,
                      "message": {"role": "assistant", "model": args.model, "content": blocks,
                                  "usage": {"input_tokens": int(usage.get("prompt_tokens") or 0),
                                            "output_tokens": int(usage.get("completion_tokens") or 0)}}})
                messages.append({"role": "assistant", "content": text or None,
                                 **({"tool_calls": calls} if calls else {})})

                if not parsed_calls:
                    if schema is None:
                        break
                    structured_failures += 1
                    if structured_failures > MAX_STRUCTURED_RETRIES:
                        raise LoopError("error_max_structured_output_retries",
                                        "the model never called StructuredOutput")
                    messages.append({"role": "user", "content":
                                     f"Call the {STRUCTURED_TOOL} tool with your final answer."})
                    continue

                results = []
                done = False
                for cid, name, call_args in parsed_calls:
                    is_error = False
                    if name == STRUCTURED_TOOL and schema is not None:
                        problem = _validate(call_args, schema)
                        if problem is None:
                            structured, done = call_args, True
                            out = "Structured output accepted."
                        else:
                            structured_failures += 1
                            is_error = True
                            out = f"Structured output rejected: {problem}"
                            if structured_failures > MAX_STRUCTURED_RETRIES:
                                emit_tool_results(session_id, [(cid, out, True)])
                                raise LoopError("error_max_structured_output_retries", problem)
                    elif name == READ_TOOL and READ_TOOL in allowed:
                        out = read_file(call_args, root)
                    elif name in hub.tools and name in allowed:
                        try:
                            out, is_error = await hub.call(name, call_args)
                        except Exception as exc:
                            out, is_error = f"tool call failed: {exc}", True
                    else:
                        out, is_error = f"tool {name!r} is not available to this stage", True
                    out = _cut(out)
                    results.append((cid, out, is_error))
                    messages.append({"role": "tool", "tool_call_id": cid, "content": out})
                emit_tool_results(session_id, results)
                if done:
                    break

        result = {"type": "result", "subtype": "success", "is_error": False,
                  "session_id": session_id, "result": final_text,
                  "num_turns": turns, "duration_ms": int((time.time() - t0) * 1000),
                  "usage": {"input_tokens": tokens_in, "output_tokens": tokens_out}}
        if cost_seen:
            result["total_cost_usd"] = round(cost, 6)
        if structured is not None:
            result["structured_output"] = structured
        return result
    finally:
        await hub.close()


def emit_tool_results(session_id: str, results: list[tuple[str, str, bool]]) -> None:
    emit({"type": "user", "session_id": session_id,
          "message": {"role": "user", "content": [
              {"type": "tool_result", "tool_use_id": cid, "content": out, "is_error": err}
              for cid, out, err in results]}})


def parse_args(argv: list[str] | None = None):
    p = argparse.ArgumentParser(prog="openrouter_loop")
    p.add_argument("--model", required=True)
    p.add_argument("--effort", default=None)
    p.add_argument("--mcp-config", default="{}")
    p.add_argument("--allowedTools", dest="allowed_tools", default="")
    p.add_argument("--system-prompt-file", default=None)
    p.add_argument("--json-schema-file", default=None)
    p.add_argument("--max-turns", type=int, default=None)
    p.add_argument("--paper-dir", default=None)
    p.add_argument("--internet", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    prompt = sys.stdin.read()
    try:
        result = asyncio.run(run(args, prompt))
    except LoopError as exc:
        emit({"type": "result", "subtype": exc.subtype, "is_error": True,
              "result": str(exc), "errors": [str(exc)]})
        return 1
    except Exception as exc:  # refuse out loud, in the stream the runner reads
        emit({"type": "result", "subtype": "error_during_execution", "is_error": True,
              "result": f"{type(exc).__name__}: {exc}", "errors": [str(exc)]})
        return 1
    emit(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
