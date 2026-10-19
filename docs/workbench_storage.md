# Workbench storage and synchronization

The workbench keeps the existing Next.js interface and scientific analysis pipeline.
Normal project, paper, image and copy/paste navigation now reads a private SQLite
cache through one persistent Python JSON-lines service. The local Postgres findings
database owns records; local files supply evidence. Missing files do not delete findings.

## Setup

Use the interpreter named by the installed `metascience` console script. Existing
database credentials come from `db_push.resolve_db_url`: one `METASCIENCE_DB_URL`
(environment or repo `.env`) naming a database on this machine. A URL naming any
other host is refused; the remote Neon database was retired 2026-10-16.

Apply the additive journal migration once, then bootstrap this computer:

```sh
python -m metascience_agent.workbench.service --migrate
python -m metascience_agent.workbench.service --sync --index webapp/data/index.json
cd webapp
npm run build
npm start
```

Here `python` means the project interpreter, not an arbitrary system Python.
The app manages its Python service automatically. A crashed service rejects its
outstanding requests and restarts on the next request. It is not an analysis worker.

SQLite defaults to `~/.local/share/metascience/workbench.sqlite3` on Linux,
`~/Library/Application Support/metascience/workbench.sqlite3` on macOS, or
`%LOCALAPPDATA%/metascience/workbench.sqlite3` on Windows. The optional
`METASCIENCE_WORKBENCH_DB` override must also point to a private local disk, never
Dropbox, another synchronization folder, or a network share. Do not copy a running
SQLite database and its WAL between machines.

Use **Local files** in the header to register multiple roots, map an individual
paper to a folder outside those roots, or associate a file with its archived
SHA-256. A source with no recorded historical hash is explicitly labeled current.
Archived media must match its recorded hash. Registered files are revalidated after
stat changes; path traversal and escaped symlinks are refused. HTTP media retains
ranges, conditional requests and streaming.

## Import existing results without running analysis

```sh
python -m metascience_agent.workbench.importer /path/to/corpus --dry-run
python -m metascience_agent.workbench.importer /path/to/corpus > import-report.json
```

The importer compares stable run IDs and sealed digests, imports missing archives
and reports/bundles, and replays timestamped reviews. It does not merge papers by
DOI. Digest conflicts and reviews without an identifiable historical owner are
reported rather than reassigned. Runs containing U+0000, or requiring an ancestor
containing it, are reported: PostgreSQL JSONB cannot represent that character.
Their original archives remain intact. A failed batch is isolated so unrelated
valid records can still migrate. Repeat the command to resume after interruption.

Full accepted, rejected and unadjudicated candidate records remain in the findings database.
PDFs, images, spreadsheets, article bodies and generated exhibits remain files.
Backfilling all candidate history increases database storage even without media.

Current publication eligibility is rebuilt during explicit import using the
existing policy. Browsing and new review decisions do not trigger this rebuild.
Legacy scientific statistics still read the explicitly generated
`corpus_stats.json`; statistics drill-down now uses paginated cached findings.
Compatibility import/export and explicit legacy index-building commands remain.

## Runtime contract

- Summary endpoints default to 50 records, maximum 100. Filters and sorting precede
  serialization. Candidate and finding details load separately.
- `/api/workbench` exposes projects, papers, runs, findings, feed, item, source,
  issue_detail, roots and status. Existing paper/image/run/review/media URLs adapt
  to these readers. Findings responses contain `rows`, `pagination`, and `sync`.
- Latest selects the latest attempt, including failed, partial and empty attempts.
  An explicit historical run never falls back to another run. Run selectors can
  load older pages.
- Paper findings are served before source extraction/locator preparation.
  Comprehensive and component findings share the paper projection. Deduplication
  requires explicit parent ownership and original finding identity.
- A compact transactional journal captures authoritative table inserts, updates
  and deletions. Statement-level writer locking prevents an uncommitted lower
  revision being skipped. Bootstrap uses a consistent snapshot and atomic SQLite
  publication. Two app processes coordinate synchronization with a local file lock.
- Active polling is 30 seconds, idle polling five minutes; focus requests a sync.
  The header displays freshness and pending writes. Startup reconciliation,
  producer notifications and background polling update known local mappings.
  Browsing does not recursively scan a corpus.
