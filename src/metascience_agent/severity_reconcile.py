"""Compare the severity a TOOL computed against the severity the MODEL wrote.

WHY THIS EXISTS
---------------
Every forensic tool returns a `severity`. The model then writes its own
`severity` into the finding, and until now nothing compared the two. The only
validation anywhere (`evaluation/deterministic.py`) checks that the string is a
member of the enum -- so a tool returning `impossible` and a model recording
`consistent` for the same check passed silently, and the tool's answer existed
nowhere in the output.

WHAT THIS DOES NOT DO
---------------------
**It does not overrule the model.** Divergence is often correct and is the
whole point of stage 2: GRIM applied to a continuous variable returns
`impossible` on a perfectly ordinary number, and downgrading that is the
reviewer doing its job. Overwriting the model with the tool would reintroduce
exactly the false positives the guards were built to prevent.

What it does is make the divergence VISIBLE and demand a reason. An unexplained
downgrade -- the tool said `impossible`, the finding says `consistent`, and no
note says why -- is the single hardest error for a later reader to catch,
because the evidence that anything was overruled has been discarded.

A downgrade is treated as more serious than an upgrade. Upgrading past a tool
overstates a case a reader can check against the printed numbers; downgrading
past one makes a real problem disappear, and nothing downstream reveals it.
"""

from __future__ import annotations

import json
from typing import Any

from .report_render import SEVERITY_RANK
from .tools.severity import normalize_severity

#: `technique` in the findings schema names a FAMILY; the ledger records the
#: exact registered tool. The first version of this table mapped each technique
#: to a single tool name, and on the first real run it matched nothing at all --
#: not one of 24 findings joined. Three separate reasons, all of which this
#: table now has to survive:
#:
#: 1. The model labels the family, not the member. It called `grim_percentage`
#:    and wrote `technique: "grim"`; it called `check_sd_range` and wrote
#:    `check_sd_or_se`. Both labels are legal schema values, so nothing was
#:    wrong -- a one-to-one table was simply the wrong shape.
#: 2. Batch tools. The finding names `check_regression`; the ledger records one
#:    `check_regression_batch` call carrying 84 rows. See
#:    `severities_from_ledger`, which expands those.
#: 3. Tools that run INSIDE another tool. `check_sd_or_se` is dispatched by
#:    `check_table` and never appears as a ledger entry under its own name.
#:    Its verdict survives only in the enclosing call's `results[]`.
#:
#: Values are candidate tool names, tried in order. `_batch` variants are added
#: automatically, so they are not listed here.
_TECHNIQUE_TOOLS: dict[str, tuple[str, ...]] = {
    "grim": ("grim_check", "grim_percentage", "grim_sweep"),
    "grimmer": ("grimmer_check",),
    "grimu": ("grimu_check",),
    "debit": ("debit_check",),
    "sprite": ("sprite_reconstruct",),
    "csf": ("csf_test",),
    "stalt": ("stalt_check",),
    "duplication": ("detect_duplication",),
    # `reconcile` is whatever produced a table the finding is arguing about.
    # `check_estimate_ci` belongs here for a measured reason: 32 of the 68
    # `reconcile` findings in the corpus reproduce with `check-ci`, i.e. about
    # half of this family is not a table-parse argument at all but an estimate
    # disagreeing with its own confidence interval. Without it those 32 join to
    # nothing and their tool verdict is discarded.
    "reconcile": ("parse_table", "parse_cells_typed", "check_table",
                  "check_estimate_ci"),
    # Dispatched by `check_table`; recovered from its per-cell results.
    "check_sd_or_se": ("check_sd_or_se", "check_sd_range", "check_table"),
    # Four registered forensic tools with no entry in the findings schema's
    # `technique` enum, so nothing routed a finding back to them: 12 of 15
    # stage-1 runs therefore showed these findings under `hand-computed` in the
    # bundle's check table AND showed the tool itself flowing to `no finding` in
    # the Sankey -- the same work counted twice, once as unattributed and once as
    # unproductive. Listing them pins the route explicitly rather than leaving it
    # to `_candidate_tools`' identity fallback, which silently produces the right
    # answer today only because the technique string happens to equal the tool
    # name. The schema enum itself is `prompts/schema/findings.schema.json` and
    # is not owned here -- see the report.
    "absence_of_evidence": ("absence_of_evidence",),
    "check_effect_plausibility": ("check_effect_plausibility",),
    "check_estimate_ci": ("check_estimate_ci",),
    "verify_power_analysis": ("verify_power_analysis",),
}


