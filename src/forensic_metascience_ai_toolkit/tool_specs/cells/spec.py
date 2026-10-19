"""The `cells` tool family: parse_cells_typed, parse_cells_as_declared, parse_table.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `forensic_metascience_ai_toolkit.tools.cellformat`, `forensic_metascience_ai_toolkit.tools.celltypes`, `forensic_metascience_ai_toolkit.tools.tableparse`.
"""

from __future__ import annotations

from ...registry import (
    REQUIRED,
    SCIENCE_AGENT,
    STAGE1,
    STAGE2,
    Param,
    ToolSpec,
)
from ...tools.cellformat import apply_format
from ...tools.celltypes import parse_cells
from ...tools.tableparse import parse_table
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="parse_cells_typed",
        fn=parse_cells,
        description=DESCRIPTIONS["parse_cells_typed"],
        params=(
            Param("cells", list, REQUIRED),
        ),
        stages=frozenset({STAGE1, STAGE2, SCIENCE_AGENT}),
        legacy_verb="parse-cells",
    ),
    ToolSpec(
        name="parse_cells_as_declared",
        fn=apply_format,
        description=DESCRIPTIONS["parse_cells_as_declared"],
        params=(
            Param("cells", list, REQUIRED),
            Param("declared", str, REQUIRED),
            Param("min_fit", float, 0.8),
        ),
        stages=frozenset({STAGE1, STAGE2, SCIENCE_AGENT}),
        legacy_verb="parse-cells-as",
    ),
    ToolSpec(
        name="parse_table",
        fn=parse_table,
        description=DESCRIPTIONS["parse_table"],
        params=(
            Param("source", str, REQUIRED),
            Param("source_format", str, 'auto'),
            Param("source_label", str, 'table'),
            Param("header_row", int, 0),
            Param("label_col", int, 0),
            Param("cross_check", str, None),
            Param("cross_check_format", str, 'auto'),
        ),
        stages=frozenset({STAGE1, STAGE2, SCIENCE_AGENT}),
        legacy_verb="parse-table",
    ),
)
