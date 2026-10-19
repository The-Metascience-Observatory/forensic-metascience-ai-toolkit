"""The `stalt` tool family: stalt_check.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `metascience_agent.tools.stalt`.
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
from ...tools.stalt import stalt_check
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="stalt_check",
        fn=stalt_check,
        description=DESCRIPTIONS["stalt_check"],
        params=(
            Param("calculated_p", float, REQUIRED, exact=True),
            Param("reported_threshold", str, '<0.05'),
            # Gate metadata, not a tool argument. Maps param -> sigma in DATA
            # UNITS, stamped by whatever extracted the value. Its presence on an
            # `exact` param makes ToolSpec.call() refuse: this check tests whether
            # a number is possible to its LAST PRINTED DIGIT, and a value measured
            # off a chart has no last printed digit.
            Param("uncertainty", dict, None),
            # The same three words `check_table` takes, on the direct call.
            # Gate metadata, not a tool argument: `ToolSpec.call` turns a
            # measured provenance into an `uncertainty` stamp on every exact
            # param and the gate above then refuses. Without it the per-cell
            # path judged figure-read numbers the table path refuses -- and
            # the per-cell path is the only one stage 2 has.
            Param("provenance", str, "printed_text", guard=True, meta=True,
                  help=PROVENANCE_HELP),
        ),
        stages=frozenset({STAGE1, STAGE2}),
        cli="stalt",
        cli_required_flags=frozenset(),
    ),
)
