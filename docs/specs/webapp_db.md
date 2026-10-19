# Spec: Webapp + Findings Database (findings store, review surface, dashboards)

> **2026-10-16: the database is LOCAL.** The remote Neon database was retired; the
> findings database is a PostgreSQL server on this machine, named by one
> `METASCIENCE_DB_URL`, and `db_push.resolve_db_url` refuses any URL naming another
> host. Mentions of Neon below are the original 2026-08 design record.

- **Status:** approved 2026-08-21, **partially implemented**. Live workbench
  storage (a private SQLite cache plus a review outbox that syncs to the local Postgres;
  media stay files; no Auth.js) is
  [docs/workbench_storage.md](../workbench_storage.md). This file remains the
  DDL / phase intent. The unbuilt plans (Phase 8 hosting, `db-pull`, the
  `webapp/lib/data/` seam, the fast-screen runner) were written up in a
  separate archived note ("the archive" below), removed on 2026-10-19 and
  kept in git history;
  their sections here are one-line pointers so section numbers stay stable. The
  `--sev1…--sev9` CSS variables of §8 do not exist either (`globals.css` keeps the
  five-enum `--sev-*` colours).
- **Source of truth for this spec's DDL and write topology:** THIS DOCUMENT. It was derived from the approved 2026-08 overhaul plan (a working file at `~/.claude/plans/`, since retired and reused for later planning — do not consult it)
  (Parts C2–C6, C7, cross-plan reconciliation R1–R6, master phasing). Where this spec and
  the plan's earlier prose differ, the plan's reconciliation/verification corrections —
  restated here as normative — win. Field names follow Part A (`producer`, `severity`,
  `provisional_severity`, `tool_verdict`, `outcome`, `computed_by`).
- **Implemented by master phases:** **5N** (Neon core: DDL, db-push, `[db]` extra,
  `corpus-stats --from-db` parity; the storage seam was not built), **6** (webapp: severity
  1–9 UI, part of index v2, findings-query + stats dashboard, drafts). **8** (hosting:
  Auth.js, DB-first reviews, `db-pull`, triage UI, object-storage media) was not built. Phase 2's webapp items
  (persisted-anchor `paper-view`, `passage_key` fix, `HtmlArticlePane` haystack) are
  specced in `docs/specs/anchors.md`, not here. Phase 9's screen *runner* is future work;
  its DB substrate ships in 5N and its producer enum value in Phase 1.

## 0. The committed decision

**Neon Postgres IS the findings database** (Dan, 2026-08-21). Files remain the per-run
forensic archive — prompts-as-sent, tool-call ledgers, transcripts, `findings.json`,
`analysis_code/` — written by the pipeline exactly as today; Neon is the canonical
*queryable* store that the webapp, dashboards, and `findings-query` read.

Normative consequences:

1. `db-push` **auto-fires at run completion** (and from the migration converter) when
   `METASCIENCE_DB_URL` is set. It is **best-effort**: an unreachable database never fails a
   paid run. A failed push appends to `<corpus>/db_push_pending.jsonl`;
   `metascience db-push --retry-pending` drains the backlog (`db_push.py`).
2. Python driver is `psycopg[binary]` behind a **`[db]` optional extra**. An absent driver
   is a **named refusal** (structured error naming the missing package and the extra),
   never a silent skip — the statcheck lesson, applied to the DB.
3. Every findings row mirrors the whole v2 record (`record` JSONB), upserted idempotently
   by natural keys: sync is replayable, drift is hash-detectable, and the file archive can
   always rebuild the DB.
4. Readers select backend by `METASCIENCE_DB_URL`: DB when set (the normal case), file
   scan otherwise. The file path is the offline fallback, not the primary.

**WSL rationale** (why the DB, one line): `/mnt/c` goes through 9P, so every stat/open is
a cross-VM RPC — pain scales with latency × file-count, not bandwidth. The DB deletes the
many-small-files index/table/stats scans; it does not fix media bytes (corpus on ext4
today, object storage in Phase 8). Persisted anchors + the single cached index already
shrink the two biggest 9P offenders before any DB exists.

## 1. Write topology (who writes what, per deployment mode)

| Writer | Local/file mode | Hosted/DB mode |
|---|---|---|
| Full pipeline runs | files written as the run archive; `db-push` fires automatically at run completion when `METASCIENCE_DB_URL` is set (best-effort → `db_push_pending.jsonl` on failure) | same (runs happen on machines with the corpus) |
| Fast screen agent (runner not built, §6) | DB-native insert (+ optional local JSONL journal for offline replay); **no per-paper files** | same |
| Webapp reviews / submissions / status | `review.json` 2.0 (run-scoped) | The planned DB-first path and `db-pull` export were not built (archive §1). The live workbench commits decisions to a local SQLite outbox and syncs them to the local Postgres findings database (docs/workbench_storage.md). |
| Paper views (who OPENED a results page) | `views.json` beside the paper (`views_io`) | `views.json` — **not mirrored**, deliberately: §2 has no table that wants it, and a view is not a review row |
| Triage decisions (queue/dismiss) | n/a | `triage_events` table exists; no writer was built (archive §1, §6) |
| Drafts | `paper_dir/drafts/*.md` | `drafts` table exists; `drafts.py` does not write it |

