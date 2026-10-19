"""END the run when information KNOWN TO EXIST did not arrive.

Greg, 2026-08-13: "we should have failsafes within the pipeline for when
information that is known to exist fails to get passed along properly to the
next step... I can see the benefit of including (even if just as an optional
setting in the CLI) a true tripwire that ends the run when a catastrophic
failure of this sort presents itself."

EVERYTHING THAT EXISTED BEFORE THIS RECORDED AND NOTHING STOPPED. `handoff.audit`
runs offline and nothing calls it mid-run; `completeness.gate` computes `passed`
with `enforce=False` on purpose; `prepass` problems, undeclared inputs, the
computation audit and the stage-1 reconciliation are all written down and none
of them blocks. A catastrophic loss was a line in an artefact nobody had to read.

THE DISTINCTION THAT MAKES A TRIPWIRE SAFE, and it is the same one the
completeness gate got right: fire on WE KNOW THIS EXISTS AND IT DID NOT ARRIVE,
never on "coverage is low". Every condition below rests on POSITIVE evidence
that something is there -- a file the paper declares, a table the prepass
counted, an XML the directory contains. None of them fires because a number is
disappointing.

FALSE-POSITIVE RATE, MEASURED 2026-08-18 before any of this was wired in:
replayed the two report-stage conditions over every archived run on disk --
0 of 47 measurable runs would have been killed.

  A first version of that replay reported 4%, and was wrong in a way worth
  keeping. It keyed condition A on "report.json is absent" and fired on two
  runs that both had `messages.stage2.json` and a `report.md` -- stage 2 had
  worked perfectly; they simply predate the JSON report schema. CORRECTED
  2026-08-18: only ONE of them (10.1002--adbi.202300439) is genuinely
  pre-schema, both stages clean. The other, `benchmarks/paper_reviews/runs/apple_cider`, had BOTH
  STAGES KILLED BY THE BUDGET CAP -- a real failure I had written off. So the
  absence of that file is ambiguous across THREE situations, not two: an old
  artefact, a budget kill and an API error. The instrument
  read an ARTEFACT-FORMAT fact as an INFORMATION-LOSS fact, which is precisely
  the failure this module exists to catch, one level up. Those runs are now
  excluded as NOT MEASURABLE rather than scored in either direction.

AND THE LIMIT OF THAT NUMBER, which must travel with it: a condition that has
never fired has an UNMEASURED true-positive rate. 0/47 proves these do not fire
on healthy runs; it cannot prove they fire on a broken one, because no archived
run is broken in these particular ways. `tests/test_tripwire.py` supplies the
other half with synthetic breakage.

DEFAULT OFF: `--tripwire off|warn|kill`. `warn` prints loudly and continues, so
a condition can be watched on real runs before it is trusted with a paid job.

WHERE IT SITS, AND WHY THAT IS NOT REDUNDANT. The call is placed after the
supplement gate and before any paid stage. VERIFIED end to end 2026-08-18 on a
directory holding only `<article></article>`:

  plain run                 the supplement gate refuses first, exit 2, with a
                            better-worded message than this module would give

(2026-10-18: the gate's `--ok-if-supplementary-missing` override no longer
reaches the unreadable-article case -- that now refuses whatever is passed, so
the escape-hatch path this module once stood alone on is closed.) A condition that
never fires on the happy path is not dead; it is a backstop, and this is the
measurement that says which.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class Trip:
    """One condition, and what it saw."""
    id: str
    fired: bool
    #: What positive evidence says the information EXISTS. A trip with no
    #: `expected` is a trip firing on an absence, which this module forbids.
    expected: str = ""
    #: What arrived instead.
    got: str = ""
    message: str = ""
    #: True when the condition could not be evaluated. NOT a pass: an
    #: unevaluated check reported as clean is the defect this file is about.
    not_measured: bool = False

    def as_dict(self) -> dict:
        return {"id": self.id, "fired": self.fired, "expected": self.expected,
                "got": self.got, "message": self.message,
                "not_measured": self.not_measured}


def _declared_supplements_have_cells(paper_dir: Path) -> Trip:
    """A DECLARED supplement or dataset that produced zero extracted cells.

    Declaration is the positive evidence: somebody said this file is part of
    the paper and carries data. Zero cells out of it means either the file was
    unreadable or the extraction never ran, and both are losses.
    """
    from . import supplements as _supp
    from .extraction import docling_tables as _dl

    try:
        c = _supp.classify_inputs(paper_dir)
    except Exception as exc:  # noqa: BLE001
        return Trip("declared_supplement_no_cells", False, not_measured=True,
                    message=f"could not classify inputs: {exc}")
    declared = [f for f in (c.get("files") or [])
                if f.get("role") in ("supplement", "dataset")
                and str(f.get("name", "")).lower().endswith(".pdf")]
    if not declared:
        return Trip("declared_supplement_no_cells", False,
                    expected="no supplementary PDF is declared",
                    got="nothing to check")
    empty = []
    for f in declared:
        p = paper_dir / f["name"]
        try:
            r = _dl.extract_pdf_tables(p, allow_extract=False)
        except Exception:  # noqa: BLE001
            continue
        if r.get("error"):
            continue  # unread is a different condition; do not double-count
        n = sum(len(t.get("cells") or t.get("data") or []) for t in (r.get("tables") or []))
        if n == 0:
            empty.append(f["name"])
    return Trip(
        "declared_supplement_no_cells", bool(empty),
        expected=f"{len(declared)} declared supplementary PDF(s)",
        got=f"{len(empty)} produced zero table cells: {', '.join(empty[:4])}",
        message=("A file declared part of this paper yielded no table cells. "
                 "It was declared because it carries data, so this is a loss, "
                 "not an empty file." if empty else ""))


def _tables_reach_the_manifest(paper_dir: Path) -> Trip:
    """The article's tables enumerate > 0 and the manifest receives 0."""
    from . import completeness as _c
    from . import prepass as _pre
    try:
        tables = list(_pre.paper_tables(paper_dir, include_supplements=True))
        items = (_c.build_manifest(paper_dir).get("items") or [])
    except Exception as exc:  # noqa: BLE001
        return Trip("tables_lost_before_manifest", False, not_measured=True,
                    message=f"could not evaluate: {exc}")
    fired = bool(tables) and not items
    return Trip(
        "tables_lost_before_manifest", fired,
        expected=f"{len(tables)} table(s) enumerated by prepass",
        got=f"{len(items)} manifest item(s)",
        message=("Tables were found and the manifest received nothing, so every "
                 "downstream check will see a paper with no tables."
                 if fired else ""))


