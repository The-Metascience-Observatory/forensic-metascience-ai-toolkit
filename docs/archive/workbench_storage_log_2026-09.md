# Workbench storage: dated audit and verification log, September 2026

> **ARCHIVED 2026-10-16.** Moved out of `docs/workbench_storage.md`, which keeps
> the current storage and runtime contract. These are dated measurements,
> backfill and capacity audits, cleanup and reset records, and test counts from
> September 10-11, 2026. The figures were true when recorded and are not
> maintained; the suite size and database sizes have changed since. The
> image-review sections that sat beside them moved to the separately
> distributed image analysis package (`docs/workbench_image_review.md` there).

## Verification on September 10, 2026

These are local diagnostic samples, not production latency percentiles:

| Check | Observed |
| --- | --- |
| Warm 50-paper list HTTP p95, 20 requests | 6 ms; 63,451 bytes |
| Warm selected paper summary HTTP p95, 20 requests | 13 ms; 5,179 bytes |
| Warm 50-candidate HTTP p95, 20 requests | 41 ms in final browser check; 146,410 bytes in the earlier payload sample |
| Warm findings visible with source deliberately delayed 2 seconds | 66 ms |
| Rendered preserved report reconciliation | 4 matching IDs, titles and severities |
| Browser media checks | suffix ranges and ETag/304 passed |

The comparable earlier image responses contained entire feeds of 17.7–23.8 MB.
The new measurements use 50-row pages; they demonstrate bounded navigation
payloads, not faster transfer of an entire history. Browser screenshots confirmed
the selected finding, complete detail, local-source label and quote location.

The full Python suite passed 10,413 tests (170 skipped, one expected failure)
before the final capacity guard; focused tests were
run again for that guard. Four opt-in PostgreSQL tests passed in disposable
schemas, covering snapshot/deltas/deletion, concurrent commit ordering, idempotent
reviews/conflicts and simultaneous bootstrap. Next production build, TypeScript,
Node bridge tests and rendered-browser checks passed.


## Backfill status before image-history retirement

Neon reports a 512 MiB cluster ceiling. At the final audit the application database
used about 462 MiB and all connectable databases used about 477 MiB. The importer
now reserves the larger of 32 MiB or 10% of the configured ceiling for live writers
and refuses additional bulk uploads above that threshold. It reports
`capacity_blocked`; raising the limit permits an idempotent resume. No records
were deleted to make room.

The batch2 archive audit has two remaining run IDs containing U+0000 or depending
on such a run. Masliah has 473 distinct legacy report IDs still awaiting import.
The other ten projects had no missing runs/reports; several legacy review notes
remain explicitly unscoped. The final publication rebuild for the large backfill
also remains pending capacity clearance. Newly imported historical candidates
are accessible by exact run; current publication eligibility is never inferred
from missing synchronization.

Detailed per-project audits live in this computer's
`~/.local/share/metascience/import-audit/`. Original archives and review files are
unchanged.

A read-only breakdown of candidate JSON storage (excluding table/index overhead)
found:

| Recorded screening decision | Records | Stored candidate JSON, MiB |
| --- | ---: | ---: |
| No decision recorded | 23,410 | 117.97 |
| Unresolved | 7,468 | 82.91 |
| Innocuous | 5,547 | 68.43 |
| Issue | 66 | 0.85 |

These are candidate records across historical runs, not distinct papers or
distinct scientific findings. No decision recorded and unresolved are not
negative findings. Candidate storage including table/index overhead is about
303 MiB; artifact references use 56 MiB, the journal 33 MiB, runs 31 MiB, and
comprehensive findings 16 MiB. No media payload is included in those figures.
A retention change needs to preserve the distinction between an explicit
innocuous judgment and missing or inconclusive adjudication.


## Superseded image cleanup — September 10

At the user's request, 28,827 old candidate payloads from 5,563 superseded image
runs were replaced with compact retirement markers. Each run had a verified
newer completed replacement in the same paper/scope, and its full local archive
was verified against the sealed digest. Current selections, the newest completed
run per scope, and runs with human reviews were protected. The protected 4,527
candidate records and all 3,540 comprehensive findings retained identical JSON
checksums.

Migration 005 keeps retirement timestamps/replacement references separate from
immutable scientific headers. Evidence guards permit only the exact retirement
marker or a logically identical maintenance rewrite; arbitrary sealed edits and
deletes remain refused. Existing candidate IDs prevent old archive mirrors from
restoring removed payloads. Historical readers explicitly say that details were
retired, and journal synchronization invalidates cached details.

After PostgreSQL compaction, application database size fell from 483,950,592 to
197,148,672 bytes: **286,801,920 bytes reclaimed (273.5 MiB, about 59%)**.
Original local archives and media remain untouched. The pending unrelated
backfill was not resumed automatically. The exact plan and checksums are in
this machine's `~/.local/share/metascience/retire-image-plan.json` and
`retire-image-result.json`.

## Integration and Masliah reset — September 10

Publication synchronization now projects the latest recorded image attempts from
Neon, rather than recomputing file-stat screening stamps on the syncing machine.
It retains the independent pair/clone policies and explicit deterministic-clearance
audit view. A prior revocation stays in force when replaying an older judgment;
a newer analysis can establish new eligibility, while reviewer conflicts do not
undo a revocation. Missing local files cannot delete shared publication records.

