# Standalone copy-paste evaluation — 2026-09-10

The standalone detector, process-parallel batch runner, Grok adjudication, dataset
import and workbench integration are implemented. The engineering checks below
use **synthetic data**. Real-paper precision and recall remain unavailable until
the downloaded files and issue-level labels are verified.

## How detection works

Readers retain source grids, numeric cells, labels and units. Applicability guards
remove or cap IDs, constants, telemetry, low-cardinality collisions, derived values
and repeated-measure structures. An inverted value/column index proposes matching
rows. Exact adjacent sequence tuples propose runs, then direct comparisons verify
them. Isolated repeated values form weaker candidates. Final context caps apply
before any AI review. Scores are heuristics, not probabilities of misconduct.

The historical single-file API and CLI remain compatible. Paper batches add a
shared comparison space within each paper, with explicit source names/checksums.
Cross-file comparisons require equal unique headers including units. Identical
file bytes count as alternate deliveries. The existing scoring thresholds are
unchanged; coverage, adjacency, evidence retention and cross-file scope changed.

Each paper runs in a separate process, default four workers capped by available
CPUs. Grok calls are asynchronous, default concurrency two, in fresh temporary
working directories. Evidence is bounded, JSON decisions validated, citations
checked against supplied text, and missing/truncated context forces uncertainty.
Call failures, timeouts and exhausted attempted-call budgets stay unresolved.
Grok cannot change raw evidence or increase the detector's severity ceiling.

## Frozen synthetic comparison

Source: `examples/evaluate_copy_paste.py` (deleted 2026-10-16 with examples/; recover it from git history), seed **20260910**. Sixteen paper jobs:
eleven with a known planted duplication issue, four independent random controls,
and one deliberately repeated baseline measurement with explicit study context.
One job has two files. This small constructed suite tests engineering behavior,
not real-world operating accuracy or prevalence.

The baseline package was verified byte-for-byte against git commit
`df8be724703c5d0d2c519a2de4aa1136a1a2c201`. It ran the historical API separately on
each file with its 5,000-pair budget. The fixtures never exhausted that budget.
Cross-file comparison was absent from that baseline; the wide-sheet fixture
exceeded its 100-column read limit. Raw outputs and input hashes were retained.

| Measurement | Frozen baseline | Engineering | Engineering + Grok |
|---|---:|---:|---:|
| Planted issues matched at labelled cells | 9 / 11 | 11 / 11 | 11 / 11 |
| Raw candidate groups preserved | 16 | 18 | 18 |
| Verified negative fixtures with no detector flag | 4 / 5 | 4 / 5 | 4 / 5 |
| AI-retained planted issues | not run | not run | 11 / 11 |
| AI decisions | not run | not run | 17 retain; 1 exclude |
| True synthetic candidates among all reviewed candidates | not separately reviewed | 17 / 18 | 17 / 18 |
| True synthetic candidates among reviewed, AI-retained candidates | not run | not run | 17 / 17 |

The two recovered issues were the match beyond column 100 and the match across
supplementary files. The legitimate baseline repeat remained a detector candidate;
Grok excluded it using the supplied repeated-measure explanation. Its raw evidence
remains in the review report. This example demonstrates contextual filtering; it
does not establish specificity on real papers.

All **84 reported cell references across 18 engineering candidates** were
recomputed from the archived CSV/XLSX source values. The displayed positive
example showed B6/B501 = 249.849455 and C6/C501 = 203.393867; the report correctly
counted one matching pair, two implicated rows out of 600, and one group. The HTML
report was inspected in the browser. A workbench preview defect found during this
pass was fixed: imported evidence now uses bounded neighborhoods around the
matched cells, with original row numbers and column letters, including cells
beyond the old 500-row/40-column display boundary. Preview omissions are announced.

## Scheduling and Grok variability

Fresh runs on the same 16 synthetic jobs produced identical complete candidate
objects at each worker setting. Each configuration reused all 16 completed runs
on an unchanged resume.

| Detector workers | Observed peak concurrent processes | Wall seconds |
|---:|---:|---:|
| 1 | 1 | 6.95 |
| 2 | 2 | 3.68 |
| 4 | 4 | 2.09 |
| 8 | 8 | 1.53 |

These are one-run timing measurements on this machine, while other repository
checks were active. They establish overlap and equivalence, not a production
throughput forecast. Four workers took about one-third of the serial wall time.
Memory is not capped by the coordinator; size concurrency for the largest paper.

The full Grok comparison completed **18 attempted calls / 18 candidate packets**,
with a peak of **two concurrent calls**, in 184.31 seconds. All 16 paper jobs
completed. The CLI reported $0.06691744 total cost; this is the receipt total, not
an independently reconciled invoice. No tool-use events were observed in the
saved model outputs.

