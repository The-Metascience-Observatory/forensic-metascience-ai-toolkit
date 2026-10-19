"""Standalone stdio MCP server exposing the forensic metascience tools.

Run as: python -m forensic_metascience_ai_toolkit.mcp_server

This is the cross-process counterpart to the in-process tool wrappers in
tools_mcp.py. The Claude CLI launches this script via --mcp-config and
talks to it over stdin/stdout. Reusing the SdkMcpTool definitions from
tools_mcp.py keeps a single source of truth for tool names, descriptions,
schemas, and handlers.
"""

import asyncio
import json
import os
from typing import Annotated, Any, get_args, get_origin

import mcp.types as mcp_types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .tools_mcp import ALL_TOOLS

_PY_TYPE_TO_JSON = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _to_json_schema(schema: Any) -> dict:
    """Convert an SdkMcpTool input_schema (dict of name->python_type) to JSON Schema.

    UNWRAPS `Annotated[type, help]`, which is how `ToolSpec.schema` carries a
    parameter's documentation. Not doing so did two things at once, silently:

      * IT THREW AWAY EVERY HELP STRING -- 135 of them, including the one that
        defines this project's primary feature: "VERBATIM text from the paper
        containing the values you are passing -- one contiguous span, copied
        exactly, not reassembled." No tool DESCRIPTION repeats it, so the model
        was asked for `source_quote` with no statement anywhere of what the
        parameter is for. `registry.ToolSpec.schema` had already fixed this at
        its own layer, and its docstring says the advice "existed and was
        invisible" -- this function then undid the fix one layer down.
      * IT MISTYPED THEM. `Annotated[int, help]` is not a key in
        `_PY_TYPE_TO_JSON`, so `.get(typ, "string")` fell through to the
        DEFAULT. MEASURED: 31 parameters were advertised to the model as
        strings when they are int, list, bool or float -- including every
        `decimals` in the registry, whose entire purpose is to carry a printed
        precision as an integer.

    A dict lookup keyed on a bare type is defeated by any wrapper around that
    type, and a `.get(..., "string")` fallback makes the failure indistinguishable
    from a deliberate default.
    """
    if isinstance(schema, dict) and schema.get("type") == "object" and "properties" in schema:
        return schema
    properties: dict[str, dict] = {}
    for name, typ in (schema or {}).items():
        description = None
        if get_origin(typ) is Annotated:
            args = get_args(typ)
            typ = args[0]
            description = next((a for a in args[1:] if isinstance(a, str)), None)
        prop: dict[str, Any] = {"type": _PY_TYPE_TO_JSON.get(typ, "string")}
        if description:
            prop["description"] = description
        properties[name] = prop
    return {"type": "object", "properties": properties}


server = Server("forensic_metascience")

#: Per-stage tool filtering, set by `agent._build_mcp_config` and read here
#: at the process boundary the pipeline owns (the model cannot write env).
#: MEASURED FAILURE, 2026-08-21 apple_cider eval: the TOOL EXPERT called
#: `run_python_script` three times -- a SCIENCE_AGENT-only tool -- and every
#: call EXECUTED, because the per-role allowlists lived in `--allowedTools`
#: (an auto-approve list under bypassPermissions, not a fence) while this
#: server registered every tool for every caller. The "tool agent writes no
#: code" guarantee was prompt-deep. With the stage named, off-role tools are
#: not registered at all: absence, the same mechanism that already keeps the
#: two CLI-only tools off this server. Unset or unrecognised -> full
#: surface (the CLI operator's server, and any archived config).
MCP_STAGE_ENV = "METASCIENCE_MCP_STAGE"


class ToolManifestError(RuntimeError):
    """A pipeline tool manifest the server cannot honour. Raised at startup:
    the server does not come up, the stage fails loudly as MCP-unavailable,
    and nothing is served on a guess."""


def _stage_filtered_tools():
    try:
        from .pipeline_config import MCP_TOOLS_ENV, enabled_tools_from_env
    except Exception as exc:  # noqa: BLE001
        if os.environ.get("METASCIENCE_MCP_TOOLS") is not None:
            raise ToolManifestError(
                f"a tool manifest was supplied but cannot be read ({exc})") from exc
        return _role_filtered_tools()
    enabled = enabled_tools_from_env()
    if enabled is None:
        return _role_filtered_tools()
    return _manifest_tools(enabled, os.environ.get(MCP_STAGE_ENV, "").strip(),
                           MCP_TOOLS_ENV)


