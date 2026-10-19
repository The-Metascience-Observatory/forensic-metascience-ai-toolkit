"""Settle each Python-vs-R SPRITE disagreement by exact enumeration.

NEITHER IMPLEMENTATION IS THE ORACLE HERE. The differential says the two
disagree; it cannot say who is right, and asking either of them is asking a
party to the dispute. So this decides each case from first principles: does an
integer distribution exist, on the stated scale, whose mean and SD both round to
the reported values at the reported precision?

The method is a dynamic program over (count, sum) accumulating the set of
attainable sums-of-squares, which is exact and scales past the point where
enumerating every composition stops being possible. A first pass adjudicated
only cases with n <= 22 because it enumerated compositions directly; that left
the larger-n disagreements unexamined, and "the ones I could afford to check"
is not a sample anybody should reason from.

The question asked of each candidate distribution is deliberately the FORENSIC
one: a paper printing "M = 1.8" has not said the mean is 1.8, it has said the
mean rounds to 1.8. Both reported values get their reporting interval, because
an accusation resting on precision the paper never claimed is rulebook rule 4.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path


def attainable_sumsq(n: int, lo: int, hi: int, target_sum: int) -> set[int]:
    """Every sum-of-squares reachable by `n` integers in [lo, hi] summing to
    `target_sum`. Exact, by DP over (count, running sum)."""
    states: dict[int, set[int]] = {0: {0}}
    for i in range(n):
        nxt: dict[int, set[int]] = defaultdict(set)
        remaining = n - i - 1
        for s, qs in states.items():
            for v in range(lo, hi + 1):
                s2 = s + v
                # prune: can the remaining picks still reach target_sum?
                if s2 + remaining * lo > target_sum: break
                if s2 + remaining * hi < target_sum: continue
                v2 = v * v
                nxt[s2].update(q + v2 for q in qs)
        states = nxt
    return states.get(target_sum, set())


def exists(n: int, lo: int, hi: int, mean: float, sd: float,
           m_prec: int, sd_prec: int) -> tuple[bool, str]:
    """Is there an integer distribution matching both reported values?"""
    mt, st = 0.5 / 10 ** m_prec + 1e-9, 0.5 / 10 ** sd_prec + 1e-9
    lo_sum = math.ceil((mean - mt) * n - 1e-9)
    hi_sum = math.floor((mean + mt) * n + 1e-9)
    for s in range(max(lo_sum, n * lo), min(hi_sum, n * hi) + 1):
        m = s / n
        if abs(m - mean) > mt:
            continue
        for q in attainable_sumsq(n, lo, hi, s):
            var = (q - s * s / n) / (n - 1)
            if var < -1e-9:
                continue
            if abs(math.sqrt(max(var, 0.0)) - sd) <= st:
                return True, f"sum={s} mean={m:.4f} sumsq={q}"
    return False, "no integer distribution matches both at the stated precision"


def main() -> int:
    src = Path(sys.argv[1] if len(sys.argv) > 1
               else str(Path(__file__).resolve().parent / "sprite_r_differential.json"))
    report = json.loads(src.read_text(encoding="utf-8"))
    cases = report.get("disagreements") or []
    print(f"disagreements to adjudicate: {len(cases)}")
    py_right = r_right = skipped = 0
    verdicts = []
    for c in cases:
        n = int(c["n"])
        if n > 40:                       # DP cost; reported, never silent
            skipped += 1
            continue
        ok, why = exists(n, int(c["lo"]), int(c["hi"]), float(c["mean"]),
                         float(c["sd"]), int(c.get("m_prec", 1)),
                         int(c.get("sd_prec", 1)))
        py_right += ok
        r_right += (not ok)
        verdicts.append({**c, "adjudicated": "python" if ok else "r",
                         "evidence": why})
    total = py_right + r_right
    out = {
        "source": str(src), "n_disagreements": len(cases),
        "n_adjudicated": total, "n_skipped_large_n": skipped,
        "python_right": py_right, "r_right": r_right,
        "method": ("exact DP over (count, sum) accumulating attainable "
                   "sums-of-squares; both reported values given their reporting "
                   "interval, which is the forensic question rather than the "
                   "exact-value one rsprite2 answers"),
        "verdicts": verdicts,
    }
    dest = src.with_name("sprite_adjudication.json")
    dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"adjudicated {total}: python right {py_right}, r right {r_right}"
          + (f" (skipped {skipped} with n>40)" if skipped else ""))
    if r_right:
        print("\ncases where R is right -- these are OUR bugs:")
        for v in verdicts:
            if v["adjudicated"] == "r":
                print(f"   mean={v['mean']} sd={v['sd']} n={v['n']} "
                      f"[{v['lo']},{v['hi']}] r_why={v.get('r_why')}")
    print(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
