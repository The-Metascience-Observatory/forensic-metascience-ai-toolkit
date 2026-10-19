"""The two LLM analysts' shared machinery: run, parse, retry.

Moved out of `parallel._coordinate_analysis` in Phase 2 (where it was a set
of closures) so each analyst is a module. The logic and every measured
comment are unchanged; `parse_output` and `retry_if_empty` read the run and
the analyst's own backend from `ctx` / `settings` instead of closure
variables. `parallel` re-exports the helpers for existing callers.
"""

from __future__ import annotations

import json
import re

from .. import agent as _agent
from ..core import prompts
from .base import Module, ModuleResult

#: WHAT COUNTS AS HAVING DONE THE WORK, per producer. Not the same question as
#: "what counts as validated evidence" -- `agent_code` and `web` are never
#: evidence (see `agent.AGENT_CODE_TOOLS`), but for the science-error analyst
#: they ARE the work: it reasons through sandboxed scripts and the literature,
#: and it is not on the forensic tools' allowlist for most of them. Counting
#: only `forensic_mcp` for that producer would refuse a science agent that had
#: done everything asked of it. The tool expert has no such excuse: its whole
#: job is the validated toolkit.
_WORK_SURFACES = {
    "tool_expert": ("forensic_mcp",),
    "science_error": ("forensic_mcp", "agent_code", "web"),
}


def _made_forensic_calls(allowed, *stages) -> bool:
    """Whether any attempt made a call on its forensic allowlist."""
    if not any(str(t).startswith(_agent.MCP_TOOL_PREFIX) for t in allowed or []):
        return True          # nothing forensic was declared: nothing to require
    return any(r.get("surface") == "forensic_mcp"
               for st in stages if st
               for r in _agent._tool_call_ledger(st.get("messages") or [],
                                                 list(allowed)))


def _n_work_calls(ledger, producer: str) -> int:
    """How many calls count as this producer having attempted the work."""
    surfaces = _WORK_SURFACES.get(producer, ("forensic_mcp",))
    return sum(1 for r in (ledger or [])
               if str(r.get("surface", "")).startswith(surfaces))


def _first_call(src) -> str:
    """The concrete first tool call for a paper, for a zero-call retry."""
    if src is None:
        return "a reader tool (`extract_xml`, `extract_pdf`) on the paper"
    if getattr(src, "xml", None):
        return f"`extract_xml` with path `{src.xml}`"
    if getattr(src, "main_pdf", None):
        return f"`extract_pdf` with pdf_path `{src.main_pdf}`"
    if getattr(src, "body_md", None):
        return f"`Read` of `{src.body_md}`"
    return "a reader tool (`extract_xml`, `extract_pdf`) on the paper"


def _producer_retry_correction(stage: dict | None, doc: dict | None,
                               n_forensic: int, schema_gate_error: bool,
                               truncated_docket: bool, first_call: str = "") -> str:
    """What to append to a producer's prompt on its one bounded retry.

    A RETRY THAT RE-SENDS A BYTE-IDENTICAL PROMPT IS A COIN FLIP, and it lost
    3 of 3 on 2026-08-22: `10.1002--alz.13600`, `10.1016--j.ebiom.2021.103246`
    and `10.1186--s13550-023-00956-9` each retried after 47, 78 and 70 forensic
    tool calls and came back empty again. The adjudicator's retry, which was
    given the rejection text in the same release, recovered 2 of 2.

    The three signatures need different sentences, because they are different
    failures. A schema-gate error is the CLI refusing the output and it can be
    quoted verbatim. A truncated or empty docket PARSED -- nothing rejected it
    -- and the model simply filed a highlights document instead of a report;
    telling it "your output was invalid" would be false and unactionable.
    """
    head = ("\n\n---\n\n## RETRY -- your previous report was not usable\n")
    if schema_gate_error:
        errs = (stage or {}).get("schema_errors") or []
        detail = ("\nThe output schema rejected it with exactly this:\n"
                  + "\n".join(f"  - {e}" for e in errs) + "\n") if errs else ""
        return (
            head + detail +
            "\nDo the reading and the tool work FIRST; the JSON is your LAST "
            "message and there is no turn after it. A placeholder or padded "
            "field ends the run with nothing.\n")
    if n_forensic == 0 and not truncated_docket:
        # THE ZERO-CALL DUMP. MEASURED 2026-10-14 (grok2_cerebrolysin_flow_2):
        # the whole session was one turn -- "Reviewing a scientific paper as
        # the Scientific Proofreading Agent", an empty placeholder document,
        # and the CLI took that as the answer. 3 of 20 grok runs. Telling it
        # it filed "a highlights document after 0 calls" names the wrong
        # failure; naming the first call is the actionable sentence.
        return (
            head +
            "\nYou wrote a findings document BEFORE examining the paper, and "
            "that document ended your run with nothing in it.\n\n"
            f"Your FIRST message must be a tool call: {first_call or 'a reader tool on the paper'}. "
            "(On grok, reach it through `use_tool` with tool_name "
            "`forensic_metascience__<name>`.) Read the whole paper, run your "
            "checks, and write the findings JSON ONCE, as your last message. "
            "A message that is only JSON, with no tool call beside it, is "
            "taken as your final answer.\n")
    n_found = len((doc or {}).get("findings") or [])
    return (
        head +
        f"\nIt parsed, so nothing rejected it -- but it recorded "
        f"{n_found} finding(s) and NO tools in `coverage`, after "
        f"{n_forensic} forensic tool call(s) on your ledger. That is a "
        "highlights document, not a docket.\n\n"
        "Every check you ran is a row, including the ones that PASSED: a "
        "clean check is the evidence that the territory was examined, and "
        "without it the report cannot distinguish 'we looked and it was fine' "
        "from 'we never looked'. Fill in `coverage.tools_run` with every tool "
        "you called, `anatomy` with the studies, variables and tests you "
        "identified, and `statistics_register` with the values you read. "
        "Prefer more rows with shorter `description` fields over a few long "
        "ones -- the report is assembled from structured fields, so prose "
        "length buys nothing and crowds out coverage.\n")


