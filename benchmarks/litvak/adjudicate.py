#!/usr/bin/env python3
"""Read every finding against every planted error, per paper, with an agent.

    python benchmarks/litvak/adjudicate.py /mnt/c/Users/gregs/fmt-litvak/modified \
        --out /mnt/c/Users/gregs/fmt-litvak/ADJUDICATION_FULL.md

WHY THIS REPLACES THE STRING MATCHER. Dan Elton, 2026-08-23: "the agent should
go through the findings for each paper ... For each of the findings in a paper,
it should match if any match the true 10 errors ... Then there should be a
detailed report on all 100. Each error that Litvak inserted should be fully
described as it is described by litvak, along with the classification/category
/type for that error. Then the matching finding should be printed below it. That
way a human can spot check also and understand things better."

He is right, and the reason is measurable. `score.py` matches on two string
rules and they fail in opposite directions: `quote` needs 60 verbatim characters
and misses every paraphrase; `numbers` is a subset test with no notion of what
the numbers MEAN, and it credited a finding about Study 1 effect sizes
RECONCILING against an error planted in Study 3. Hand-checking 20 of them took
12 automatic matches down to 9 real ones.

Thirty findings per paper is nothing for a model to read. Semantic judgement is
the right instrument, and printing the pairing underneath each error is what
makes the result auditable rather than asserted.

SCOPED PER PAPER, which the string matcher was not: it pooled all ten papers'
findings, so a finding about paper 3 could be credited against an error planted
in paper 7. Four matches were cross-paper -- 35 of 100 unscoped, 31 scoped.

THE ADJUDICATOR IS TOLD TO PREFER "no". A benchmark that flatters itself is
worth nothing, and the failure mode here is generous matching, not stinginess.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

BENCH = Path("/mnt/c/Users/gregs/ai-peer-review-benchmark")

PROMPT = """You are adjudicating a benchmark. Be strict; a benchmark that \
flatters itself is worthless.

Below are {n_err} errors that were deliberately planted into one paper, and \
{n_find} findings that an automated reviewer produced for that same paper.

For EACH planted error, decide whether ANY finding actually identifies it.

A finding matches only if it identifies THE SAME PROBLEM the planted error \
describes. It is NOT a match when it merely mentions the same numbers, the same \
table, or the same section. Example of a NON-match seen in this benchmark: a \
finding reporting that Study 1's effect sizes RECONCILE with their intervals \
was credited against an error planted in Study 3 -- same numerals, opposite \
meaning, not a match.

Return ONLY a JSON array, one object per planted error, in the order given:

[{{"error_index": 0, "matched": true|false, "finding_index": <int or null>,
   "confidence": "high"|"medium"|"low",
   "reason": "<one sentence: why it matches, or what the closest finding got \
instead>"}}]

=== PLANTED ERRORS ===
{errors}

