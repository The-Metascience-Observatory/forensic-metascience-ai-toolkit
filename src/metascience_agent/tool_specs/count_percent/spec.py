"""The `count_percent` tool family: check_count_percent.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `metascience_agent.tools.count_percent`.
"""

from __future__ import annotations

from ...registry import (
    REQUIRED,
    SCIENCE_AGENT,
    STAGE1,
    STAGE2,
    Param,
    ToolSpec,
)
from ...tools.count_percent import check_count_percent
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="check_count_percent",
        fn=check_count_percent,
        description=DESCRIPTIONS["check_count_percent"],
        params=(
            Param("count", int, REQUIRED),
            Param("percentage", float, REQUIRED),
            Param("n", int, REQUIRED),
            Param("decimals", int, None),
            Param("source_quote", str, None),
            Param("source_locator", str, None),
        ),
        stages=frozenset({STAGE1, STAGE2, SCIENCE_AGENT}),
        cli="check-count-percent",
        cli_required_flags=frozenset(),
    ),
)
