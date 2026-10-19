"""The `r_wrappers` tool family: r_grim_ground_truth, r_sprite_ground_truth, statcheck.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `forensic_metascience_ai_toolkit.tools.r_wrappers`.
"""

from __future__ import annotations

from ...registry import (
    REQUIRED,
    STAGE1,
    STAGE2,
    Param,
    ToolSpec,
    _statcheck_adapter,
)
from ...tools.r_wrappers import python_statcheck_text, r_grim, r_sprite
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="r_grim_ground_truth",
        fn=r_grim,
        description=DESCRIPTIONS["r_grim_ground_truth"],
        params=(
            Param("mean", float, REQUIRED),
            Param("n", int, REQUIRED),
            Param("items", int, 1),
            Param("decimals", int, 2),
            Param("percentage", bool, False,
                  help="`mean` is a percentage share (100*k/n), not a mean. "
                       "Set this when cross-checking grim_percentage."),
        ),
        stages=frozenset({STAGE2}),
    ),
    ToolSpec(
        name="r_sprite_ground_truth",
        fn=r_sprite,
        description=DESCRIPTIONS["r_sprite_ground_truth"],
        params=(
            Param("mean", float, REQUIRED),
            Param("sd", float, REQUIRED),
            Param("n", int, REQUIRED),
            Param("scale_min", int, 1),
            Param("scale_max", int, 7),
            Param("num_samples", int, 10),
            Param("decimals", int, 2),
            # Recorded, not merely defaulted -- rsprite2's search is Monte
            # Carlo and this tool is the referee the Python SPRITE is judged
            # against. See the seed note in `r_wrappers.r_sprite`.
            Param("seed", int, 20260811,
                  help="RNG seed passed to R as set.seed(). Vary it to test whether a no-solution result is robust."),
        ),
        stages=frozenset({STAGE1, STAGE2}),
    ),
    ToolSpec(
        name="statcheck",
        fn=python_statcheck_text,
        description=DESCRIPTIONS["statcheck"],
        params=(
            Param("pdf_path", str, REQUIRED),
            Param("text", str, REQUIRED),
        ),
        stages=frozenset({STAGE1, STAGE2}),
        legacy_verb="statcheck",
        adapter=_statcheck_adapter,
    ),
)
