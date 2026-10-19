"""LLM judge: grade a produced review against a fixture's key findings.

The judge scores against hand-authored expected findings (not free-form
quality) to limit judge circularity; verdict agreement and the deterministic
checks stay LLM-free.

Severity calibration (optional, per key finding):
  - `severity_expected: [min, max]` — an INTERVAL over the severity ladder,
    because the label author's own certainty is bounded; a wide interval
    encodes "I am not sure either".
  - `confidence: high|medium|low` — `low` rows are scored and reported but
    EXCLUDED from the pass/fail aggregates (the "can't tell" bucket).
The judge's only new job is naming WHICH finding in findings.json covers each
expected finding; the severity itself is then read DETERMINISTICALLY from
findings.json, keeping the LLM out of the calibration arithmetic. Aggregates
are directional on purpose: over-severity (accusation where the label says
none is warranted) and under-severity (a miss) are different failures, and
`severity_bias` (signed) makes systematic hedging or over-accusation visible
where a symmetric error count would hide it.
"""

from __future__ import annotations

import json
from typing import Any

from ..agent import _build_claude_cmd, _extract_json, _run_stage
from ..llm_backend import resolve_backend
from ..tools.severity import SEVERITY_LEVELS, normalize_severity

WEIGHTS = {"critical": 3, "major": 2, "minor": 1}

#: Rank on the ladder, most severe first: impossible=4 ... consistent=0.
_SEV_RANK = {name: rank for rank, name in enumerate(reversed(SEVERITY_LEVELS))}

JUDGE_SCHEMA: dict = {
    "type": "object",
    "required": ["per_finding", "false_positives"],
    "additionalProperties": False,
    "properties": {
        "per_finding": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "covered"],
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string"},
                    "covered": {
                        "type": "boolean",
                        "description": "true iff the review substantively raises this problem (any wording)",
                    },
                    "evidence_quote": {
                        "type": "string",
                        "description": "verbatim excerpt from the review showing coverage (empty if not covered)",
                    },
                    "matched_finding_id": {
                        "type": "string",
                        "description": "the `id` of the finding in findings.json that covers this expected finding (empty if not covered or if only the prose report covers it)",
                    },
                },
            },
        },
        "false_positives": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["claim", "why_unsupported"],
                "additionalProperties": False,
                "properties": {
                    "claim": {"type": "string"},
                    "why_unsupported": {"type": "string"},
                },
            },
            "description": "confident severe claims in the review that the gold review does not support and that rest on invented assumptions",
        },
        "notes": {"type": "string"},
    },
}


#: The fields of a finding the judge needs to grade coverage and false
#: positives. The full JSON (anchors, inputs, ledger joins, register) was cut
#: at 30,000 characters, so a review that filed 60-80 findings -- the
#: post-fix Grok runs of 2026-10-14 -- was graded on whatever fitted, and
#: judges wrote "findings.json was truncated" in their notes.
_JUDGE_FIELDS = ("finding_id", "id", "producer", "technique", "title", "description",
                 "location", "outcome", "severity", "provisional_severity")


def _judge_view(findings: Any) -> Any:
    if isinstance(findings, dict) and isinstance(findings.get("findings"), list):
        rows = [{k: f.get(k) for k in _JUDGE_FIELDS if f.get(k) is not None}
                for f in findings["findings"] if isinstance(f, dict)
                and (f.get("adjudication") or {}).get("action") not in ("discarded", "merged")]
        return {"findings": rows,
                "adjudication": {k: (findings.get("adjudication") or {}).get(k)
                                 for k in ("verdict", "paper_severity", "headline_finding_id", "summary")}}
    return findings


