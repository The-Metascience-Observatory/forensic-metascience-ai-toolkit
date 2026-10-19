"""The `estimates` tool family: absence_of_evidence, check_estimate_ci.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `metascience_agent.tools.estimates`.
"""

from __future__ import annotations

from ...registry import (
    REQUIRED,
    STAGE1,
    STAGE2,
    Param,
    ToolSpec,
)
from ...tools.estimates import absence_of_evidence, check_estimate_ci
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="absence_of_evidence",
        fn=absence_of_evidence,
        description=DESCRIPTIONS["absence_of_evidence"],
        params=(
            # NO LONGER REQUIRED, and that is the point. Measured across the
            # archive: 7 papers could not be checked here at all because they
            # print no interval anywhere, and 3 of those print b AND se, which
            # determines one completely. In two of them the null result IS the
            # paper's conclusion -- so the one check that spoke to the headline
            # claim was the one that could not run.
            Param("ci_low", float, None),
            Param("ci_high", float, None),
            Param("measure", str, None, guard=True),
            Param("sesoi", float, None),
            Param("claim_of_no_effect", bool, True),
            Param("null_value", float, None),
            Param("b", float, None),
            Param("se", float, None),
            Param("df", int, None),
            Param("confidence_level", float, 0.95),
        ),
        stages=frozenset({STAGE1}),
        legacy_verb="absence-of-evidence",
    ),
    ToolSpec(
        name="check_estimate_ci",
        fn=check_estimate_ci,
        description=DESCRIPTIONS["check_estimate_ci"],
        params=(
            Param("estimate", float, REQUIRED),
            Param("ci_low", float, REQUIRED),
            Param("ci_high", float, REQUIRED),
            Param("measure", str, None, guard=True),
            Param("reported_p", float, None),
            Param("reported_p_operator", str, "=",
                  help="Comparison the paper printed with the p: '=', '<', "
                       "'<=', '>' or '>='. Pass '<' for 'P < .001'."),
            Param("confidence_level", float, None,
                  help="The level the paper STATES for this interval (0.95, 0.8). "
                       "Omit when it states none: 95% is then assumed and a p "
                       "that reconciles only at another common level is noted. "
                       "A stated level is never overridden -- reconciling only "
                       "at a different one is `suspicious`."),
            Param("null_value", float, None),
            Param("decimals", int, None,
                  help="Printed decimals of the coarsest of estimate, ci_low, ci_high."),
            Param("sampling", str, "simple_random", guard=True),
            Param("interval_method", str, None,
                  "How the interval was CONSTRUCTED, if the paper says -- \"bootstrap\", \"BCa\", \"exact\", \"Clopper-Pearson\", \"profile likelihood\", \"Fieller\", \"Wilson\", \"Bayesian credible\". The midpoint test assumes a WALD interval (estimate +/- z*SE), which is the only method symmetric about its estimate. Bootstrap intervals are mandatory practice for skewed cost data and exact intervals are routine in epidemiology; both fail a midpoint test innocently. Leave it out when the paper does not say -- the test then still runs and names the ambiguity rather than asserting an inconsistency.")
        ),
        stages=frozenset({STAGE1, STAGE2}),
        legacy_verb="check-ci",
    ),
)
