"""The `se_sd` tool family: check_sd_or_se.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `forensic_metascience_ai_toolkit.tools.se_sd`.
"""

from __future__ import annotations

from ...registry import (
    REQUIRED,
    STAGE1,
    Param,
    ToolSpec,
    _sd_or_se_adapter,
)
from ...tools.se_sd import check_sd_or_se
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="check_sd_or_se",
        fn=check_sd_or_se,
        description=DESCRIPTIONS["check_sd_or_se"],
        params=(
            Param("reported_value", float, REQUIRED),
            Param("n", int, REQUIRED),
            Param("reported_as", str, 'unknown'),
            Param("plausible_sd_max", float, None),
            Param("variable_range_min", float, None),
            Param("variable_range_max", float, None),
            Param("decimals", int, None,
                  help="Printed decimals of reported_value, read from the literal."),
            Param("bound_source", str, 'assumed', guard=True),
        ),
        stages=frozenset({STAGE1}),
        legacy_verb="sd-or-se",
        adapter=_sd_or_se_adapter,
    ),
)
