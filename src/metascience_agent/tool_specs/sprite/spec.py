"""The `sprite` tool family: sprite_reconstruct.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `metascience_agent.tools.sprite`.
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
from ...tools.sprite import sprite_reconstruct
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="sprite_reconstruct",
        fn=sprite_reconstruct,
        description=DESCRIPTIONS["sprite_reconstruct"],
        params=(
            Param("mean", float, REQUIRED, exact=True),
            Param("sd", float, REQUIRED, exact=True),
            Param("n", int, REQUIRED, exact=True),
            Param("scale_min", int, 1),
            Param("scale_max", int, 7),
            Param("num_samples", int, 100),
            Param("decimals_mean", int, None),
            Param("decimals_sd", int, None),
            Param("data_type", str, 'unknown', guard=True),
            Param("discreteness_source", str, 'assumed', guard=True,
                  help=DISCRETENESS_SOURCE_HELP),
            # WITHHELD: search budget; a model that can raise it can search until SPRITE stops saying search_exhausted
            Param("max_iterations", int, 10000, withheld=True),
            # RECORDED, not merely defaulted. GREG, 2026-08-11: "insofar as we
            # do simulations, we must supply the initial seed for the purposes
            # of reproducibility." A fixed default makes the search
            # deterministic; declaring it a Param is what puts the actual seed
            # into the call ledger, so a reader re-running the tool a year from
            # now can reproduce THIS result rather than a similar one. The other
            # simulating tools (both RIVETS, the Carlisle dispersion test,
            # check_proportion_from_normal) already declared theirs; SPRITE --
            # the one whose negative verdict can reach `impossible` -- did not.
            Param("seed", int, 20260811,
                  help="RNG seed for the reconstruction search. Vary it to test "
                       "whether a `no solution` result is robust; the analytic "
                       "parity screen that PROVES infeasibility does not use it."),
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
        legacy_verb="sprite",
    ),
)
