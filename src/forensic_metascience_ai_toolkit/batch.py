"""
Run the Forensic Metascience AI Toolkit on a batch of paper directories.

Each input subdirectory should contain at least body.md and/or a PDF
(matching the cerebrolysin_papers/ layout). For each paper analyzed, a
forensic_review/ subdirectory is created inside the paper's own directory
containing report.md, findings.json, run_meta.json, and slimmed message logs.

Per-paper cost/verdict rows are appended to <corpus>/batch_costs.jsonl;
failures are appended to <corpus>/failed.jsonl for retry; runs where a stage
errored but a usable report was still produced go to <corpus>/partial.jsonl.

Long runs are protected by the usage guard (see forensic_metascience_ai_toolkit/usage_guard.py):
the batch pauses rather than burning papers against a spent 5-hour session limit.

Usage:
    python -m forensic_metascience_ai_toolkit.batch cerebrolysin_papers --limit 3
    python -m forensic_metascience_ai_toolkit.batch cerebrolysin_papers --limit 20 --concurrency 4
    python -m forensic_metascience_ai_toolkit.batch cerebrolysin_papers --max-budget-usd 2.0 --timeout 1800
    python -m forensic_metascience_ai_toolkit.batch cerebrolysin_papers --usage-threshold 70
"""

import argparse
import asyncio
import datetime
import functools
import json
import math
import os
import random
import shutil
import sys
import traceback
from pathlib import Path

DONE_SUBDIR = "done"
#: Corpus scaffolding. `pick_papers` must not treat these as a paper. `priority/`
#: holds a pre-run queue; pass that folder itself as `corpus` to run it.
SKIP_SUBDIRS = frozenset({
    "done", "failed", "logs", "reviews", "blinded", "priority",
    "prioritized_cerebrolysin_papers", "already_retracted", "retracted",
})

from forensic_metascience_ai_toolkit.agent import (
    DEFAULT_EFFORT, STAGE1_TOOLS, analyze_paper, completed_review,
    _tool_call_ledger,
)
from forensic_metascience_ai_toolkit.parallel import write_parallel_outputs
from forensic_metascience_ai_toolkit.llm_backend import (
    BackendUnavailable, BudgetUnsupported, ForensicToolsNeverRan,
    fatal_backend_reason,
)
from forensic_metascience_ai_toolkit.preflight import PreflightError
from forensic_metascience_ai_toolkit.progress import (
    CURRENT_PAPER, BatchGrid, LiveBatchStatus, prefix_stdout_by_paper,
)
from forensic_metascience_ai_toolkit.usage_guard import WeeklyLimitReached
from forensic_metascience_ai_toolkit.usage_guard import guard as usage_guard


async def probe_backend(backend_name: str | None, timeout: int = 90) -> str | None:
    """One tiny call before any paper starts. Returns a refusal reason or None.

    `batch` is the spend gate, so it is the right place for a live check and the
    ONLY place: `_run_stage` must stay free of billing probes, or a ten-paper
    run makes thirty of them.

    Fails OPEN. A probe that cannot reach the network, times out, or returns
    something unparseable must not stop a batch -- its job is to convert an
    account-level refusal from ten tracebacks into one line, not to become a
    new way for runs to die. Only an explicit fatal marker in the output counts.
    """
    from forensic_metascience_ai_toolkit.llm_backend import resolve_backend

    be = resolve_backend(backend_name)
    binary = shutil.which(be.binary)
    if not binary:
        return None                    # preflight already covers a missing CLI
    # Print-mode differs per CLI: claude reads the prompt from stdin behind
    # `-p`, grok takes it as the VALUE of `--single` (aliased `--print`).
    # Passing `--print` with the prompt as a separate argv entry makes grok
    # exit with "a value is required for '--single'" -- which carries no fatal
    # marker, so the probe failed open and the batch ran anyway. Codex reads
    # stdin behind an explicit `-` sentinel; the probe is a real tiny spend
    # because only a spend attempt surfaces an exhausted balance (a logged-out
    # codex was measured emitting "401 Unauthorized" here, 2026-09-01), and it
    # runs read-only, ephemeral, and outside any git repo on purpose.
    if be.name == "claude":
        argv, stdin_text = [binary, "-p", "--model", be.default_model], b"ping"
    elif be.name == "codex":
        argv, stdin_text = (
            [binary, "exec", "--ignore-user-config", "--skip-git-repo-check",
             "--ephemeral", "-s", "read-only", "--disable", "shell_snapshot",
             "-m", be.default_model,
             "-c", 'model_reasoning_effort="low"', "-"],
            b"ping",
        )
    elif be.name == "antigravity":
        # `/usage` is answered without a model turn (free), and a logged-out
        # or locked-keyring agy fails it with its authentication sentence.
        # An exhausted quota is the usage guard's job, not this probe's.
        argv, stdin_text = [binary, "-p", "/usage", "--output-format", "json"], b""
    else:
        argv, stdin_text = [binary, "--single", "ping",
                            "--model", be.default_model], b""
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, err = await asyncio.wait_for(proc.communicate(stdin_text),
                                          timeout=timeout)
    except Exception:                                          # noqa: BLE001
        return None                    # fail open, deliberately
    return fatal_backend_reason(
        out.decode("utf-8", "replace") + err.decode("utf-8", "replace"))


