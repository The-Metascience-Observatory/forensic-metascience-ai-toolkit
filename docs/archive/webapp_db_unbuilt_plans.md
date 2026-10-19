# Webapp + Neon: plans that were never built

> ARCHIVED 2026-10-16. Moved out of `docs/specs/webapp_db.md`, whose section
> numbers are kept with a one-line pointer to the matching section here.
> Nothing below describes the current system. Live workbench storage (SQLite
> cache, review outbox, sync to Neon) is `docs/workbench_storage.md`; the
> applied DDL is `db/schema.sql` and `db/migrations/`.

Checked against the code on 2026-10-16: there is no `metascience db-pull`
command, no `webapp/lib/data/` directory, no `@neondatabase/serverless` or
Auth.js dependency in `webapp/package.json`, no `batch --from-queue` option,
and no fast-screen runner. The `drafts` table exists in `db/schema.sql` but
`drafts.py` writes files only.

## 1. Write topology: the hosted/DB-mode rows

The original table's rows for review data and its hosted column:

| Writer | Local/file mode | Hosted/DB mode |
|---|---|---|
| Webapp reviews / submissions / status | `review.json` 2.0 (run-scoped) via the round-trip | DB-first (`reviews`, `run_review_status`, `paper_reviews`); `review.json` export via `db-pull` |
| Triage decisions (queue/dismiss) | n/a (the funnel needs the DB) | `triage_events` (state via derived view — trim 2026-08-21) |
| Drafts | `paper_dir/drafts/*.md` | `drafts` table |

**One master per deployment for review data.** `db-pull` refuses loudly when the file is
newer than the last push (§5). Screens have no file master — the DB is their home, and
`db-push` never touches `kind='screen'` rows.

## 4. db-pull

`metascience db-pull` exports DB reviews back to `review.json` (Phase 8; the path hosted
reviewers' verdicts take back to the file world). **Refusal rule:** when the on-disk
review file's hash/mtime shows it is newer than `sync_state.last_push_at` /
`source_sha256` for that paper's `review` scope, db-pull REFUSES loudly and names both
timestamps — one master per deployment, and a silent overwrite in either direction is the
forbidden outcome.

## 6. Fast screen agent — DB contract (runner is Phase 9; substrate is 5N)

- **DB-native from day one**: the screen runner writes `runs` (`kind='screen'`, its own
  `run_uid`, `backend='openrouter'` + model id) + `findings` directly, with an optional
  local JSONL journal for offline replay. A cheap triage pass over thousands of XMLs must
  not mint thousands of per-paper directories — that recreates the many-small-files
  problem the DB exists to fix.
- **A screen is a funnel, not evidence** (the Table-1 screening lesson), encoded structurally:
  `producer='fast_screen'` rows are always `severity_is_provisional=true`, never
  `impossible` (both CHECK-enforced, §2), provisional ≤ 4 (app-layer rule in the runner),
  `computed_by='model_reading'`; excluded by default from accusation-grade fire-rate
  stats (query 1's WHERE); they get their own screen-performance stats (query 3) instead.
- Screen techniques come from the registry-derived namespace (`check_flow_arithmetic`,
  `internal_contradiction`, …) so screen→full confirmation joins are equality joins.
- **Funnel semantics**: a `problem` screen finding fires `triage_events 'flagged'`; the
  webapp queue view lists `triage_state='flagged'` papers; a human (or batch policy)
  moves them to `queued`; `metascience batch --from-queue <corpus>` consumes the queue in
  hosted mode. The triage-queue UI (human writes) arrives with Phase 8's auth.

## 7. Webapp storage seam — `webapp/lib/data/`

One interface, **both backends from Phase 5N**: `loadIndex`, `paperView`, `writeReview`,
`queryFindings`, `stats`, `mediaUrl`, plus `triage` and `drafts`.

- `fileBackend.ts` — extracted from today's code; the offline/no-DB fallback.
- `dbBackend.ts` — findings/stats/query READS from Phase 5N when `METASCIENCE_DB_URL` is
  set; review WRITES stay file-master locally until Phase 8's auth exists, then
  reviews/paper_reviews go DB-first for hosted deployments.
- Backend selection: `METASCIENCE_DB_URL` set → db, else file. No third mode.
- Hosted driver: `@neondatabase/serverless` from the Next.js routes; short transactions
  only. Auth: Auth.js (NextAuth v5) magic-link with the Neon adapter, adapter tables
  separate from `users` (§2), mapped by verified email at sign-in; `users.role` gates
  admin vs reviewer. Media stays files/object storage (R2/S3) — **HTTP Range required**
  (the blink-comparison scrubber contract).
- Drift check: `metascience corpus-stats --from-db` output is asserted equal to the
  file-scan mode on the migrated corpora (two implementations of the same stats must not
  diverge silently).

## 13. Phase mapping: phases 8 and 9

| Phase | Delivers from this spec |
|---|---|
| **8 — Hosting** | Auth.js + reviewer identity off localStorage; reviews/paper_reviews DB-first; `db-pull` + refusal rule (§4); triage-queue UI writes (§6); `drafts` table live; object-storage media (R2/S3, HTTP Range); per-deployment cutover. |
| **9 — Fast screen (future)** | The screen runner + screen-performance stats. Its substrate (triage tables, producer enum, CHECK invariants, query 3) already exists from 5N/Phase 1 — **no schema break at any point**. |
