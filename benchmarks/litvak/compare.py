#!/usr/bin/env python3
"""Head-to-head against every system Litvak tested, error by error.

    python benchmarks/litvak/compare.py --from-db modified

A total tells you who scored higher. It does NOT tell you whether two systems
found the SAME errors, and on this benchmark that is the whole question: an FMA
that catches ten errors nobody else caught is a different proposition from an
FMA that catches ten of GPT-5.5's seventy-one.

So every row is a set comparison on the same planted errors:

    +X  errors THEY caught that we missed
    -Y  errors WE caught that they missed
    net  Y - X

`+` and `-` are from OUR point of view: `+7 / -3` means they are ahead by four
on this subset, and that we still hold three errors they never found.

SPENDS NOTHING. Runs the scorer in `--cached-only` mode: it reuses judgements
already bought and never makes a call. Findings with no cached judgement are
reported as UNCOVERED, not as "no match" -- a question we never asked is not an
answer of no, and reporting it as one would make a partial run look complete.

RESTRICTED TO THE PAPERS WE HAVE COMPLETE. If our run has judged five of the
ten papers, every number here is out of those five papers' fifty errors, for us
AND for them. Comparing our 5-paper result against their 10-paper total is the
denominator error this whole harness exists to prevent.

THE COMPARISON IS NOT LIKE-FOR-LIKE, and the caveats are printed with it:
Litvak's systems read a flattened text PDF from `docx_to_pdf.py`; we read a
layout-preserving conversion. Different input, in our favour on table-bound
checks. His judge and ours share a prompt but ran on different findings.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score as S                                            # noqa: E402
from paths import BenchmarkNotFound, add_bench_arg, resolve_bench  # noqa: E402

#: Conditions that are NOT a system's headline detection score.
#: `_originals` is the false-positive baseline (the clean papers, where a
#: "match" is a false alarm); `_open` is a different prompt; `_run2`/`_run3`
#: are reliability repeats. `writeup_numbers.py:37` skips exactly these.
EXCLUDE_SUFFIXES = ("_originals", "_open", "_run2", "_run3")


def load_litvak(bench: Path, include_originals: bool = False
                ) -> dict[str, dict[tuple[int, str], bool]]:
    """{provider: {(paper, subcategory): matched}} from his stored results.

    `include_originals=True` loads ONLY the `_originals` conditions -- the same
    systems run over the ten UNMODIFIED papers. Nothing is planted there, so a
    "match" is the judge matching something to nothing: a direct measurement of
    the matching procedure's false-positive rate. Kept behind a flag because
    these rows must never enter a detection leaderboard, which is what the
    default exclusion protects.
    """
    root = bench / "benchmark" / "results"
    out: dict[str, dict[tuple[int, str], bool]] = {}
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        is_orig = d.name.endswith("_originals")
        if include_originals:
            if not is_orig:
                continue
        elif any(d.name.endswith(sfx) for sfx in EXCLUDE_SUFFIXES):
            continue
        got: dict[tuple[int, str], bool] = {}
        for fp in sorted(d.glob("paper_*_matched.json")):
            try:
                rows = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            for r in rows:
                gt = r.get("ground_truth") or {}
                if "paper" in gt and "subcategory" in gt:
                    got[(int(gt["paper"]), gt["subcategory"])] = bool(r.get("matched"))
        if got:
            out[d.name[:-10] if include_originals else d.name] = got
    return out


def our_results(a) -> tuple[dict[tuple[int, str], bool], set[int], dict]:
    """({(paper, subcategory): caught}, complete_papers, stats) -- no spend."""
    bench = resolve_bench(a.bench)
    rows = S.ground_truth(bench)
    by_paper: dict[int, list[dict]] = defaultdict(list)
    for r in rows:
        by_paper[r["paper"]].append(r)

    db_findings, db_meta = S.load_findings_from_db(a.from_db, a.db_url)
    cache = S.load_cache()

    jobs, cands_by_paper = [], {}
    for n in sorted(db_findings):
        cands = S.candidates(db_findings[n], a.include_quarantined)
        cands_by_paper[n] = cands
        if cands:
            jobs.append((n, by_paper[n], cands))

    judged = asyncio.run(S.judge_corpus(
        jobs, model=a.model, timeout=a.timeout, concurrency=1, cache=cache,
        retries=0, run_cli=None, cached_only=True))

    caught: dict[tuple[int, str], bool] = {}
    complete: set[int] = set()
    n_uncached = n_total = 0
    for n, cands in cands_by_paper.items():
        miss = sum(1 for c in cands if S.cache_key(n, c) not in cache)
        n_uncached += miss
        n_total += len(cands)
        # A paper counts only if EVERY one of its eligible findings has an
        # answer. One unasked question is enough to make its score a floor,
        # and a floor mixed into a head-to-head reads as a loss.
        if miss == 0:
            complete.add(n)
        claimed = judged.get(n, ({}, 0))[0]
        for i, gt in enumerate(by_paper[n]):
            caught[(n, gt["subcategory"])] = i in claimed
    stats = {"uncached": n_uncached, "eligible": n_total,
             "papers_total": len(cands_by_paper)}
    return caught, complete, stats


def compare(ours, theirs, gt_rows, papers):
    keys = [(r["paper"], r["subcategory"]) for r in gt_rows
            if r["paper"] in papers]
    both = they_only = we_only = neither = 0
    we_only_rows, they_only_rows = [], []
    for k in keys:
        w, t = ours.get(k, False), theirs.get(k, False)
        if w and t:
            both += 1
        elif t:
            they_only += 1
            they_only_rows.append(k)
        elif w:
            we_only += 1
            we_only_rows.append(k)
        else:
            neither += 1
    return {"n": len(keys), "both": both, "they_only": they_only,
            "we_only": we_only, "neither": neither,
            "ours": both + we_only, "theirs": both + they_only,
            "we_only_rows": we_only_rows, "they_only_rows": they_only_rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-db", metavar="CORPUS", default="modified")
    ap.add_argument("--db-url", default=None)
    add_bench_arg(ap)
    ap.add_argument("--include-quarantined", action="store_true")
    ap.add_argument("--model", default=S.JUDGE_MODEL)
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--json", type=Path, default=None)
    a = ap.parse_args()

    try:
        bench = resolve_bench(a.bench)
    except BenchmarkNotFound as exc:
        print(exc, file=sys.stderr)
        return 1

    ours, complete, stats = our_results(a)
    if not complete:
        print("No paper has a complete set of cached judgements yet, so there "
              "is nothing to compare.\nRun `score.py --from-db "
              f"{a.from_db}` to completion first "
              f"({stats['uncached']} of {stats['eligible']} findings unjudged).",
              file=sys.stderr)
        return 1

    gt_rows = S.ground_truth(bench)
    litvak = load_litvak(bench)
    band = "all 100"
    n_errors = len([r for r in gt_rows if r["paper"] in complete])

    print(f"HEAD-TO-HEAD -- {band} planted errors, "
          f"{len(complete)} of {stats['papers_total']} papers")
    print(f"papers    : {', '.join(f'litvak{n:02d}' for n in sorted(complete))}")
    print(f"errors    : {n_errors} (the shared denominator; every number below "
          "is out of this)")
    if stats["uncached"]:
        incomplete = stats["papers_total"] - len(complete)
        print(f"EXCLUDED  : {incomplete} paper(s) with {stats['uncached']} "
              f"unjudged finding(s) of {stats['eligible']}.")
        print("            An unasked question is not an answer of 'no match', "
              "so those papers\n            are left out entirely rather than "
              "scored as misses.")
    print()
    print("  +X = errors THEY caught and we missed;  -Y = errors WE caught and "
          "they missed")
    print(f"  {'system':<34} {'them':>5} {'us':>4} {'both':>5} {'+X':>4} "
          f"{'-Y':>4} {'net':>5}")
    print(f"  {'-' * 34} {'-' * 5} {'-' * 4} {'-' * 5} {'-' * 4} {'-' * 4} {'-' * 5}")

    payload, rows = {}, []
    for name, theirs in sorted(litvak.items()):
        c = compare(ours, theirs, gt_rows, complete)
        rows.append((name, c))
        payload[name] = {k: v for k, v in c.items()
                         if not k.endswith("_rows")}
    for name, c in sorted(rows, key=lambda r: -r[1]["theirs"]):
        net = c["we_only"] - c["they_only"]
        print(f"  {name:<34} {c['theirs']:>5} {c['ours']:>4} {c['both']:>5} "
              f"{c['they_only']:>4} {c['we_only']:>4} {net:>+5}")

    # The column a total hides: what do we hold that the whole field missed?
    if rows:
        in_band = {(r["paper"], r["subcategory"]) for r in gt_rows
                   if r["paper"] in complete}
        ours_only_vs_all = [k for k in in_band if ours.get(k)
                            and not any(t.get(k, False) for t in litvak.values())]
        print(f"\nERRORS WE CAUGHT THAT **NO** SYSTEM LITVAK TESTED CAUGHT "
              f"({len(ours_only_vs_all)}):")
        by_sub = {(r["paper"], r["subcategory"]): r for r in gt_rows}
        for k in sorted(ours_only_vs_all):
            r = by_sub.get(k, {})
            print(f"  p{k[0]:<3} {k[1][:36]:<38} {str(r.get('category','')):<24} "
                  f"{str(r.get('description'))[:40]}")
        if not ours_only_vs_all:
            print("  none")

    print("\nCAVEATS, and they are not small:")
    print("  1. DIFFERENT INPUT. His systems read the flattened text PDF from")
    print("     `docx_to_pdf.py`; we read a layout-preserving conversion. That")
    print("     favours us on every table-bound check, and `verify_tables.py`")
    print("     has not been run on this corpus to say how much.")
    print("  2. DIFFERENT JUDGE RUN. Same prompt, same protocol, but his")
    print("     judgements were made over his systems' findings and ours over")
    print("     ours. Judge leniency does not have to be equal between them.")
    print("  3. His numbers here are recomputed on THIS paper subset from")
    print("     `benchmark/results/*/paper_*_matched.json`, not copied from his")
    print("     leaderboard, so they will not equal his published /100.")

    if a.json:
        a.json.write_text(json.dumps({
            "commit": S.commit(), "corpus": a.from_db,
            "band": band, "papers": sorted(complete),
            "n_errors": n_errors, "uncached_findings": stats["uncached"],
            "systems": payload,
        }, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
