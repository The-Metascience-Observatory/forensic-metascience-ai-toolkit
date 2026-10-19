"""The `bounds` tool family: check_statistic_bounds.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `metascience_agent.tools.bounds`.
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
from ...tools.bounds import check_statistic_bounds
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="check_statistic_bounds",
        fn=check_statistic_bounds,
        description=DESCRIPTIONS["check_statistic_bounds"],
        params=(
            Param("value", float, REQUIRED),
            Param("measure", str, REQUIRED,
                  help="What the value is meant to be. Only measures with a bound "
                       "that follows from their DEFINITION are known; anything else "
                       "is refused rather than guessed at."),
            Param("extraction_verified", bool, False, guard=True,
                  help="Set true ONLY after re-reading the value in the paper itself "
                       "and confirming both the digits and the column. This is what "
                       "lifts the refusal to `impossible`."),
            Param("source_quote", str, None,
                  help="The passage the value was confirmed against."),
        ),
        stages=frozenset({STAGE1, STAGE2, SCIENCE_AGENT}),
        legacy_verb="check-bounds",
    ),
)