- Decisions first commit to a local outbox, with immutable event IDs. Pending
  state remains until the database acknowledges and the shared event has been pulled.
  Each reviewer's latest decision and timestamped history remain visible.
  Conflicts do not silently pick a winning reviewer or reverse a publication
  revocation. Submission flag edits retain that reviewer's decision and notes.
- `workbench.service --migrate` applies journal migration 004 and retention
  migrations 005 (image retirement) and 006 (image reset). Retired or reset image
  payloads keep run-identity tombstones and cannot be reimported under their old
  run IDs; a new analysis uses a new run ID. Other sealed findings and reviews
  keep their guards.
- Publication synchronization projects the latest recorded attempts from the database,
  not from file-stat stamps on the syncing machine. An older judgment cannot undo
  a later revocation, and reviewer conflicts cannot silently republish. Missing
  local files never delete shared publication records.
- Foreground details use their own connection and executor, separate from
  background synchronization and source conversion. Archived XML renders only
  after hash verification.
- The local monitor (`workbench/monitor.py`) watches known roots, paper mappings
  and registered file directories nonrecursively, with a five-minute full
  reconciliation for missed events. It is independent of the database. Install the `db`
  extra for `watchfiles`; a watcher failure appears in the header and periodic
  reconciliation continues.

## Verification

Repeat verification using the project interpreter and a separate Next build
directory if another dev server is using `.next`:

```sh
python -m pytest tests/test_workbench_catalog.py tests/test_analysis_history.py -q
METASCIENCE_TEST_POSTGRES=1 python -m pytest tests/test_workbench_remote.py -q
cd webapp
npm test
node --experimental-strip-types test/workbench.mjs
METASCIENCE_NEXT_DIST=.next-workbench-qa npm run build
PORT=3120 METASCIENCE_NEXT_DIST=.next-workbench-qa npm run start
# From another terminal:
METASCIENCE_TEST_URL=http://localhost:3120 node test/workbench-browser.mjs
```

The PostgreSQL tests create and remove random test schemas; they do not replace
production tables. The browser script expects the named local review fixtures.
A clean initial synchronization is required before assessing warm-cache targets.

## Queues and production review

This contract dates from September 11, 2026; the measurements taken then are in
[archive/workbench_storage_log_2026-09.md](archive/workbench_storage_log_2026-09.md).

Use Node 22 on this machine (`nvm use 22`). Everyday review uses an optimized
Next.js build:

```sh
cd /home/dan/Dropbox/AAA_METASCIENCE_OBSERVATORY/agent_for_forensic_metascience/webapp
nvm use 22
npm run build
npm start
```

Stop the previous production server with Ctrl+C before rebuilding or restarting.
The review URL stays `http://localhost:3101`; the launcher refuses an occupied
port. Development is available with `npm run dev` on 3100, or the next free
port if 3100 is taken. The build directories
are named `.next-review` and `.next-dev`; `scripts/serve.mjs` places them (and any
`METASCIENCE_NEXT_DIST` name) in the operating system's cache directory under
`metascience-webapp/<checkout hash>/`, outside Dropbox, and prints the folder at
startup. `METASCIENCE_NEXT_CACHE` moves that root; `METASCIENCE_NEXT_LOCAL_BUILD=0`
restores the in-checkout folder. Never rebuild a directory used by a running
server: old processes retain manifests referring to files replaced by the build.
For separate validation, use `METASCIENCE_NEXT_DIST=.next-performance-qa` for both
build/start and `PORT=3199` for start. The final review server is launched by the
user; validation does not replace it.

SQLite performs a one-time local migration that creates expression indexes and
transactional revision triggers. This indexes the existing cache without an
analysis rerun or a database schema change. Shared records, review outbox entries and
local mappings have durable revisions; status updates, cached detail writes and
file registration do not change queue revisions. Triggers also observe writes
from another app process. Each worker reads through its own SQLite connection,
with snapshot transactions around projection loading. Interactive repositories
load project headers and selected-run records; media uses exact owning-run and
artifact lookups with a bounded, revision-keyed reference cache. Cached reference
metadata never replaces original file hash/stat/containment validation.

