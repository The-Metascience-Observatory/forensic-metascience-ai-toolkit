"""The `csf` tool family: csf_test.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `metascience_agent.tools.csf`.
"""

from __future__ import annotations

from ...registry import (
    REQUIRED,
    STAGE1,
    STAGE2,
    Param,
    ToolSpec,
)
from ...tools.csf import DEFAULT_RHO_GRID, csf_test
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="csf_test",
        fn=csf_test,
        description=DESCRIPTIONS["csf_test"],
        params=(
            Param("p_values", list, REQUIRED),
            Param("method", str, 'stouffer'),
            Param("design", str, None, guard=True),
            Param("correlation", float, None),
            # WITHHELD: correlation grid; a model that can shrink it can tune CSF until the result clears significance
            Param("rho_grid", tuple, DEFAULT_RHO_GRID, withheld=True),
        ),
        stages=frozenset({STAGE1, STAGE2}),
        legacy_verb="csf",
    ),
)
