"""The `power_check` tool family: required_n, verify_power_analysis.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `forensic_metascience_ai_toolkit.tools.power_check`.
"""

from __future__ import annotations

from ...registry import (
    REQUIRED,
    STAGE1,
    STAGE2,
    Param,
    ToolSpec,
)
from ...tools.power_check import required_n, verify_power_analysis
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="required_n",
        fn=required_n,
        description=DESCRIPTIONS["required_n"],
        params=(
            Param("test_type", str, REQUIRED),
            Param("effect_size", float, REQUIRED),
            Param("alpha", float, 0.05),
            Param("power", float, 0.8),
            Param("tails", int, 2),
            Param("groups", int, 2),
            Param("df", int, None),
            Param("actual_n", int, None,
                  help="The sample size the study ACTUALLY used, if you know it. "
                       "Supplying it adds the `design_sensitivity` comparison; "
                       "omitting it leaves the answer a bare sample-size calculation."),
        ),
        # OFFERED 2026-08-16 (Greg): "make required_n a proper check so the
        # model can call it." It now returns a severity from the ladder and
        # carries a source quote, which is what the invariant required; with
        # `actual_n` it compares the design a paper HAD against the design its
        # own reported effect needs. Withholding it cost a real run: the sweep
        # on PNAS 0801268105 reached for it three times and was refused.
        stages=frozenset({STAGE1, STAGE2}),
        legacy_verb="required-n",
    ),
    ToolSpec(
        name="verify_power_analysis",
        fn=verify_power_analysis,
        description=DESCRIPTIONS["verify_power_analysis"],
        params=(
            Param("test_type", str, REQUIRED, guard=True),
            Param("effect_size", float, None),
            Param("alpha", float, None),
            Param("target_power", float, None),
            Param("n_reported", int, None),
            Param("n_reported_is_per_group", bool, False),
            Param("tails", int, None, guard=True,
                  help="1 or 2 AS STATED BY THE PAPER. Leave unset when the paper does "
                       "not state its tail convention: the check then tries both and "
                       "refuses to accuse when the one-tailed reading reconciles. "
                       "Stating it restores full sensitivity."),
            Param("groups", int, 2),
            Param("df", int, None),
            Param("allows_attrition_inflation", bool, True),
            Param("allocation_ratio", float, 1.0, guard=True,
                  help="Arm allocation ratio. Anything other than 1.0 is REFUSED: the "
                       "recomputation is 1:1, and grading a k:1 design against it can "
                       "accuse a correct calculation."),
        ),
        stages=frozenset({STAGE1}),
        legacy_verb="power-check",
    ),
)
