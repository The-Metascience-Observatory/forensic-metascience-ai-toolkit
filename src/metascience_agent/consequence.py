"""What a finding CHANGES, as distinct from how wrong it is.

WHY THIS EXISTS
---------------
Severity answers "can these numbers be right?". It says nothing about whether
anything the paper claims depends on the answer. A p-value typo'd from .043 to
.034 and a discrepancy that turns a significant result non-significant are both
`suspicious`, and before this module the report could not tell them apart --
they sorted by the model's own `rank` and rendered identically.

The information was already there and was thrown away twice:

* `statcheck` returns `decision_error` per statistic. That field means,
  precisely, "recomputing this p moves it across the alpha the paper used".
* `multiplicity_report` returns `n_claims_lost_to_correction` -- how many
  results significant uncorrected fail to survive correction.

So this is mostly plumbing, not modelling. Which is the point: a consequence a
tool computed is worth more than one a model asserted, and the only way to keep
that distinction is to derive the computed ones mechanically.

THE GUARD, AND WHY IT NEEDS THE LEDGER
--------------------------------------
`basis` records where the claim came from, and the two are rendered
differently to a reader. A first version of this module read the consequence
keys straight out of a finding's `computed` block and labelled the result
`computed`. That guard was cosmetic: `computed` is `additionalProperties: true`
in the findings schema and is written by the MODEL, in the same JSON blob as
everything else. A finding claiming `technique: "manual"` with
`computed: {"n_claims_lost_to_correction": 99}` was awarded the highest
consequence rank in the system, on a number nothing produced.

So a `computed` basis now requires CORROBORATION from the tool-call ledger --
the record of what the validated MCP tools actually returned. Values that
appear in a finding but not in any real tool result are treated as `asserted`.
Corroboration fails CLOSED: with no ledger, nothing is `computed`.

`null` is preserved as `null` throughout: an unknown consequence and a
consequence of none are different claims, and collapsing them would let "we did
not check" render as "nothing depends on it".
"""

from __future__ import annotations

import json
import re
from typing import Any

COMPUTED = "computed"
ASSERTED = "asserted"

#: Keys whose values carry consequence information. Corroboration is checked
#: against exactly these, so adding a producer means adding it here.
CONSEQUENCE_KEYS = ("decision_error", "decision_errors", "n_claims_lost_to_correction")

#: WHICH TOOL PRODUCES EACH CONSEQUENCE KEY. Corroboration without this is
#: value matching, and value matching is the defect it was built to stop:
#: censused over the live run's 53-call ledger, every integer 0-21 plus 23 and
#: 26 appears somewhere in a validated result, and so do both booleans. A
#: matcher that accepts "this number occurs in the ledger" fires on 14 of 14
#: consequence claims -- the original exploit with extra steps.
CONSEQUENCE_PRODUCERS = {
    "decision_error": "statcheck",
    "decision_errors": "statcheck",
    "n_claims_lost_to_correction": "multiplicity_report",
}

#: Collapsing runs of whitespace left behind when a repeated sentence is cut
#: out of an explanation. See `_merge_explanation`.
_WS = re.compile(r"\s+")


def _exact_int(value: Any) -> int | None:
    """An integer, or None. Never a truncation and never a bool.

    `True` is an `int` in Python, so a naive cast counts a boolean flag as one
    claim. And `int(0.9)` is 0, which would silently turn a fractional value
    into a clean bill of health rather than a refusal.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


# ---------------------------------------------------------------------------
# Corroboration
# ---------------------------------------------------------------------------

def _walk(node: Any, out: set[tuple[str, Any]]) -> None:
    """Collect every (consequence key, value) pair anywhere in a tool result.

    Recursive because statcheck nests `decision_error` inside
    `result["statistics"][i]` and only the TOTAL appears at the top level. A
    flat lookup found the totals and missed every per-statistic flag -- over
    the committed corpus, 0 of 17 statcheck findings carried a top-level
    `decision_error`.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            if key in CONSEQUENCE_KEYS and not isinstance(value, (dict, list)):
                out.add((key, value))
            _walk(value, out)
    elif isinstance(node, list):
        for item in node:
            _walk(item, out)


