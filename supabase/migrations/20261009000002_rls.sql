-- Row level security (brief §14.3).
--
-- The brief's policy is: auth.jwt() ->> 'email' = (select value->>'admin_email' from settings where key='admin').
-- Used directly as a policy on `settings` itself, that sub-select recurses into the same
-- policy ("infinite recursion detected in policy"). So the check lives in a SECURITY DEFINER
-- function, which reads `settings` as its owner and is used by every policy.

create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select coalesce(
    lower(auth.jwt() ->> 'email') = (
      select lower(value ->> 'admin_email') from public.settings where key = 'admin'
    ),
    false
  );
$$;

revoke all on function public.is_admin() from public;
grant execute on function public.is_admin() to authenticated, service_role;

do $$
declare
  t text;
begin
  foreach t in array array[
    'businesses', 'places_raw', 'audits', 'psi_cache', 'runs', 'evaluations', 'facts',
    'leads', 'events', 'suppression', 'search_cells', 'api_usage', 'settings'
  ] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('drop policy if exists admin_all on public.%I', t);
    execute format(
      'create policy admin_all on public.%I for all to authenticated using (public.is_admin()) with check (public.is_admin())',
      t
    );
    -- Explicit grants (newer Supabase projects no longer auto-grant the Data API roles).
    execute format('revoke all on public.%I from anon', t);
    execute format('grant select, insert, update, delete on public.%I to authenticated', t);
    execute format('grant all on public.%I to service_role', t);
  end loop;
end $$;

grant usage on schema public to authenticated, service_role;
grant usage, select on all sequences in schema public to authenticated, service_role;
