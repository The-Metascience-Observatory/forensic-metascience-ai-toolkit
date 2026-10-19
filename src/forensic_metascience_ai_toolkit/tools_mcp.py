"""Forensic tools as MCP tools for the Claude Code SDK.

This module is now a thin builder. Every tool's name, description, schema,
implementation, guard parameters and stage membership are declared once in
`registry.py`; the SDK objects below are derived from that.

It used to be 38 hand-written wrappers of ~22 lines each, all the same shape,
kept in sync BY HAND with `agent.py`'s stage allowlists, `cli.py`, and the
prompt reference. Six defects came from that duplication, each one an omission
in a different place. See `registry.py` for the list.

Equivalence to the previous hand-written wrappers was verified tool-by-tool
before the switch: 52 argument cases across all 38 tools, byte-identical MCP
responses. `tests/test_registry_equivalence.py` keeps that honest.
"""

from typing import Any

from claude_agent_sdk import tool

from .registry import SPECS, ToolSpec, as_mcp_content


def _make_handler(spec: ToolSpec):
    """Build the async MCP handler for one spec.

    `spec` is bound as a default argument rather than captured by closure: a
    closure over the loop variable would give every handler the LAST spec, and
    the failure mode is tools that appear to work while returning another
    tool's results.
    """

    async def handler(args: dict[str, Any], _spec: ToolSpec = spec) -> dict[str, Any]:
        return as_mcp_content(_spec.call(args))

    handler.__name__ = f"{spec.name}_tool"
    handler.__doc__ = spec.description
    return handler


def _build(spec: ToolSpec):
    return tool(spec.name, spec.description, spec.schema())(_make_handler(spec))


#: Specs a model may be offered. `stages=frozenset()` is CLI-only by design
#: (`registry.CLI_ONLY`): the deterministic image and text tracks import the
#: Python functions directly. Serving those names over MCP is how a sweep
#: LLM launches a CV pipeline (or re-runs a free screen as a paid turn)
#: and then dumps empty findings that still read as a completed review.
MCP_SPECS = [spec for spec in SPECS if spec.stages]

ALL_TOOLS = [_build(spec) for spec in MCP_SPECS]

#: name -> SDK tool object, for callers that want one directly.
TOOLS_BY_NAME = {spec.name: t for spec, t in zip(MCP_SPECS, ALL_TOOLS)}
