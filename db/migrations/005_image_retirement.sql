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