def _judge_prompt(fixture: dict, report_markdown: str, findings: Any) -> str:
    expected = [
        {
            "id": kf["id"],
            "weight": kf["weight"],
            "description": kf["description"],
            "aliases": kf.get("aliases", []),
        }
        for kf in fixture["key_findings"]
    ]
    findings_str = (
        json.dumps(_judge_view(findings), indent=1, default=str)[:60_000]
        if findings is not None
        else "(no structured findings)"
    )
    return f"""You are grading an automated forensic review of a scientific paper against a checklist of expected key findings derived from a human expert's gold-standard review.

For each expected finding below, decide whether the automated review SUBSTANTIVELY raises the same problem (wording may differ; use the aliases as hints, but judge the substance). A finding that identifies the SAME DEFECT by a different route counts as covered: for example, "the survey percentages imply 73-74 respondents, not the printed n=79/80" IS a GRIM failure against the printed n, even though it never says "GRIM". Quote the evidence, and when a finding in findings.json covers it, report that finding's `id` as matched_finding_id (empty string if coverage exists only in the prose report). Then list false positives: claims in the automated review presented as severe (impossible/highly suspicious) that rest on invented assumptions or that misread the paper — do not count reasonable minor observations.

EXPECTED KEY FINDINGS:
```json
{json.dumps(expected, indent=2)}
```

AUTOMATED REVIEW (report.md):
```markdown
{(report_markdown or "")[:40_000]}
```

AUTOMATED STRUCTURED FINDINGS (findings.json):
```json
{findings_str}
```

Emit ONLY the JSON verdict conforming to the schema."""


async def judge_paper(
    fixture: dict,
    report_markdown: str,
    findings: Any,
    model: str = "sonnet",
    timeout: int | None = 600,
    verbose: bool = False,
    backend=None,
    effort: str = "high",
) -> dict:
    """Run the judge and compute weighted recall. Returns a scorecard dict.

    `effort` is high: see `harness.JUDGE_EFFORT` for the measured mis-grade
    at medium."""
    be = resolve_backend(backend)
    prompt = _judge_prompt(fixture, report_markdown, findings)
    # Prompt is a required positional of `_run_stage` and must never go on
    # argv (128 KB MAX_ARG_STRLEN). The previous call omitted `prompt` and
    # put ~70 KB on `-p`, so every eval judge raised TypeError.
    cmd = _build_claude_cmd(
        system_prompt="Grade the review. Emit only JSON matching the schema.",
        allowed_tools=["Read"],
        model=model or be.default_model,
        effort=effort,
        json_schema=JUDGE_SCHEMA,
        backend=be,
    )
    stage = await _run_stage(cmd, prompt, verbose=verbose, timeout=timeout,
                             stage_label="judge")
    parsed, parse_path = _extract_json(stage)
    if parsed is None:
        return {
            "error": "judge output unparseable",
            "cost_usd": stage["cost_usd"],
        }
    scorecard = score_judgement(fixture, parsed, findings)
    scorecard["judge_parse_path"] = parse_path
    scorecard["cost_usd"] = stage["cost_usd"]
    return scorecard


