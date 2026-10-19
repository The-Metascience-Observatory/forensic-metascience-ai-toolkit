"""The `grimu` tool family: grimu_check, grimu_coexistence.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `metascience_agent.tools.grimu`.
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
from ...tools.grimu import grimu_check, grimu_coexistence
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="grimu_check",
        fn=grimu_check,
        description=DESCRIPTIONS["grimu_check"],
        params=(
            Param("n1", int, REQUIRED, exact=True),
            Param("n2", int, REQUIRED, exact=True),
            Param("reported_p", str, REQUIRED, exact=True),
            Param("decimals", int, None),
            Param("continuity_correction", str, 'both'),
            Param("method", str, 'normal'),
            Param("one_sided", bool, False),
            Param("test_type", str, "mann_whitney",
                  help="What test the paper attributed this p to. "
                       "mann_whitney / wilcoxon only; t, F, chi-squared, ANOVA "
                       "are refused (indeterminate), not scored."),
            Param("reported_z", float, None,
                  help="The normal-approximation Z printed beside the p, if the "
                       "paper printed one. If it reproduces the p at its printed "
                       "precision the check refuses: the p is the Z's rounding, "
                       "not U's granularity."),
            Param("p_source", str, "unspecified",
                  help="'u_statistic' | 'normal_z' | 'unspecified'. 'normal_z' "
                       "refuses without needing the Z itself."),
            Param("ties_possible", bool, None,
                  help="True for a small-integer or ordinal outcome. Ranks tie, "
                       "the tie correction shrinks sdU, and the untied lattice "
                       "no longer describes the achievable p's."),
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
        cli="grimu",
        cli_required_flags=frozenset(),
    ),
    ToolSpec(
        name="grimu_coexistence",
        fn=grimu_coexistence,
        description=DESCRIPTIONS["grimu_coexistence"],
        params=(
            Param("n1", int, REQUIRED, exact=True),
            Param("n2", int, REQUIRED, exact=True),
            Param("p_values", list, REQUIRED, exact=True),
            Param("decimals", int, None),
            Param("continuity_correction", str, 'both'),
            Param("method", str, 'normal'),
            Param("one_sided", bool, False),
            Param("test_type", str, "mann_whitney",
                  help="What test the paper attributed these p-values to. "
                       "mann_whitney / wilcoxon only."),
            Param("p_source", str, "unspecified",
                  help="'u_statistic' | 'normal_z' | 'unspecified'. 'normal_z' "
                       "refuses: a p rendered from a rounded Z does not sit on "
                       "the U lattice."),
            Param("ties_possible", bool, None,
                  help="True for a small-integer or ordinal outcome; the tie "
                       "correction moves every achievable p."),
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
        cli="grimu-coexist",
        cli_required_flags=frozenset(),
    ),
)