def _xml_paper_has_text(paper_dir: Path) -> Trip:
    """A paper with publisher XML whose `paper_text` comes back empty."""
    from .extraction.jats import paper_text
    xmls = list(Path(paper_dir).glob("*.xml"))
    if not xmls:
        return Trip("xml_present_but_no_text", False,
                    expected="no publisher XML", got="nothing to check")
    try:
        text = paper_text(paper_dir)
    except Exception as exc:  # noqa: BLE001
        return Trip("xml_present_but_no_text", False, not_measured=True,
                    message=f"could not read: {exc}")
    fired = not (text or "").strip()
    return Trip(
        "xml_present_but_no_text", fired,
        expected=f"publisher XML present ({xmls[0].name})",
        got=f"{len((text or '').strip())} characters of paper text",
        message=("The publisher's own marked-up full text is on disk and the "
                 "reader returned nothing from it."
                 if fired else ""))


def _stage2_carried_something(findings: list, report: dict | None) -> Trip:
    """Stage 1 produced findings and stage 2 carried none of them."""
    if report is None:
        return Trip("stage2_carried_nothing", False, not_measured=True,
                    message="no structured report: not measurable, not a pass")
    ed = report.get("findings") or []
    fired = bool(findings) and not ed
    return Trip(
        "stage2_carried_nothing", fired,
        expected=f"{len(findings)} sweep finding(s)",
        got=f"{len(ed)} finding(s) in the report",
        message=("The sweep wrote findings down and the report carried none of "
                 "them forward." if fired else ""))


