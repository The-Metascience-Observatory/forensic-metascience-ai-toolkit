"""The `regression` tool family: check_regression, check_regression_batch.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `metascience_agent.tools.regression`.
"""

from __future__ import annotations

from ...registry import (
    REQUIRED,
    STAGE1,
    Param,
    ToolSpec,
)
from ...tools.regression import check_regression, check_regression_batch
from ...tools.ttest import ONE_TAILED_STATED_HELP, P_ADJUSTMENT_HELP, P_RELATION_HELP
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="check_regression",
        fn=check_regression,
        description=DESCRIPTIONS["check_regression"],
        params=(
            Param("b", float, REQUIRED),
            Param("se", float, REQUIRED),
            Param("reported_t", float, None),
            Param("reported_p", float, None),
            Param("df", int, None),
            Param("decimals_b", int, None,
                  help="Printed decimals of b, read from the literal."),
            Param("decimals_se", int, None,
                  help="Printed decimals of se, read from the literal."),
            Param("decimals_t", int, None,
                  help="Printed decimals of reported_t, read from the literal."),
            Param("decimals_p", int, None,
                  help="Printed decimals of reported_p, read from the literal."),
            Param("p_is_threshold", bool, None, guard=True,
                  help="TRUE when the paper printed a BOUND ('P < .001') rather than "
                       "an exact p. The float cannot carry the difference."),
            Param("p_relation", str, None, guard=True, help=P_RELATION_HELP),
            Param("p_adjustment", str, None, guard=True, help=P_ADJUSTMENT_HELP),
            Param("one_tailed_stated", bool, False, help=ONE_TAILED_STATED_HELP),
        ),
        stages=frozenset({STAGE1}),
    ),
    ToolSpec(
        name="check_regression_batch",
        fn=check_regression_batch,
        description=DESCRIPTIONS["check_regression_batch"],
        params=(Param("rows", list, REQUIRED),),
        stages=frozenset({STAGE1}),
        legacy_verb="regression-batch",
    ),
)