_LEDGER_ROW_CHARS = 900
_LEDGER_DIGEST_CHARS = 120_000


def _ledger_digest(ledger: list[dict] | None) -> str:
    """The producer's own forensic calls and results, as text it can read back.

    Ground truth about what was computed, built from the transcript rather
    than from the model's account of itself -- the same source
    `_coverage_with_ledger_fallback` trusts.
    """
    rows, total = [], 0
    for r in (ledger or []):
        # `agent_code` rides along: for the science agent its scripts ARE
        # the work being recovered, and their stdout is what a finding rests
        # on. They are still never `validated`.
        if not str(r.get("surface", "")).startswith(("forensic_mcp", "agent_code")):
            continue
        res = r.get("result")
        if not isinstance(res, str):
            res = json.dumps(res, default=str) if res is not None else ""
        if len(res) > _LEDGER_ROW_CHARS:
            res = res[:_LEDGER_ROW_CHARS] + " …[truncated]"
        inp = str(r.get("input") or "")
        if len(inp) > 300:
            inp = inp[:300] + " …"
        block = (f"### call {r.get('seq')} — {r.get('tool_short')}\n"
                 f"inputs: {inp}\nresult: {res}\n")
        if total + len(block) > _LEDGER_DIGEST_CHARS:
            rows.append(f"\n…[{len(rows)} of the calls shown; digest capped]\n")
            break
        rows.append(block)
        total += len(block)
    return "\n".join(rows)


def _ledger_recovery_prompt(ledger: list[dict] | None, doc: dict | None,
                            n_forensic: int) -> str:
    """Ask for the DOCUMENT ONLY, from work the producer has already done.

    MEASURED 2026-09-03 on `wound_healing` (grok-4.6, v1.15.0): the tool
    expert made 90 calls, began writing its report, degenerated into
    `n.n.n.n.n…` mid-document and recovered by filing ONE finding. Its ledger
    held 78 forensic results -- 1 `highly_suspicious`, 13 `suspicious`, 12
    `indeterminate`, 48 `consistent`. The bounded retry re-ran the whole stage
    from scratch, came back empty, and every one of those results was
    discarded.

    Re-deriving what is already recorded is the expensive way to fail twice.
    This asks only for the serialization, from a context that is the ledger
    rather than the whole 238K-token transcript the first attempt degenerated
    under.
    """
    n_found = len((doc or {}).get("findings") or [])
    return (
        "Your previous report did not survive serialization: it recorded "
        f"{n_found} finding(s) after {n_forensic} forensic tool call(s).\n\n"
        "YOU HAVE ALREADY DONE THE WORK. Below is your own tool ledger -- "
        "every forensic call you made and what it returned. Do not run any "
        "tools; there are none available on this turn. Write the findings "
        "document from this ledger and nothing else.\n\n"
        "Every check is a row, including the ones that PASSED: a clean check "
        "is the evidence that the territory was examined, and without it the "
        "report cannot distinguish 'we looked and it was fine' from 'we never "
        "looked'. Fill `coverage.tools_run` with every tool named below, and "
        "`statistics_register` with the values those calls read. Prefer more "
        "rows with short `description` fields over a few long ones.\n\n"
        "Do not invent a result that is not in the ledger.\n\n"
        "---\n\n## YOUR TOOL LEDGER\n\n" + _ledger_digest(ledger))


def _looks_empty_doc(raw: str) -> bool:
    """True when the stage's final output is a schema-shaped shell with no
    findings and no unchecked entries -- the grok final-turn dump."""
    try:
        doc = json.loads(raw)
    except (ValueError, TypeError):
        return False
    return (isinstance(doc, dict)
            and not (doc.get("findings") or [])
            and not (doc.get("unchecked") or []))


def _final_assistant_texts(messages: list, n: int = 4) -> str:
    """The last `n` assistant messages' text blocks, joined -- the narrated
    findings a grok schema failure leaves behind (thinking blocks are
    excluded: they are reasoning, not the agent's asserted output)."""
    texts: list[str] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        inner = msg.get("message") if isinstance(msg.get("message"), dict) \
            else msg
        if inner.get("role") != "assistant":
            continue
        for block in inner.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "text" \
                    and str(block.get("text") or "").strip():
                texts.append(str(block["text"]))
    joined = "\n\n".join(texts[-n:])
    return joined if len(joined.strip()) > 200 else ""


#: The one CLI error subtype that means "the model wrote something, and the
#: `--json-schema` gate refused it". Distinct from a budget stop or a timeout,
#: which the retry below must NOT touch.
_SCHEMA_GATE = "error_max_structured_output_retries"


