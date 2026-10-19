"""The `ratio` tool family: check_ratio.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `metascience_agent.tools.ratio`.
"""

from __future__ import annotations

from ...registry import (
    PROVENANCE_HELP,
    REQUIRED,
    SCIENCE_AGENT,
    STAGE1,
    STAGE2,
    Param,
    ToolSpec,
)
from ...tools.ratio import check_ratio
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="check_ratio",
        fn=check_ratio,
        description=DESCRIPTIONS["check_ratio"],
        params=(
            Param("numerator", float, REQUIRED, exact=True),
            Param("denominator", float, REQUIRED, exact=True),
            Param("reported_ratio", float, REQUIRED, exact=True),
            Param("decimals_numerator", int, None, guard=True,
                  help="Printed decimals of the numerator, read from the literal. "
                       "Without it the check refuses."),
            Param("decimals_denominator", int, None, guard=True,
                  help="Printed decimals of the denominator, read from the literal. "
                       "Without it the check refuses."),
            Param("decimals_ratio", int, None, guard=True,
                  help="Printed decimals of the reported ratio, read from the literal. "
                       "Without it the check refuses."),
            Param("description", str, 'ratio'),
            # Gate metadata, not a tool argument. This check tests whether a
            # printed quotient reproduces to its last printed digit, and a
            # value measured off a chart has no last printed digit -- so a
            # measured provenance makes `ToolSpec.call` refuse rather than
            # judge.
            Param("provenance", str, "printed_text", guard=True, meta=True,
                  help=PROVENANCE_HELP),
        ),
        stages=frozenset({STAGE1, STAGE2, SCIENCE_AGENT}),
        cli="check-ratio",
        cli_required_flags=frozenset(
            {"decimals_numerator", "decimals_denominator", "decimals_ratio"}),
    ),
)