def corroboration_from_ledger(ledger: list[dict] | None) -> set[tuple[str, Any]] | None:
    """What the VALIDATED tools actually returned, as (key, value) pairs.

    Returns None when there is no ledger to read, which callers must treat as
    "cannot corroborate" rather than "nothing to corroborate" -- the difference
    between failing closed and failing open.

    Only `validated` calls count. An unvalidated call is the model running its
    own code, which is precisely the provenance this is meant to exclude.
    """
    if ledger is None:
        return None
    found: set[tuple[str, Any]] = set()
    for call in ledger:
        if not isinstance(call, dict) or not call.get("validated"):
            continue
        text = call.get("result")
        if not isinstance(text, str) or not text.strip():
            continue
        try:
            _walk(json.loads(text), found)
        except (ValueError, TypeError):
            # MCP results are sometimes wrapped in prose. Fall back to finding
            # the keys textually rather than discarding the whole record.
            for key in CONSEQUENCE_KEYS:
                for m in re.finditer(rf'"{key}"\s*:\s*(true|false|-?\d+)', text):
                    raw = m.group(1)
                    found.add((key, {"true": True, "false": False}.get(raw)
                               if raw in ("true", "false") else int(raw)))
    return found


def _corroborated(key: str, value: Any,
                  corroboration: set[tuple[str, Any]] | None) -> bool:
    if corroboration is None:
        return False
    return (key, value) in corroboration


# ---------------------------------------------------------------------------
# Derivation
# ---------------------------------------------------------------------------

def from_tool_output(computed: dict | None,
                     corroboration: set[tuple[str, Any]] | None = None) -> dict | None:
    """Derive a consequence block from a finding's `computed` output, or None.

    `basis` is `computed` only where every value used appears in the tool-call
    ledger. Otherwise the same numbers are reported as `asserted` -- they may
    well be right, but nothing establishes that they came from a tool.

    Returns None when the output carries no consequence information at all --
    the common case, and one that must not be confused with a consequence of
    zero.
    """
    if not isinstance(computed, dict):
        return None

    found: set[tuple[str, Any]] = set()
    _walk(computed, found)
    if not found:
        return None

    flips: bool | None = None
    claims: int | None = None
    why: list[str] = []
    all_corroborated = True

    # --- multiplicity: refuse on the tool's own red flag --------------------
    # `multiplicity_report` surfaces `internal_inconsistency` rather than
    # clamping a negative claim count away. Deriving a consequence from
    # arithmetic the tool has flagged as wrong would launder its warning into
    # a clean bill of health.
    if computed.get("internal_inconsistency") is True:
        return {
            "flips_significance": None,
            "claims_affected": None,
            "basis": ASSERTED,
            "explanation": (
                "The multiplicity arithmetic flagged itself as internally "
                "inconsistent, so no consequence can be derived from it."
            ),
        }

    # --- statcheck ---------------------------------------------------------
    # A per-statistic `decision_error` is the cleanest signal available: it
    # means the recomputed p crosses the alpha the paper used. `False` is a
    # finding in its own right ("checked, nothing moves") and is kept.
    per_stat = [v for (k, v) in found if k == "decision_error" and isinstance(v, bool)]
    if per_stat:
        flips = any(per_stat)
        why.append(f"statcheck decision_error over {len(per_stat)} statistic(s)")
        for v in set(per_stat):
            all_corroborated &= _corroborated("decision_error", v, corroboration)

    totals = [_exact_int(v) for (k, v) in found if k == "decision_errors"]
    totals = [n for n in totals if n is not None]
    if totals:
        n = max(totals)
        if flips is None:
            flips = n > 0
        else:
            flips = flips or n > 0
        # NOT `claims_affected`. `decision_errors` counts STATISTICS, and the
        # schema defines claims_affected as claims the paper STATES depend on
        # this. Several statistics can back one claim, one claim can rest on
        # none of them, and this total is a whole-paper roll-up that happens to
        # be attached to whichever finding embedded the statcheck summary.
        why.append(f"{n} statistic(s) whose recomputed p crosses the paper's alpha")
        all_corroborated &= _corroborated("decision_errors", n, corroboration)

    # --- multiplicity ------------------------------------------------------
    lost = None
    for (k, v) in found:
        if k == "n_claims_lost_to_correction":
            lost = _exact_int(v)
            break
    if lost is not None and lost >= 0:
        claims = lost
        # NOT a significance flip. `flips_significance` is defined as crossing
        # THE ALPHA THE PAPER USED, and a result lost to Benjamini-Hochberg
        # does not: it fails a correction the paper did not apply, over a
        # family `multiplicity_report` explicitly declines to assert is the
        # right one. Calling that a flip would import a judgement into the
        # basis reserved for things a tool established.
        why.append(
            f"{lost} result(s) significant uncorrected do not survive correction "
            "(a correction the paper did not apply, over a family we chose)"
        )
        all_corroborated &= _corroborated("n_claims_lost_to_correction", lost, corroboration)

    if flips is None and claims is None:
        return None

    block: dict[str, Any] = {
        "flips_significance": flips,
        "claims_affected": claims,
        "basis": COMPUTED if all_corroborated else ASSERTED,
    }
    if why:
        lead = "Computed from" if all_corroborated else "Stated in the finding, not corroborated by any tool call:"
        block["explanation"] = f"{lead} " + "; ".join(why) + "."
    return block


