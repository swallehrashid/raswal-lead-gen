-- Raswal Lead Generator: schema (brief §14).
-- Subcategory is plain text (not an enum) so keys can be renamed in config only.
-- gen_random_uuid() is built into Postgres 13+, so no extension is needed.


-- ------------------------------------------------------------------ enums
do $$ begin
  create type lead_status as enum (
    'shortlisted', 'reserve', 'approved', 'skipped',
    'sent', 'no_whatsapp', 'replied', 'interested',
    'demo_queued', 'demo_sent', 'negotiating',
    'won', 'lost', 'no_response', 'snoozed', 'opted_out'
  );
exception when duplicate_object then null; end $$;

do $$ begin
  create type track as enum ('web', 'content');
exception when duplicate_object then null; end $$;

do $$ begin
  create type site_status as enum ('none', 'social_as_site', 'dead', 'insecure', 'free_builder', 'weak', 'good');
exception when duplicate_object then null; end $$;

-- ------------------------------------------------------------------ businesses
create table if not exists public.businesses (
  place_id          text primary key,
  name              text not null,
  name_norm         text not null,
  display_name      text,
  subcategory       text not null,
  types             text[] not null default '{}',
  primary_type      text,
  address           text,
  area              text,
  lat               double precision,
  lng               double precision,
  maps_url          text,
  phone_e164        text,
  phone_type        text,
  website_url       text,
  rating            numeric(2,1),
  review_count      integer not null default 0,
  newest_review_at  timestamptz,
  branch_count      integer not null default 1,
  manages_listings  integer not null default 0,
  merged_place_ids  text[] not null default '{}',
  first_seen_at     timestamptz not null default now(),
  last_seen_at      timestamptz not null default now()
);
create index if not exists businesses_phone_idx on public.businesses (phone_e164);
create index if not exists businesses_subcategory_idx on public.businesses (subcategory);

-- ------------------------------------------------------------------ places_raw (purged after 30 days)
create table if not exists public.places_raw (
  id          bigint generated always as identity primary key,
  place_id    text not null,
  fetched_at  timestamptz not null default now(),
  payload     jsonb not null
);
create index if not exists places_raw_fetched_idx on public.places_raw (fetched_at);
create index if not exists places_raw_place_idx on public.places_raw (place_id);

-- ------------------------------------------------------------------ audits (latest audit per business)
create table if not exists public.audits (
  place_id                 text primary key references public.businesses (place_id) on delete cascade,
  audited_at               timestamptz not null default now(),
  site_status              site_status not null,
  website_url              text,
  final_url                text,
  status_code              integer,
  https_ok                 boolean,
  cert_error               boolean not null default false,
  redirect_chain           jsonb not null default '[]',
  html_bytes               integer,
  title                    text,
  platform                 text,
  copyright_year           integer,
  has_whatsapp_link        boolean,
  has_tel_link             boolean,
  meta_viewport            boolean,
  has_video                boolean,
  blog_last_date           date,
  word_count               integer,
  social_links             jsonb not null default '{}',
  weak_signals             text[] not null default '{}',
  dead_marker              text,
  psi_perf                 numeric(5,1),
  psi_lcp_s                numeric(6,2),
  current_screenshot_path  text,
  logo_url                 text,
  logo_path                text,
  colours                  jsonb not null default '{}',
  hero_image_url           text,
  hero_path                text,
  raw                      jsonb not null default '{}'
);

-- ------------------------------------------------------------------ PSI cache per domain (30 days)
create table if not exists public.psi_cache (
  domain           text primary key,
  fetched_at       timestamptz not null default now(),
  perf             numeric(5,1),
  lcp_s            numeric(6,2),
  screenshot_path  text
);

-- ------------------------------------------------------------------ runs
create table if not exists public.runs (
  id                 uuid primary key default gen_random_uuid(),
  list_date          date not null,
  subcategory        text,
  started_at         timestamptz not null default now(),
  finished_at        timestamptz,
  status             text not null default 'running',   -- running | ok | failed | skipped
  dry_run            boolean not null default false,
  skipped_reason     text,
  places_calls       integer not null default 0,
  psi_calls          integer not null default 0,
  gemini_calls       integer not null default 0,
  raw_candidates     integer not null default 0,
  passed_gates       integer not null default 0,
  enriched           integer not null default 0,
  qualified_web      integer not null default 0,
  qualified_content  integer not null default 0,
  shipped_web        integer not null default 0,
  shipped_content    integer not null default 0,
  gate_counts        jsonb not null default '{}',
  errors             jsonb not null default '[]'
);
create index if not exists runs_list_date_idx on public.runs (list_date desc);