def _candidate_tools(technique: Any) -> tuple[str, ...]:
    """Registered tool names that could have produced this finding.

    Unknown techniques fall through to themselves, which is right: most of the
    schema's technique values ARE registered tool names, and a bare identity
    map covers them without an entry here.
    """
    if not isinstance(technique, str) or technique == "manual":
        return ()
    names = _TECHNIQUE_TOOLS.get(technique, (technique,))
    out: list[str] = []
    for n in names:
        out.append(n)
        out.append(f"{n}_batch")
    return tuple(out)


def _comparable(pairs: set[tuple[str, Any]]) -> set[tuple[str, Any]]:
    """Only the pairs that can honestly be equality-joined.

    A finding's `inputs` is written for a HUMAN. Measured on a real run it
    contains things like `decimals_b: "2 (3 for -0.004 and 0.001)"`,
    `n: "not supplied - the level-1 observation count is never reported"`, and
    a `rows` value that is an eight-clause English summary of a table. None of
    those will ever equal the argument the tool received, and requiring them to
    is why a subset join matched almost nothing.

    Numbers and booleans are the part that does survive the round trip, so they
    are the part we join on. Strings are dropped rather than fuzzy-matched:
    a near-match on prose is a guess, and a guess here silently attributes one
    check's verdict to another check.
    """
    return {(k, v) for k, v in pairs
            if isinstance(v, (int, float, bool)) and not isinstance(v, str)}


def _scalars(args: Any) -> set[tuple[str, Any]]:
    """Comparable (name, value) pairs from a tool-argument dict.

    Scalars only: a list or dict argument is reproduced by the model with
    varying formatting and would defeat an equality join without adding
    discriminating power that the scalars do not already carry.
    """
    if not isinstance(args, dict):
        return set()
    out = set()
    for k, v in args.items():
        if v is None or isinstance(v, (dict, list)):
            continue
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        out.add((k, v))
    return out


def _expand_rows(tool: str, parsed: dict, call_input: Any) -> list[tuple[str, set, str]]:
    """Per-row entries from a tool that checked many things in one call.

    Three tools in this codebase return a `results` list where each element
    carries its own severity: the two `_batch` wrappers and `check_table`. The
    call-level severity is the WORST row, which is the wrong thing to compare a
    single-row finding against -- one `impossible` cell would make every other
    cell in the table look impossible too.

    Two shapes, distinguished by whether the row names its own tool:

    * `check_table` rows carry `tool` and `inputs`, because it DISPATCHES a
      different check per cell. The row is recorded under the tool that
      actually ran, which is the only place that verdict exists -- those checks
      never appear in the ledger under their own names.
    * `_batch` rows carry the check's own return fields and a `row` index. They
      are recorded under the base tool name, and the matching input row is
      folded in: a batch row echoes `b` and `se` but not `reported_t` or `df`,
      while the finding's `inputs` names all four, so the row's own fields are
      not enough to join on.
    """
    rows = parsed.get("results")
    if not isinstance(rows, list):
        return []
    base = tool[: -len("_batch")] if tool.endswith("_batch") else tool
    input_rows = call_input.get("rows") if isinstance(call_input, dict) else None
    if not isinstance(input_rows, list):
        input_rows = []

    out: list[tuple[str, set, str]] = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        raw = row.get("severity")
        if not isinstance(raw, str) or not raw.strip():
            continue
        scalars = _scalars(row) | _scalars(row.get("inputs"))
        # `row` is the batch's own index and `check_id` its bookkeeping; neither
        # is something a finding would restate, and leaving them in makes every
        # subset test fail on a key the model never had.
        scalars -= {(k, v) for k, v in scalars if k in ("row", "check_id", "seq")}
        idx = row.get("row") if isinstance(row.get("row"), int) else i
        if 0 <= idx < len(input_rows):
            scalars |= _scalars(input_rows[idx])
        name = row.get("tool") if isinstance(row.get("tool"), str) else base
        out.append((name, scalars, normalize_severity(raw)))
    return out


