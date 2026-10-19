"""The tools agent (stored producer `tool_expert`). See MODULE.md."""

from __future__ import annotations

from ... import agent as _agent
from ... import parallel as _par
from ...core import prompts
from ...registry import TOOL_AGENT
from .._analyst import AnalystModule


class ToolsAgent(AnalystModule):
    label = "tool_agent"
    producer = "tool_expert"
    mcp_stage = TOOL_AGENT
    budget_fraction = _par.TOOL_BUDGET_FRACTION
    records_own_spend = True
    requires_forensic_calls = True

    def allowed_tools(self, ctx):
        return _par.tool_agent_tools(ctx.figures, ctx.toolset)

    def json_schema(self, ctx):
        return prompts.producer_findings_schema("tool_expert", figures=ctx.figures)

    def mcp_tools(self, ctx):
        return sorted(ctx.toolset) if ctx.toolset is not None else None

    def user_prompt(self, ctx):
        src = ctx.src
        return _par._restrict_user_prompt(_agent._build_sweep_prompt(
            src.body_md, src.main_pdf, ctx.paper_id, si_pdfs=src.si_pdfs,
            xml=src.xml, html=src.html, si_readable=src.si_readable,
            paper_dir=ctx.paper_dir),
            ctx.toolset) + ctx.survey_note

    async def run_stage(self, ctx, settings, build_cmd, prompt):
        # Records its own spend per attempt (spend_label).
        return await _agent._run_stage_requiring_forensic_tools(
            build_cmd=build_cmd, prompt=prompt,
            allowed_tools=_par.TOOL_AGENT_TOOLS, stage_label=self.label,
            backend=settings.backend, spend_label=self.label,
            verbose=ctx.verbose, timeout=ctx.timeout, on_progress=ctx.on_progress)

    def after(self, ctx, stage, doc, limitations):
        # BELT AND BRACES, because the retry can be skipped (budget floor) and
        # can fail. `coverage` is the report's only account of what ran, and
        # "tools run: none recorded" under a Coverage heading is not a
        # reader's cue that a paid analyst's results were lost. The
        # contradiction -- forensic calls on the ledger, no tools in the
        # coverage -- is a fact this code has both halves of, so it is stated.
        if doc is not None and not (
                (doc.get("coverage") or {}).get("tools_run") or []):
            n = sum(1 for r in _agent._tool_call_ledger(
                (stage or {}).get("messages") or [], [])
                if str(r.get("surface", "")).startswith("forensic_mcp"))
            if n:
                limitations.append(
                    f"the tool_agent ran {n} forensic tool call(s) but its report "
                    "records no tools in `coverage`; those results did not survive "
                    "into the docket and this review's coverage is understated")


MODULE = ToolsAgent()
