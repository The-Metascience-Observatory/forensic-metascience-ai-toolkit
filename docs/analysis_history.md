# Versioned analysis history

Image, copy/paste, and comprehensive audits share three identity levels:
execution (a project job), run (a paper/component attempt), and item (a saved
candidate or tool group). Versions are provenance, never identifiers. Two jobs
using the same version remain separate selections.

## Review

Open `/project/<project>/images` or `/project/<project>/copypaste`. The paper
reviewer uses the same **Version / run** control. `?run=latest` selects the latest
recorded component attempt per paper; failed attempts do not silently fall back.
An explicit execution selects its own outputs and recorded reuse references.
Copy/paste retains all tool invocations within the selected paper job.

All saved results are shown by default. Original adjudication, saved AI screening,
and the human decision are separate facts. Historical candidates can be reviewed
without becoming current published findings. Decisions name both the real owning
run and item; `latest` is never a write target. Reused `IMGDUP-N` ordinals do not
transfer decisions. Unassigned legacy decisions and other-run decisions are
context only.

Selection survives URLs, refresh, queue/item navigation, browser history, and
CSV export. Historical panels, source PDFs, worksheets, exhibits, and videos are
resolved through the owning run's artifact manifest. Missing historical media is
an error, never a reason to substitute current panels. Video responses retain HTTP
range support. Rebuild reconstructs the archive index, without analysis or paid
screening.

## Preservation and producers

Each project has `.analysis_runs/`:

- `executions/`: configuration, requested components, job status and reuse IDs.
- `pending/`: identities minted before execution starts.
- `runs/`: sealed records, candidates, judgments, provenance and artifact manifests.
- `objects/<prefix>/<sha256>`: deduplicated byte copies; never hard links into
  mutable producer output.
- `work/`: isolated producer workspaces. These are not completed runs.
- `reviews.jsonl`: append-only human decisions, outside the sealed outputs.
- `publication.json`: the separately rebuildable current-publication projection.
- `derived/`: exhibits and sheet views derived from named archived sources.

Run manifests are published atomically, with a digest. Changed output under an
existing sealed ID is rejected. Re-screening, adjudication, and report enrichment
create linked revisions. Concurrent runs use distinct workspaces. A failed or
cancelled writer cannot erase an earlier sealed result. Abrupt process termination
may leave a pending record; it is shown as unfinished, never as a clean result.

Image track, direct image analysis, corpus sweeps, cross-paper matching and
screening capture history. Comprehensive reports record child analyst,
adjudicator, image, and actual copy/paste invocations. An uncalled copy/paste tool
is `not_requested`; it is not a mandatory independent stage. Tool capture occurs
before ledger truncation. The standalone detector remains independent.

When the pipeline includes the `raw_data` module (pipelines `raw_data_only`,
`full_raw_data`), the copy/paste component is recorded from that module's
result instead (`parallel.py`): `unavailable` when it did not run (no
spreadsheet to read, never a clean result), `failed` on error, `incomplete`
when the module reports incomplete execution, and `completed` otherwise.

The image-history producers (image track, direct image analysis, corpus sweeps,
cross-paper matching and screening) live in the separately distributed image
analysis package and record history only when it is installed. A comprehensive
run configured for image forensics without the package seals its
`image_forensics` component as `unavailable`, with the install hint as detail,
not as `failed` or `not_requested`.

## Commands

```bash
metascience history-import /path/to/project --dry-run
metascience history-import /path/to/project
metascience history-db-migrate --dry-run
metascience history-db-migrate
metascience history-sync /path/to/project

metascience copy-paste /path/to/input.xlsx \
  --project-root /path/to/project --paper /path/to/project/paper

copy-paste-detect /path/to/input.xlsx --run-dir /path/to/portable-runs
metascience history-import-copy /path/to/portable-runs/<run-id> \
  --project-root /path/to/project --paper /path/to/project/paper
```

The copy importer also accepts older detector JSON. Portable artifacts and result
hashes are checked; historical versions and dates remain unknown when unrecorded.
Existing JSON/stdout detector usage is supported.

The inventory/import command reads sweep manifests, retained results, review
folders, preserved screening originals, partial detector logs and tool ledgers.
It never reruns detectors or invokes paid screening. Missing baseline outputs are
recorded as unavailable; newer output is not assigned to a baseline merely because
its filename matches. Legacy media copied at import is marked as unverified
historical evidence. Repeating the import leaves existing sealed records intact.

## Database and APIs

The additive migration extends `runs` and `reviews`, and adds `executions`,
`component_items`, `component_item_papers`, `run_artifacts` and
`image_publication`. Cross-paper items have one deterministic owner and both paper
associations. A project attempt with zero pairs can have no paper owner.
Composite foreign keys prevent a component review from naming another run's item.
Sealed analysis evidence cannot be replaced; human reviews are append-only.
Repeated sync is idempotent. Failed synchronization leaves `sync_error.json` for
an explicit retry and never invalidates local evidence.

`published_component_items` joins preserved screening evidence to the current
policy/input eligibility projection. Historical queries do not apply today's
policy retrospectively. Component runs are excluded from comprehensive report
counts. See [database specification](specs/webapp_db.md).

`GET /api/runs?project=…&component=image_forensics|copy_paste` returns the catalog.
Feeds use `/api/images?project=…&run=…&component=…`; CSV adds `format=csv`.
Review POSTs require `project`, owning `run`, `item`, `decision`, and `reviewer`.
Media references have the form `__runs/<run-id>/<artifact-id>`.

Database-only image media retrieval is deferred. The local artifact archive is
required for historical image browsing.