def _final_after_placeholders(messages: list) -> dict | None:
    """The model's final document, when every EARLIER text it wrote was an
    empty placeholder document. None for any other shape.

    MEASURED 2026-10-11 (schnall2008, grok-4.6 science agent): the model wrote
    `{"schema_version": "2.0", "paper_id": ..., "findings": []}` beside seven
    of its tool calls, then a complete seven-finding document as its last
    message. The Grok CLI joined the texts, failed to parse the result
    ("trailing characters at line 1 column 73", the end of the first
    placeholder) and ended at `error_max_structured_output_retries`. The
    transcript salvage kept the right document but called the stream
    DEGENERATED and the analyst's coverage unverified, and the channel read
    `refused` beside seven of that analyst's findings.

    Nothing degenerated: placeholders are normal on grok (see
    `_salvage_documents`). So this shape is accepted only when it is exactly
    that: every assistant text block is a complete JSON document, every one
    before the last has no findings and nothing unchecked, and the last has
    some. Narration, a truncated document, or two non-empty documents fall
    back to the salvage path and its warning.
    """
    texts: list[str] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        inner = msg.get("message") if isinstance(msg.get("message"), dict) \
            else msg
        if inner.get("role") != "assistant":
            continue
        for block in inner.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "text" \
                    and str(block.get("text") or "").strip():
                texts.append(str(block["text"]))
    if len(texts) < 2:
        return None
    docs: list[dict] = []
    for text in texts:
        try:
            doc = json.loads(text)
        except (ValueError, TypeError):
            return None
        if not (isinstance(doc, dict)
                and any(k in doc for k in _agent._DOCUMENT_MARKERS)):
            return None
        docs.append(doc)
    *earlier, final = docs
    if any(d.get("findings") or d.get("unchecked") for d in earlier):
        return None
    if not (final.get("findings") or final.get("unchecked")):
        return None
    return final


async def parse_output(ctx, settings, stage, label, producer, limitations):
    """Parse a stage's findings document, repairing it when allowed
    (moved from `parallel._coordinate_analysis`)."""
    config = ctx.config
    be, model, effort = settings.backend, settings.model, settings.effort
    verbose, timeout = ctx.verbose, ctx.timeout
    if stage is None:
        return None
    doc, path = _agent._extract_json(stage)
    if (stage.get("is_error")
            and str(stage.get("error_subtype") or "") == _SCHEMA_GATE):
        final = _final_after_placeholders(stage.get("messages") or [])
        if final is not None:
            # The CLI refused output it had concatenated itself; the model's
            # last message is its complete answer. The stage did not fail,
            # so it is not recorded as failed; the refusal is kept beside it.
            doc, path = final, "final_after_placeholders"
            stage["cli_error_subtype"] = stage.get("error_subtype")
            stage["is_error"] = False
            stage["error_subtype"] = None
    if doc is None:
        raw = str(stage.get("text") or stage.get("result") or "")
        if not raw.strip() or _looks_empty_doc(raw):
            # TRANSCRIPT SALVAGE (measured 2026-08-22, neulet on grok):
            # the science agent did 22 tool calls and 13 web searches,
            # NARRATED its findings in its final turns, then emitted an
            # empty findings JSON while launching another tool call in
            # the same message -- error_max_structured_output_retries,
            # $0.32 of real work lost, and two of the four papers'
            # dropped findings trace to exactly this. The findings were
            # in the transcript the whole time; hand the repair pass the
            # final assistant texts instead of the empty envelope.
            salvage = _final_assistant_texts(stage.get("messages") or [])
            if salvage:
                raw = salvage
        if raw and not config.complete_review and be.name != "claude":
            # FAIL CLOSED. A partial pipeline's repair must run with no
            # tools, and only Claude can: Codex keeps a read-only shell and
            # Grok `read_file`, which neither CLI can drop. So on those
            # backends the repair call is not made, and the gap is named.
            limitations.append(
                f"the {label} stage's output did not parse and was NOT "
                f"repaired: a partial pipeline's repair must be tool-free, "
                f"and {be.name} cannot run without built-in tools")
        elif raw:
            doc = await _agent._repair_json(
                raw, prompts.producer_findings_schema(producer), model,
                verbose, timeout, effort=effort, backend=be.name,
                **({} if config.complete_review else {"tool_free": True}))
        path = "repair_call" if doc else "failed"
    stage["output_parse_path"] = path
    # A SALVAGED DOCUMENT MEANS THE PRODUCER DEGENERATED AND RECOVERED, and
    # the reader is entitled to know that before trusting the coverage.
    # Measured 2026-09-04 (airforce, grok, parallel/parallel): the stream
    # opened with a document that broke off mid-write into `Extra. Extra.
    # Extra...`, then re-emitted a complete 18-finding one. We now keep the
    # complete one instead of paying for a repair that returns nothing --
    # but "we recovered it" is not the same fact as "it ran cleanly".
    if path == "salvaged_object":
        limitations.append(
            f"the {label} stage's output stream DEGENERATED mid-document "
            "and was recovered deterministically: a complete document was "
            "salvaged from the stream, but the producer abandoned at least "
            "one earlier attempt, so treat this analyst's coverage as "
            "unverified rather than clean")
    if path == _agent.ACCEPTED_TOOL_CALL_PATH:
        limitations.append(_agent.accepted_tool_call_note(stage, label))
    if doc is None:
        _agent.mark_no_document(stage)
        if _agent._stage_hit_budget(stage):
            limitations.append(
                f"the {label} stage was BUDGET-TRUNCATED before emitting "
                "findings -- raise --max-budget-usd; its spend is recorded")
        elif _agent._stage_hit_timeout(stage):
            # The sibling of the branch above. Until 2026-09-02 a stage
            # cut off by the wall clock or the stall detector reached the
            # report as "produced no parseable findings JSON", which
            # reads as a model failure rather than a coverage fact.
            limitations.append(
                f"the {label} stage was CUT OFF by the per-stage timeout "
                "before emitting findings -- raise --timeout; the paper "
                "was not fully examined by this analyst")
        elif stage.get("result_event") is False:
            limitations.append(
                f"the {label} stage's stream ended without the CLI's final "
                "`result` event and no accepted findings document is in its "
                "transcript"
                + (" (the stream was cut mid-line)"
                   if stage.get("stdout_ended_mid_line") else "")
                + " -- this analyst's findings were LOST, not absent, and "
                "its cost is unknown")
        else:
            limitations.append(f"the {label} stage produced no parseable "
                               "findings JSON")
    return doc


