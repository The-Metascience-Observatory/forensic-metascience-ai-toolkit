"""The `flow` tool family: check_flow_arithmetic.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `forensic_metascience_ai_toolkit.tools.flow`.
"""

from __future__ import annotations

from ...registry import (
    ADJUDICATOR,
    REQUIRED,
    SCIENCE_AGENT,
    Param,
    ToolSpec,
)
from ...tools.flow import check_flow_arithmetic
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="check_flow_arithmetic",
        fn=check_flow_arithmetic,
        description=DESCRIPTIONS["check_flow_arithmetic"],
        params=(
            Param("stages", list, REQUIRED,
                  help='Ordered cascade, top-down: [{"label", "n", '
                       '"excluded": [{"reason", "n"}], '
                       '"arms": [{"label", "n"}], '
                       '"also_reported": [{"n", "source"}]}]. Transcribe every n as '
                       'printed; the tool refuses rather than assumes. '
                       '`also_reported` carries the SAME stage\'s count as printed '
                       'elsewhere (abstract, figure, another table).'),
            Param("randomized_label", str, None,
                  help="Which stage the analyzed<=randomized check anchors "
                       "on, when no stage label contains 'random'."),
            Param("description", str, "participant flow"),
        ),
        stages=frozenset({SCIENCE_AGENT, ADJUDICATOR}),
        legacy_verb="flow-check",
    ),
)
