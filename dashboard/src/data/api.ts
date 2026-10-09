import type { Action } from '../lib/actions'
import type {
  ApiUsageRow, CellSummary, EventRow, Lead, LeadStatus, Run, Settings, Suppression, Track, UsageStats,
} from './types'

export interface LeadFilter {
  statuses?: LeadStatus[]
  subcategory?: string
  track?: Track
  from?: string
  to?: string
  sentOnly?: boolean
  limit?: number
}

export interface SessionInfo { email: string }

export interface Api {
  mode: 'mock' | 'live'
  today(): string
  now(): string
  session(): Promise<SessionInfo | null>
  onAuthChange(cb: (s: SessionInfo | null) => void): () => void
  signIn(email: string): Promise<void>
  signOut(): Promise<void>
  isAdmin(): Promise<boolean>

  settings(): Promise<Settings>
  runs(limit?: number): Promise<Run[]>
  latestListDate(): Promise<string | null>
  leadsForList(listDate: string): Promise<Lead[]>
  leads(filter: LeadFilter): Promise<Lead[]>
  lead(id: string): Promise<Lead | null>
  events(leadIds?: string[]): Promise<EventRow[]>
  apiUsage(month: string): Promise<ApiUsageRow[]>
  cellSummary(): Promise<CellSummary[]>
  usageStats(): Promise<UsageStats | null>
  suppression(): Promise<Suppression[]>
  fileUrl(path: string | null | undefined): Promise<string | null>

  apply(lead: Lead, action: Action): Promise<{ promoted: string | null }>
  addSuppression(row: { phone_e164: string; place_id?: string | null; reason: string; note?: string | null }): Promise<void>
  removeSuppression(phone: string): Promise<void>
  saveSetting(key: string, value: unknown): Promise<void>
  resetMock?(): void
}

export const LIVE = Boolean(import.meta.env.VITE_SUPABASE_URL)

let instance: Promise<Api> | null = null

/** Real Supabase when VITE_SUPABASE_URL is set, otherwise the fixture-backed mock. */
export function getApi(): Promise<Api> {
  if (!instance) {
    instance = LIVE
      ? import('./supabaseApi').then((m) => m.createSupabaseApi())
      : import('./mockApi').then((m) => m.createMockApi())
  }
  return instance
}

export const CONTACTED: LeadStatus[] = [
  'sent', 'replied', 'interested', 'demo_queued', 'demo_sent', 'negotiating', 'won', 'lost', 'no_response', 'snoozed', 'opted_out',
]