def _carrying_work(recovery: dict, *worked: dict | None) -> dict:
    """The document-only recovery stage, with the transcripts of the attempts
    that DID THE WORK spliced ahead of its own.

    The recovery turn has no tools, so its own transcript holds no tool call.
    Returned bare, it became the stage the run records: the tool ledger the
    tool verdicts are joined from (`parallel._rows_from_producer`), the
    `toolcalls.<label>.json` audit, the checks tally and the receipts join
    were all built from a transcript with no calls in it, beside a document
    composed from those calls. The archived `messages.<label>.json` now
    holds every attempt in order, which is what happened."""
    msgs: list = []
    for st in worked:
        if st:
            msgs.extend(st.get("messages") or [])
    recovery["messages"] = msgs + list(recovery.get("messages") or [])
    return recovery


async def retry_if_empty(ctx, settings, stage, doc, label, producer, cmd_builder,
                         prompt, limitations, recover_cmd=None):
    """One bounded retry for the two EMPTY-REPORT signatures.

    MEASURED 2026-08-21 (wound_healing on grok): the science agent
    one-turn-dumped a schema-valid empty doc in 6 s with zero tool
    calls, and the tool agent ran a 91-call sweep then filed ZERO rows
    -- not even pass rows -- so a paper whose gold review lists five
    findings scored recall 0.0 with every stage reading "success".
    A parsed doc with no findings AND no unchecked entries, beside a
    ledger that is either silent or busy, is not a clean paper; it is
    a dropped report. One retry, billed and recorded; if the retry is
    empty too, the original stands and the limitation says so.
    """
    verbose, timeout, on_progress = ctx.verbose, ctx.timeout, ctx.on_progress
    if stage is None:
        return stage, doc
    schema_gate_error = doc is None and str(
        stage.get("error_subtype") or "") == "error_max_structured_output_retries"
    if doc is None and not schema_gate_error:
        return stage, doc
    led = _agent._tool_call_ledger(stage.get("messages") or [], [])
    n_forensic = _n_work_calls(led, producer)

    def _n_forensic(st):
        return _n_work_calls(
            _agent._tool_call_ledger((st or {}).get("messages") or [], []),
            producer)

    # THE THIRD SIGNATURE: A DOCKET THAT IS NOT EMPTY, JUST TRUNCATED.
    #
    # MEASURED 2026-08-22, 10.1177--0956797614564191 on grok-4.6. The tool
    # agent made 56 calls, then its structured output degenerated mid-array
    # -- backticks where quotes belonged, `...paragraph.`,`inputs`:{},` --
    # and it recovered by closing the findings list after ONE row and
    # emitting `"coverage":{"stats_found":0,"tools_run":[]}` with an empty
    # anatomy and register. 55 of 56 tool results were discarded, including
    # a statcheck run that had already found two real inconsistencies.
    #
    # Every gate downstream read healthy: `is_error` false,
    # `output_parse_path` "json_schema", `limitations` EMPTY, and the
    # adjudicator wrote "the original docket recorded no passing statistical
    # checks" as though it were a fact about the paper. The two-signature
    # check below could not see it because one surviving finding satisfied
    # the not-empty test.
    #
    # `coverage` is taken from the TOOL doc alone (see `_build`), so this is
    # scoped to that producer: a docket that filed rows off forensic tools
    # and then lists none of them is describing a report that did not
    # survive serialization, whatever its findings count says.
    truncated_docket = (
        doc is not None
        and producer == "tool_expert"
        and (doc.get("findings") or [])
        and not ((doc.get("coverage") or {}).get("tools_run") or [])
        and n_forensic >= 8
    )
    if (doc is not None and not truncated_docket
            and ((doc.get("findings") or [])
                 or (doc.get("unchecked") or []))):
        return stage, doc
    if _agent._stage_hit_budget(stage):
        return stage, doc
    if (not schema_gate_error and not truncated_docket
            and not (n_forensic == 0 or n_forensic >= 8)):
        return stage, doc
    # The schema-gate variant (measured 2026-08-22, neulet on grok): the
    # stage errored at error_max_structured_output_retries after real
    # work, transcript salvage found nothing usable, and the run would
    # otherwise proceed on the OTHER agent alone. Same bounded retry:
    # once, billed, recorded.
    what = ("ERRORED at the structured-output gate" if schema_gate_error
            else "returned a TRUNCATED report (%d finding(s), no tools "
                 "recorded in its coverage)" % len(doc.get("findings") or [])
            if truncated_docket
            else "returned an EMPTY report")
    limitations.append(
        f"the {label} stage {what} "
        f"({n_forensic} forensic calls on its ledger); retried once")
    # ANTIGRAVITY: RESUME, DON'T RESTART. agy does not force a schema-bearing
    # turn to end in `finish`, and MEASURED 2026-10-18 (apple_cider,
    # gemini-3.8-flash-medium) the tools agent stopped after declaring its
    # tables -- before a single check -- so neither branch below could help:
    # the ledger recovery has no tools and only the setup to describe, and a
    # fresh run starts over. The conversation itself was kept
    # (`llm_backend.antigravity_resume_invocation`); continue it, with its
    # context and tools, and fall through to the usual retry only if the
    # resumed turn still delivers no report.
    if schema_gate_error:
        from ..llm_backend import (MCPUnavailable, antigravity_resume_invocation,
                                   antigravity_resume_prompt, merge_resumed_stage)
        resume_inv = antigravity_resume_invocation(stage)
        if resume_inv is not None:
            try:
                resumed = await _agent._run_stage(
                    resume_inv, antigravity_resume_prompt(),
                    verbose, timeout, on_progress,
                    stage_label=f"{label}_resume")
            except (_agent.StageError, MCPUnavailable) as exc:
                limitations.append(
                    f"the {label} resume failed ({type(exc).__name__})")
                resumed = None
            if resumed is not None:
                _agent.record_spend(f"{label}_resume", resumed)
                merged = merge_resumed_stage(stage, resumed)
                doc_r, path_r = _agent._extract_json(merged)
                if doc_r is not None and ((doc_r.get("findings") or [])
                                          or (doc_r.get("unchecked") or [])):
                    merged["output_parse_path"] = path_r
                    limitations.append(
                        f"the {label} retry RESUMED the same agy conversation "
                        f"({_n_forensic(merged)} forensic calls across both "
                        "turns), which delivered the report")
                    return merged, doc_r
                limitations.append(
                    f"the resumed {label} conversation delivered no report "
                    "either; falling back to a fresh retry")
    # TWO FAILURES, TWO RESPONSES. With forensic calls on the ledger the
    # work exists and only the serialization failed, so ask for the
    # document alone from a context that is the ledger (see
    # `_ledger_recovery_prompt`). With an EMPTY ledger nothing has been
    # done and there is nothing to recover from, so the full stage is
    # re-run as before.
    if n_forensic > 0 and recover_cmd is not None:
        retry = await _agent._run_stage(
            recover_cmd(),
            _ledger_recovery_prompt(led, doc, n_forensic),
            verbose, timeout, on_progress,
            stage_label=f"{label}_retry")
        _agent.record_spend(f"{label}_retry", retry)
    else:
        correction = _producer_retry_correction(
            stage, doc, n_forensic, schema_gate_error, truncated_docket,
            first_call=_first_call(getattr(ctx, "src", None)))
        retry = await _agent._run_stage(
            cmd_builder(), prompt + correction,
            verbose, timeout, on_progress,
            stage_label=f"{label}_retry")
        _agent.record_spend(f"{label}_retry", retry)
        # A ZERO-CALL DUMP GETS ONE MORE ATTEMPT: it costs seconds, and the
        # one-retry rule lost grok2_cerebrolysin_flow_2's science agent whole.
        if (n_forensic == 0 and _n_forensic(retry) == 0
                and getattr(settings, "name", None) in ZERO_CALL_RETRY_BACKENDS):
            limitations.append(
                f"the {label} retry made no forensic calls either; retried a second time")
            retry = await _agent._run_stage(
                cmd_builder(), prompt + correction,
                verbose, timeout, on_progress,
                stage_label=f"{label}_retry2")
            _agent.record_spend(f"{label}_retry2", retry)
    recovered_from_ledger = n_forensic > 0 and recover_cmd is not None
    doc2, path2 = _agent._extract_json(retry)
    retry_truncated = (
        doc2 is not None
        and producer == "tool_expert"
        and (doc2.get("findings") or [])
        and not ((doc2.get("coverage") or {}).get("tools_run") or []))
    if doc2 is not None and not retry_truncated and (
            (doc2.get("findings") or []) or (doc2.get("unchecked") or [])):
        retry["output_parse_path"] = path2
        if recovered_from_ledger:
            return _carrying_work(retry, stage), doc2
        return retry, doc2
    # THE FULL RE-RUN DID THE WORK AND FILED NOTHING: RECOVER IT TOO.
    # MEASURED 2026-10-18, 10.1001--archpediatrics.2012.999 on grok-4.6
    # (tools_only): the first attempt took one turn and no tool call; the
    # re-run made 25 forensic calls in 7.5 min -- its MCP receipts, run slug
    # grok-4-6-8757eabf, include two `suspicious` recalc_stat_to_p results
    # -- and filed no usable document. The original zero-call attempt was
    # returned, so the work was discarded and the forensic-tools gate
    # refused the paper for making "no call (not even a reader)", which
    # was false. The ledger recovery that rescues a first attempt's work
    # is applied to the re-run's.
    n_retry = 0 if recovered_from_ledger else _n_forensic(retry)
    if (n_retry > 0 and recover_cmd is not None
            and not _agent._stage_hit_budget(retry)):
        led_retry = _agent._tool_call_ledger(retry.get("messages") or [], [])
        limitations.append(
            f"the {label} retry made {n_retry} forensic calls but filed no "
            "usable report; asked once to compose it from that ledger")
        rescue = await _agent._run_stage(
            recover_cmd(), _ledger_recovery_prompt(led_retry, doc2, n_retry),
            verbose, timeout, on_progress,
            stage_label=f"{label}_retry_recover")
        _agent.record_spend(f"{label}_retry_recover", rescue)
        doc3, path3 = _agent._extract_json(rescue)
        if doc3 is not None and (
                (doc3.get("findings") or []) or (doc3.get("unchecked") or [])):
            rescue["output_parse_path"] = path3
            return _carrying_work(rescue, retry), doc3
    if truncated_docket and doc2 is not None and (doc2.get("findings")
                                                  or doc2.get("unchecked")):
        # The retry is truncated too, but it is still a docket. Keep
        # whichever carries more rows and say the coverage is unusable --
        # discarding both would trade a stated gap for a silent one.
        if len(doc2.get("findings") or []) > len(doc.get("findings") or []):
            retry["output_parse_path"] = path2
            limitations.append(
                f"the {label} retry was truncated too; its coverage is unusable")
            if recovered_from_ledger:
                return _carrying_work(retry, stage), doc2
            return retry, doc2
    # A STAGE THAT NEVER CALLED A TOOL DID NOT EXAMINE THE PAPER.
    # MEASURED 2026-09-03 on `airforce` (grok-4.6): the tool expert took
    # one turn, 36,169 input tokens, 184 output tokens, ZERO tool calls,
    # `end_turn` in 7.4 s -- it emitted a schema-valid empty document and
    # stopped, and the retry did the same. An empty-but-valid document
    # from a stage that ran no check is indistinguishable downstream from
    # a paper with nothing wrong, which is the absence-as-evidence error
    # this repository exists to refuse. It is a REFUSAL, and it is named.
    if (n_forensic == 0 and _n_forensic(retry) == 0
            and not (doc or {}).get("findings")
            and not (doc or {}).get("unchecked")):
        stage["is_error"] = True
        stage["error_subtype"] = "no_forensic_calls"
        limitations.append(
            f"the {label} stage made NO forensic tool calls on either "
            "attempt and produced no findings -- it did not examine the "
            "paper, so its silence is OUR failure and not a result about "
            "this paper; nothing from it is merged")
        return stage, None
    limitations.append(
        f"the {label} retry was empty too; its coverage is unusable")
    if n_retry > n_forensic:
        # Its transcript is the one with the calls in it: returning the
        # zero-call attempt made the forensic-tools gate call a stage that
        # ran 25 checks one that never reached its tools.
        return retry, doc
    return stage, doc


