export type LeadStatus =
  | 'shortlisted' | 'reserve' | 'approved' | 'skipped'
  | 'sent' | 'no_whatsapp' | 'replied' | 'interested'
  | 'demo_queued' | 'demo_sent' | 'negotiating'
  | 'won' | 'lost' | 'no_response' | 'snoozed' | 'opted_out'
  | 'pilot_onboarding' | 'pilot_live' | 'pilot_review'

export type Track = 'web' | 'content' | 'ads'
export type SiteStatus = 'none' | 'social_as_site' | 'dead' | 'insecure' | 'free_builder' | 'weak' | 'good'
export type SocialState = 'none' | 'stale' | 'active' | 'polished'

export interface Fact {
  id: string
  code: string
  strength: 'strong' | 'medium'
  text: string
  evidence: Record<string, unknown>
  track: 'web' | 'content' | 'any' | 'upsell'
  source: string
}

export interface Variant {
  message: string
  used_fact_ids: string[]
  source: 'llm' | 'fallback'
  swahili_touch: boolean
}

export interface Audit {
  site_status: SiteStatus
  website_url: string | null
  final_url: string | null
  https_ok: boolean | null
  platform: string | null
  copyright_year: number | null
  psi_perf: number | null
  psi_lcp_s: number | null
  current_screenshot_path: string | null
  social_links: Record<string, string>
  colours: Record<string, string>
  logo_url: string | null
  hero_image_url: string | null
  dead_marker: string | null
  weak_signals?: string[]
}

export interface Business {
  place_id: string
  name: string
  display_name: string | null
  area: string | null
  address: string | null
  phone_e164: string | null
  website_url: string | null
  maps_url: string | null
  rating: number | null
  review_count: number
  branch_count: number
  manages_listings: number
  audit: Audit | null
  ads_status?: 'active' | 'none' | 'unknown' | null
  ads_active_count?: number | null
  ads_longest_days?: number | null
  social?: Record<string, unknown> | null
  scam_flag?: 'hard' | 'soft' | null
  scam_terms?: string[] | null
}

export interface Evaluation {
  score: number | null
  breakdown: Record<string, number>
  facts: { facts: Fact[]; review_facts: Array<Record<string, unknown>> } | null
}

export interface Brand {
  logo_path?: string | null
  hero_path?: string | null
  primary?: string
  accent?: string
  /** Set by `pipeline generate` (Phase 5) once the demo is built + deployed. */
  demo_message?: string
  demo_kind?: 'web' | 'content' | 'pilot'
  angle?: 'A' | 'B' | 'C'
  ads_override?: 'active' | 'none' | 'unknown'
  offer?: Record<string, unknown>
  listings?: Array<Record<string, unknown>>
  demo_generated_at?: string
}

export interface Lead {
  id: string
  place_id: string
  list_date: string
  subcategory: string
  track: Track
  rank: number
  status: LeadStatus
  site_status: SiteStatus | null
  area: string | null
  top_fact_code: string | null
  message_variants: Variant[]
  message_final: string | null
  chosen_variant: number | null
  used_fact_ids: string[]
  variant_source: string | null
  poster_lines: string[]
  teaser_path: string | null
  slug: string | null
  social_state: SocialState | null
  brand: Brand
  skip_reason: string | null
  notes: string | null
  approved_at: string | null
  sent_at: string | null
  fu1_due: string | null
  fu1_sent_at: string | null
  fu2_due: string | null
  fu2_sent_at: string | null
  replied_at: string | null
  reply_type: string | null
  snoozed_until: string | null
  demo_type: Track | null
  demo_queued_at: string | null
  demo_link: string | null
  demo_sent_at: string | null
  demo_fu1_due: string | null
  demo_fu1_sent_at: string | null
  demo_fu2_due: string | null
  demo_fu2_sent_at: string | null
  outcome_value_kes: number | null
  lost_reason: string | null
  closed_at: string | null
  created_at: string
  updated_at: string
  business: Business
  evaluation: Evaluation | null
}

export type LeadPatch = Partial<Omit<Lead, 'id' | 'business' | 'evaluation'>>

export interface EventRow {
  id: number | string
  lead_id: string
  at: string
  type: string
  payload: Record<string, unknown>
}

export interface Run {
  id: string
  list_date: string
  subcategory: string | null
  started_at: string
  finished_at: string | null
  status: 'running' | 'ok' | 'failed' | 'skipped'
  dry_run: boolean
  skipped_reason: string | null
  places_calls: number
  psi_calls: number
  gemini_calls: number
  raw_candidates: number
  passed_gates: number
  enriched: number
  qualified_web: number
  qualified_content: number
  shipped_web: number
  shipped_content: number
  gate_counts: Record<string, number>
  errors: Array<{ stage: string; error: string; place_id?: string | null }>
}

export interface QuickReply { key: string; label: string; text: string; action?: string | null }

export interface CalendarSettings {
  timezone: string
  send_days: string[]
  holidays: Array<{ date: string; name: string }>
  pauses: Array<{ start: string; end: string; name: string }>
  pauses_block_followups: boolean
  followups: { fu1_working_days: number; fu2_working_days: number; demo_fu_working_days: number[] }
  pacing: { max_per_hour: number; batch_windows: Array<{ start: string; end: string }> }
  same_day_demo_cutoff: string
}

export interface Settings {
  calendar: CalendarSettings
  subcategories: Record<string, { label: string; active: boolean; template: string }>
  scoring: { ads_min_score: number }
  pilot?: PilotConfig
  messaging: { signoff: string; length: { min: number; max: number } }
  budget: { places_calls_per_month: number; places_calls_per_night: number; psi_calls_per_night: number; gemini_calls_per_night: number; db_cap_mb: number; storage_cap_mb: number }
  quick_replies: QuickReply[]
  followup_templates: Record<string, string>
  demo_cap: Record<string, number>
  daily_mix: Record<string, number>
  outreach_whatsapp: string
  pause_list: Array<{ start: string; end: string; note?: string }>
}

export interface ApiUsageRow { month: string; api: string; sku: string; count: number }
export interface CellSummary { subcategory: string; tier1_active: number; tier1_total: number }
export interface UsageStats { db_bytes: number; storage_bytes: number; storage_files: number }
export interface Suppression { phone_e164: string; place_id: string | null; reason: string; note: string | null; added_at: string }

export interface PilotConfig {
  pilot_days: number
  budget_kes: number
  vat_note: string
  stop_rule: { max_cost_per_chat_kes: number; after_hours: number }
  reply_rule: string
  estimates: Record<string, unknown>
  pricing: { engine_intro_kes: number; engine_standard_kes: number; website_setup_kes: number; website_monthly_kes: number; december_pack_kes: number }
}

export type PilotRoute = 'A' | 'B' | 'C' | 'backup'

export interface Pilot {
  id: string
  lead_id: string
  route: PilotRoute | null
  offer: Record<string, unknown> | null
  budget_kes: number
  mpesa_ref: string | null
  paid_at: string | null
  access_granted_at: string | null
  submitted_at: string | null
  live_at: string | null
  ends_at: string | null
  targets: { chats?: number; visits?: number } | null
  winner_ad: string | null
  outcome: 'converted' | 'declined' | 'extended' | null
  plan_price_kes: number | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface PilotDay {
  pilot_id: string
  day: number
  date: string | null
  spend_kes: number | null
  reach: number | null
  chats: number | null
  serious: number | null
  visits: number | null
  ad_breakdown: Record<string, unknown> | null
  note: string | null
}
