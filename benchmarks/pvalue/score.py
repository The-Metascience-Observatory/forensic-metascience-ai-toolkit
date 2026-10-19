"""Score reviews against the p-value-error ground truth, statistic by statistic.

Ground truth: `labels_*.jsonl`, one row per documented erroneous statistic in the
statcheck_pvalue_errors corpus (see that corpus's README and manifest.csv for the
evidence behind each). Three numbers per labelled statistic, as in
benchmarks/grim/score.py, because they come apart:

  checked   a p-value tool call (statcheck, recalc_*, check_estimate_ci,
            reconstruct_2x2) had the statistic's value in its arguments or,
            for statcheck, among the statistics it extracted
  flagged   such a call came back inconsistent: an accusing severity, or a
            statcheck row with `error: true` for that value
  reported  a finding in findings.v2.json that the adjudicator did not
            discard prints every key group of the label (title, description,
            quote, location). `dismissed` counts a matching finding that WAS
            discarded: the system saw the error and threw it away.

A label's `keys` is a list of groups; each group is a list of alternatives,
and every group must match within WINDOW characters of the first. Numbers match with or without a leading zero and
sign ("0.049" ~ ".049", "-1.64" ~ "−1.64").

The papers carry at least the documented error, not only it: a finding that
matches no label is UNMATCHED, which is not the same as a false positive.
Unmatched findings are listed for a human (or a recompute) to audit.

    python benchmarks/pvalue/score.py --labels benchmarks/pvalue/labels_working_set.jsonl \
        --papers-root CORPUS/working_set --review 'forensic_review_sonnet*' [--json OUT]
"""

from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

P_TOOLS = frozenset({"statcheck", "recalc_stat_to_p", "recalc_f_to_p", "recalc_anova",
                     "recalc_independent_t", "recalc_within_subjects_t", "recalc_chi_squared",
                     "check_estimate_ci", "reconstruct_2x2", "absence_of_evidence"})
ACCUSING = frozenset({"suspicious", "highly_suspicious", "impossible"})
DROPPED_ACTIONS = frozenset({"discarded"})
#: a merged finding lives on in the finding it was merged into: not a separate final finding
MERGED_ACTIONS = frozenset({"merged"})
#: `notes` is left out on purpose: it holds hand-offs and side remarks ("also F = 11.01 is borderline")
#: inside a finding about another statistic, which is not a report of that statistic
TEXT_FIELDS = ("title", "description", "quote", "location", "slug", "claim")


def _short(tool: str) -> str:
    return tool.rsplit("__", 1)[-1]


def _norm(text: str) -> str:
    return (text.replace("−", "-").replace("–", "-").replace(" ", " ")
            .replace(" ", " ").lower())


def _key_pattern(key: str) -> re.Pattern:
    """A number matches with or without its leading zero or sign; a word matches as a substring."""
    k = _norm(key)
    m = re.fullmatch(r"([<>]?\s*)-?0?(\.\d+)|([<>]?\s*)-?(\d+(?:\.\d+)?)", k)
    if not m:
        return re.compile(re.escape(k))
    if m.group(2):  # decimal below 1: ".049" or "0.049"
        prefix = re.escape(m.group(1).strip())
        body = r"0?" + re.escape(m.group(2))
    else:
        prefix = re.escape(m.group(3).strip())
        body = re.escape(m.group(4))
    if prefix:
        prefix += r"\s*"
    return re.compile(prefix + r"(?<![\d.])-?" + body + (r"0*" if "." in body else "") + r"(?!\d)")


#: every key group must match within this many characters of the first group's match, so a
#: finding about ANOTHER statistic that happens to quote these numbers elsewhere does not count
WINDOW = 150


def _matches(text: str, keys: list[list[str]]) -> bool:
    t = _norm(text)
    spots = [[m.start() for alt in group for m in _key_pattern(alt).finditer(t)] for group in keys]
    if not all(spots):
        return False
    return any(all(any(abs(q - p) <= WINDOW for q in other) for other in spots[1:]) for p in spots[0])


def find_review(paper_dir: Path, glob: str) -> Path | None:
    best, best_at = None, ""
    for d in paper_dir.glob(glob):
        meta = d / "run_meta.json"
        if not meta.exists():
            continue
        try:
            at = json.loads(meta.read_text()).get("analysed_at") or ""
        except ValueError:
            at = ""
        if best is None or at > best_at:
            best, best_at = d, at
    return best