def severities_from_ledger(ledger: list[dict] | None) -> list[tuple[str, set, str]]:
    """(tool name, argument scalars, severity) for every validated call.

    Only validated calls: an unvalidated call is the model running its own
    code, and its verdict is not a tool's verdict.

    Calls carrying per-row results contribute their rows INSTEAD of themselves
    (see `_expand_rows`). Not in addition: the call-level severity is the worst
    row, so keeping both would let a finding join to a verdict belonging to a
    different row of the same table.
    """
    out: list[tuple[str, set, str]] = []
    for call in ledger or []:
        if not isinstance(call, dict) or not call.get("validated"):
            continue
        text = call.get("result")
        if not isinstance(text, str) or not text.strip():
            continue
        try:
            parsed = json.loads(text)
        except (ValueError, TypeError):
            continue
        if not isinstance(parsed, dict):
            continue
        tool = str(call.get("tool_short") or "")
        expanded = _expand_rows(tool, parsed, call.get("input"))
        if expanded:
            out.extend(expanded)
            continue
        raw = parsed.get("severity")
        if not isinstance(raw, str) or not raw.strip():
            # Not every tool issues a verdict. `multiplicity_report` returns
            # arithmetic -- thresholds and counts -- and deliberately does not
            # decide whether losing two claims is suspicious; that judgement is
            # stage 2's job and inventing a threshold here would prejudge it.
            # `statcheck` reports extraction success separately from its stats.
            continue
        out.append((tool, _scalars(call.get("input")), normalize_severity(raw)))
    return out


def _tool_severity(finding: dict,
                   from_ledger: list[tuple[str, set, str]] | None = None) -> str | None:
    """The severity the TOOL returned for this finding, if it can be established.

    Two routes, in order of directness:

    1. **`computed.severity`** -- the model transcribed the tool's own verdict.
       Exact when present, but measured over the committed corpus it is present
       in only 3 of 164 findings: the model copies the numbers it wants to talk
       about, not the whole tool result. On its own this check was nearly inert.
    2. **The tool-call ledger** -- match the finding's `technique` and `inputs`
       against the validated call that produced them. This is where the verdict
       actually survives; the ledger for one real run carried 40 tool
       severities against the findings' 3.

    Never read from the finding's own top-level `severity`: that is the MODEL's
    verdict, and comparing a field with itself would report perfect agreement
    forever.
    """
    computed = finding.get("computed")
    if isinstance(computed, dict):
        raw = computed.get("severity")
        if isinstance(raw, str) and raw.strip():
            return normalize_severity(raw)

    tools = _candidate_tools(finding.get("technique"))
    if not tools or not from_ledger:
        return None
    wanted = _scalars(finding.get("inputs"))
    # An empty `wanted` used to return None here, on the reasoning that a
    # finding naming no scalars cannot identify its call. But it can, when the
    # tool was called once or when every call of it agreed -- and the unanimity
    # requirement below already enforces exactly that. On the first real run
    # this bail discarded the ONLY finding that would otherwise have joined,
    # which is how a join broken in three other ways still managed to look like
    # "no divergence to report" rather than "nothing matched".
    #
    # A call whose arguments CONTAIN everything the finding says it passed.
    # Subset rather than equality: the model omits defaulted arguments from
    # `inputs` far more often than it invents them, so equality misses the
    # match while a subset join does not admit an unrelated call unless every
    # scalar the finding names also appears in it.
    wanted = _comparable(wanted)
    candidates = [(args, sev) for name, args, sev in from_ledger if name in tools]
    if not candidates:
        return None
    if wanted:
        hits = {sev for args, sev in candidates if wanted <= _comparable(args)}
    else:
        # Nothing comparable to join on -- but the tool still ran, and if every
        # call of it returned the same verdict then that verdict is this
        # finding's whichever call produced it. This is the only route left for
        # a finding whose `inputs` are entirely prose, which is most of them.
        hits = {sev for _, sev in candidates}
    # Unanimity, not arbitrary choice: several calls may match, and if they all
    # returned the same verdict then that verdict is this finding's regardless
    # of which one it was. If they disagree, we cannot say which row the model
    # meant, and guessing would manufacture a divergence that may not exist --
    # or worse, clear a finding using a different row's verdict.
    return hits.pop() if len(hits) == 1 else None


