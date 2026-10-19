"""The `chi_squared` tool family: recalc_chi_squared.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `metascience_agent.tools.chi_squared`.
"""

from __future__ import annotations

from ...registry import (
    REQUIRED,
    STAGE1,
    STAGE2,
    Param,
    ToolSpec,
)
from ...tools.chi_squared import recalc_chi_squared
from ...tools.ttest import P_ADJUSTMENT_HELP, P_RELATION_HELP
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="recalc_chi_squared",
        fn=recalc_chi_squared,
        description=DESCRIPTIONS["recalc_chi_squared"],
        params=(
            Param("observed", list, REQUIRED),
            Param("reported_chi2", float, None),
            Param("reported_p", float, None),
            Param("use_yates", bool, False),
            Param("decimals_p", int, None,
                  help="Printed decimals of reported_p, read from the literal."),
            Param("p_relation", str, None, guard=True, help=P_RELATION_HELP),
            Param("p_adjustment", str, None, guard=True, help=P_ADJUSTMENT_HELP),
            Param("paired", bool, False,
                  help="The 2x2 is a PAIRED agreement table (McNemar), not an "
                       "independence table. Makes McNemar the headline test; "
                       "it is computed and matched against either way."),
            Param("sampling", str, "simple_random", guard=True),
        ),
        stages=frozenset({STAGE1, STAGE2}),
        cli="chi2",
        cli_required_flags=frozenset(),
    ),
)