def _findings(review: Path) -> list[dict]:
    try:
        doc = json.loads((review / "findings.v2.json").read_text())
    except (OSError, ValueError):
        return []
    return doc.get("findings") or []


def _finding_text(f: dict) -> str:
    return " ".join(str(f.get(k) or "") for k in TEXT_FIELDS)


def _dropped(f: dict) -> bool:
    return (f.get("adjudication") or {}).get("action") in DROPPED_ACTIONS


def _receipt_severities(review: Path, stage: str) -> dict[str, list[str]]:
    """Per tool, the severity of each call in order, from receipts.<stage>.jsonl.

    The ledger truncates long results (result_truncated), which can cut the
    severity field off; the receipt keeps it. Joined by stage, tool and position.
    """
    out: dict[str, list[str]] = collections.defaultdict(list)
    path = review / f"receipts.{stage}.jsonl"
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        out[_short(r.get("tool") or "")].append(str(r.get("severity") or "").lower())
    return out


def _final_severity(f: dict, by_id: dict):
    adj = f.get("adjudication") or {}
    if adj.get("action") in MERGED_ACTIONS and adj.get("merged_into") in by_id:
        return by_id[adj["merged_into"]].get("severity")
    return f.get("severity") if f.get("severity") is not None else f.get("provisional_severity")


def _survives(f: dict, by_id: dict, depth: int = 0) -> bool:
    """Not discarded; a merged finding survives if the finding it was merged into does."""
    adj = f.get("adjudication") or {}
    if adj.get("action") in DROPPED_ACTIONS:
        return False
    if adj.get("action") in MERGED_ACTIONS:
        target = by_id.get(adj.get("merged_into"))
        return target is not None and depth < 5 and _survives(target, by_id, depth + 1)
    return True


def _calls(review: Path) -> list[dict]:
    out = []
    for path in sorted(review.glob("toolcalls.*.json")):
        stage = path.name[len("toolcalls."):-len(".json")]
        receipts = _receipt_severities(review, stage)
        seen: collections.Counter = collections.Counter()
        try:
            ledger = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        for call in ledger if isinstance(ledger, list) else []:
            tool = _short(call.get("tool_short") or call.get("tool") or call.get("name") or "")
            if tool not in P_TOOLS:
                continue
            raw = call.get("result")
            try:
                result = json.loads(raw) if isinstance(raw, str) else (raw or {})
            except ValueError:
                result = {"_text": raw}
            if not isinstance(result, dict):
                result = {"_text": str(result)}
            i = seen[tool]
            seen[tool] += 1
            if not result.get("severity") and i < len(receipts.get(tool, [])):
                result["severity"] = receipts[tool][i]
            args = call.get("args") or call.get("input") or call.get("arguments") or {}
            out.append({"tool": tool, "stage": stage, "args": json.dumps(args) if not isinstance(args, str) else args,
                        "result": result})
    return out


def _value_re(value: str) -> re.Pattern:
    return _key_pattern(value)


def _call_hits(call: dict, label: dict) -> tuple[bool, bool]:
    """(checked, flagged) for one call against one label."""
    vre = _value_re(label["value"])
    res = call["result"] if isinstance(call["result"], dict) else {}
    if call["tool"] == "statcheck":
        checked = flagged = False
        rows = res.get("statistics") or []
        if not rows and "_text" in res:  # truncated ledger result: recover the rows present
            rows = [{"raw": m.group(1), "error": m.group(2) == "true"} for m in
                    re.finditer(r'"raw":\s*"([^"]*)".*?"error":\s*(true|false)', str(res["_text"]), re.S)]
        for s in rows:
            if vre.search(_norm(str(s.get("raw", "")))):
                checked = True
                flagged = flagged or bool(s.get("error"))
        return checked, flagged
    checked = bool(vre.search(_norm(call["args"])))
    severity = str(res.get("severity", "")).lower()
    if not severity and "_text" in res:  # result truncated in the ledger: read the field from text
        m = re.search(r"'severity':\s*'(\w+)'|\"severity\":\s*\"(\w+)\"", str(res["_text"]))
        severity = (m.group(1) or m.group(2)).lower() if m else ""
    flagged = checked and severity in ACCUSING
    return checked, flagged


