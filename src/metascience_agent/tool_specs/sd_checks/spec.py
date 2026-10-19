"""The `sd_checks` tool family: check_sd_range, grimmer_check.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `metascience_agent.tools.sd_checks`.
"""

from __future__ import annotations

from ...registry import (
    DISCRETENESS_SOURCE_HELP,
    PROVENANCE_HELP,
    REQUIRED,
    STAGE1,
    STAGE2,
    Param,
    ToolSpec,
)
from ...tools.sd_checks import check_sd_range, grimmer_test
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="check_sd_range",
        fn=check_sd_range,
        description=DESCRIPTIONS["check_sd_range"],
        params=(
            Param("sd", float, REQUIRED),
            Param("min_val", float, REQUIRED),
            Param("max_val", float, REQUIRED),
            Param("n", int, None),
            Param("decimals_sd", int, None,
                  help="Printed decimals of sd, read from the literal."),
            Param("bound_source", str, "assumed", guard=True,
                  help="stated | logically_necessary | assumed. The ceiling is derived "
                       "ENTIRELY from [min_val, max_val], so a violation of ASSUMED bounds "
                       "caps at highly_suspicious; only a range the paper states licenses "
                       "`impossible`."),
        ),
        # STILL NOT EXPOSED TO THE SWEEP, and that is now a separate decision
        # rather than a consequence of the missing guard. It was withheld
        # because the tool could reach `impossible` on a range nobody stated;
        # `bound_source` closes that, so the only remaining question is whether
        # a second dispersion check earns its place beside `check_sd_or_se` and
        # the SD-range rows `check_table` already runs. Left to a human; the
        # CLI path is complete either way.
        # OFFERED TO THE MODEL 2026-08-15 (Greg): "if they have the potential
        # to be useful, I want them." Was `frozenset()` -- reachable from the
        # CLI and never by the agent.
        stages=frozenset({STAGE1}),
        cli="sd-range",
        cli_required_flags=frozenset(),
    ),
    ToolSpec(
        name="grimmer_check",
        fn=grimmer_test,
        description=DESCRIPTIONS["grimmer_check"],
        params=(
            Param("mean", float, REQUIRED, exact=True),
            Param("sd", float, REQUIRED, exact=True),
            Param("n", int, REQUIRED, exact=True),
            Param("scale_min", int, 1),
            Param("scale_max", int, 7),
            Param("decimals", int, None, guard=True),
            Param("decimals_sd", int, None, guard=True),
            Param("data_type", str, 'unknown', guard=True),
            Param("discreteness_source", str, 'assumed', guard=True,
                  help=DISCRETENESS_SOURCE_HELP),
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
        cli="grimmer",
        cli_required_flags=frozenset({"data_type", "decimals_sd"}),
    ),
)
