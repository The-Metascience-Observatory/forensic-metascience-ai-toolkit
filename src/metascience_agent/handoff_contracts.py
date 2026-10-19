"""Did each stage's work actually ARRIVE, or was it computed and dropped?

WHY A THIRD DETECTOR, when `inertness.py` and `handoff.py` already exist.

Greg, 2026-08-26, after `grace.py` turned out to reach no report:

    "considering how frequently this issue of 'built, never fired' recurs, I was
     wondering if there is some kind of programmatic way of detecting this ...
     there is a way for the subsequent processing steps to notice the absence of
     the grace.py module's contributions (but not just 'any values', but the
     kind of data that indicates a successful handoff)."

That is the right question and the existing detectors cannot answer it.
`inertness.find_unconsumed_definitions` is STATIC: it proves a name is
referenced nowhere. `grace.record` IS referenced -- `tools/regression.py` calls
it -- so inertness correctly says nothing, and the module still reaches no
reader. The defect is not an unreferenced name. It is a CALL WHOSE OUTPUT GOES
NOWHERE, which is a property of the data a real run produced and cannot be seen
in the syntax tree at all.

So: a contract registry, checked against run ARTIFACTS. Each contract names a
producer, the payload that proves it ran, the artifact that must carry it, and
what silently breaks when it stops.

THE PAYLOAD PREDICATE MUST BE SPECIFIC, which is Greg's "not just 'any values'".
A contract asserting that `findings.v2.json` contains the key `grace` would pass
on `{"grace": {}}` -- the shape a broken handoff produces. Every predicate here
tests for the payload that only real work produces: a summary with a nonzero
count, a register with values in it, an anchor that resolves.

THREE STATES AND THE THIRD IS THE WHOLE DIFFICULTY. A contract can be
`satisfied`, `violated`, or -- the one that makes this safe --
`precondition_absent`: the producing situation never arose on this run, so
nothing was owed and nothing is wrong. A detector without that state fires on
every paper that happened to have no rescued checks, which is most of them, and
a linter that cries wolf gets switched off. That is the same failure this module
exists to catch, one level up, and `inertness.py` names it in its own docstring.

POSITIVE CONTROLS ARE MANDATORY. Every contract must have a test that CONSTRUCTS
the violation and asserts the audit reports it. A detector that cannot fire
returns zero exactly as convincingly as a healthy pipeline, and this repository
has shipped that mistake before.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

#: A contract's outcome. Only VIOLATED is a defect.
SATISFIED = "satisfied"
VIOLATED = "violated"
PRECONDITION_ABSENT = "precondition_absent"
CANNOT_TELL = "cannot_tell"


@dataclass(frozen=True)
class Contract:
    """One producer's work, and the artifact that must carry it.

    `owed` answers "did the producing situation occur on this run?" and returns
    None when the run does not record enough to tell -- which is reported as
    `cannot_tell`, never as a pass. `arrived` answers "is the payload there?"
    and must test the payload, not the key.
    """

    producer: str
    payload: str
    consumer: str
    why: str
    owed: Callable[[dict], bool | None]
    arrived: Callable[[dict], bool]


@dataclass(frozen=True)
class Result:
    contract: Contract
    state: str
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "producer": self.contract.producer,
            "payload": self.contract.payload,
            "consumer": self.contract.consumer,
            "state": self.state,
            "why_it_matters": self.contract.why,
            "detail": self.detail,
        }


# ---------------------------------------------------------------------------
# Helpers over a loaded run. `run` is the dict `load_run` builds.
# ---------------------------------------------------------------------------

def _tally(run: dict) -> dict:
    return ((run.get("findings_v2") or {}).get("checks_tally") or {})


def _n_rescued_by_convention(run: dict) -> int:
    """How many checks the CONVENTIONS rescued, from the tally.

    This is the precondition for the grace contract: it is computed by
    `agent.py` independently of `grace.py`, so it establishes that rescues
    happened WITHOUT relying on the module whose arrival is in question. A
    precondition read from the producer's own output would be circular and would
    pass whenever the producer was silent -- exactly the case being tested.
    """
    t = _tally(run)
    n = 0
    for key, field in (("rounding_convention", "n_fit_only_under_truncation"),
                       ("sd_convention", "n_fit_only_under_population_sd")):
        v = (t.get(key) or {}).get(field)
        if isinstance(v, int):
            n += v
    return n


def _grace_arrived(run: dict) -> bool:
    """A grace SUMMARY with a nonzero rescue count, anywhere it could live.

    Tests the payload, not the key: `{"grace": {}}` is what a broken handoff
    writes, and it must not pass.
    """
    doc = run.get("findings_v2") or {}
    for blob in (doc.get("grace"), (doc.get("checks_tally") or {}).get("grace")):
        if isinstance(blob, dict) and isinstance(blob.get("n_rescued"), int):
            return blob["n_rescued"] > 0
    for f in doc.get("findings") or []:
        g = f.get("grace") if isinstance(f, dict) else None
        if isinstance(g, dict) and g.get("rescued"):
            return True
    return False


CONTRACTS: tuple[Contract, ...] = (
    Contract(
        producer="grace.py",
        payload="a grace summary with n_rescued > 0, or per-finding grace records",
        consumer="findings.v2.json",
        why=("Every check applies allowances before returning -- a printed-precision "
             "interval, a truncated mean, a population SD. Those allowances keep the "
             "tools from convicting honest papers and cannot be removed. But an item "
             "they rescue comes back `consistent` and its residual is destroyed at "
             "source, so the only signal that distinguishes rounding noise from "
             "something else -- DIRECTION -- becomes uncomputable. Fifty cells within "
             "tolerance is noise; fifty of which forty-seven lean the same way is not, "
             "and no individual cell can tell you that."),
        owed=lambda run: _n_rescued_by_convention(run) > 0,
        arrived=_grace_arrived,
    ),
    Contract(
        producer="agent.py checks_tally",
        payload="the rounding/SD convention rates, rendered in the report",
        consumer="report.md",
        why=("Both rates were computed into every findings-v2 document from the day "
             "the conventions were added, and `report_v2.py` rendered neither, so the "
             "reader saw the rescued verdict and never the rescue. This contract is "
             "the regression guard on that fix."),
        owed=lambda run: bool(_tally(run).get("rounding_convention")),
        arrived=lambda run: "Reporting conventions" in (run.get("report_md") or ""),
    ),
    Contract(
        producer="values.py",
        payload="a value register carrying values, not merely a file",
        consumer="value_register.json",
        why=("`write_review_outputs` builds the register only when told which paper "
             "the review is of, and `metascience batch` never told it -- so every "
             "paper a batch analysed was written with no register and no note saying "
             "so. The viewer then reported that the values were not checked."),
        owed=lambda run: bool(run.get("has_paper_dir")),
        arrived=lambda run: int((run.get("value_register") or {}).get("n_values") or 0) > 0,
    ),
    Contract(
        producer="values.coverage",
        payload="the stratified coverage denominators, all four states present",
        consumer="value_register.json coverage block",
        why=("A denominator of effort cannot distinguish a thorough run from a lazy "
             "one. The strata (`n_checked`, `n_no_applicable_tool`, `n_silent`, and "
             "the `states_are_exclusive` conservation flag) are what make the number "
             "falsifiable; losing any one of them turns coverage back into a claim."),
        owed=lambda run: bool(run.get("value_register")),
        arrived=lambda run: all(
            k in ((run.get("value_register") or {}).get("coverage") or {})
            for k in ("n_checked", "n_no_applicable_tool", "n_silent",
                      "states_are_exclusive")),
    ),
    Contract(
        producer="anchors.py",
        payload="at least one finding carrying a resolved anchor",
        consumer="findings.v2.json findings[]",
        why=("An anchor is how a reader gets from an accusation back to the place in "
             "the paper it rests on. Findings without anchors are assertions."),
        owed=lambda run: bool((run.get("findings_v2") or {}).get("findings")),
        arrived=lambda run: any(
            (f.get("anchors") or f.get("anchor_summary"))
            for f in ((run.get("findings_v2") or {}).get("findings") or [])
            if isinstance(f, dict)),
    ),
    Contract(
        producer="channels bookkeeping",
        payload="a per-channel state for every channel, not an empty block",
        consumer="findings.v2.json channels",
        why=("A channel that did not run is not a channel that found nothing. Without "
             "the per-channel tri-state a reader cannot tell a paper we examined from "
             "one we glanced at, and 'no findings' carries a weight it has not "
             "earned."),
        owed=lambda run: bool(run.get("findings_v2")),
        arrived=lambda run: bool(
            (run.get("findings_v2") or {}).get("channels")
            and all(isinstance(v, dict) and v.get("state")
                    for v in ((run.get("findings_v2") or {}).get("channels") or {}).values())),
    ),
)


def load_run(review_dir: str | Path, paper_dir: str | Path | None = None) -> dict:
    """Everything the contracts read, loaded once.

    A file that is absent and a file that is unreadable both become None rather
    than `{}`: a contract must be able to report `cannot_tell` instead of
    inventing a violation out of our own IO failure.
    """
    review = Path(review_dir)

    def _json(name: str):
        p = review / name
        if not p.is_file():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _text(name: str):
        p = review / name
        try:
            return p.read_text(encoding="utf-8") if p.is_file() else None
        except OSError:
            return None

    return {
        "review_dir": str(review),
        "findings_v2": _json("findings.v2.json"),
        "value_register": _json("value_register.json"),
        "run_meta": _json("run_meta.json"),
        "report_md": _text("report.md"),
        "has_paper_dir": bool(paper_dir and Path(paper_dir).is_dir()),
    }


def audit(run: dict, contracts: tuple[Contract, ...] = CONTRACTS) -> list[Result]:
    """Each contract's state on one run. Never raises."""
    out: list[Result] = []
    for c in contracts:
        try:
            owed = c.owed(run)
        except Exception as exc:                        # noqa: BLE001
            out.append(Result(c, CANNOT_TELL,
                              f"precondition could not be evaluated: "
                              f"{type(exc).__name__}: {exc}"))
            continue
        if owed is None:
            out.append(Result(c, CANNOT_TELL,
                              "the run does not record enough to say whether this "
                              "producer had anything to hand over"))
            continue
        if not owed:
            out.append(Result(c, PRECONDITION_ABSENT,
                              "nothing was owed on this run"))
            continue
        try:
            ok = bool(c.arrived(run))
        except Exception as exc:                        # noqa: BLE001
            out.append(Result(c, CANNOT_TELL,
                              f"payload check failed: {type(exc).__name__}: {exc}"))
            continue
        out.append(Result(c, SATISFIED if ok else VIOLATED,
                          "" if ok else
                          f"{c.producer} had work to hand over and "
                          f"{c.consumer} does not carry it"))
    return out


def render(results: list[Result]) -> str:
    """Worst first, because that is the order an operator acts in."""
    order = {VIOLATED: 0, CANNOT_TELL: 1, SATISFIED: 2, PRECONDITION_ABSENT: 3}
    lines = []
    for r in sorted(results, key=lambda x: order.get(x.state, 9)):
        mark = {VIOLATED: "VIOLATED", CANNOT_TELL: "cannot tell",
                SATISFIED: "ok", PRECONDITION_ABSENT: "n/a"}[r.state]
        lines.append(f"[{mark:>11}] {r.contract.producer} -> {r.contract.consumer}")
        if r.state == VIOLATED:
            lines.append(f"              {r.contract.payload}")
            lines.append(f"              {r.detail}")
    n_bad = sum(1 for r in results if r.state == VIOLATED)
    lines.append("")
    lines.append(f"{n_bad} violated of {len(results)} contracts "
                 f"({sum(1 for r in results if r.state == PRECONDITION_ABSENT)} "
                 f"not applicable to this run)")
    return "\n".join(lines)