def stage_budget_share(config, fraction: float) -> float:
    """`fraction` rescaled over the paid stages `config` runs.

    The full pipeline's three paid stages (tools agent, scientific proofreading
    agent, adjudicator) sum to 1, so it is unchanged; a pipeline without some
    of them hands their share to the stages it does run. Without a config (old
    callers) the raw fraction is returned."""
    from .. import parallel as _par
    if config is None:
        return fraction
    uses = {m.use for m in config.modules}
    shares = {
        "tools_agent": _par.TOOL_BUDGET_FRACTION,
        "scientific_proofreading_agent": _par.SCIENCE_BUDGET_FRACTION,
        "adjudicator": 1.0 - _par.TOOL_BUDGET_FRACTION - _par.SCIENCE_BUDGET_FRACTION,
    }
    total = sum(v for k, v in shares.items() if k in uses)
    return fraction / total if total > 0 else fraction


#: Backends whose analysts get the unfiled-results pass. MEASURED 2026-10-13
#: (25 eval runs, one judge): Grok tools agents filed 1 finding after 79-95
#: forensic calls in 4 of 11 runs, Claude in 0 of 10, so the pass was
#: Grok-side (and the API loop's, untested). Codex is listed for the same
#: structured-output path, and Antigravity (2026-10-18, unmeasured) for the
#: same reason. CLAUDE JOINED IN 1.91.0: on the statcheck_pvalue_errors
#: working set (2026-10-18) Sonnet's tools_only run left 56 of its own
#: suspicious-or-worse results neither filed nor dismissed -- fewer than
#: Grok's 143, not zero -- and the pass costs nothing when there are none.
UNFILED_RECOVERY_BACKENDS = frozenset({"grok", "openrouter", "codex", "antigravity", "claude"})
#: Backends whose zero-call dump gets a second full retry (`retry_if_empty`):
#: the unfiled-pass set as it stood before Claude joined it. Claude has not
#: been seen to dump an empty document, so its runs keep one retry.
ZERO_CALL_RETRY_BACKENDS = UNFILED_RECOVERY_BACKENDS - {"claude"}
#: At most this many results are sent back, most severe first.
MAX_UNFILED_ITEMS = 40
_SEVERITY_RANK = {"impossible": 0, "highly_suspicious": 1, "suspicious": 2}