A view is kept OUT of `review.json` on purpose: `webapp_index.review_state`
answers `reviewed: True` because that file exists, and `sort_papers` orders the
work queue off that answer, so a per-open write there would demote every paper
anyone merely opened. It is also the only per-paper write on a hot path — every
page open — and isolating it keeps that traffic away from the decision file
(`views_io`'s module docstring carries the full argument).

**One master per deployment for review data.** The planned `db-pull` refusal rule
is archived (archive §1, §4). Screens have no file master, and `db-push` never touches
`kind='screen'` rows.

## 2. DDL v2 (normative)

Create tables in **dependency order**: corpora → papers → users → runs → run_channels →
findings → reviews → run_review_status → paper_reviews → triage_events → drafts →
sync_state. (authors/paper_authors and finding_aliases: DEFERRED, see notes below.) (`run_channels` is shown beside papers below for
readability; its FK to `runs` means it MUST be created after `runs`.)

```sql
create table corpora (
  id bigint generated always as identity primary key,
  name text unique not null,
  papers_root text,
  created_at timestamptz not null default now()
);

create table papers (
  id bigint generated always as identity primary key,
  corpus_id bigint not null references corpora(id),
  dir text,                          -- corpus-relative; NULL for DOI-only screen targets
  doi text, paper_slug text,         -- doi NORMALIZED at ingest: lowercased, resolver prefix stripped
  title text,
  journal text,                      -- verbatim Crossref string
  journal_full text,                 -- = metadata 1.1's journal_normalized (Part A §A5)
  year int,
  first_author text,
  authors jsonb,                     -- authors_list verbatim (expanded names)
  metadata jsonb,                    -- metadata.json verbatim
  sources jsonb,                     -- (channel states live on run_channels — one copy)
  -- triage_state column DEFERRED (trim 2026-08-21): state is the derived
  -- view over triage_events until queue reads need the denormalized column.
  -- When added: text not null default 'unscreened', check in ('unscreened',
  -- 'screened_clean','flagged','queued','in_full_review','full_reviewed',
  -- 'dismissed'), plus the papers_triage_idx index.
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (dir is not null or doi is not null)
);
-- IDENTITY: no generated natural key — identity derived from a MUTABLE column silently
-- changes when a DOI-only screen target later gains a dir, splitting the screen findings
-- and the full review across two paper rows and zeroing the confirmation join forever.
create unique index papers_dir_uq on papers (corpus_id, dir) where dir is not null;
create unique index papers_doi_uq on papers (corpus_id, lower(doi)) where dir is null;
-- Resolution order for db-push/ingest: match (corpus_id, dir) first, then
-- (corpus_id, lower(doi)) over ALL rows; insert only when neither matches.
-- PROMOTION RULE: fetching a queued DOI-only paper sets `dir` on the SAME row (identity
-- persists; the row simply leaves the doi-unique partial index). Duplicate fetches of one
-- DOI into two dirs remain two papers (real case: 14 ids already sit in two corpus roots —
-- paper identity is per corpus, never global-by-DOI).
create index papers_journal_idx on papers (journal_full, year);
create index papers_doi_idx     on papers (lower(doi));
-- papers_triage_idx arrives with the deferred triage_state column.

-- AUTHOR TRACKING: DEFERRED (Dan, 2026-08-21 — "hold off on how we track
-- authors, but make sure to expand to full names"). No authors/paper_authors
-- tables and no by_author stats in v1: name-string identity merges homonyms
-- ('Y. Wang' is one row), which is accusation-adjacent in a forensic tool;
-- ORCID or a defensible person-key is the reopening condition. What DOES ship
-- now is the DATA: papers.authors carries metadata 1.1's authors_list with
-- FULL EXPANDED NAMES (the expand_author_names port: initials-only given
-- names detected, title-based refetch, update only when more complete), so
-- the tracking layer can be added later without refetching anything.

-- Channel states are facts about a RUN, not a paper (the image track ran during a
-- specific review; two runs can differ), so they key by run — a replayed older push can
-- never regress a newer run's denominators, and there is exactly ONE copy (papers carries
-- no channels JSONB in the DB). Paper-level channel view = the CURRENT run's projection.
create table run_channels (
  run_id bigint not null references runs(id),
  channel text not null,
  state text not null check (state in
    ('ran','ran_result_discarded','refused','did_not_run','unknown')),
  detail text,
  primary key (run_id, channel)
);

create table runs (
  id bigint generated always as identity primary key,
  paper_id bigint not null references papers(id),
  run_uid text unique not null,      -- Part A's r_<hash>; screens mint their own
  kind text not null,                -- full_review|screen|image_track|text_track|legacy —
                                     -- TEXT + app validation, not CHECK: run kinds evolve
  name text,                         -- forensic_review* dir name; NULL for DB-native screens
  status text check (status in ('complete','partial','failed','incomplete')),
  verdict text, confidence text, paper_severity smallint,
  backend text, model text,          -- 'openrouter'/model id for screens
  pipeline_version text, git_sha text, prompt_sha256 text, registry_sha256 text,
  analysed_at timestamptz, analysed_at_source text,
  cost_usd numeric, wall_seconds numeric,
  pushed_at timestamptz,             -- sync watermark: when db-push last wrote this run
  meta jsonb,                        -- run_meta verbatim (stages, tokens, sandbox)
  unique (id, paper_id)              -- lets findings enforce run/paper agreement structurally
);
create index runs_paper_kind_idx on runs (paper_id, kind, analysed_at desc);

-- THE CURRENT-RUN CONCEPT: without it every stats query double-counts re-run papers and
-- the webapp's run selection is undefined. Mirrors the file-side rule (newest usable
-- review dir). BOTH NULL guards are load-bearing:
--   * `analysed_at desc NULLS LAST` — converter-backdated runs can lack analysed_at, and
--     Postgres DESC defaults to NULLS FIRST; an undated legacy run must not outrank a
--     dated fresh one.
--   * `coalesce(status in (...), false)` — status is nullable, and a NULL boolean under
--     DESC sorts FIRST; without the coalesce an unknown-status run outranks a complete one.
create view current_runs as
  select distinct on (paper_id, kind) *
  from runs
  order by paper_id, kind,
           coalesce(status in ('complete','partial'), false) desc,
           analysed_at desc nulls last, id desc;
-- Every stats/webapp query joins findings through current_runs unless it is explicitly a
-- run-history query.

create table findings (
  id bigint generated always as identity primary key,
  run_id bigint not null references runs(id),
  paper_id bigint not null references papers(id),   -- denormalized: the dashboard join
  finding_id text not null,          -- v2 stable content hash (f_<16hex>)
  producer text not null,            -- incl. 'fast_screen' from day one (Phase 1 enum) —
                                     -- the screen's arrival is not a schema break
  technique text, computed_by text,
  title text, description text,
  outcome text not null check (outcome in ('problem','pass','undecided')),
  severity smallint check (severity between 1 and 9),
  provisional_severity smallint check (provisional_severity between 1 and 9),
  severity_is_provisional boolean not null,
  impossible boolean not null default false,
  quarantined boolean not null default false,
  adjudication_action text check (adjudication_action in
    ('kept','merged','downgraded','upgraded','discarded')),
  adjudication jsonb, tool_verdict jsonb,
  anchors jsonb, anchor_summary jsonb,
  web_sources jsonb, basis text,
  legacy_original_id text,           -- review.json decision-key join (PREFIXED, verbatim)
  record jsonb not null,             -- whole v2 record, byte-mirrorable
  created_at timestamptz not null default now(),
  unique (run_id, finding_id),
  foreign key (run_id, paper_id) references runs (id, paper_id),
  -- screen invariants by CONSTRAINT, not construction alone:
  check (producer <> 'fast_screen'
         or (impossible = false and severity_is_provisional))
);
create index findings_tech_sev_idx  on findings (technique, severity desc);
create index findings_paper_idx     on findings (paper_id);
create index findings_producer_idx  on findings (producer);
create index findings_impossible_px on findings (technique) where impossible;
-- Deliberately NO GIN index on anchor_summary: no query in the plan uses containment, and
-- an index consumed by nothing is write amplification (LESSONS #3). Add jsonb_path_ops
-- GIN if and when a real containment query exists.

-- Content-hash drift across re-runs: the same real defect can hash differently when the
-- hasher gains a field, anchors improve, or the model extracts "3.53" vs "3.530" — and a
-- reviewer's false_positive verdict must NOT silently orphan (the LESSONS-class
-- substitution). Hasher inputs are canonicalized (numeric normalization); the hasher
-- version is recorded in the finding record.
-- finding_aliases: DEFERRED (Dan, 2026-08-21). Under the multi-report model
-- (§reviews below) every run's report is reviewed INDEPENDENTLY, so verdicts
-- never carry across runs and alias-matching is not needed for correctness.
-- The cross-run "previously reviewed" HINT is a plain equality join: identical
-- evidence hashes to the identical finding_id across runs, so
--   prior verdicts = current_reviews rows on OTHER runs of the same paper
--   with the same issue_key
-- — shown as context in the GUI, never inherited. The orphaned-reviews report
-- on db-push stays (it protects the file-import path). Reopen aliases only if
-- observed hash drift makes the equality hint miss real matches in practice.

-- App users are SEPARATE from Auth.js's adapter tables (which own their own
-- users/accounts/sessions shapes): Auth.js authenticates, then maps to this table by
-- verified email at sign-in. Keeps FKs bigint and auth swappable. email is NULLABLE
-- because legacy review.json rows carry only a free-text reviewer name; migration mints
-- kind='legacy' users from distinct names (identity = legacy_name).
create table users (
  id bigint generated always as identity primary key,
  email text unique, name text,
  legacy_name text unique,           -- the review.json free-text identity
  role text not null default 'reviewer' check (role in ('reviewer','admin')),
  created_at timestamptz not null default now()
);

-- MULTI-REPORT REVIEW (NORMATIVE — Dan, 2026-08-21): a paper may hold
-- MULTIPLE findings reports from multiple runs (different dates, different
-- pipeline versions — a v1.2 run and a later v1.5 run), and **each report is
-- reviewed independently**. A verdict belongs to the RUN whose report the
-- reviewer read — never to the paper. Verdicts NEVER carry across runs
-- (two reviews across a version boundary are not comparable — the version
-- invariant); the GUI may SHOW another run's verdict on the same finding_id
-- as context ("marked false_positive in the 2026-08 v1.2 run"), via the
-- equality join described at the deferred-aliases note above.
--
-- LITERALLY append-only: no UPDATE ever, no is_current flip (a two-statement flip is racy
-- under a one-shot HTTP driver, and ON CONFLICT..DO UPDATE would mutate history).
-- Current verdict := latest row per (RUN, issue, reviewer), via the view below.
create table reviews (
  id bigint generated always as identity primary key,
  run_id bigint not null references runs(id),   -- THE RUN WHOSE REPORT WAS REVIEWED —
                                     -- the scope of every verdict (multi-report model)
  paper_id bigint not null references papers(id),   -- denormalized for paper rollups
  finding_pk bigint references findings(id)
    on delete set null,              -- THE ROW THE REVIEWER SAW — provenance, never
                                     -- re-pointed. SET NULL semantics: db-push's
                                     -- replace-within-run delete (§4) must not be BLOCKED
                                     -- by an FK on a reviewed finding; a nulled pk still
                                     -- joins via (run_id, issue_key) and lands in the
                                     -- orphaned-reviews report.
  issue_key text not null,           -- v2 finding_id, or the PREFIXED legacy key
                                     -- ('image:IMGDUP-3'), exactly as review.json writes it
  reviewer_id bigint not null references users(id),
  decision text,                     -- app-validated against review_io.ALL_DECISIONS
                                     -- (numeric correct_minor|correct_significant|
                                     -- false_positive; image true_issue|unsure|
                                     -- false_positive_same_condition|false_positive_other;
                                     -- legacy 'correct'); deliberately NO CHECK — the
                                     -- vocabulary evolves
  note text,
  submitted_to_pubpeer boolean not null default false,
  submitted_to_editor boolean not null default false,
  pubpeer_url text,
  extra jsonb,                       -- review.json's extra-keys-survive contract
                                     -- (route, verified_by_hand, …)
  decided_at timestamptz not null default now()
);
create index reviews_lookup_idx on reviews (run_id, issue_key, reviewer_id,
                                            decided_at desc, id desc);
create view current_reviews as
  select distinct on (run_id, issue_key, reviewer_id) *
  from reviews order by run_id, issue_key, reviewer_id,
                        decided_at desc, id desc;

-- Per-(run, reviewer) review STATUS — each report is its own review unit.
-- DELIBERATE EXCEPTION to append-only (status, not judgment); updated in place.
create table run_review_status (
  run_id bigint not null references runs(id),
  reviewer_id bigint not null references users(id),
  status text not null default 'unreviewed'
    check (status in ('unreviewed','in_progress','complete')),
  updated_at timestamptz not null default now(),
  primary key (run_id, reviewer_id)
);

-- Paper-level record: PubPeer/letter submissions are about the PAPER (they cite
-- findings from whichever run), so they stay paper-scoped. Same in-place
-- exception. ROLLUP RULE for the index/table cell with N reviewers × M runs:
-- a run is 'complete' if ANY reviewer completed it; the paper cell shows the
-- LATEST run's status plus an "N older reviewed runs" affordance; decision
-- disagreement on the same issue within one run renders a chip — surfaced,
-- never averaged.
create table paper_reviews (
  paper_id bigint not null references papers(id),
  reviewer_id bigint not null references users(id),
  submitted_to_pubpeer boolean, pubpeer_url text, pubpeer_note text,
  letter_to_editor_sent boolean, letter_sent_at timestamptz,
  extra jsonb,                       -- 1.0 gates + unknown keys, verbatim
  updated_at timestamptz not null default now(),
  primary key (paper_id, reviewer_id)
);

-- The screen→full-review funnel, auditable: append-only event log. TRIM
-- (Dan, 2026-08-21): triage state starts as a DERIVED VIEW over the log
-- (computed at queue-page read time), NOT a trigger-maintained papers column —
-- one less piece of in-database logic before the Phase-9 screen agent exists
-- to feed it. papers.triage_state and the trigger are the scale-up path,
-- added only when queue reads measurably need them; the state-machine rules
-- below bind the view exactly as they would bind the trigger.
create table triage_events (
  id bigint generated always as identity primary key,
  paper_id bigint not null references papers(id),
  event text not null,               -- screened_clean|flagged|queued|dismissed|
                                     -- full_review_started|full_review_done —
                                     -- TEXT + app validation (events will evolve)
  run_id bigint references runs(id), -- the screen or review run behind it
  technique text,                    -- what was flagged/dismissed (scopes dismissals)
  actor_id bigint references users(id),  -- NULL when machine-generated
  note text,
  at timestamptz not null default now()
);
create index triage_events_paper_idx on triage_events (paper_id, at desc);
-- STATE-MACHINE RULES (enforced in the trigger/recompute function):
--  * a human 'dismissed' is scoped to (run_id, technique): a later screen firing on a
--    DIFFERENT technique re-flags; a re-screen repeating the same dismissed technique
--    does NOT (human decisions survive re-screens);
--  * machine events never override human ones for the same scope;
--  * db-push of a full_review run emits full_review_started/full_review_done so
--    file-mode reviews advance the funnel too — otherwise every fully reviewed paper
--    sits at 'unscreened' and the queue view lies.

create table drafts (                -- PubPeer/letter drafts, DB-side in hosted mode
  id bigint generated always as identity primary key,
  paper_id bigint not null references papers(id),
  kind text not null check (kind in ('pubpeer','letter')),
  body text not null, finding_ids jsonb, model text,
  created_by bigint references users(id),
  created_at timestamptz not null default now(),
  edited boolean not null default false
);

create table sync_state (            -- the db-pull refusal rule's data:
  paper_id bigint not null references papers(id),   -- "is the file newer than
  scope text not null,               -- 'review' | 'findings' | …   the last push?"
  last_push_at timestamptz, source_sha256 text,
  primary key (paper_id, scope)
);
```

Vocabulary validation split (normative): `producer` and `technique` are validated by
db-push at insert time **at the app layer, deliberately not CHECK constraints** — both
vocabularies evolve. One canonical producer list (owned by the findings-v2 schema in
`src/forensic_metascience_ai_toolkit/schema/`) and one technique namespace (registry-derived, per Part A §A1).

## 3. db-push replay semantics

Insert-only upserts are not enough. Normative rules:

1. **One transaction PER RUN** (short transactions; a rule kept from the Neon era): upsert the
   paper (resolution order §2) and the run, then the findings.
2. **Preserve completed reports** (updated 2026-09-09): resolve the document digest
   before writing. Changed report content receives a linked revision ID; a sealed
   ID cannot be replaced. An archive-first push uses the saved document to recognize
   an identical report, even before its compatibility metadata has been populated.
3. Identical reports hydrate missing indexed findings once. Archive sync rejects
   conflicting finding records; replay does not change sealed evidence. Legacy
   replacement/upsert statements operate only after revision identity is resolved,
   and sealed finding updates/deletes are rejected by database triggers.
4. `runs.pushed_at` is the run-level sync watermark; `sync_state(paper_id, scope,
   last_push_at, source_sha256)` is the review-file watermark. "The file is newer than
   the last push" must be answerable from the DB alone, or §5 is unimplementable.
5. **(DEFERRED with finding_aliases)** — every push still PRINTS the orphaned-reviews
   report; the heuristic alias population is reopened only if hash drift is observed.
   Original text: every push populates `finding_aliases` by heuristic match against the paper's
   prior runs (same paper + producer + technique, overlapping anchor region; `matched_by`
   records which rule) and **prints the orphaned-reviews report**: a human verdict whose
   `issue_key` matches nothing current and aliases to nothing is REPORTED, never silently
   dropped.
6. `legacy_original_id` stores the PREFIXED review key exactly as review.json writes it
   (`image:IMGDUP-3`); the migrator scopes legacy joins to the run the workbench
   displayed at review time (newest-with-report), recording ambiguity when a paper's
   multiple legacy runs reuse slugs.
7. Failure path: any error → append to `<corpus>/db_push_pending.jsonl`, return
   success to the pipeline (best-effort contract, §0); `db-push --retry-pending`
   drains it.
8. `db-push` never touches `kind='screen'` rows (they are DB-native, §7).

## 4. db-pull

Not built: there is no `metascience db-pull` command. The planned export and its
refusal rule were in an archived note, removed 2026-10-19 and kept in git history.

**Workbench read fallback (2026-09-01).** `review_issues.collect_issues` reads the
analyst findings from disk first; when a paper has NO `forensic_review*/` directory
it asks `db_push.fetch_paper_runs` (identity: `(corpus, dir)`, then `lower(doi)`
over all corpora — a DOI hit is labelled `corpus/run` in the run picker). The
response carries `source.kind ∈ {disk, database, none}` and the database TRI-STATE
(`hit` / `miss` / `unavailable`, with detail), and the empty-pane message renders
that state in words: an unreachable database must never read as a clean paper. This is
a READ path only — nothing is written back to disk, and the `db-pull` refusal rule
above is untouched. Motivating case (2026-09-01, when the database was the shared
Neon instance): `10.1002--jfa2.70171`, run on another machine and auto-pushed, 24
findings in the database and none on this disk. Since 2026-10-16 the database is
local only, so the fallback now covers runs whose files were moved or deleted.

## 5. Proof queries (normative — each rule below was a caught bug in the first draft)

Rules every stats/webapp query must obey:

- **Join through `current_runs`** — else re-run papers double-count.
- **Split adjudicator-discarded from fires** — "ran and discarded" must never read as
  "fired" (the tri-state doctrine).
- **Denominators come from `run_channels`/`current_runs`, never from `findings`** — a
  paper where GRIM ran and emitted nothing must be in the denominator.
- **"Ran" for denominator purposes means `state IN ('ran','ran_result_discarded')`** — a
  channel that demonstrably ran and retained nothing STILL RAN. Counting only `'ran'`
  would drop ~369 of the 370 measured image-channel papers and inflate that fire rate by
  orders of magnitude. (This CORRECTED rule overrides the plan's earlier C3 wording.)
- **Track-kind runs count** — fire-rate joins include
  `kind IN ('full_review','image_track','text_track')`; the migrated masliah corpus
  (544 track-only image findings) must never read as zero fires.
- **Human-review joins go through `current_reviews`** — per-reviewer latest rows;
  disagreement visible, never averaged away.

```sql
-- 1) Fire rate per technique (accusation-grade: screens excluded, discarded split out,
--    current run only, track kinds included)
select f.technique,
  count(*) filter (where f.outcome='problem'
                   and coalesce(f.adjudication_action,'kept') <> 'discarded') as fires,
  count(*) filter (where f.adjudication_action = 'discarded')  as discarded,
  count(distinct f.paper_id) filter (where f.outcome='problem'
                   and coalesce(f.adjudication_action,'kept') <> 'discarded') as papers_fired,
  count(*) filter (where f.impossible)                          as impossible_count
from findings f
join current_runs cr on cr.id = f.run_id
     and cr.kind in ('full_review','image_track','text_track')
where f.producer <> 'fast_screen'
group by 1;

-- 2) Impossible-rate per tool per journal, with an honest denominator
--    (papers whose numeric channel RAN, not papers that happen to have rows)
select p.journal_full, f.technique,
       count(*) filter (where f.impossible)  as n_impossible,
       den.n_papers_ran
from findings f
join current_runs cr on cr.id = f.run_id
     and cr.kind in ('full_review','image_track','text_track')
join papers p on p.id = f.paper_id
join lateral (
  select count(distinct cr2.paper_id) as n_papers_ran
  from current_runs cr2
  join run_channels rc on rc.run_id = cr2.id
  join papers p2 on p2.id = cr2.paper_id
  where rc.channel = 'numeric'
    and rc.state in ('ran','ran_result_discarded')   -- discarded STILL RAN
    and p2.journal_full = p.journal_full
) den on true
group by 1, 2, 4;

-- 3) Screen performance. Denominator = flagged papers that WERE fully reviewed (a clean
--    full review counts as reviewed-and-unconfirmed; dropping it inflates the
--    confirmation rate). An adjudicator-discarded match must NOT count as confirmed —
--    the confirmation rate decides whether the funnel is trusted.
select s.technique,
  count(distinct s.paper_id)  as flagged,
  count(distinct rr.paper_id) as reviewed,          -- reviewed, not "had rows"
  count(distinct fr.paper_id) filter (where fr.outcome = 'problem') as confirmed
from findings s
join runs sr on sr.id = s.run_id and sr.kind = 'screen'
left join current_runs rr on rr.paper_id = s.paper_id and rr.kind = 'full_review'
left join findings fr on fr.run_id = rr.id and fr.technique = s.technique
     and coalesce(fr.adjudication_action, 'kept') <> 'discarded'
where s.producer = 'fast_screen' and s.outcome = 'problem'
group by 1;

-- 4) False-positive rate per technique from human review (per-reviewer current rows;
--    disagreement surfaced, never averaged)
select f.technique, r.decision, count(*)
from current_reviews r join findings f on f.id = r.finding_pk
group by 1, 2;
```

The Phase 5N/C7 golden stats fixture (3 tiny papers) asserts the denominators — and for
query 3 asserts BOTH corrections: the clean-review case lands in `reviewed`, and the
adjudicator-discarded case does not land in `confirmed`.

## 6. Fast screen agent — DB contract (runner is Phase 9; substrate is 5N)

Not built: the screen runner and `batch --from-queue`. The contract is in the archive
(§6). Its substrate exists in `db/schema.sql`: the `fast_screen` CHECK on `findings`,
`triage_events`, and proof query 3.

## 7. Webapp storage seam — `webapp/lib/data/`

Not built: the `webapp/lib/data/` seam (`fileBackend.ts` / `dbBackend.ts`), the
`@neondatabase/serverless` hosted driver and Auth.js. The plan is in the archive (§7).
The webapp reads through the workbench service (docs/workbench_storage.md).

- Drift check (built): `metascience corpus-stats --from-db` output is asserted equal to
  the file-scan mode on the migrated corpora (two implementations of the same stats must
  not diverge silently).

## 8. Severity 1–9 in the webapp

- **One generated constants module**: CLI verb `metascience gen-webapp-constants` emits
  checked-in `webapp/lib/constants.gen.ts` from `severity9.as_json()` — levels, labels,
  9-step colors, the canonical `FIVE_TO_NINE` legacy map
  ({suspicious: 3, highly_suspicious: 4, impossible: 5}), and the review decision vocab.
  A Python test (`tests/test_webapp_constants.py`) regenerates and **byte-compares**,
  with a mutated-ladder known-positive so the drift guard is proven live (LESSONS #4).
  `severity.ts` and `projectTableSort.ts` re-export from it. Python `tools/severity.py`
  and `report_render.SEVERITY_RANK` stay the tool-level 5-enum world — tools keep
  speaking the evidence enum.
- **Colors**: sequential concern ramp — slate (1–2) → amber/orange (3–5) → red (6–7) →
  deep-red/aubergine (8–9), with a deliberate hue break at 8 (misconduct is a kind
  change, not a shade). CSS vars `--sev1…--sev9`, light + dark, emitted by the codegen.
- **IssueList**: badges like `S7 · fatal error`. Legacy-mapped runs show
  `S5 · impossible (legacy)` — S5 per the canonical FIVE_TO_NINE map, one value, stated
  once; **a mapped value is never presented as an assigned one**. Hide-below-N control
  (localStorage); hidden findings render as ONE collapsed count line, never silent
  absence. Queue order stays computed in Python (`issue_sort_key`: severity-9 desc, then
  impossible flag, consequence, warrant, model rank).
- **ProjectTable**: numeric `worst_severity_9` chip + `S≥7 / S≥5 / total` counts.

## 9. webapp_index v2 (schema `"3"`)

As built, the index `schema_version` stayed `"1.0"`. Per-run `severity9_counts`,
`worst_severity_9` and `severity_axis` (`assigned` | `provisional`) exist; the schema
`"3"` bump, per-technique counts, the `legacy_mapped` marker, `n_drafts` and
`anchor_health` were not built. The plan follows.

Additions: per-run `severity9_counts` (**present-at-zero** — an absent count is not a
zero count), `worst_severity_9`, per-technique counts, `severity_axis: "legacy_mapped"`
marker on converted runs; per-paper rollups + `n_drafts` + `anchor_health {anchored,
page_only, unanchored}`. **The five-state channel vocabulary
(`ran|ran_result_discarded|refused|did_not_run|unknown`) is untouched** — it is a core
invariant (`tests/test_webapp_index.py` is the contract). The scanner reads new file
names (`findings.v2.json`, per-agent artifacts); the stage1/stage2 fallback for
archives was removed in 1.100.0. A missing index keeps its loud `IndexMissing`
behavior across the schema bump.

## 10. Fire-rate dashboard + findings-query

- New `webapp/app/project/[project]/stats/page.tsx` + `/api/stats`, consuming Part A's
  `corpus_stats.json` (file mode) or SQL (DB mode). Contents: per-technique table
  (fires / papers_fired / impossible_count / confirmed-vs-FP — the review-outcome
  columns are joined by the DASHBOARD from review data (review.json now,
  `current_reviews` later); `corpus_stats.json` itself stays review-free), five-state
  channel stacked bar, by-journal/year/author tables with per-severity mini-histograms
  (by-author surfaces carry the "grouped by name string, not by person" disclaimer, §2),
  and a dedicated impossible-per-tool table (GRIM/GRIMMER/DEBIT…). Fire-rate
  stats carry `computed_by` as a dimension (plan R4): `registry_tool` /
  `agent_code` / `model_reading` / `deterministic_track` counts are shown
  separately, never folded together.
- **Denominator rule is contractual**: every rate renders as `n/N` with
  N = papers whose channel state ∈ {`ran`, `ran_result_discarded`} (§5's corrected
  rule); `refused`/`did_not_run`/`unknown` are printed separately, never folded into
  "did not fire".
- Drill-down: counts link to a filtered ProjectTable and to `/api/findings` → new CLI
  verb `metascience findings-query --project-dir … [--technique] [--min-severity]
  [--producer] [--journal] [--year] --json`. **DB-backed against the findings database when
  `METASCIENCE_DB_URL` is set — the normal case**; the file-scan implementation is the
  offline/no-DB fallback, not the primary path.

## 11. PubPeer + letter drafts (on demand — NOT part of the analysis agents)

- `src/forensic_metascience_ai_toolkit/drafts.py`: one `claude -p` subprocess with an injectable
  runner; structured refusal on failure; **it NEVER posts anywhere**.
- CLI: `metascience draft-pubpeer <paper_dir> --findings f_9c1e22ab,f_77aa01bc` and
  `metascience draft-letter …`. Findings are addressed by hash `finding_id`; bare slugs
  are accepted and resolved — ambiguity is refused, not guessed.
- Input: findings-v2 records + metadata citation + the published disclaimer. PubPeer
  register: courteous, numbers-first, verbatim quotes, reproduction commands,
  inconsistency-never-intent, severity language capped by the errorlevels rung. Letter
  variant adds journal/salutation + COPE framing.
- Storage: `paper_dir/drafts/{kind}-{timestamp}.md` with front-matter. The planned
  hosted-mode `drafts` table writes and the index's `n_drafts` were not built.
- Webapp: `/api/draft` (POST generate — its own long route-local timeout; GET list/read;
  PUT save edits) + a modal with finding checkboxes (pre-checked: severity ≥ 5 and not
  reviewer-marked false positive), an editable textarea, and **Copy — there is no Post
  button**.
- Tests: `tests/test_drafts.py` — mocked transport, refusal shape.

## 12. Test obligations (webapp/DB slice of the master plan)

- `tests/test_webapp_constants.py`: regenerate + byte-compare + mutated-ladder
  known-positive (§8).
- Golden stats fixture: 3 tiny papers; asserts every denominator rule in §5, including
  the two screen-query corrections.
- `corpus-stats --from-db` ≡ file-scan on migrated corpora (§7); corpus-stats must also
  reproduce the measured 370/369 image-channel facts.
- `webapp/test/smoke.mjs` extensions: `passage_key` collision regression, anchor→target
  translation, legacy-map + hide-below-N, stats shape.
- db-push tests: replace-within-run leaves no stale finding; no-op replay writes no
  record; orphaned-review report fires on a known orphan (a guard that never fires is
  indistinguishable from a broken one); missing `psycopg` → named refusal.

## 13. Phase mapping (what lands when)

| Phase | Delivers from this spec |
|---|---|
| **5N — Neon core** | DDL migrations (§2, dependency order); `db-push` (§3: replace-within-run, aliases, orphaned-reviews report, auto-push hook at run completion, `--retry-pending`); `[db]` extra with `psycopg[binary]` + named refusal; `lib/data/` seam with BOTH backends (§7, not built); DB-backed findings-query/stats reads; `corpus-stats --from-db` parity check. Reviews remain file-master locally. |
| **6 — Webapp** | Severity 9-axis UI + legacy badges + hide-below-N (§8); webapp_index v2 (§9); findings-query + stats dashboard (§10); drafts.py + PubPeer/letter UI (§11). Public-website consumer contract pinned (reads `findings.v2.json`/`report.json`; fixture check in the website repo's ingestor). |
| **8 — Hosting** | Not built; archived (archive §13). |
| **9 — Fast screen (future)** | Not built; archived (archive §13). The substrate exists from 5N/Phase 1. |

## 14. `corpus_stats.json` producer contract (A6 — resolves critic open #4)

Produced by `src/forensic_metascience_ai_toolkit/corpus_stats.py` / `metascience
corpus-stats <corpus-root> [--from-db]` (`schema_version: "1.0"`). The
`--from-db` SQL mode's output is asserted EQUAL to the file-scan mode on the
migrated corpora (the two-implementations drift check, Phase 5N).

```jsonc
{ "schema_version": "1.0", "generated_at": "…", "corpus": "…", "n_papers": 396,
  "channel_status": { "<channel>": {"ran": 370, "ran_result_discarded": 0,
                       "refused": 26, "did_not_run": 0, "unknown": 0} },
  "per_technique": [
    { "technique": "grim_check", "computed_by": "registry_tool",   // R4 dimension
      "n_papers_ran": 41,          // channel state ∈ {ran, ran_result_discarded}
      "n_papers_fired": 9, "fire_rate": 0.2195,
      "n_findings": {"problem": 17, "pass": 210, "undecided": 12},
      "n_impossible": 6, "by_severity": {"3": 5, "4": 6, "5": 6},
      "n_discarded_by_adjudicator": 3 } ],                          // never in fires
  "by_journal": [ {"journal_normalized": "…", "n_papers": 12, "n_papers_fired": 3,
                   "n_findings_problem": 7, "n_impossible": 2, "worst_severity": 6} ],
  "by_year": [],                    // by_author DEFERRED with author tracking;
                                    // rendered with the name-string disclaimer
  "tool_calls": { "source": "toolcalls_ledger", "available_for_n_papers": 4,
                  "per_tool": [{"tool": "grim_check", "n_calls": 60, "n_validated": 58}] } }
```

Denominator discipline is CONTRACTUAL (LESSONS #2): every rate names its
denominator; `n_papers_ran` counts channel states `ran` +
`ran_result_discarded`; `refused`/`did_not_run`/`unknown` are counted and
printed separately, never folded into "did not fire"; adjudicator-discarded
rows are `n_discarded_by_adjudicator`, never `fires`. `corpus_stats.json` is
review-free — the dashboard joins review outcomes itself (§10). Everything
except `tool_calls` is SQL-derivable from the §2 tables (the §5 proof
queries are the reference implementations); track-kind runs are included so
migrated track-only corpora never read as zero fires. Golden fixture: 3 tiny
papers + one migrated track-only paper + one adjudicator-discarded finding +
one clean-review screen case, denominators asserted by hand.

## 15. Multi-report review (normative — Dan, 2026-08-21)

A paper holds MULTIPLE findings reports — one per run, with different dates
and pipeline versions (v1.2 now, v1.5 later) — and **each report is reviewed
independently**.

- **GUI**: the paper page gains a RUN PICKER (the index already carries the
  full `runs[]` list per paper: name, date, `pipeline_version`, verdict).
  Default = current run; any run's report opens read/review-able. Each run
  shows its own review status (`run_review_status`). A finding whose
  `finding_id` also appears in another reviewed run of the same paper shows
  that run's verdict as a CONTEXT chip ("false_positive in the v1.2 run,
  2026-08-14") — displayed, never inherited.
- **API**: `/api/paper` gains `?run=<name|run_uid>` (default current);
  `/api/review` payloads carry the run identity; `paper-view`/`review-write`
  CLI verbs gain `--run`.
- **review.json → SCHEMA 2.0 (run-scoped)**: verdicts nest under the run —
  `{"schema_version": "2.0", "paper": {…paper-level pubpeer/letter…},
  "runs": {"<review-dir-name>": {"status": …, "issues": {…}}}}`.
  Migration: 1.x verdicts are assigned to the run the workbench displayed at
  review time (newest-with-report — the same rule the legacy converter uses),
  recorded with `migrated_from: "1.1"`. 1.x files remain readable; first
  write upgrades in place (the review_io normalise pattern).
- **Stats**: review-outcome joins (FP rates per technique) aggregate over
  ALL reviewed runs, labeled per run's pipeline_version where it matters —
  which is exactly what makes cross-version FP-rate comparison possible
  (the metascience payoff of independent per-run review).

## Versioned component history (2026-09-09)

Project executions group per-paper reports and component runs. `component_items` is immutable candidate evidence; `findings` remains report output. Component reviews name an owning run. `image_publication` is the current eligibility projection; `published_component_items` requires matching input and policy stamps and deduplicates revisions. Run and artifact history are never rewritten by screening or export. Image and copy/paste candidates do not inflate comprehensive-report counts.

The DDL is not repeated here. It is `db/migrations/003_analysis_history.sql`
(identical to `src/forensic_metascience_ai_toolkit/analysis_history.sql`, and included in
`db/schema.sql`); the narrative is [docs/analysis_history.md](../analysis_history.md).
