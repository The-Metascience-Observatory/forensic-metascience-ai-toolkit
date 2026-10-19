"""The `multiplicity` tool family: multiplicity_report.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `forensic_metascience_ai_toolkit.anatomy`.
"""

from __future__ import annotations

from ...anatomy import multiplicity_report
from ...registry import (
    REQUIRED,
    STAGE1,
    STAGE2,
    Param,
    ToolSpec,
    _multiplicity_adapter,
)
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="multiplicity_report",
        fn=multiplicity_report,
        description=DESCRIPTIONS["multiplicity_report"],
        params=(
            Param("tests", list, REQUIRED,
                  help="One dict per test in the family; p_value and correction_applied are "
                       "the load-bearing fields."),
            Param("alpha", float, 0.05),
            Param("family_label", str, REQUIRED, guard=True,
                  help="Describe the family you chose. Family definition is a judgement the "
                       "tool cannot make for you, so there is no default -- an omitted "
                       "label is refused, not filled in."),
        ),
        stages=frozenset({STAGE1, STAGE2}),
        legacy_verb="multiplicity",
        adapter=_multiplicity_adapter,
    ),
)
