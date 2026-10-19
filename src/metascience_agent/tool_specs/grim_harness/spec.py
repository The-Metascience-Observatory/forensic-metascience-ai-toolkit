"""The `grim_harness` tool family: list_tables, declare_table.

The model's half of the harness GRIM sweep (`metascience_agent.grim_harness`):
the model declares what each table's cells are, and the harness checks every
cell that declaration covers -- during the run, in the tool result, and again
after it, when the failures are filed as findings.
"""

from __future__ import annotations

from ...grim_harness import declare_table, list_tables
from ...registry import (
    REQUIRED,
    STAGE1,
    Param,
    ToolSpec,
)
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="list_tables",
        fn=list_tables,
        description=DESCRIPTIONS["list_tables"],
        params=(
            Param("paper_dir", str, REQUIRED),
        ),
        stages=frozenset({STAGE1}),
        cli=None,
        cli_required_flags=frozenset(),
    ),
    ToolSpec(
        name="declare_table",
        fn=declare_table,
        description=DESCRIPTIONS["declare_table"],
        params=(
            Param("paper_dir", str, REQUIRED),
            Param("table", str, REQUIRED),
            Param("variables", list, None),
            Param("rows", list, None),
            Param("columns", list, None),
            Param("default_variable_id", str, None),
            Param("percent_of_units", bool, False),
        ),
        stages=frozenset({STAGE1}),
        cli=None,
        cli_required_flags=frozenset(),
    ),
)
