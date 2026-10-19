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
