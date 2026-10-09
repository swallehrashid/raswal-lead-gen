-- Triggers and RPC functions used by the pipeline and dashboard.

-- ------------------------------------------------------------------ updated_at + status events
create or replace function public.leads_touch()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if tg_op = 'INSERT' then
    insert into public.events (lead_id, type, payload)
    values (new.id, 'created', jsonb_build_object('status', new.status, 'track', new.track, 'rank', new.rank));
    return new;
  end if;
  new.updated_at := now();
  if new.status is distinct from old.status then
    insert into public.events (lead_id, type, payload)
    values (new.id, 'status', jsonb_build_object('from', old.status, 'to', new.status));
  end if;
  return new;
end;
$$;

drop trigger if exists leads_touch_ins on public.leads;
create trigger leads_touch_ins after insert on public.leads
  for each row execute function public.leads_touch();

drop trigger if exists leads_touch_upd on public.leads;
create trigger leads_touch_upd before update on public.leads
  for each row execute function public.leads_touch();

-- ------------------------------------------------------------------ reserve promotion (brief §10.4)
-- Called when a lead is skipped or marked No WhatsApp. Promotes the best reserve in the
-- same list and track. Runs as the caller, so RLS applies (admin only).
create or replace function public.promote_reserve(p_lead_id uuid)
returns uuid
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_list_date date;
  v_track track;
  v_promoted uuid;
begin
  select list_date, track into v_list_date, v_track from public.leads where id = p_lead_id;
  if v_list_date is null then
    return null;
  end if;
  select id into v_promoted
  from public.leads
  where list_date = v_list_date and track = v_track and status = 'reserve'
  order by rank asc
  limit 1
  for update skip locked;
  if v_promoted is not null then
    update public.leads set status = 'shortlisted' where id = v_promoted;
    insert into public.events (lead_id, type, payload)
    values (v_promoted, 'promoted', jsonb_build_object('replaces', p_lead_id));
  end if;
  return v_promoted;
end;
$$;

revoke all on function public.promote_reserve(uuid) from public, anon;
grant execute on function public.promote_reserve(uuid) to authenticated, service_role;

-- ------------------------------------------------------------------ API usage counter (pipeline)
create or replace function public.increment_api_usage(p_month text, p_api text, p_sku text, p_n integer)
returns integer
language sql
security invoker
set search_path = public
as $$
  insert into public.api_usage (month, api, sku, count)
  values (p_month, p_api, p_sku, p_n)
  on conflict (month, api, sku) do update set count = public.api_usage.count + excluded.count
  returning count;
$$;

revoke all on function public.increment_api_usage(text, text, text, integer) from public, anon, authenticated;
grant execute on function public.increment_api_usage(text, text, text, integer) to service_role;

-- ------------------------------------------------------------------ DB + storage usage (Stats screen)
create or replace function public.usage_stats()
returns jsonb
language plpgsql
stable
security definer
set search_path = public
as $$
begin
  if not (public.is_admin() or coalesce(auth.role(), '') = 'service_role') then
    raise exception 'not allowed';
  end if;
  return jsonb_build_object(
    'db_bytes', pg_database_size(current_database()),
    'storage_bytes', coalesce((
      select sum(coalesce((metadata ->> 'size')::bigint, 0))
      from storage.objects where bucket_id = 'leadgen'
    ), 0),
    'storage_files', (select count(*) from storage.objects where bucket_id = 'leadgen')
  );
end;
$$;

revoke all on function public.usage_stats() from public, anon;
grant execute on function public.usage_stats() to authenticated, service_role;