Foreground details use a separate reusable connection and executor from background
synchronization and source conversion. Archived XML renders through the existing
escaped article renderer only after hash verification, including when an archived
PDF is unavailable. A changed file cannot reuse the cached XML rendering.

The local monitor uses nonrecursive watches on known roots, paper mappings, and
registered file directories, with five-minute reconciliation after missed events.
It is independent of the Neon lane and revalidates modified registered evidence.
Install the `db` extra to include `watchfiles`; watcher failures appear in the
header and retain periodic reconciliation. The watcher API is documented at
https://watchfiles.helpmanual.io/api/watch/ .

`workbench.service --migrate` now applies journal migration 004 and retention
migrations 005/006. Migration 006 permits explicit image-only payload removal
under a recorded `user_requested_rerun` retirement reason. Other sealed findings
and reviews retain their guards, and deleted image payloads cannot be reinserted
under their old run identities. A new analysis must use a new run ID.

The user subsequently requested clearing **all Masliah image results**, including
local generated files, in preparation for a future rerun. The in-progress legacy
report import was stopped because those reports included image-only results.
The reset removed 3,781 candidate rows, 901 standalone image findings, 8,934
artifact-reference rows, and associated image reviews/channels from 3,984 shared
image runs. On disk it removed 34,079 generated files (8,874,578,355 bytes), including
2,861 archived image manifests. Minimal retirement records remain; original PDFs,
source figures/supplements, 6,628 protected archive-object hashes, and all 157
non-image findings were preserved. The non-image findings' JSON checksum was
unchanged. Legacy image decisions were removed from 31 local review files without
removing their non-image decisions.

After compaction, database size fell from 202,620,928 to 183,164,928 bytes, reclaiming
19,456,000 bytes (18.55 MiB). These measurements include the earlier partial report
import and are separate from the previous 273.5 MiB prototype cleanup. A fresh
Masliah audit reports zero missing runs/reports, zero conflicts, and zero errors.
The image API returns zero results with “awaiting a new analysis,” not a clean-paper
verdict. No new image analysis has been started.

The exact reset manifest and result are stored outside Dropbox in
`~/.local/share/metascience/masliah-image-reset-plan.json` and
`masliah-image-reset-result.json`.

Final verification for this integration passed 10,440 Python tests (173 skipped,
one expected failure), TypeScript checking, the persistent-service bridge, and
rendered browser checks. PostgreSQL integration tests additionally cover a reset
that cannot delete non-image analyses or reimport payloads under cleared IDs.
A fresh warm 50-row image API sample measured p50 26.8 ms and p95 29.9 ms across
30 requests, with a maximum 147,664-byte response. The earlier browser sample
while the full suite was busy measured p95 373 ms; these are diagnostic samples,
not production percentiles. The current dev UI was checked to show the reset
message without claiming saved candidates were still available.

## Queue measurements and limits — September 11, 2026

These are diagnostic samples on the local batch3 image queue, not a service-level
guarantee. The selected latest runs contain 926 saved items, of which 405 match
Issue/Unresolved; responses contain the first 50 matching rows. The browser viewport
for the timings below was 1500×1000 with 10 initially visible thumbnails.

| Measurement | Before | After |
| --- | --- | --- |
| Queue HTTP diagnostic requests | 2.9 s; 7.6 s on reload | Final 20-request sample: p95 36 ms |
| Corpus projection refresh | 1.8–2.5 s for about 297,000 rows / 230 MB JSON | Indexed project/run reads; cached projection checks about 0.05 ms |
| Fresh browser, 10 visible thumbnails ready | Only 3/10 loaded after 11 s | 653 ms, all 10 loaded |
| Warm reload, 10 visible thumbnails ready | Not separately recorded | 816 ms, all 10 loaded |
| Item controls, queue artificially delayed 2 s | Previously waited for queue | 1,187 ms |
| Warm detail HTTP, 20 requests | Not separately recorded | p95 13 ms |
| Cached thumbnail HTTP, 20 requests | Full originals previously transferred | p95 5 ms |
| Local status HTTP, 20 requests | Not separately recorded | p95 2 ms |

The fresh browser measurements above use an initialized backend and existing
thumbnail cache. The first production probe, including initial backend/index
startup and thumbnail generation, took 4.5 s for the visible images. Cold startup
and uncached remote details must be reported separately from warm requests.
One 20-request feed sample during concurrent startup/background work had p95
513 ms; a subsequent 30-request sample had median 36 ms, p95 162 ms and maximum
374 ms. The final 20-request sample in the table reached p95 36 ms. An earlier cached
thumbnail sample reached p95 317 ms before adding the validated reference cache.
Other active rendering/test jobs also competed for CPU. The warm targets were
reached in follow-up samples but tail latency under concurrent load is not yet
consistently below 250 ms; do not report a universal latency guarantee.

Final validation on September 11: optimized Next build, TypeScript and frontend
checks passed. The required Python suite passed **10,554 tests**, with 173 skips
and one expected failure. `metascience lint-inert --certain-only` still reports
46 existing findings (248 worklist); this change did not increase that baseline.
Infinite-scroll unit checks cover ordering, the short final batch, revision
changes and refusal of inconsistent pages; `npm run test:infinite-scroll` checks
actual browser append/retry, keyboard selection, back navigation and filter reset.
