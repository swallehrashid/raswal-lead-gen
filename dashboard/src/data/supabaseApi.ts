import { createClient, type SupabaseClient } from '@supabase/supabase-js'
import type { Action } from '../lib/actions'
import { todayIn } from '../lib/workdays'
import type { Api, LeadFilter } from './api'
import type { Lead, Pilot, PilotDay, Settings } from './types'

const LEAD_SELECT =
  '*, business:businesses(*, audit:audits(*)), evaluation:evaluations(score, breakdown, facts(facts, review_facts))'
const BUCKET = 'leadgen'

export function createSupabaseApi(): Api {
  const sb: SupabaseClient = createClient(import.meta.env.VITE_SUPABASE_URL as string, import.meta.env.VITE_SUPABASE_ANON_KEY as string, {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
  })
  let tz = 'Africa/Nairobi'
  const urlCache = new Map<string, { url: string; exp: number }>()
  const must = <T>(r: { data: T | null; error: { message: string } | null }): T => {
    if (r.error) throw new Error(r.error.message)
    return r.data as T
  }

  const api: Api = {
    mode: 'live',
    today: () => todayIn(tz),
    now: () => new Date().toISOString(),

    async session() {
      const { data } = await sb.auth.getSession()
      return data.session?.user.email ? { email: data.session.user.email } : null
    },
    onAuthChange(cb) {
      const { data } = sb.auth.onAuthStateChange((_e, s) => cb(s?.user.email ? { email: s.user.email } : null))
      return () => data.subscription.unsubscribe()
    },
    async signIn(email, password) {
      const { error } = await sb.auth.signInWithPassword({ email, password })
      if (error) throw new Error(error.message)
    },
    async signOut() {
      await sb.auth.signOut()
    },
    async isAdmin() {
      const { data, error } = await sb.rpc('is_admin')
      return !error && data === true
    },

    async settings() {
      const rows = must(await sb.from('settings').select('key, value'))
      const s = Object.fromEntries((rows as Array<{ key: string; value: unknown }>).map((r) => [r.key, r.value])) as unknown as Settings
      if (s.calendar?.timezone) tz = s.calendar.timezone
      return s
    },
    async runs(limit = 30) {
      return must(await sb.from('runs').select('*').order('started_at', { ascending: false }).limit(limit))
    },
    async latestListDate() {
      const rows = must(await sb.from('leads').select('list_date').order('list_date', { ascending: false }).limit(1))
      return (rows as Array<{ list_date: string }>)[0]?.list_date ?? null
    },
    async leadsForList(listDate) {
      return must(await sb.from('leads').select(LEAD_SELECT).eq('list_date', listDate).order('track').order('rank')) as Lead[]
    },
    async leads(f: LeadFilter) {
      let q = sb.from('leads').select(LEAD_SELECT)
      if (f.statuses?.length) q = q.in('status', f.statuses)
      if (f.subcategory) q = q.eq('subcategory', f.subcategory)
      if (f.track) q = q.eq('track', f.track)
      if (f.from) q = q.gte('list_date', f.from)
      if (f.to) q = q.lte('list_date', f.to)
      if (f.sentOnly) q = q.not('sent_at', 'is', null)
      return must(await q.order('updated_at', { ascending: false }).limit(f.limit ?? 1000)) as Lead[]
    },
    async lead(id) {
      const rows = must(await sb.from('leads').select(LEAD_SELECT).eq('id', id).limit(1)) as Lead[]
      return rows[0] ?? null
    },
    async events(leadIds) {
      let q = sb.from('events').select('*').order('at', { ascending: true }).limit(10000)
      if (leadIds?.length) q = q.in('lead_id', leadIds.slice(0, 500))
      return must(await q)
    },
    async apiUsage(month) {
      return must(await sb.from('api_usage').select('*').eq('month', month))
    },
    async cellSummary() {
      const rows = must(await sb.from('search_cells').select('subcategory, tier, exhausted').eq('tier', 1)) as Array<{
        subcategory: string; exhausted: boolean }>
      const m = new Map<string, { subcategory: string; tier1_active: number; tier1_total: number }>()
      for (const r of rows) {
        const e = m.get(r.subcategory) ?? { subcategory: r.subcategory, tier1_active: 0, tier1_total: 0 }
        e.tier1_total += 1
        if (!r.exhausted) e.tier1_active += 1
        m.set(r.subcategory, e)
      }
      return [...m.values()]
    },
    async usageStats() {
      const { data, error } = await sb.rpc('usage_stats')
      return error ? null : data
    },
    async suppression() {
      return must(await sb.from('suppression').select('*').order('added_at', { ascending: false }))
    },
    async fileUrl(path) {
      if (!path) return null
      const hit = urlCache.get(path)
      if (hit && hit.exp > Date.now()) return hit.url
      const { data, error } = await sb.storage.from(BUCKET).createSignedUrl(path, 3600)
      if (error || !data) return null
      urlCache.set(path, { url: data.signedUrl, exp: Date.now() + 50 * 60 * 1000 })
      return data.signedUrl
    },

    async pilots() {
      return must(await sb.from('pilots').select('*').order('created_at', { ascending: false })) as Pilot[]
    },
    async pilotDays(pilotId) {
      return must(await sb.from('pilot_days').select('*').eq('pilot_id', pilotId).order('day')) as PilotDay[]
    },
    async savePilot(p) {
      const row = { ...p, updated_at: new Date().toISOString() }
      const r = p.id ? await sb.from('pilots').update(row).eq('id', p.id).select('*') : await sb.from('pilots').insert(row).select('*')
      return (must(r) as Pilot[])[0]
    },
    async savePilotDay(d) {
      must(await sb.from('pilot_days').upsert(d, { onConflict: 'pilot_id,day' }).select('pilot_id'))
    },

    async apply(lead: Lead, a: Action) {
      if (Object.keys(a.patch).length) must(await sb.from('leads').update(a.patch).eq('id', lead.id).select('id'))
      if (a.event) must(await sb.from('events').insert({ lead_id: lead.id, type: a.event.type, payload: a.event.payload }).select('id'))
      if (a.suppress)
        must(await sb.from('suppression').upsert({ ...a.suppress, added_at: new Date().toISOString() }).select('phone_e164'))
      let promoted: string | null = null
      if (a.promoteReserve) {
        const { data } = await sb.rpc('promote_reserve', { p_lead_id: lead.id })
        promoted = (data as string | null) ?? null
      }
      return { promoted }
    },
    async addSuppression(row) {
      must(await sb.from('suppression').upsert({ ...row, added_at: new Date().toISOString() }).select('phone_e164'))
    },
    async removeSuppression(phone) {
      must(await sb.from('suppression').delete().eq('phone_e164', phone).select('phone_e164'))
    },
    async saveSetting(key, value) {
      must(await sb.from('settings').upsert({ key, value, updated_by: 'dashboard', updated_at: new Date().toISOString() }).select('key'))
    },
  }
  return api
}
