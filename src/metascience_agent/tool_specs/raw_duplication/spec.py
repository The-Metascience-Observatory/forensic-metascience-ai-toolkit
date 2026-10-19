"""The `raw_duplication` tool family: detect_raw_duplication.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `copy_paste_detector.detector`.
"""

from __future__ import annotations

from ...registry import (
    REQUIRED,
    STAGE1,
    STAGE2,
    Param,
    ToolSpec,
)
from copy_paste_detector import detect_raw_duplication
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="detect_raw_duplication",
        fn=detect_raw_duplication,
        description=DESCRIPTIONS["detect_raw_duplication"],
        params=(
            Param("path", str, REQUIRED),
            Param("sheet", str, None,
                  help="Restrict to one worksheet (default: all, capped and announced)."),
            Param("exclude_columns", list, None,
                  help="Column names shared BY DESIGN (IDs, coordinates, site-level "
                       "covariates); they are excluded from every comparison."),
            Param("data_context", str, "unknown", guard=True,
                  help="raw_participant_level | pooled_or_meta_analysis | unknown. "
                       "Pooled/meta-analytic files duplicate rows by construction; "
                       "findings are then capped at indeterminate."),
            Param("max_row_pairs", int, 5000, withheld=True),
        ),
        stages=frozenset({STAGE1, STAGE2}),
        legacy_verb="raw-duplication-detect",
    ),
)
