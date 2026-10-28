-- Ads pivot: ad-library signals, social activity, scam flags, pilots. Additive only.

-- ------------------------------------------------------------------ businesses: new signals
alter table public.businesses
  add column if not exists ads_status       text check (ads_status in ('active', 'none', 'unknown')),
  add column if not exists ads_active_count int,
  add column if not exists ads_longest_days int,
  add column if not exists ads_last_seen_at timestamptz,
  add column if not exists ads_sample       jsonb,          -- up to 3 {ad_archive_id, start_date, body, cta_type, link}
  add column if not exists social           jsonb,          -- {facebook, instagram, tiktok, ig_last_post_at, ig_followers, ig_posts_30d}
  add column if not exists scam_flag        text check (scam_flag in ('hard', 'soft')),
  add column if not exists scam_terms       text[];

-- ------------------------------------------------------------------ Meta Ad Library index (Apify, weekly)
create table if not exists public.ad_library_ads (
  ad_archive_id   text primary key,
  page_id         text,
  page_name       text,
  page_name_norm  text,
  wa_phone_e164   text,                                   -- parsed from a wa.me / api.whatsapp.com link
  link_url        text,
  cta_type        text,
  body            text,
  start_date      date,
  first_seen_at   timestamptz not null default now(),
  last_seen_at    timestamptz not null default now(),
  query           text,
  raw             jsonb
);
create index if not exists ad_library_ads_name_idx on public.ad_library_ads (page_name_norm);
create index if not exists ad_library_ads_wa_idx on public.ad_library_ads (wa_phone_e164);

-- ------------------------------------------------------------------ pilots
create table if not exists public.pilots (
  id               uuid primary key default gen_random_uuid(),
  lead_id          uuid not null references public.leads (id),
  route            text check (route in ('A', 'B', 'C', 'backup')),
  offer            jsonb,                                  -- the offer form (pilot kit 01)
  budget_kes       integer not null default 5000,
  mpesa_ref        text,
  paid_at          timestamptz,
  access_granted_at timestamptz,
  submitted_at     timestamptz,
  live_at          timestamptz,
  ends_at          timestamptz,
  targets          jsonb,                                  -- agreed day-0 targets {chats, visits}
  winner_ad        text,
  outcome          text check (outcome in ('converted', 'declined', 'extended')),
  plan_price_kes   integer,
  notes            text,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);
create index if not exists pilots_lead_idx on public.pilots (lead_id);

create table if not exists public.pilot_days (
  pilot_id      uuid not null references public.pilots (id) on delete cascade,
  day           integer not null check (day between 1 and 14),
  date          date,
  spend_kes     integer,
  reach         integer,
  chats         integer,
  serious       integer,
  visits        integer,
  ad_breakdown  jsonb,                                     -- per-ad chats / spend
  note          text,
  primary key (pilot_id, day)
);

create or replace function public.pilots_touch()
returns trigger language plpgsql set search_path = public as $$
begin
  new.updated_at := now();
  return new;
end $$;
revoke execute on function public.pilots_touch() from public, anon, authenticated;

drop trigger if exists pilots_touch_upd on public.pilots;
create trigger pilots_touch_upd before update on public.pilots
  for each row execute function public.pilots_touch();

-- ------------------------------------------------------------------ RLS (same pattern as 20261009000002_rls.sql)
do $$
declare
  t text;
begin
  foreach t in array array['ad_library_ads', 'pilots', 'pilot_days'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('drop policy if exists admin_all on public.%I', t);
    execute format(
      'create policy admin_all on public.%I for all to authenticated using (public.is_admin()) with check (public.is_admin())',
      t
    );
    execute format('revoke all on public.%I from anon', t);
    execute format('grant select, insert, update, delete on public.%I to authenticated', t);
    execute format('grant all on public.%I to service_role', t);
  end loop;
end $$;

-- ------------------------------------------------------------------ settings seed
insert into public.settings (key, value, updated_by) values
  ('daily_mix', '{"land_developers": 20, "property_agency": 10}'::jsonb, 'seed'),
  ('outreach_whatsapp', '""'::jsonb, 'seed')
on conflict (key) do nothing;
