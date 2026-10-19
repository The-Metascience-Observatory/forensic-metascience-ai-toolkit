"""The `grim` tool family: grim_check, grim_percentage, grim_sweep, reconstruct_2x2.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `metascience_agent.tools.grim`.
"""

from __future__ import annotations

from ...registry import (
    DISCRETENESS_SOURCE_HELP,
    PROVENANCE_HELP,
    REQUIRED,
    SCIENCE_AGENT,
    STAGE1,
    STAGE2,
    Param,
    ToolSpec,
)
from ...tools.grim import grim_sweep, grim_test, grim_test_percentage, reconstruct_2x2
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="grim_check",
        fn=grim_test,
        description=DESCRIPTIONS["grim_check"],
        params=(
            Param("mean", float, REQUIRED, exact=True),
            Param("n", int, REQUIRED, exact=True),
            Param("scale_min", int, 1),
            Param("scale_max", int, 7),
            # Was `default=2, guard=False`, while the sibling `grimmer_check`
            # already had `default=None, guard=True`. Verified: mean 5.9 at n=12
            # on a likert scale is `impossible` on the default and `consistent`
            # at decimals=1; on rows consistent at 1 dp the default returned a
            # false `impossible` 41.1% of the time.
            Param("decimals", int, None, guard=True, precision=True,
                  help="Printed decimals of `mean`, read from the literal in the paper "
                       "('5.9' is 1, '5.90' is 2). No default: the wrong one accuses."),
            Param("data_type", str, 'unknown', guard=True),
            Param("bound_source", str, 'assumed', guard=True),
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
        legacy_verb="grim",
    ),
    ToolSpec(
        name="grim_percentage",
        fn=grim_test_percentage,
        description=DESCRIPTIONS["grim_percentage"],
        params=(
            Param("percentage", float, REQUIRED, exact=True),
            Param("n", int, REQUIRED, exact=True),
            Param("decimals", int, None, guard=True, precision=True,
                  help=("Printed decimals OF THIS PERCENTAGE, read off the literal: '23' is 0, '23.7' is 1, '23.70' is 2. No default -- the wrong one accuses.")),
            # DEFAULT 'unknown', NOT 'proportion'. A guard whose default is a
            # substantive value is not a guard.
            #
            # This param was flagged `guard=True` and the gate works perfectly
            # when it is reached: 'unknown' and 'continuous' both refuse. It was
            # simply unreachable, because omitting the argument handed the check
            # the one value that lets it fire. MEASURED before this change:
            # `grim_percentage(percentage=23.7, n=42)` with no declaration
            # returned `impossible` -- the top of the severity ladder, reserved
            # for bound-free arithmetic -- on the exact case this tool's own
            # description names as the false-accusation example, "glucose fell
            # 23.7%". Its sibling `grim_check` defaults `data_type` to 'unknown'
            # and correctly returns indeterminate on the same omission.
            Param("data_type", str, 'unknown', guard=True),
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
    ),
    ToolSpec(
        name="grim_sweep",
        fn=grim_sweep,
        description=DESCRIPTIONS["grim_sweep"],
        params=(
            Param("values", list, REQUIRED, exact=True),
            Param("n_max", int, REQUIRED),
            Param("n_min", int, 2),
            Param("decimals", int, None, guard=True, precision=True,
                  help=("The COARSEST printed precision among `values`. If the paper prints 45.2%, 33% and 21.7%, pass 0, not 1: one rounding window covers every value here, and the finest precision present shrinks it for all of them. No default -- the wrong one accuses.")),
            Param("value_type", str, 'percentage'),
            Param("n_max_source", str, "assumed", guard=True,
                  help="stated | logically_necessary | assumed. Say 'stated' ONLY when n_max "
                       "is the paper's own total N. An empty intersection inside a range WE "
                       "chose is a fact about the search, not the paper, so it refuses with "
                       "`indeterminate` unless the range is the paper's."),
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
        legacy_verb="grim-sweep",
    ),
    ToolSpec(
        name="reconstruct_2x2",
        fn=reconstruct_2x2,
        description=DESCRIPTIONS["reconstruct_2x2"],
        params=(
            Param("pct_col1", float, REQUIRED, exact=True),
            Param("pct_col2", float, REQUIRED, exact=True),
            Param("n_total", int, REQUIRED, exact=True),
            Param("decimals", int, None, guard=True, precision=True,
                  help=("The COARSEST printed precision among the percentages given. One window covers both columns, so the finest precision present would shrink it for both. No default -- the wrong one accuses.")),
            Param("value_type", str, 'percentage'),
            Param("reported_chi2", float, None),
            Param("chi2_tolerance", float, 0.05),
            Param("balance_ratio_max", float, 4.0),
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
        # OFFERED TO THE MODEL 2026-08-15 (Greg): "if they have the potential
        # to be useful, I want them." Was `frozenset()` -- reachable from the
        # CLI and never by the agent.
        stages=frozenset({STAGE1, STAGE2, SCIENCE_AGENT}),
        legacy_verb="reconstruct-2x2",
    ),
)