def normalise(block: Any) -> dict | None:
    """Coerce a model-supplied consequence block into the schema's shape.

    Anything arriving here is `asserted`. `from_tool_output` with a ledger is
    the only producer of `computed`.
    """
    if not isinstance(block, dict):
        return None
    out: dict[str, Any] = {
        "flips_significance": (block.get("flips_significance")
                               if isinstance(block.get("flips_significance"), bool) else None),
        "claims_affected": _exact_int(block.get("claims_affected")),
        "basis": ASSERTED,
    }
    if isinstance(block.get("explanation"), str) and block["explanation"].strip():
        out["explanation"] = block["explanation"].strip()
    return out


# ---------------------------------------------------------------------------
# Ordering and rendering
# ---------------------------------------------------------------------------

def rank(finding: dict | None) -> tuple[int, int]:
    """Sort key within a severity band. Lower sorts first.

    The ordering, and why:

    1. **Flips a significance decision** -- a conclusion in the paper changes.
    2. **Affects stated claims without flipping one** -- it touches something
       the paper argues, but no reported decision moves.
    3. **Unknown** -- we did not determine the consequence. Above (4) because
       "not checked" must never be presented as "harmless"; a reader who reads
       silence as clearance is the failure this whole toolkit exists to avoid.
    4. **Explicitly flips nothing** -- checked, and nothing the paper claims
       depends on it.

    `basis` breaks ties WITHIN a level, so a computed claim outranks an
    identical asserted one. It is deliberately not the primary key: an asserted
    flip still sorts above a computed non-flip, because the magnitude of the
    consequence is what a reader triages by and the provenance is rendered
    beside it to be discounted.

    Total on any input. This runs from `sort_findings` on RAW model output,
    before `normalise` has coerced anything, and the renderer's contract is
    that it must never fail the analysis pipeline -- a `TypeError` here loses
    the whole rendered report to the fallback path.
    """
    block = (finding or {}).get("consequence")
    if not isinstance(block, dict):
        return (2, 1)
    flips = block.get("flips_significance")
    claims = _exact_int(block.get("claims_affected")) or 0
    if flips is True:
        level = 0
    elif claims > 0:
        level = 1
    elif flips is False:
        level = 3
    else:
        level = 2
    return (level, 0 if block.get("basis") == COMPUTED else 1)


def describe(block: dict | None) -> str | None:
    """One-line human rendering, or None when there is nothing to say."""
    if not isinstance(block, dict):
        return None
    parts: list[str] = []
    flips = block.get("flips_significance")
    claims = _exact_int(block.get("claims_affected"))
    if flips is True:
        parts.append("changes a significance decision")
    elif flips is False:
        parts.append("changes no significance decision")
    if claims is not None and claims > 0:
        parts.append(f"{claims} stated claim{'s' if claims != 1 else ''} affected")
    if not parts:
        return None
    tag = "computed" if block.get("basis") == COMPUTED else "asserted, not computed"
    text = "; ".join(parts)
    explanation = block.get("explanation")
    if isinstance(explanation, str) and explanation.strip():
        text = f"{text} -- {explanation.strip()}"
    return f"{text} ({tag})"


# ---------------------------------------------------------------------------
# The pass
# ---------------------------------------------------------------------------

