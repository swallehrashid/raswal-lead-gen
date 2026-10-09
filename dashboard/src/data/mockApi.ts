// Mock data layer: the dataset produced by `python -m pipeline export-mock` from the same
// fixtures the pipeline tests use. Changes are kept in localStorage so you can click through
// Review → Send → Follow-ups → Demo queue → Stats. Settings → "Reset mock data" starts over.
import type { Action } from '../lib/actions'
import type { Api, LeadFilter } from './api'
import type { ApiUsageRow, CellSummary, EventRow, Lead, Run, Settings, Suppression, UsageStats } from './types'

interface Dataset {
  generated_at: string
  today: string
  settings: Settings
  runs: Run[]
  leads: Lead[]
  events: EventRow[]
  api_usage: ApiUsageRow[]
  cells: CellSummary[]
  suppression: Suppression[]
  usage_stats: UsageStats
  files: Record<string, string>
}

const KEY = 'raswal-mock-state'

export async function createMockApi(): Promise<Api> {
  const res = await fetch('/mock/dataset.json')
  if (!res.ok) throw new Error('Mock data missing: run `npm run mock` (or `python -m pipeline export-mock`) first.')
  const base = (await res.json()) as Dataset
  let state: Dataset = base
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) ?? 'null') as Dataset | null
    if (saved && saved.generated_at === base.generated_at) state = saved
  } catch {
    /* private mode or corrupt: start fresh */
  }
  const save = () => {
    try {
      localStorage.setItem(KEY, JSON.stringify(state))
    } catch {
      /* storage full or blocked: keep working in memory */
    }
  }
  let eventId = Math.max(0, ...state.events.map((e) => Number(e.id) || 0)) + 1
  const clone = <T>(x: T): T => structuredClone(x)
  const addEvent = (lead_id: string, type: string, payload: Record<string, unknown>, at: string) =>
    state.events.push({ id: eventId++, lead_id, type, payload, at })
  const nowIso = () => `${state.today}T${new Date().toISOString().slice(11)}`

  const api: Api = {
    mode: 'mock',
    today: () => state.today,
    now: nowIso,
    async session() {
      return { email: 'mock@raswal.local' }
    },
    onAuthChange: () => () => undefined,
    async signIn() {},
    async signOut() {},
    async isAdmin() {
      return true
    },

    async settings() {
      return clone(state.settings)
    },
    async runs(limit = 30) {
      return clone([...state.runs].sort((a, b) => b.started_at.localeCompare(a.started_at)).slice(0, limit))
    },
    async latestListDate() {
      return state.leads.reduce<string | null>((m, l) => (!m || l.list_date > m ? l.list_date : m), null)
    },
    async leadsForList(d) {
      return clone(state.leads.filter((l) => l.list_date === d).sort((a, b) => a.track.localeCompare(b.track) || a.rank - b.rank))
    },
    async leads(f: LeadFilter) {
      return clone(
        state.leads
          .filter((l) => !f.statuses?.length || f.statuses.includes(l.status))
          .filter((l) => !f.subcategory || l.subcategory === f.subcategory)
          .filter((l) => !f.track || l.track === f.track)
          .filter((l) => !f.from || l.list_date >= f.from)
          .filter((l) => !f.to || l.list_date <= f.to)
          .filter((l) => !f.sentOnly || l.sent_at)
          .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
          .slice(0, f.limit ?? 1000),
      )
    },
    async lead(id) {
      return clone(state.leads.find((l) => l.id === id) ?? null)
    },
    async events(ids) {
      return clone(ids?.length ? state.events.filter((e) => ids.includes(e.lead_id)) : state.events)
    },
    async apiUsage(month) {
      return clone(state.api_usage.filter((r) => r.month === month))
    },
    async cellSummary() {
      return clone(state.cells)
    },
    async usageStats() {
      return clone(state.usage_stats)
    },
    async suppression() {
      return clone(state.suppression)
    },
    async fileUrl(path) {
      return path ? (state.files[path] ?? null) : null
    },

    async apply(lead: Lead, a: Action) {
      const at = nowIso()
      const row = state.leads.find((l) => l.id === lead.id)
      if (!row) throw new Error('lead not found')
      const before = row.status
      Object.assign(row, a.patch, { updated_at: at })
      if (a.patch.status && a.patch.status !== before) addEvent(row.id, 'status', { from: before, to: a.patch.status }, at)
      if (a.event) addEvent(row.id, a.event.type, a.event.payload, at)
      if (a.suppress && !state.suppression.some((s) => s.phone_e164 === a.suppress!.phone_e164))
        state.suppression.unshift({ ...a.suppress, note: null, added_at: at })
      let promoted: string | null = null
      if (a.promoteReserve) {
        const reserve = state.leads
          .filter((l) => l.list_date === row.list_date && l.track === row.track && l.status === 'reserve')
          .sort((x, y) => x.rank - y.rank)[0]
        if (reserve) {
          reserve.status = 'shortlisted'
          reserve.updated_at = at
          addEvent(reserve.id, 'status', { from: 'reserve', to: 'shortlisted' }, at)
          addEvent(reserve.id, 'promoted', { replaces: row.id }, at)
          promoted = reserve.id
        }
      }
      save()
      return { promoted }
    },
    async addSuppression(r) {
      state.suppression = [{ phone_e164: r.phone_e164, place_id: r.place_id ?? null, reason: r.reason, note: r.note ?? null,
        added_at: nowIso() }, ...state.suppression.filter((s) => s.phone_e164 !== r.phone_e164)]
      save()
    },
    async removeSuppression(phone) {
      state.suppression = state.suppression.filter((s) => s.phone_e164 !== phone)
      save()
    },
    async saveSetting(key, value) {
      ;(state.settings as unknown as Record<string, unknown>)[key] = value
      save()
    },
    resetMock() {
      try {
        localStorage.removeItem(KEY)
      } catch {
        /* ignore */
      }
      state = clone(base)
    },
  }
  return api
}
