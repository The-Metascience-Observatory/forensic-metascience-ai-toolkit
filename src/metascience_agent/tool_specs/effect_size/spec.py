"""The `effect_size` tool family: check_effect_plausibility, paired_d_interval.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `metascience_agent.tools.effect_size`.
"""

from __future__ import annotations

from ...registry import (
    EVIDENCE_DESCRIPTIVE,
    SCIENCE_AGENT,
    STAGE1,
    STAGE2,
    Param,
    ToolSpec,
)
from ...tools.effect_size import check_effect_plausibility, paired_d_interval
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="check_effect_plausibility",
        fn=check_effect_plausibility,
        description=DESCRIPTIONS["check_effect_plausibility"],
        params=(
            Param("d", float, None),
            Param("reported_d", float, None),
            Param("field", str, None, guard=True),
            Param("mean1", float, None),
            Param("sd1", float, None),
            Param("n1", int, None),
            Param("mean2", float, None),
            Param("sd2", float, None),
            Param("n2", int, None),
            Param("design", str, None),
            Param("provenance", str, "printed_text", guard=True),
        ),
        # + SCIENCE_AGENT (2026-08-21): implausibly large effects need field
        # norms -- the science analyst's beat -- and the v1.2.0 apple_cider
        # run showed neither analyst ran this tool once it left the old
        # sweep's habit loop; the guard-bearing tool goes where the norms
        # knowledge lives.
        stages=frozenset({STAGE1, STAGE2, SCIENCE_AGENT}),
        legacy_verb="effect-size",
    ),
    ToolSpec(
        name="paired_d_interval",
        fn=paired_d_interval,
        description=DESCRIPTIONS["paired_d_interval"],
        params=(
            Param("dz", float, None),
            Param("t", float, None),
            Param("n", int, None),
            Param("r", float, None),
        ),
        evidence=EVIDENCE_DESCRIPTIVE,
        stages=frozenset({STAGE1, STAGE2, SCIENCE_AGENT}),
        legacy_verb="paired-d-interval",
    ),
)
