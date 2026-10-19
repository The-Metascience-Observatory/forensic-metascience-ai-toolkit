"""The `variance_dispersion` tool family: check_variance_dispersion.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `forensic_metascience_ai_toolkit.tools.variance_dispersion`.
"""

from __future__ import annotations

from ...registry import (
    REQUIRED,
    STAGE1,
    STAGE2,
    Param,
    ToolSpec,
)
from ...tools.variance_dispersion import check_variance_dispersion
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="check_variance_dispersion",
        fn=check_variance_dispersion,
        description=DESCRIPTIONS["check_variance_dispersion"],
        params=(
            Param("sds", list, REQUIRED),
            Param("ns", list, REQUIRED),
            Param("sd_texts", list, None, precision=True),
            Param("homogeneous_variances", bool, None, guard=True),
            Param("design", str, None, guard=True),
            # WITHHELD for the reason `rho_grid` and `ci_level` are withheld on the
            # neighbouring tools: iteration count moves the p-value's Monte Carlo
            # noise, so exposing it hands the model a dial it can turn until an
            # inconvenient result crosses a threshold. Operators set it from the CLI.
            Param("iterations", int, 100_000, withheld=True),
            Param("seed", int, 0),
        ),
        stages=frozenset({STAGE1, STAGE2}),
        legacy_verb="variance-dispersion",
    ),
)