def _has_reason(finding: dict) -> bool:
    """Did the model say anything that could serve as a reason?

    Deliberately permissive: any non-trivial `notes` counts. The check is for
    SILENCE, not for the quality of the argument -- judging whether a stated
    reason is a good one is a reader's job, and a stricter rule here would
    just teach the model to pad.
    """
    for key in ("notes", "assumptions"):
        value = finding.get(key)
        if isinstance(value, str) and len(value.strip()) >= 15:
            return True
    return False


def reconcile_finding(finding: dict,
                      from_ledger: list[tuple[str, set, str]] | None = None) -> dict | None:
    """Build the `severity_source` block for one finding, or None if it agrees.

    None means either "the tool and the model agree" or "no tool severity to
    compare against" -- both of which are unremarkable and should not add
    noise to the output.
    """
    tool = _tool_severity(finding, from_ledger)
    if tool is None:
        return None
    model = normalize_severity(finding.get("severity"))
    if model == tool:
        return None

    tool_rank = SEVERITY_RANK.get(tool, 99)
    model_rank = SEVERITY_RANK.get(model, 99)
    # Lower rank is MORE severe, so a larger model_rank means the model
    # softened the tool's verdict.
    direction = "downgraded" if model_rank > tool_rank else "upgraded"
    explained = _has_reason(finding)
    return {
        "model": model,
        "tool": tool,
        "direction": direction,
        "explained": explained,
        "note": (
            f"The tool returned `{tool}`; this finding records `{model}`. "
            + ("A reason is stated in the finding."
               if explained else
               "NO REASON IS STATED. "
               + ("A downgrade with no stated reason makes a tool result "
                  "disappear from the output, which is the hardest kind of "
                  "error for a later reader to catch."
                  if direction == "downgraded" else
                  "An upgrade past the tool asserts more than the tool "
                  "established."))
        ),
    }


def annotate(result: dict, ledger: list[dict] | None = None) -> dict:
    """Attach `severity_source` wherever tool and model disagree, in place.

    Returns a summary for `run_meta`. Only sweep findings are reconciled;
    stage-2 findings restate `computed` as prose and have no machine-readable
    tool verdict to compare against.
    """
    from_ledger = severities_from_ledger(ledger)
    summary: dict[str, Any] = {
        "n_compared": 0, "n_diverged": 0,
        "n_downgraded_unexplained": 0, "n_upgraded_unexplained": 0,
        "n_tool_severities_available": len(from_ledger),
        # Findings that named a real tool but could not be matched to its call.
        # This exists because the first version of this module compared NOTHING
        # on a run with 22 validated calls, and reported that as an absence of
        # divergence rather than as a broken join. A reader could not tell the
        # two apart, and neither could I. `n_manual` is the honest zero -- a
        # finding the model computed by hand has no tool verdict by definition.
        "n_unjoined": 0, "n_manual": 0,
        "divergences": [],
    }

    sweep = result.get("findings")
    items = sweep.get("findings") if isinstance(sweep, dict) else None
    for f in items or []:
        if not isinstance(f, dict):
            continue
        if _tool_severity(f, from_ledger) is None:
            if _candidate_tools(f.get("technique")):
                summary["n_unjoined"] += 1
            else:
                summary["n_manual"] += 1
            continue
        summary["n_compared"] += 1
        block = reconcile_finding(f, from_ledger)
        if block is None:
            f.pop("severity_source", None)
            continue
        f["severity_source"] = block
        summary["n_diverged"] += 1
        if not block["explained"]:
            summary[f"n_{block['direction']}_unexplained"] += 1
        summary["divergences"].append(
            f"{f.get('id', '?')}: tool={block['tool']} model={block['model']} "
            f"({block['direction']}, {'explained' if block['explained'] else 'UNEXPLAINED'})"
        )

    # Record unconditionally. Writing the summary only when something matched
    # is what hid the broken join: `severity_reconciliation` was simply absent
    # from `run_meta`, which reads as "this run had no disagreements" and is
    # indistinguishable from "this module did nothing".
    meta = result.setdefault("run_meta", {})
    if isinstance(meta, dict):
        meta["severity_reconciliation"] = summary
    return summary


