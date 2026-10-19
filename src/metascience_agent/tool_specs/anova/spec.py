"""The `anova` tool family: recalc_anova, recalc_f_to_p.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `metascience_agent.tools.anova`.
"""

from __future__ import annotations

from ...registry import (
    REQUIRED,
    STAGE1,
    STAGE2,
    Param,
    ToolSpec,
)
from ...tools.anova import recalc_f_to_p, recalc_one_way_anova
from ...tools.ttest import P_ADJUSTMENT_HELP, P_RELATION_HELP, TEST_CONFIRMED_HELP
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="recalc_anova",
        fn=recalc_one_way_anova,
        description=DESCRIPTIONS["recalc_anova"],
        params=(
            Param("means", list, REQUIRED),
            Param("sds", list, REQUIRED),
            Param("ns", list, REQUIRED),
            Param("reported_f", float, None),
            Param("reported_p", float, None),
            Param("decimals_p", int, None,
                  help="Printed decimals of reported_p, read from the literal."),
            Param("p_relation", str, None, guard=True, help=P_RELATION_HELP),
            Param("p_adjustment", str, None, guard=True, help=P_ADJUSTMENT_HELP),
            Param("test_confirmed", bool, False, help=TEST_CONFIRMED_HELP),
            Param("decimals_mean", int, None,
                  help="Printed decimals of the group means, read from the table."),
            Param("decimals_sd", int, None,
                  help="Printed decimals of the group SDs, read from the table."),
            Param("sampling", str, "simple_random", guard=True),
        ),
        stages=frozenset({STAGE1, STAGE2}),
        cli="anova",
        cli_required_flags=frozenset(),
    ),
    ToolSpec(
        name="recalc_f_to_p",
        fn=recalc_f_to_p,
        description=DESCRIPTIONS["recalc_f_to_p"],
        params=(
            Param("f_value", float, REQUIRED),
            Param("df1", int, REQUIRED),
            Param("df2", int, None,
                  help="ONLY if the paper prints it; omit when unstated and "
                       "the tool sweeps every df2 instead. An inferred df2 "
                       "is an assumed bound and has produced a false "
                       "positive."),
            Param("reported_p", float, None),
            Param("decimals_p", int, None,
                  help="Printed decimals of reported_p, read from the literal."),
            Param("p_relation", str, None, guard=True, help=P_RELATION_HELP),
            Param("p_adjustment", str, None, guard=True, help=P_ADJUSTMENT_HELP),
            Param("decimals_f", int, None,
                  help="Printed decimals of the reported F, read from the literal."),
        ),
        stages=frozenset({STAGE1, STAGE2}),
        cli="f-to-p",
        cli_required_flags=frozenset(),
    ),
)