def _merge_explanation(derived: dict, model_block: Any) -> dict:
    """Keep the model's explanation alongside the derived one.

    The schema asks the model for "one sentence naming the specific claim
    affected" and the derived string names no claim -- it names the arithmetic.
    Replacing one with the other discards the more useful half.
    """
    out = dict(derived)
    if isinstance(model_block, dict):
        stated = (model_block.get("explanation") or "").strip()
        computed = (out.get("explanation") or "").strip()
        # IDEMPOTENT. `annotate` runs twice on every real run -- once in
        # `analyze_paper` before the report is rendered, once in
        # `write_review_outputs` -- and on the second pass `model_block` is the
        # block this function produced on the first. Appending unconditionally
        # therefore doubled the derived sentence in the saved output:
        # "... do not survive correction (...). ... do not survive correction (...)."
        # Containment rather than equality, because the first pass has already
        # concatenated the model's sentence in front of the derived one.
        if stated and computed:
            # Strip every existing copy of the derived sentence and re-append
            # one. Idempotent, and it also REPAIRS a block already doubled by
            # the previous behaviour rather than freezing the duplicate in.
            prefix = _WS.sub(" ", stated.replace(computed, " ")).strip()
            out["explanation"] = f"{prefix} {computed}".strip()
        elif stated:
            out["explanation"] = stated
    return out


def annotate(result: dict, ledger: list[dict] | None = None) -> dict:
    """Populate `consequence` across a run's findings, in place.

    `ledger` is the tool-call ledger (see `agent._tool_call_ledger`). Without
    it nothing can be marked `computed` -- see the module docstring.

    Two passes:

    1. **Sweep findings** get a block derived from their own `computed` output,
       corroborated against the ledger; anything the model wrote is demoted to
       `asserted`.
    2. **Report findings** inherit the strongest computed block among the sweep
       findings they cite in `stage1_finding_ids`. A stage-2 finding that rests
       on a computed consequence should not lose it because stage 2 rewrote the
       prose.
    """
    corroboration = corroboration_from_ledger(ledger)
    summary = {
        "n_sweep": 0, "n_report": 0,
        "n_computed": 0, "n_asserted": 0, "n_absent": 0,
        "corroborated": corroboration is not None,
    }

    sweep = (result.get("findings") or {})
    sweep_items = sweep.get("findings") if isinstance(sweep, dict) else None
    by_id: dict[str, dict] = {}

    def _record(finding: dict, block: dict | None) -> None:
        if block is None:
            finding.pop("consequence", None)
            summary["n_absent"] += 1
        else:
            finding["consequence"] = block
            summary["n_computed" if block["basis"] == COMPUTED else "n_asserted"] += 1

    for f in sweep_items or []:
        if not isinstance(f, dict):
            continue
        summary["n_sweep"] += 1
        model_block = f.get("consequence")
        derived = from_tool_output(f.get("computed"), corroboration)
        block = (_merge_explanation(derived, model_block) if derived
                 else normalise(model_block))
        _record(f, block)
        fid = f.get("id")
        if isinstance(fid, str):
            by_id[fid] = f

    report = (result.get("report_obj") or {})
    report_items = report.get("findings") if isinstance(report, dict) else None
    for f in report_items or []:
        if not isinstance(f, dict):
            continue
        summary["n_report"] += 1
        model_block = f.get("consequence")
        inherited = [
            by_id[i]["consequence"]
            for i in (f.get("stage1_finding_ids") or [])
            if isinstance(i, str) and i in by_id
            and isinstance(by_id[i].get("consequence"), dict)
            and by_id[i]["consequence"].get("basis") == COMPUTED
        ]
        if inherited:
            # Strongest of the cited sweep findings. `rank` already encodes
            # "strongest", so reuse it rather than inventing a second ordering.
            # COPIED, not aliased: the same dict on two findings means a later
            # in-place edit to one silently changes the other.
            block = _merge_explanation(
                min(inherited, key=lambda b: rank({"consequence": b})), model_block)
        else:
            block = normalise(model_block)
        _record(f, block)

    if summary["n_sweep"] or summary["n_report"]:
        meta = result.setdefault("run_meta", {})
        if isinstance(meta, dict):
            meta["consequence"] = summary
    return summary


# ---------------------------------------------------------------------------
# The v2 path
#
# WHY A SECOND ENTRY POINT RATHER THAN A CALL TO `annotate`. The parallel
# pipeline never called this module at all, and on the live run of 2026-08-29
# that showed: 14 of 34 findings carried `basis: "computed"` and 12 of those
# were `computed_by: "model_reading"` -- the model asserted the number and the
# row said a tool produced it. `bundle.py` ranks `computed` above `asserted`
# within a severity band and prints the word, so the forgery reached the reader
# with the toolkit's own authority attached.
#
# Re-calling `annotate` was tried and is WRONG, not merely incomplete. It walks
# a v1 result shape, and its exact-key match cannot see a v2 finding's
# derivation-suffixed keys -- the v2 schema instructs the model to write
# `n_claims_lost_to_correction_read_off_bh` rather than the bare name. Replayed
# over the live ledger it corroborates NOTHING, including the one claim that is
# genuinely corroborable. The guard and the schema drifted apart during the
# period they were disconnected, so a naive re-plumb demotes a true positive
# and calls that a fix.
# ---------------------------------------------------------------------------