-- ------------------------------------------------------------------ evaluations (one per business per night)
create table if not exists public.evaluations (
  id           uuid primary key default gen_random_uuid(),
  run_id       uuid references public.runs (id) on delete set null,
  place_id     text not null references public.businesses (place_id) on delete cascade,
  list_date    date not null,
  subcategory  text not null,
  track        track,
  site_status  site_status,
  pre_score    numeric(6,2),
  score        numeric(6,2),
  breakdown    jsonb not null default '{}',
  scores       jsonb not null default '{}',
  gate_codes   text[] not null default '{}',
  selected     boolean not null default false,
  created_at   timestamptz not null default now()
);
create index if not exists evaluations_list_date_idx on public.evaluations (list_date);
create index if not exists evaluations_place_idx on public.evaluations (place_id);

-- ------------------------------------------------------------------ facts
create table if not exists public.facts (
  evaluation_id  uuid primary key references public.evaluations (id) on delete cascade,
  facts          jsonb not null default '[]',
  review_facts   jsonb not null default '[]'
);

-- ------------------------------------------------------------------ leads
create table if not exists public.leads (
  id                 uuid primary key default gen_random_uuid(),
  place_id           text not null references public.businesses (place_id) on delete cascade,
  evaluation_id      uuid references public.evaluations (id) on delete set null,
  list_date          date not null,
  subcategory        text not null,
  track              track not null,
  rank               integer not null,
  status             lead_status not null default 'shortlisted',
  site_status        site_status,
  area               text,
  top_fact_code      text,
  -- message
  message_variants   jsonb not null default '[]',
  message_final      text,
  chosen_variant     integer,
  used_fact_ids      text[] not null default '{}',
  variant_source     text,
  poster_lines       jsonb not null default '[]',
  -- assets
  teaser_path        text,
  slug               text,
  social_state       text check (social_state in ('none', 'stale', 'active', 'polished')),
  brand              jsonb not null default '{}',
  -- review
  skip_reason        text,
  notes              text,
  -- timeline
  approved_at        timestamptz,
  sent_at            timestamptz,
  fu1_due            date,
  fu1_sent_at        timestamptz,
  fu2_due            date,
  fu2_sent_at        timestamptz,
  replied_at         timestamptz,
  reply_type         text,
  snoozed_until      date,
  -- demo and outcome
  demo_type          track,
  demo_queued_at     timestamptz,
  demo_link          text,
  demo_sent_at       timestamptz,
  demo_fu1_due       date,
  demo_fu1_sent_at   timestamptz,
  demo_fu2_due       date,
  demo_fu2_sent_at   timestamptz,
  outcome_value_kes  integer,
  lost_reason        text,
  closed_at          timestamptz,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now(),
  unique (place_id, list_date)
);
create index if not exists leads_list_date_idx on public.leads (list_date desc, track, rank);
create index if not exists leads_status_idx on public.leads (status);
create index if not exists leads_fu1_idx on public.leads (fu1_due) where fu1_sent_at is null;
create index if not exists leads_fu2_idx on public.leads (fu2_due) where fu2_sent_at is null;

-- ------------------------------------------------------------------ events (audit trail)
create table if not exists public.events (
  id       bigint generated always as identity primary key,
  lead_id  uuid not null references public.leads (id) on delete cascade,
  at       timestamptz not null default now(),
  type     text not null,
  payload  jsonb not null default '{}'
);
create index if not exists events_lead_idx on public.events (lead_id, at);
create index if not exists events_type_idx on public.events (type, at);

-- ------------------------------------------------------------------ suppression
create table if not exists public.suppression (
  phone_e164  text primary key,
  place_id    text,
  reason      text not null check (reason in ('opted_out', 'client', 'manual', 'do_not_contact')),
  note        text,
  added_at    timestamptz not null default now()
);
create index if not exists suppression_place_idx on public.suppression (place_id);

-- ------------------------------------------------------------------ search cells
create table if not exists public.search_cells (
  id                uuid primary key default gen_random_uuid(),
  subcategory       text not null,
  query_template    text not null,
  area              text not null,
  tier              integer not null,
  last_run          timestamptz,
  pages_fetched     integer not null default 0,
  last_new_ratio    numeric(4,3),
  exhausted_streak  integer not null default 0,
  exhausted         boolean not null default false,
  unique (subcategory, query_template, area)
);

-- ------------------------------------------------------------------ api usage
create table if not exists public.api_usage (
  month  text not null,             -- YYYY-MM
  api    text not null,             -- places | psi | gemini
  sku    text not null,
  count  integer not null default 0,
  primary key (month, api, sku)
);

-- ------------------------------------------------------------------ settings
create table if not exists public.settings (
  key         text primary key,
  value       jsonb not null,
  updated_at  timestamptz not null default now(),
  updated_by  text not null default 'pipeline'   -- pipeline | dashboard | seed
);