def _no_stage_reported_an_error(run_meta: dict | None) -> Trip:
    """A stage told us it failed. The least ambiguous signal there is.

    FOUND BY A REAL FAILURE 2026-08-18, hours after this module shipped. A
    Sonnet repeat on the Stapel paper lost its API connection mid-response: the
    sweep finished cleanly with 14 findings, the editorial stage recorded
    `is_error: True, error_subtype: "api_error"`, no `report.json` was written,
    and the run billed $5.18.

    `_stage2_carried_something` returned NOT MEASURED on it. That was the
    correct call for the case it was designed against -- two archived runs whose
    stage 2 worked fine and simply predate the JSON report schema, where firing
    would have invented a false-positive rate. But it means the absence of a
    report is ambiguous between an old artefact, a budget kill and an API error,
    and a real failure walked straight through. Replayed over the archive, this
    condition fires on exactly 1 of 49 runs -- `apple_cider`, both stages
    `error_max_budget_usd` -- and that is a TRUE positive, not a false one.

    `is_error` is not ambiguous. The stage itself is asserting that it failed,
    which is positive evidence of exactly the kind this module requires, and it
    distinguishes the two cases the missing file cannot.
    """
    stages = ((run_meta or {}).get("stages") or {})
    if not stages:
        return Trip("stage_reported_an_error", False, not_measured=True,
                    message="no run_meta stages: not measurable, not a pass")
    failed = [n for n, st in stages.items()
              if isinstance(st, dict) and st.get("is_error")]
    if not failed:
        return Trip("stage_reported_an_error", False,
                    expected=f"{len(stages)} stage(s)", got="none reported an error")
    detail = ", ".join(
        f"{n} ({(stages[n] or {}).get('error_subtype') or 'unspecified'})"
        for n in failed)
    return Trip(
        "stage_reported_an_error", True,
        expected=f"{len(stages)} stage(s) to complete",
        got=f"{len(failed)} reported an error: {detail}",
        message=("A stage recorded its own failure. Whatever it was working on "
                 "did not arrive, and the run was billed regardless."))


#: How many output tokens a NON-PRIMARY model may emit before we stop calling it
#: housekeeping. MEASURED 2026-08-18 across 40 archived stage transcripts:
#: claude-haiku-4-5 never exceeded 32 output tokens, on inputs from 800 to
#: 36,000 tokens. 200 is far above that ceiling and far below anything that
#: could be a conversation summary, which would run to thousands.
_SECONDARY_MODEL_TOKEN_CEILING = 200