=== FINDINGS PRODUCED BY THE REVIEWER ===
{findings}
"""


def _rows() -> list[dict]:
    with open(BENCH / "error_insertions.csv", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _findings_for(paper_dir: Path) -> list[dict]:
    out: list[dict] = []
    for name in ("findings.v2.json", "findings.json"):
        for fp in paper_dir.rglob(name):
            try:
                doc = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            items = doc.get("findings") if isinstance(doc, dict) else doc
            if isinstance(items, list):
                out.extend(x for x in items if isinstance(x, dict))
    return out


def _finding_text(f: dict, limit: int = 700) -> str:
    parts = []
    for k in ("title", "summary", "description", "quote", "consequence", "basis"):
        v = str(f.get(k) or "").strip()
        if v and v not in parts:
            parts.append(v)
    return " | ".join(parts)[:limit]


def _ask(prompt: str, model: str, timeout: int) -> list[dict] | None:
    """One `claude -p` call. Returns the parsed array, or None on any failure.

    None is a REFUSAL, not an empty result: a paper whose adjudication failed
    must not be silently scored as zero matches.
    """
    try:
        r = subprocess.run(["claude", "-p", prompt, "--model", model],
                           capture_output=True, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    txt = (r.stdout or "").strip()
    m = re.search(r"\[.*\]", txt, re.S)
    if not m:
        return None
    try:
        got = json.loads(m.group(0))
        return got if isinstance(got, list) else None
    except json.JSONDecodeError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--only", type=int, default=None, help="one paper, for a dry run")
    a = ap.parse_args()

    rows = _rows()
    papers = sorted({int(r["paper"]) for r in rows})
    if a.only:
        papers = [a.only]

    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True,
                            cwd=Path(__file__).resolve().parents[2]).stdout.strip()

    results: dict[int, list[dict]] = {}
    findings_by_paper: dict[int, list[dict]] = {}
    failed: list[int] = []

    for pno in papers:
        errs = [r for r in rows if int(r["paper"]) == pno]
        pdir = a.run_dir / ("litvak%02d" % pno)
        fs = _findings_for(pdir)
        findings_by_paper[pno] = fs
        if not fs:
            failed.append(pno)
            print("  paper %2d: NO FINDINGS -- not scored" % pno, flush=True)
            continue
        etxt = "\n".join(
            "[%d] category=%s subcategory=%s difficulty=%s\n"
            "     description: %s\n     text as planted: %s"
            % (i, e["category"], e["subcategory"], e["difficulty"],
               e["description"][:400], (e["modified_snippet"] or "")[:300])
            for i, e in enumerate(errs))
        ftxt = "\n".join("[%d] %s" % (i, _finding_text(f))
                         for i, f in enumerate(fs))
        got = _ask(PROMPT.format(n_err=len(errs), n_find=len(fs),
                                 errors=etxt, findings=ftxt),
                   a.model, a.timeout)
        if got is None:
            failed.append(pno)
            print("  paper %2d: ADJUDICATION FAILED -- not scored" % pno, flush=True)
            continue
        results[pno] = got
        hits = sum(1 for g in got if g.get("matched"))
        print("  paper %2d: %2d of %d matched  (%d findings read)"
              % (pno, hits, len(errs), len(fs)), flush=True)

    # ---- the report Dan asked for: all 100, fully described, pairing below ----
    L: list[str] = []
    L.append("# Litvak benchmark — full adjudication, all 100 planted errors\n")
    L.append("Adjudicated per paper by an agent reading every finding against that "
             "paper's ten planted errors, replacing the string matcher in "
             "`score.py`. Each error is stated as Litvak describes it, with its "
             "category, and the matching finding printed beneath so a human can "
             "spot-check.\n")
    L.append("| | |\n|---|---|")
    L.append("| run | `%s` |" % a.run_dir)
    L.append("| FMT commit | `%s` |" % (commit or "unknown"))
    L.append("| adjudicator | `claude -p --model %s` |" % a.model)
    scored = [p for p in papers if p in results]
    total = sum(1 for p in scored for g in results[p] if g.get("matched"))
    denom = sum(1 for r in rows if int(r["paper"]) in scored)
    L.append("| papers scored | %d of %d |" % (len(scored), len(papers)))
    if failed:
        L.append("| **NOT SCORED** | papers %s — counted in no denominator |"
                 % ", ".join(str(x) for x in failed))
    L.append("| **matched** | **%d of %d** |\n" % (total, denom))

    by_cat: dict[str, list[int]] = {}
    for p in scored:
        errs = [r for r in rows if int(r["paper"]) == p]
        for g, e in zip(results[p], errs):
            c = by_cat.setdefault(e["category"], [0, 0])
            c[1] += 1
            if g.get("matched"):
                c[0] += 1
    L.append("## By category\n")
    L.append("| category | matched | of |\n|---|---|---|")
    for c, (h, n) in sorted(by_cat.items(), key=lambda kv: -kv[1][0]):
        L.append("| `%s` | %d | %d |" % (c, h, n))
    L.append("")

    for p in papers:
        errs = [r for r in rows if int(r["paper"]) == p]
        L.append("\n---\n\n## Paper %d\n" % p)
        if p not in results:
            L.append("**Not scored** — %s. Its ten errors are excluded from every "
                     "figure above rather than counted as misses.\n"
                     % ("no findings found" if not findings_by_paper.get(p)
                        else "adjudication failed"))
            continue
        fs = findings_by_paper[p]
        for i, e in enumerate(errs):
            g = results[p][i] if i < len(results[p]) else {}
            ok = g.get("matched")
            L.append("### %d.%d `%s` — %s" % (p, i + 1, e["category"],
                                              e["subcategory"]))
            L.append("**%s** · difficulty %s\n" % (
                "MATCHED" if ok else "MISSED", e["difficulty"]))
            L.append("> **As Litvak describes it:** %s\n" % e["description"])
            if e.get("original_snippet"):
                L.append("- original: `%s`" % e["original_snippet"][:220].replace("\n", " "))
            L.append("- as planted: `%s`\n" % (e["modified_snippet"] or "")[:220].replace("\n", " "))
            fi = g.get("finding_index")
            if ok and isinstance(fi, int) and 0 <= fi < len(fs):
                L.append("**Matching finding** (confidence: %s)\n"
                         % g.get("confidence", "?"))
                L.append("> %s\n" % _finding_text(fs[fi], 900).replace("\n", " "))
            L.append("*Adjudicator:* %s\n" % g.get("reason", "—"))

    a.out.write_text("\n".join(L), encoding="utf-8")
    print("\nmatched %d of %d across %d paper(s)" % (total, denom, len(scored)))
    if failed:
        print("NOT SCORED: papers %s" % failed)
    print("wrote", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