The fixed `variant=thumbnail` media option produces aspect-preserving PNGs within
260×120 pixels, displayed at 130×60. Derivatives live beside the private SQLite
cache under `derived/thumbnails`, outside Dropbox, keyed by source hash, dimensions
and renderer version. Generation uses two dedicated workers and cross-process
file locks. The disposable PNG cache is bounded to 1 GiB. Cached thumbnails use
the media worker lane; source conversion and diagnostic rendering cannot occupy
those workers. Missing/changed originals are refused even when a thumbnail exists.
Original-resolution hover previews, full-detail images, byte ranges and ETags
remain supported.

Queue images are requested for visible rows plus roughly one viewport ahead.
The queue uses infinite scrolling over bounded 50-row HTTP requests. Additional
batches append without replacing visible rows; Up/Down arrows move selection and
keep it visible, and Enter opens the selected item. Returning restores loaded
batches, scroll position and selection. Filter changes cancel obsolete requests.
A revision change refreshes loaded batches together, preventing mixed-generation
page boundaries; a failed next batch retains prior rows and offers retry.
Filters are restored before the first query; obsolete hidden adjudicator filters
are discarded, and Reset filters restores the default Issue/Unresolved selection.
A paper-folder search (`q`) matches the folder shown in the Paper column,
including a DOI pasted with a slash against the `--` directory name, and is
applied on the server before pagination so it covers the whole run, not the
loaded page.
The Paper column header sorts that folder name A→Z, then Z→A, then back to
rank score; the Score header does the same for rank. Sort is applied on the
server before pagination so it covers the whole run.
A successful image (or copy/paste) feedback click, including keys 1–9,
advances to the next undecided item in the current filter; a failed save
stays on the item.
An empty filtered view reports that saved records still exist. Item details can
render before their queue arrives. Detail requests are bounded, deduplicated and
cancelled when navigation becomes obsolete. Responses carry a record revision;
optional diagnostics only attach to matching details. Comparator and PDF boxes
share decoded panel images and dimensions. Document-wide PDF search indexing
starts after the selected page paints. Status polling is consolidated at 30
seconds normally, 5 seconds while writes are pending, and immediate focus/review
refreshes; background shared sync retains its active/idle cadence.

### Diagnostics

The service returns request-queue, database, projection, file-validation,
thumbnail-generation and serialization durations, exposed as `Server-Timing`
on summary/detail/media responses. Nested categories overlap (projection includes
its database work); do not sum the header values as independent phases. The
outermost duration is counted once when one category nests inside itself.

Repeat browser checks against a separate built server:

```sh
cd webapp
METASCIENCE_TEST_URL=http://localhost:3199 npm run test:performance
```

The checks inspect actual queue rows, hidden-filter recovery, thumbnail dimensions,
original hover media, item-before-queue rendering, queue/item navigation, matching
neon PDF polygons, suffix byte ranges, conditional requests and browser errors.
Python regressions exercise two independent SQLite/app instances, snapshot reads
with concurrent writes, zero projection reloads after unrelated writes, scoped
ordering/filter parity, reference invalidation/deletion, cross-project refusal,
concurrent thumbnail deduplication, changed/missing sources, derivative eviction,
offline cached reads and durable review acknowledgment.

## Image review

The image queue, comparator, local image rapid review (`--images-local`,
`image-review.sqlite3`), on-demand video generation, thumbnails and XML-paper
figure navigation are implemented in the separately distributed image analysis
package (`metascience_observatory_image_analysis.review_workbench`). The host keeps
no aliases of those modules (removed 2026-10-18, v1.85.0): `workbench/service.py`
loads them through `image_plugin.load`, or `workbench/image_review_host.load` for
the three assembled from the host's storage (`local_images`,
`local_image_import`, `local_image_service`). The import CLI is
`python -m metascience_agent.workbench.image_import`, and `--images-local`
refuses with an install hint when the package is absent. The statistical workbench runs without it. Their
documentation moved with the code on 2026-10-16: see
`docs/workbench_image_review.md` in the image package.

## Dated records

Verification samples, Database capacity and backfill audits, the September 10
superseded-image cleanup, the Masliah image reset and the September 11 queue
measurements are archived in
[archive/workbench_storage_log_2026-09.md](archive/workbench_storage_log_2026-09.md).
