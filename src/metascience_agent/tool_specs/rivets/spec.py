"""The `rivets` tool family: rivets_anova, rivets_independent_t.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `metascience_agent.tools.rivets`.
"""

from __future__ import annotations

from ...registry import (
    PROVENANCE_HELP,
    REQUIRED,
    STAGE1,
    Param,
    ToolSpec,
)
from ...tools.rivets import rivets_anova, rivets_independent_t
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="rivets_anova",
        fn=rivets_anova,
        description=DESCRIPTIONS["rivets_anova"],
        params=(
            Param("means", list, REQUIRED, exact=True),
            Param("sds", list, REQUIRED, exact=True),
            Param("ns", list, REQUIRED, exact=True),
            Param("reported_f", float, None),
            Param("reported_p", float, None),
            Param("decimals_mean", int, 2),
            Param("decimals_sd", int, 2),
            Param("decimals_f", int, 3),
            Param("decimals_p", int, 3),
            Param("p_is_threshold", bool, None, guard=True,
                  help="TRUE when the paper printed a BOUND ('p < .001') rather than an exact value. A bound is a one-sided claim, refuted only if even the smallest achievable p exceeds it; read as exact it is, in this module's own words, 'a large false-accusation class rather than a detection'. The literal cannot carry this -- `reported_p` is a float here -- so if the paper printed a bound you must say so."),
            Param("num_samples", int, 5000),
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
            Param("sampling", str, "simple_random", guard=True),
        ),
        stages=frozenset({STAGE1}),
        cli="rivets-anova",
        cli_required_flags=frozenset(),
    ),
    ToolSpec(
        name="rivets_independent_t",
        fn=rivets_independent_t,
        description=DESCRIPTIONS["rivets_independent_t"],
        params=(
            Param("mean1", float, REQUIRED, exact=True),
            Param("sd1", float, REQUIRED, exact=True),
            Param("n1", int, REQUIRED, exact=True),
            Param("mean2", float, REQUIRED, exact=True),
            Param("sd2", float, REQUIRED, exact=True),
            Param("n2", int, REQUIRED, exact=True),
            Param("reported_t", float, None),
            Param("reported_p", float, None),
            Param("decimals_mean", int, 2),
            Param("decimals_sd", int, 2),
            Param("decimals_t", int, 3),
            Param("decimals_p", int, 3),
            Param("use_welch", bool, None,
                  help="True=Welch, False=Student (pooled). Omit when the paper "
                       "does not say; both standard tests are then accepted."),
            Param("p_tail", str, 'unknown',
                  help="'two'|'one'|'unknown': tail convention of reported_p. "
                       "Omit when the paper does not say."),
            Param("p_is_threshold", bool, None, guard=True,
                  help="TRUE when the paper printed a BOUND ('p < .001') rather than an exact value. A bound is a one-sided claim, refuted only if even the smallest achievable p exceeds it; read as exact it is, in this module's own words, 'a large false-accusation class rather than a detection'. The literal cannot carry this -- `reported_p` is a float here -- so if the paper printed a bound you must say so."),
            Param("num_samples", int, 10000),
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
            Param("sampling", str, "simple_random", guard=True),
        ),
        stages=frozenset({STAGE1}),
        cli="rivets-t",
        cli_required_flags=frozenset(),
    ),
)
