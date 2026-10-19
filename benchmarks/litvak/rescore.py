#!/usr/bin/env python3
"""Re-score Litvak's own systems with the grounded verifier.

    python benchmarks/litvak/rescore.py --systems reviewer3 --dry-run
    python benchmarks/litvak/rescore.py --systems six --concurrency 10

WHY. Every comparison in this repo has been asymmetric: only FMA's findings
have been through the grounded verifier, while his published figures come from
one haiku call per finding with no evidence requirement. We have measured that
protocol failing three ways -- 14% of credits withdrawn on our own findings
(49 -> 42), non-determinism on borderline calls, and 17 of the 100 ground-truth
items matched on CLEAN papers by half or more of his systems, three of them by
13 of 13. Putting our verified number beside his unverified one is not a
comparison.

His repo holds the raw findings for all 54 conditions, INCLUDING the
`_originals` runs, so both halves of `adjusted = modified - originals` can be
recomputed under one grounded matcher.

WHAT THIS IS AND IS NOT. It produces OUR RE-ANALYSIS of his published results,
not a correction to his paper: a number from a judge he did not use is not his
figure. Rows are stored with `source="litvak_rescored"` so no table can present
them as either his published result or as one of our runs.

COSTS REAL MONEY. 100 calls per condition -- one per planted ERROR, not per
finding, so a 704-finding system costs the same as a 125-finding one. Run
`--dry-run` first; it prices the job and spends nothing.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import litvak_findings as LF                                   # noqa: E402
import results_store as RS                                     # noqa: E402
import score as S                                              # noqa: E402
from paths import BenchmarkNotFound, add_bench_arg, resolve_bench  # noqa: E402

#: The six Dan named, with the versions resolved from each run's `model_id`.
#: `claude_opus_*` is claude-opus-4-6; `claude_opus48_*` is 4.8 and is NOT here.
SIX = (
    "openai_gpt55_high_reasoning",     # gpt-5.5
    "claude_sonnet_no_thinking",       # claude-sonnet-4-6
    "claude_opus_high_thinking",       # claude-opus-4-6
    "claude_opus_no_thinking",         # claude-opus-4-6
    "refine_ink",
    "reviewer3",
)


def conditions_for(names: list[str], both: bool) -> list[str]:
    out = []
    for n in names:
        out.append(n)
        if both:
            out.append(f"{n}_originals")
    return out


async def rescore_condition(bench: Path, condition: str, gt_rows: list[dict],
                            *, model: str, timeout: int, concurrency: int,
                            cache: dict, retries: int, dry_run: bool) -> dict:
    """One condition -> a results_store row. Reuses `score.verify_corpus`."""
    findings = LF.load_condition(bench, condition)
    by_paper: dict[int, list[dict]] = {}
    for r in gt_rows:
        by_paper.setdefault(r["paper"], []).append(r)

    papers = sorted(set(findings) & set(by_paper))
    jobs = [(n, by_paper[n], findings[n]) for n in papers if findings[n]]
    todo = sum(1 for n, gts, cs in jobs for g in gts
               if not isinstance(cache.get(S.verify_cache_key(n, g, cs)), dict))
    n_findings = sum(len(v) for v in findings.values())

    if dry_run:
        return {"condition": condition, "papers": len(papers),
                "findings": n_findings, "calls": todo, "dry_run": True}

    t0 = time.monotonic()
    done = [0]

    def _on(ok: bool):
        done[0] += 1
        if done[0] % 10 and done[0] != todo:
            return
        el = time.monotonic() - t0
        rate = el / done[0]
        left = max(0, todo - done[0])
        print(f"    {done[0]}/{todo}  [{S.hms(el)}, {rate:.1f}s/call"
              + (f", ~{S.hms(left * rate)} left" if left else "") + "]",
              file=sys.stderr, flush=True)

    verified = await S.verify_corpus(
        jobs, model=model, timeout=timeout, concurrency=concurrency,
        cache=cache, retries=retries, run_cli=None, on_call_done=_on)
    S.save_cache(cache)

    caught = {}
    for n in papers:
        for gt in by_paper[n]:
            v = verified.get((n, gt["subcategory"]))
            caught[(n, gt["subcategory"])] = bool(v) and v.get("state") == "match"
    protocol = LF.load_protocol_matches(bench, condition)
    protocol = {k: protocol.get(k, False) for k in caught}

    row = RS.build_row(
        corpus=condition, backend="litvak",
        model=LF.model_id(bench, condition) or condition,
        verify_model=model,
        scored_at=_dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        commit=S.commit(), caught=caught, caught_protocol=protocol,
        gt_rows=gt_rows, n_hits_protocol=sum(protocol.values()),
        n_findings=n_findings, source="litvak_rescored", condition=condition)
    RS.upsert(row)
    return {"condition": condition, "papers": len(papers),
            "findings": n_findings, "calls": done[0],
            "protocol": sum(protocol.values()), "verified": row["n_hits"],
            "seconds": time.monotonic() - t0}


async def run(a) -> int:
    bench = resolve_bench(a.bench)
    gt_rows = S.ground_truth(bench)
    names = list(SIX) if a.systems == ["six"] else a.systems
    conds = conditions_for(names, a.both_conditions)

    missing = [c for c in conds if c not in LF.available(bench)]
    if missing:
        print(f"no stored findings for: {', '.join(missing)}", file=sys.stderr)
        return 1

    cache = S.load_cache()
    print(f"benchmark : {bench}")
    print(f"verifier  : {a.verify_model}, concurrency {a.concurrency}, "
          f"{len(conds)} condition(s)\n")

    results = []
    for c in conds:
        if not a.dry_run:
            print(f"  {c} ...", file=sys.stderr, flush=True)
        try:
            results.append(await rescore_condition(
                bench, c, gt_rows, model=a.verify_model, timeout=a.timeout,
                concurrency=a.concurrency, cache=cache, retries=a.retries,
                dry_run=a.dry_run))
        except S.JudgeUnavailable as exc:
            S.save_cache(cache)
            print(f"\nVERIFIER UNAVAILABLE: {exc}", file=sys.stderr)
            print("Everything verified so far is cached; re-run to resume.",
                  file=sys.stderr)
            return 2
        except KeyboardInterrupt:
            S.save_cache(cache)
            print("\nINTERRUPTED. Cached work is kept; re-run to resume.",
                  file=sys.stderr)
            return 130

    if a.dry_run:
        calls = sum(r["calls"] for r in results)
        print(f"{'condition':<36} {'papers':>6} {'findings':>9} {'calls':>6}")
        for r in results:
            print(f"{r['condition']:<36} {r['papers']:>6} {r['findings']:>9} "
                  f"{r['calls']:>6}")
        print(f"\n{calls} verifier call(s) to make. One call per planted ERROR,")
        print("not per finding -- a 704-finding system costs the same as a "
              "125-finding one.")
        print(f"Estimated ${calls * 0.30:.0f}-${calls * 0.40:.0f} at "
              f"{a.verify_model} rates measured 2026-08-23.")
        print("Nothing was spent. Drop --dry-run to run it.")
        return 0

    print(f"\n{'condition':<36} {'protocol':>9} {'verified':>9} {'delta':>6}")
    for r in results:
        print(f"{r['condition']:<36} {r['protocol']:>9} {r['verified']:>9} "
              f"{r['verified'] - r['protocol']:>+6}")
    print("\n`protocol` is Litvak's published figure (haiku, per finding, no "
          "evidence required).")
    print("`verified` is OUR re-analysis (per error, evidence quote required "
          "and checked in code).")
    print("Neither is a correction to his paper: a number from a judge he did "
          "not use is not his figure.")
    print("\nRender with: python benchmarks/litvak/tables.py")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    add_bench_arg(ap)
    ap.add_argument("--systems", nargs="+", default=["six"],
                    help="condition names, or `six` for the set Dan named")
    ap.add_argument("--both-conditions", action="store_true", default=True,
                    help="also re-score each system's `_originals` run, which "
                         "is what makes a VERIFIED adjusted score possible")
    ap.add_argument("--modified-only", dest="both_conditions",
                    action="store_false")
    ap.add_argument("--verify-model", default=S.VERIFY_MODEL)
    ap.add_argument("--concurrency", type=int, default=10)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--dry-run", action="store_true",
                    help="price the job and spend nothing")
    a = ap.parse_args()
    try:
        return asyncio.run(run(a))
    except BenchmarkNotFound as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
