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
