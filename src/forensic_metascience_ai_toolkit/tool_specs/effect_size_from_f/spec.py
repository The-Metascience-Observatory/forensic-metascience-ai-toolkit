"""The `effect_size_from_f` tool family: effect_size_from_f.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `forensic_metascience_ai_toolkit.tools.effect_size_from_f`.
"""

from __future__ import annotations

from ...registry import (
    PROVENANCE_HELP,
    REQUIRED,
    STAGE1,
    STAGE2,
    Param,
    ToolSpec,
)
from ...tools.effect_size_from_f import effect_size_from_f
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="effect_size_from_f",
        fn=effect_size_from_f,
        description=DESCRIPTIONS["effect_size_from_f"],
        params=(
            Param("f_value", float, REQUIRED, exact=True),
            Param("df1", int, REQUIRED, exact=True),
            Param("df2", int, REQUIRED, exact=True),
            Param("reported_effect_size", float, None, exact=True),
            Param("measure", str, "partial_eta_squared",
                  help="What the paper called it. partial_eta_squared | "
                       "cohens_f are recoverable; eta_squared, "
                       "generalized_eta_squared, omega_squared and r_squared "
                       "are refused by name."),
            Param("decimals_f", int, None),
            Param("decimals_effect_size", int, None),
            # This check reads BOTH numbers to their last printed digit, so a
            # value measured off a chart has no business here -- same gate the
            # rest of the exact family carries.
            Param("uncertainty", dict, None),
            Param("provenance", str, "printed_text", guard=True, meta=True,
                  help=PROVENANCE_HELP),
            Param("source_quote", str, None, meta=True),
            Param("source_locator", str, None, meta=True),
        ),
        stages=frozenset({STAGE1, STAGE2}),
        legacy_verb="effect-size-from-f",
    ),
)
