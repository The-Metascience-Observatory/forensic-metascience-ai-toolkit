"""The `check_table` tool family: check_table.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `metascience_agent.dispatch`.
"""

from __future__ import annotations

from ...dispatch import check_table
from ...registry import (
    REQUIRED,
    STAGE1,
    Param,
    ToolSpec,
)
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="check_table",
        fn=check_table,
        description=DESCRIPTIONS["check_table"],
        params=(
            Param("cells", list, REQUIRED),
            Param("variables", list, None, guard=True),
            Param("bindings", dict, None, guard=True),
            Param("provenance", str, "printed_table", guard=True),
        ),
        stages=frozenset({STAGE1}),
        legacy_verb="check-table",
    ),
)