#: The two evidence grades that no validated tool stands behind. A finding here
#: may be entirely right -- the archive's best catches are in this band -- but
#: nothing in the pipeline reproduced it, so it may not reach the two rungs that
#: read as established fact.
#: The v1 five-value enum a TOOL returns, onto the 1-9 ladder a v2 finding
#: carries. `severity9.FIVE_TO_NINE` covers only the three ACCUSATORY values
#: (suspicious 3, highly_suspicious 4, impossible 5); `indeterminate` and
#: `consistent` map to non-problem outcomes with a NULL severity and have no
#: rung at all. They are therefore NOT COMPARABLE to an integer, and the
#: reconciler says so rather than treating them as 0 -- diffing a missing rung
#: against a real one would manufacture a divergence out of a category error,
#: and the interesting case there ("the tool said fine and a finding was filed
#: anyway") is a different question that `_unbacked_findings` already owns.
_NOT_ON_THE_LADDER = frozenset({"indeterminate", "consistent"})


def _has_real_tool(technique: Any) -> bool:
    """Could a REGISTERED tool have produced this technique's verdict?

    `_candidate_tools` answers "what would the tool be called", which for an
    unknown technique is just the technique's own name. This asks whether such
    a tool exists, so a finding whose technique is a judgement rather than a
    computation is counted as manual and not as a failed join.
    """
    from . import registry as _registry

    names = _candidate_tools(technique)
    if not names:
        return False
    known = getattr(_registry, "BY_NAME", None) or {}
    return any(n in known for n in names)


def _adjudication_reason(finding: dict) -> bool:
    """Did the ADJUDICATOR record why it set the severity it set?

    THE V2 QUESTION IS NOT THE V1 QUESTION, and porting the v1 one unchanged
    would have produced a guard nobody reads.

    In v1 the editorial stage had no mandate to re-grade, so any departure
    from the tool's verdict was suspicious on its face. In v2 an adjudicator
    exists whose ENTIRE JOB is assigning the final 1-9 severity: a departure
    is the design working. Flagging every departure would fire on nearly every
    finding, and a guard that fires on everything is one nobody reads.

    So the v2 check is narrower and sharper: a departure from the tool's
    verdict that the adjudication does not explain. Permissive about what
    counts as an explanation, for the same reason `_has_reason` is -- the
    check is for SILENCE, not for the quality of the argument.
    """
    adj = finding.get("adjudication")
    if isinstance(adj, dict):
        for key in ("rationale", "note", "reason"):
            value = adj.get(key)
            if isinstance(value, str) and len(value.strip()) >= 15:
                return True
    return _has_reason(finding)


