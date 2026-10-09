-- Private storage bucket `leadgen` (brief §13.4, §14.3). The dashboard reads files through
-- 1-hour signed URLs; the pipeline uploads with the service-role key (bypasses RLS).
-- Paths: teasers/{list_date}/{lead_id}.jpg · current/{place_id}.jpg · brand/{place_id}/logo.png|hero.jpg

insert into storage.buckets (id, name, public)
values ('leadgen', 'leadgen', false)
on conflict (id) do update set public = false;

drop policy if exists leadgen_admin_select on storage.objects;
drop policy if exists leadgen_admin_insert on storage.objects;
drop policy if exists leadgen_admin_update on storage.objects;
drop policy if exists leadgen_admin_delete on storage.objects;

create policy leadgen_admin_select on storage.objects
  for select to authenticated
  using (bucket_id = 'leadgen' and public.is_admin());

create policy leadgen_admin_insert on storage.objects
  for insert to authenticated
  with check (bucket_id = 'leadgen' and public.is_admin());

create policy leadgen_admin_update on storage.objects
  for update to authenticated
  using (bucket_id = 'leadgen' and public.is_admin())
  with check (bucket_id = 'leadgen' and public.is_admin());

create policy leadgen_admin_delete on storage.objects
  for delete to authenticated
  using (bucket_id = 'leadgen' and public.is_admin());
