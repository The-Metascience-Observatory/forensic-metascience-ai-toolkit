# Copy-paste detector

Independent Python package for numeric row duplication, adjacent copied sequences
and unusually specific repeated values. Detection requires no agent, service,
database or API key. Optional adjudication uses the installed Grok CLI and its
existing login. The paper-level workflow focuses on **XLSX, XLSM, CSV and TSV**.
The existing single-file API and DOCX reader remain available.

## Install

Copy this directory to another machine, then:

```sh
python -m pip install .
copy-paste-detect supplement.xlsx --output findings.json
copy-paste-batch --help
copy-paste-dataset --help
copy-paste-benchmark --help
```

The parent metascience distribution also includes these commands. For repository
development use the parent editable install (`pip install -e .` at the repository
root). Do not install both distributions into one environment: they contain the
same Python package.

## Paper-level batch

One JSONL line describes one paper and one dataset version. Paths are relative to
the manifest. Multiple files in the line are compared together. Original and
corrected versions must be **separate lines**, with the same optional `family_id`.

```json
{"paper_id":"study-original","family_id":"study","files":[{"path":"inputs/data.xlsx","name":"data.xlsx","exclude_columns":["site_code"]},{"path":"inputs/visit2.csv","name":"visit2.csv"}],"context_files":["inputs/README.txt","inputs/paper.md"],"data_context":"raw_participant_level"}
```

`name` is the unique source label retained in evidence; use relative directory
names to distinguish equal basenames. `sheet` and `exclude_columns` are optional
per-file fields. Column exclusions accept names or zero-based indices. Context
accepts UTF-8 TXT, MD, XML or HTML; extract PDF text first. Include study design,
units and the original README, **never issue reports or benchmark labels**.
Missing context is explicitly unresolved. Unknown manifest keys, including labels,
are not passed to Grok; listed context files are trusted to be the intended study
sources, so keep the annotation directory separate.

```sh
copy-paste-batch papers.jsonl --output-dir runs --workers 4
copy-paste-batch papers.jsonl --output-dir grok-runs --workers 4 \
  --backend grok --model grok-4.6 --ai-concurrency 2 \
  --max-ai-calls 500 --ai-timeout 180 --detector-timeout 300 --resume
```

Defaults: at most four available CPU workers, two concurrent Grok calls, two
retries for transient failures, 500 **attempted** AI calls across the invocation.
Retries count toward this limit. No retry is made for invalid JSON or unsupported
citations. Each paper runs in a separate detector process; BLAS threads are
limited to one. AI overlaps detection and other AI calls. Explicit worker counts
can exceed the default; more workers are not guaranteed to be faster.

Batch reader limits default to zero (unlimited). `--max-rows`, `--max-columns`,
`--max-sheets`, `--max-row-pairs` allow explicit limits; every omitted region or
exhausted comparison budget makes coverage partial. The detector timeout bounds
individual processing. There is no imposed process memory ceiling: size worker
counts for your largest workbooks. Exact matching is indexed, but repeated seeds
and large outputs can still be expensive. No Cartesian comparison across papers.

Exit 0 means every requested paper completed; exit 1 also covers partial coverage
or AI failures. It does not mean suspicious versus clean. Read `index.json` and
`index.html`, then each run's `review.html`.

## Evidence and adjudication

- All candidate groups and their cells survive into `result.json`, with stable
  content-based IDs and file/sheet/cell/value references and input SHA-256 hashes.
- Separate `adjudication.json` stores retain / exclude / uncertain decisions,
  reasons, verified verbatim citations and invocation receipts. No AI decision
  changes detector evidence, severity or hard applicability caps. Retain means
  investigate, not confirmed error. A capped indeterminate candidate stays capped.
- Each candidate receives bounded evidence (approximately 48,000 characters,
  including at most 12,000 study-context characters). Truncation, missing context,
  or a requested context file that failed to load forces uncertain. Failed calls
  and exhausted call budgets leave candidates unreviewed, never excluded.
- Grok starts a fresh session in an empty temporary directory, with web access,
  subagents and tool use disabled by CLI configuration. Observed tool invocation
  invalidates the answer. CLI global settings may still affect initialization;
  this is session isolation, not an operating-system security sandbox. Inspect
  saved `ai/*/packet.json`, prompt, stdout, stderr and receipts when auditing.
- Source files, context and every AI artifact are retained and hashed. Publication
  of run manifests and the latest index is atomic. One coordinator owns an output
  directory. Cancellation kills/reaps active child process groups and records
  interrupted runs; unstarted papers remain absent from the completed-run list.

