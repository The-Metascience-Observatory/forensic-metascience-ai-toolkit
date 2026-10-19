"""The `table1_dispersion` tool family: bayesian_table1_dispersion.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `metascience_agent.tools.table1_dispersion`.
"""

from __future__ import annotations

from ...registry import (
    REQUIRED,
    STAGE1,
    STAGE2,
    Param,
    ToolSpec,
)
from ...tools.csf import DEFAULT_RHO_GRID
from ...tools.table1_dispersion import table1_dispersion
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="bayesian_table1_dispersion",
        fn=table1_dispersion,
        description=DESCRIPTIONS["bayesian_table1_dispersion"],
        params=(
            Param("rows", list, REQUIRED),
            Param("num_bootstrap", int, 1000),
            # WITHHELD, for exactly the reason `rho_grid` is. `ci_level` sets the
            # accusation threshold directly -- lowering it narrows the CI on tau
            # and makes `ci_lo > 2` easier to clear -- so exposing it hands the
            # model a dial it can turn until a finding appears. Its predecessor
            # `bootstrap_ci_level` WAS exposed; that was an oversight, not a
            # decision. Operators still set it from the CLI (`--ci`).
            Param("ci_level", float, 0.95, withheld=True),
            Param("seed", int, 0),
            Param("design", str, None, guard=True),
            Param("correlation", float, None),
            # Withheld for the same reason as csf_test's: a model that can shrink
            # the grid can tune it until an inconvenient result clears.
            Param("rho_grid", tuple, DEFAULT_RHO_GRID, withheld=True),
        ),
        stages=frozenset({STAGE1, STAGE2}),
        legacy_verb="table1-dispersion",
    ),
)
