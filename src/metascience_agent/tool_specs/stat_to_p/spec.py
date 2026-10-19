"""The `stat_to_p` tool family: recalc_stat_to_p.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `metascience_agent.tools.stat_to_p`.
"""

from __future__ import annotations

from ...registry import (
    REQUIRED,
    STAGE1,
    STAGE2,
    Param,
    ToolSpec,
)
from ...tools.stat_to_p import recalc_stat_to_p
from ...tools.ttest import ONE_TAILED_STATED_HELP, P_ADJUSTMENT_HELP, P_RELATION_HELP
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="recalc_stat_to_p",
        fn=recalc_stat_to_p,
        description=DESCRIPTIONS["recalc_stat_to_p"],
        params=(
            Param("statistic", float, REQUIRED),
            Param("kind", str, REQUIRED),
            Param("df", float, None),
            Param("df2", float, None),
            Param("n", int, None),
            Param("reported_p", float, None),
            Param("decimals_stat", int, None),
            Param("decimals_p", int, None),
            Param("p_relation", str, None, guard=True, help=P_RELATION_HELP),
            Param("p_adjustment", str, None, guard=True, help=P_ADJUSTMENT_HELP),
            Param("one_tailed_stated", bool, False, help=ONE_TAILED_STATED_HELP),
            Param("tails", int, 2),
            Param("source_quote", str, None),
            Param("source_locator", str, None),
            Param("sampling", str, "simple_random", guard=True),
            Param("df_min", float, None),
            Param("df_max", float, None),
        ),
        stages=frozenset({STAGE1, STAGE2}),
        cli="stat-to-p",
        cli_required_flags=frozenset(),
    ),
)
