# Errors this project keeps making, and what actually catches them

Read this before you measure anything or wire anything up. Each rule below came
from a real defect in this repository. One short example each is kept so the
rule is recognisable; the full history is in git. Code and docs cite entries by
number (`LESSONS #4`), so the numbers are stable.

---

## 1. Absence read as evidence

A missing file, an absent field or a misspelled key becomes a ZERO MEASUREMENT
instead of NO MEASUREMENT. Example: "0 archived calls pass a p" was really 745;
the code keyed on `tool` while the archive used `tool_short`.

**Rule.** Before you report a zero, prove the instrument was pointed at
something. Return "could not measure" (e.g. `reconcilable: False`), never a
count of 0. This is the same error the toolkit exists to catch in papers: a
channel that did not run is not a channel that found nothing.

## 2. The denominator is wrong, or the direction is

Example: "3.78% of 556" used the flagged list (556) where the checks run (2,113)
belonged. Another: measuring "how many report findings trace back to the
analyst" (92.5%) instead of "how many analyst findings reach the report"
(59.9%) hid a 40% drop.

**Rule.** State the denominator before the percentage. For a ratio between two
populations, name both. When one count lumps several different failures
together, print them separately.

## 3. Built, tested, consumed by nothing

This is the most common structural defect here. A field gets written into
every run and rendered nowhere. A prompt says "state why you discarded it" and
no schema field exists for the answer. A module ships with tests and zero
callers. A value is recorded in every record and no code branches on it. A
value in a record is not a guard.

**Rule.** A feature is done when something READS it. Add its consumer in the
same commit: a renderer listed in `VIEWER_MUST_RENDER`, or a test that fails
without it (`tests/test_output_is_read.py` enforces this for payload keys).

## 4. Guards that silently stop guarding

A guard that returns "nothing found" looks exactly like a broken guard. One
check meant to catch 18 bad findings PASSED all 18, because it counted letters
in a dict's keys. A detector's regex broke the moment the claims it read got
date stamps.

**Rule.** Every detector and guard gets a test asserting it still finds a KNOWN
POSITIVE. Run it on the population it exists to catch, and count the hits. When
the question can't be decided in code, split off the part code CAN decide and
report the rest as a named fact for a human. Don't dress a heuristic up as a
verdict.

## 5. Measured claims in prompts go stale and then steer wrongly

A number quoted in a prompt or schema reads as timeless fact forever. One such
claim told the model a calibration had failed after it had started working.

**Rule.** Every measured claim in a prompt or schema carries the date it was
measured (`tests/test_prompt_claims_are_dated.py` enforces this). Re-measure
before you rely on it.

## 6. Reading the code instead of the output

These were invisible in source and obvious on the page: a title rendered as
"Forensic review -- al. 2019"; `"; ".join(x).capitalize()` lowercasing "NOT in
the paper"; a generated command that exited 2 because Click reads `-0.01` as an
option.

**Rule.** Run it, render it, and read what a reader would see. For the viewer:
build a REAL bundle and execute the page's own JavaScript. Reasoning about
`bundle.py` from source has been wrong every time.

## 7. Your own fix, or your own instrument, reproduces the bug

The reproduction-command generator, written to replace commands the model got
wrong, made the model's exact mistake. A fix for "a `git status` timeout loses
`git_dirty`" covered the second call and not the first. A new ground-truth
scorer reported a found duplication as MISSED because it misassigned grid rows.
It nearly prompted loosening a detector threshold to fix a bug that wasn't there.

**Rule.** Test a fix against the specific instances that defined the defect. If
your new code can't reproduce the original failure, you haven't tested it. When
a failure early in a sequence can swallow a guarantee later on, test every
position. When a mature component and a new measuring tool disagree, suspect the
tool first, and check its mapping against the raw output for at least one case.

## 8. Before calling something a bug

- Check `git log` / `git blame`. Several "defects" were deliberate, documented
  decisions.
- Check whether the code POSTDATES the archive you are measuring. A tool newer
  than the runs was "never called" because it didn't exist yet.
- Check the guard is reachable before reporting it as inert.

## 9. The repo's own guards catch you faster than re-reading does

**Rule.** Run `metascience lint-inert --certain-only` and the full suite
(`metascience-test --stack -q`) BEFORE you decide a change is finished. When a
ratchet test fires, assume first that it is right.

## 10. Derived state that outlives what it was derived from

Example: a cached copy of a detector's answer had no validity key. A detector
change re-ran 907 papers, the stale copies survived, and they were written back
over the fresh answers on 176 papers.

**Rule.** Anything derived from a run carries that run's stamp and is checked
against it, or is deleted by whatever writes the next run. A cache without an
invalidation key is a time bomb. Choose ONE file as the authority on which run
is current.

## 11. A whole corpus can read as clean while several things are broken

Example: a 3,000-paper image run in which every stage reported success and,
after full human review, zero true positives turned up. Underneath were three
independent failures. One backend aborted all 62 of its calls before the first
turn. A validator refused 90 of 142 answers by rules no prompt stated. The paper
selection excluded exactly the papers most likely to be positive. Counting
caught them, not the tests: `calls_spent: 234` beside `validated: 52` can't both
be right.

**Rules.**
- Never report a corpus as clean without a recall measurement on a population
  with known positives.
- Count what each backend actually did, per backend, every run.
- A rule the validator enforces and the prompt omits is a trap. Prompt and
  validator must state the same contract.
- Keep a ledger of every model answer. A validator change can then be rescored
  against the real population for free, instead of being argued about.
- Put a guard at the boundary it protects. A publication guard belongs at
  publication; an analysis run must be able to record "publication refused" and
  finish.

## 12. A capability that silently resolved to something weaker

Example: the panel detector's `auto` setting silently fell back to the weaker detector
because nothing looked where the model files actually were. Every chart gate
then read a null `panel_type` on 103,243 panels. The visible symptom was "the
chart gates don't work"; the gates were right and idle.

**Rules.**
- A flag that selects a capability records what it RESOLVED to (and why) in the
  artifact, not just what was requested. A log line does not survive.
- An impossible combination, such as "stamp says learned, no panel has a type",
  should raise an alarm, not be accepted as a state.
- `auto` never means "silently do the weaker thing". Ambiguity (two candidates,
  no canonical one) refuses by name.
- `python -m <pkg>.cli` with no `__main__` guard exits 0 and does nothing.
  Fix it with a guard and a test, not a note.
- Ask a program what it is; don't parse it from a file. The documented
  `$(head -1 $(which metascience) | tr -d '#!')` resolved to `/bin/sh` on a
  shim, and Python piped into it ran `import json` as ImageMagick, dropping a
  48 MB screenshot into the repo (2026-10-18). `metascience python` prints
  `sys.executable` instead.

---

**In one sentence: prove the instrument was working before you believe what it
says**, whether it's about a paper, the pipeline or your own change.