Resume reuses only completed runs whose input bytes, context, configuration,
code and prompt fingerprints match and whose saved artifacts still verify.
Partial or failed papers are rerun; their prior attempts remain available.
Changing only worker counts does not invalidate detection. The call limit applies
to each invocation, including a resume invocation; rerunning unresolved papers
can therefore spend again. The current index describes the supplied manifest;
older run directories remain immutable history.

## Local dataset acquisition and benchmark

```sh
copy-paste-dataset discover --output cases
copy-paste-dataset import --catalog cases/catalog.json \
  --incoming /path/to/downloads --output acquired
copy-paste-batch acquired/manifest.jsonl --output-dir runs --backend grok --resume
copy-paste-benchmark --labels labels.jsonl --run-index runs/index.json --output score
```

Discovery records all Science Detective entries and exact Dryad version/file IDs
and published checksums. It fetches public metadata only. Download files through
your browser, preserve names, and keep original/corrected files in separate
folders. Import matches filename **and repository checksum**, computes SHA-256,
refuses conflicting existing bytes and retains missing requested files in the
manifest. A missing file cannot become a negative result.

`copy-paste-dataset frame --output frame --pages 7` freezes a bounded public
Dryad convenience frame. `sample --frame frame/frame.json --output sample.json
--count 100 --seed 20260910 --exclude-catalog cases/catalog.json` draws distinct
paper families with format/domain strata. It refuses fewer than 100 eligible
families. The sample is unlabelled and is not a prevalence sample of all Dryad.
Use `frame --cached-only` to freeze acquired metadata without requesting missing
file inventories; `--retry-failed` revisits previously failed metadata lookups.
Use the repository's `benchmarks/copy_paste` for the frozen acquisition lists,
held-out assignments, annotation contract and evaluation report.

## Workbench import

Copy a complete `runs/cp_.../` folder, then in the parent environment:

```sh
python -m metascience_agent.analysis_history import-copy /path/to/corpus \
  --paper /path/to/corpus/paper --file /path/to/runs/cp_...
```

The existing copy/paste workbench displays both archived spreadsheets with their
own highlighted cells, coverage and the saved Grok judgment. AI review does not
publish findings or substitute for the separately stored human decision. The
legacy schema-1 portable single-file import continues to work.

## Python and single-file compatibility

```python
from copy_paste_detector import DetectionLimits, detect_paper_duplication, detect_raw_duplication

paper = detect_paper_duplication(
    ["data.xlsx", {"path": "followup.csv", "exclude_columns": ["site"]}],
    paper_id="study", data_context="raw_participant_level",
)
legacy = detect_raw_duplication("data.xlsx", limits=DetectionLimits(0, 0, 0))
```

The legacy defaults remain 5,000 rows, 100 columns, eight sheets and 5,000 row
comparisons. Limits now report partial coverage and the complete group list is
returned. `copy-paste-detect` exposes reader limits too; `highlight_workbook` and
`--highlight-out` retain their existing contracts. Single-file read exceptions may
propagate through the Python API; batch records them per source.

## Interpretation and capability limits

Thresholds remain unchanged. Row comparison requires two matching informative
values; sequences require at least three physically adjacent numeric rows and
exact verification. Blank/missing cells break adjacency. Cross-file comparison
requires equal unique headers, including units; ambiguous or absent headers stay
local. Differently named equivalent measurements need preprocessing with a
recorded mapping. Byte-identical files count as alternate deliveries.

IDs, constants, instrument telemetry, categorical collisions, derived values,
pooled data and repeated-measure structures are excluded or capped as before.
Reader limits, unsupported formats, read failures, empty/noncomparable data and
uncached Excel formulas are different output states. Formula cells use existing
caches; formulas are never executed or recalculated. Near-duplicate edits, shifts
in measurement assignment and misaligned joins are separate capability limits:
a few surviving exact cells can create a candidate, but absence of a candidate
does not establish correct assignment. DOCX enhancements and legacy XLS are deferred.

## Development

```sh
python -m pip install -e '.[dev]'
python -m pytest
python -m build
```

`paper` combines readers and the existing scoring/guard modules; `batch` owns
workers and portable output; `grok` owns evidence packets and validated decisions;
`datasets` and `benchmark` own acquisition and issue-localized scoring. No module
imports the full agent.

## Attribution

Extracted from the MIT-licensed Forensic Metascience AI Toolkit. Digit-information
weighting, derived-value discounts, regularity discounts and occurrence weighting
follow ideas published for inspection in Markus Englund's `copy-paste-detective`
(source-available, all rights reserved). This is an independent implementation;
no code from that project is included. The consistency principle follows James
Heathers (2025), “Pursuing internal consistency.” See `LICENSE`.
