"""The `run_script` tool family: run_python_script.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `metascience_agent.run_script`.
"""

from __future__ import annotations

from ...registry import (
    REQUIRED,
    SCIENCE_AGENT,
    Param,
    ToolSpec,
)
from ...run_script import run_python_script
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="run_python_script",
        fn=run_python_script,
        description=DESCRIPTIONS["run_python_script"],
        params=(
            Param("code", str, REQUIRED,
                  help="The Python script. stdout is your result -- print what "
                       "you need. No network; filesystem read-only outside "
                       "the scripts directory."),
            Param("label", str, "script",
                  help="Short slug naming what the script checks; becomes "
                       "part of the persisted filename."),
            Param("timeout_seconds", int, 60),
        ),
        stages=frozenset({SCIENCE_AGENT}),
    ),
)