def score(labels: list[dict], root: Path, glob: str, producer: str | None = None) -> dict:
    by_paper = collections.defaultdict(list)
    for lab in labels:
        by_paper[lab["paper_id"]].append(lab)
    rows, papers, all_findings = [], [], []
    for pid, labs in sorted(by_paper.items()):
        review = find_review(root / pid, glob)
        if review is None:
            papers.append({"paper_id": pid, "review": None})
            for lab in labs:
                rows.append({**lab, "review": None, "checked": False, "flagged": False,
                             "reported": False, "dismissed": False, "severity": None})
            continue
        meta = json.loads((review / "run_meta.json").read_text())
        findings = _findings(review)
        by_id = {f.get("finding_id"): f for f in findings}
        if producer:  # e.g. only the tools agent's findings from a full-pipeline run
            findings = [f for f in findings if f.get("producer") == producer]
        calls = _calls(review)
        matched_ids = set()
        for lab in labs:
            hits = [_call_hits(c, lab) for c in calls]
            # only a PROBLEM finding reports an error: a `pass` that prints the same numbers
            # says the opposite, and `undecided` declined to say
            rep = [f for f in findings if f.get("outcome") == "problem" and _matches(_finding_text(f), lab["keys"])]
            kept = [f for f in rep if _survives(f, by_id)]
            matched_ids.update(f.get("finding_id") for f in rep)
            rows.append({**lab, "review": review.name,
                         "checked": any(h[0] for h in hits), "flagged": any(h[1] for h in hits),
                         "reported": bool(kept), "dismissed": bool(rep) and not kept,
                         "n_reporting": len([f for f in kept if (f.get("adjudication") or {}).get("action")
                                             not in MERGED_ACTIONS and not f.get("duplicate_of")]),
                         "severity": max((_final_severity(f, by_id) or 0 for f in kept), default=None),
                         "finding_titles": [f.get("title") for f in rep]})
        for f in findings:
            all_findings.append({"paper_id": pid, "finding_id": f.get("finding_id"),
                                 "producer": f.get("producer"), "technique": f.get("technique"),
                                 "severity": f.get("severity"), "outcome": f.get("outcome"),
                                 "dropped": _dropped(f), "quarantined": bool(f.get("quarantined")),
                                 "action": (f.get("adjudication") or {}).get("action"),
                                 "duplicate_of": f.get("duplicate_of"),
                                 "matched": f.get("finding_id") in matched_ids,
                                 "title": f.get("title")})
        papers.append({"paper_id": pid, "review": review.name,
                       "cost_usd": meta.get("total_cost_usd") or meta.get("cost_usd"),
                       "is_error": meta.get("is_error"), "model": meta.get("model"),
                       "n_findings": len(findings)})
    return {"labels": rows, "papers": papers, "findings": all_findings}


