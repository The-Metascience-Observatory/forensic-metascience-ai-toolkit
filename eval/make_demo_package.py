"""Build the three-paper demonstration package, reproducibly.

WHY THIS IS A COMMITTED SCRIPT AND NOT A SHELL SESSION
------------------------------------------------------
The first version of this package was assembled by an ad-hoc script that lived
only in a terminal. A hostile review caught it immediately: the blinded
directories passed every audit, and no code in the repository could produce
them. "Our artifacts are sound" is not a claim you can make about a process
nobody can re-run. Everything here goes through committed functions, and this
file is the record of which ones.

WHAT THE THREE PAPERS ARE FOR
-----------------------------
1. FRAUD, BLINDED -- a retracted paper whose misconduct was established by
   INVESTIGATION, not by statistics, so detecting it is not circular. Its ground
   truth predicts a specific arithmetic failure in advance: undisclosed
   participant exclusions mean the reported means cannot be consistent with the
   stated N.
2. CONTROL, BLINDED -- a non-retracted paper with plenty of checkable material.
   The exhibit here is a NULL result. A tool that only ever finds problems is a
   false-positive dispenser, and the null is the harder thing to demonstrate.
3. LIVE PAPER, UNBLINDED -- from the working corpus, carrying two hand-verified
   internal inconsistencies. Not blinded because nothing about it is being
   concealed: it is a real review of a paper we are actually reviewing.

WHAT THIS PACKAGE MAY AND MAY NOT CLAIM
---------------------------------------
It may show that a blinded run finds a real arithmetic problem, and that a
blinded control comes back clean. It may NOT be read as a detection RATE.
Fifteen of the thirty fraud papers in this corpus have no full text at all,
against none of the forty-eight controls, so "empty blinded directory" alone
predicts the label at 50% sensitivity and zero false positives (task #135). One
paper is an illustration; a rate would need a corpus whose two classes were
acquired the same way.
"""
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

from metascience_agent import blinding
from metascience_agent.evaluation.corpus_run import resolve_paper_dir

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "eval" / "ground_truth" / "manifest.csv"
PAPERS = REPO / "eval" / "ground_truth" / "papers"

#: doi -> why it is in the package. Both are non-empty in the corpus (checked).
BLINDED = {
    "10.1038/srep12770":
        "FRAUD. Retracted for undisclosed participant exclusions, established by "
        "investigation rather than by any statistical test, so detecting it is "
        "not circular. Ground truth predicts the signature in advance: 16 "
        "undisclosed exclusions mean the reported means cannot be consistent "
        "with the stated N.",
    "10.3349/ymj.2008.49.4.553":
        "CONTROL. Not retracted, an RCT with nine tables, a fair design match "
        "for the fraud paper. The exhibit is a NULL -- plenty of checkable "
        "material and, if the toolkit is calibrated, nothing to report -- which "
        "is the harder thing to demonstrate and the one that answers 'is this "
        "just a false-positive dispenser'. Chosen over a 10-table alternative "
        "because that one CITES SUPPLEMENTARY MATERIAL WE DO NOT HOLD: a null "
        "on a paper we could not fully see is a weak null, and a reader would "
        "be right to say we found nothing because we did not look. This one's "
        "supplement gate proceeds with no override. Preferred over a 2026 paper "
        "with more tables because eighteen years unretracted is evidence; not "
        "yet challenged is not.",
}


def build(dest: Path) -> dict:
    """Materialize the blinded half of the package. Returns the manifest."""
    rows = {r["doi"]: r for r in csv.DictReader(MANIFEST.open(encoding="utf-8"))}
    blinded_root = dest / "blinded"
    if blinded_root.exists():
        shutil.rmtree(blinded_root)
    blinded_root.mkdir(parents=True)

    key: dict[str, dict] = {}
    for doi, why in BLINDED.items():
        src = resolve_paper_dir(PAPERS, doi)
        if src is None:
            raise SystemExit(
                f"{doi} is not in {PAPERS}. The demo package names its papers "
                "explicitly, so a missing one is a broken package, not a "
                "smaller one -- refusing rather than shipping a short deck."
            )
        # The exact chain `evaluation/corpus_run.run_paper` uses, in the same
        # order, so the package cannot be sound while the pipeline is not.
        bp = blinding.materialize(src, blinded_root)
        identifiers = blinding.derive_identifiers(src)
        counts = blinding.scrub_identity(bp.blinded_dir, identifiers)
        leaks = blinding.identity_residue(bp.blinded_dir, identifiers)
        markers, review = blinding.verify(bp.blinded_dir)
        if leaks or markers:
            raise SystemExit(
                f"REFUSING to package {doi}: {len(leaks)} identity leak(s), "
                f"{len(markers)} marker(s). First: {(leaks + markers)[0][:160]}"
            )
        key[bp.paper_id] = {
            "doi": doi, "label": rows[doi]["label"], "why_included": why,
            "how_established": rows[doi]["how_established"],
            "expected_signature": rows[doi]["expected_statistical_signature"],
            "blinding": {
                "identifiers_derived_from_source": len(identifiers),
                "scrub_counts": counts,
                "identity_residue": 0,
                "retraction_markers": 0,
                "flagged_for_human_review": len(review),
            },
        }
    # The key is what makes the run scoreable afterwards, and is exactly what a
    # reader of the blinded package must not have. Written OUTSIDE it.
    (dest / "UNBLINDING_KEY.json").write_text(
        json.dumps(key, indent=2), encoding="utf-8")
    return key


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "funder_demo_2026-08-10"
    out.mkdir(parents=True, exist_ok=True)
    k = build(out)
    for pid, meta in k.items():
        b = meta["blinding"]
        print(f"{pid}  {meta['label']:8} identifiers={b['identifiers_derived_from_source']:>4} "
              f"residue={b['identity_residue']} markers={b['retraction_markers']} "
              f"review={b['flagged_for_human_review']}")
    print(f"\nkey -> {out / 'UNBLINDING_KEY.json'}  (NOT part of the shared package)")
