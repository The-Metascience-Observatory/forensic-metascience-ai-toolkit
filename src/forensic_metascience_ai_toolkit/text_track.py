"""
The deterministic text-forensics track (tortured-phrases screen), run as an
ISOLATED CHILD PROCESS.

Invoked as `python -m forensic_metascience_ai_toolkit.text_track <paper_dir> --json` by
`analyze_paper`, concurrently with the stage-1 sweep. The matching itself is
pure Python and cannot segfault -- the subprocess exists for the EXTRACTION
fallback: a paper without body.md/XML/HTML forces a pdfplumber pass, whose
layout analysis genuinely hangs and balloons memory on pathological PDFs, and
asyncio cannot cancel a CPU-bound library call in-process. A child is
killable, and the containment client (`agent._run_forensic_track`) already
exists for the image track; a uniform track contract means the next text
screen lands on the same rails.

The contract with the parent is `schema/text_track.schema.json`: one
JSON object on stdout. The parent validates it structurally and injects
`findings_rows` only from a valid object -- malformed output becomes
`track_output_invalid` with zero findings injected, never an exception in the
pipeline. Every row leaves here QUARANTINED (`severity` is `indeterminate` or
`consistent`); the pre-registered grade rides in `severity_before_quarantine`.

ROWS ARE PER FAMILY, NOT PER MATCH (deliberately unlike the image track):
each image duplicate group is independent evidence needing its own
side-by-side review, while tortured phrases are homogeneous within a family
-- the AGGREGATE count of distinct fingerprints is the signal, and severity
attaches to the pattern. At most 3 rows (one per family that fired), each
itemizing up to `_MAX_MATCHES_PER_ROW` distinct fingerprints with the
remainder ANNOUNCED, never silent. Zero guarded hits => zero rows: a finite
dictionary cannot certify prose, so there is no `consistent` row.

REFUSAL SUBTYPES ARE DISTINCT FACTS (the house invariant):
`fingerprints_missing` is a property of the installation; `no_text_source` of
the directory (no text-bearing file at all); `text_unreadable` of the files
(sources exist, none yielded text -- the shape of a scanned, never-OCR'd
paper). Only when the dictionary loaded and real text was scanned does
`status.ran` become True -- and only then does the report swap its blanket
"no tortured-phrase screening" note for the narrower scope note.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"

#: Distinct fingerprints itemised inside one family row. A mill paper can
#: carry 50+ distinct tortured phrases; the paid editorial prompt re-reads
#: every byte injected here, so the list is capped and the remainder is
#: announced in the same row. The COUNTS are never capped.
_MAX_MATCHES_PER_ROW = 10

#: Row order is fixed so ids are stable across runs of the same paper.
_FAMILY_ORDER = ("tortured_phrase", "llm_boilerplate", "tortured_acronym")

_FAMILY_LABEL = {
    "tortured_phrase": "tortured phrase(s)",
    "llm_boilerplate": "LLM-boilerplate string(s)",
    "tortured_acronym": "tortured acronym expansion(s)",
}


def _family_rows(result: dict, paper_dir: Path) -> list[dict]:
    """Shape the tool result as findings.schema.json rows, one per family
    with at least one GUARDED (unsuppressed) body match."""
    reproduction = ("metascience tool run detect_tortured_phrases --json "
                    + shlex.quote(json.dumps({"paper_dir": str(paper_dir)})))
    quarantine_reason = result.get("quarantine_reason", "")
    raw_by_family = result.get("severity_raw_by_family", {})
    rows: list[dict] = []
    for family in _FAMILY_ORDER:
        guarded = [m for m in result.get("matches", [])
                   if m["family"] == family and m["suppressed_by"] is None]
        if not guarded:
            continue
        distinct: dict[str, list[dict]] = {}
        for m in guarded:
            distinct.setdefault(m["fingerprint"], []).append(m)
        itemised = list(distinct.items())[:_MAX_MATCHES_PER_ROW]
        n_not_itemised = len(distinct) - len(itemised)
        # acronym expansions ride the tortured_phrase ladder
        raw = raw_by_family.get(
            "tortured_phrase" if family == "tortured_acronym" else family,
            result.get("severity_before_quarantine")
            or result.get("severity", ""))
        items = [{
            "matched": fp_name,
            "expected": ms[0]["expected"],
            "count": len(ms),
            "example_context": ms[0]["context"],
            "in_quotation": ms[0]["in_quotation"],
            "extraction_risk": any(m["extraction_risk"] for m in ms),
        } for fp_name, ms in itemised]
        sample = "; ".join(
            f"'{it['matched']}'"
            + (f" for '{it['expected']}'" if it["expected"] else "")
            for it in items[:3])
        remainder = (f" {n_not_itemised} further distinct fingerprint(s) are "
                     f"not itemised here (row budget); the full list is in "
                     f"text_forensics.json -- the counts above are complete."
                     if n_not_itemised else "")
        rows.append({
            "id": f"TORT-{len(rows) + 1}",
            "location": "body text (offsets in text_forensics.json)",
            "technique": "tortured_phrases",
            "consistent": False,
            "severity": "indeterminate",
            "reproduction": reproduction,
            "inputs": {
                "family": family,
                "n_distinct_fingerprints": len(distinct),
                "n_total_occurrences": len(guarded),
                "n_not_itemised": n_not_itemised,
                "dictionary_version": result["dictionary"]["version"],
                "dictionary_sha256": result["dictionary"]["sha256"],
                "matches": items,
            },
            "explanation": (
                f"{len(distinct)} distinct {_FAMILY_LABEL[family]} "
                f"({len(guarded)} occurrence(s)) survived the guards, e.g. "
                f"{sample}.{remainder} QUARANTINED: this screen's "
                f"false-positive classes are not yet measured on this "
                f"pipeline, so it may not accuse -- the pre-registered grade "
                f"was '{raw}'. {quarantine_reason} Report as an unvalidated "
                f"signal for human review of the quoted spans, never as a "
                f"finding of record, and never in the headline."),
            "severity_before_quarantine": raw,
            "quarantine_reason": quarantine_reason,
        })
    return rows


#: Fallback `quarantine_reason` for a v2 row when the tool result carries an
#: empty one -- the v2 contract forbids a bare cap with no reason, and the v1
#: rows legitimately ship `""` there.
_V2_TEXT_QUARANTINE_REASON = (
    "The tortured-phrases screen's false-positive classes are not yet "
    "measured on this pipeline, so it may not accuse; every row it emits is "
    "quarantined by design.")

#: Provisional rung for a v2 row whose RAW grade was not accusatory (no
#: `severity9.FIVE_TO_NINE` mapping). Rung 2 sits below
#: `severity9.ACCUSATORY_MIN`: levels 1-2 are record-keeping, not
#: accusations. Mirrors `image_track._V2_NON_ACCUSATORY_PROVISIONAL`.
_V2_NON_ACCUSATORY_PROVISIONAL = 2


def _matched_text_for(result: dict, family: str, fingerprint: str) -> str:
    """The verbatim matched span for one itemised fingerprint.

    The v1 items record the FINGERPRINT name; the anchor wants the text as
    it appears in the paper (`matched_text`), which can differ from the
    dictionary entry through case or a hyphenation variant -- and an anchor
    that quotes the dictionary instead of the paper may fail to locate. The
    first guarded occurrence is used, the same one `_family_rows` takes
    `example_context` from.
    """
    for m in result.get("matches", []):
        if (m.get("family") == family and m.get("suppressed_by") is None
                and m.get("fingerprint") == fingerprint):
            return str(m.get("matched_text") or "") or fingerprint
    return fingerprint


def _family_rows_v2(result: dict, paper_dir: Path) -> list[dict]:
    """The tool result as findings_v2 records, one per fired family
    (ADDITIVE: emitted only under `run_track(..., emit_v2=True)`, beside the
    v1 rows -- dual emission per findings_v2.md).

    DERIVED FROM THE V1 ROWS, so the per-family aggregation, itemisation cap
    and announced remainder cannot drift from what stage 2 was shown.
    Anchors are one `quote` record per ITEMISED distinct fingerprint, the
    matched span verbatim (spec section 3 -- upgrades tortured-phrase
    findings from unlocatable to anchored). `tool_verdict` is builder-written
    (this track has no ledger to join and no prose to distrust): delivered
    severity `indeterminate`, the pre-registered grade in `quarantined_raw`
    (v1's `severity_before_quarantine`).
    """
    from . import findings_v2, severity9

    quarantine_reason = (result.get("quarantine_reason", "")
                         or _V2_TEXT_QUARANTINE_REASON)
    rows: list[dict] = []
    for v1 in _family_rows(result, paper_dir):
        inputs = dict(v1["inputs"])
        family = inputs["family"]
        raw = v1.get("severity_before_quarantine") or ""
        anchors = [
            {"kind": "quote",
             "quote": _matched_text_for(result, family, item["matched"])}
            for item in inputs.get("matches", []) if item.get("matched")
        ]
        rows.append({
            "slug": v1["id"],
            "producer": "text_track",
            # Registry-exact tool name (findings_v2.md section 1.2), not
            # v1's `tortured_phrases` label.
            "technique": "detect_tortured_phrases",
            "title": findings_v2.clip(
                f"Body text: {inputs['n_distinct_fingerprints']} distinct "
                f"{_FAMILY_LABEL[family]} survived the guards", 90),
            "description": findings_v2.clip(v1["explanation"], 700),
            "location": v1["location"],
            "outcome": "problem",
            "provisional_severity": severity9.FIVE_TO_NINE.get(
                raw, _V2_NON_ACCUSATORY_PROVISIONAL),
            "severity_is_provisional": True,
            "impossible": False,
            "quarantined": True,
            "quarantine_reason": quarantine_reason,
            "computed_by": "deterministic_track",
            "tool_verdict": {
                "severity": "indeterminate",
                "tool": "detect_tortured_phrases",
                "validated": True,
                "quarantined_raw":
                    raw if raw in severity9.OUTCOME_FROM_FIVE else None,
            },
            "inputs": inputs,
            "anchors": anchors,
            "reproduction": v1["reproduction"],
        })
    findings_v2.assign_finding_ids(rows, paper_dir.name)
    # Quarantine cap: FIVE_TO_NINE's ceiling of 5 clamps to
    # severity9.QUARANTINE_CAP (probabilistic evidence class, quarantined).
    findings_v2.clamp_provisionals(rows)
    return rows


def run_track(paper_dir: str | Path, emit_v2: bool = False) -> dict[str, Any]:
    """Run the whole track for one paper directory.

    Anticipated failures (no dictionary, no text source, unreadable text)
    become structured refusal statuses. Anything unanticipated is allowed to
    crash THE CHILD -- containment of exactly that is why this runs as a
    subprocess, and the parent records it as `track_crashed` without the text
    review noticing.

    `emit_v2=True` adds a `findings_rows_v2` key to the envelope (empty on
    every refusal path) carrying `_family_rows_v2` records BESIDE the v1
    rows -- dual emission per findings_v2.md. The default is False and the
    `__main__` path never passes it, so the live subprocess contract is
    byte-identical until the v2 cutover.
    """
    t0 = time.monotonic()
    paper_dir = Path(paper_dir)

    def _status(ran: bool, subtype: str | None, detail: str = "",
                **extra: Any) -> dict[str, Any]:
        return {"ran": ran, "refusal_subtype": subtype,
                "wall_seconds": round(time.monotonic() - t0, 2),
                "detail": detail, **extra}

    def _out(status: dict, result: dict | None = None,
             rows: list[dict] | None = None,
             rows_v2: list[dict] | None = None) -> dict[str, Any]:
        out = {"schema_version": SCHEMA_VERSION, "paper_id": paper_dir.name,
               "status": status, "result": result or {},
               "findings_rows": rows or []}
        # The key EXISTS only under emit_v2, so the live envelope stays
        # byte-identical; under emit_v2 it exists on refusal paths too --
        # an absent key would read as "v2 was not asked for" on exactly the
        # runs where the answer is "asked for, and there was nothing".
        if emit_v2:
            out["findings_rows_v2"] = rows_v2 or []
        return out

    from .tools.tortured_phrases import detect_tortured_phrases
    result = detect_tortured_phrases(paper_dir=str(paper_dir))

    if not result.get("success"):
        subtype = {"dictionary_missing": "fingerprints_missing",
                   "no_text_source": "no_text_source",
                   "text_unreadable": "text_unreadable"}.get(
                       result.get("refusal", ""), "text_unreadable")
        dict_block = result.get("dictionary") or {}
        return _out(_status(
            False, subtype, result.get("error", ""),
            text_source=None,
            dictionary_version=dict_block.get("version", ""),
            dictionary_sha256=dict_block.get("sha256", ""),
            n_fingerprints_loaded=dict_block.get("n_fingerprints", 0),
        ), result)

    rows = _family_rows(result, paper_dir)
    rows_v2 = _family_rows_v2(result, paper_dir) if emit_v2 else None
    families_fired = sorted({r["inputs"]["family"] for r in rows})
    k = result.get("n_distinct_fingerprints", 0)
    return _out(_status(
        True, None,
        (f"{k} distinct guarded fingerprint(s) across "
         f"{result.get('n_matches', 0)} match(es) in "
         f"{result.get('n_words_scanned', 0)} words"),
        text_source=result.get("text_source") or "direct",
        dictionary_version=result["dictionary"]["version"],
        dictionary_sha256=result["dictionary"]["sha256"],
        n_fingerprints_loaded=result["dictionary"]["n_fingerprints"],
        n_words_scanned=result.get("n_words_scanned", 0),
        families_fired=families_fired,
    ), result, rows, rows_v2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic tortured-phrases track (child process).")
    parser.add_argument("paper_dir")
    parser.add_argument("--json", action="store_true",
                        help="emit the machine contract on stdout (what the "
                             "pipeline consumes)")
    args = parser.parse_args(argv)

    try:
        out = run_track(args.paper_dir)
    except Exception as exc:  # noqa: BLE001 -- crash the child loudly, alone
        print(f"text_track crashed: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 3
    if args.json:
        json.dump(out, sys.stdout)
        sys.stdout.write("\n")
    else:
        st = out["status"]
        print(f"paper: {out['paper_id']}")
        print(f"ran: {st['ran']}  refusal: {st['refusal_subtype']}  "
              f"({st['wall_seconds']}s)")
        print(st.get("detail", ""))
        for row in out["findings_rows"]:
            print(f"- {row['inputs']['family']}: {row['explanation']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