def _v2_tool_severity(finding: dict,
                      from_ledger: list[tuple[str, set, str]] | None = None
                      ) -> tuple[str | None, str | None]:
    """The tool's verdict for a v2 finding, and WHICH route established it.

    PREFER THE ANNOTATOR'S `tool_verdict`, which `parallel.py` already wrote
    (via `findings_v2.tool_verdict_for`) long before this runs. The first cut
    of this port re-derived the join with `_tool_severity` instead, and that
    was a measured mistake: `_tool_severity` matches on the finding's `inputs`
    scalars, and **v2 findings do not carry `inputs`**, so it fell through to
    its weakest path and compared 1 of 39 findings on apple_cider where the
    block already sitting on those same findings had 8. Re-deriving an answer
    the document already carries is how two joins drift apart; consuming it
    means the reconciler and the per-tool fire statistics can never disagree
    about which call backs a finding.

    `tool_verdict_for` is also the SOUNDER join for this question. It refuses
    on disagreement (unanimity over the matched calls) and it never reads
    `computed.severity` -- the model's own transcription of a tool result.
    Comparing the adjudicator against a number the model typed would be
    comparing the model with itself, which is the trap `_tool_severity`'s
    docstring names and then walks into via its route 1.

    The `_tool_severity` fallback is kept so this is a SUPERSET of the old
    behaviour: a finding the annotator could not join, but whose `inputs` do
    identify a call, is still compared.
    """
    verdict = finding.get("tool_verdict")
    if isinstance(verdict, dict):
        raw = verdict.get("severity")
        if isinstance(raw, str) and raw.strip():
            return normalize_severity(raw), "tool_verdict"
    fallback = _tool_severity(finding, from_ledger)
    return fallback, ("ledger" if fallback is not None else None)


def reconcile_finding_v2(finding: dict,
                         from_ledger: list[tuple[str, set, str]] | None = None
                         ) -> dict | None:
    """The `severity_source` block for one v2 finding, or None if unremarkable.

    None means the tool and the adjudicator agree, there is no tool verdict to
    compare against, or the tool's verdict is not on the ladder.
    """
    from . import severity9

    tool, joined_by = _v2_tool_severity(finding, from_ledger)
    if tool is None or tool in _NOT_ON_THE_LADDER:
        return None
    tool_rung = severity9.FIVE_TO_NINE.get(tool)
    if tool_rung is None:
        return None
    final = finding.get("severity")
    if not isinstance(final, int):
        # A discarded or provisional-only finding has no final rung. Not a
        # divergence: nothing was published to diverge.
        return None
    if final == tool_rung:
        return None

    direction = "upgraded" if final > tool_rung else "downgraded"
    explained = _adjudication_reason(finding)
    return {
        "model": final,
        "tool": tool,
        "tool_rung": tool_rung,
        "direction": direction,
        "explained": explained,
        "joined_by": joined_by,
        "note": (
            f"The tool returned `{tool}` (rung {tool_rung}); this finding was "
            f"published at rung {final}. "
            + ("The adjudication states a reason."
               if explained else
               "THE ADJUDICATION STATES NO REASON. "
               + ("A downgrade with no stated reason makes a tool result "
                  "disappear from the output, which is the hardest kind of "
                  "error for a later reader to catch."
                  if direction == "downgraded" else
                  "An upgrade past the tool asserts more than the tool "
                  "established."))
        ),
    }


