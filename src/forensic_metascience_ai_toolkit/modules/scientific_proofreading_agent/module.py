"""The scientific proofreading agent (stored producer `science_error`). See MODULE.md."""

from __future__ import annotations

from ... import parallel as _par
from ...registry import SCIENCE_AGENT
from .._analyst import AnalystModule


class ScientificProofreadingAgent(AnalystModule):
    label = "science_agent"
    producer = "science_error"
    mcp_stage = SCIENCE_AGENT
    budget_fraction = _par.SCIENCE_BUDGET_FRACTION
    internet = True

    def allowed_tools(self, ctx):
        return _par.SCIENCE_AGENT_TOOLS

    def user_prompt(self, ctx):
        return _par._build_science_agent_prompt(ctx.src, ctx.paper_id) + ctx.survey_note


MODULE = ScientificProofreadingAgent()