def score_judgement(fixture: dict, parsed: dict, findings: Any) -> dict:
    """Deterministic scoring of the judge's parsed verdict.

    Separated from the LLM call so the arithmetic — weighted recall, the
    severity-interval calibration, the directional counts and the signed bias
    — is unit-testable without a model in the loop.
    """
    # Deterministic severity lookup: the judge only NAMES the matched finding;
    # its severity comes from findings.json, not from the judge.
    findings_list = (
        findings.get("findings") if isinstance(findings, dict) else findings
    ) or []
    severity_of: dict = {}
    known_ids: set = set()
    for f in findings_list:
        if not isinstance(f, dict):
            continue
        known_ids.update(k for k in (f.get("slug"), f.get("finding_id"),
                                     f.get("id")) if k)
        sev = f.get("severity")
        if isinstance(sev, int):
            # findings-v2: an integer on the 1-9 ladder, matchable by slug
            # OR finding_id; a provisional final severity still scores (the
            # fixture's interval is about the finding, not the adjudicator).
            value: object = sev
        elif sev is None and isinstance(f.get("provisional_severity"), int):
            value = f["provisional_severity"]
        elif f.get("id"):
            severity_of[f["id"]] = normalize_severity(sev)
            continue
        else:
            continue
        for key in (f.get("slug"), f.get("finding_id"), f.get("id")):
            if key:
                severity_of[key] = value

    by_id = {row["id"]: row for row in parsed.get("per_finding", [])}
    per_finding = []
    achieved = 0.0
    possible = 0.0
    possible_reachable = 0.0
    achieved_reachable = 0.0
    n_scored = n_in = n_over = n_under = n_unmatched = n_excluded = 0
    bias = 0.0
    for kf in fixture["key_findings"]:
        weight = WEIGHTS.get(kf["weight"], 1)
        row = by_id.get(kf["id"], {"covered": False})
        covered = bool(row.get("covered"))
        reachable = kf.get("reachable", True)
        possible += weight
        achieved += weight if covered else 0
        if reachable:
            possible_reachable += weight
            achieved_reachable += weight if covered else 0
        entry = {
            "id": kf["id"],
            "weight": kf["weight"],
            "reachable": reachable,
            "covered": covered,
            "evidence_quote": row.get("evidence_quote", ""),
        }

        interval = kf.get("severity_expected")
        confidence = kf.get("confidence", "high")
        if interval:
            entry["severity_expected"] = list(interval)
            entry["confidence"] = confidence
            matched_id = row.get("matched_finding_id") or ""
            matched_sev = severity_of.get(matched_id)
            if covered and matched_sev is not None:
                entry["matched_finding_id"] = matched_id
                entry["matched_severity"] = matched_sev
                if all(isinstance(x, int) for x in interval) \
                        and isinstance(matched_sev, int):
                    # Fixture format v2: 1-9 integer interval against a
                    # findings-v2 integer severity -- the same direction
                    # arithmetic, on the real ladder (bias becomes linear).
                    lo, hi = min(interval), max(interval)
                    got = matched_sev
                elif all(isinstance(x, int) for x in interval) \
                        or isinstance(matched_sev, int):
                    # Mixed eras cannot be compared; say so, never guess.
                    lo = hi = got = None
                else:
                    ranks = [_SEV_RANK[normalize_severity(s)]
                             for s in interval]
                    lo, hi = min(ranks), max(ranks)
                    got = _SEV_RANK[matched_sev]
                if got is None:
                    direction = "incomparable_eras"
                else:
                    direction = ("in" if lo <= got <= hi
                                 else "over" if got > hi else "under")
                entry["severity_in_interval"] = direction == "in"
                entry["severity_direction"] = direction
                if confidence == "low" or got is None:
                    n_excluded += 1        # reported, never aggregated
                else:
                    n_scored += 1
                    n_in += direction == "in"
                    n_over += direction == "over"
                    n_under += direction == "under"
                    bias += got - (lo + hi) / 2.0
            elif covered and kf.get("allow_undecided") \
                    and matched_id in known_ids:
                # The label says undecided is a legitimate landing, and the
                # judge matched a REAL finding that carries no severity
                # (findings-v2 outcome: undecided). Allowed, excluded from
                # the aggregates -- distinct from matching nothing at all.
                entry["matched_finding_id"] = matched_id
                entry["severity_in_interval"] = None
                entry["severity_direction"] = "undecided_allowed"
                n_excluded += 1
            elif covered:
                # Covered in prose but matched to no structured finding: the
                # interval cannot be scored, and saying so beats guessing.
                entry["severity_in_interval"] = None
                n_unmatched += 1
        per_finding.append(entry)

    false_positives = parsed.get("false_positives", [])
    return {
        "per_finding": per_finding,
        "false_positives": false_positives,
        "recall_weighted": round(achieved / possible, 3) if possible else None,
        "recall_weighted_reachable": (
            round(achieved_reachable / possible_reachable, 3)
            if possible_reachable else None
        ),
        "num_false_positives": len(false_positives),
        # A judge pass on an empty sweep is not a pass; upstream starvation
        # must be visible in the scorecard, not masked by coverage arithmetic.
        "no_findings_produced": not findings_list,
        "severity_calibration": {
            "n_scored": n_scored,
            "n_in_interval": n_in,
            # Directional on purpose: severity ABOVE the interval is an
            # over-accusation, BELOW is a miss — different failures. The
            # signed bias (positive = systematically more severe than the
            # labels, negative = systematic hedging) is the drift detector.
            "n_over_severity": n_over,
            "n_under_severity": n_under,
            "severity_bias": round(bias, 3),
            "n_excluded_low_confidence": n_excluded,
            "n_covered_but_unmatched": n_unmatched,
        },
        "judge_notes": parsed.get("notes", ""),
        # A JUDGE THAT SAID NOTHING IS NOT A ZERO. Measured 2026-10-13: a
        # Grok judge returned no coverage and empty notes for a review that
        # filed 26 findings, and the scorecard read recall 0.0; Sonnet graded
        # the same review 0.462. Every expected finding uncovered, no notes,
        # and findings present is the signature; the run says so instead of
        # passing a grader's silence off as a measurement.
        "judge_degenerate": bool(
            findings_list and not str(parsed.get("notes") or "").strip()
            and not any(r.get("covered") for r in per_finding)),
    }
