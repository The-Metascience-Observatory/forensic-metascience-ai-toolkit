"""The `ttest` tool family: recalc_independent_t, recalc_within_subjects_t.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `metascience_agent.tools.ttest`.
"""

from __future__ import annotations

from ...registry import (
    REQUIRED,
    STAGE1,
    STAGE2,
    Param,
    ToolSpec,
)
from ...tools.ttest import recalc_independent_t, recalc_within_subjects_t
from ...tools.ttest import P_ADJUSTMENT_HELP, P_RELATION_HELP, TEST_CONFIRMED_HELP
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="recalc_independent_t",
        fn=recalc_independent_t,
        description=DESCRIPTIONS["recalc_independent_t"],
        params=(
            Param("mean1", float, REQUIRED),
            Param("sd1", float, REQUIRED),
            Param("n1", int, REQUIRED),
            Param("mean2", float, REQUIRED),
            Param("sd2", float, REQUIRED),
            Param("n2", int, REQUIRED),
            Param("reported_p", float, None),
            Param("reported_t", float, None),
            Param("use_welch", bool, None,
                  help="True=Welch, False=Student (pooled). Omit when the paper "
                       "does not say; both standard tests are then accepted."),
            Param("decimals_p", int, None,
                  help="Printed decimals of reported_p, read from the literal."),
            Param("p_relation", str, None, guard=True, help=P_RELATION_HELP),
            Param("p_adjustment", str, None, guard=True, help=P_ADJUSTMENT_HELP),
            Param("test_confirmed", bool, False, help=TEST_CONFIRMED_HELP),
            Param("p_tail", str, 'unknown',
                  help="'two'|'one'|'unknown': tail convention of reported_p. "
                       "Omit when the paper does not say."),
            Param("decimals_mean", int, None,
                  help="Printed decimals of the means, read from the table."),
            Param("decimals_sd", int, None,
                  help="Printed decimals of the SDs, read from the table."),
            Param("sampling", str, "simple_random", guard=True),
        ),
        stages=frozenset({STAGE1, STAGE2}),
        cli="ttest",
        cli_required_flags=frozenset(),
    ),
    ToolSpec(
        name="recalc_within_subjects_t",
        fn=recalc_within_subjects_t,
        description=DESCRIPTIONS["recalc_within_subjects_t"],
        params=(
            Param("mean_pre", float, REQUIRED),
            Param("sd_pre", float, REQUIRED),
            Param("mean_post", float, REQUIRED),
            Param("sd_post", float, REQUIRED),
            Param("n", int, REQUIRED),
            Param("reported_p", str, REQUIRED),
            Param("p_is_threshold", bool, False),
            Param("p_tail", str, 'two'),
            Param("decimals_mean", int, None,
                  help="Printed decimals of the means, read from the table."),
            Param("decimals_sd", int, None,
                  help="Printed decimals of the SDs, read from the table."),
            Param("decimals_p", int, None,
                  help="Printed decimals of reported_p, read from the literal."),
            Param("sampling", str, "simple_random", guard=True),
        ),
        stages=frozenset({STAGE1, STAGE2}),
        cli=None,
        cli_required_flags=frozenset(),
    ),
)
