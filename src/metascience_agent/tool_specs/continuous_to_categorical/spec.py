"""The `continuous_to_categorical` tool family: check_proportion_from_normal.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `metascience_agent.tools.continuous_to_categorical`.
"""

from __future__ import annotations

from ...registry import (
    REQUIRED,
    STAGE2,
    Param,
    ToolSpec,
)
from ...tools.continuous_to_categorical import check_proportion_from_normal
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="check_proportion_from_normal",
        fn=check_proportion_from_normal,
        description=DESCRIPTIONS["check_proportion_from_normal"],
        params=(
            Param("reported_proportion", float, REQUIRED),
            Param("mean", float, REQUIRED),
            Param("sd", float, REQUIRED),
            Param("n", int, REQUIRED),
            Param("threshold", float, REQUIRED),
            Param("direction", str, 'below'),
            Param("summary", str, "arithmetic",
                  "Whether `mean` and `sd` are ARITHMETIC or GEOMETRIC. Pass \"geometric\" when the paper reports a geometric mean with a geometric SD -- the convention for right-skewed quantities like biomarkers, titers, concentrations, exposures and costs, which are printed as \"mean\" and \"SD\" on the page like any other. The test is then run on the LOG scale, where a lognormal variable is normal, and the verdict is capped because that lognormal model is ours. Getting this wrong is not cosmetic: an honest GM 10.0 (GSD 3.0) reporting 15.9% above 30 reads as `highly_suspicious` when passed as arithmetic, and `consistent` when declared."),
            Param("num_simulations", int, 10000),
            Param("seed", int, 0),
        ),
        stages=frozenset({STAGE2}),
        cli="prop-from-normal",
        cli_required_flags=frozenset(),
    ),
)