def _no_secondary_model_wrote_content(run_meta: dict | None) -> Trip:
    """A model other than the primary one produced real output.

    WHY THIS EXISTS. Greg, 2026-08-18: "my concern here is that the Haiku model
    that is dispatched to perform a task might do a poor job and supply
    incorrect information to the pipeline."

    Investigated and, on the evidence, not happening: `claude-haiku-4-5` is
    invoked and billed on every run, but nothing it produces reaches the
    pipeline. It appears in 0 of 156 assistant messages, only in the final
    billing rollup, and its output never exceeded 32 tokens across 40 runs.
    See docs/HAIKU_IN_THE_LOOP.md.

    THE CHECK EXISTS FOR THE CASE THAT EVIDENCE COULD NOT RULE OUT. What the CLI
    sends a secondary model, and what it does with the answer, happen inside the
    CLI. If one were ever used to SUMMARISE a long conversation, that summary
    would re-enter the main model's context and a poor one would degrade the
    analysis -- exactly the failure described. No archived run shows it, but
    every archived run fits in context; a longer paper is where it would appear.

    Output tokens are the signature that separates the two. Housekeeping writes
    a sentence. A summary that reached the model writes thousands.
    """
    stages = ((run_meta or {}).get("stages") or {})
    if not stages:
        return Trip("secondary_model_wrote_content", False, not_measured=True,
                    message="no run_meta stages: not measurable, not a pass")
    offenders: list[str] = []
    measured = 0
    for name, st in stages.items():
        if not isinstance(st, dict):
            continue
        usage = st.get("model_usage") or {}
        primary = st.get("primary_billed_model")
        for model, u in usage.items():
            if not isinstance(u, dict) or "outputTokens" not in u:
                continue          # pre-dates the field; NOT evidence of absence
            measured += 1
            if model == primary:
                continue
            if int(u.get("outputTokens") or 0) > _SECONDARY_MODEL_TOKEN_CEILING:
                offenders.append(
                    f"{name}: {model} emitted {u['outputTokens']} output tokens")
    if not measured:
        return Trip("secondary_model_wrote_content", False, not_measured=True,
                    message=("no per-model output-token record in this run "
                             "(it predates the field), so whether a secondary "
                             "model wrote content is UNKNOWN"))
    if offenders:
        return Trip(
            "secondary_model_wrote_content", True,
            expected=f"secondary models under {_SECONDARY_MODEL_TOKEN_CEILING} "
                     "output tokens (housekeeping)",
            got="; ".join(offenders),
            message=("A model other than the one this run was commissioned from "
                     "produced substantial output. If that output was a summary "
                     "folded back into the analysis context, the review rests "
                     "partly on a model nobody chose. Inspect "
                     "messages.stage*.json before trusting the findings."))
    return Trip("secondary_model_wrote_content", False,
                expected=f"{measured} model-usage record(s) checked",
                got="every secondary model stayed within the housekeeping ceiling")


def check_run(run_meta: dict | None) -> list[Trip]:
    """Conditions readable from `run_meta.json` after the stages have run."""
    return [_no_stage_reported_an_error(run_meta),
            _no_secondary_model_wrote_content(run_meta)]


#: Conditions evaluated BEFORE the expensive stage. Firing after stage 2 has run
#: wastes the money the tripwire exists to protect, so these are the ones that
#: matter most.
PREFLIGHT_CONDITIONS: tuple[Callable[[Path], Trip], ...] = (
    _declared_supplements_have_cells,
    _tables_reach_the_manifest,
    _xml_paper_has_text,
)


def check_preflight(paper_dir: str | Path) -> list[Trip]:
    d = Path(paper_dir)
    return [fn(d) for fn in PREFLIGHT_CONDITIONS]


def check_report(findings: list, report: dict | None) -> list[Trip]:
    return [_stage2_carried_something(findings or [], report)]


def summarise(trips: list[Trip]) -> dict:
    fired = [t for t in trips if t.fired]
    unmeasured = [t for t in trips if t.not_measured]
    return {
        "tripped": bool(fired),
        "n_conditions": len(trips),
        "n_fired": len(fired),
        # Reported separately and never folded into a pass: see the module note.
        "n_not_measured": len(unmeasured),
        "fired": [t.as_dict() for t in fired],
        "conditions": [t.as_dict() for t in trips],
        "note": (
            "; ".join(f"{t.id}: expected {t.expected}, got {t.got}" for t in fired)
            if fired else
            f"no condition fired ({len(unmeasured)} not measurable)"),
    }


class TripwireError(RuntimeError):
    """Raised when a condition fires and the tripwire is armed to kill."""


def enforce(trips: list[Trip], *, mode: str = "off") -> dict:
    """`off` records, `warn` records loudly, `kill` raises.

    Returns the summary either way, so the artefacts carry what fired even on a
    run that was allowed to continue -- a tripped run must be diagnosable rather
    than merely dead.
    """
    s = summarise(trips)
    if s["tripped"] and mode == "kill":
        raise TripwireError(
            "TRIPWIRE: information known to exist did not arrive. "
            + s["note"]
            + ". Run `metascience handoff-audit` on this paper for the detail, "
              "or re-run without --tripwire to proceed anyway.")
    return s
