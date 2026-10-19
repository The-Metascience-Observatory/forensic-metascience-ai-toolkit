"""The `heuristics` tool family: flag_round_n, flag_uninformative_stat.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `metascience_agent.tools.heuristics`.
"""

from __future__ import annotations

from ...registry import (
    PROVENANCE_HELP,
    REQUIRED,
    STAGE1,
    Param,
    ToolSpec,
)
from ...tools.heuristics import flag_round_n, flag_uninformative_stat
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="flag_round_n",
        fn=flag_round_n,
        description=DESCRIPTIONS["flag_round_n"],
        params=(
            Param("ns", list, REQUIRED),
            Param("moderate_modulus", int, 50),
            Param("strong_modulus", int, 100),
        ),
        # OFFERED TO THE MODEL 2026-08-15 (Greg): "if they have the potential
        # to be useful, I want them." Was `frozenset()` -- reachable from the
        # CLI and never by the agent.
        stages=frozenset({STAGE1}),
        cli="flag-round-n",
        cli_required_flags=frozenset(),
    ),
    ToolSpec(
        name="flag_uninformative_stat",
        fn=flag_uninformative_stat,
        description=DESCRIPTIONS["flag_uninformative_stat"],
        params=(
            Param("means", list, REQUIRED, exact=True),
            Param("sds", list, REQUIRED, exact=True),
            Param("ns", list, REQUIRED, exact=True),
            Param("reported_p", float, None),
            Param("decimals_mean", int, 2),
            Param("decimals_sd", int, 2),
            Param("decimals_p", int, 3),
            Param("significance_threshold", float, 0.05),
            Param("p_range_warn", float, 0.5),
            Param("num_samples", int, 3000),
            Param("seed", int, 0),
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
        stages=frozenset({STAGE1}),
        cli="flag-uninformative",
        cli_required_flags=frozenset(),
    ),
)
