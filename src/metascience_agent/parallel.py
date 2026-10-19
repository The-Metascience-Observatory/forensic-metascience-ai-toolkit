"""The parallel pipeline: two analysts, one adjudicator (mode="parallel").

Contract: docs/specs/pipeline.md. This is the only analysis pipeline;
`agent.analyze_paper` dispatches here. Stage execution, source resolution,
forensic tracks and JSON extraction still live in `agent.py` and are shared
helpers, not a second pipeline:

    tool expert (no web, no code)  ||  science analyst (web on, MCP code)
                       ||  image track  ||  text track
        -> merge to findings-v2 -> pre-adjudication annotation
        -> adjudicator (final 1-9) -> anchors -> write

Failure matrix (spec section "failure/partial"): one agent fails -> proceed
with the survivor, loudly; both fail -> StageError; adjudicator fails ->
apply_skip (findings ship provisional; impossible rows stamped
cross_check:"not_run"). Findings are never lost to their own pipeline.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import adjudicate, agent as _agent, findings_v2 as fv2
from .core import prompts
from . import consequence as _consequence
from . import anchors as _anchors
from . import llm_backend as _llm
from . import scrub as _scrub
from .registry import ADJUDICATOR, SCIENCE_AGENT, TOOL_AGENT, stage_tools

TOOL_BUDGET_FRACTION = 0.40
SCIENCE_BUDGET_FRACTION = 0.25
MIN_ADJUDICATOR_BUDGET_USD = 0.20

TOOL_AGENT_TOOLS = ["Read"] + [_agent._mcp(n) for n in stage_tools(TOOL_AGENT)]


def tool_agent_tools(figures: bool, toolset=None) -> list[str]:
    """The tool agent's allowlist, minus the figure tools when the pass is off.

    MIRRORS `agent._stage1_tools`, which states the rule for the legacy path in
    one line: "Removing it from the PROMPT is not enough -- a tool that is
    offered can be called. Default-off has to mean unavailable, not merely
    unmentioned." The parallel path had no such filter, so `--figures` was
    decorative there in a worse way than it had ever been on the legacy path.

    WHAT THAT COST, measured on the live run of 2026-08-29. `parallel.py` never
    took a `figures` argument at all, so the system prompt was built with the
    default and the figure section was stripped -- and ALL the figure discipline
    lives in that section: the instruction to stamp
    `provenance="measured_raster"`, the error-bar rules, the figures-array duty.
    Meanwhile `extract_figures` stayed in the 57-tool allowlist and the model
    called it. The exact-arithmetic gate at `registry.py:705` keys on a
    `provenance` parameter that defaults to `printed_table` and that nothing was
    telling the model to set.

    CAPABILITY ON, GUARDS OFF -- strictly worse than either coherent setting. A
    value read off a plot, handed to a granularity check at the default
    provenance, is the false accusation this project exists to avoid: measured
    on the figure-extractor benchmark, the best reader recovers a mean to ~0.44%
    and an error bar to ~3.89% (worst 27.7%), and GRIM needs error below
    1/(2n) -- so a figure read is admissible only when n x value < ~114. A 1-7
    Likert mean at n=30 already fails that.

    Making OFF real enforces a decision the CLI already records ("OFF BY
    DECISION: figure-value extraction is not yet reliable, and a wrong number
    read off a plot is worse than a stated gap"). It cannot manufacture an
    accusation, because removing a tool never accuses; the blindness it restores
    is a reported gap.
    """
    if toolset is not None:
        # A pipeline's toolset: `Read` plus exactly the resolved tools, which
        # already include or exclude the figure tools per `figures`.
        keep = {_agent._mcp(n) for n in toolset}
        return [t for t in TOOL_AGENT_TOOLS if t == "Read" or t in keep]
    if figures:
        return TOOL_AGENT_TOOLS
    drop = {_agent._mcp(n) for n in prompts.FIGURE_TOOLS}
    return [t for t in TOOL_AGENT_TOOLS if t not in drop]


#: The user turn's tool instructions that a restricted toolset can remove.
#: Each is a whole sentence naming one tool; the system prompt's toolset note
#: covers everything else.
_USER_PROMPT_TOOL_SENTENCES = {
    # One entry per source layout of `agent._build_sweep_prompt` (XML/HTML,
    # markdown + PDF, markdown only); pinned by a test that builds each.
    "statcheck": (
        "For NHST verification, run `statcheck` with the `text` argument set "
        "to the returned body text.",
        "For NHST verification, prefer `statcheck` with the `text` argument "
        "set to the body content.",
        "For NHST verification, use `statcheck` with the `text` argument.",
    ),
}


def _restrict_user_prompt(prompt: str, toolset) -> str:
    """Drop user-turn instructions for tools the pipeline does not enable.
    Identity for the full toolset (None), so complete reviews keep their bytes."""
    if toolset is None:
        return prompt
    for tool, sentences in _USER_PROMPT_TOOL_SENTENCES.items():
        if tool not in toolset:
            for sentence in sentences:
                prompt = prompt.replace(sentence, "")
    if "declare_table" not in toolset:
        # The declaration block names the paper's own directory, so it is cut
        # by its heading rather than matched as a fixed sentence.
        from .agent import TABLE_DECLARATIONS_HEADING
        at = prompt.find("\n\n" + TABLE_DECLARATIONS_HEADING)
        if at >= 0:
            end = prompt.find("\n\n", at + 2)
            prompt = prompt[:at] + (prompt[end:] if end >= 0 else "")
    return prompt


def _module_defs():
    from .modules import definitions
    return definitions()


def _disabled_verbs(toolset) -> frozenset[str]:
    """The tools-agent tools a restricted toolset excludes: their CLI verbs
    (archived per-tool commands) and their names (`metascience tool run X`)."""
    from .registry import SPECS
    role = set(stage_tools(TOOL_AGENT))
    off = [s for s in SPECS if s.name in role and s.name not in toolset]
    return frozenset([s.cli for s in off if s.cli] + [s.name for s in off])


def _not_configured_state(config) -> tuple[str, str]:
    return "did_not_run", f"not configured in pipeline {config.name!r}"


SCIENCE_AGENT_TOOLS = (["Read", "WebSearch", "WebFetch"]
                       + [_agent._mcp(n) for n in stage_tools(SCIENCE_AGENT)])
ADJUDICATOR_TOOLS = ["Read"] + [_agent._mcp(n) for n in stage_tools(ADJUDICATOR)]

_WEB_TOOLS = {"WebSearch", "WebFetch"}

# The analysts' shared helpers moved to `modules/_analyst.py` in Phase 2;
# re-exported here for existing callers.
from .modules._analyst import (  # noqa: E402,F401
    _LEDGER_DIGEST_CHARS, _LEDGER_ROW_CHARS, _WORK_SURFACES,
    _final_after_placeholders, _final_assistant_texts, _ledger_digest,
    _ledger_recovery_prompt, _looks_empty_doc, _n_work_calls,
    _producer_retry_correction,
)


def _usage_totals(stages_meta: dict) -> dict:
    """Token and wall-clock totals for the cost row, summed over every stage.

    THE USAGE TABLE PRINTED "output tokens: 0" for a run that produced about
    1.3 million. MEASURED 2026-08-22: ten papers, stages writing 40k-73k output
    tokens each, all of it in the archived transcripts -- and `batch.py`
    wrote null because the parallel result had no such key, so
    `cli._usage_table` rendered `int(None or 0)`. The "input tokens 41,261,824"
    beside it was cache-read alone.

    Includes the retry rows `_add_ledger_only_attempts` adds, because the
    retries were billed.

    `total_wall_seconds` is the SUM of stage wall clocks, not the run's elapsed
    time: the two analysts run concurrently, so the sum overstates the wall
    clock and understates nothing. It is named `total_wall_seconds` because
    that is the key `batch.py` and `cli._usage_table` already read, and
    what they label it -- "total runtime" -- is compute time across stages.

    `None` rather than `0.0` when nothing was timed: the row is suppressed by
    its own `if secs:`, and 0.0 would print a false measurement.
    """
    metas = [m for m in stages_meta.values() if isinstance(m, dict)]
    try:
        out = {k: sum(int(m.get(k) or 0) for m in metas)
               for k in _agent._SPEND_USAGE_FIELDS}
        wall = sum(float(m.get("wall_seconds") or 0) for m in metas)
    except (TypeError, ValueError) as exc:
        # ONE GUARD ROUND THE WHOLE SUM, not eight per-field ones, and it
        # reports UNKNOWN rather than a partial total. Every field here is an
        # int written by `_stage_meta` or `record_spend`, so this should be
        # unreachable -- but this function runs inside the return statement of
        # a finished paper, and a formatting error in a cost summary must not
        # be how a paid review is lost. A silently short sum would be worse
        # than either: it would look like a measurement.
        return {k: None for k in _agent._SPEND_USAGE_FIELDS} | {
            "total_wall_seconds": None, "usage_totals_error": str(exc)}
    out["total_wall_seconds"] = round(wall, 2) if wall else None
    return out


def _add_ledger_only_attempts(stages_meta: dict) -> None:
    """Add a row for every BILLED attempt the stage table does not already show.

    16% OF A RUN'S SPEND WAS INVISIBLE. MEASURED 2026-08-22: $1.82 of $11.57
    over ten papers, $0.85 on one, because a retry returns one attempt and the
    other is dropped -- money included. The total was right and the
    decomposition was not, so a reader could not see which stage cost what.

    Read off `record_spend`'s ledger rather than plumbed through the retry
    paths: that ledger is the ONE place that sees every attempt, it already
    labels them, and it also covers the two retries `parallel` never handles
    (the legacy `stage2_editorial` and the tool agent's internal one).

    SUMS BY LABEL, because two attempts can share one. `tool_agent_retry` is
    emitted both by `_run_stage_requiring_forensic_tools` and by
    `_retry_if_empty`, and in a run where both fire, keying by name would let
    one silently overwrite the other -- an undercount presented as a
    decomposition.
    """
    totals: dict[str, dict] = {}
    for row in _agent.spend_so_far().get("stages") or []:
        label = str(row.get("stage") or "")
        if not label or label in stages_meta:
            continue
        acc = totals.setdefault(label, {"n_attempts": 0})
        acc["n_attempts"] += 1
        for key in ("cost_usd", "wall_seconds") + _agent._SPEND_USAGE_FIELDS:
            if row.get(key) is not None:
                acc[key] = (acc.get(key) or 0) + row[key]
    for label, acc in totals.items():
        # `source` so nobody reads this as a full stage record: it carries
        # money and tokens, not messages, coverage or a parse path.
        #
        # `is_error` IS DELIBERATELY NOT COPIED, though the ledger has it.
        # `tripwire.stage_reported_an_error` scans these rows, and a discarded
        # first attempt that errored before a successful retry would fire it on
        # a paper that recovered cleanly. That attempt's failure is already
        # reported -- by the `limitations` entry that says the stage was
        # retried -- so carrying it here would double-count it as a tripwire
        # and change behaviour this commit is not entitled to change.
        stages_meta[label] = {**acc, "source": "spend_ledger"}


def _with_grim_coverage(coverage: dict, grim_sweep: dict | None) -> dict:
    """The coverage block plus the harness GRIM sweep's own counts and line."""
    if not isinstance(grim_sweep, dict) or grim_sweep.get("not_run"):
        return coverage
    from . import grim_harness as _gh
    out = dict(coverage or {})
    out["grim_sweep"] = {k: grim_sweep.get(k) for k in (
        "n_tables", "enumerated", "checked", "consistent", "inconsistent",
        "explained_by_nonresponse", "refused", "n_by_source",
        "premise_by_source", "n_declarations", "refused_whole_paper")
        if grim_sweep.get(k) is not None}
    out["grim_sweep"]["line"] = _gh.coverage_line(grim_sweep)
    return out


def _coverage_with_ledger_fallback(tool_doc: dict | None,
                                   ledger: list[dict] | None) -> dict:
    """The tool doc's coverage, or -- when it lost it -- the ledger's.

    A DOCKET THAT DID NOT SURVIVE SERIALIZATION IS NOT A PAPER WITH NOTHING
    CHECKED. MEASURED 2026-08-22 at v1.9.0, three of ten papers filed
    `coverage: {"stats_found": 0, "tools_run": []}` after 47, 70 and 78 forensic
    tool calls, and the bounded retry was empty on all three. It is not
    truncation: on `10.1186--s13550-023-00956-9` the final message is 3,726
    characters of complete, well-formed JSON with three findings and stub
    metadata. The model did the work over 19 turns and then filed a highlights
    document.

    The ledger is ground truth about which tools ran -- it is built from the
    transcript, not from the model's own account of itself -- so publishing `[]`
    beside it is the absence-as-evidence error this repository keeps finding.
    The rebuilt list is marked `tools_run_source: "ledger"` so no reader mistakes
    it for the producer's own statement, and `stats_found` is NOT invented: how
    many statistics the paper contains is not something a ledger knows.
    """
    coverage = dict((tool_doc or {}).get("coverage") or {})
    if coverage.get("tools_run"):
        return coverage
    ran = sorted({
        str(r.get("tool_short") or "")
        for r in (ledger or [])
        if str(r.get("surface", "")).startswith("forensic_mcp")
        and r.get("tool_short")
    })
    if not ran:
        return coverage
    coverage["tools_run"] = ran
    coverage["tools_run_source"] = "ledger"
    return coverage


#: Per-row and total caps for the recovery digest. A forensic result is small
#: JSON; `extract_pdf` is not, and its text is not evidence for a finding.
def _survey_design_note(text: str | None) -> str:
    """A paragraph appended to both analyst prompts, or "" -- see `survey_design`.

    PREVENTION IS THE MAIN LEVER HERE. The code guards refuse a misapplied check
    after the model has already spent a turn on it and formed an opinion; this
    stops it being run. The pipeline already knew the rule and applied it
    unevenly: on `10.15585--mmwr.mm6923e2` the model refused GRIM on weighted
    percentages unprompted in both archived runs, and on
    `10.1186--s12889-025-24026-y` it recomputed six weighted statistics as
    though they were a simple random sample. Prompt-only knowledge fires when
    the model happens to think of it, which is why the guards exist too.

    The paper's OWN SENTENCE is quoted, not our conclusion about it: the claim
    "this is a complex survey" has to be auditable against the source.
    """
    from .survey_design import declares_complex_survey
    found = declares_complex_survey(text)
    if not found:
        return ""
    return (
        "\n\n**THIS PAPER DECLARES A COMPLEX SURVEY DESIGN.** Its own words:\n"
        f"> {found['quote']}\n\n"
        "Published p-values, confidence intervals and standard errors therefore "
        "come from a design-based variance estimator on a t with the survey "
        "degrees of freedom (PSUs minus strata), which is typically small. They "
        "are NOT functions of the printed means, SDs or counts, and weighting "
        "moves the composition of the sample, not merely its variance.\n\n"
        "- Pass `sampling=\"complex_survey\"` to `recalc_independent_t`, "
        "`recalc_within_subjects_t`, `recalc_anova`, `recalc_chi_squared`, "
        "`recalc_stat_to_p`, `rivets_independent_t`, `rivets_anova` and "
        "`check_estimate_ci`. They then refuse, or narrow, rather than accuse.\n"
        "- A printed p that is LARGER than one you recover assuming a simple "
        "random sample is EXPECTED under this design and is not a finding. A "
        "printed p SMALLER than the recovery still is.\n"
        "- Counting checks on printed integers -- `check_count_percent`, "
        "`check_summation`, `check_flow_arithmetic`, the GRIM family -- are "
        "valid under any design and stay in scope. But if a PERCENTAGE is "
        "itself weighted, no integer k/n produces it; say so in `unchecked` "
        "rather than back-deriving counts from it.\n"
        "- If you compare a printed summary statistic against a model output or "
        "a figure (a love plot, a forest plot, a standardised mean difference), "
        "state whether both are on the same weighting basis. If they are not, "
        "the comparison is not evidence."
    )


def _build_science_agent_prompt(src, paper_id: str) -> str:
    """The science analyst's per-paper prompt: main text only, two passes."""
    lines = [
        f"Review the paper `{paper_id}`. Use `paper_id`: \"{paper_id}\" in "
        "the findings JSON.",
        "",
    ]
    if src.xml:
        lines.append(f"The paper's XML is `{src.xml}` -- your PRIMARY source; "
                     "read it with `extract_xml`, tables with `get_table`.")
    elif src.html:
        lines.append(f"The paper's HTML is `{src.html}`; read it with "
                     "`extract_html`.")
    if src.main_pdf:
        lines.append(f"The paper's PDF is `{src.main_pdf}`; read it with "
                     "`extract_pdf`" +
                     (" (cross-check only when XML/HTML is present)."
                      if (src.xml or src.html) else " -- your primary source."))
    if src.body_md and not (src.xml or src.html):
        lines.append(f"A pre-extracted body is `{src.body_md}` (use `Read`).")
    if src.si_pdfs or src.si_readable:
        lines.append(
            "Supplements exist for this paper and are being analyzed by the "
            "tools agent IN PARALLEL. Do not open them.")
    lines += [
        "",
        "Pass 1 -- read the ENTIRE main text linearly, building the claims "
        "register (primary outcome, doses, durations, group sizes, "
        "directions of effect) and every participant count.",
        "Pass 2 -- run the flow arithmetic through `check_flow_arithmetic`, "
        "verify drifting denominators with the integer cross-checks, verify "
        "named entities per the web-facts discipline, and file findings.",
    ]
    return "\n".join(lines)


def _mint_run_uid(paper_id: str, analysed_at: str) -> str:
    h = hashlib.sha256(f"{paper_id}\x1f{analysed_at}".encode()).hexdigest()
    return f"r_{h[:16]}"


def _rows_from_producer(doc: dict | None, producer: str,
                        ledger: list[dict], paper_id: str) -> list[dict]:
    """Producer-subset rows -> findings-v2 rows: producer stamped, ids
    assigned, tool verdicts joined from the LEDGER (never prose), impossible
    derived, provisionals clamped."""
    rows = [r for r in ((doc or {}).get("findings") or [])
            if isinstance(r, dict)]
    # Scripts this stage ACTUALLY ran, from the ledger. Measured on the
    # 2026-08-21 cerebrolysin run: the model cited its scripts loosely
    # ("# compare against the roster script"), never as "analysis_code/...",
    # so the prose-only test stamped every script-backed row model_reading.
    # A persisted path or label from a real run_python_script result is the
    # ground truth; labels shorter than 8 chars are too generic to substring-
    # match against prose without false hits.
    script_refs: set[str] = set()
    for call in ledger or []:
        if call.get("tool_short") != "run_python_script":
            continue
        try:
            parsed = json.loads(call.get("result") or "")
        except (ValueError, TypeError):
            parsed = None
        if isinstance(parsed, dict):
            for key in ("script_path", "label"):
                v = str(parsed.get(key) or "")
                if len(v) >= 8:
                    script_refs.add(v)
    for r in rows:
        r["producer"] = producer
        # A BARE URL IS A SOURCE, NOT A FINDING. See
        # `fv2.title_is_a_bare_url` for the three mmwr rows that prompted
        # this. The row is kept -- discarding a producer's row on a
        # formatting judgement would be worse -- but the link moves to
        # `notes`, where a source belongs, and the title says what the row is.
        if fv2.title_is_a_bare_url(r.get("title")):
            url = " ".join(str(r.get("title")).split())
            r["title"] = f"Source consulted ({producer}); no finding stated"
            r["notes"] = " ".join(x for x in (str(r.get("notes") or ""), url) if x)
        # A producer may submit a title up to `PRODUCER_TITLE_MAX`; the stored
        # row holds `TITLE_MAX`, cut at a word, the full title kept in notes.
        fv2.fit_row_title(r, producer)
        r.setdefault("quarantined", False)
        r.setdefault("outcome",
                     "problem" if r.get("consistent") is False else "undecided")
        tv = fv2.tool_verdict_for(r, ledger)
        if tv is not None:
            r["tool_verdict"] = tv
        rep_text = " ".join(str(r.get(k) or "")
                            for k in ("reproduction", "notes"))
        script_backed = (
            r.get("reproduction_kind") == "script"
            or "analysis_code/" in rep_text
            or any(ref in rep_text for ref in script_refs))
        # A joined tool verdict outranks a script citation: the tool result
        # is the evidence (and the only channel `impossible` can derive
        # from); a script beside it was data-wrangling, not the finding's
        # arithmetic.
        r["computed_by"] = (
            "registry_tool" if tv is not None
            else "agent_code" if script_backed
            else "model_reading")
        r["impossible"] = fv2.derive_impossible(r)
    fv2.assign_finding_ids(rows, paper_id)
    fv2.clamp_provisionals(rows)
    if producer == "science_error":
        web_rows = [row for row in ledger or []
                    if row.get("tool_short") in _WEB_TOOLS]
        n_web = len(web_rows)
        # What the agent actually visited, for the docket. The row's own
        # web_sources stays the model's attestation and is never filled in
        # for it -- but an unsourced claim beside a list of real fetches is
        # a different adjudication question than one beside nothing, and
        # until 2026-08-22 the adjudicator could not tell them apart.
        visited = []
        for row in web_rows:
            inp = row.get("input") or {}
            ref = inp.get("url") or inp.get("query")
            if ref and ref not in visited:
                visited.append(str(ref)[:200])
        for r in rows:
            if r.get("web_sources") and not n_web:
                r["web_unbacked"] = "no_ledger_call"  # cites lookups its ledger lacks
            elif r.get("basis") == "web_lookup" and not (r.get("web_sources")
                                                         or []):
                # The INVERTED unbacked shape (measured 2026-08-22, four-paper
                # grok rematch): all ten basis=web_lookup rows across four
                # papers carried web_sources: [] while the ledgers held real
                # web calls -- the lookups happened, but no source was
                # recorded, so no reader can audit the claim. The severity
                # clamp treats such a row as model_knowledge.
                r["web_unbacked"] = "no_recorded_source"
                if visited:
                    r["ledger_web_context"] = visited[:10]
    return rows


_SCHEMA_GATE_SUBTYPE = "error_max_structured_output_retries"


def _adjudicator_hit_schema_gate(stage: dict | None) -> bool:
    """True only for the structured-output gate, never for budget/timeout."""
    if not isinstance(stage, dict):
        return False
    return str(stage.get("error_subtype") or "") == _SCHEMA_GATE_SUBTYPE


def _schema_gate_correction(stage: dict | None) -> str:
    """The retry's extra instruction, quoting what the gate actually rejected.

    A retry that re-sends an identical prompt is a coin flip, and it lost
    twice on 2026-08-22. The CLI already told us the offending field and
    value; `_run_stage` now carries it as `schema_errors`. Quote it back.

    Degrades to the generic paragraph when the CLI reported no detail --
    the retry is still worth making, it just cannot be specific.
    """
    errs = (stage or {}).get("schema_errors") or []
    detail = ""
    if errs:
        joined = "\n".join(f"  - {e}" for e in errs)
        detail = (
            "\n\nYour previous attempt was REJECTED by the output schema "
            "with exactly this:\n" + joined + "\n")
    return (
        "\n\n---\n\n## RETRY -- your previous attempt produced no usable "
        "adjudication" + detail +
        "\nRe-read the turn contract. Do the reading and the tool work FIRST. "
        "The JSON is your LAST message and there is no turn after it, so a "
        "placeholder or padded `summary` ends the run with nothing. Write the "
        "real summary: the defect that most undermines trust with its numbers, "
        "what did reconcile, what the journal would have to do, and what this "
        "review did not establish.\n")


def _stage_state(stage: dict | None, record: dict | None = None) -> tuple[str, str]:
    if stage is None and record is None:
        return "did_not_run", "stage not attempted"
    if record is not None:                  # a deterministic track record
        if record.get("execution_status") == "disabled":
            return "did_not_run", record["detail"]
        if record.get("ran"):
            return "ran", str(record.get("detail") or "")
        return ("refused", str(record.get("detail")
                               or record.get("error_subtype") or "refused"))
    if stage.get("is_error"):
        if _output_recovered(stage):
            # The stage errored AND its findings are in this document: calling
            # it `refused` beside them contradicts the report (measured
            # 2026-10-11, a grok science agent with seven findings).
            return "ran", (f"{stage.get('error_subtype') or 'stage error'}; "
                           f"output recovered ({stage['output_parse_path']}) "
                           "and used")
        return "refused", str(stage.get("error_subtype") or "stage error")
    return "ran", ""


def _image_disabled_record() -> dict:
    from .modules.image_analysis.module import disabled_record
    return disabled_record()


def _image_evidence_bundle(merged: list[dict]) -> dict:
    """The screened image evidence packets the adjudicator must read
    (`image_forensics.evidence.adjudication_bundle`). Without the image
    package there is no image track, so normally nothing to load; a row that
    nevertheless names a packet gets a per-finding error, never a silent drop."""
    from .image_plugin import INSTALL_HINT, available, load
    if available():
        return load("image_forensics.evidence").adjudication_bundle(merged)
    errors = {f.get("finding_id"): f"screened evidence packet not loaded: {INSTALL_HINT}"
              for f in merged
              if ((f.get("inputs") or {}).get("ai_screening") or {}).get("evidence_packet")}
    return {"packets": {}, "by_finding": {}, "errors": errors, "attachments": []}


def _raw_state(record: dict | None) -> tuple[str, str]:
    """The raw-data channel: `did_not_run` when the paper has no spreadsheet
    (nothing was read, so nothing is cleared), `refused` on a crash or a
    timeout, else `ran`."""
    if not record:
        return "did_not_run", "raw-data module did not report"
    if record.get("ran"):
        return "ran", str(record.get("detail") or "")
    if record.get("execution_status") == "did_not_run":
        return "did_not_run", str(record.get("detail") or "")
    return "refused", str(record.get("detail") or "raw-data track failed")


def _output_recovered(stage: dict | None) -> bool:
    """An errored stage whose document was nevertheless parsed and used."""
    return bool(stage) and stage.get("output_parse_path") not in (None, "failed")


async def analyze_paper_parallel(
    paper_path: str,
    verbose: bool = False,
    timeout: float | None = None,
    budget_usd: float | None = None,
    model: str | None = None,
    effort: str | None = None,
    figures: bool = False,
    image_forensics: bool = True,
    text_forensics: bool = True,
    on_progress=None,
    extra_supplements=None,
    backend: str | None = None,
    image_segment_montages: bool = False,
    image_reassemble_tiles: bool = False,
    pipeline=None,
) -> dict:
    from .analysis_runs import Archive, project_root, provenance, now
    from . import pipeline_config as _pc
    # WHICH MODULES RUN. A caller that passes no pipeline gets exactly the
    # pipeline its flags always described; a pipeline, when given, decides
    # the module set and the flags are read from it.
    config = pipeline or _pc.from_flags(
        image_forensics=image_forensics, text_forensics=text_forensics,
        figures=figures, segment_montages=image_segment_montages,
        reassemble_tiles=image_reassemble_tiles)
    figures = config.figures
    image_forensics = config.has("image_analysis")
    text_forensics = config.has("text_forensics")
    image_segment_montages = bool(config.option(
        "image_analysis", "segment_montages", False))
    image_reassemble_tiles = bool(config.option(
        "image_analysis", "reassemble_tiles", False))
    backend, model, effort = _pc.resolve_backend_settings(
        config, backend, model, effort)
    # Resolved BEFORE history records it: the API default used to be the
    # constant itself, and history recorded "high", never null.
    effort = effort or _agent.DEFAULT_EFFORT
    # A PARTIAL RUN IS NOT THE PAPER'S REVIEW. The parent component is what
    # the workbench and history_db read as "the comprehensive review"; a
    # one-tool or no-adjudication run recorded under it would replace the
    # paper's review in every summary. Complete reviews keep the name.
    parent_component = ("comprehensive" if config.complete_review
                        else "partial_review")
    agent_children = [(label, component) for label, component, module in (
        ("tool_agent", "tool_expert", "tools_agent"),
        ("science_agent", "science_error", "scientific_proofreading_agent"),
        ("adjudicator", "adjudicator", "adjudicator")) if config.has(module)]
    from .history_runtime import CONTEXT
    from .llm_backend import resolve_backend, BudgetUnsupported
    if budget_usd is not None and not resolve_backend(backend).supports_budget:
        raise BudgetUnsupported(f"{resolve_backend(backend).name} has no spend cap")
    if budget_usd is not None:
        # Before any history is written: a module on its own backend needs
        # a spend cap too (only Claude has one).
        for spec in config.modules:
            if spec.backend and not resolve_backend(spec.backend["name"]).supports_budget:
                raise BudgetUnsupported(
                    f"{spec.use} runs on {spec.backend['name']}, which has no spend cap")
    paper = Path(paper_path).resolve()
    if paper.is_file(): paper = paper.parent
    history = Archive(project_root(paper))
    context = CONTEXT.get()
    execution = context.get("execution_id")
    if not execution:
        execution = history.execution(parent_component, components=[parent_component, "image_forensics", "copy_paste"] + [c for _, c in agent_children], provenance=provenance(parent_component))["id"]
    parameters = {"model": model, "backend": backend, "effort": effort,
                  "budget_usd": budget_usd, "timeout": timeout, "image_forensics": image_forensics, "text_forensics": text_forensics}
    if pipeline is not None:
        parameters["pipeline"] = config.record()
    parent = history.start(execution, parent_component, paper.relative_to(history.root).as_posix(), run_id="r_" + uuid.uuid4().hex[:16],
                           provenance=provenance(parent_component, parameters=parameters))
    try:
        _, input_artifacts = history.freeze_items(parent, [])
    except BaseException as exc:
        history.seal(parent, status="failed", detail=str(exc), completed_at=now())
        if not context.get("execution_id"):
            history.finish_execution(execution, "failed")
        raise
    token = CONTEXT.set({"root": str(history.root), "execution_id": execution, "run_id": parent["id"]})
    stages = {label: history.start(execution, component, parent["paper"], parent_run_id=parent["id"], provenance=provenance(component, model=model, backend=backend))
              for label, component in agent_children}
    tasks: list[asyncio.Task] = []
    try:
        result = await _coordinate_analysis(
            paper_path, verbose, timeout, budget_usd, model, effort, figures,
            image_forensics, text_forensics, on_progress, extra_supplements,
            backend, image_segment_montages, image_reassemble_tiles,
            _background_tasks=tasks, config=config)
        result["run_meta"]["history"] = parent
        # Pinned for the report writers: see history_runtime.result_archive.
        result["history_root"] = str(history.root)
        for label, component in agent_children:
            stage = result.get(label)
            child = stages[label]
            child["stage_output"] = stage
            # An errored stage whose output was recovered and used is
            # PARTIAL, not failed (the CLAUDE.md invariant for stages).
            history.seal(child, status="not_requested" if not stage else ("incomplete" if _output_recovered(stage) else "failed") if stage.get("is_error") else "completed", completed_at=now())
        from .analysis_runs import read
        children = [r for r in read(history.base / "index.json", {"runs": {}})["runs"].values() if r.get("parent_run_id") == parent["id"]]
        for component in ("copy_paste", "image_forensics"):
            if not any(r["component"] == component for r in children):
                child = history.start(execution, component, parent["paper"], parent_run_id=parent["id"], provenance=provenance(component))
                raw = result.get("raw_data_track") if component == "copy_paste" else None
                if raw is not None:
                    # The raw_data module IS the copy_paste component; record
                    # what it did. No spreadsheet means nothing was available
                    # to read, never a clean result.
                    state = ("unavailable" if raw.get("execution_status") == "did_not_run"
                             else "failed" if raw.get("is_error")
                             else "incomplete" if raw.get("execution_status") == "incomplete"
                             else "completed")
                    history.seal(child, status=state, detail=str(raw.get("detail") or ""), completed_at=now())
                    continue
                state = "failed" if component == "image_forensics" and image_forensics else "not_requested"
                detail = "No component result was recorded" if state == "failed" else "The component was not invoked"
                if state == "failed" and (result.get("image_track") or {}).get("execution_status") == "unavailable":
                    # Configured, but the image analysis package is not installed.
                    state, detail = "unavailable", result["image_track"]["detail"]
                history.seal(child, status=state, detail=detail, completed_at=now())
        parent["document"] = result.get("findings_v2")
        history.seal(parent, artifacts=input_artifacts, status="incomplete" if result.get("is_error") else "completed", completed_at=now())
        if not context.get("execution_id"): history.finish_execution(execution, "completed")
        return result
    except BaseException as exc:
        for child in stages.values():
            if not (history.base / "runs" / f"{child['id']}.json").exists():
                history.seal(child, status="cancelled", detail=f"Parent analysis stopped: {type(exc).__name__}", completed_at=now())
        if not (history.base / "runs" / f"{parent['id']}.json").exists():
            history.seal(parent, status="cancelled" if isinstance(exc, asyncio.CancelledError) else "failed", detail=str(exc), completed_at=now())
        raise
    finally:
        CONTEXT.reset(token)
        for task in tasks:
            if not task.done(): task.cancel()
        if tasks: await asyncio.gather(*tasks, return_exceptions=True)


async def _coordinate_analysis(
    paper_path: str,
    verbose: bool = False,
    timeout: float | None = None,
    budget_usd: float | None = None,
    model: str | None = None,
    effort: str | None = None,
    figures: bool = False,
    image_forensics: bool = True,
    text_forensics: bool = True,
    on_progress=None,
    extra_supplements=None,
    backend: str | None = None,
    image_segment_montages: bool = False,
    image_reassemble_tiles: bool = False,
    *, _background_tasks: list[asyncio.Task],
    config=None,
) -> dict:
    from .llm_backend import resolve_backend
    from . import pipeline_config as _pc
    if config is None:
        config = _pc.from_flags(
            image_forensics=image_forensics, text_forensics=text_forensics,
            figures=figures, segment_montages=image_segment_montages,
            reassemble_tiles=image_reassemble_tiles)
    run_tools = config.has("tools_agent")
    run_science = config.has("scientific_proofreading_agent")
    run_adjudicator = config.has("adjudicator")
    # THE TOOLSET, when restricted. None means the role's whole surface and
    # the historical commands byte for byte; a list narrows the allowlist,
    # the MCP server (fail-closed manifest), check_table and the harness.
    restricted = run_tools and not config.full_toolset
    toolset = frozenset(config.toolset) if restricted else None
    be = resolve_backend(backend)
    model = model or be.default_model
    effort = effort or _agent.DEFAULT_EFFORT
    if budget_usd is not None and not be.supports_budget:
        from .llm_backend import BudgetUnsupported
        raise BudgetUnsupported(f"{be.name} has no spend cap")

    _agent.reset_spend()
    # WHICH RUN THIS IS, minted once and handed to every stage. It scopes the
    # `analysis_code/` directory `run_python_script` writes into, so a second
    # analysis of the SAME paper directory -- a cross-backend comparison, or
    # simply a re-run started before the first finished -- cannot overwrite
    # this run's scripts, share its sandbox workdirs, or carry them off in its
    # own archive. The uuid matters as much as the model: two runs of the same
    # model have the identical collision.
    run_slug = (f"{re.sub(r'[^A-Za-z0-9]+', '-', str(model)).strip('-') or 'model'}"
                f"-{uuid.uuid4().hex[:8]}")
    src = _agent._resolve_paper_sources(paper_path, extra_supplements)
    paper_id = _agent._paper_id(paper_path)
    paper_dir = Path(paper_path if Path(paper_path).is_dir()
                     else Path(paper_path).parent)
    try:
        from . import paper_metadata
        metadata = paper_metadata.record_for_run(paper_dir)
    except Exception:  # noqa: BLE001 -- metadata is best-effort by contract
        metadata = None
    # THE RECORD IS KEPT, not discarded. It says which reader produced the
    # text and what failed on the way, and the census publishes it as
    # `coverage_summary.extraction`; a failed extraction is otherwise
    # indistinguishable from a paper with nothing in it.
    extraction_record = _agent.ensure_paper_extracted(paper_path)

    # LOADED ONCE, HERE, because two consumers need it and one of them is the
    # prompt. It used to be read just before the adjudicator; the sampling-design
    # detector below has to see it before either analyst is instructed.
    from .extraction.jats import paper_text
    try:
        text = paper_text(paper_dir)
    except Exception:  # noqa: BLE001
        text = ""
    survey_note = _survey_design_note(text)
    # A declared p correction rides with the design note: both tell the
    # analysts that a printed p larger than a recomputation is expected.
    from .p_adjustment import p_adjustment_note
    survey_note += p_adjustment_note(text)

    # THE MODULES. Each configured producer runs as its own task, started as
    # soon as the modules it `needs` have finished (core/scheduler.py); their
    # results are merged below in CANONICAL order, never completion order.
    # What each analyst sends -- system prompt, allowlist, schema, manifest --
    # is built inside its module and remembered in `ctx.system_prompts` at
    # the moment the command is built.
    from .core.context import BackendSettings, RunContext
    from .core.scheduler import run_producers
    from . import modules as _modules
    ctx = RunContext(
        config=config, paper_path=paper_path, paper_dir=paper_dir,
        paper_id=paper_id, src=src, text=text, survey_note=survey_note,
        run_slug=run_slug, run_settings=BackendSettings(be, model, effort),
        verbose=verbose, timeout=timeout, on_progress=on_progress,
        budget_usd=budget_usd, toolset=toolset)
    if budget_usd is not None:
        for spec in config.modules:
            if spec.definition.backend_configurable:
                mod_be = ctx.settings_for(spec.use).backend
                if not mod_be.supports_budget:
                    from .llm_backend import BudgetUnsupported
                    raise BudgetUnsupported(
                        f"{spec.use} runs on {mod_be.name}, which has no spend cap")
    modules = {spec.use: _modules.load(spec.use) for spec in config.modules}
    producers = sorted((s for s in config.modules
                        if s.definition.kind != "finalizer"),
                       key=lambda s: s.definition.order)
    results = await run_producers(ctx, producers, modules, _background_tasks)
    system_prompts = ctx.system_prompts
    limitations: list[str] = []
    # Only analysts read figures, so a run without one has no figure scope
    # to declare (an image-only pipeline).
    analysts_ran = run_tools or run_science
    if not figures:
        # A STANDING SCOPE BOUNDARY, DECLARED RATHER THAN LEFT TO THE MODEL.
        # With `figures` off -- the default -- no figure content is read at
        # all: `tool_agent_tools` withholds `extract_figures` and the system
        # prompt carries none of the figure discipline. That is deliberate
        # (Greg, 2026-08-30: prose and tables have enough open problems), but
        # it is a limit on what the review COULD have found, and until now it
        # reached a reader only when the model happened to mention it.
        #
        # MEASURED, 2026-09-01, and this is why it is now structural:
        # 10.1210--clinem--dgag124's CONSORT screening and exclusion counts
        # exist ONLY inside the Figure 1A image, so its participant-flow
        # arithmetic was unverifiable. The run handled that correctly -- it
        # checked the cascade the text prints, returned `consistent`, and did
        # not invent the figure's numbers -- and said so only because the
        # model wrote it into a tool-call description. On a paper where the
        # model does not think to mention it, the same silence would read as
        # "the flow checks out".
        limitations.extend([] if not analysts_ran else [
            "figure values were not extracted for the numeric/science analysts: "
            "figure extraction was off, so any "
            "value printed only inside an image -- a CONSORT diagram's "
            "screening and exclusion counts, a plotted mean or error bar -- "
            "was neither checked nor counted as unchecked by those analysts. "
            "Image duplication screening is a separate check; its coverage "
            "is reported under image analysis."])
    try:
        from .webapp_index import probe_main_pdf_stub
        stub = probe_main_pdf_stub(paper_dir)
    except Exception:  # noqa: BLE001 -- a probe must never fail a paid run
        stub = None
    if stub and stub.get("pdf_suspect_stub"):
        limitations.append(
            f"the main PDF appears to be a {stub.get('main_pdf_pages')}-page "
            "publisher preview STUB beside a full-text XML -- the text was "
            "reviewed from the XML, but figure-dependent checks were "
            "effectively blind; re-fetch the full PDF")
    # A cited supplement we do not hold no longer blocks the run (supplements.
    # gate, 2026-10-18), so the run itself must say so: a 'not reported'
    # finding is read against this line.
    try:
        from .supplements import audit as _supp_audit
        _supp = _supp_audit(paper_dir, extra=extra_supplements)
    except Exception:  # noqa: BLE001 -- a probe must never fail a paid run
        _supp = None
    if _supp and _supp.get("missing") is True:
        cited = "; ".join(f"{style}: {', '.join(refs[:4])}"
                          for style, refs in (_supp.get("styles") or {}).items())
        limitations.append(
            "the paper cites supplementary material that was not available to "
            f"this review ({cited}); a 'not reported' finding may be an artefact "
            "of the missing files, and checks of values printed only there did "
            "not run")

    # Each module's own limitations, in canonical module order.
    for spec in producers:
        if spec.definition.kind == "agent":
            limitations.extend(results[spec.use].limitations)
    _tool_res = results.get("tools_agent")
    _science_res = results.get("scientific_proofreading_agent")
    tool_stage = _tool_res.stage if _tool_res else None
    tool_doc = _tool_res.doc if _tool_res else None
    science_stage = _science_res.stage if _science_res else None
    science_doc = _science_res.doc if _science_res else None

    configured_docs = ([tool_doc] if run_tools else []) + (
        [science_doc] if run_science else [])
    if configured_docs and all(d is None for d in configured_docs):
        # If both analysts died of the same ACCOUNT-level refusal, the paper did
        # not fail -- the backend did. Re-raise that rather than wrapping it in a
        # StageError, or the batch runner sees a per-paper failure and repeats
        # it once per paper (measured: 20 identical 402s across 10 papers).
        reason = _llm.fatal_backend_reason(" ".join(str(x) for x in limitations))
        if reason:
            raise _llm.BackendUnavailable(
                f"both analysis agents failed because the backend cannot serve "
                f"requests ({reason}); no paper in this corpus can run until "
                f"that is fixed. {limitations[0] if limitations else ''}"[:600])
        raise _agent.StageError(
            ("both analysis agents failed" if len(configured_docs) > 1
             else "the analysis agent failed")
            + f"; nothing to adjudicate (limitations: {limitations})")

    tool_ledger = _agent._tool_call_ledger(
        (tool_stage or {}).get("messages") or [], TOOL_AGENT_TOOLS)
    science_ledger = _agent._tool_call_ledger(
        (science_stage or {}).get("messages") or [], SCIENCE_AGENT_TOOLS)

    merged: list[dict] = []
    tool_rows = _rows_from_producer(tool_doc, "tool_expert", tool_ledger, paper_id)
    if toolset is not None:
        # THE FENCE IN CODE, independent of the transport. The server refuses
        # disabled tools, but a model can still FILE a row under one -- from
        # its own reading, or from a repair call on a backend whose built-in
        # shell cannot be removed (Codex). A one-tool experiment's findings
        # are its tools' findings; anything else is out of scope, dropped,
        # and counted where the reader looks.
        disabled = set(stage_tools(TOOL_AGENT)) - set(toolset)
        out_of_scope = [r for r in tool_rows if r.get("technique") in disabled]
        if out_of_scope:
            tool_rows = [r for r in tool_rows if r not in out_of_scope]
            limitations.append(
                f"{len(out_of_scope)} tools-agent row(s) named tools not "
                "enabled in this pipeline ("
                + ", ".join(sorted({str(r.get('technique')) for r in out_of_scope}))
                + "); they were not merged")
    merged += tool_rows
    merged += _rows_from_producer(science_doc, "science_error",
                                  science_ledger, paper_id)

    # The independent image branch has already performed its publication gate.
    image_record = (results["image_analysis"].record if "image_analysis" in results
                    else _image_disabled_record())
    merged += image_record["findings"]
    limitations.extend(image_record["limitations"])
    text_record = (results["text_forensics"].record if "text_forensics" in results
                   else None)
    if text_record and text_record.get("ran"):
        from .text_track import _family_rows_v2 as text_rows_v2
        merged += text_rows_v2(text_record.get("output", {}).get("result")
                               or {}, paper_dir)
    raw_record = (results["raw_data"].record if "raw_data" in results
                  else None)
    if "raw_data" in results:
        # Its partial-coverage / crash / timeout statements. Only AGENT
        # modules' limitations are merged above; without this a partial
        # spreadsheet scan read as a complete one (measured 2026-10-15,
        # healthcare11101497: coverage partial, limitations empty).
        limitations.extend(results["raw_data"].limitations)
    if raw_record and raw_record.get("ran"):
        from .raw_track import rows_v2 as raw_rows_v2
        merged += raw_rows_v2(raw_record.get("output") or {}, paper_dir)

    fv2.assign_finding_ids(merged, paper_id)
    producer_problems = fv2.validate_producer_constraints(merged)

    # Pre-adjudication annotation on the MERGED set. `_annotate_quotes`
    # takes a RESULT dict wrapping a findings doc (it reads
    # result["findings"]["findings"]); handing it the doc directly crashed
    # with AttributeError on every parallel run, the except below turned
    # that into a permanent "quotes ship unverified" limitation, and the
    # quote-verification guard shipped disabled -- found diagnosing the
    # failed 2026-08-21 apple_cider eval gate. Anatomy rides along because
    # the quote pass also adjudicates each variable's `provenance_quote`,
    # which `run_exhaustive`'s sd_range sweep reads.
    merged_doc = {"schema_version": "2.0", "paper_id": paper_id,
                  "anatomy": (tool_doc or {}).get("anatomy") or {},
                  "findings": merged}
    try:
        _agent._annotate_quotes({"findings": merged_doc}, paper_path)
    except Exception:  # noqa: BLE001
        limitations.append("quote annotation failed; quotes ship unverified")

    # DOES THE COMMAND WE PRINT ACTUALLY RUN? `_annotate_reproductions` was
    # called only from the legacy path, so on a parallel run every finding
    # shipped its `Reproduce:` line with no verdict attached -- measured on the
    # 2026-08-29 ajcp run, 24 of 34 findings carried a command and ZERO carried
    # `reproduction_valid`.
    #
    # THE STATIC CHECK IS NOT ENOUGH, which is why this executes. Over this
    # repo's archive of 523 distinct commands: 60 (11.5%) ran and exited 0, 352
    # (67.3%) passed the static check and then exited NON-ZERO. Every flag,
    # argument order and arity is invisible to a string test, and that is where
    # the commands actually die.
    #
    # AFFORDABLE, measured rather than assumed: 34.8s for that run's 24
    # commands, against a run costing minutes and real money -- and it found
    # that only 6 of them run. Cached by `_run_repro_cached`, so a re-render
    # does not pay again. A failure here must never cost the analysis, so the
    # limitation is recorded and the renderer then treats an absent verdict as
    # UNVERIFIED rather than as working.
    try:
        _agent._annotate_reproductions(
            {"findings": merged_doc}, paper_dir=paper_path,
            ledgers={"tool_expert": tool_ledger, "science_error": science_ledger},
            run_slug=run_slug,
            **({"disabled_verbs": _disabled_verbs(toolset)}
               if toolset is not None else {}))
    except Exception:  # noqa: BLE001
        limitations.append(
            "reproduction commands were not validated; they ship marked "
            "UNVERIFIED rather than as runnable")
    # The deterministic harness prepass (stacked-headers merge follow-
    # through): enumerate EVERY eligible target and run the duplication and
    # sd_range sweeps, the coverage-complete complement to whatever the
    # analysts aimed at. STRICTLY AFTER the quote pass -- check_sd_range may
    # only use bounds whose provenance the quote pass just adjudicated.
    exhaustive = None
    try:
        from . import prepass as _prepass
        # The harness sweeps are the tools agent's complement: without it
        # they do not run, and a restricted toolset scopes them.
        exhaustive = (_prepass.run_exhaustive(paper_path, merged_doc,
                                              enabled=toolset,
                                              ledger=tool_ledger)
                      if run_tools else None)
    except Exception as exc:  # noqa: BLE001 -- a free sweep must not kill the run
        limitations.append(
            f"the harness sweeps failed ({type(exc).__name__}: {exc}); no "
            "harness-aimed check, GRIM included, covers this run")
    # THE GRIM SWEEP'S FAILURES ARE FINDINGS (Dan, 2026-10-18): one row per
    # table, producer `harness`, filed before adjudication so the adjudicator
    # judges them like any other row.
    grim_sweep = (exhaustive or {}).get("grim") if isinstance(exhaustive, dict) else None
    if isinstance(grim_sweep, dict) and grim_sweep.get("failures"):
        from . import grim_harness as _gh
        merged += _gh.finding_rows(grim_sweep, paper_id)
    from . import secondlook
    second_look = secondlook.worklist(merged)
    tally = _agent.checks_tally((tool_stage or {}).get("messages"), merged_doc)
    if isinstance(exhaustive, dict):
        # The adjudicator sees the harness sweep's outcome in its tally
        # block; accusatory results are listed so silence stays
        # distinguishable from not-having-run.
        tally = dict(tally or {})
        tally["harness_sweep"] = {
            k: exhaustive.get(k)
            for k in ("n_tables", "n_accusatory", "accusatory", "why",
                      "not_run")
            if exhaustive.get(k) is not None}

    # The adjudicator.
    # WHERE THE PAPER IS. The two analysts get these paths in their prompts;
    # the adjudicator got none, and spent 66% of its tool calls guessing
    # filenames -- see `adjudicate._sources_block` for the measurement. Built
    # from the SAME `src` record the analyst prompts use, so the three stages
    # cannot be told different things about one paper.
    from .extraction.markdown_out import body_path as _md_body
    _md = _md_body(paper_dir)
    docket_sources = {
        "paper directory": paper_dir,
        "plain text (markdown)": _md if _md.is_file() else None,
        "XML full text (extract_xml)": src.xml,
        "main PDF (extract_pdf)": src.main_pdf,
        "HTML full text (extract_html)": src.html,
        "supplements (extract_supplement)": list(src.si_readable or []),
        "analysis code the science agent wrote": (
            (Path(paper_dir) / "analysis_code")
            if (Path(paper_dir) / "analysis_code").is_dir() else None),
    }
    image_bundle = _image_evidence_bundle(merged)
    docket = adjudicate.build_docket(merged, paper_text=text,
                                     tally=json.dumps(tally, default=str),
                                     second_look=second_look,
                                     sources=docket_sources,
                                     unchecked={
                                         "tool_expert": (tool_doc or {}).get("unchecked"),
                                         "science_error": (science_doc or {}).get("unchecked"),
                                     })
    if image_bundle["packets"] or image_bundle["errors"]:
        docket["text"] += "\n\nVISUAL EVIDENCE: Read every listed attachment before reinterpreting image findings. " \
                          "Packet IDs scope attachment IDs. Missing delivery preserves provisional status.\n" + json.dumps(image_bundle)
    adjudicator_stage = None
    deduplicated: list[dict] = []
    if not run_adjudicator:
        # NO ADJUDICATOR TO MERGE THE SAME STATISTIC FILED TWICE (1.91.0):
        # statcheck and recalc_stat_to_p each file `t(94) = 1.64, p < .001`,
        # and both used to stand as separate findings. Collapsed here by the
        # statistic itself, never the quote; the removed rows are listed in
        # coverage_summary.deduplicated.
        merged, deduplicated = fv2.deduplicate_by_statistic(merged)
        if deduplicated:
            limitations.append(
                f"{len(deduplicated)} p-value finding(s) restated a statistic "
                "another finding of the same outcome already reported and were "
                "merged into it (no adjudicator ran); each is listed in "
                "coverage_summary.deduplicated")
        # NOT CONFIGURED is a decision about this run, not a failure: the
        # same finaliser as every other skip (provisional severities,
        # impossible rows stamped cross_check "not_run"), with its reason.
        findings, adj_summary = adjudicate.apply_skip(
            merged, skipped_reason=(
                f"adjudication not configured in pipeline {config.name!r}"))
        if merged:
            limitations.append(
                "adjudication was not configured for this pipeline; "
                "severities are provisional")
    else:
        findings, adj_summary, adjudicator_stage = await modules[
            "adjudicator"].finalize(ctx, merged, docket=docket,
                                    image_bundle=image_bundle, text=text,
                                    limitations=limitations)
    adj_summary["n_not_adjudicated"] = docket["n_not_adjudicated"]

    # WHAT THE TOOLS AGENT'S OWN TOOLS ACCUSED AND THE FINAL REVIEW DOES NOT
    # ACCOUNT FOR (1.91.0), as a structured record. The recovery pass reported
    # this only as a sentence in `limitations`, so no reader could count it
    # across runs. Computed on the FINAL findings, minus what the recovery
    # pass dismissed with a reason.
    unaccounted = _unaccounted_record(
        findings, tool_ledger,
        ((_tool_res.extra or {}).get("unfiled_stage") or {}).get("dismissed_calls")
        if _tool_res else None)
    if unaccounted["n"]:
        limitations.append(
            f"{unaccounted['n']} suspicious-or-worse result(s) from the tools "
            "agent's own checks were neither filed as a finding nor dismissed "
            "with a reason; listed in coverage_summary.unaccounted_tool_results")

    # Persisted anchors -- never fails the run.
    _anchors.annotate_findings(paper_dir, findings)

    # WHO SAYS THIS CONSEQUENCE WAS COMPUTED. The model writes a `consequence`
    # block and the schema lets it write `basis: "computed"`; nothing on this
    # path ever checked. MEASURED on the run of 2026-08-29: 14 of 34 findings
    # claimed `computed` and 12 of those were `computed_by: "model_reading"`.
    # `bundle.py` ranks computed above asserted within a severity band and
    # prints the word, so the claim reached the reader wearing the toolkit's
    # own authority. Replayed with this pass: 14 -> 1.
    #
    # `annotate_v2`, not `annotate`: the legacy guard's exact-key match cannot
    # see v2's derivation-suffixed keys, and corroborates NOTHING here --
    # including the one claim that genuinely is corroborable.
    consequence_summary = None
    try:
        _adj_ledger = _agent._tool_call_ledger(
            (adjudicator_stage or {}).get("messages") or [], ADJUDICATOR_TOOLS)
        consequence_summary = _consequence.annotate_v2(
            findings, tool_ledger + science_ledger + _adj_ledger)
    except Exception as exc:  # noqa: BLE001 -- never lose a paid analysis
        # RECORDED, not swallowed. A silent failure here restores the exact
        # false-authority channel this exists to close, and the empty Audit
        # panel of 2026-08-29 is what an unrecorded gap looks like downstream.
        consequence_summary = {"error": f"{type(exc).__name__}: {exc}"}

    from . import reassurance
    reassuring = reassurance.scan(findings, adj_summary)
    if reassuring:
        limitations.append(
            f"{len(reassuring)} passage(s) in this review read as reassurance about "
            "the paper (" + "; ".join(sorted({r['match'] for r in reassuring}))
            + "): a consistent check is not clearance (rulebook rules 1 and 9)")
    analysed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "schema_version": "2.0",
        "paper_id": paper_id,
        "run_id": __import__("metascience_agent.history_runtime", fromlist=["CONTEXT"]).CONTEXT.get().get("run_id") or _mint_run_uid(paper_id, analysed_at),
        "paper_metadata": fv2.paper_metadata_projection(metadata),
        "channels": fv2.channels_block(
            tool_expert=(_stage_state(tool_stage) if run_tools
                         else _not_configured_state(config)),
            science_error=(_stage_state(science_stage) if run_science
                           else _not_configured_state(config)),
            image_forensics=_stage_state(None, image_record),
            tortured_phrases=_stage_state(None, text_record)
            if text_forensics else ("did_not_run", "text track disabled"),
            # Only when configured, so a run without it is byte-identical.
            **({"raw_data": _raw_state(raw_record)}
               if config.has("raw_data") else {}),
        ),
        "pipeline": config.record(),
        "findings": findings,
        "adjudication": adj_summary,
        "coverage": _with_grim_coverage(
            _coverage_with_ledger_fallback(tool_doc, tool_ledger), grim_sweep),
        "anatomy": (tool_doc or {}).get("anatomy") or {},
        "unchecked": ((tool_doc or {}).get("unchecked") or [])
        + ((science_doc or {}).get("unchecked") or []),
        "statistics_register": (tool_doc or {}).get("statistics_register") or [],
        "checks_tally": tally,
        # ALWAYS WRITTEN, EMPTY LIST AND ALL. This was `if producer_problems:`,
        # so a clean run and a run where the validator never executed produced
        # the identical artifact -- absence rendered as knowledge, on the record
        # that says whether the finding schema's own constraints held. Every
        # neighbouring key here ships empty (`unchecked`, `statistics_register`)
        # for the same reason.
        #
        # `validate_producer_constraints` is what answers the question
        # `clamp_provisionals` delegates: a row with `outcome: problem` and no
        # `provisional_severity` is flagged `problem_requires_provisional`. That
        # chain works -- verified on a live run 2026-08-29, where all 13 rows
        # lacking a provisional were `pass` or `undecided`, which correctly have
        # none, and every `problem` row carried one. What did not work was being
        # able to TELL that from the artifact.
        # BOTH SEAMS, because three of these constraints cannot fire at the
        # first one. `validate_producer_constraints` runs at line 896, BEFORE
        # adjudication -- and `severity_requires_problem`, `severity_on_discarded`
        # and `fast_screen_provisional` read `severity`, `adjudication.action`
        # and `severity_is_provisional`, none of which exists until
        # `adjudicate.apply` writes them. Verified: a row with `outcome: pass`
        # and `severity: 5` produces NO problem pre-adjudication and the correct
        # one post.
        #
        # So an empty list here used to mean "the constraints that could fire at
        # this seam held", and the artifact did not say which those were --
        # which is the same absence-rendered-as-knowledge the comment below was
        # written to fix, one level down. Running it again on the adjudicated
        # rows makes the empty list mean what a reader takes it to mean.
        "producer_constraint_problems": _merge_constraint_problems(
            producer_problems,
            fv2.validate_producer_constraints(findings) + reassuring),
    }

    stages_meta: dict[str, Any] = {}
    for label, stage in (("tool_agent", tool_stage),
                         ("science_agent", science_stage),
                         ("adjudicator", adjudicator_stage)):
        if stage is not None:
            _module = {"tool_agent": "tools_agent",
                       "science_agent": "scientific_proofreading_agent",
                       "adjudicator": "adjudicator"}[label]
            _settings = ctx.settings_for(_module)
            meta = _agent._stage_meta(
                stage, _settings.model,
                output_parse_path=stage.get("output_parse_path"))
            if _settings is not ctx.run_settings:
                # A module on its own backend says so; the run-level fields
                # describe the run's default.
                meta["llm_backend"] = _settings.name
            meta["internet"] = (label == "science_agent")
            if label == "science_agent":
                meta["n_web_calls"] = sum(
                    1 for r in science_ledger
                    if r.get("tool_short") in _WEB_TOOLS)
            stages_meta[label] = meta
            # 16% OF A RUN'S SPEND WAS INVISIBLE HERE. MEASURED 2026-08-22:
            # $1.82 of $11.57 across ten papers -- $0.85 on one -- because
            # `_retry_if_empty` returns one attempt and DISCARDED the other,
            # money included. The total was right and the decomposition was
            # not, so a reader could not see which stage cost what.
    _add_ledger_only_attempts(stages_meta)
    for label, record in (("image_forensics", image_record),
                          ("text_forensics", text_record),
                          ("raw_data", raw_record)):
        if record is not None:
            stages_meta[label] = {k: v for k, v in record.items()
                                  if k not in ("output", "findings_rows", "findings")}

    # The prompts that identify THIS run are the parallel trio; hashing the
    # legacy stage prompts here would leave a science_error.md edit invisible
    # to the recorded fingerprint. Provenance must never break a run.
    try:
        # Empty for a pipeline with no agent module (image only): that hashes
        # as the empty blob, exactly as `runs.build_fingerprint` recomputes
        # it. None would fall back to the full-review trio and call every
        # such run stale.
        prompt_blob = prompts.prompt_blob(config)
    except Exception:  # noqa: BLE001
        prompt_blob = None
    from .version import __version__ as _release
    unreported_cost = sorted(
        label for label, m in stages_meta.items()
        if isinstance(m, dict) and m.get("cost_reported") is False)
    run_meta = {
        "paper_id": paper_id,
        "mode": "parallel",
        "schema_version": "2.0",
        "run_id": doc["run_id"],
        "analysed_at": analysed_at,
        # The release number: db_push reads it into runs.pipeline_version,
        # and the 2026-08-21 live run pushed NULL because only the legacy
        # _run_stamp recorded it.
        "version": _release,
        "llm_backend": be.name,
        "model": model,
        "effort": effort,
        "stages": stages_meta,
        # WHAT THIS RUN WAS CONFIGURED TO DO, resolved, plus the hash of each
        # system prompt as SENT. `runs.build_matches` rebuilds the expected
        # fingerprint from this block rather than assuming the default.
        "pipeline": {**config.record(), "system_prompt_sha256": {
            label: hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
            for label, text in sorted(system_prompts.items())}},
        "limitations": limitations,
        "total_cost_usd": _agent.spend_so_far()["total_cost_usd"],
        # A STAGE WHOSE BACKEND REPORTS NO COST adds 0.0 to the total above, so
        # the total is a lower bound and a Codex-only run reads $0.00. Named
        # here so no reader (webapp_index first) mistakes it for free.
        **({"cost_unreported_stages": unreported_cost}
           if unreported_cost else {}),
        # Legacy parity: the harness prepass summary reaches run_meta so a
        # reader can see the deterministic sweeps' coverage (or their named
        # absence) without opening the docket.
        **({"exhaustive_checks": exhaustive}
           if isinstance(exhaustive, dict) else {}),
        # HOW MANY CONSEQUENCE CLAIMS SURVIVED CORROBORATION. Recorded rather
        # than left implicit: the counts ARE the measurement of the channel this
        # closes, and a reader comparing runs needs to see the ratio move.
        **({"consequence": consequence_summary}
           if isinstance(consequence_summary, dict) else {}),
        "unaccounted_tool_results": unaccounted,
        **({"deduplicated": deduplicated} if deduplicated else {}),
        **_agent._provenance(be, prompt_blob=prompt_blob),
        # WHAT THE RUN ACTUALLY SWEPT. In `run_meta` and not only in the
        # returned result, because run_meta.json is what reaches disk: the
        # legacy result carried this and the parallel one did not, so no
        # archived parallel run names a supplement at all.
        # `supplied_supplement_paths` in particular cannot be recovered by
        # re-listing the paper directory later, since a `--supplement` may
        # live anywhere, so a run whose record omits it is not reproducible
        # from its own metadata. It matters more since v1.23.0: the census
        # counts supplements toward its denominator, so which ones were
        # readable is now part of a published coverage figure.
        **_agent._supplement_record(src, extra_supplements),
    }

    # Only CONFIGURED modules can fail: an analyst the pipeline did not ask
    # for is not missing, and adjudication that was not configured is not an
    # adjudication that failed.
    is_error = ((run_tools and tool_doc is None)
                or (run_science and science_doc is None)
                or run_adjudicator and not adj_summary.get("ran", False)
                and bool(merged))
    # A DETERMINISTIC MODULE THAT IS THE WHOLE RUN decides its outcome. Beside
    # an analyst, an image or text failure stays a named limitation (as it
    # always has: those tracks never fail a review); alone, it is the run, and
    # a failed image-only experiment must not read as a finished one.
    sole_failures = []
    if not (run_tools or run_science):
        # `is_error` too: a screening exception after a successful detection
        # leaves `ran` true and the status "incomplete", and is still a failure.
        if config.has("image_analysis") and (
                not image_record.get("ran")
                or image_record.get("is_error")
                or image_record.get("execution_status") == "failed"):
            sole_failures.append("image_analysis")
        if config.has("text_forensics") and not (
                text_record and text_record.get("ran")):
            sole_failures.append("text_forensics")
        if config.has("raw_data") and (raw_record or {}).get("is_error"):
            # A paper with no spreadsheet did not FAIL; it had nothing to read.
            sole_failures.append("raw_data")
    is_error = bool(is_error or sole_failures)
    incomplete = (config.has("image_analysis")
                  and image_record.get("execution_status") == "incomplete")
    outcome = "error" if is_error else "incomplete" if incomplete else "ok"
    # Recorded on both documents: the batch skip reads it (a failed partial
    # experiment is not a done one) from run_meta, or from findings.v2 when
    # run_meta is unreadable.
    run_meta["pipeline"]["outcome"] = outcome
    doc["pipeline"]["outcome"] = outcome
    if sole_failures:
        limitations.append(
            f"the pipeline's only module(s) {', '.join(sole_failures)} did not "
            "complete; this run examined nothing it can report as clean")
    return {
        "mode": "parallel",
        "paper_id": paper_id,
        "paper_path": paper_path,
        "extraction_record": extraction_record,
        **_agent._supplement_record(src, extra_supplements),
        # `write_parallel_outputs` archives only THIS run's scripts, and it
        # needs the slug to know which subdirectory is ours.
        "run_slug": run_slug,
        # What actually instructed each agent, as sent. See `_remember`.
        "system_prompts": system_prompts,
        "findings_v2": doc,
        "adjudication_raw": (
            _agent._extract_json(adjudicator_stage)[0]
            if adjudicator_stage else None),
        "docket": {k: docket[k] for k in
                   ("n_itemized", "n_not_adjudicated")},
        "tool_agent": tool_stage, "science_agent": science_stage,
        # The unfiled-results pass's own transcripts (modules/_analyst), by
        # stage label, so `messages.<label>_unfiled.json` is archived.
        "unfiled_stages": {
            _module_defs()[res.name].label: res.extra["unfiled_stage"]
            for res in (_tool_res, _science_res)
            if res is not None and (res.extra or {}).get("unfiled_stage")},
        "adjudicator": adjudicator_stage,
        "image_track": image_record, "text_track": text_record,
        **({"raw_data_track": raw_record} if raw_record is not None else {}),
        "run_meta": run_meta,
        "limitations": limitations,
        "total_cost_usd": _agent.spend_so_far()["total_cost_usd"],
        # THE USAGE TABLE PRINTED "output tokens: 0" FOR A RUN THAT PRODUCED
        # ABOUT 1.3 MILLION. MEASURED 2026-08-22: ten papers, stages writing
        # 40k-73k output tokens each, all of it in the archived transcripts --
        # and `batch.py` wrote null because this dict had no such key, so
        # `cli._usage_table` rendered `int(None or 0)`. The "input tokens
        # 41,261,824" on the same table was cache-read alone. Summed from the
        # stage metas, which is where the per-stage numbers already live; the
        # retry rows are included, because the retries were billed.
        **_usage_totals(stages_meta),
        "is_error": bool(is_error),
        "verdict": adj_summary.get("verdict"),
    }


def _merge_constraint_problems(pre: list, post: list) -> list:
    """Problems from both validation seams, deduplicated, order preserved.

    A problem visible at both seams is one problem, not two. Identity is the
    (row, code) pair -- the same row failing two DIFFERENT constraints is two
    problems and must stay two.
    """
    out, seen = [], set()
    for source, rows in (("pre", pre or []), ("post", post or [])):
        for p in rows:
            if not isinstance(p, dict):
                continue
            key = (p.get("index"), p.get("slug"), p.get("code"))
            if key in seen:
                continue
            seen.add(key)
            out.append({**p, "seen_at": source})
    return out


def _build_coverage_summary(result: dict, ledgers: dict, doc: dict) -> dict:
    """The coverage census for a parallel run.

    THE ONLY INDEPENDENT DENOMINATOR THIS SYSTEM HAS. It reads the paper's own
    tables with no model involved and answers "how many numbers COULD have been
    checked", so the model's own "I checked N" has something to be divided by.
    Without it a reader gets effort, not coverage, and the defect it was built
    for is on the record: one report listed three tables as checked while 0 of
    79 checkable cells had received a cell-level check.

    It ran only on the retiring legacy path until v1.23.0, even though
    `docs/specs/pipeline.md §12` says the enrichment block "attaches to the
    ADJUDICATED object". Ported per that sentence.

    Each block is independently guarded and RECORDS its failure as
    `{"error": ...}` rather than vanishing -- the legacy assembly's own
    contract, and the reason a missing block cannot be mistaken for a clean
    one. `stage1_reconciliation` is deliberately NOT ported: its two inputs (a
    v1 stage-1 findings list and the legacy editorial object) do not exist
    here, and v2 answers the same question as
    `adjudication.docket.n_not_adjudicated`.
    """
    paper_path = result.get("paper_path")
    led = [r for rows in ledgers.values() for r in (rows or [])]
    out: dict = {}
    if not paper_path:
        return {"error": "no paper_path on the result; the census needs the "
                         "paper's own tables and cannot be computed without it"}
    paper_dir = Path(paper_path)
    paper_dir = paper_dir if paper_dir.is_dir() else paper_dir.parent

    # 1. THE CENSUS. Fed the LEDGER rather than the messages: `_slim_messages`
    #    empties large tool_result payloads before they are persisted, so a
    #    census computed from an archived run reports nothing checked (measured
    #    2026-09-03: 0 chars in the messages, 25,519 in the ledger for the same
    #    check_table call). See `agent._tool_events`.
    try:
        cov = _agent._checkable_coverage(paper_dir, None, led)
        # A NAMED ABSENCE, NOT A MISSING KEY. `_checkable_coverage` returns
        # None when it found no table to survey, which is a real and
        # legitimate answer -- but dropping the block entirely makes "this
        # paper prints no tables" indistinguishable from "we could not read
        # the paper", on the one artifact whose job is telling a reader what
        # was measurable.
        out["checkable"] = cov if cov is not None else {
            "no_cells_examined": True,
            "note": ("No table cell in this paper could be surveyed: the "
                     "extractor found no tables to walk. This is a statement "
                     "about what we could read, not a clean result, and it is "
                     "not a count of zero checkable cells."),
        }
    except Exception as exc:  # noqa: BLE001 -- recorded, never swallowed
        out["checkable"] = {"error": f"census failed: {type(exc).__name__}: {exc}"}

    # 2. COMPLETENESS -- the model-free manifest of checkable items and how
    #    each ended the run. `n_checked` is deliberately withheld: no persisted
    #    item identity joins a tool call back to a manifest row, and a count of
    #    "unknown" must not be published as a count of zero.
    manifest = None
    try:
        from . import completeness as _completeness
        manifest = _completeness.build_manifest(paper_path)
        if manifest.get("n_items"):
            disp = _completeness.disposition_report(manifest)
            gate = _completeness.gate(disp, enforce=False)
            out["completeness"] = {
                **{k: disp[k] for k in ("n_items", "n_refused", "n_outstanding",
                                        "by_disposition", "complete")},
                **{k: manifest.get(k) for k in
                   ("n_table_items", "n_body_items", "n_supplement_items",
                    "n_supplement_table_items", "n_supplement_body_items")},
                "n_checked": None,
                "n_checked_measurable": False,
                "n_checked_unmeasured_because": (
                    "no persisted item identity joins a tool call back to a "
                    "manifest row, so how many items were CHECKED cannot be "
                    "counted. This is not a count of zero."),
                "gate_passed": gate["passed"],
                "gate_enforced": gate["enforced"],
                "gate_message": gate["message"],
                "note": _completeness.render(disp),
            }
    except Exception as exc:  # noqa: BLE001
        out["completeness"] = {
            "error": f"manifest could not be built: {type(exc).__name__}: {exc}"}

    # 3. WHERE EVERY NUMBER CAME FROM -- derived, transcribed, or unauditable.
    try:
        from . import computation as _comp
        hay, hay_problem = _agent._number_haystack(paper_path, manifest)
        ca = _comp.audit(doc.get("findings") or [], haystack=hay)
        if hay_problem:
            ca["haystack_problem"] = hay_problem
        out["computation_audit"] = ca
    except Exception as exc:  # noqa: BLE001
        out["computation_audit"] = {
            "error": f"audit failed: {type(exc).__name__}: {exc}"}

    # 4. THE REGISTER'S FLOOR TRIPWIRE. v2 carries the register's ROWS at the
    #    document's top level but has never validated them: `register.validate`
    #    had exactly one call site and it was the legacy writer.
    try:
        from . import completeness as _c3
        from . import register as _reg
        body, _ = _c3._read_body(paper_dir)
        out["statistics_register"] = _reg.validate(
            doc.get("statistics_register"), text=body or None,
            floor_items=_c3._body_items(body or ""),
            provenance=_agent._text_provenance(paper_path))
    except Exception as exc:  # noqa: BLE001
        out["statistics_register"] = {
            "error": f"register validation failed: {type(exc).__name__}: {exc}"}

    # 5. GLYPH CORRUPTION. A font that renders a minus sign as a hyphen, or a
    #    digit as a letter, silently changes the arithmetic a checker sees.
    try:
        from .glyphs import scan_paper as _glyph_scan
        g = _glyph_scan(paper_dir)
        out["text_integrity"] = {
            "quarantine": bool(g.get("quarantine")),
            "note": g.get("note"),
            "patterns": [{k: pat.get(k) for k in
                          ("pattern", "count", "corrupts_digits", "examples")}
                         for pat in (g.get("patterns") or [])],
        }
    except Exception as exc:  # noqa: BLE001
        out["text_integrity"] = {
            "error": f"glyph scan failed: {type(exc).__name__}: {exc}"}

    # 6. WHAT THE EXTRACTOR DID. `analyze_paper_parallel` calls
    #    `ensure_paper_extracted` and discarded its record until v1.23.0.
    rec = result.get("extraction_record")
    if isinstance(rec, dict):
        out["extraction"] = rec

    # 7. RECONCILIATION RECORDS (1.91.0), copied from run_meta so the census a
    #    reader opens carries them: tool results nobody accounted for, and the
    #    restatements merged away when no adjudicator ran.
    meta = result.get("run_meta") or {}
    if isinstance(meta.get("unaccounted_tool_results"), dict):
        out["unaccounted_tool_results"] = meta["unaccounted_tool_results"]
    if meta.get("deduplicated"):
        out["deduplicated"] = meta["deduplicated"]
    return out


def _unaccounted_record(findings: list[dict], ledger: list[dict] | None,
                        dismissed: list[dict] | None) -> dict:
    """The tool agent's suspicious-or-worse calls that no final finding
    accounts for (`fv2.unaccounted_verdicts`) and the recovery pass did not
    dismiss. One entry per call, with its arguments, so it can be replayed."""
    def key(tool, args):
        return (str(tool), json.dumps(args, sort_keys=True, default=str))
    gone = {key(d.get("tool"), d.get("input")) for d in dismissed or []
            if isinstance(d, dict)}
    items, seen = [], set()
    try:
        verdicts = fv2.unaccounted_verdicts(findings, ledger)
    except Exception as exc:  # noqa: BLE001 -- recorded, never swallowed
        return {"n": 0, "items": [], "error": f"{type(exc).__name__}: {exc}"}
    for v in verdicts:
        call = v.get("call") or {}
        k = key(v.get("tool"), call.get("input"))
        if k in gone or (call.get("seq"), v.get("expanded")) in seen:
            continue
        seen.add((call.get("seq"), v.get("expanded")))
        items.append({"tool": v.get("tool"), "severity": v.get("severity"),
                      "seq": call.get("seq"), "input": call.get("input"),
                      **({"batch_row": True} if v.get("expanded") else {})})
    return {"n": len(items), "n_dismissed": len(gone), "items": items}


#: Which producer's findings each agent is answerable for. Only an agent that
#: CLAIMS a check ran can have named one that did not, so the adjudicator --
#: which re-reads findings rather than deriving them -- has none of its own.
_AUDIT_PRODUCERS = {"tool_agent": "tool_expert", "science_agent": "science_error"}


def _write_sandbox_audit(result: dict, ledgers: dict, doc: dict, _w) -> None:
    """`sandbox_audit.json` for a parallel run, and `run_meta.sandbox`.

    `docs/specs/pipeline.md §13` has listed this among the parallel run's
    outputs since the v2 cutover ("per-stage union, as today") and
    `README.md` calls it "**read this one** ... a silently un-sandboxed run is
    otherwise indistinguishable from a validated one". It was never written.
    MEASURED 2026-09-03: none of the four archived parallel runs has one,
    while all three legacy runs do, and `obligations.py` had come to excuse
    the absence as a "legacy-path artifact" -- a missing requirement wearing
    the clothes of a design decision.

    Each agent is scored against ITS OWN ledger and ITS OWN findings, joined
    by `producer`. The alternative -- one union over every finding -- was
    measured wrong on the legacy path: 29 top-level unbacked findings fell to
    6 once each stage was scored against the tools it could actually call.

    The adjudicator is audited for breaches (a `Bash` call there is a breach
    wherever it happens) but is answerable for no unbacked findings: it does
    not derive them.
    """
    allowed = {"tool_agent": TOOL_AGENT_TOOLS,
               "science_agent": SCIENCE_AGENT_TOOLS,
               "adjudicator": ADJUDICATOR_TOOLS}
    by_producer: dict[str, list] = {}
    for f in (doc.get("findings") or []):
        if isinstance(f, dict):
            by_producer.setdefault(f.get("producer"), []).append(f)
    audits: dict[str, dict] = {}
    for label, led in ledgers.items():
        if not led:
            continue
        findings = by_producer.get(_AUDIT_PRODUCERS.get(label), [])
        audits[label] = _agent._sandbox_audit(led, allowed[label], findings)
        # THE GUARD AUDIT, which v1.22.0's port dropped. The legacy writer
        # attaches it per stage (`agent.py`: `audits[key]["guards"] = ...`)
        # and `bundle._guards_by_stage` reads
        # `sandbox_audit.stages.<stage>.guards`; its docstring asserts
        # "_guard_audit runs on every stage of every run", which was false for
        # every parallel run between v1.22.0 and now -- the viewer's guard
        # pane was empty and nothing said why.
        #
        # This is the more consequential half of the sandbox audit. A guard is
        # a precondition without which a check INVERTS rather than degrades: a
        # defaulted `data_type` is the single likeliest cause of a false
        # accusation, and this is the only thing that counts how often one is
        # supplied.
        audits[label]["guards"] = _agent._guard_audit(led)
    if not audits:
        # WRITTEN ANYWAY, saying so. No ledger means no stage recorded a tool
        # call -- every agent failed, or the run was refused -- and omitting
        # the file would make "we could not look" indistinguishable from "we
        # looked and it was clean", on the one artifact whose entire job is
        # telling those apart.
        _w("sandbox_audit.json", {
            "level": "not_measured",
            "verdict": ("not measured: no agent produced a tool ledger, so "
                        "whether anything ran outside the validated surface "
                        "is unknown for this run"),
            "n_unbacked_findings": None,
            "unbacked_finding_ids": [],
            "n_unvalidated_total": None,
            "n_severe_total": None,
            "n_off_allowlist_total": None,
            "stages": {},
        })
        return
    audit_doc = _agent.compose_sandbox_audit(audits, "tool_agent")
    _w("sandbox_audit.json", audit_doc)
    meta = result.get("run_meta")
    if isinstance(meta, dict):
        meta["sandbox"] = _agent.sandbox_run_meta(audit_doc)


def _write_delivery_and_source_coverage(result: dict, ledgers: dict,
                                        _w) -> None:
    """Two per-run audits the legacy writer produced and this one did not.

    `run_meta.delivery` -- `handoff.delivery_audit` over the tool agent's
    ledger. A tool result that overflowed and never reached the model is the
    difference between a starved run and an incurious one, and the viewer
    renders the section ONLY when the key is present, so its absence was
    silent (`bundle.py`, "Information that did not arrive").

    `source_coverage.json` -- `quotes.verify_ledger` per agent. Operator-only
    by the standing decision in `tests/test_output_is_read.py`; the bundle
    recounts inline rather than reading the file, so the two cannot drift.

    Neither may cost a paid run its archive, so both are caught -- but a
    caught failure is RECORDED, never swallowed. `delivery` becomes an
    explicit `ok: None` with the reason, which is the shape a reader already
    knows means NOT MEASURED; the coverage tally gets a named error file
    beside the one it would have written, the same contract
    `value_register.error.txt` carries. Silence here would say every fetch
    arrived and every check cited its source, which is the absence-as-evidence
    error this repository exists to refuse.
    """
    meta = result.get("run_meta")
    if ledgers.get("tool_agent"):
        try:
            from .handoff import delivery_audit
            if isinstance(meta, dict):
                meta["delivery"] = delivery_audit(ledgers["tool_agent"])
        except Exception as exc:  # noqa: BLE001 -- recorded, not swallowed
            if isinstance(meta, dict):
                meta["delivery"] = {"ok": None, "note": (
                    "the delivery audit could not run "
                    f"({type(exc).__name__}: {exc}), so whether the model's "
                    "fetches ARRIVED is not measured")}
    try:
        cov = _agent._sweep_source_coverage(ledgers, result.get("paper_path"))
        if cov:
            _w("source_coverage.json", cov)
    except Exception as exc:  # noqa: BLE001 -- recorded, not swallowed
        _w("source_coverage.error.txt",
           f"the per-agent quote-verification tally could not be computed: "
           f"{type(exc).__name__}: {exc}\n")


def write_parallel_outputs(result: dict, out_dir: str | Path,
                           render_pdf: bool = True) -> dict:
    """Seal a private report workspace before publishing compatibility files."""
    from .analysis_runs import now
    from .atomicio import file_lock
    from .history_runtime import result_archive
    parent = result.get("run_meta", {}).get("history")
    if not parent:
        return _write_parallel_outputs_impl(result, out_dir, render_pdf)
    paper = Path(result["paper_path"])
    if paper.is_file(): paper = paper.parent
    archive = result_archive(result)
    staging = archive.base / "work" / parent["id"] / ("report_" + uuid.uuid4().hex)
    destination = Path(out_dir)
    try:
        written = _write_parallel_outputs_impl(result, staging, render_pdf, publish=False)
        with file_lock(paper / ".report_publish.lock"):
            destination.mkdir(parents=True, exist_ok=True)
            for source in staging.rglob("*"):
                if source.is_file():
                    target = destination / source.relative_to(staging)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    temporary = target.with_name(target.name + "." + uuid.uuid4().hex + ".tmp")
                    shutil.copyfile(source, temporary)
                    temporary.replace(target)
        from .db_push import auto_push
        auto_push(paper, destination)
        from .webapp_index import refresh_index_paper
        refresh_index_paper(paper)
        published = {key: destination / value.relative_to(staging)
                     for key, value in written.items()}
        # The same leak `analysis_runs.workspace()` had, in the report writer:
        # this staging tree under work/ was never removed on any path, so every
        # run left a second copy of its report behind. Success only -- a failed
        # run's staging is the only record of what it managed to write -- and
        # best effort, because the files are already published to `destination`
        # by the loop above.
        if not os.environ.get("METASCIENCE_KEEP_WORKSPACE"):
            shutil.rmtree(staging, ignore_errors=True)
        return published
    except BaseException as exc:
        current = result.get("run_meta", {}).get("history") or parent
        if not (archive.base / "runs" / f"{current['id']}.json").exists():
            archive.seal(current, status="failed", detail=str(exc), completed_at=now())
        raise


def _write_parallel_outputs_impl(result: dict, out_dir: str | Path,
                                 render_pdf: bool = True, *, publish=True) -> dict:
    """The parallel run's archive. File names follow R6 (per-agent prompt/ledger/messages,
    adjudication.json beside the applied findings).

    `render_pdf`: the README lists `report.pdf` among a run's outputs and
    `analyze --pdf` defaults on, but until 2026-09-02 only the LEGACY writer
    rendered one -- on the default pipeline the flag reached nothing. The
    render is best-effort and precedes run_meta.json so a failure's reason
    (`run_meta.pdf_error`) reaches the file.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    def _w(name: str, payload) -> None:
        p = out / name
        if isinstance(payload, str):
            p.write_text(payload, encoding="utf-8")
        else:
            p.write_text(json.dumps(payload, indent=2, default=str),
                         encoding="utf-8")
        written[name] = p

    doc = result["findings_v2"]
    from .disclaimer import DISCLAIMER_SHORT

    allowed = {"tool_agent": TOOL_AGENT_TOOLS,
               "science_agent": SCIENCE_AGENT_TOOLS,
               "adjudicator": ADJUDICATOR_TOOLS}
    # THE LEDGERS, ONCE. Written per label further down, and read here by the
    # three audits that need every stage at once. Building them twice would
    # let the audit and the archive disagree about the same run.
    ledgers = {
        label: _agent._tool_call_ledger(
            (result.get(label) or {}).get("messages") or [], allowed[label])
        for label in ("tool_agent", "science_agent", "adjudicator")
        if result.get(label)
    }

    # THE TOOL SIDE'S RECEIPTS, joined to the transcript's ledger
    # (receipts.py): which ledger calls our tool layer really answered, and
    # which answers no ledger row claims. Reported, never acted on.
    _slug = result.get("run_slug")
    if _slug:
        from . import receipts as _receipts
        joined = {}
        for label, ledger in ledgers.items():
            text = _receipts.collect(_slug, label)
            recs = [json.loads(x) for x in (text or "").splitlines() if x.strip()]
            joined[label] = _receipts.join(ledger, recs)
            if text is not None:
                _w(f"receipts.{label}.jsonl", text)
        result["run_meta"]["tool_receipts"] = joined

    # THE CENSUS, ONTO THE DOCUMENT, BEFORE IT IS SERIALISED. Per
    # docs/specs/pipeline.md §12 the enrichment block "attaches to the
    # ADJUDICATED object". Order matters and has bitten this repo twice:
    # `run_meta.sandbox` was set AFTER run_meta.json was written and reached
    # the in-memory dict and never the file, on 21 archived runs.
    try:
        doc["coverage_summary"] = _build_coverage_summary(result, ledgers, doc)
    except Exception as exc:  # noqa: BLE001 -- recorded, never swallowed
        doc["coverage_summary"] = {
            "error": f"the coverage census could not be assembled: "
                     f"{type(exc).__name__}: {exc}"}

    # WHAT THE DISPATCHER DECLINED, from the machine rather than the model.
    # `dispatch.check_table` builds a per-(cell, check) `not_run` record with a
    # reader-grade reason precisely so coverage does not depend on the model
    # remembering what it skipped, and on the parallel path nothing consumed
    # it. A run that submitted three tables and had every cell inside them
    # refused still read as "checked", because checked meant attempted.
    #
    # Merged into `unchecked`, which until now held the PRODUCERS' own account
    # only. The model's declaration and the dispatcher's refusals are the same
    # kind of fact and belong in one list; deduped on (location, reason) as the
    # legacy path does.
    #
    # FROM RAW MESSAGES, NOT THE LEDGER, and deliberately: `check_table` is a
    # bulk tool whose ledger result is truncated at 4,000 chars, so the
    # refusals would be cut off on exactly the tables big enough to matter.
    # (The census reads the ledger for the opposite reason -- there the
    # archive's messages are the truncated copy. The two are not inconsistent:
    # each reads whichever source keeps the payload it needs.)
    try:
        machine: list = []
        for label in ("tool_agent", "science_agent"):
            machine += _agent._machine_refusals(
                (result.get(label) or {}).get("messages") or [])
        if machine:
            existing = list(doc.get("unchecked") or [])
            seen = {(e.get("location"), e.get("reason")) for e in existing
                    if isinstance(e, dict)}
            existing.extend(m for m in machine
                            if (m.get("location"), m.get("reason")) not in seen)
            doc["unchecked"] = existing
    except Exception as exc:  # noqa: BLE001 -- recorded, never swallowed
        meta = result.get("run_meta")
        if isinstance(meta, dict):
            meta["machine_refusals_error"] = (
                f"the dispatcher's refusal list could not be harvested "
                f"({type(exc).__name__}: {exc}), so `unchecked` carries the "
                f"producers' account only")

    # BOTH OF THESE WRITE ONTO THE FINDINGS, SO BOTH RUN BEFORE THE DOCUMENT
    # IS SERIALISED. The severity reconciler used to sit BELOW this write, and
    # its `severity_source` blocks therefore never reached disk -- only the
    # `run_meta` summary did, which is why every test still passed. That is the
    # fourth serialise-then-mutate defect in this writer (scrub, census,
    # machine refusals, this), and the reason the annotators are now one block
    # immediately above the write rather than scattered around it.
    _flat_ledger = [r for rows in ledgers.values() for r in (rows or [])]

    # WHICH PASSAGE WAS THIS FINDING READ FROM? Ported 2026-09-04. `source` is
    # declared in findings.v2.schema.json AND listed in
    # `prompts._NOT_PRODUCER_WRITTEN` -- the contract already said the pipeline
    # writes it -- and nothing on this path did: 0 of 80 findings across the
    # four archived parallel runs carried it, against every legacy run that
    # did.
    try:
        from . import sourcing as _sourcing
        summary = _sourcing.annotate_v2(doc, _flat_ledger)
        meta = result.get("run_meta")
        if isinstance(meta, dict):
            meta["sourcing"] = summary
    except Exception as exc:  # noqa: BLE001 -- recorded, never swallowed
        meta = result.get("run_meta")
        if isinstance(meta, dict):
            meta["sourcing"] = {"error": (
                f"the finding-to-passage join could not run "
                f"({type(exc).__name__}: {exc}), so no finding on this run "
                f"carries the passage its numbers were read from")}

    # DID THE ADJUDICATOR KEEP THE TOOL'S VERDICT? Ported 2026-09-03; it ran
    # only in the legacy writer, so `run_meta.severity_reconciliation` -- whose
    # `divergences` list is pinned in VIEWER_MUST_RENDER and rendered by the
    # viewer's "Did the write-up keep the tool's verdict?" section -- was
    # satisfied by archived legacy runs alone and the section silently
    # vanished on every current run.
    try:
        from . import severity_reconcile as _sevrec
        meta = result.get("run_meta")
        if isinstance(meta, dict):
            meta["severity_reconciliation"] = _sevrec.annotate_v2(
                doc, _flat_ledger)
    except Exception as exc:  # noqa: BLE001 -- recorded, never swallowed
        meta = result.get("run_meta")
        if isinstance(meta, dict):
            meta["severity_reconciliation"] = {"error": (
                f"the tool-vs-published severity comparison could not run "
                f"({type(exc).__name__}: {exc}), so whether the adjudicator "
                f"kept each tool's verdict is NOT MEASURED for this run")}

    from .history_runtime import prepare_report_revision
    prepare_report_revision(result)
    _w("findings.v2.json", {"disclaimer": DISCLAIMER_SHORT, **doc})
    if result.get("adjudication_raw") is not None:
        _w("adjudication.json", result["adjudication_raw"])
    from .report_v2 import render_report_v2
    report_md = render_report_v2(doc, result.get("run_meta"),
                                 result.get("limitations"))
    # SCRUBBED AT WRITE TIME, as the legacy writer has always done
    # (agent.py's `write_review_outputs`). `bundle.py` scrubs its own copy on
    # the way out, so the emailed artifact was never at risk; this is the
    # forwarded `forensic_review/report.md`, which was not. Measured
    # 2026-09-03: 0 leaks across the four archived parallel runs, so this
    # closes a guarantee rather than a wound.
    _w("report.md", _scrub.scrub(report_md))
    if render_pdf and report_md.strip():
        from .agent import _render_report_pdf
        pdf_path = _render_report_pdf(result, report_md, out)
        if pdf_path is not None:
            written["report.pdf"] = pdf_path

    _write_delivery_and_source_coverage(result, ledgers, _w)
    # BEFORE run_meta.json is serialised. On the legacy path this block ran
    # after the write, so `run_meta.sandbox` reached the in-memory dict and
    # never the file: 0 of 21 archived run_meta.json carry it, 17 of them
    # beside a sandbox_audit.json whose verdict begins BREACH.
    try:
        _write_sandbox_audit(result, ledgers, doc, _w)
    except Exception as exc:  # noqa: BLE001 -- recorded, never swallowed
        _w("sandbox_audit.error.txt",
           f"the sandbox audit could not be computed: "
           f"{type(exc).__name__}: {exc}\n")
    _w("run_meta.json", result["run_meta"])
    for label in ("tool_agent", "science_agent", "adjudicator"):
        stage = result.get(label)
        if not stage:
            continue
        if stage.get("prompt"):
            _w(f"prompt.{label}.md", stage["prompt"])
        # The SYSTEM prompt, beside the user turn. Written per role rather
        # than deduplicated: the three differ (role-filtered CLI map, the
        # figure section, the grok MCP route), and a shared file keyed by hash
        # would need a resolver at read time for no saving worth having.
        sys_prompt = (result.get("system_prompts") or {}).get(label)
        if sys_prompt:
            _w(f"system_prompt.{label}.md", sys_prompt)
        _w(f"toolcalls.{label}.json", ledgers[label])
        _w(f"messages.{label}.json",
           _agent._slim_messages(stage.get("messages") or []))
    for label, extra_stage in (result.get("unfiled_stages") or {}).items():
        _w(f"messages.{label}_unfiled.json",
           _agent._slim_messages(extra_stage.get("messages") or []))
    # The science agent's persisted scripts move into the run archive.
    paper_dir = Path(result["paper_path"]) if \
        Path(result["paper_path"]).is_dir() else Path(result["paper_path"]).parent
    # ONLY THIS RUN'S SCRIPTS. `run_python_script` writes under
    # `analysis_code/<run_slug>/` whenever the pipeline named the run, so a
    # concurrent analysis of the same paper keeps its own subdirectory and this
    # move cannot carry it off. The slug is FLATTENED on the way in: an
    # archived run reads `analysis_code/007_x.py` exactly as it always did,
    # which is also what `run_python_script` reports as `script_path`.
    # `run_slug` absent (a legacy or hand-driven run) means the flat directory,
    # unchanged.
    scripts_root = paper_dir / "analysis_code"
    # Through `run_script._slug`, the SAME function that named the directory --
    # not the raw string. Two spellings of one name is how a writer and a
    # reader drift apart silently, and here the drift would archive nothing
    # while leaving the scripts in the paper directory.
    from .run_script import _slug as _script_slug
    _raw_slug = result.get("run_slug")
    run_slug = _script_slug(_raw_slug) if _raw_slug else None
    scripts = (scripts_root / run_slug) if run_slug else scripts_root
    if scripts.is_dir() and any(scripts.iterdir()):
        dest = out / "analysis_code"
        if not dest.exists():
            shutil.move(str(scripts), str(dest))
            written["analysis_code"] = dest
            # Leave no empty `analysis_code/` behind when ours was the only
            # run; a directory that exists but holds nothing reads, to the next
            # run and to a human, as "scripts ran and produced nothing".
            if run_slug:
                try:
                    scripts_root.rmdir()
                except OSError:
                    pass   # another run's subdirectory is still in there
    # THE VALUE REGISTER runs on parallel output too (stacked-headers merge
    # follow-through): Greg's `build_value_register` reads anatomy plus the
    # stage messages, and the parallel analysts' stage dicts carry the same
    # message shape the legacy stages did -- so a two-key shim is the whole
    # adapter. The adjudicator's few spot re-checks are not joined (the shim
    # has two slots); that loss is noted here rather than silently absorbed.
    try:
        shim = {
            "findings": {"anatomy": doc.get("anatomy") or {}},
            "stage1": result.get("tool_agent") or {},
            "stage2": result.get("science_agent") or {},
        }
        written.update(_agent.build_value_register(
            shim, str(result.get("paper_path") or paper_dir), out))
    except Exception:  # noqa: BLE001 -- the register must never fail a run
        pass
    try:
        from . import webapp_index
        webapp_index.refresh_index_paper(paper_dir)
    except Exception:  # noqa: BLE001 -- the index must never fail a paid run
        pass
    # Database auto-push: fires whenever a local database URL resolves
    # ($METASCIENCE_DB_URL or the repo .env -- wired live 2026-08-21);
    # best-effort by contract (an unreachable database lands in the pending
    # journal, never fails the paid run).
    from .db_push import auto_push
    from .history_runtime import seal_report_outputs
    seal_report_outputs(result, out)
    if publish:
        auto_push(paper_dir, out)
    return written