def summarise(res: dict) -> dict:
    rows = res["labels"]

    def tally(group):
        n = len(group)
        return {k: sum(r[k] for r in group) for k in ("checked", "flagged", "reported", "dismissed")} | {"n": n}

    by_paper = collections.defaultdict(list)
    for r in rows:
        by_paper[r["paper_id"]].append(r)
    paper_found = sum(any(r["reported"] for r in g) for g in by_paper.values())
    allf = res["findings"]
    # FINAL findings: problems the adjudicator neither discarded nor merged into another finding
    # FINAL findings: problems the adjudicator neither discarded nor merged into another
    # finding, that are not a deduplicated copy and are not quarantined (a quarantined
    # row never reaches the headline, so counting it would overstate what a reader sees).
    final = [f for f in allf if f["outcome"] == "problem" and not f["dropped"]
             and f["action"] not in MERGED_ACTIONS and not f.get("duplicate_of")
             and not f["quarantined"]]
    sev = collections.Counter(f["severity"] for f in final)
    accusing = [f for f in final if (f["severity"] or 0) >= 3]
    return {
        "statistics": tally(rows),
        "by_tier": {t: tally([r for r in rows if r["tier"] == t]) for t in sorted({r["tier"] for r in rows})},
        "by_kind": {k: tally([r for r in rows if r["kind"] == k]) for k in sorted({r["kind"] for r in rows})},
        "papers": {"n": len(by_paper), "with_review": sum(p["review"] is not None for p in res["papers"]),
                   "error_reported": paper_found},
        "findings": {"total": len(allf),
                     "by_outcome": dict(collections.Counter(f["outcome"] for f in allf)),
                     "by_action": dict(collections.Counter(f["action"] for f in allf)),
                     "final": len(final),
                     "final_per_paper": round(len(final) / max(1, sum(p["review"] is not None for p in res["papers"])), 1),
                     "final_matched": sum(f["matched"] for f in final),
                     "final_unmatched": sum(not f["matched"] for f in final),
                     "final_by_severity": dict(sorted(sev.items(), key=lambda kv: (kv[0] is None, kv[0] or 0))),
                     "final_by_producer": dict(collections.Counter(f["producer"] for f in final)),
                     # severity >= 3 is the ladder's accusatory floor (severity9.ACCUSATORY_MIN)
                     "final_sev3plus": len(accusing),
                     "final_sev3plus_unmatched": sum(not f["matched"] for f in accusing),
                     "quarantined": sum(f["quarantined"] for f in allf),
                     "deduplicated": sum(bool(f.get("duplicate_of")) for f in allf)},
        # labels a tool flagged that no surviving finding reports: the tool saw it, the
        # agent did not file it
        "flagged_not_reported": [r["id"] for r in rows if r["flagged"] and not r["reported"]],
        # the same known error filed more than once (no adjudicator to merge them)
        "duplicate_reports": sum(max(0, r.get("n_reporting", 0) - 1) for r in rows),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--labels", type=Path, required=True)
    ap.add_argument("--papers-root", type=Path, required=True)
    ap.add_argument("--review", required=True, help="glob for the review dir inside each paper dir")
    ap.add_argument("--producer", help="score only findings from this producer (e.g. tool_expert)")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--list", action="store_true", help="print every label and unmatched finding")
    a = ap.parse_args(argv)
    labels = [json.loads(line) for line in a.labels.read_text().splitlines() if line.strip()]
    res = score(labels, a.papers_root, a.review, a.producer)
    summ = summarise(res)
    s = summ["statistics"]
    who = f" [producer {a.producer}]" if a.producer else ""
    print(f"{a.review}{who}: {summ['papers']['with_review']}/{summ['papers']['n']} papers have a review")
    print(f"  statistics: reported {s['reported']}/{s['n']}  flagged {s['flagged']}/{s['n']}  "
          f"checked {s['checked']}/{s['n']}  dismissed {s['dismissed']}")
    for name, group in (("tier", summ["by_tier"]), ("kind", summ["by_kind"])):
        for k, t in group.items():
            print(f"    {name} {k:7} reported {t['reported']}/{t['n']}  flagged {t['flagged']}/{t['n']}")
    print(f"  papers with >=1 known error reported: {summ['papers']['error_reported']}/{summ['papers']['n']}")
    f = summ["findings"]
    print(f"  findings: {f['total']} filed; outcomes {f['by_outcome']}; adjudication {f['by_action']}")
    print(f"  FINAL problem findings: {f['final']} ({f['final_per_paper']}/paper); matching a known error "
          f"{f['final_matched']}, unmatched {f['final_unmatched']}")
    print(f"  final by severity: {f['final_by_severity']}")
    print(f"  final by producer: {f['final_by_producer']}")
    print(f"  final at severity >= 3: {f['final_sev3plus']} (unmatched {f['final_sev3plus_unmatched']}); "
          f"quarantined {f['quarantined']}, deduplicated {f['deduplicated']}")
    print(f"  known errors filed more than once: {summ['duplicate_reports']} extra; "
          f"flagged by a tool but not reported: {summ['flagged_not_reported']}")
    if a.list:
        for r in res["labels"]:
            mark = "R" if r["reported"] else ("D" if r["dismissed"] else ("F" if r["flagged"] else ("C" if r["checked"] else "-")))
            print(f"  [{mark}] {r['id']:16} {r['raw'][:60]:60} sev={r.get('severity')}")
            for t in r.get("finding_titles") or []:
                print(f"         - {t[:110]}")
    if a.json:
        a.json.write_text(json.dumps({"summary": summ, **res}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