def _write_outputs(result: dict, out_dir: Path, paper: Path | None = None) -> None:
    """Write the review layout. One pipeline, one writer since v1.27.0.

    `paper` is kept in the signature because callers pass it and it costs
    nothing; the parallel writer resolves the paper from the result.
    """
    write_parallel_outputs(result, out_dir)


def pick_papers(corpus: Path, limit: int, seed: int | None) -> list[Path]:
    """Pick paper subdirectories from corpus, excluding scaffolding dirs.

    A dot folder is the toolkit's own state, never a paper: `run_batch` writes
    the run archive `.analysis_runs/` into the corpus root, so every batch after
    the first counted it as a paper with no full text ("papers found 11" on a
    ten-paper corpus, "SKIP .analysis_runs"), which `discovery` already refuses.
    Only the dot is excluded: a real paper folder that holds no readable text
    is still picked, so the plan counts it and names it.
    """
    candidates = sorted(
        p for p in corpus.iterdir()
        if p.is_dir() and p.name not in SKIP_SUBDIRS
        and not p.name.startswith(".")
    )
    if seed is not None:
        random.Random(seed).shuffle(candidates)
    return candidates[:limit]


def _append_jsonl(path: Path, row: dict) -> None:
    with path.open("a") as f:
        f.write(json.dumps(row, default=str) + "\n")


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


_DUMP_TEXT_CAP = 8000


def _capped_text(value, cap: int = _DUMP_TEXT_CAP):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        try:
            text = json.dumps(value, default=str)
        except (TypeError, ValueError):
            text = str(value)
    else:
        text = str(value)
    if len(text) <= cap:
        return value if isinstance(value, (dict, list)) else text
    return text[:cap] + f"\n… truncated {len(text) - cap} chars"


def _init_tools(messages: list) -> list | None:
    for ev in messages:
        if not isinstance(ev, dict):
            continue
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            tools = ev.get("tools")
            return list(tools) if isinstance(tools, list) else tools
    return None


def _assistant_text_excerpt(messages: list) -> str | None:
    chunks = []
    for ev in messages:
        if not isinstance(ev, dict) or ev.get("type") != "assistant":
            continue
        content = (ev.get("message") or {}).get("content") or []
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                chunks.append(str(block.get("text") or ""))
    if not chunks:
        return None
    return _capped_text("\n".join(chunks), cap=2000)


def _cost_fields_from_refuse(exc: ForensicToolsNeverRan) -> dict:
    """Sum last attempt + any Grok empty-dump retry so the refuse is billed."""
    stages = list(getattr(exc, "prior_stages", None) or [])
    if getattr(exc, "stage", None):
        stages.append(exc.stage)
    return {
        "total_cost_usd": round(
            sum(float(s.get("cost_usd") or 0) for s in stages), 6),
        "input_tokens": sum(int(s.get("input_tokens") or 0) for s in stages),
        "output_tokens": sum(int(s.get("output_tokens") or 0) for s in stages),
        "cache_creation_input_tokens": sum(
            int(s.get("cache_creation_input_tokens") or 0) for s in stages),
        "cache_read_input_tokens": sum(
            int(s.get("cache_read_input_tokens") or 0) for s in stages),
        "total_wall_seconds": round(
            sum(float(s.get("wall_seconds") or 0) for s in stages), 2),
        "n_attempts": len(stages) or 1,
    }


