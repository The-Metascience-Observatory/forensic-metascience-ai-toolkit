#!/usr/bin/env python3
"""The append-only record of every FMA run scored on this benchmark.

One JSON file, `results.json`, holding one row per run: which corpus, which
backend and model, when, and the per-error caught map. Every table in
`tables.py` is rendered FROM this file, so a new run is a new row and nothing
has to be re-derived or re-typed.

WHY A STORE AND NOT A RE-SCORE. Re-running the scorer reproduces a number only
if the judge is deterministic, and it measurably is not -- the same haiku call
on the same finding returned `5` during one run and `none` on a re-run minutes
later. So a published table has to be built from the answers that were actually
given, recorded once, not recomputed on demand. The alternative is a table that
quietly changes under a reader who re-runs it.

Rows are keyed on `run_id` (corpus + backend + model + scored_at) and appended;
re-scoring the same corpus with the same models REPLACES its row rather than
adding a second, because two rows for one run would silently double-count in
any per-category total.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

STORE_PATH = Path(__file__).resolve().parent / "results.json"


def load(path: Optional[Path] = None) -> list[dict]:
    path = path or STORE_PATH
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:                                          # noqa: BLE001
        return []
    return data if isinstance(data, list) else []


def save(rows: list[dict], path: Optional[Path] = None) -> None:
    """Atomic, for the same reason the judge cache is.

    A plain write truncates before it writes, so a reader mid-save gets a
    half-written file -- and `load` swallows that into an empty list, which
    would silently drop every recorded run.
    """
    path = path or STORE_PATH
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(rows, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def run_id(corpus: str, backend: str, model: str) -> str:
    return f"{corpus}|{backend}|{model}"


#: Where a row's findings came from. `ours` is a run FMA produced;
#: `litvak_rescored` is one of HIS systems' stored findings put through our
#: verifier. Different claims -- one is our system's performance, the other is
#: our re-analysis of someone else's published result -- so the tables must not
#: present them identically.
SOURCES = ("ours", "litvak_rescored")


def upsert(row: dict, path: Optional[Path] = None) -> list[dict]:
    """Append, or replace the row with the same `run_id`.

    Replace rather than append, because two rows for one run double-count in
    every total the tables compute.
    """
    rows = [r for r in load(path) if r.get("run_id") != row.get("run_id")]
    rows.append(row)
    rows.sort(key=lambda r: (-int(r.get("n_hits") or 0), str(r.get("run_id"))))
    save(rows, path)
    return rows


def build_row(*, corpus: str, backend: str, model: str, verify_model: str | None,
              scored_at: str, commit: str, caught: dict[tuple[int, str], bool],
              gt_rows: list[dict], n_hits_protocol: int | None,
              caught_protocol: dict[tuple[int, str], bool] | None = None,
              cost_usd: float | None = None,
              n_findings: int | None = None,
              source: str = "ours",
              condition: str | None = None) -> dict:
    """One run, reduced to what every table needs.

    TWO per-error maps, and the distinction is load-bearing:

      `caught_protocol` -- Litvak's protocol verbatim: haiku, one call per
        finding, no evidence requirement. THIS is what every leaderboard
        comparison must use, because it is how his fourteen systems were
        scored. Comparing our verified number against his protocol number
        compares a strict judge with a lenient one and understates us.

      `caught` -- the verified pass: stronger model, one call per error, a
        verbatim evidence quote required and checked in code. This is the
        better estimate of what was actually caught, and it is NOT comparable
        to anyone else's number.

    Categories are recomputed here from the ground truth rather than carried
    in, so a row can never disagree with the CSV about which category an error
    belongs to.
    """
    caught_protocol = caught_protocol or caught

    def _cats(m):
        cat = {}
        for r in gt_rows:
            k = (r["paper"], r["subcategory"])
            if k not in m:
                continue
            c = cat.setdefault(r["category"], {"hits": 0, "of": 0})
            c["of"] += 1
            c["hits"] += 1 if m[k] else 0
        return cat

    cat = _cats(caught)
    if source not in SOURCES:
        raise ValueError(f"source must be one of {SOURCES}, got {source!r}")
    return {
        "run_id": run_id(corpus, backend, model),
        "source": source, "condition": condition,
        "label": (f"FMA {model}" + (f" ({backend})" if backend != "claude" else "")
                  if source == "ours" else str(condition or model)),
        "corpus": corpus, "backend": backend, "model": model,
        "verify_model": verify_model, "scored_at": scored_at, "commit": commit,
        "n_hits": sum(1 for v in caught.values() if v),
        "n_errors": len(caught),
        "n_hits_litvak_protocol": n_hits_protocol,
        "cost_usd": cost_usd, "n_findings": n_findings,
        "by_category": cat,
        "by_category_protocol": _cats(caught_protocol),
        "caught": {f"{k[0]}|{k[1]}": v for k, v in caught.items()},
        "caught_protocol": {f"{k[0]}|{k[1]}": v
                            for k, v in caught_protocol.items()},
    }


def caught_map(row: dict, which: str = "caught") -> dict[tuple[int, str], bool]:
    """`which='caught_protocol'` for anything compared against Litvak."""
    out = {}
    for k, v in (row.get(which) or row.get("caught") or {}).items():
        p, _, sub = k.partition("|")
        out[(int(p), sub)] = bool(v)
    return out