def corroboration_by_producer(
        ledger: list[dict] | None) -> dict[str, set[tuple[str, Any]]] | None:
    """`{tool: {(key, value)}}` from VALIDATED calls, per producing tool.

    Same pair semantics as `corroboration_from_ledger`, partitioned by which
    tool returned them. `annotate` keeps using the unpartitioned view, so
    nothing on the legacy path changes.
    """
    if ledger is None:
        return None
    out: dict[str, set[tuple[str, Any]]] = {}
    for call in ledger:
        if not isinstance(call, dict) or not call.get("validated"):
            continue
        name = str(call.get("tool_short") or call.get("tool") or "").split("__")[-1]
        if not name:
            continue
        found: set[tuple[str, Any]] = set()
        text = call.get("result")
        if isinstance(text, str) and text.strip():
            try:
                _walk(json.loads(text), found)
            except (ValueError, TypeError):
                for key in CONSEQUENCE_KEYS:
                    for m in re.finditer(rf'"{key}"\s*:\s*(true|false|-?\d+)', text):
                        raw = m.group(1)
                        found.add((key, {"true": True, "false": False}.get(raw)
                                   if raw in ("true", "false") else int(raw)))
        if found:
            out.setdefault(name, set()).update(found)
    return out


def _canonical_view(computed: Any, technique: Any) -> dict | None:
    """A finding's consequence numbers under their CANONICAL keys, gated.

    Two gates, and the second is the one that closes the borrowing hole. A
    finding-side key counts when it is a consequence key or that key plus a
    derivation suffix (`n_claims_lost_to_correction_read_off_bh`), AND when the
    finding's own `technique` names the tool that produces it.

    An earlier cut of this fell back to the ungated derivation when the gated
    view came out empty, and a finding carrying the exact canonical key under
    the WRONG technique came out `computed` -- verified firing. That is the same
    two-paths-one-guarded shape that caused the original defect, so there is no
    fallback here: this view is the only path.
    """
    if not isinstance(computed, dict):
        return None
    tech = str(technique or "")
    view: dict[str, Any] = {}
    for key, value in computed.items():
        k = str(key)
        for canon in CONSEQUENCE_KEYS:
            if (k == canon or k.startswith(canon + "_")) \
                    and tech == CONSEQUENCE_PRODUCERS[canon]:
                view[canon] = value
                break
    if not view:
        return None
    # The tool's own red flag travels with the numbers, or `from_tool_output`
    # cannot refuse on it.
    if computed.get("internal_inconsistency") is True:
        view["internal_inconsistency"] = True
    return view


def annotate_v2(findings: list[dict] | None,
                ledger: list[dict] | None = None) -> dict:
    """Populate `consequence` across v2 findings, in place.

    FAILS TOWARD `asserted`, ALWAYS. Labelling an asserted claim `computed`
    forges the one distinction this toolkit rests on, in the direction a reader
    trusts -- on a run where 29 of 34 findings are `model_reading`, that badge
    is the only thing separating "a validated tool computed this" from "the
    model asserted it". Labelling a computed claim `asserted` merely
    understates: the number still prints, with honest provenance. So every
    ambiguity -- no ledger, a truncated result, an unmatched technique, a
    partially corroborated block -- resolves to `asserted`.
    """
    by_producer = corroboration_by_producer(ledger)
    summary = {"n_computed": 0, "n_asserted": 0, "n_absent": 0,
               "corroborated": by_producer is not None}
    for f in (findings or []):
        if not isinstance(f, dict):
            continue
        view = _canonical_view(f.get("computed"), f.get("technique"))
        block = None
        if view is not None:
            producer = next((CONSEQUENCE_PRODUCERS[k] for k in view
                             if k in CONSEQUENCE_PRODUCERS), None)
            corr = (by_producer or {}).get(producer) if by_producer is not None else None
            block = from_tool_output(view, corr)
        if block is None:
            block = normalise(f.get("consequence"))
        else:
            block = _merge_explanation(block, f.get("consequence"))
        if block is None:
            f.pop("consequence", None)
            summary["n_absent"] += 1
        else:
            f["consequence"] = block
            summary["n_computed" if block.get("basis") == COMPUTED
                    else "n_asserted"] += 1
    return summary