def _dump_forensic_tools_never_ran(
    paper: Path, subdir: str, exc: ForensicToolsNeverRan,
) -> Path | None:
    """Write a diagnostic so a 0-tool sweep is inspectable.

    The refuse is correct -- a clean review from a sweep that called no
    forensic tool is the failure this gate exists to stop. The traceback
    alone is not: measured 2026-08-20, grok returned in ~19 s with nothing
    on disk to say whether MCP was missing, the model only used read_file,
    or the stream never parsed. Measured the same day: the dump omitted
    `result`/`structured_output`, so the empty findings skeleton (173
    tokens, `tools_run: []`) was only recoverable from ~/.grok/sessions
    after the sandbox was deleted.
    """
    stage = getattr(exc, "stage", None) or {}
    out_dir = paper / subdir
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    messages = stage.get("messages") or []
    try:
        ledger = _tool_call_ledger(messages, STAGE1_TOOLS)
    except Exception:  # noqa: BLE001 -- a dump must not raise over a refuse
        ledger = []
    event_summary = []
    for ev in messages[:80]:
        if not isinstance(ev, dict):
            continue
        row: dict = {"type": ev.get("type")}
        content = (ev.get("message") or {}).get("content") or []
        tools = []
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tools.append(block.get("name"))
        if tools:
            row["tools"] = tools
        event_summary.append(row)
    prior = getattr(exc, "prior_stages", None) or []
    payload = {
        "error": str(exc),
        "n_messages": len(messages),
        "n_attempts": 1 + len(prior),
        "mcp_discovery": stage.get("mcp_discovery"),
        "init_tools": _init_tools(messages),
        "llm_backend": stage.get("llm_backend"),
        "error_subtype": stage.get("error_subtype"),
        "stop_reason": stage.get("stop_reason"),
        "num_turns": stage.get("num_turns"),
        "current_tool": stage.get("current_tool"),
        "tool_calls": stage.get("tool_calls"),
        "input_tokens": stage.get("input_tokens"),
        "output_tokens": stage.get("output_tokens"),
        "wall_seconds": stage.get("wall_seconds"),
        "result": _capped_text(stage.get("result")),
        "text": _capped_text(stage.get("text"), cap=2000),
        "structured_output": _capped_text(stage.get("structured_output")),
        "assistant_text": _assistant_text_excerpt(messages),
        "ledger_tools": [
            {"tool": r.get("tool_short"), "surface": r.get("surface")}
            for r in ledger
        ],
        "event_summary": event_summary,
    }
    path = out_dir / "forensic_tools_never_ran.json"
    try:
        path.write_text(json.dumps(payload, default=str, indent=2) + "\n")
    except OSError:
        return None
    # The sandbox is already gone; persist the stream so the empty dump
    # does not live only under ~/.grok/sessions/.
    try:
        (out_dir / "messages.stage1.json").write_text(
            json.dumps(messages, default=str) + "\n")
    except OSError:
        pass
    return path


def _bill(progress: dict, amount) -> None:
    """Add one paper's recorded spend to THIS batch's running total.

    The batch summary used to re-read `batch_costs.jsonl` and sum every row
    whose paper was in this batch, but that ledger is the corpus's whole
    history: on the GRIM dev set (2026-10-18) the third ten-paper batch printed
    "Batch cost: $26.47" for papers that cost $9.53, because each name also
    matched both earlier batches' rows. Summed here, from what this process
    itself recorded, it can only describe this run.
    """
    try:
        progress["cost_usd"] = progress.get("cost_usd", 0.0) + float(amount or 0)
    except (TypeError, ValueError):
        pass


def _verdict_label(result: dict, pipeline=None) -> str:
    """What the per-paper line says in place of a verdict.

    Only the adjudicator writes a paper verdict. A pipeline without one
    (`tools_only`), or a run whose adjudicator was skipped, printed
    "verdict: -", which reads as a blank rather than as a statement that the
    findings were never adjudicated and their severities are provisional.
    `pipeline` is the batch's config (None: the complete review, which has an
    adjudicator).
    """
    verdict = result.get("verdict")
    if verdict:
        return str(verdict)
    if pipeline is not None and not pipeline.has("adjudicator"):
        return "none -- this pipeline has no adjudicator; severities provisional"
    adj = (result.get("findings_v2") or {}).get("adjudication") or {}
    if adj.get("ran") is False:
        if adj.get("failure"):
            return "none -- the adjudicator failed; severities provisional"
        return "none -- not adjudicated; severities provisional"
    return "none recorded"