def annotate_v2(doc: dict, ledger: list[dict] | None = None) -> dict:
    """Reconcile a findings-v2 document against its tool ledger, in place.

    Returns the `run_meta.severity_reconciliation` summary. The v2 sibling of
    `annotate`, following `consequence.annotate_v2`'s shape.

    Ported 2026-09-03. Until then this ran only in the legacy writer, so
    `run_meta.severity_reconciliation.divergences` -- pinned in
    `VIEWER_MUST_RENDER` and rendered by the viewer's "Did the write-up keep
    the tool's verdict?" section -- was satisfied by archived legacy runs
    alone, and the section silently vanished on every current run.
    """
    from_ledger = severities_from_ledger(ledger)
    summary: dict[str, Any] = {
        "n_compared": 0, "n_diverged": 0,
        "n_downgraded_unexplained": 0, "n_upgraded_unexplained": 0,
        "n_tool_severities_available": len(from_ledger),
        # Every finding lands in exactly one bucket, and each is a different
        # fact. Recording them separately is the whole lesson of this module's
        # first version, which compared NOTHING on a run with 22 validated
        # calls and reported that as an absence of divergence.
        "n_unjoined": 0, "n_manual": 0, "n_not_on_ladder": 0,
        "n_no_final_severity": 0,
        # WHICH join established each comparison. Split because the two are
        # different degrees of confidence, and because a run where
        # `n_joined_by_ledger` dominates means the annotator's `tool_verdict`
        # has stopped being written -- visible here rather than as a quiet
        # drop in `n_compared`.
        "n_joined_by_tool_verdict": 0, "n_joined_by_ledger": 0,
        "divergences": [],
    }
    for f in (doc.get("findings") or []):
        if not isinstance(f, dict):
            continue
        tool, joined_by = _v2_tool_severity(f, from_ledger)
        if tool is None:
            # MANUAL vs UNJOINED IS A REAL DISTINCTION AND V2 BROKE IT.
            # `_candidate_tools` falls back to `(technique, technique_batch)`
            # for an unknown technique, which was fair in v1 where every
            # technique named a tool. v2 techniques include `not_computational`,
            # `internal_contradiction` and `factual_claim` -- findings with no
            # tool verdict BY DEFINITION -- so the fallback filed them as a
            # broken join. That overstates our own failure, which is the
            # mirror of understating it and just as misleading.
            if _has_real_tool(f.get("technique")):
                summary["n_unjoined"] += 1
            else:
                summary["n_manual"] += 1
            continue
        if tool in _NOT_ON_THE_LADDER:
            summary["n_not_on_ladder"] += 1
            continue
        if not isinstance(f.get("severity"), int):
            summary["n_no_final_severity"] += 1
            continue
        summary["n_compared"] += 1
        if joined_by:
            summary[f"n_joined_by_{joined_by}"] += 1
        block = reconcile_finding_v2(f, from_ledger)
        if block is None:
            f.pop("severity_source", None)
            continue
        f["severity_source"] = block
        summary["n_diverged"] += 1
        if not block["explained"]:
            summary[f"n_{block['direction']}_unexplained"] += 1
        # EVERY divergence is listed, each marked, as the v1 version does. A
        # list carrying only the unexplained ones beside an `n_diverged` that
        # counts all of them makes a reader do subtraction to find out what
        # they are not being shown.
        summary["divergences"].append(
            f"{f.get('finding_id', '?')}: tool={block['tool']} "
            f"(rung {block['tool_rung']}) published={block['model']} "
            f"({block['direction']}, "
            f"{'explained' if block['explained'] else 'UNEXPLAINED'})")
    return summary


UNCOMPUTED_GRADES = frozenset({"reading", "hand_computed"})

#: The ceiling those grades may reach. `suspicious` is the highest rung that
#: still reads as a question rather than a determination, which is exactly what
#: an unreproduced claim is.
UNCOMPUTED_CEILING = "suspicious"

_ABOVE_CEILING = ("impossible", "highly_suspicious")