def unfiled_results(ledger: list[dict], doc: dict | None,
                    receipts_list: list[dict] | None = None) -> list[dict]:
    """The analyst's own suspicious-or-worse tool results that its report
    does not account for, most severe first, one per call.

    With receipts, only calls the forensic tool layer really answered
    (`receipts.join`) are listed: the list is then exactly what our tools
    said, never a transcript artefact."""
    from ..findings_v2 import unaccounted_verdicts
    if receipts_list:
        import copy

        from .. import receipts
        ledger = copy.deepcopy(ledger)
        receipts.join(ledger, receipts_list)
        ledger = [c for c in ledger if c.get("receipt")]
    items, seen = [], set()
    for v in unaccounted_verdicts((doc or {}).get("findings"), ledger):
        key = v["call"].get("seq")
        if key in seen:
            continue
        seen.add(key)
        items.append(v)
    items.sort(key=lambda v: (_SEVERITY_RANK.get(v["severity"], 9),
                              v["call"].get("seq") or 0))
    return items


def _unfiled_prompt(items: list[dict]) -> str:
    """Ask the analyst to account for each listed result: file it, or
    dismiss it with a reason. Nothing else is written."""
    lines = []
    for i, v in enumerate(items, 1):
        call = v["call"]
        args = {k: val for k, val in (call.get("input") or {}).items()
                if k not in ("source_quote",)}
        said = ""
        try:
            parsed = json.loads(call.get("result") or "")
            said = str(parsed.get("explanation") or parsed.get("interpretation")
                       or parsed.get("note") or "")
        except (TypeError, ValueError, AttributeError):
            pass
        lines.append(
            f"{i}. `{v['tool']}` returned **{v['severity']}**"
            + (" (one row of a batch call)" if v.get("expanded") else "")
            + f"\n   arguments: {json.dumps(args, default=str)[:600]}"
            + (f"\n   the tool said: {said[:400]}" if said else ""))
    return (
        "Your findings report does not account for the tool results below. "
        "You ran each of these checks yourself, and each came back suspicious or "
        "worse; a result that is neither filed nor dismissed is lost to the "
        "review.\n\n"
        "Do not run any tools; there are none on this turn. For EACH numbered "
        "result, do exactly one of:\n"
        "- FILE it: add a finding row for it, whose `description` BEGINS with "
        "`result #N:` (N is the number below), with the tool's name as "
        "`technique`, its arguments in `inputs`, and the verbatim quote and "
        "location from the paper, exactly as your procedure says. Use "
        "`outcome` `problem` when the result stands, `undecided` when it "
        "depends on something the paper does not settle.\n"
        "- DISMISS it: add an `unchecked` entry whose `location` BEGINS with "
        "`result #N:` and names the tool and the values, and whose `reason` says "
        "why the result does not "
        "stand (wrong premise, a reporting convention, a value misread).\n\n"
        "Return a findings document that contains ONLY these new rows and "
        "entries, not your earlier findings. Do not invent results that are "
        "not listed.\n\n---\n\n## THE RESULTS TO ACCOUNT FOR\n\n"
        + "\n".join(lines))


