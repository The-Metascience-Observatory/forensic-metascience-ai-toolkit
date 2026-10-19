"""Issue-localized scorecards and human-review queues for frozen runs."""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path

from .storage import atomic_json, file_hash, read_jsonl

SUPPORTED = {"row_pair", "column_sequence", "repeated_value"}


def cells(group):
    return group.get("cells", []) + group.get("cells_a", []) + group.get("cells_b", [])


def matches(group, issue):
    """A hit must cover the annotated cells; another flag in the paper is not a hit."""
    if group.get("kind") not in issue.get("detector_kinds", [issue["kind"]]):
        return False
    expected = issue.get("cells", [])
    if not expected:
        return False
    actual = cells(group)
    return all(
        any(
            all(
                ref.get(k) == wanted[k]
                for k in ("file", "sheet", "cell", "source_sha256")
                if k in wanted
            )
            for ref in actual
        )
        for wanted in expected
    )


def ratio(numerator, denominator):
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def score(labels, run_index, output, *, reviews=None, seed=20260910):
    gold = read_jsonl(labels)
    if len({g["paper_id"] for g in gold}) != len(gold):
        raise ValueError("Labels must contain one record per paper/version")
    index_path = Path(run_index)
    index = json.loads(index_path.read_text())
    runs = {r["paper_id"]: r for r in index["runs"]}
    details, queue, unflagged = [], [], []
    reviewed = read_jsonl(reviews) if reviews else []
    review_map = {(r["run_id"], r["candidate_id"]): r for r in reviewed}
    positives = hit = retained = evaluable = supported = supported_hit = 0
    verified_negatives = negative_clear = complete_negatives = 0
    flagged_reviewed = true_reviewed = 0
    kept_reviewed = true_kept_reviewed = 0
    evaluated_papers = flagged_papers = 0
    ai_requested = decided_candidates = retained_candidates = 0
    file_states = Counter()
    for label in gold:
        run = runs.get(label["paper_id"])
        record = {
            "paper_id": label["paper_id"],
            "split": label.get("split", "unassigned"),
            "issues": [],
            "status": "not_run",
        }
        result, judgments = {}, {}
        if run:
            folder = index_path.parent / run["directory"]
            try:
                meta = json.loads((folder / "manifest.json").read_text())
                for name in ("result.json", "adjudication.json"):
                    if file_hash(folder / name) != meta["artifacts"][name]["sha256"]:
                        raise ValueError("Run artifact hash mismatch")
                result = json.loads((folder / "result.json").read_text())
                adjudication = json.loads((folder / "adjudication.json").read_text())
                ai_requested += adjudication.get("status") != "not_requested"
                judgments = {
                    d["candidate_id"]: d
                    for d in json.loads((folder / "adjudication.json").read_text()).get(
                        "decisions", []
                    )
                }
                expected_hashes = label.get("source_sha256", {})
                actual_hashes = {s["file"]: s.get("sha256") for s in result.get("sources", [])}
                mismatches = {
                    name for name, sha in expected_hashes.items() if actual_hashes.get(name) != sha
                }
                record["status"] = (
                    "version_mismatch"
                    if mismatches
                    else result.get("coverage", {}).get("status", "not_evaluable")
                )
                if mismatches:
                    result = {}
            except (OSError, ValueError, KeyError) as exc:
                record.update(status="unavailable", error=str(exc))
        available = record["status"] in {"complete", "partial"}
        groups = result.get("duplicate_groups", []) if available else []
        actionable = [g for g in groups if g["severity"] in {"suspicious", "highly_suspicious"}]
        file_states.update(s["status"] for s in result.get("sources", []) if "status" in s)
        if available:
            evaluated_papers += 1
            flagged_papers += bool(actionable)
            if not actionable and record["status"] == "complete":
                unflagged.append(
                    {
                        "paper_id": label["paper_id"],
                        "run_id": run["run_id"],
                        "reason": "unflagged_sample",
                    }
                )
        if label.get("verification_status") == "verified_negative":
            verified_negatives += 1
            complete_negatives += record["status"] == "complete"
            negative_clear += record["status"] == "complete" and not actionable
        for g in groups:
            decision = judgments.get(g["id"], {}).get("decision")
            decided_candidates += decision in {"retain", "exclude"}
            retained_candidates += decision == "retain" and g["severity"] in {
                "suspicious",
                "highly_suspicious",
            }
            queue.append(
                {
                    "paper_id": label["paper_id"],
                    "run_id": run["run_id"],
                    "candidate_id": g["id"],
                    "severity": g["severity"],
                    "ai_decision": judgments.get(g["id"], {}).get("decision", "unreviewed"),
                    "reason": "flagged_candidate",
                    "review": run.get("review"),
                }
            )
            human = review_map.get((run["run_id"], g["id"]))
            if human and human.get("label") in {"confirmed_error", "legitimate_repetition"}:
                flagged_reviewed += 1
                true_reviewed += human["label"] == "confirmed_error"
                if decision == "retain" and g["severity"] in {"suspicious", "highly_suspicious"}:
                    kept_reviewed += 1
                    true_kept_reviewed += human["label"] == "confirmed_error"
        for issue in label.get("issues", []):
            verified = issue.get("verification_status") in {
                "confirmed_error",
                "verified_duplication",
            }
            # Verified labels require pinned bytes and localized source evidence.
            if verified and (
                not label.get("source_sha256")
                or not issue.get("cells")
                or not issue.get("evidence_url")
            ):
                raise ValueError(
                    f"{label['paper_id']}: verified issue needs source hashes, cells and evidence_url"
                )
            found = [g for g in groups if matches(g, issue)]
            keep = [
                g
                for g in found
                if judgments.get(g["id"], {}).get("decision") == "retain"
                and g["severity"] in {"suspicious", "highly_suspicious"}
            ]
            in_scope = issue["kind"] in SUPPORTED
            state = (
                "unverified"
                if not verified
                else "source_unavailable"
                if not available
                else "unsupported_issue_type"
                if not in_scope
                else "retained"
                if keep
                else "candidate_only"
                if found
                else "missed"
            )
            record["issues"].append(
                {
                    "id": issue["id"],
                    "kind": issue["kind"],
                    "state": state,
                    "candidate_ids": [g["id"] for g in found],
                    "retained_ids": [g["id"] for g in keep],
                }
            )
            if verified:
                positives += 1
                evaluable += available
                hit += bool(found)
                retained += bool(keep)
                supported += available and in_scope
                supported_hit += bool(found) and in_scope
        details.append(record)
    rng = random.Random(seed)
    selected = rng.sample(sorted(unflagged, key=lambda r: r["paper_id"]), min(20, len(unflagged)))
    report = {
        "labels_sha256": file_hash(labels),
        "run_index_sha256": file_hash(run_index),
        "seed": seed,
        "papers_requested": len(gold),
        "papers_evaluable": evaluated_papers,
        "verified_issues": positives,
        "verified_issues_with_available_sources": evaluable,
        "candidate_recall_all_verified": ratio(hit, positives),
        "candidate_recall_available_supported": ratio(supported_hit, supported),
        "retained_recall_all_verified": ratio(retained, positives if ai_requested else 0),
        "ai_requested_papers": ai_requested,
        "ai_retention_of_definite_candidates": ratio(retained_candidates, decided_candidates),
        "acquisition_file_states": dict(file_states),
        "reviewed_candidate_precision": ratio(true_reviewed, flagged_reviewed),
        "reviewed_retained_precision": ratio(true_kept_reviewed, kept_reviewed),
        "specificity_complete_verified_negatives": ratio(negative_clear, complete_negatives),
        "verified_negative_papers_requested": verified_negatives,
        "flag_rate_evaluable_papers": ratio(flagged_papers, evaluated_papers),
        "candidate_review_burden": len(queue),
        "unflagged_review_sample": selected,
        "papers": details,
    }
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    atomic_json(out / "scorecard.json", report)
    (out / "review_queue.jsonl").write_text("".join(json.dumps(r) + "\n" for r in queue + selected))
    lines = [
        "# Copy-paste scorecard",
        "",
        "Missing measurements are unavailable, not zero. Recall is issue-localized; a different flag in the same paper is not a hit.",
        "",
    ]
    for key, value in report.items():
        if isinstance(value, dict) and "denominator" in value:
            lines.append(
                f"- {key}: {value['numerator']} / {value['denominator']}"
                + (" (unavailable)" if value["value"] is None else f" = {value['value']:.3f}")
            )
    lines += [
        "",
        f"Candidate reviews queued: {len(queue)}. Random unflagged papers queued: {len(selected)}.",
        "",
    ]
    for paper in details:
        lines.append(
            f"- {paper['paper_id']}: {paper['status']}; "
            + ", ".join(f"{i['id']}: {i['state']}" for i in paper["issues"])
        )
    (out / "scorecard.md").write_text("\n".join(lines))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--run-index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reviews", type=Path)
    parser.add_argument("--seed", type=int, default=20260910)
    args = parser.parse_args(argv)
    result = score(args.labels, args.run_index, args.output, reviews=args.reviews, seed=args.seed)
    print(
        json.dumps(
            {k: v for k, v in result.items() if k not in {"papers", "unflagged_review_sample"}},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