async def process_paper(
    paper: Path,
    args: argparse.Namespace,
    done_dir: Path,
    costs_path: Path,
    failed_path: Path,
    partial_path: Path,
    sem: asyncio.Semaphore,
    progress: dict,
    monitor: LiveBatchStatus | None = None,
) -> tuple[str, str]:
    """Analyze one paper. Returns (paper_name, status) where status is
    'ok', 'partial', 'skip', or 'fail'. 'partial' means a stage errored but a
    complete, usable report was still written -- degraded, not lost."""
    stem = paper.name
    out_dir = paper / args.subdir_name
    report_path = out_dir / "report.md"

    # Shares `completed_review` with `metascience batch` so the two cannot
    # disagree about what "already analysed" means. It matches the whole
    # `<subdir_name>*` family, which is what an `analyze` run writes.
    # The same backend and model only: a different model is a new experiment.
    from forensic_metascience_ai_toolkit.llm_backend import resolve_backend
    _be = resolve_backend(getattr(args, "backend", None))
    existing = completed_review(paper, args.subdir_name,
                                pipeline=_pipeline(args), backend=_be.name,
                                model=args.model or _be.default_model)
    if args.skip_existing and existing is not None:
        from forensic_metascience_ai_toolkit.analysis_runs import Archive, read
        from forensic_metascience_ai_toolkit.history_runtime import CONTEXT
        from forensic_metascience_ai_toolkit.analysis_history import import_reports
        context = CONTEXT.get()
        if context.get("execution_id"):
            archive = Archive(context["root"])
            import_reports(archive, [paper], {"imported": 0, "errors": []})
            saved_uid = read(existing / "findings.v2.json", {}).get("run_id")
            if saved_uid and (archive.base / "runs" / f"{saved_uid}.json").exists():
                archive.reuse(context["execution_id"], saved_uid)
                for record in read(archive.base / "index.json", {"runs": {}})["runs"].values():
                    if record.get("parent_run_id") == saved_uid:
                        archive.reuse(context["execution_id"], record["id"])
        print(f"SKIP  {stem}")
        print(f"      already analysed ({existing / 'report.md'})")
        return (stem, "skip")

    async with sem:
        # Pause the whole worker pool if session usage crosses the threshold,
        # BEFORE spending the call. analyze_paper() guards internally too, but
        # keeping it explicit here means a batch stays protected even if that
        # internal hook is ever refactored away. Concurrent workers serialize
        # on the guard's lock and pause together. Tune with
        # METASCIENCE_USAGE_THRESHOLD / METASCIENCE_USAGE_INTERVAL_MIN.
        #
        # MUST pass backend= -- omitting it used to default to probing
        # Claude's own /usage regardless of --backend grok. Grok has no probe
        # (Backend.supports_usage_probe=False) so guard() is a no-op for it,
        # but the unguarded default silently checked the OPERATOR's separate
        # Claude Code account instead. Measured 2026-08-19: that account's
        # weekly quota was at 100%, so a --backend grok batch raised
        # WeeklyLimitReached on paper 1 -- BEFORE the try/except below that
        # would have handled it -- while paper 2 had already started a
        # concurrent _run_text_track() task. The uncaught raise propagated
        # through asyncio.gather() (which does not cancel sibling tasks) and
        # crashed run_batch with that task still in flight, which is what
        # asyncio.run()'s teardown then hung trying to unwind.
        await usage_guard(backend=getattr(args, "backend", None))
        lock = progress.get("lock")
        if lock is not None:
            async with lock:
                progress["started"] += 1
                n = progress["started"]
        else:
            progress["started"] += 1
            n = progress["started"]
        if monitor is None or not monitor.live:
            print(f"\n[{n}/{progress['total']}] {stem}")
        if monitor is not None:
            monitor.begin(stem)
        # Names this paper for everything its task prints (`-v` prefixing).
        paper_token = CURRENT_PAPER.set(stem)

        def _on_progress(snapshot: dict) -> None:
            if monitor is not None:
                monitor.update(stem, snapshot)

        try:
            result = await analyze_paper(
                str(paper),
                verbose=args.verbose,
                timeout=args.timeout,
                mode=args.mode,
                budget_usd=args.budget_usd,
                model=args.model,
                effort=args.effort,
                image_forensics=getattr(args, "image_forensics", True),
                text_forensics=getattr(args, "text_forensics", True),
                backend=getattr(args, "backend", None),
                on_progress=None if args.verbose else _on_progress,
                pipeline=_pipeline(args),
            )
        except (PreflightError, BudgetUnsupported, BackendUnavailable) as e:
            # An environment / invocation fault, not a property of this paper.
            # Recording it per-paper would fill failed.jsonl with papers whose
            # "failure" was a missing library, a Grok+--max-budget-usd combination,
            # or an exhausted API balance, and retrying cannot fix any of those
            # -- so it stops the batch and is deliberately NOT written to the
            # retry queue.
            #
            # BackendUnavailable joined this tuple 2026-08-23, after a grok run
            # with no xAI credit produced twenty identical 402s, ten tracebacks
            # and ten failed.jsonl rows naming papers that were never analysed.
            print(f"\n  STOPPED at {stem}: {e}")
            print("  No paper was analysed. Fix the environment and re-run the "
                  "same command; completed papers are skipped.")
            raise
        except WeeklyLimitReached as e:
            # NOT a per-paper failure, and it must not fall through to the
            # generic handler below: every remaining paper would then be
            # attempted and recorded as failed, filling the retry queue with
            # papers that were never tried against a quota that is simply spent.
            _append_jsonl(failed_path, {
                "paper": stem, "reason": f"weekly quota reached: {e}",
                "retryable": True, "when": _now(),
            })
            print(f"\n  STOPPED at {stem}: {e}")
            print("  Remaining papers were not attempted. Re-run the same "
                  "command once the weekly window resets; papers already "
                  "completed are skipped.")
            raise
        except asyncio.TimeoutError:
            _append_jsonl(failed_path, {
                "paper": stem, "reason": f"timeout after {args.timeout}s",
                "when": _now(),
            })
            print(f"  FAILED (timeout): {stem}")
            return (stem, "fail")
        except ForensicToolsNeverRan as e:
            dump = _dump_forensic_tools_never_ran(paper, args.subdir_name, e)
            cost = _cost_fields_from_refuse(e)
            _append_jsonl(failed_path, {
                "paper": stem, "reason": str(e), "when": _now(),
                "diagnostic": str(dump) if dump else None,
                "retryable": True,
                **cost,
            })
            _append_jsonl(costs_path, {
                "paper": stem,
                "when": _now(),
                "mode": args.mode,
                "model": args.model,
                "effort": args.effort,
                "refused": "forensic_tools_never_ran",
                **cost,
            })
            _bill(progress, cost.get("total_cost_usd"))
            print(f"  FAILED: {stem}: {e}")
            if dump:
                print(f"  diagnostic -> {dump}")
            return (stem, "fail")
        except Exception as e:
            _append_jsonl(failed_path, {
                "paper": stem, "reason": str(e), "when": _now(),
            })
            print(f"  FAILED: {stem}: {e}")
            traceback.print_exc()
            return (stem, "fail")
        finally:
            if monitor is not None:
                monitor.end(stem)
            stream = sys.stdout
            if hasattr(stream, "flush_paper"):
                stream.flush_paper(stem)
            CURRENT_PAPER.reset(paper_token)

    # Success criterion: no CLI error, plus the findings-v2 document. The
    # report is RENDERED from that document at write time, so an empty
    # `report` key is not a failure signal (it was, for the serial pipeline
    # removed in v1.27.0, whose report came from the model).
    findings_ok = result.get("findings_v2") is not None
    report_ok = True
    if not report_ok or not findings_ok:
        reason = "empty report" if not report_ok else "findings JSON unparseable"
        # Keep whatever we got for debugging, but flag the failure.
        _write_outputs(result, out_dir, paper)
        _append_jsonl(failed_path, {
            "paper": stem, "reason": reason, "when": _now(),
            "cost_usd": result.get("total_cost_usd"),
        })
        _bill(progress, result.get("total_cost_usd"))
        print(f"  FAILED ({reason}): {stem}")
        return (stem, "fail")

    # A STAGE THAT ERRORED BUT STILL YIELDED A FULL REPORT IS DEGRADED, NOT
    # FAILED, AND FILING IT UNDER "FAILED" LOSES WORK THAT WAS PAID FOR.
    #
    # `result["is_error"]` is `stage1.is_error or stage2.is_error`, so a sweep
    # that exhausted its structured-output retries marked the whole paper
    # failed even when the editorial stage recovered and wrote a complete
    # report. MEASURED: `10.1111--j.1468-1331.2010.03092.x` cost $6.02, has a
    # verdict, a report.md, a report.pdf and four findings -- and sat in
    # failed.jsonl, where nobody looks, described as though nothing had been
    # produced. The report itself already announces its own degradation (the
    # PARTIAL COVERAGE limitation), so the batch summary was the only place
    # claiming total loss.
    #
    # Reported as its own status: not silently promoted to `ok`, because a
    # sweep that died IS a real coverage gap and a reader must see it.
    # Falls THROUGH rather than returning: a partial run still owes a
    # batch_costs.jsonl row (it was billed, and a summary that omits it
    # understates the batch) and still owes its outputs. Only the move to
    # `done/` is withheld, so a degraded paper stays where someone will see it.
    partial_detail = ""
    if result.get("is_error"):
        _stages = (result.get("run_meta") or {}).get("stages") or {}
        broken = [name for name, s in _stages.items() if s.get("is_error")]
        subtypes = {name: s.get("error_subtype") for name, s in _stages.items()
                    if s.get("is_error") and s.get("error_subtype")}
        partial_detail = ", ".join(
            f"{n} ({subtypes[n]})" if n in subtypes else n
            for n in broken) or "a stage reported is_error"
        _append_jsonl(partial_path, {
            "paper": stem,
            "reason": f"stage error but report written: {partial_detail}",
            "when": _now(), "cost_usd": result.get("total_cost_usd"),
            "stages_errored": broken,
        })

    # `paper` IS REQUIRED FOR THE VALUE REGISTER on the legacy write path.
    # Omitting it does not degrade the register, it SKIPS it -- see the guard
    # in the review writer.
    _write_outputs(result, out_dir, paper)
    meta = result.get("run_meta", {})
    stages = meta.get("stages", {}) or {}
    # Which model actually carried the bill, not merely which alias was asked
    # for -- `_resolved_models` exists because a run recorded as one model can be
    # billed to another after a refusal fallback.
    billed = sorted({s.get("primary_billed_model") for s in stages.values()
                     if s.get("primary_billed_model")})
    _append_jsonl(costs_path, {
        "paper": stem,
        "when": _now(),
        "mode": args.mode,
        # WITHOUT `model` this ledger cannot be split by model, so a corpus run
        # partly on each yields one blended average that describes neither, and
        # the batch cost estimator silently prices one model from the other's
        # history. See `_corpus_mean_cost` in cli.py.
        "model": args.model,
        "primary_billed_model": billed[0] if len(billed) == 1 else (billed or None),
        "effort": args.effort,
        "total_cost_usd": result.get("total_cost_usd"),
        "input_tokens": result.get("input_tokens"),
        "output_tokens": result.get("output_tokens"),
        # Cache tokens ARE the spend on this workload -- a representative sweep
        # read 3.06M cached against 261K created and only 30 plain input tokens.
        # Recording only `input_tokens` made the ledger read as if almost nothing
        # had been sent.
        "cache_creation_input_tokens": sum(
            int(s.get("cache_creation_input_tokens") or 0) for s in stages.values()),
        "cache_read_input_tokens": sum(
            int(s.get("cache_read_input_tokens") or 0) for s in stages.values()),
        # `_print_batch_usage` has always summed this field to print "total
        # runtime"; nothing ever wrote it, so the row was permanently 0 and
        # suppressed by its own `if secs:`. `analyze_paper` returns it.
        "total_wall_seconds": result.get("total_wall_seconds"),
        "verdict": result.get("verdict"),
        "confidence": result.get("confidence"),
        "stages": {
            name: {
                "cost_usd": s.get("cost_usd"),
                "wall_seconds": s.get("wall_seconds"),
                "output_parse_path": s.get("output_parse_path"),
            }
            for name, s in stages.items()
        },
    })
    _bill(progress, result.get("total_cost_usd"))
    label = "PARTIAL" if partial_detail else "OK"
    print(f"  {label} -> {report_path} (verdict: {_verdict_label(result, _pipeline(args))}, "
          f"${float(result.get('total_cost_usd') or 0):.4f})")
    if partial_detail:
        print(f"       degraded: {partial_detail}; the report is usable but "
              "its coverage is incomplete -- left in place, not archived")
        return (stem, "partial")

    if not args.no_move_to_done:
        target = done_dir / stem
        if target.exists():
            print(f"  WARN: {target} already exists; skipping move")
        else:
            shutil.move(str(paper), str(target))
            print(f"  moved -> {target}")

    return (stem, "ok")


