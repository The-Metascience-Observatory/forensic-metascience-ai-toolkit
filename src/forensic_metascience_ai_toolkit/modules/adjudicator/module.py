"""The adjudicator: the finaliser that assigns every row its final severity.

The core builds the docket (every producer's rows, the tally, the second-look
worklist, where the paper is, the image evidence bundle) and calls
`finalize`. This module decides whether to run -- there must be rows, and
there must be budget above the floor -- runs the adjudicator with one bounded
retry for the schema gate, and applies its verdicts through
`adjudicate.apply`, whose clamps are code. When it cannot run, it finalises
through `adjudicate.apply_skip`, so findings are never lost to their own
pipeline. Moved from `parallel._coordinate_analysis` in Phase 2, unchanged.
"""

from __future__ import annotations

from ... import adjudicate
from ...core import prompts
from ... import agent as _agent
from ...llm_backend import MCPUnavailable
from ...registry import ADJUDICATOR
from ..base import Module

#: Failures of THIS paper's adjudicator call, which `apply_skip` absorbs.
#: Account-level stops are deliberately absent (see `finalize`).
_PER_PAPER_FAILURES = (_agent.StageError, MCPUnavailable)


def attach_to_command(cmd, packet: dict, backend: str) -> list[str]:
    """`image_forensics.evidence.attach_to_command`; a no-op when the docket
    carries no image attachments (always, without the image package)."""
    if not packet.get("attachments"):
        return []
    from ...image_plugin import load
    return load("image_forensics.evidence").attach_to_command(cmd, packet, backend)


def adjudication_receipts(bundle: dict, stage: dict, backend: str) -> dict:
    """`image_forensics.evidence.adjudication_receipts`, or the per-finding
    load errors alone when no packet was loaded."""
    if not bundle.get("by_finding"):
        return {fid: {"complete": False, "error": err}
                for fid, err in (bundle.get("errors") or {}).items()}
    from ...image_plugin import load
    return load("image_forensics.evidence").adjudication_receipts(bundle, stage, backend)