def clamp_uncomputed(result: dict, ledger: list[dict] | None = None) -> dict:
    """Cap report findings that no validated tool computed, and say so.

    THE RULE ALREADY EXISTED AND WAS NEVER ENFORCED. `prompts/stage2_editorial.md`
    line 157 tells the model that a finding it worked out by hand may not reach
    `impossible`. That is prompt-law, and prompt-law leaks: MEASURED across 23
    archived runs, 88 of 222 report findings (40%) rest on no validated
    computation, and while 86 of those are already at or below the ceiling, TWO
    are not -- one `manual` finding at `impossible`, and one manual-backed
    `highly_suspicious` carried into a headline. A rule enforced 99% of the time
    is a rule that fails in exactly the cases that matter, because the leak is at
    the top of the ladder.

    THE CLAMP IS VISIBLE, NEVER SILENT. It writes the same `severity_source`
    block the tool/model reconciler uses, so a reader sees the original verdict,
    the ceiling, and why -- a severity quietly lowered is its own kind of
    dishonesty, and it would also hide a model that is systematically over-calling.

    WHY THIS DOES NOT SUPPRESS THE CAPABILITY. Greg's instruction is that this
    function of the pipeline be "characterized and optimized rather than
    excluded", and the real risk is teaching the editorial stage to stop writing
    readings at all -- trading hedged critique for silent omission, which is the
    false all-clear. Two reasons it does not bite: 86 of 88 findings are already
    compliant, so there is almost nothing to learn from; and the escape is open
    rather than closed -- route the claim through a validated tool and it becomes
    `computed`, at which point every rung is available to it. The clamp restricts
    what an UNREPRODUCED claim may assert, not what may be claimed.
    """
    from .viewer_facts import evidence_grade

    summary: dict[str, Any] = {"n_findings": 0, "n_uncomputed": 0,
                               "n_clamped": 0, "clamps": []}
    # THE KEY PRODUCTION ACTUALLY USES IS `report_obj`. Read as `report` alone,
    # this returned at the first line on EVERY REAL RUN -- the Romano run of
    # 2026-08-11 has no `uncomputed_severity_clamp` and no `supplied_norm_clamp`
    # in its `run_meta.json` at all, while `severity_reconciliation` (which
    # reads `result["findings"]`) is right there beside them. So the clamp that
    # commit e1fa555 shipped as "the enforced severity cap" enforced nothing,
    # and its tests passed throughout because they hand-build `{"report": ...}`.
    # Tested against a shape production never produces is the same defect as
    # never being called; `lint-inert` should learn this one.
    #
    # `report` is kept as a fallback so those hand-built fixtures, and the
    # archive replay in tests/test_corpus_invariants.py, keep working.
    report = result.get("report_obj")
    if not isinstance(report, dict):
        report = result.get("report")
    findings = report.get("findings") if isinstance(report, dict) else None
    if not isinstance(findings, list):
        return summary

    sweep = result.get("findings")
    sweep_items = sweep.get("findings") if isinstance(sweep, dict) else []
    by_id = {str(f.get("id")): f for f in (sweep_items or [])
             if isinstance(f, dict) and f.get("id")}

    for f in findings:
        if not isinstance(f, dict):
            continue
        summary["n_findings"] += 1
        grade = evidence_grade(f, by_id).get("grade")
        if grade not in UNCOMPUTED_GRADES:
            continue
        summary["n_uncomputed"] += 1
        original = str(f.get("severity") or "")
        if original not in _ABOVE_CEILING:
            continue
        f["severity"] = UNCOMPUTED_CEILING
        f["severity_source"] = {
            "tool": None,
            "model": original,
            "final": UNCOMPUTED_CEILING,
            "direction": "clamped",
            "explained": True,
            "reason": (
                f"Capped at `{UNCOMPUTED_CEILING}`. The model recorded "
                f"`{original}`, but no validated check computed this finding "
                f"(evidence grade: {grade}). The two rungs above the cap read as "
                "established fact, and nothing in this pipeline established it. "
                "The claim may still be correct -- route it through a validated "
                "tool and the cap lifts."
            ),
        }
        summary["n_clamped"] += 1
        # Report findings carry no `id` -- measured across the archive, every
        # clamp logged as "?". The title is what a reader can actually find on
        # the page, so the log names that rather than a field that is absent.
        who = str(f.get("id") or f.get("title") or "?")[:70]
        summary["clamps"].append(
            f"{who}: {original} -> {UNCOMPUTED_CEILING} ({grade})")

    # Recorded unconditionally, for the reason the reconciler's summary is:
    # a key that appears only when something fired is indistinguishable from a
    # module that did nothing.
    meta = result.setdefault("run_meta", {})
    if isinstance(meta, dict):
        meta["uncomputed_severity_clamp"] = summary
    return summary