def _manifest_tools(enabled, stage: str, env_name: str = "METASCIENCE_MCP_TOOLS"):
    """The role's surface narrowed to a pipeline's toolset -- FAIL CLOSED.

    The role-only filter below fails open (an unset or unknown stage serves
    everything) because an operator's own server must keep working. A
    MANIFEST is a pipeline's explicit claim about what this agent may call, so
    every way it can be wrong refuses instead: no stage, an unknown stage, a
    name the registry does not know, or a set that leaves nothing to serve.
    It only ever narrows -- an off-role name cannot widen the role.
    """
    if not stage:
        raise ToolManifestError(
            f"{env_name} was supplied without {MCP_STAGE_ENV}; refusing to "
            "guess which role's surface it narrows")
    from .registry import stage_tools
    role = set(stage_tools(stage))
    if not role:
        raise ToolManifestError(f"unknown role {stage!r} for a tool manifest")
    known = {t.name for t in ALL_TOOLS}
    unknown = sorted(set(enabled) - known)
    if unknown:
        raise ToolManifestError(f"tool manifest names unknown tool(s) {unknown}")
    served = [t for t in ALL_TOOLS if t.name in role and t.name in enabled]
    if not served:
        raise ToolManifestError(
            f"tool manifest leaves nothing to serve on the {stage} role")
    return served


def _role_filtered_tools():
    stage = os.environ.get(MCP_STAGE_ENV, "").strip()
    if not stage:
        return list(ALL_TOOLS)
    try:
        from .registry import stage_tools
        allowed = set(stage_tools(stage))
    except Exception:  # noqa: BLE001 -- an unknown stage must not kill the server
        return list(ALL_TOOLS)
    if not allowed:
        return list(ALL_TOOLS)
    return [t for t in ALL_TOOLS if t.name in allowed]


_SERVED_TOOLS = _stage_filtered_tools()
_TOOLS_BY_NAME = {t.name: t for t in _SERVED_TOOLS}

#: Default per-call deadline. A cache-hit extract_pdf is milliseconds; this
#: exists so RapidOCR / a wedged native call fails the TOOL rather than the
#: whole stage (measured: a supplement OCR hang sat through the 1800 s
#: stage cap). Override with METASCIENCE_MCP_TOOL_TIMEOUT.
MCP_TOOL_TIMEOUT_DEFAULT = 60.0

#: `tool_access: mcp_brief` (docs/specs/tool_access.md): each description is
#: cut to its first sentence and `describe_tool` serves the rest on demand.
#: Absent for every default run, so its config bytes are unchanged.
BRIEF_ENV = "METASCIENCE_MCP_BRIEF"
DESCRIBE_TOOL = "describe_tool"


def _brief() -> bool:
    return os.environ.get(BRIEF_ENV, "").strip() == "1"


def _describe_tool_decl() -> mcp_types.Tool:
    return mcp_types.Tool(
        name=DESCRIBE_TOOL,
        description=("The full instructions for one forensic tool: its complete "
                     "description, parameters with their guards, assumptions and "
                     "procedure guidance. The tool list carries one-line "
                     "summaries; call this before you first use a tool."),
        inputSchema={"type": "object",
                     "properties": {"name": {"type": "string",
                                             "description": "The tool's name."}},
                     "required": ["name"]})


def _mcp_tool_timeout() -> float:
    raw = os.environ.get("METASCIENCE_MCP_TOOL_TIMEOUT", "")
    try:
        t = float(raw) if raw.strip() else MCP_TOOL_TIMEOUT_DEFAULT
    except ValueError:
        return MCP_TOOL_TIMEOUT_DEFAULT
    return t if t > 0 else MCP_TOOL_TIMEOUT_DEFAULT


@server.list_tools()
async def _list_tools() -> list[mcp_types.Tool]:
    brief = _brief()
    if brief:
        from .registry import BY_NAME
    tools = [
        mcp_types.Tool(
            name=t.name,
            description=BY_NAME[t.name].brief if brief else t.description,
            inputSchema=_to_json_schema(t.input_schema),
        )
        for t in _SERVED_TOOLS
    ]
    return tools + ([_describe_tool_decl()] if brief else [])


def _answer(name: str, arguments: dict, text: str) -> list[mcp_types.TextContent]:
    """A refusal the server composed itself is still an answer to a call, so
    it gets a receipt like any tool result."""
    from . import receipts
    receipts.record(name, arguments, text)
    return [mcp_types.TextContent(type="text", text=text)]