from forensic_metascience_ai_toolkit.image_plugin import available as _image_available, load as _image_load

if _image_available():
    # Shared image CPU/memory budgets across papers (the image package's).
    managed_run = _image_load("image_forensics.image_resources").managed_run
else:
    def managed_run(fn):
        return fn


@managed_run
async def run_batch(args: argparse.Namespace, papers: list[Path] | None = None) -> int:
    if getattr(args, "dry_run", False):
        return await _run_batch_impl(args, papers)
    from forensic_metascience_ai_toolkit.analysis_runs import Archive, provenance
    from forensic_metascience_ai_toolkit.history_runtime import CONTEXT
    history = Archive(args.corpus)
    execution = history.execution("comprehensive", name="Comprehensive batch", components=["comprehensive", "image_forensics", "copy_paste", "tool_expert", "science_error", "adjudicator"], configuration={k:str(v) for k,v in vars(args).items()}, provenance=provenance("comprehensive"))
    token = CONTEXT.set({"root":str(history.root),"execution_id":execution["id"]})
    try:
        result = await _run_batch_impl(args,papers)
        history.finish_execution(execution["id"], "completed" if result == 0 else "incomplete")
        return result
    except BaseException:
        history.finish_execution(execution["id"], "failed")
        raise
    finally:
        CONTEXT.reset(token)


