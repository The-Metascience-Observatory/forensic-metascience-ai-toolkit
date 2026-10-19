-- Generated from workbench.remote.migration_sql; tested for equality.

create table if not exists workbench_changes (
 revision bigint generated always as identity primary key,
 entity text not null, key text not null, deleted boolean not null,
 changed_at timestamptz not null default now(),
 unique(entity,key)
);
create or replace function workbench_serialize() returns trigger language plpgsql as $$
begin
 perform pg_advisory_xact_lock(7168340291);
 return null;
end $$;
create or replace function workbench_journal() returns trigger language plpgsql as $$
declare obj jsonb; k jsonb := '[]'::jsonb; col text;
begin
 if TG_OP='UPDATE' and NEW is not distinct from OLD then return NEW; end if;
 if TG_OP='DELETE' then obj:=to_jsonb(OLD); else obj:=to_jsonb(NEW); end if;
 foreach col in array TG_ARGV loop k:=k || jsonb_build_array(obj->col); end loop;
 insert into workbench_changes(entity,key,deleted) values(TG_TABLE_NAME,k::text,TG_OP='DELETE')
 on conflict(entity,key) do update set revision=DEFAULT,deleted=excluded.deleted,changed_at=excluded.changed_at;
 if TG_OP='DELETE' then return OLD; else return NEW; end if;
end $$;


create table if not exists component_item_derived (
 item_id bigint primary key references component_items(id) on delete cascade,
 image_type text not null,
 panel_types jsonb not null default '{}'::jsonb,
 typer text,
 derived_at timestamptz not null default now()
);
create index if not exists component_item_derived_type on component_item_derived(image_type);


drop trigger if exists workbench_serialize on corpora;
create trigger workbench_serialize before insert or update or delete on corpora
 for each statement execute function workbench_serialize();
drop trigger if exists workbench_journal on corpora;
create trigger workbench_journal after insert or update or delete on corpora
 for each row execute function workbench_journal('id');


drop trigger if exists workbench_serialize on papers;
create trigger workbench_serialize before insert or update or delete on papers
 for each statement execute function workbench_serialize();
drop trigger if exists workbench_journal on papers;
create trigger workbench_journal after insert or update or delete on papers
 for each row execute function workbench_journal('id');


drop trigger if exists workbench_serialize on runs;
create trigger workbench_serialize before insert or update or delete on runs
 for each statement execute function workbench_serialize();
drop trigger if exists workbench_journal on runs;
create trigger workbench_journal after insert or update or delete on runs
 for each row execute function workbench_journal('id');


drop trigger if exists workbench_serialize on executions;
create trigger workbench_serialize before insert or update or delete on executions
 for each statement execute function workbench_serialize();
drop trigger if exists workbench_journal on executions;
create trigger workbench_journal after insert or update or delete on executions
 for each row execute function workbench_journal('execution_uid');


drop trigger if exists workbench_serialize on findings;
create trigger workbench_serialize before insert or update or delete on findings
 for each statement execute function workbench_serialize();
drop trigger if exists workbench_journal on findings;
create trigger workbench_journal after insert or update or delete on findings
 for each row execute function workbench_journal('id');


drop trigger if exists workbench_serialize on component_items;
create trigger workbench_serialize before insert or update or delete on component_items
 for each statement execute function workbench_serialize();
drop trigger if exists workbench_journal on component_items;
create trigger workbench_journal after insert or update or delete on component_items
 for each row execute function workbench_journal('id');


drop trigger if exists workbench_serialize on users;
create trigger workbench_serialize before insert or update or delete on users
 for each statement execute function workbench_serialize();
drop trigger if exists workbench_journal on users;
create trigger workbench_journal after insert or update or delete on users
 for each row execute function workbench_journal('id');


drop trigger if exists workbench_serialize on reviews;
create trigger workbench_serialize before insert or update or delete on reviews
 for each statement execute function workbench_serialize();
drop trigger if exists workbench_journal on reviews;
create trigger workbench_journal after insert or update or delete on reviews
 for each row execute function workbench_journal('id');


drop trigger if exists workbench_serialize on run_artifacts;
create trigger workbench_serialize before insert or update or delete on run_artifacts
 for each statement execute function workbench_serialize();
drop trigger if exists workbench_journal on run_artifacts;
create trigger workbench_journal after insert or update or delete on run_artifacts
 for each row execute function workbench_journal('run_id','artifact_uid');


drop trigger if exists workbench_serialize on run_channels;
create trigger workbench_serialize before insert or update or delete on run_channels
 for each statement execute function workbench_serialize();
drop trigger if exists workbench_journal on run_channels;
create trigger workbench_journal after insert or update or delete on run_channels
 for each row execute function workbench_journal('run_id','channel');


drop trigger if exists workbench_serialize on component_item_papers;
create trigger workbench_serialize before insert or update or delete on component_item_papers
 for each statement execute function workbench_serialize();
drop trigger if exists workbench_journal on component_item_papers;
create trigger workbench_journal after insert or update or delete on component_item_papers
 for each row execute function workbench_journal('item_id','paper_id');


drop trigger if exists workbench_serialize on image_publication;
create trigger workbench_serialize before insert or update or delete on image_publication
 for each statement execute function workbench_serialize();
drop trigger if exists workbench_journal on image_publication;
create trigger workbench_journal after insert or update or delete on image_publication
 for each row execute function workbench_journal('corpus_id','paper_id','item_uid');


drop trigger if exists workbench_serialize on run_review_status;
create trigger workbench_serialize before insert or update or delete on run_review_status
 for each statement execute function workbench_serialize();
drop trigger if exists workbench_journal on run_review_status;
create trigger workbench_journal after insert or update or delete on run_review_status
 for each row execute function workbench_journal('run_id','reviewer_id');


drop trigger if exists workbench_serialize on paper_reviews;
create trigger workbench_serialize before insert or update or delete on paper_reviews
 for each statement execute function workbench_serialize();
drop trigger if exists workbench_journal on paper_reviews;
create trigger workbench_journal after insert or update or delete on paper_reviews
 for each row execute function workbench_journal('paper_id','reviewer_id');


drop trigger if exists workbench_serialize on component_item_derived;
create trigger workbench_serialize before insert or update or delete on component_item_derived
 for each statement execute function workbench_serialize();
drop trigger if exists workbench_journal on component_item_derived;
create trigger workbench_journal after insert or update or delete on component_item_derived
 for each row execute function workbench_journal('item_id');