@server.call_tool()
async def _call_tool(name: str, arguments: dict) -> list[mcp_types.TextContent]:
    if name == DESCRIBE_TOOL and _brief():
        wanted = str((arguments or {}).get("name") or "")
        if wanted in _TOOLS_BY_NAME:
            from .tool_cli import describe_text
            text = describe_text(wanted)
        else:
            text = json.dumps({"error": f"no tool named {wanted!r} on this surface",
                               "severity": "indeterminate"})
        return [mcp_types.TextContent(type="text", text=text)]
    tool = _TOOLS_BY_NAME.get(name)
    if tool is None:
        # Named refusal, not a bare unknown: a call for a tool that exists
        # in the registry but not on THIS stage's surface is a role breach
        # attempt and the message says so (it lands in the ledger).
        stage = os.environ.get(MCP_STAGE_ENV, "").strip()
        known_offrole = any(t.name == name for t in ALL_TOOLS)
        if known_offrole and stage:
            return [mcp_types.TextContent(type="text", text=json.dumps({
                "error": (f"tool '{name}' is not on the {stage} role's "
                          "surface; it exists but this agent may not call "
                          "it"),
                "refusal": "off_role_tool",
                "severity": "indeterminate"}))]
        return [mcp_types.TextContent(type="text", text=json.dumps({"error": f"unknown tool: {name}"}))]
    try:
        result = await asyncio.wait_for(
            tool.handler(arguments or {}), timeout=_mcp_tool_timeout())
    except asyncio.TimeoutError:
        limit = _mcp_tool_timeout()
        payload = {
            "error": f"{name} timed out after {limit:.0f}s",
            "severity": "indeterminate",
            "tool": name,
            "arguments": arguments,
            "note": (
                "The tool did not return within the per-call deadline. This "
                "is a fact about this run (a hung native decoder, a scan "
                "OCR, a stall), not about the paper. Retry with a narrower "
                "input or raise METASCIENCE_MCP_TOOL_TIMEOUT."
            ),
        }
        return _answer(name, arguments, json.dumps(payload, default=str))
    except Exception as exc:  # noqa: BLE001 — a tool crash must not kill the turn
        payload = {
            "error": f"{type(exc).__name__}: {exc}",
            "severity": "indeterminate",
            "tool": name,
            "arguments": arguments,
            "note": (
                "The tool raised instead of returning a result. Check the "
                "inputs (e.g. n too small, zero SD, malformed table) and "
                "retry with corrected arguments if appropriate."
            ),
        }
        return _answer(name, arguments, json.dumps(payload, default=str))
    # The handler returns {"content": [{"type": "text", "text": "..."}], ...}
    content = result.get("content") if isinstance(result, dict) else None
    out = []
    if isinstance(content, list) and content:
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                out.append(mcp_types.TextContent(type="text", text=str(item.get("text", ""))))
    if not out:
        # Fallback: serialise whatever we got
        out = [mcp_types.TextContent(type="text", text=json.dumps(result, default=str))]
    # The tool side's own record of this answer (receipts.py). Written after
    # the result exists and never raising, so it cannot change the answer.
    from . import receipts
    receipts.record(name, arguments, "".join(t.text for t in out))
    return out


def _protocol_stdout():
    """Stdout for the JSON-RPC stream ONLY; everything else goes to stderr.

    MEASURED 2026-10-18 (apple_cider on --backend antigravity): the statcheck
    package prints "Extracting statistics from text" to stdout on every call.
    Claude's MCP client skips a non-JSON line; agy's does not -- it reported
    `invalid character 'E' looking for beginning of value`, marked the server
    failed, and every later forensic call in the stage was refused (csf_test
    among them). So the protocol gets a private duplicate of fd 1, and fd 1
    itself (and `sys.stdout`) is pointed at stderr: a print from any tool, a
    native library or a child process can no longer reach the protocol.
    """
    import sys
    from io import TextIOWrapper

    import anyio
    sys.stdout.flush()
    proto = os.fdopen(os.dup(1), "wb", buffering=0)
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    return anyio.wrap_file(TextIOWrapper(proto, encoding="utf-8",
                                         write_through=True))


async def _main() -> None:
    async with stdio_server(stdout=_protocol_stdout()) as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(_main())
