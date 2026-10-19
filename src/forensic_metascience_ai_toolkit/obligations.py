"""What a finished review OWES its reader, and a way to notice when it stops.

THE FAILURE THIS EXISTS TO CATCH, which has happened at least twelve times.

Capabilities in this codebase do not usually break; they stop being CALLED. The
consequence corroborator, the sandbox audit, the delivery audit, reproduction
validation, ledger quote verification, the sourcing join, the computation audit,
the machine-generation-residue sweep, report scrubbing, `severity_source` --
each was written, tested, and then left behind when the execution path moved
from `agent.py` to `parallel.py`. Every one of them passed every existence
check: the module was present, the function was importable, the tests were
green. Nothing said the output had stopped appearing.

A CHECKLIST WOULD NOT HAVE CAUGHT IT EITHER, and this is the design point. A
list of files to assert only catches an artifact that DISAPPEARS. It says
nothing about an artifact that APPEARS and that nobody has thought about -- and
an unregistered output is how a promise gets made to a reader with no owner:
`report_v2` printed a `Reproduce:` line for months that nobody had validated.

So this is a CONSERVATION law, asserted in both directions:

    every artifact this registry declares must appear   (nothing owed is lost)
    every artifact that appears must be declared here   (nothing arrives unowned)

The second direction is the whole point. It fails when someone adds a new output
without saying what it is for, which is exactly the moment to ask.

WHAT A GREEN SUITE HERE DOES **NOT** MEAN -- read this before trusting it.

This proves EXISTENCE PARITY. It cannot prove BEHAVIOUR PARITY, and the
difference has already cost this project a live defect. `secondlook` was
present, imported, called, and returned a docket reading "No finding accuses the
paper, so there is nothing to re-check." beside 34 findings and 21 outcomes of
`problem`. Its `ACCUSATORY` set had frozen on the v1 STRING severities while v2
rows carry the NUMERIC ladder; the overlap was empty. Every existence check in
this file would have passed while the adjudicator was told a false sentence.

So: a file appearing here means a writer wrote it. It does not mean the content
is right, that the guard inside it fired, or that anyone read it. Those need
their own tests, and this registry is not a substitute for one.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Artifact:
    """One file a writer owes, and what a reader loses without it."""

    name: str
    #: Why it exists, in terms of what is LOST when it is absent. A reason that
    #: only restates the filename is a sign nobody knows what it is for.
    why: str
    #: `required` artifacts must appear on every successful run. Optional ones
    #: are declared so that conservation still passes when they DO appear --
    #: they are known, just not always applicable.
    required: bool = True
    #: Set when absence is itself informative and a named error file may stand
    #: in. `value_register.json` may legitimately fail; what it may not do is
    #: vanish silently.
    or_error_file: str | None = None


#: Written by `parallel.write_parallel_outputs`. Adding an output means adding
#: it here, and the conservation test is what makes that not optional.
PARALLEL_ARTIFACTS: tuple[Artifact, ...] = (
    Artifact("findings.v2.json",
             "the findings themselves; without it there is no review"),
    Artifact("report.md",
             "the human-readable review -- the only artifact most readers open"),
    # Best-effort since 2026-09-02 (v1.16.0): before that, `analyze --pdf`
    # reached nothing on this path and the README promised the file anyway.
    # Optional because a machine without a renderer still produces a review;
    # what it may not do is drop the file silently -- `run_meta.pdf_error`
    # carries the reason, and the viewer prints it.
    Artifact("report.pdf",
             "the review as a fixed-layout document, the form that gets "
             "emailed; without it a reader gets markdown or nothing",
             required=False),
    Artifact("run_meta.json",
             "what code produced this, and when. Without it a run cannot be "
             "dated, and `runs.is_current` fails closed and calls it stale"),
    Artifact("value_register.json",
             "every value we read and what we did with it -- the denominator "
             "of every coverage claim the report makes",
             or_error_file="value_register.error.txt"),
    # Operator-facing, and optional because it needs at least one stage
    # ledger to exist. Written by the parallel writer since v1.20.0; the
    # bundle deliberately recounts the same figures inline rather than
    # reading this file, so the two cannot drift apart silently.
    # Required since v1.22.0: docs/specs/pipeline.md §13 lists it among a
    # parallel run's outputs and README calls it the one to read. It was
    # PARALLEL_TOLERATED as a "legacy-path artifact" until then, which is how
    # a missing spec requirement came to look like expected behaviour.
    Artifact("sandbox_audit.json",
             "whether anything ran outside the validated tool surface. A "
             "silently un-sandboxed run is otherwise indistinguishable from a "
             "validated one",
             or_error_file="sandbox_audit.error.txt"),
    Artifact("source_coverage.json",
             "per agent, how many of its checks said where their numbers came "
             "from -- the quote-verification tally behind every coverage claim",
             required=False,
             or_error_file="source_coverage.error.txt"),
    Artifact("adjudication.json",
             "what the adjudicator was asked and what it answered, so a "
             "verdict can be traced to the docket that produced it"),

    # The prompts. Archived because a finished review cannot be audited for
    # what instructed it otherwise -- and because `_provenance`'s prompt hash
    # has nothing to compare against.
    *(Artifact(f"prompt.{a}.md",
               f"the USER turn sent to the {a}; the question actually asked")
      for a in ("tool_agent", "science_agent", "adjudicator")),
    *(Artifact(f"system_prompt.{a}.md",
               f"the SYSTEM prompt for the {a} -- the rulebook, severity "
               f"ladder and guard sentences. MEASURED 2026-08-22: the user "
               f"turn is 504 bytes and carries none of it")
      for a in ("tool_agent", "science_agent", "adjudicator")),
    *(Artifact(f"messages.{a}.json",
               f"the {a}'s full transcript, so a quote can be traced to the "
               f"turn that produced it")
      for a in ("tool_agent", "science_agent", "adjudicator")),
    *(Artifact(f"toolcalls.{a}.json",
               f"the {a}'s tool ledger -- what was computed versus asserted")
      for a in ("tool_agent", "science_agent", "adjudicator")),
)

#: Names that may appear without being owed: writer-internal scratch, or files
#: whose presence depends on the paper rather than on the writer. Each needs a
#: reason, for the same purpose the registry has -- an unexplained exemption is
#: how the conservation direction gets quietly defeated.
PARALLEL_TOLERATED: dict[str, str] = {
    "value_register.error.txt":
        "the named failure of an optional artifact; better than its silence",
    "report.html":
        "the viewer bundle, written only when bundling is requested",
    "source.json":
        "written by the extractor, not the review writer",
}


def required_names(artifacts=PARALLEL_ARTIFACTS) -> set[str]:
    return {a.name for a in artifacts if a.required}


def declared_names(artifacts=PARALLEL_ARTIFACTS) -> set[str]:
    names = {a.name for a in artifacts}
    names |= {a.or_error_file for a in artifacts if a.or_error_file}
    return names


def missing(present: set[str], artifacts=PARALLEL_ARTIFACTS) -> list[Artifact]:
    """Owed artifacts that did not appear. An `or_error_file` satisfies its own
    artifact -- a named failure is a report, and silence is not."""
    out = []
    for a in artifacts:
        if not a.required:
            continue
        if a.name in present:
            continue
        if a.or_error_file and a.or_error_file in present:
            continue
        out.append(a)
    return out


def unregistered(present: set[str], artifacts=PARALLEL_ARTIFACTS,
                 tolerated=PARALLEL_TOLERATED) -> list[str]:
    """Files that appeared and that nothing in the registry accounts for.

    THE DIRECTION THAT MAKES THIS CONSERVATION rather than a checklist. A new
    output arriving unannounced is not a bug in itself -- it is an unanswered
    question about what promise it makes to a reader, and this is where that
    question gets asked.
    """
    return sorted(present - declared_names(artifacts) - set(tolerated))

# ---------------------------------------------------------------------------
# Field obligations: the losses that a FILE registry cannot see
# ---------------------------------------------------------------------------
#
# The file list above catches an artifact that stops being written. It cannot
# catch the failure that actually happened twelve times, because the parallel
# writer emits MORE files than the legacy one (17 against 16) -- what went
# missing was FIELDS INSIDE those files. `reproduction_valid` is the clean
# example: 24 findings per run carried a `Reproduce:` command and ZERO carried
# a verdict, in a file that existed, was well-formed, and passed every
# structural check.
#
# A CORRECTION THAT MATTERS, and it is why this list is short. The project notes
# name twelve "lost capabilities" including `severity_source`, `computation` and
# `sourcing`. `computation` is NOT in `findings.v2.schema.json` -- it is a v1
# field whose consumer is the v1 renderer, and a v2 document that omits it is
# not losing a capability; it is honouring a different contract. Asserting it
# here would manufacture a debt rather than record one.
#
# THE OTHER TWO HAVE SINCE MOVED, and this comment asserted otherwise for long
# enough to be worth naming (found 2026-09-04 by a second reader checking the
# claim against the schema rather than against this paragraph):
#
#   * `severity_source` IS now written -- by `severity_reconcile.annotate_v2`
#     on the live parallel path since v1.24.0 -- and is declared in the v2
#     schema beside `tool_verdict`. No debt: it is produced.
#   * `source` IS declared in the v2 schema (five subfields, "Set by the
#     pipeline, not the model") AND listed in `prompts._NOT_PRODUCER_WRITTEN`,
#     so the contract already says the PIPELINE writes it -- and nothing on the
#     parallel path does. Measured: 0 of 80 findings across the four archived
#     parallel runs carry it, against every legacy run that does. That is a
#     REAL debt of exactly the shape this module exists to record, and it is
#     the `sandbox_audit.json` case again: a requirement excused into
#     invisibility. `sourcing.annotate_v2` now produces it (wired at
#     `parallel.py`, above the write), so it is asserted below.
#
# So the rule for adding anything below: the field must be DECLARED IN THE V2
# SCHEMA, and the condition under which it is owed must be stated. The schema is
# the contract; this is a check that the contract is kept.

@dataclass(frozen=True)
class FieldObligation:
    """A field owed on a finding, and when."""

    field: str
    #: The field whose presence makes this one owed. None means always.
    owed_when_present: str | None
    why: str

    def applies(self, finding: dict) -> bool:
        if self.owed_when_present is None:
            return True
        value = finding.get(self.owed_when_present)
        return bool(value if not isinstance(value, str) else value.strip())


FINDING_FIELDS: tuple[FieldObligation, ...] = (
    FieldObligation(
        "reproduction_valid", "reproduction",
        "whether the command we print actually RUNS. Measured over 523 "
        "archived commands: 60 (11.5%) exit 0 and 352 (67.3%) pass the static "
        "check then fail. Without the verdict a reader is handed a command "
        "that errors on first use, which reads as a broken tool"),
    FieldObligation(
        "quote_verified", "quote",
        "whether the quote we attribute to the paper is IN the paper. A quote "
        "we cannot locate must never be presented as the paper's words"),
    FieldObligation(
        "source", "tool_verdict",
        "the passage the CHECKED NUMBERS were read from. A finding backed by a "
        "validated tool call has a producing call, and that call carried the "
        "quote it read -- so a reader can be shown the paper's own words rather "
        "than the model's summary of them. Measured 2026-09-04 when the v2 "
        "producer was wired: 3 of 8 (apple_cider) and 1 of 8 "
        "(cerebrolysin_flow) tool-backed findings still do not join, because "
        "the calls behind them quote different passages and a guess would "
        "attach one row's evidence to another row's accusation"),
)


def unmet_field_obligations(findings: list[dict],
                            obligations=FINDING_FIELDS) -> list[dict]:
    """Findings that owe a field and do not carry it.

    Returns one row per (obligation, count) rather than per finding: the
    interesting number is how many of the applicable findings are missing it,
    because one is a bug and all of them is a disconnected pipeline stage.
    """
    out = []
    for ob in obligations:
        applicable = [f for f in findings if isinstance(f, dict) and ob.applies(f)]
        missing_it = [f for f in applicable if ob.field not in f]
        if missing_it:
            out.append({
                "field": ob.field, "owed_when": ob.owed_when_present,
                "n_applicable": len(applicable), "n_missing": len(missing_it),
                "why": ob.why,
                "example_finding_id": missing_it[0].get("finding_id"),
            })
    return out
