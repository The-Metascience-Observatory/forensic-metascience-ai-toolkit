#!/usr/bin/env python3
"""Where the benchmark and its outputs live -- resolved, never assumed.

Both scripts here used to hardcode `/mnt/c/Users/gregs/...`, a WSL path from
the machine they were written on. `/mnt/c` does not exist on a native Linux
checkout, so `score.py` died with a bare `FileNotFoundError` on the CSV before
printing anything, and `prepare.py` raised `NotReachableByWindows` for a reason
that had nothing to do with the actual problem.

Resolution order, first hit wins:

  1. an explicit `--bench` / `--out` argument
  2. `$LITVAK_BENCH` / `$LITVAK_OUT`
  3. the sibling-checkout layout (this repo and the benchmark side by side)
  4. the historical `/mnt/c` paths, so the original machine keeps working

A miss names every path that was tried. "I looked in these four places" is a
fixable message; `FileNotFoundError: error_insertions.csv` is not.
"""
from __future__ import annotations

import os
from pathlib import Path

#: This repo's root -- benchmarks/litvak/paths.py -> up three.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: Ordered candidates for the upstream benchmark checkout.
BENCH_CANDIDATES: tuple[Path, ...] = (
    REPO_ROOT.parent / "ai-peer-review-benchmark",
    Path.home() / "Dropbox/AAA_METASCIENCE_OBSERVATORY/ai-peer-review-benchmark",
    Path("/mnt/c/Users/gregs/ai-peer-review-benchmark"),
)

#: Ordered candidates for the output root. Deliberately OUTSIDE this repo: the
#: modified manuscripts are corrupted by design and must not become committable.
OUT_CANDIDATES: tuple[Path, ...] = (
    Path("/mnt/c/Users/gregs/fmt-litvak"),
    Path.home() / "fmt-litvak",
)

#: The file whose presence proves a directory really is the benchmark checkout.
_MARKER = "error_insertions.csv"


class BenchmarkNotFound(RuntimeError):
    """No benchmark checkout, with every path that was tried named."""


def resolve_bench(explicit: Path | str | None = None) -> Path:
    """Locate the upstream `ai-peer-review-benchmark` checkout.

    Verified by the presence of `error_insertions.csv`, not by `is_dir()`: an
    empty directory of the right name is the failure mode that produces a
    confident zero rather than an error.
    """
    # An explicit request is honoured or REFUSED -- never quietly replaced by a
    # different checkout. Scoring against ground truth the operator did not ask
    # for is a silent substitution, and it would be invisible in the output.
    named = explicit or os.environ.get("LITVAK_BENCH")
    if named:
        cand = Path(named).expanduser()
        if (cand / _MARKER).is_file():
            return cand
        raise BenchmarkNotFound(
            f"{cand} was named explicitly "
            f"({'--bench' if explicit else '$LITVAK_BENCH'}) but holds no "
            f"{_MARKER}. Refusing to fall back to another checkout: scoring "
            "against ground truth you did not ask for would not be visible in "
            "the output."
        )

    tried: list[str] = []
    for cand in BENCH_CANDIDATES:
        tried.append(str(cand))
        if (cand / _MARKER).is_file():
            return cand
    raise BenchmarkNotFound(
        "Could not find the ai-peer-review-benchmark checkout (looked for "
        f"{_MARKER} in each of these):\n  " + "\n  ".join(tried)
        + "\n\nPass --bench <path>, or set LITVAK_BENCH."
    )


def resolve_out(explicit: Path | str | None = None) -> Path:
    """Where prepared paper directories go.

    Unlike the benchmark root this need not exist yet, so the first candidate
    whose PARENT exists wins -- we are choosing a place to create, not finding
    something already there.
    """
    for cand in _candidates(explicit, "LITVAK_OUT", OUT_CANDIDATES):
        if cand.is_dir() or cand.parent.is_dir():
            return cand
    return OUT_CANDIDATES[-1]


def _candidates(explicit, env_var: str, defaults) -> list[Path]:
    out: list[Path] = []
    if explicit:
        out.append(Path(explicit).expanduser())
    if os.environ.get(env_var):
        out.append(Path(os.environ[env_var]).expanduser())
    out.extend(defaults)
    seen: set[Path] = set()
    uniq: list[Path] = []
    for p in out:
        try:
            key = p.resolve()
        except OSError:
            key = p
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    return uniq


def add_bench_arg(ap) -> None:
    """The `--bench` flag, worded the same way in both scripts."""
    ap.add_argument("--bench", type=Path, default=None,
                    help="ai-peer-review-benchmark checkout "
                         "(default: sibling of this repo, or $LITVAK_BENCH)")
