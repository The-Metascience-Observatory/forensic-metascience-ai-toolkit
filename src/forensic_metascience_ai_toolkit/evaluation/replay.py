"""Re-run an archived run's tool calls at HEAD and diff the verdicts.

WHY THIS EXISTS
---------------
Every fix in this repo faces the same question -- "would that actually have
changed the output?" -- and until now the only way to answer it was a fresh paid
run: $9-10 and ~26 minutes, with a non-deterministic model in the middle, so
even then you could not tell a fix from a re-roll.

But the model is only half the pipeline. Once it has chosen a tool and its
arguments, EVERYTHING DOWNSTREAM IS A PURE FUNCTION of those arguments: the
checks, the clamps, the severity ladder, the rendering. And every archived run
records the arguments -- `toolcalls.tool_agent.json` stores each call's `input`
alongside the `result` it produced at the time.

So the deterministic half can be replayed exactly. Feed the archived inputs to
today's code, diff the severities, and you have measured your change against
REAL calls on REAL papers in seconds, for free, with the model held fixed.

This is the instrument the session of 2026-08-12 kept needing and hand-rolling.
Every defect fixed that day -- the Bernoulli duplication flag, the p-value typed
as a percentage, the sparse-OR midpoint, the shared denominator -- lived in this
replayable half, and each was verified by an ad-hoc script that was thrown away.

WHAT IT DOES NOT DO
-------------------
It cannot tell you whether the MODEL would have behaved differently: a fix that
makes a tool refuse more often may change what the model does next, and only a
live run shows that. Replay answers "given the same questions, do we now give
better answers", which is the question a code change actually raises.

Tools that write files or shell out are skipped by name rather than by guess --
see `SKIP`. A skipped call is REPORTED, never silently dropped, because a replay
that quietly covered half the calls would be a coverage figure computed against
effort, which is the defect this repo has fixed twice already.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MCP_PREFIX = "mcp__forensic_metascience__"

#: Not replayable, and each for a stated reason rather than because it looked
#: awkward. Replay must be free of side effects: it runs against a checkout a
#: developer is mid-edit on.
SKIP: dict[str, str] = {
    "extract_figures": "writes image files into the paper directory",
    "r_grim_ground_truth": "shells out to R; not part of the Python surface under test",
    "r_sprite_ground_truth": "shells out to R; not part of the Python surface under test",
}

#: Fields compared between the archived result and today's. Severity first --
#: it is the only field that becomes an accusation -- then the handful of
#: verdict-bearing companions.
COMPARED = ("severity", "verdict", "consistent", "impossible", "reconciles")


def _tool_name(call: dict) -> str:
    name = str(call.get("tool") or call.get("tool_short") or "")
    return name[len(MCP_PREFIX):] if name.startswith(MCP_PREFIX) else name


def _verdict_of(payload: Any) -> dict:
    """The verdict-bearing fields of a tool result, at the top level only.

    Deliberately shallow. A deep diff of two 60 KB payloads reports every
    reworded explanation as a change and buries the one severity that moved;
    the severity IS the thing that becomes an accusation, so it is what a
    reader needs to see.
    """
    if not isinstance(payload, dict):
        return {}
    out = {k: payload[k] for k in COMPARED if k in payload}
    # Batch tools carry their verdicts one level down, per row.
    rows = payload.get("results") or payload.get("rows")
    if isinstance(rows, list) and rows:
        sev = [r.get("severity") for r in rows if isinstance(r, dict)]
        if any(s is not None for s in sev):
            out["row_severities"] = sev
    return out


def _archived_payload(call: dict) -> Any:
    """The archived result, parsed. Returns None when it cannot be recovered."""
    if call.get("result_truncated"):
        return None
    raw = call.get("result")
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def replay_run(run_dir: str | Path, stage: str = "tool_agent") -> dict:
    """Re-invoke every replayable tool call of an archived run at HEAD.

    Returns a record per call plus totals. `changed` is the list that matters:
    each entry names the tool, the archived verdict and today's.
    """
    from .. import registry as R

    path = Path(run_dir)
    ledger_file = path / f"toolcalls.{stage}.json"
    if not ledger_file.exists():
        return {"run": str(path), "error": f"no {ledger_file.name} in this run",
                "n_calls": 0, "changed": [], "unchanged": 0, "skipped": []}
    try:
        ledger = json.loads(ledger_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"run": str(path), "error": f"could not read the ledger: {exc}",
                "n_calls": 0, "changed": [], "unchanged": 0, "skipped": []}

    changed: list[dict] = []
    skipped: list[dict] = []
    errored: list[dict] = []
    unchanged = 0

    for call in ledger if isinstance(ledger, list) else []:
        name = _tool_name(call)
        spec = R.BY_NAME.get(name)
        if spec is None:
            skipped.append({"tool": name, "seq": call.get("seq"),
                            "why": "not a registered forensic tool"})
            continue
        if name in SKIP:
            skipped.append({"tool": name, "seq": call.get("seq"), "why": SKIP[name]})
            continue
        before_payload = _archived_payload(call)
        if before_payload is None:
            # The archived result was clipped or unparseable, so there is
            # nothing to diff AGAINST. Reported, not counted as agreement.
            skipped.append({"tool": name, "seq": call.get("seq"),
                            "why": "archived result truncated or unparseable"})
            continue
        args = call.get("input")
        if not isinstance(args, dict):
            skipped.append({"tool": name, "seq": call.get("seq"),
                            "why": "no recorded input to replay"})
            continue
        try:
            # statcheck's R-derived wrapper prints progress banners to stdout on
            # every call. Over hundreds of replayed calls that buries the diff,
            # which is the only thing anyone runs this to read. Captured, not
            # silenced: a crash still surfaces through the except below.
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()):
                after_payload = spec.call(dict(args))
        except Exception as exc:  # noqa: BLE001 -- a crash IS the finding here
            errored.append({"tool": name, "seq": call.get("seq"),
                            "error": f"{type(exc).__name__}: {exc}"})
            continue

        before, after = _verdict_of(before_payload), _verdict_of(after_payload)
        if before == after:
            unchanged += 1
        else:
            changed.append({"tool": name, "seq": call.get("seq"),
                            "before": before, "after": after,
                            "locator": (args.get("source_locator")
                                        or args.get("table") or "")})

    return {
        "run": str(path),
        "paper": path.parent.name,
        "stage": stage,
        "n_calls": len(ledger) if isinstance(ledger, list) else 0,
        "n_replayed": unchanged + len(changed),
        "unchanged": unchanged,
        "changed": changed,
        "errored": errored,
        "skipped": skipped,
    }


def replay_corpus(root: str | Path, stage: str = "tool_agent") -> dict:
    """`replay_run` over every archived run under `root`."""
    # A bundle carries a COPY of the run's ledger under `analysis/`, so a naive
    # walk replays every run twice and doubles every count. Matched on the path
    # PARTS rather than on a substring, because bundle directories are named
    # variously (`*_bundle`, `bundle_HEAD_<date>`) and a substring test missed
    # the second form -- which is how the first corpus replay reported 13 runs
    # where the archive holds 11.
    def _is_bundle(p: Path) -> bool:
        return any(part == "analysis" or part.startswith("bundle")
                   or part.endswith("_bundle") for part in p.parts)

    runs = sorted(p.parent for p in Path(root).rglob(f"toolcalls.{stage}.json")
                  if not _is_bundle(p))
    results = [replay_run(r, stage) for r in runs]
    return {
        "root": str(root),
        "n_runs": len(results),
        "n_replayed": sum(r["n_replayed"] for r in results),
        "n_changed": sum(len(r["changed"]) for r in results),
        "n_errored": sum(len(r["errored"]) for r in results),
        "n_skipped": sum(len(r["skipped"]) for r in results),
        "runs": results,
    }


#: The tiers that constitute an ACCUSATION. `indeterminate` is not one of them,
#: and the distinction is the whole point of `classify` below.
from ..tools.severity import ACCUSES_AT_ALL as ACCUSATORY  # one definition; see severity.py


def classify(summary: dict) -> dict:
    """Split the moved verdicts by DIRECTION, which is what actually matters.

    A naive "more severe / less severe" split on the ladder is misleading here
    and produced a wrong headline the first time this was run: 111 calls looked
    like they had got worse, but 107 of them were `consistent -> indeterminate`,
    which is a REFUSAL, not an accusation -- and under this project's cardinal
    rule a visible refusal is a good outcome and a false all-clear is a bad one.

    So the split that matters is three-way:
      became_accusatory   was not an accusation, now is. Each one needs
                          justifying cell by cell before it ships.
      relieved            was an accusation, now is not. The win column.
      refused             now `indeterminate` where it was `consistent`. We
                          stopped claiming to know something. Usually correct.
    """
    out = {"became_accusatory": [], "relieved": [], "refused": [], "other": []}
    for r in summary.get("runs") or [summary]:
        for c in r.get("changed") or []:
            before = (c.get("before") or {}).get("severity")
            after = (c.get("after") or {}).get("severity")
            entry = dict(c, paper=r.get("paper"), run=r.get("run"))
            if after in ACCUSATORY and before not in ACCUSATORY:
                out["became_accusatory"].append(entry)
            elif before in ACCUSATORY and after not in ACCUSATORY:
                out["relieved"].append(entry)
            elif before == "consistent" and after == "indeterminate":
                out["refused"].append(entry)
            else:
                out["other"].append(entry)
    return out


def render(summary: dict) -> str:
    """One screen a human reads to answer 'did my change do anything?'."""
    lines: list[str] = []
    lines.append(
        f"replayed {summary.get('n_replayed', 0)} archived tool call(s) across "
        f"{summary.get('n_runs', 1)} run(s) at HEAD")
    n_changed = summary.get("n_changed", len(summary.get("changed") or []))
    if not n_changed:
        lines.append("NO VERDICT MOVED. Every replayed call returns what it "
                     "returned when the run was archived.")
        return "\n".join(lines)

    split = classify(summary)
    lines.append(
        f"  {len(split['became_accusatory'])} became ACCUSATORY   "
        f"{len(split['relieved'])} relieved of an accusation   "
        f"{len(split['refused'])} now refuse where they were clean   "
        f"{len(split['other'])} other")

    if split["became_accusatory"]:
        lines.append("\nBECAME ACCUSATORY -- justify each of these by hand "
                     "before shipping:")
        for c in split["became_accusatory"]:
            lines.append(f"  {c.get('paper', '?')} · {c['tool']}"
                         + (f" · {c['locator']}" if c.get("locator") else ""))
            lines.append(f"      {c['before'].get('severity')} -> "
                         f"{c['after'].get('severity')}")
    for r in summary.get("runs") or [summary]:
        for e in r.get("errored") or []:
            lines.append(f"  CRASH {r.get('paper', '?')} · {e['tool']}: {e['error']}")
    n_skip = summary.get("n_skipped", len(summary.get("skipped") or []))
    if n_skip:
        lines.append(f"\n{n_skip} call(s) not replayable (side effects, R, or an "
                     "archived result that was truncated) -- NOT counted as "
                     "agreement.")
    return "\n".join(lines)
