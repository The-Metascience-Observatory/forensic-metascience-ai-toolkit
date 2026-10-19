"""The `debit` tool family: debit_check, debit_check_batch.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `metascience_agent.tools.debit`.
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
from ...tools.debit import debit_test, debit_test_batch
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="debit_check",
        fn=debit_test,
        description=DESCRIPTIONS["debit_check"],
        params=(
            Param("mean", float, REQUIRED, exact=True),
            Param("sd", float, REQUIRED, exact=True),
            Param("n", int, REQUIRED, exact=True),
            # Were `default=2, guard=False`, while the sibling `grimmer_check`
            # already had `default=None, guard=True`. Conditioned on rows that
            # are consistent at 1 dp, the 2-dp default returned a false
            # `impossible` on 73.6% of DEBIT rows -- the worst of the three.
            # A proportion printed "0.3" is exactly the common case.
            Param("decimals_mean", int, None, guard=True, precision=True,
                  help="Printed decimals of `mean`, read from the literal in the paper "
                       "('0.3' is 1, '0.30' is 2). No default: the wrong one accuses."),
            Param("decimals_sd", int, None, guard=True, precision=True,
                  help="Printed decimals of `sd`, read from the literal in the paper."),
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
        stages=frozenset({STAGE1, STAGE2}),
        legacy_verb="debit",
    ),
    ToolSpec(
        name="debit_check_batch",
        fn=debit_test_batch,
        description=DESCRIPTIONS["debit_check_batch"],
        params=(
            Param("rows", list, REQUIRED, exact=True),
            # NO BATCH-WIDE PRECISION, AND DELETED RATHER THAN DEFAULTED TO
            # None. One precision for a whole table is wrong in PRINCIPLE, not
            # merely unset: an honest Table 1 prints a mean to 2 dp beside its
            # own SD at 1 dp, and the corpus has one --
            # `10.1001--jamanetworkopen.2023.51752` Table 8 prints `0.55 (0.5)`
            # in a column of `0.46`/`0.49`/`0.44`/`0.47`. Exhaustively over
            # n=20..200, k=1..n-1 (19,729 honest binary rows): 0 `impossible`
            # at each row's true precision, 13,447 (68.2%) at a batch-wide
            # 2 dp. A fallback that is wrong in principle is not a safety net,
            # it is the accusation. Precision travels PER ROW.
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
            # PASS THIS. It defaults to None here while the function defaults to
            # "binary", and None is not in {binary, proportion}, so an omitted
            # data_type refuses the whole batch as `indeterminate` -- the same
            # rows return `consistent` with data_type="binary". MEASURED
            # 2026-08-16 over the archive: all 4 real calls did supply it, so
            # this has never actually cost a run; it was a silent trap, not a
            # live failure. Stating the requirement is what closes it.
            Param("data_type", str, None, guard=True,
                  help="REQUIRED in practice: DEBIT is defined only for 0/1-coded "
                       "data, so pass 'binary' (or 'proportion'). Any other value "
                       "-- including omitting it -- refuses the batch rather than "
                       "judging it."),
        ),
        stages=frozenset({STAGE1}),
    ),
)