async def _run_batch_impl(args: argparse.Namespace,
                    papers: list[Path] | None = None) -> int:
    # `papers=` is the list the CLI already gated (no full text, incomplete
    # supplement, already analysed). Re-picking from the corpus here used to
    # ignore that table: "to run: 3" then "Analyzing 6 papers".
    if papers is None:
        papers = pick_papers(args.corpus, args.limit, args.seed)
    else:
        papers = list(papers)
    if not papers:
        print(f"No paper directories found in {args.corpus}", file=sys.stderr)
        return 1

    done_dir = args.corpus / DONE_SUBDIR
    if not args.no_move_to_done:
        done_dir.mkdir(exist_ok=True)

    costs_path = args.corpus / "batch_costs.jsonl"
    failed_path = args.corpus / "failed.jsonl"
    # Paid-for output that a stage error degraded but did not destroy.
    partial_path = args.corpus / "partial.jsonl"

    reason = await probe_backend(getattr(args, "backend", None))
    if reason:
        print(f"\nBACKEND UNAVAILABLE ({reason}). Nothing was analysed and "
              f"nothing was spent.")
        print("Every paper would fail identically and retrying cannot fix it, "
              "so the batch stops\nhere rather than producing one traceback "
              "per paper. Fix the account and re-run\nthe same command; "
              "completed papers are skipped and the extraction cache is kept.")
        return 2

    print(f"Analyzing {len(papers)} papers from {args.corpus}")
    print(f"  mode={args.mode}, concurrency={args.concurrency}, "
          f"timeout={args.timeout}s, budget=${args.budget_usd or '∞'}/paper")
    print(f"  reports -> <paper>/{args.subdir_name}/")
    print(f"  costs   -> {costs_path}")
    if not args.no_move_to_done:
        print(f"  archive -> {done_dir}/")
    print("=" * 70)

    sem = asyncio.Semaphore(args.concurrency)
    progress = {"started": 0, "total": len(papers), "lock": asyncio.Lock(),
                "cost_usd": 0.0}
    # Verbose streams tool text; a Live grid would fight it, so -v gets
    # neither and instead prefixes every streamed line with its paper when
    # more than one paper is in flight. Otherwise: the grid on a TTY, and on a
    # redirected stderr one plain line per (paper, stage) every 15 s.
    # `live=None` is what asks for that TTY check -- this used to pass
    # `live=not args.verbose`, which forced Rich Live onto a redirected
    # stream, where a transient Live prints nothing at all.
    monitor = BatchGrid(total=len(papers),
                        live=False if args.verbose else None,
                        periodic_log=not args.verbose)

    async def _tracked(p):
        name, status = await process_paper(
            p, args, done_dir, costs_path, failed_path, partial_path, sem,
            progress, monitor=monitor)
        monitor.record(name, status)
        return name, status

    with prefix_stdout_by_paper(enabled=args.verbose
                                and args.concurrency > 1), monitor:
        results = await asyncio.gather(*(_tracked(p) for p in papers))

    succeeded = [n for n, s in results if s == "ok"]
    skipped = [n for n, s in results if s == "skip"]
    failed = [n for n, s in results if s == "fail"]
    partial = [n for n, s in results if s == "partial"]

    # This run's spend only; the corpus's whole history is the "Usage for
    # this corpus (all recorded runs)" table printed after this. See `_bill`.
    total_cost = progress["cost_usd"]

    print("\n" + "=" * 70)
    print(f"Done. Succeeded: {len(succeeded)}, Partial: {len(partial)}, "
          f"Skipped: {len(skipped)}, Failed: {len(failed)}. "
          f"Batch cost (this run): ${total_cost:.2f}")
    for name in succeeded:
        print(f"  ok   {name}")
    for name in partial:
        print(f"  PART {name} -- a stage errored; the report was still written "
              f"and is usable (see {partial_path})")
    for name in skipped:
        print(f"  skip {name}")
    for name in failed:
        print(f"  FAIL {name} (see {failed_path})")

    # Flush into the stream these lines were written to, BEFORE returning.
    # The image package's `managed_run` stops a multiprocessing manager
    # Server on the way out, and CPython's `Server.serve_forever` then resets
    # this process's sys.stdout to sys.__stdout__ -- stranding anything still
    # buffered in a redirected stdout (a test runner, the workbench). The
    # always-on Rich Live used to flush as a side effect and hid this.
    sys.stdout.flush()
    return 0 if not failed else 2


