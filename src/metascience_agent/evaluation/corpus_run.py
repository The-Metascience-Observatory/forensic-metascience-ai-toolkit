"""The missing middle: blind the corpus, run what can honestly run, emit cells.

Two halves of a measurement existed and could not reach each other.

  `blinding.py`   -- 403 lines, materializes a label-free copy of a paper.
                     ZERO importers. Every "blinded" run to date was unblinded,
                     because nothing ever called it.
  `evaluation/corpus.py` -- the preregistered scorer, reads `cells.jsonl`.
                     NOTHING IN THE REPO PRODUCES `cells.jsonl`. A consumer with
                     no producer; the preregistered evaluation could not run
                     end to end.

A producer with no consumer and a consumer with no producer, in the same
package, both written this week. This module is the connection.

WHAT IT WILL REPORT, AND WHY THAT IS THE POINT
----------------------------------------------
Almost nothing runs. GRIM, GRIMMER, SPRITE and DEBIT all need a variable
declaration -- what kind of quantity is this, on what scale -- and no human has
written declarations for this corpus. Baseline similarity needs a declared
design. Duplicate detection needs a judgement about which rows describe the same
sample. Running any of them on guessed declarations is how nearly every false
accusation in this project was produced, so they REFUSE, by name, with a reason.

That is not a failure of the run, it is the measurement. `PREREGISTRATION.md`
section 8 already fixed what to conclude: if fewer than a quarter of eligible
cells can be evaluated, the study is a parsing result and the forensic endpoints
are suppressed. This module is what lets that conclusion be reached from data
rather than asserted.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .. import blinding
from ..paper_ids import doi_dirname
from ..registry import BY_NAME

#: manifest tool name -> (registry tool, why it cannot run without a human)
#:
#: The manifest's vocabulary was written before the toolkit's, and they do not
#: agree. `digit_preference` names a technique THIS REPOSITORY DOES NOT
#: IMPLEMENT -- there is no digit-preference, terminal-digit or Benford tool in
#: the registry. The pre-registration counted scoreable cells for it anyway,
#: because I derived the vocabulary from the manifest without checking the tools
#: existed. Cells for it can never be anything but refusals.
REFUSALS = {
    "grim": "needs a variable declaration (integer-valued? what scale?) and an n; "
            "running it on a guessed declaration is the project's single largest "
            "source of false accusations",
    "grimmer": "needs a variable declaration and an n, as GRIM does",
    "sprite": "needs a declared scale range; SPRITE on invented bounds reconstructs "
              "samples the paper never claimed",
    "debit": "needs a declared binary variable; applied to anything else it accuses "
             "ordinary data",
    "baseline_similarity": "needs a declared design (parallel-group? cluster? "
                           "crossover?) and a baseline table identified as such",
    "duplication": "needs a judgement about which rows describe the same sample; "
                   "tables that legitimately restate a baseline duplicate by "
                   "construction",
    "digit_preference": "NOT IMPLEMENTED in this toolkit. The manifest's tool "
                        "vocabulary names it; the registry has no digit-preference, "
                        "terminal-digit or Benford check. Cells for it are "
                        "unscoreable, not merely unevaluated.",
}


def paper_slug(doi: str) -> str:
    """The directory name a DOI is filed under in the ground-truth corpus.

    Lowercased, because the script that CREATED every directory lowercases
    (`eval/ground_truth/tools/fetch_paper.py:slug`). Three consumers did not,
    and the mismatch stayed invisible for as long as every manifest DOI
    happened to be lowercase already. Two are not: `10.2147/TCRM.S15812` and
    `10.2147/TCRM.S43811` sit on disk as `10.2147--tcrm.s15812`, so both
    dropped out of every corpus measurement -- 2 of the 30 fraud papers, and
    2 of the 15 fraud XMLs, absent from a run that still reported itself
    complete. DOIs are case-insensitive by specification (ISO 26324), so the
    case a publisher prints carries no information and must never decide
    whether a paper is found.

    Delegates to `paper_ids.doi_dirname`, which is the same rule stated where
    the producer of these directories can be pointed at it. Two independent
    copies of a naming convention drift, and the drift is invisible until a
    paper silently drops out of a corpus measurement -- which is the exact
    failure described above.
    """
    return doi_dirname(doi)


def resolve_paper_dir(papers_root: Path, doi: str) -> Path | None:
    """The paper's directory, or None if the corpus does not hold it.

    Canonical name first, then a case-insensitive match against what is
    actually on disk, so a corpus filed with case preserved resolves too: the
    point is to stop case deciding presence, in either direction.

    The fallback SCANS rather than restating the slash-to-dashes rule a second
    time (this sentence deliberately does not spell it, because the detector
    reads source lines and a comment quoting the pattern trips it -- the test
    splits its own needle for the same reason). Writing that mapping outside
    `paper_ids` is what
    `test_nobody_spells_the_mapping_themselves` forbids, and for a good
    reason -- two copies of the rule drift, and the drift shows up as a paper
    silently missing from a corpus measurement. Scanning is also strictly more
    capable than the old as-printed attempt: it matches ANY case variant on
    disk, not just the one the manifest happened to use.
    """
    canonical = papers_root / paper_slug(doi)
    if canonical.exists():
        return canonical
    want = paper_slug(doi)
    try:
        for child in papers_root.iterdir():
            if child.name.lower() == want:
                return child
    except OSError:
        return None
    return None


def _paper_text(blinded_dir: Path) -> str:
    """Everything readable in the blinded directory, concatenated.

    Deliberately simple: blinded materialization already restricted this to
    scrubbed, allowlisted text, so anything present here is safe to read.
    """
    parts = []
    for p in sorted(blinded_dir.rglob("*")):
        if p.is_file() and p.suffix.lower() in {".md", ".txt", ".xml"}:
            parts.append(p.read_text(encoding="utf-8", errors="replace"))
    return "\n\n".join(parts)


def run_paper(doi: str, source: Path, blinded_root: Path) -> list[dict]:
    """One paper -> one cells.jsonl row per manifest tool."""
    # MARKER-BLINDING IS NOT IDENTITY-BLINDING, and this function did only the
    # first. `materialize` removes retraction notices and leaves the DOI, the
    # authors, the affiliations and the journal, so every "blinded" run this
    # function has produced was blind to the NOTICE and never to the PAPER.
    # MEASURED across all 78 corpus papers before these three lines existed:
    # `identity_residue` fired on 63 of 63 non-empty papers, 183 hits.
    #
    # Identifiers are derived from the SOURCE rather than read off the manifest,
    # so a field nobody thought to record cannot silently exempt itself -- that
    # exact hole left affiliation cities in the text while the audit reported
    # clean. See `blinding.derive_identifiers`.
    bp = blinding.materialize(source, blinded_root)
    identifiers = blinding.derive_identifiers(source)
    blinding.scrub_identity(bp.blinded_dir, identifiers)
    leaks = blinding.identity_residue(bp.blinded_dir, identifiers)
    rows: list[dict] = []

    def row(tool, evaluated, severity=None, n=0, note=""):
        rows.append({"doi": doi, "tool": tool, "evaluated": bool(evaluated),
                     "max_severity": severity, "n_findings": n, "note": note,
                     "paper_id": bp.paper_id})

    # `bp.clean`, not `bp.excluded`. The two differ exactly on the review tier,
    # and `BlindedPaper.clean` exists to say so: "a review-tier hit does not mean
    # the paper is contaminated, only that nobody has looked; treating
    # unexamined as clean is how the default silently becomes inclusion."
    #
    # Gating on `excluded` alone made `clean` a property with ZERO consumers and
    # shipped the exact default the docstring forbids. It has not leaked yet --
    # review hits are 3 fraud against 5 control, symmetric -- but "no leak so
    # far" is not the property that was promised. A paper needs a logged human
    # decision to be scored, and no such log exists, so the honest state is a
    # refusal naming what a human would have to look at.
    if not bp.clean:
        why = (f"blinding failure: {bp.residual[0][:120]}" if bp.excluded
               else f"awaiting human review of: {bp.needs_review[0][:100]}")
        for tool in REFUSALS | {"statcheck": ""}:
            row(tool, False, note=why)
        return rows

    # An identity leak is a blinding failure exactly as a marker leak is: the
    # measurement it would feed is not one we are entitled to report. Refuse the
    # paper rather than score it, which is what PREREGISTRATION.md section 3.2
    # says to do and what `bp.excluded` already does for markers.
    if leaks:
        for tool in REFUSALS | {"statcheck": ""}:
            row(tool, False, note=f"identity leak: {leaks[0][:120]}")
        return rows

    text = _paper_text(bp.blinded_dir)
    for tool, why in REFUSALS.items():
        row(tool, False, note=why)

    # statcheck is the ONE technique that needs no declaration: it finds APA
    # statistics in running text and recomputes them. Its yield on this corpus
    # is already known to be poor -- the format is psychology-shaped and the
    # corpus is medicine-heavy -- which is itself the finding.
    if not text.strip():
        row("statcheck", False, note="no machine-readable text in the blinded copy "
                                     "(PDF-only paper; blinding ships no PDF because "
                                     "page watermarks are unscrubbable pixels)")
        return rows
    try:
        res = BY_NAME["statcheck"].call({"text": text[:400_000]})
    except Exception as exc:  # a crash is a refusal, never a clean pass
        row("statcheck", False, note=f"statcheck raised: {type(exc).__name__}")
        return rows
    if not res.get("success"):
        row("statcheck", False, note=str(res.get("error") or "statcheck declined")[:160])
        return rows
    found = int(res.get("stats_found") or 0)
    if not found:
        row("statcheck", True, "consistent", 0,
            note="ran; no APA-format statistic present to check")
        return rows
    errs = int(res.get("errors_found") or 0)
    dec = int(res.get("decision_errors") or 0)
    # A decision error changes what the paper CLAIMS; a consistency error does
    # not. Neither is `impossible`: statcheck cannot see rounding conventions,
    # one- vs two-tailed, or a correction the authors applied silently.
    sev = "highly_suspicious" if dec else ("suspicious" if errs else "consistent")
    row("statcheck", True, sev, errs + dec, note=f"{found} statistics recomputed")
    return rows


def run_corpus(manifest: Path, papers_root: Path, out_dir: Path,
               limit: int | None = None) -> dict:
    """Blind every paper, run what can run, write cells.jsonl beside a report."""
    out_dir.mkdir(parents=True, exist_ok=True)
    blinded_root = out_dir / "blinded"
    with open(manifest, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if limit:
        rows = rows[:limit]

    cells, blind_reports, missing = [], [], []
    for r in rows:
        # `resolve_paper_dir`, not a bare `root / doi_dirname(...)`: it tries
        # the DOI as PRINTED before the canonical slug, so a corpus filed with
        # case preserved resolves too. The rule it canonicalises with is
        # `paper_ids.doi_dirname`, the producer's own convention.
        d = resolve_paper_dir(papers_root, r["doi"])
        if d is None:
            missing.append(r["doi"])
            continue
        cells += run_paper(r["doi"], d, blinded_root)
        blind_reports.append(blinding.materialize(d, blinded_root).report())

    cells_path = out_dir / "cells.jsonl"
    cells_path.write_text("".join(json.dumps(c) + "\n" for c in cells), encoding="utf-8")
    (out_dir / "blinding_report.json").write_text(
        json.dumps(blind_reports, indent=2), encoding="utf-8")

    evaluated = sum(1 for c in cells if c["evaluated"])
    return {
        "papers": len(rows) - len(missing),
        "papers_missing_on_disk": missing,
        "cells": len(cells),
        "evaluated": evaluated,
        "coverage": evaluated / len(cells) if cells else 0.0,
        "blinding_excluded": sum(1 for b in blind_reports if b["excluded"]),
        "blinding_needs_review": sum(1 for b in blind_reports
                                     if b["needs_review"] and not b["excluded"]),
        "cells_path": str(cells_path),
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[3]
    ap.add_argument("--manifest", type=Path,
                    default=root / "eval" / "ground_truth" / "manifest.csv")
    ap.add_argument("--papers", type=Path,
                    default=root / "eval" / "ground_truth" / "papers")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args(argv)
    summary = run_corpus(a.manifest, a.papers, a.out, a.limit)
    print(json.dumps(summary, indent=2))
    print("\nScore it with:\n  python -m metascience_agent.evaluation.corpus "
          f"{summary['cells_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
