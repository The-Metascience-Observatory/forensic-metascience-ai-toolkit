"""Which runs are current, and the refusal to read the ones that are not.

WHY THIS EXISTS. Greg Fitzgerald, 2026-08-29:

    "many problems it finds were fixed, and things like the fable subagents keep
     assuming that those runs are representative of the output of our current
     system. It thwarts progress, because it promotes rediscovery and chasing
     false leads."

That is not hypothetical, and the cost is measured. On 2026-08-28 a research
round censused 416 findings across 16 archived run directories, found that NONE
carried the fields the severity gate reads, and concluded from it that the
toolkit's central safety guarantee had never governed a shipped finding. The
count was exact. The conclusion was wrong twice over: the gate was wired on
2026-08-21 (`4fd2dc2`) and every one of those runs predates it, and the current
pipeline writes `findings.v2.json` while all 416 were `findings.json` -- a
different artifact entirely. A live run then showed the gate firing on 34 of 34
rows. An entire architectural argument, and several hours of agent time, rested
on output produced by code that no longer exists.

THE HORIZON IS A DEFAULT, NOT A LAW. Two weeks is Greg's number and it is a
judgement about how fast this codebase moves, not a property of runs. Override
it deliberately with `horizon_days=` or the environment, and the override is
visible in the partition it returns.

MTIME IS NOT USED, AND THAT IS THE DESIGN'S ONE SHARP EDGE. Measured 2026-08-29:
all 15 archived run directories under `high_value_pdfs_to_run_on/` carry an
mtime of 2026-08-22, from a bulk copy, while their own recorded `git_sha` values
span 2026-08-11 to 2026-08-16. A filesystem timestamp dates the COPY, not the
run, and trusting it would have called every stale run current -- the exact
failure this module exists to prevent, with the sign inverted.

FAILS CLOSED. A run whose date cannot be established is treated as STALE. That
is the safe direction here for the same reason refusal is the safe direction
everywhere else in this toolkit: acting on output from unknown code is how a
fixed defect gets rediscovered and argued about. An undatable run is also, in
practice, an OLD one -- the runs that cannot be dated are the ones written
before the pipeline recorded `analysed_at`.

AND IT IS NEVER SILENT. `partition` returns what it excluded and why, because
"there were no runs" and "there were nine runs and all of them were stale" are
different facts and this project has a long history of rendering the second as
the first. Callers must report the exclusion; a caller that drops the stale list
on the floor has reintroduced the house failure mode.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
from pathlib import Path
from typing import Iterable

#: Greg's number, 2026-08-29. A run older than this is not evidence about the
#: current system.
RUN_HORIZON_DAYS = 14

#: What this module could not read, appended in order. A guard that hides its
#: own failures is the defect it exists to prevent, so the reasons are kept and
#: `partition` reports them.
#:
#: A LIST, NOT A KEYED MAP, and the correction is worth recording. The first
#: version was `dict[str, str]` keyed by path, and `lint-inert` flagged
#: `_UNREADABLE["registry_surface"]` and `["prompt_blob"]` as WRITE-ONLY KEYS --
#: written once and read nowhere. It was right, and about this module of all
#: modules. These were never a lookup: nothing ever asks "did the prompt blob
#: fail", it asks "what went wrong". A list says that, and a failure on one path
#: no longer overwrites an earlier one on the same path.
_UNREADABLE: list[dict[str, str]] = []


def _note_unreadable(where: str, exc: Exception) -> None:
    _UNREADABLE.append({"where": where, "why": f"{type(exc).__name__}: {exc}"})

#: Set to a number of days to widen or narrow the horizon, or to `all` to read
#: everything. Whichever is in force is reported in every `partition` result, so
#: a widened horizon cannot be mistaken for the default one.
HORIZON_ENV = "METASCIENCE_RUN_HORIZON_DAYS"

#: The schema the CURRENT pipeline writes. A run stamped with anything else came
#: out of a retired pipeline, and age alone will not catch it: measured
#: 2026-08-29, `forensic_review_2026-08-16` is thirteen days old -- inside the
#: horizon -- and is schema 1.0, written before the parallel pipeline and before
#: the severity gate existed. It emits `findings.json`; the current one emits
#: `findings.v2.json`. Reading the first as though it were the second is
#: precisely the mistake that cost a night. Corpus-wide today: 25 runs at 1.0,
#: 2 at 2.0.
#:
#: This constant is pinned by a test against what a real run actually writes, so
#: bumping the pipeline's schema without bumping this fails loudly rather than
#: silently admitting the old shape.
CURRENT_RUN_SCHEMA = "2.0"

#: `forensic_review_2026-08-13`, `analysis_2026_08_13`. Only used when the run
#: did not record its own date.
_NAME_DATE = re.compile(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})")


def _parse_iso(text: str) -> _dt.datetime | None:
    try:
        return _dt.datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def run_date(run_dir: str | Path) -> tuple[_dt.datetime | None, str]:
    """When this run happened, and HOW that was established.

    The `how` is returned because the three sources are not equally trustworthy
    and a caller deciding whether to argue from a run deserves to know which one
    it got. In order:

    1. `analysed_at` in the run's own `run_meta.json`. The run stamping itself.
       Present on every archived run in this repo, old schema and new.
    2. A date in the directory name. Weaker -- a human typed it -- but it is a
       claim about the run rather than about the filesystem.
    3. Nothing. Returns `(None, "undatable")`, which `is_current` reads as stale.
    """
    d = _source_dir(Path(run_dir))
    meta = d / "run_meta.json"
    if meta.is_file():
        try:
            doc = json.loads(meta.read_text(encoding="utf-8"))
        except Exception as exc:                             # noqa: BLE001
            # SAID, NOT SWALLOWED. An unreadable run_meta falls through to the
            # weaker date sources, and a caller comparing two runs deserves to
            # know one of them could not state its own date.
            _note_unreadable(str(meta), exc)
            doc = {}
        when = _parse_iso(doc.get("analysed_at"))
        if when is not None:
            return when, "analysed_at"
    # THE FINDINGS FILE STAMPS ITSELF TOO, and some runs carry `analysed_at`
    # there and nowhere else -- found 2026-08-29 when a corpus-stats fixture
    # written that way read as undatable.
    fv2 = d / "findings.v2.json"
    if fv2.is_file():
        try:
            when = _parse_iso(json.loads(fv2.read_text(encoding="utf-8"))
                              .get("analysed_at"))
        except Exception:                                    # noqa: BLE001
            when = None
        if when is not None:
            return when, "findings.v2.json"

    m = _NAME_DATE.search(d.name)
    if m:
        try:
            return (_dt.datetime(int(m[1]), int(m[2]), int(m[3]),
                                 tzinfo=_dt.timezone.utc), "directory_name")
        except ValueError:
            pass
    return None, "undatable"


def _source_dir(run_dir: Path) -> Path:
    """A bundle is a COPY of a run, so it is judged by the run it copies.

    `forensic_review_X_bundle` carries no `run_meta.json` of its own, so it
    would read as undatable-but-named and slip through on its directory name
    while `forensic_review_X` beside it was correctly excluded as schema 1.0.
    A copy of stale output is stale output.
    """
    if run_dir.name.endswith("_bundle"):
        src = run_dir.with_name(run_dir.name[: -len("_bundle")])
        if src.is_dir():
            return src
    return run_dir


def run_schema(run_dir: str | Path) -> str | None:
    """The schema this run was written under, or None if it did not say."""
    meta = _source_dir(Path(run_dir)) / "run_meta.json"
    if not meta.is_file():
        return None
    try:
        return str(json.loads(meta.read_text(encoding="utf-8"))
                   .get("schema_version") or "") or None
    except Exception as exc:                                 # noqa: BLE001
        _note_unreadable(str(meta), exc)
        return None


#: The stamp fields that decide whether a run reflects the CURRENT build, in the
#: order they matter. A run whose registry surface and prompts hash the same as
#: HEAD is evidence about today's tool behaviour however many commits ago it
#: ran; a run one commit old whose registry hash differs is not.
#:
#: This is the exact test the 14-day horizon only approximates. Greg,
#: 2026-08-29: "use versioning such that a given run is stamped with the exact
#: build of the codebase, such that you can understand its output in context."
#: The stamping was already there -- `git_sha`, `git_dirty`, `schema_version`,
#: `registry_sha256`, `prompt_sha256`, `version`, `model`, `effort` are all
#: recorded. Nothing read them. This does.
BUILD_FIELDS = ("schema_version", "registry_sha256", "prompt_sha256")


def build_fingerprint(config=None) -> dict:
    """What the CURRENT tree would stamp a run with.

    Computed the same way `agent._run_meta` computes it, by importing the same
    modules -- not by parsing a recorded value, which would only tell us what
    some past run believed.

    `config` is the run's pipeline (`pipeline_config.PipelineConfig`); None is
    the complete review every run before pipelines was. The prompt hash is a
    function of the configuration -- a one-tool run is sent a different
    prompt -- so comparing it against the default would call every partial
    run stale forever.
    """
    import hashlib

    out: dict[str, str | None] = {"schema_version": CURRENT_RUN_SCHEMA}
    try:
        from . import registry as _registry

        surface = json.dumps(
            [[sp.name, sorted(sp.schema()), sp.description]
             for sp in _registry.SPECS], sort_keys=True, default=str)
        out["registry_sha256"] = hashlib.sha256(
            surface.encode("utf-8")).hexdigest()[:16]
    except Exception as exc:                                 # noqa: BLE001
        _note_unreadable("registry surface", exc)
        out["registry_sha256"] = None
    # THE PARALLEL BLOB, NOT THE LEGACY PAIR. `agent._provenance` defaults to
    # `stage1 + stage2` for the retired serial path, and a parallel run passes
    # its own three prompts (`parallel.py:1071`). Hashing the default here would
    # have compared a parallel run's stamp against a blob it never used and
    # called every one of them stale forever -- a guard that rejects everything
    # is not a guard. Caught 2026-08-29 on this session's own reference run,
    # where the registry hash matched and only the prompt hash did not.
    try:
        from .core import prompts as _prompts

        if config is None:
            from . import pipeline_config as _pc
            config = _pc.from_flags()
        blob = _prompts.prompt_blob(config)
        out["prompt_sha256"] = hashlib.sha256(
            blob.encode("utf-8")).hexdigest()[:16]
    except Exception as exc:                                 # noqa: BLE001
        _note_unreadable("prompt blob", exc)
        out["prompt_sha256"] = None
    return out


def run_build(run_dir: str | Path) -> dict:
    """The build fingerprint a run recorded for itself, plus `git_dirty`."""
    meta = _source_dir(Path(run_dir)) / "run_meta.json"
    if not meta.is_file():
        return {}
    try:
        doc = json.loads(meta.read_text(encoding="utf-8"))
    except Exception as exc:                                 # noqa: BLE001
        _note_unreadable(str(meta), exc)
        return {}
    out = {k: doc.get(k) for k in BUILD_FIELDS}
    out["git_sha"] = doc.get("git_sha")
    out["git_dirty"] = doc.get("git_dirty")
    out["pipeline"] = doc.get("pipeline")
    return out


def build_matches(run_dir: str | Path) -> tuple[bool, str]:
    """Does this run reflect the build HEAD would produce, and if not, where?

    STALENESS IS QUESTION-RELATIVE, and this is the honest version of that. A
    run is out of date for a given question if the code answering it changed.
    Comparing the recorded hashes to the current ones answers that exactly,
    where a clock only guesses.

    A run recorded with `git_dirty: true` NEVER matches. Its sha names a commit
    plus unknown edits, so it does not identify a build at all -- the stamp is a
    comforting fiction. Found on this session's own reference run, 2026-08-29.
    """
    rec = run_build(run_dir)
    if not rec:
        return False, "no run_meta.json, so the build is unknown"
    if rec.get("git_dirty"):
        return False, ("recorded git_dirty: the sha names a commit plus "
                       "uncommitted edits and does not identify a build")
    # CONFIGURATION-AWARE: the expected build is the one THIS run's pipeline
    # would get from the current tree. A recorded pipeline the current tree
    # cannot resolve (a tool since removed, a module renamed) does not match.
    from . import pipeline_config as _pc
    try:
        config = _pc.from_record(rec.get("pipeline"))
    except _pc.PipelineConfigError as exc:
        return False, f"recorded pipeline no longer resolves: {exc}"
    now = build_fingerprint(config)
    for field in BUILD_FIELDS:
        want, got = now.get(field), rec.get(field)
        if want is None or got is None:
            return False, f"{field} missing on one side; cannot compare"
        if str(want) != str(got):
            return False, f"{field} differs: run {got}, current {want}"
    return True, "registry, prompts and schema all match the current build"


def _horizon(horizon_days: int | None) -> int | None:
    if horizon_days is not None:
        return horizon_days
    raw = os.environ.get(HORIZON_ENV)
    if raw is None:
        return RUN_HORIZON_DAYS
    if str(raw).strip().lower() in ("all", "none", "0"):
        return None                       # deliberately unbounded; reported
    try:
        return int(raw)
    except ValueError:
        return RUN_HORIZON_DAYS


def is_current(run_dir: str | Path, now: _dt.datetime | None = None,
               horizon_days: int | None = None) -> bool:
    """Is this run recent enough to be evidence about the system as it is now?

    False for an undatable run. See the module docstring: failing closed is the
    point, and the undatable runs are in fact the old ones.
    """
    limit = _horizon(horizon_days)
    if limit is None:
        return True
    # SCHEMA BEFORE AGE. A run from a retired pipeline is not evidence about
    # this one however recently it ran, and `schema_version` says so directly
    # where a date only implies it.
    # BUILD IDENTITY FIRST, AND IT CAN RESCUE AN OLD RUN AS WELL AS CONDEMN A
    # RECENT ONE. If the registry surface, the prompts and the schema all hash
    # the same as HEAD, the run describes today's behaviour whatever the
    # calendar says -- and the clock would have thrown it away.
    ok, _why = build_matches(run_dir)
    if ok:
        return True
    schema = run_schema(run_dir)
    if schema is not None and schema != CURRENT_RUN_SCHEMA:
        return False
    when, _how = run_date(run_dir)
    if when is None:
        return False
    now = now or _dt.datetime.now(_dt.timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=_dt.timezone.utc)
    return (now - when).days <= limit


def partition(run_dirs: Iterable[str | Path],
              now: _dt.datetime | None = None,
              horizon_days: int | None = None) -> dict:
    """Split runs into current and stale, and SAY what was excluded.

    Returns `{horizon_days, unbounded, current, stale, n_current, n_stale,
    why}`. `why` maps each excluded directory to its age and how that age was
    established, so a report can name the exclusion instead of quietly showing
    a shorter list.
    """
    limit = _horizon(horizon_days)
    now = now or _dt.datetime.now(_dt.timezone.utc)
    current: list[Path] = []
    stale: list[Path] = []
    why: dict[str, str] = {}
    for d in run_dirs:
        d = Path(d)
        if limit is None:
            current.append(d)
            continue
        schema = run_schema(d)
        if schema is not None and schema != CURRENT_RUN_SCHEMA:
            stale.append(d)
            why[str(d)] = (f"schema {schema}, current is {CURRENT_RUN_SCHEMA} "
                           f"-- a retired pipeline, whatever its age")
            continue
        when, how = run_date(d)
        if when is None:
            stale.append(d)
            why[str(d)] = "undatable, so treated as stale"
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=_dt.timezone.utc)
        age = (now - when).days
        if age <= limit:
            current.append(d)
        else:
            stale.append(d)
            why[str(d)] = f"{age} days old (from {how}), horizon is {limit}"
    return {
        "horizon_days": limit,
        "unbounded": limit is None,
        "current": current,
        "stale": stale,
        "n_current": len(current),
        "n_stale": len(stale),
        "why": why,
        # WHAT THIS MODULE ITSELF COULD NOT READ. Recorded at the point of
        # failure and REPORTED HERE, which the `_UNREADABLE` docstring claimed
        # from the start and did not do -- `lint-inert` caught it as a
        # write-only key, which is exactly right: an answer computed and
        # delivered to nobody, in the module written to stop that happening.
        # A caller comparing two runs must be able to tell "these dates
        # differ" from "one of them could not state its date".
        "unreadable": list(_UNREADABLE),
        # THE SENTENCE A CALLER SHOULD PRINT. Not decoration: "no runs" and
        # "nine runs, all stale" are different facts and the second must not be
        # rendered as the first.
        "note": (
            f"{len(current)} current run(s); {len(stale)} excluded as older "
            f"than {limit} days. Output from a run that old describes code that "
            f"may no longer exist -- set {HORIZON_ENV} to widen the horizon "
            f"deliberately." if stale else ""
        ),
    }


def current_runs(paper_dir: str | Path, pattern: str = "forensic_review*",
                 now: _dt.datetime | None = None,
                 horizon_days: int | None = None) -> dict:
    """`partition` over one paper's run directories, newest first."""
    base = Path(paper_dir)
    dirs = sorted((d for d in base.glob(pattern) if d.is_dir()),
                  key=lambda d: (run_date(d)[0] or _dt.datetime.min.replace(
                      tzinfo=_dt.timezone.utc)), reverse=True)
    return partition(dirs, now=now, horizon_days=horizon_days)
