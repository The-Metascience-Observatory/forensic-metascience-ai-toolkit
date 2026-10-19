# Copy-paste evaluation protocol

The acquisition catalog is a list of reported concerns, **not ground truth**.
Science Detective itself says some reports may not establish genuine errors
([source list](https://www.sciencedetective.org/about/)). Issue-level verification
requires the original source bytes, affected cells and independent evidence.

## Download first

Keep filenames unchanged. The complete prioritized list, exact version IDs,
file IDs and published hashes are in [DOWNLOADS.md](DOWNLOADS.md) and the
machine-readable [catalog](sciencedetective_catalog.json).

1. [Parkinson's mouse study](https://datadryad.org/dataset/doi:10.5061/dryad.4mp6h):
   **MouseTreatmentMotorFunction.xlsx** first, then HumanizedMotorFunction.xlsx
   and SynucleinandInflammation.xlsx.
2. [Clonal fish](https://datadryad.org/dataset/doi:10.5061/dryad.td3sj): original
   **Bierbach et al clonal molly behav development_data for deposit.xlsx**, March
   9, 2018 (version 16385), and corrected
   **Clonal_molly_behavioral_individuality_for_deposit_SL_corrected.csv**, February
   5, 2026 (version 423653). Dryad's changelog describes body-size values assigned
   to the wrong IDs during a join. That confirms an assignment error at study
   level; the exact affected cells still require inspection. It is not automatically
   an exact-duplication positive. Preserve the corrected analysis README/code for
   human verification, separately from blinded AI input.
3. Proceed through the remaining catalog priorities, preferring supported files
   with available source/correction evidence. Preserve every dataset version;
   repository withdrawal/retraction status is recorded separately from issue labels.

Use the standalone `copy-paste-dataset import` command with this catalog. It
matches local files by published hashes; no login or download automation is
required. It will deliberately list missing versions/files as unavailable.

## Label contract

Start with `labels.pending.jsonl`. A paper/version record contains `paper_id`,
`family_id`, `split`, `verification_status`, `source_sha256` keyed by original
filename, and `issues`. Each issue needs an immutable `id`, `kind`, status,
`evidence_url`, `cells`, reviewer, verification date and explanation. Cells use
`file`, `sheet`, and Excel-style `cell` (optional `source_sha256`). For example:

```json
{"id":"issue-1","kind":"row_pair","verification_status":"confirmed_error","evidence_url":"https://publisher.example/correction","cells":[{"file":"data.xlsx","sheet":"Data","cell":"D38"},{"file":"data.xlsx","sheet":"Data","cell":"D92"}],"reviewer":"reviewer name","verified_at":"YYYY-MM-DD","explanation":"Source-specific account of the error"}
```

Use `confirmed_error` only with error evidence, `verified_duplication` for verified
cell equality still requiring interpretation, `legitimate_repetition` for a
supported innocent explanation, `unresolved_concern` for a report not settled by
evidence, and `unavailable_evidence` for inaccessible source data. A verified
negative paper requires a complete human review of the relevant scope; corrected
files are not presumed entirely error-free. Record assignment errors as
`misassignment`, near-duplicate edits as `near_duplicate_edit`; current exact-match
coverage for these is unsupported. Candidate recall measures localized matching,
not detecting any unrelated anomaly somewhere in a paper.

Recall counts issue/version instances, not independent families. Do not label
metadata-only versions with identical source bytes as independent replications;
report their family grouping and repeated bytes explicitly.

Keep original/corrected versions together under `family_splits.json` (seed
20260910, approximately 30% held out). Do not tune thresholds after inspecting
held-out labels. Synthetic controls are development checks and never count as
independent real-paper families. The initial engineering changes keep scoring
thresholds fixed.

## Comparison sample and review

`comparison_frame.json` records a frozen convenience frame drawn from bounded
public Dryad API listing pages, its retrieval time and acquisition failures.
`comparison_sample.json` selects 100 independent paper families with seed 20260910,
excluding the known Science Detective families. Sampling balances recorded
format/domain strata after seeded shuffling. Unannotated domains remain
`unclassified`; the frame is not representative of all scientific literature or
of all Dryad data, and provides no prevalence estimate.

All comparison papers start **unlabelled**. Download/import the pinned versions
using `comparison_catalog.json`; study context must be supplied separately. Review
every flagged case and 20 seeded randomly selected unflagged papers. The benchmark
command writes a candidate review queue and the unflagged sample. Human review
rows are JSONL with `run_id`, `candidate_id`, `label` (`confirmed_error`,
`legitimate_repetition` or unresolved), `reviewer`, rationale and evidence. Pass
this ledger via `--reviews`; a Grok judgment never becomes the human truth label.
Partial coverage is not an eligible negative review.

## Three-way comparison

Freeze the baseline code before evaluating. Use identical source hashes for the
legacy detector, the engineering changes and engineering plus Grok. The legacy
API runs each file separately, so cross-file matching is a documented new scope.
Keep all raw candidates even when AI excludes them. Record reader limits,
normalization, prompt/model, input and code hashes in every run.

The script below was deleted 2026-10-16 with `examples/`; recover it from git
history to rerun.

```sh
PYTHONPATH=copy_paste_detector/src python examples/evaluate_copy_paste.py \
  --output .copy_paste_evaluation/acceptance \
  --baseline-dir .copy_paste_evaluation/baseline --live-grok --full-grok
copy-paste-benchmark --labels reviewed-labels.jsonl \
  --run-index runs/index.json --reviews human-reviews.jsonl --output score
```

The script generates 16 synthetic papers with known planted cells, legitimate
repetition and independent controls, tests 1/2/4/8 process scheduling and resume,
and optionally launches six live Grok paper jobs (two repeats of three contexts).
It measures scheduling overlap separately from model-output agreement. The frozen
baseline used here is the standalone package at commit
`df8be724703c5d0d2c519a2de4aa1136a1a2c201`; extract its
`copy_paste_detector/src/copy_paste_detector/` directory into the baseline folder.
See `EVALUATION.md` for measured results and limits.

Report acquisition states by file and paper, candidate recall over **all verified
issues** and over **available supported issues**, AI retention and unresolved-call
coverage, precision over explicitly human-reviewed candidates and total review
burden. A zero denominator is unavailable. Report development and held-out
families separately; a pooled result must not hide the split. No real-paper
precision or recall may be reported before the source data and labels exist.
