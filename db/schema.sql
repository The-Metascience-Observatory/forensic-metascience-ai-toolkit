-- findings database schema v2 (local Postgres)
-- NORMATIVE SOURCE: docs/specs/webapp_db.md section 2 -- this file is that
-- DDL reordered into executable dependency order (the spec shows
-- run_channels beside papers for readability; here it follows runs).
-- Regenerate deliberately when the spec changes; tests compare the two.
-- Deferred by decision (2026-08-21): authors/paper_authors, finding_aliases,
-- papers.triage_state column + trigger (state is a derived view until queue
-- reads need it).

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

create table run_channels (
  run_id bigint not null references runs(id),
  channel text not null,
  state text not null check (state in
    ('ran','ran_result_discarded','refused','did_not_run','unknown')),
  detail text,
  primary key (run_id, channel)
);

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

-- Versioned analysis history (also deployed by migration 003).
-- Additive history migration; existing paper reports and review IDs are preserved.
create table if not exists executions (
  execution_uid text primary key,
  corpus_id bigint not null references corpora(id),
  mode text not null,
  name text not null,
  requested_components jsonb not null,
  configuration jsonb not null,
  provenance jsonb not null,
  started_at timestamptz, finished_at timestamptz,
  status text not null
);
-- A project component can fail or return zero pairs without a paper owner.
alter table runs alter column paper_id drop not null;
alter table runs add column if not exists execution_uid text references executions(execution_uid);
alter table runs add column if not exists parent_run_uid text references runs(run_uid) deferrable initially deferred;
alter table runs add column if not exists revision_of text references runs(run_uid) deferrable initially deferred;
alter table runs add column if not exists component text;
alter table runs add column if not exists sealed_digest text;
alter table runs add column if not exists history_record jsonb;
alter table runs add column if not exists execution_status text;
create table if not exists component_items (
  id bigint generated always as identity primary key,
  run_id bigint not null references runs(id),
  item_uid text not null,
  owner_paper_id bigint not null references papers(id),
  record jsonb not null,
  unique (run_id,item_uid), unique (id,run_id)
);
create table if not exists component_item_papers (
  item_id bigint not null references component_items(id),
  paper_id bigint not null references papers(id),
  primary key (item_id,paper_id)
);
create table if not exists run_artifacts (
  run_id bigint not null references runs(id),
  artifact_uid text not null,
  role text not null,
  content_sha256 text not null,
  size_bytes bigint not null,
  local_reference text not null,
  record jsonb not null,
  primary key (run_id,artifact_uid)
);
alter table reviews add column if not exists component_item_pk bigint;
alter table reviews add column if not exists event_uid text;
create unique index if not exists reviews_event_uid_uq on reviews(event_uid) where event_uid is not null;
do $$ begin
 if not exists(select 1 from pg_constraint where conname='reviews_component_run_fk' and conrelid='reviews'::regclass) then
  alter table reviews add constraint reviews_component_run_fk foreign key (component_item_pk,run_id) references component_items(id,run_id);
 end if;
 if not exists(select 1 from pg_constraint where conname='reviews_single_target' and conrelid='reviews'::regclass) then
  alter table reviews add constraint reviews_single_target check (finding_pk is null or component_item_pk is null);
 end if;
end $$;
-- Current eligibility is a separate projection. Saved component records are immutable.
create table if not exists image_publication (
  corpus_id bigint not null references corpora(id),
  paper_id bigint not null references papers(id),
  item_uid text not null,
  policy text not null,
  eligible boolean not null,
  source_fingerprint text,
  updated_at timestamptz not null default now(),
  primary key (corpus_id,paper_id,item_uid)
);
create or replace function protect_sealed_history() returns trigger language plpgsql as $$
begin
 if old.sealed_digest is not null and
    (new.sealed_digest is distinct from old.sealed_digest or new.history_record is distinct from old.history_record) then
   raise exception 'sealed run content cannot be replaced; create a revision';
 end if;
 return new;
end $$;
drop trigger if exists sealed_history_guard on runs;
create trigger sealed_history_guard before update on runs for each row execute function protect_sealed_history();
create or replace function protect_component_evidence() returns trigger language plpgsql as $$
begin
 if exists(select 1 from runs where id=old.run_id and sealed_digest is not null) then
   raise exception 'sealed component evidence cannot be changed';
 end if;
 if tg_op='DELETE' then return old; end if;
 return new;
end $$;
drop trigger if exists component_evidence_guard on component_items;
create trigger component_evidence_guard before update or delete on component_items for each row execute function protect_component_evidence();
drop trigger if exists artifact_evidence_guard on run_artifacts;
create trigger artifact_evidence_guard before update or delete on run_artifacts for each row execute function protect_component_evidence();
create or replace view published_component_items as
 select distinct on (i.owner_paper_id,i.item_uid) i.*
 from component_items i join runs r on r.id=i.run_id
 join image_publication p on p.paper_id=i.owner_paper_id and p.item_uid=i.item_uid
 where p.eligible and i.record->'screening'->>'inputs_stamp'=p.source_fingerprint
   and i.record->'screening'->>'policy'=p.policy
 order by i.owner_paper_id,i.item_uid,r.analysed_at desc nulls last,r.id desc;