class Adjudicator(Module):
    async def finalize(self, ctx, merged, *, docket, image_bundle, text,
                       limitations):
        """Returns (findings, adj_summary, adjudicator_stage)."""

        from ...parallel import (
            ADJUDICATOR_TOOLS,
            MIN_ADJUDICATOR_BUDGET_USD,
            _adjudicator_hit_schema_gate,
            _schema_gate_correction,
        )
        settings = ctx.settings_for(self.name)
        config, budget_usd = ctx.config, ctx.budget_usd
        be, model, effort = settings.backend, settings.model, settings.effort
        verbose, timeout, on_progress = ctx.verbose, ctx.timeout, ctx.on_progress
        paper_dir, run_slug, _remember = ctx.paper_dir, ctx.run_slug, ctx.remember
        spent = _agent.spend_so_far()["total_cost_usd"]
        adj_budget = (budget_usd - spent) if budget_usd else None
        adjudicator_stage = None
        if not merged:
            findings, adj_summary = adjudicate.apply_skip(
                merged, skipped_reason="no findings to adjudicate")
        elif adj_budget is not None and adj_budget < MIN_ADJUDICATOR_BUDGET_USD:
            findings, adj_summary = adjudicate.apply_skip(
                merged, skipped_reason=(
                    f"budget below adjudication floor "
                    f"(${adj_budget:.2f} < ${MIN_ADJUDICATOR_BUDGET_USD})"))
            limitations.append("the adjudicator did not run (budget floor); "
                               "severities are provisional")
        else:
            adj_cmd = _agent._build_claude_cmd(
                system_prompt=_remember("adjudicator",
                                        prompts.system_prompt_for(config, "adjudicator")),
                allowed_tools=ADJUDICATOR_TOOLS, model=model, effort=effort,
                json_schema=prompts.adjudication_schema(),
                budget_usd=adj_budget, paper_dir=paper_dir, backend=be.name,
                mcp_stage=ADJUDICATOR, run_slug=run_slug, vision=bool(image_bundle["by_finding"]))
            attach_to_command(adj_cmd, image_bundle, be.name)
            try:
                adjudicator_stage = await _agent._run_stage(
                    adj_cmd, docket["text"], verbose, timeout, on_progress,
                    stage_label="adjudicator")
            except _PER_PAPER_FAILURES as exc:
                # A STAGE THAT RAISES MUST NOT TAKE THE ANALYSTS' WORK WITH
                # IT. Before this, a CLI crash here propagated and no
                # findings.v2 was written: every finding the two analysts had
                # been paid for was lost to the step that only grades them.
                # Account-level stops (`BackendUnavailable`,
                # `WeeklyLimitReached`) still propagate, so a batch stops.
                findings, adj_summary = adjudicate.apply_skip(
                    merged, failure=f"adjudicator stage failed "
                                    f"({type(exc).__name__}: {exc})"[:500])
                limitations.append(
                    f"the adjudicator stage failed ({type(exc).__name__}); "
                    "severities are provisional")
                return findings, adj_summary, None
            _agent.record_spend("adjudicator", adjudicator_stage)
            adj_out, adj_path = _agent._extract_json(adjudicator_stage)
            adjudicator_stage["output_parse_path"] = adj_path
            # ONE BOUNDED RETRY, AND ONLY FOR THE SCHEMA GATE.
            #
            # The adjudicator had no retry at all: one shot, and `apply_skip` on
            # anything that did not parse. MEASURED 2026-08-22 over a 10-paper
            # grok-4.6 batch, that cost 2 of 10 papers their adjudication for
            # $0.007 and $0.011 of actual model time -- both died on turn ONE, in
            # 7 seconds, with zero tool calls, because the model emitted a
            # placeholder `summary` intending to fill it in later and the schema's
            # 200-character floor rejected it. Nothing about those runs was
            # expensive or ambiguous; they were simply never retried, and $1.15 of
            # completed analyst work shipped unadjudicated.
            #
            # NARROW ON PURPOSE. Only the structured-output gate qualifies. A
            # budget stop must not be retried (the money is the constraint, and
            # `MIN_ADJUDICATOR_BUDGET_USD` is re-checked below), and a timeout must
            # not be retried (the retry inherits the same wall clock and would
            # double the stall). Everything else keeps the old one-shot behaviour.
            if adj_out is None and _adjudicator_hit_schema_gate(adjudicator_stage):
                spent_now = _agent.spend_so_far()["total_cost_usd"]
                retry_budget = (budget_usd - spent_now) if budget_usd else None
                if retry_budget is None or retry_budget >= MIN_ADJUDICATOR_BUDGET_USD:
                    limitations.append(
                        "the adjudicator ERRORED at the structured-output gate; "
                        "retried once")
                    # Antigravity keeps the unfinished conversation: resume
                    # it (context and tools intact) instead of re-sending the
                    # docket to a fresh session. See `retry_if_empty`.
                    from ...llm_backend import (antigravity_resume_invocation,
                                                antigravity_resume_prompt,
                                                merge_resumed_stage)
                    first_stage = adjudicator_stage
                    resume_cmd = antigravity_resume_invocation(adjudicator_stage)
                    retry_cmd = resume_cmd or _agent._build_claude_cmd(
                            system_prompt=_remember(
                                "adjudicator",
                                prompts.system_prompt_for(config, "adjudicator")),
                            allowed_tools=ADJUDICATOR_TOOLS, model=model,
                            effort=effort,
                            json_schema=prompts.adjudication_schema(),
                            budget_usd=retry_budget, paper_dir=paper_dir,
                            backend=be.name, mcp_stage=ADJUDICATOR,
                            run_slug=run_slug, vision=bool(image_bundle["by_finding"]))
                    if resume_cmd is None:
                        attach_to_command(retry_cmd, image_bundle, be.name)
                        retry_prompt = (docket["text"]
                                        + _schema_gate_correction(adjudicator_stage))
                    else:
                        retry_prompt = antigravity_resume_prompt()
                        limitations.append(
                            "the adjudicator retry RESUMED the same agy conversation")
                    try:
                        adj_retry = await _agent._run_stage(
                            retry_cmd, retry_prompt,
                            verbose, timeout, on_progress,
                            stage_label="adjudicator_retry")
                    except _PER_PAPER_FAILURES as exc:
                        # The first attempt's outcome stands (apply_skip below).
                        limitations.append(
                            f"the adjudicator retry failed ({type(exc).__name__})")
                        adj_retry = None
                    if adj_retry is not None:
                        _agent.record_spend("adjudicator_retry", adj_retry)
                        if resume_cmd is not None:
                            adj_retry = merge_resumed_stage(first_stage, adj_retry)
                    retry_out, retry_path = (_agent._extract_json(adj_retry)
                                             if adj_retry is not None
                                             else (None, "failed"))
                    if retry_out is not None:
                        adjudicator_stage = adj_retry
                        adjudicator_stage["output_parse_path"] = retry_path
                        adj_out, adj_path = retry_out, retry_path
            if adj_path == _agent.ACCEPTED_TOOL_CALL_PATH:
                limitations.append(
                    _agent.accepted_tool_call_note(adjudicator_stage, "adjudicator"))
            if adj_out is None:
                _agent.mark_no_document(adjudicator_stage)
                findings, adj_summary = adjudicate.apply_skip(
                    merged, failure=f"adjudicator output unparseable ({adj_path})")
                limitations.append(
                    "the adjudicator's output did not parse; "
                    + ("its stream ended without the CLI's final `result` "
                       "event; " if adjudicator_stage.get("result_event") is False
                       else "")
                    + "severities are provisional")
            else:
                receipts = adjudication_receipts(image_bundle, adjudicator_stage, be.name)
                adjudicator_stage["image_delivery"] = receipts
                findings, adj_summary = adjudicate.apply(merged, adj_out,
                                                         paper_text=text, image_delivery=receipts)
                if adj_summary.get("n_image_delivery_withheld"):
                    limitations.append(
                        "The adjudicator could not verify delivery of some image "
                        "evidence; those image findings retain provisional status.")
        return findings, adj_summary, adjudicator_stage


MODULE = Adjudicator()