@functools.lru_cache(maxsize=None)
def _load_pipeline(name_or_path: str):
    from forensic_metascience_ai_toolkit import pipeline_config as _pc
    return _pc.load(name_or_path)


def _pipeline(args):
    """The batch's pipeline (None: the complete review). Resolved once per name."""
    name = getattr(args, "pipeline", None)
    return _load_pipeline(name) if name else None


def build_parser() -> argparse.ArgumentParser:
    """The argument parser, separate from `main` so tests can inspect it.

    `metascience batch` delegates here, so the two entry points must agree on
    what every flag is called; a test asserts that by parsing flags rather than
    by reading this file.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default=None, help="Execution backend: auto, cpu, cuda:N or mps")
    parser.add_argument("--gpu-memory-gib", type=float, default=None)
    parser.add_argument("--gpu-reserve-gib", type=float, default=None)
    parser.add_argument("corpus", type=Path, help="Directory containing paper subdirectories")
    parser.add_argument("--limit", type=int, default=3, help="Number of papers to analyze")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for sampling (omit for deterministic order)")
    parser.add_argument("--subdir-name", default=None,
                        help="Name of the per-paper output subdirectory "
                             "(default: forensic_review_<model>_v<version>, "
                             "the same name `metascience analyze` writes)")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip papers already analysed by the same pipeline, "
                             "backend and model")
    parser.add_argument("--no-move-to-done", action="store_true",
                        help="Don't move processed paper directories into <corpus>/done/ after analysis")
    # `--workers` is an alias for the same value: one worker holds `sem` for one
    # whole paper, so the worker count IS the in-flight paper count. Kept as one
    # argparse dest so the two spellings cannot disagree.
    parser.add_argument("--workers", "--concurrency", type=int, default=3,
                        dest="concurrency",
                        help="Papers analyzed in parallel, one paper per worker (default: 3)")
    parser.add_argument("--timeout", type=int, default=1800,
                        help="Per-stage timeout in seconds (default: 1800; 0 = none)")
    parser.add_argument("--max-budget-usd", "--budget-usd", dest="budget_usd",
                        type=float, default=None,
                        help="Maximum spend per paper, split across the paid stages "
                             "(Claude backend only; --budget-usd is the old name)")
    parser.add_argument("--mode",
                        choices=("parallel", "two_stage"),
                        default="parallel",
                        help="Analysis mode (default: parallel; two_stage is "
                             "a deprecated alias for it)")
    parser.add_argument("--model", default=None,
                        help="Model alias; default follows --backend")
    parser.add_argument("--backend", default=None,
                        help="LLM backend: claude (default), grok, codex, openrouter or antigravity (Google's agy CLI). Overrides METASCIENCE_LLM_CLI.")
    parser.add_argument("--image-forensics", action=argparse.BooleanOptionalAction,
                        default=True,
                        help="Run independent image detection and AI screening "
                             "per paper alongside both analysts (default on)")
    parser.add_argument("--no-text-forensics", dest="text_forensics",
                        action="store_false",
                        help="Disable the deterministic tortured-phrases "
                             "track (on by default: free, local, quarantined; "
                             "its failures never mark a paper failed or "
                             "partial)")
    parser.add_argument("--effort", default=None,
                        help="Reasoning effort: low|medium|high|xhigh|max "
                             f"(default: the pipeline's, else {DEFAULT_EFFORT})")
    parser.add_argument("--pipeline", default=None,
                        help="Pipeline to run per paper: a shipped name "
                             "(`metascience pipeline list`) or a YAML path. "
                             "Decides the modules and the tools agent's "
                             "toolset; default is the complete review. Only "
                             "runs of the SAME pipeline count as already done "
                             "for a partial pipeline.")
    parser.add_argument("--verbose", action="store_true",
                        help="Stream agent output (noisy with concurrency > 1)")
    parser.add_argument("--no-usage-guard", action="store_true",
                        help="Disable the Claude Code usage guard entirely "
                             "(session pause and weekly stop)")
    parser.add_argument("--ignore-weekly-limit", action="store_true",
                        help="Do not stop when the weekly /usage gauge is spent. "
                             "Session pausing still runs. Use this when extra "
                             "usage credits will cover the spend")
    parser.add_argument("--usage-threshold", type=float, default=None,
                        help="Pause at/above this session %% used (default: 90)")
    parser.add_argument("--usage-max-wait-min", type=float, default=None,
                        help="Give up waiting for the usage window after this many minutes "
                             "and continue anyway (default: wait indefinitely)")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.device is not None:
        os.environ["METASCIENCE_DEVICE"] = args.device
        requested = _image_load("compute.devices").requested
        try:
            requested()
        except ValueError as exc:
            parser.error(str(exc))
    for value, key, minimum in ((args.gpu_memory_gib, "METASCIENCE_GPU_MEMORY_BYTES", .01),
                                 (args.gpu_reserve_gib, "METASCIENCE_GPU_RESERVE_BYTES", 0)):
        if value is not None:
            if value < minimum or not math.isfinite(value):
                parser.error("Invalid GPU memory budget")
            os.environ[key] = str(int(value*1024**3))

    if args.timeout == 0:
        args.timeout = None

    # THE SAME DEFAULT NAME `analyze` AND `metascience batch` USE. Commit
    # 4ec9bb3 introduced `forensic_review_<model>_v<version>` so "the two entry
    # points cannot drift apart again", but it changed cli.py and agent.py only
    # -- this script's argparse default stayed the bare `forensic_review`, so
    # running it directly put every model and every pipeline version into one
    # folder. Two backends compared on one paper overwrote each other there.
    # `metascience batch` passes an explicit `subdir_name`, so it is unaffected.
    if args.pipeline is not None:
        from forensic_metascience_ai_toolkit import pipeline_config as _pc
        try:
            config = _pipeline(args)
        except _pc.PipelineConfigError as exc:
            parser.error(str(exc))
        if not args.image_forensics or not args.text_forensics:
            parser.error("--no-image-forensics / --no-text-forensics cannot be "
                         "combined with --pipeline: the pipeline decides the "
                         "modules")
        args.backend, args.model, args.effort = _pc.resolve_backend_settings(
            config, args.backend, args.model, args.effort)
    args.effort = args.effort or DEFAULT_EFFORT
    if not args.subdir_name:
        from forensic_metascience_ai_toolkit.llm_backend import resolve_backend
        from forensic_metascience_ai_toolkit.cli import _versioned_review_dirname
        be = resolve_backend(args.backend)
        args.subdir_name = _versioned_review_dirname(args.model
                                                     or be.default_model,
                                                     _pipeline(args))

    # The guard reads its configuration from the environment so that every
    # entry point (batch script, CLI, direct import) shares one knob set.
    from forensic_metascience_ai_toolkit.usage_guard import apply_cli_overrides
    apply_cli_overrides(
        no_usage_guard=args.no_usage_guard,
        ignore_weekly_limit=args.ignore_weekly_limit,
    )
    if args.usage_threshold is not None:
        os.environ["METASCIENCE_USAGE_THRESHOLD"] = str(args.usage_threshold)
    if args.usage_max_wait_min is not None:
        os.environ["METASCIENCE_USAGE_MAX_WAIT_MIN"] = str(args.usage_max_wait_min)

    if not args.corpus.is_dir():
        print(f"Error: corpus directory not found: {args.corpus}", file=sys.stderr)
        return 1

    return asyncio.run(run_batch(args))


if __name__ == "__main__":
    sys.exit(main())