_RESULT_NO = re.compile(r"^\s*result\s*#\s*(\d+)", re.I)


def _numbers(rows: list[dict], field: str, n_max: int) -> set[int]:
    out = set()
    for r in rows:
        m = _RESULT_NO.match(str(r.get(field) or ""))
        if m and 1 <= int(m.group(1)) <= n_max:
            out.add(int(m.group(1)))
    return out


async def recover_unfiled(ctx, settings, stage, doc, label, producer,
                          mcp_stage, recover_cmd, limitations):
    """One bounded pass: hand the analyst its unaccounted suspicious-or-worse
    results and merge what it files or dismisses into its document.

    Returns (doc, the extra call's stage or None); the stage's transcript is
    archived as `messages.<label>_unfiled.json`."""
    if (doc is None or stage is None or recover_cmd is None
            or settings.name not in UNFILED_RECOVERY_BACKENDS):
        return doc, None
    ledger = _agent._tool_call_ledger(stage.get("messages") or [], [])
    from .. import receipts
    recs = receipts.load(ctx.run_slug, mcp_stage) if ctx.run_slug else []
    items = unfiled_results(ledger, doc, recs)
    if not items:
        return doc, None
    sent = items[:MAX_UNFILED_ITEMS]
    extra = await _agent._run_stage(
        recover_cmd(), _unfiled_prompt(sent), ctx.verbose, ctx.timeout,
        ctx.on_progress, stage_label=f"{label}_unfiled")
    _agent.record_spend(f"{label}_unfiled", extra)
    add, _path = _agent._extract_json(extra)
    have = {f.get("slug") for f in doc.get("findings") or []}
    new_rows = [f for f in (add or {}).get("findings") or []
                if isinstance(f, dict) and f.get("slug") not in have]
    dismissed = [u for u in (add or {}).get("unchecked") or [] if isinstance(u, dict)]
    doc.setdefault("findings", []).extend(new_rows)
    doc.setdefault("unchecked", []).extend(dismissed)
    # EXACT ACCOUNTING, by the numbers the prompt asked for. The first
    # version counted "still unaccounted" from findings alone, so every
    # dismissal was counted twice ("6 dismissed, 6 still unaccounted").
    filed = _numbers(new_rows, "description", len(sent))
    gone = _numbers(dismissed, "location", len(sent)) - filed
    # Which calls were DISMISSED, by tool and arguments, so the run's final
    # record of unaccounted results (parallel.py) can leave them out: a
    # dismissal is an account, but it does not join a call the way a row does.
    extra["dismissed_calls"] = [
        {"tool": sent[n - 1]["tool"], "input": sent[n - 1]["call"].get("input")}
        for n in sorted(gone)]
    unnumbered = (len(new_rows) - len(filed)) + (len(dismissed) - len(gone))
    still = len(items) - len(filed) - len(gone)
    limitations.append(
        f"the {label} report did not account for {len(items)} of its own "
        f"suspicious-or-worse tool results"
        + (f" ({len(sent)} sent back, most severe first)" if len(items) > len(sent) else "")
        + f"; asked once to account for them: {len(filed)} filed, "
        f"{len(gone)} dismissed with a reason, {still} still unaccounted"
        + (f" ({unnumbered} new row(s) named no result number)" if unnumbered else ""))
    return doc, extra


