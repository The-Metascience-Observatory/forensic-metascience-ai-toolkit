"""The `summation` tool family: check_summation, check_summation_batch.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `forensic_metascience_ai_toolkit.tools.summation`.
"""

from __future__ import annotations

from ...registry import (
    REQUIRED,
    SCIENCE_AGENT,
    STAGE1,
    Param,
    ToolSpec,
)
from ...tools.summation import check_summation, check_summation_batch
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="check_summation",
        fn=check_summation,
        description=DESCRIPTIONS["check_summation"],
        params=(
            Param("values", list, REQUIRED),
            Param("expected_sum", float, REQUIRED),
            Param("decimals", list, None, guard=True,
                  help="Printed decimals per addend, read from the literals. Without it "
                       "the check refuses."),
            Param("decimals_total", int, None,
                  help="Printed decimals of expected_sum."),
            Param("tolerance", float, None),
            Param("description", str, 'values'),
        ),
        stages=frozenset({STAGE1, SCIENCE_AGENT}),
        legacy_verb="summation",
    ),
    ToolSpec(
        name="check_summation_batch",
        fn=check_summation_batch,
        description=DESCRIPTIONS["check_summation_batch"],
        params=(
            Param("rows", list, REQUIRED),
            Param("tolerance", float, None),
        ),
        stages=frozenset({STAGE1, SCIENCE_AGENT}),
        legacy_verb="summation-batch",
    ),
)