A separate six-job variability check repeated each of three contexts twice.
Both legitimate-repetition answers were `exclude`; both missing-context answers
were `uncertain`. One positive answer passed as `retain`; the other supplied an
unsupported citation and was rejected, leaving no validated decision. Thus
scheduling passed independently of output validation (five of six accepted).
The later 18-call comparison does not erase that failed attempt. Two repetitions
are insufficient to estimate a stable model error rate. Inspect saved packets,
stdout and receipts before drawing conclusions about model behavior.

Grok still advertises some global CLI initialization context despite its disabled
integration settings. Temporary working directories and denied tools isolate
sessions; they are not an operating-system security sandbox. A tool invocation
invalidates the answer. Benchmark labels and issue reports were kept out of all
Grok packets.

## Real-paper acquisition and evaluation readiness

The [Science Detective source list](https://www.sciencedetective.org/about/) yielded
**22 paper families**, resolved to **36 dataset versions**, with **47 supported
structured files across 34 version jobs**. Two versions have no supported files.
The import receipt currently has **0 / 47 verified local files**. Every missing
requested file stays in the manifest; no case is scored as clean. Seven of the
22 families are held out (31.8%), keeping original/corrected versions together.

The [clonal-fish Dryad changelog](https://datadryad.org/dataset/doi:10.5061/dryad.td3sj)
documents a misassignment of body-size values to IDs. Exact cell localization is
pending the files. This is an assignment-error challenge, with original and
corrected versions pinned separately; it must not be relabelled as an exact-copy
positive merely because the paper has a correction.

The comparison frame consists of the first **seven public Dryad listing pages,
700 records**, with repository default ordering, frozen from acquired metadata.
File inventories were resolved for **697 / 700 records**; **155** met the
structured-file/article-DOI criteria. Three missing inventories remain explicit.
Earlier rapid requests encountered HTTP 429; the final freeze reused saved
metadata without retrying missing inventories. It is a convenience frame affected
by acquisition availability, not a random population sample.

The seeded selection contains **100 distinct paper families** and **284 files**:
38 CSV-only, 38 XLSX-only, 12 TSV-only, nine CSV/XLSX, two TSV/XLSX and one XLSM-only
paper. All domains remain `unclassified`; no scientific-domain balance is claimed.
Every selected paper remains unlabelled. The frozen frame, sample, import catalog,
checksum-bearing download list and pending label ledger are in this directory.

The real-data phase must review every flagged comparison paper and 20 seeded
unflagged papers with complete coverage, verify issue-level labels and corrected
counterparts, then report development and held-out results separately. The
benchmark command provides localized recall, acquisition states, AI retention,
reviewed precision and review queues with explicit denominators. Ground truth
and empirical real-paper performance are not yet established.

## Validation

See the final validation counts appended below. Regression coverage includes the
Excel row/column/sheet limits, uncached formulas, over 100 candidate groups,
complete cell retention, cross-file matches/exclusions, differently labelled
units, duplicate deliveries, physical row gaps, checksum failures, malformed AI
output, call budgets/retries, subprocess overlap, cancellation/reaping, atomic
publication and fingerprint resume. Fresh-wheel tests run outside the repository
with no `forensic_metascience_ai_toolkit` installed.

The machine-readable [evaluation.json](evaluation.json) records the measurements
and source/code fingerprints. Full inputs, raw runs, prompts and test logs are
retained locally under `.copy_paste_evaluation/`; these generated files are
intentionally gitignored. Reproduce deterministic checks with the example script;
Grok outputs may vary on rerun. Add `--full-grok` to the example script to
adjudicate all 16 synthetic paper jobs; `--live-grok` runs the separate six-job
variability check. Human-review metrics require the independently reviewed ledger.

## Final acceptance results

- Standalone wheel: **159 passed**, using a clean virtual environment outside
  the repository; `metascience_agent` (the toolkit, under its name then) is absent. A 16-paper process batch also
  completed from the installed wheel, and the 100-paper sample reproduced byte-for-byte.
- Required repository run: **10,387 passed, 166 skipped, one expected failure**,
  in 85.66 seconds. Skips and the expected failure are not passed checks.
- TypeScript compiler, standalone Ruff and `git diff --check`: passed.
- `metascience lint-inert --certain-only`: completed and reported **46 certain
  findings** elsewhere in the repository; no listed finding was in the
  copy-paste package or its modified history import. This is not a zero-warning claim.
- Cancellation during process creation, including repeated cancellation from a
  surrounding batch, is now shielded until the child handle is acquired and the
  process is killed and reaped. Regression tests cover this race directly.

These final tests include the later cancellation and workbench-preview fixes.
The earlier timing/model experiments retain their original fingerprints; their
archived outputs were not relabelled with the final code hash.