class AnalystModule(Module):
    """An LLM analyst: build its command, run its stage, parse, retry once.

    Subclasses state what differs -- label, producer, role, allowlist,
    schema, user prompt, budget share, internet -- and nothing else. The
    whole of `run` happens inside this module's own task, so two analysts
    parse and retry concurrently; the core merges their limitations in
    canonical order.
    """

    label: str = ""
    producer: str = ""
    mcp_stage: str = ""
    budget_fraction: float | None = None
    internet: bool = False
    #: The tools agent's wrapper records its own spend per attempt.
    records_own_spend: bool = False
    #: Refuse a document from an agent whose attempts, retries included,
    #: made no call on its forensic allowlist (see `run`).
    requires_forensic_calls: bool = False

    # -- what a subclass states --------------------------------------------
    def allowed_tools(self, ctx) -> list[str]:
        raise NotImplementedError

    def json_schema(self, ctx) -> dict:
        return prompts.producer_findings_schema(self.producer)

    def user_prompt(self, ctx) -> str:
        raise NotImplementedError

    def mcp_tools(self, ctx) -> list[str] | None:
        return None

    async def run_stage(self, ctx, settings, build_cmd, prompt):
        return await _agent._run_stage(
            build_cmd(), prompt, ctx.verbose, ctx.timeout, ctx.on_progress,
            stage_label=self.label)

    def after(self, ctx, stage, doc, limitations) -> None:
        """A hook after parse and retry (the tools agent states a coverage gap)."""

    # -- shared --------------------------------------------------------------
    def budget(self, ctx) -> float | None:
        """This analyst's cap: its fraction of the per-paper budget, scaled to
        the paid stages the pipeline actually runs (`stage_budget_share`).

        The fractions (tools 0.40, science 0.25, the adjudicator the rest)
        assume all three run. Applied raw, a `tools_only` run capped its only
        agent at 40% of `--max-budget-usd`: on 2026-10-18 two GRIM dev papers were
        cut off at ~$1.25 of $3 with 60% of the budget unspent."""
        if ctx.budget_usd and self.budget_fraction is not None:
            return ctx.budget_usd * stage_budget_share(ctx.config, self.budget_fraction)
        return None

    def build_cmd(self, ctx, settings, *, recover: bool = False):
        extra = {} if self.mcp_tools(ctx) is None else {"mcp_tools": self.mcp_tools(ctx)}
        if recover:
            # Document-only: the producer's schema, no forensic tools, one turn.
            return _agent._build_claude_cmd(
                system_prompt=ctx.system_prompts.get(self.label) or "",
                allowed_tools=list(_agent.BUILTIN_TOOLS), model=settings.model,
                effort=settings.effort, json_schema=self.json_schema(ctx),
                budget_usd=self.budget(ctx), paper_dir=ctx.paper_dir,
                backend=settings.name, mcp_stage=self.mcp_stage,
                run_slug=ctx.run_slug, max_turns=1, **extra)
        access = self.tool_access(ctx)
        return _agent._build_claude_cmd(
            system_prompt=ctx.remember(self.label, prompts.system_prompt_for(
                ctx.config, self.name,
                grok_mcp_route=(settings.name == "grok" and access != "skill"))),
            allowed_tools=self.allowed_tools(ctx), model=settings.model,
            effort=settings.effort, json_schema=self.json_schema(ctx),
            budget_usd=self.budget(ctx), paper_dir=ctx.paper_dir,
            backend=settings.name,
            **({"internet": True} if self.internet else {}),
            **({"tool_access": access} if access != "mcp" else {}),
            mcp_stage=self.mcp_stage, run_slug=ctx.run_slug, **extra)

    def tool_access(self, ctx) -> str:
        """This module's `tool_access` (docs/specs/tool_access.md)."""
        spec = ctx.config.module(self.name) if ctx.config is not None else None
        return getattr(spec, "tool_access", "mcp")

    async def run(self, ctx, needed) -> ModuleResult:
        settings = ctx.settings_for(self.name)
        limitations: list[str] = []
        prompt = self.user_prompt(ctx)

        def build():
            return self.build_cmd(ctx, settings)
        try:
            try:
                stage = await self.run_stage(ctx, settings, build, prompt)
            finally:
                # Stop this line's clock even when the agent DIES, so its
                # status line does not keep counting as though still working.
                _agent._safe_on_progress(ctx.on_progress,
                                         {"stage": self.label, "done": True})
        except Exception as exc:  # noqa: BLE001 -- one analyst must not sink the run
            limitations.append(f"the {self.label} stage failed "
                               f"({type(exc).__name__}: {exc})")
            return ModuleResult(self.name, limitations=limitations)
        if stage is not None and self.budget(ctx) is not None:
            stage["budget_cap_usd"] = self.budget(ctx)
        if stage is not None and not self.records_own_spend:
            _agent.record_spend(self.label, stage)
        doc = await parse_output(ctx, settings, stage, self.label,
                                 self.producer, limitations)
        worked = stage            # the attempt that ran the tools
        stage, doc = await retry_if_empty(
            ctx, settings, stage, doc, self.label, self.producer, build, prompt,
            limitations, recover_cmd=lambda: self.build_cmd(ctx, settings, recover=True))
        if stage is not worked and _n_work_calls(
                _agent._tool_call_ledger((stage or {}).get("messages") or [], []),
                self.producer) > _n_work_calls(
                _agent._tool_call_ledger((worked or {}).get("messages") or [], []),
                self.producer):
            # The retry did the work (or carries it): the unfiled pass and the
            # gate below read ITS ledger, not the empty first attempt's.
            worked = stage
        doc, unfiled_stage = await recover_unfiled(
            ctx, settings, worked, doc, self.label, self.producer, self.mcp_stage,
            lambda: self.build_cmd(ctx, settings, recover=True), limitations)
        if (self.requires_forensic_calls and doc is not None
                and not _made_forensic_calls(self.allowed_tools(ctx),
                                             worked, stage)):
            # THE FORENSIC-TOOLS GATE, AFTER THE RETRIES. The stage wrapper's
            # `_assert_forensic_tools_ran` only checks the legacy labels
            # `sweep`/`analysis`, so in the parallel pipeline (label
            # `tool_agent`) it never fired: a tools agent that never reached
            # its tools could file a document that read as a checked paper.
            # Checked here rather than in the wrapper so the zero-call retry
            # (`retry_if_empty`) gets its chance first. MEASURED 2026-10-13
            # (branch confident-chandrasekhar, superseded by this): a codex
            # tools agent on `10.1007--s00702-003-0025-7` (v1.68.0) made 0
            # calls, wrote "the forensic MCP tools were not available" into
            # `unchecked`, and sealed `is_error: false`; of 40 archived
            # parallel tool-agent ledgers, three were at zero calls.
            limitations.append(
                f"the {self.label} stage made no call on its forensic tool "
                "list (not even a reader), so its report was REFUSED: that is "
                "a plumbing failure, not a paper with nothing to check")
            doc = None
        self.after(ctx, stage, doc, limitations)
        return ModuleResult(self.name, stage=stage, doc=doc,
                            limitations=limitations,
                            extra={"settings": settings,
                                   **({"unfiled_stage": unfiled_stage}
                                      if unfiled_stage else {})})