-- Report hydration is allowed once; a sealed finding may never be replaced.
drop trigger if exists report_evidence_guard on findings;
create trigger report_evidence_guard before update or delete on findings for each row execute function protect_component_evidence();
create index if not exists runs_execution_component_idx on runs(execution_uid,component);
create index if not exists component_items_owner_idx on component_items(owner_paper_id);
create index if not exists component_item_papers_paper_idx on component_item_papers(paper_id);

-- Archived review events are judgments, never an editable current-state row.
create or replace function protect_history_review() returns trigger language plpgsql as $$
begin
 if old.event_uid is not null then
   raise exception 'history reviews are append-only; append another decision';
 end if;
 if tg_op='DELETE' then return old; end if;
 return new;
end $$;
drop trigger if exists history_review_guard on reviews;
create trigger history_review_guard before update or delete on reviews for each row execute function protect_history_review();

-- Retention state is separate from immutable scientific run content.
alter table runs add column if not exists retired_at timestamptz;
alter table runs add column if not exists replacement_run_uid text references runs(run_uid);

create or replace function protect_component_evidence() returns trigger language plpgsql as $$
declare replacement text; expected jsonb;
begin
 -- Logical no-op rewrites permit physical compaction without changing evidence.
 if tg_op='UPDATE' and new is not distinct from old then return new; end if;
 if exists(select 1 from runs where id=old.run_id and sealed_digest is not null) then
   if tg_op='UPDATE' and tg_table_name in ('component_items','run_artifacts') then
     select replacement_run_uid into replacement from runs
       where id=old.run_id and retired_at is not null;
     if replacement is not null then
       if tg_table_name='component_items' then
         expected:=jsonb_build_object('id',to_jsonb(old)->>'item_uid','retired',true,'replacement_run',replacement);
       else
         expected:=jsonb_build_object('name',old.record->>'name','retired',true);
       end if;
       if new.record=expected and (to_jsonb(new)-'record')=(to_jsonb(old)-'record') then
         return new;
       end if;
     end if;
   end if;
   raise exception 'sealed component evidence cannot be changed';
 end if;
 if tg_op='DELETE' then return old; end if;
 return new;
end $$;

-- Explicit user-requested image reset. Keep run identities to prevent reimport.
alter table runs add column if not exists retirement_reason text;
alter table runs add column if not exists retired_at timestamptz;
alter table runs add column if not exists replacement_run_uid text references runs(run_uid);

create or replace function protect_component_evidence() returns trigger language plpgsql as $$
declare replacement text; expected jsonb;
begin
 if tg_op='DELETE' and exists(select 1 from runs where id=old.run_id
     and retired_at is not null and retirement_reason='user_requested_rerun'
     and (component='image_forensics' or kind='image_track')) then return old; end if;
 -- Logical no-op rewrites permit physical compaction without changing evidence.
 if tg_op='UPDATE' and new is not distinct from old then return new; end if;
 if exists(select 1 from runs where id=old.run_id and sealed_digest is not null) then
   if tg_op='UPDATE' and tg_table_name in ('component_items','run_artifacts') then
     select replacement_run_uid into replacement from runs
       where id=old.run_id and retired_at is not null;
     if replacement is not null then
       if tg_table_name='component_items' then
         expected:=jsonb_build_object('id',to_jsonb(old)->>'item_uid','retired',true,'replacement_run',replacement);
       else
         expected:=jsonb_build_object('name',old.record->>'name','retired',true);
       end if;
       if new.record=expected and (to_jsonb(new)-'record')=(to_jsonb(old)-'record') then
         return new;
       end if;
     end if;
   end if;
   raise exception 'sealed component evidence cannot be changed';
 end if;
 if tg_op='DELETE' then return old; end if;
 return new;
end $$;

create or replace function protect_history_review() returns trigger language plpgsql as $$
begin
 if tg_op='DELETE' and exists(select 1 from runs where id=old.run_id
     and retired_at is not null and retirement_reason='user_requested_rerun'
     and (component='image_forensics' or kind='image_track')) then return old; end if;
 if old.event_uid is not null then
   raise exception 'history reviews are append-only; append another decision';
 end if;
 if tg_op='DELETE' then return old; end if;
 return new;
end $$;

create or replace function refuse_cleared_image_payload() returns trigger language plpgsql as $$
begin
 if exists(select 1 from runs where id=new.run_id and retired_at is not null
     and retirement_reason='user_requested_rerun'
     and (component='image_forensics' or kind='image_track')) then
   raise exception 'Image results explicitly cleared; create a new analysis run';
 end if;
 return new;
end $$;
drop trigger if exists cleared_image_guard on component_items;
create trigger cleared_image_guard before insert on component_items
 for each row execute function refuse_cleared_image_payload();
drop trigger if exists cleared_image_guard on run_artifacts;
create trigger cleared_image_guard before insert on run_artifacts
 for each row execute function refuse_cleared_image_payload();
drop trigger if exists cleared_image_guard on findings;
create trigger cleared_image_guard before insert on findings
 for each row execute function refuse_cleared_image_payload();
