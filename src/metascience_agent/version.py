"""What produced a run, and what the number means.

THE VERSION IS NOT DECORATION. A forensic review is an accusation about someone
else's arithmetic, and the first question a challenged author -- or a second
reader, or we ourselves six months on -- will ask is "what produced this?".
Until now a report answered that nowhere: `report.md` and `report.pdf` carried
no date and no version at all, and the number they would have carried was a
hardcoded `0.1.0` duplicated in `pyproject.toml` and `__init__.py`, never
bumped, with no tags and no changelog. Two reports a month apart were
indistinguishable.

THREE FACTS, AND THEY ARE DIFFERENT FACTS.

* `__version__` -- the release number, bumped BY HAND under the rules in
  CHANGELOG.md. It is the only part a human can talk about ("that was fixed in
  0.3"), and the only part that can signal *whether two reviews are comparable*.
  A git sha cannot: it tells you the code differed, never whether the
  difference matters.
* the git sha -- what actually ran. `__version__` moves about once a month; the
  code moves several times a day, so the release number alone does NOT identify
  a run. This is the same reason `agent._provenance` records prompt and
  registry hashes: the prompts move faster still.
* the dirty flag -- whether the sha means anything. A sha taken from a tree with
  uncommitted edits identifies code that exists nowhere but that machine.

Hence the composite that `pipeline_version()` returns. All three or the string
is a lie by omission.

`git_dirty` HAS THREE STATES, and the third is the point: `True`, `False`, and
`"unknown"` when the check itself could not run. Collapsing "the check said
clean" into "the check failed" publishes our own failure as a fact about the
code that ran -- the mistake this codebase keeps having to unlearn.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

#: The release number. Bump BY HAND, under the rules in CHANGELOG.md:
#:
#:   MAJOR  the report layout or an output schema changed in a way that breaks
#:          a downstream reader parsing it.
#:   MINOR  a new tool, or a change to what severity a check can return -- i.e.
#:          the same paper may now produce different findings.
#:   PATCH  a fix with no change to output semantics.
#:
#: The MINOR rule is the load-bearing one. It is what lets a reader compare two
#: reviews: same MAJOR.MINOR means a difference between them is about the
#: PAPERS, not about us.
#:
#: `pyproject.toml` reads this via hatchling's `dynamic = ["version"]`, so there
#: is exactly one place to edit. `tests/test_version.py` pins that they agree.
__version__ = "1.92.0"

#: What every provenance field prints when it could not be established. Shared
#: so the report, the viewer and the CLI say it the same way -- and so that a
#: missing fact reads as a missing fact rather than vanishing off the page.
NOT_RECORDED = "not recorded"


def git_state(repo_path: Path | None = None) -> dict:
    """`{git_sha, git_dirty}` for the checkout this code was loaded from.

    Best effort and silent: this is bookkeeping, and a failure here must never
    cost a paid analysis.

    `git_dirty` is ALWAYS present, and is set to "unknown" before any
    subprocess runs. An absent key also means "could not tell", but only to a
    reader who thinks to ask why it is missing; an explicit "unknown" says it.
    The sha probe failing must not take the flag with it -- that is the shape
    the whole three-state rule exists to prevent, one level up.

    The dirty probe sits in its OWN try. It used to share the outer one, so a
    `TimeoutExpired` -- a `SubprocessError` -- skipped the assignment entirely
    and left a `git_sha` with no `git_dirty` beside it. FOUND 2026-08-12 by
    running the suite under 10 xdist workers: concurrent `git status` calls
    contend, and one run in the full parallel suite dropped the key. It is a
    load-dependent hole in provenance, so it would have shown up first on a big
    batch -- the runs that matter most.
    """
    repo = str((repo_path or Path(__file__).resolve().parent))
    # Set BEFORE any subprocess: if a probe raises, the flag is still stamped,
    # and stamped as unknown rather than silently absent.
    out: dict = {"git_dirty": "unknown"}
    # TWO INDEPENDENT PROBES, not one nested in the other. Nesting made the
    # "always present" guarantee hold only while `rev-parse` ANSWERED, which is
    # the same load-dependent hole one level out: under parallel workers the
    # first call can time out, and the dirty check that would have answered
    # perfectly well never runs.
    try:
        sha = subprocess.run(
            ["git", "-C", repo, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if sha.returncode == 0 and sha.stdout.strip():
            # No sentinel when this fails: `handoff._predates_head` would read
            # one as a commit.
            out["git_sha"] = sha.stdout.strip()[:12]
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        dirty = subprocess.run(
            ["git", "-C", repo, "status", "--porcelain", "--untracked-files=no"],
            capture_output=True, text=True, timeout=15,
        )
        if dirty.returncode == 0:
            out["git_dirty"] = bool(dirty.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass              # stays "unknown": louder than a wrong False
    return out


def pipeline_version(stamp: dict | None = None) -> str:
    """The one string that says what produced a run.

    Pass the recorded `run_meta` (or any dict carrying `version` / `git_sha` /
    `git_dirty`) to describe an ARCHIVED run; pass nothing to describe the code
    running right now. The distinction matters when re-rendering an old review:
    formatting it with today's version would be a fabrication about a document
    produced by different code.

    A run predating this record keeps its honesty -- `version not recorded` --
    rather than borrowing the current number.
    """
    if stamp is None:
        stamp = {"version": __version__, **git_state()}

    release = str(stamp.get("version") or "").strip()
    head = f"v{release}" if release else f"version {NOT_RECORDED}"

    sha = str(stamp.get("git_sha") or "").strip()
    if not sha:
        # No parenthetical for an archived run that recorded no sha at all:
        # "version not recorded (commit not recorded)" is noise. Say it once.
        return head if not release else f"{head} (commit {NOT_RECORDED})"

    dirty = stamp.get("git_dirty")
    if dirty is True:
        return f"{head} (g{sha}, uncommitted changes)"
    if dirty is False:
        return f"{head} (g{sha})"
    # None or "unknown" -- the probe did not run. The sha may or may not
    # identify what ran, and saying which is not something we know.
    return f"{head} (g{sha}, tree state unknown)"
