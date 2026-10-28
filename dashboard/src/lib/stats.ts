import type { EventRow, Lead } from '../data/types'
import { hourIn } from './workdays'

export const STAGES = ['sent', 'replied', 'interested', 'demo', 'pilot', 'won'] as const
export type Stage = (typeof STAGES)[number]

/** Stages each lead reached, derived from the events log (the audit trail). */
export function stagesFromEvents(events: EventRow[]): Map<string, Set<Stage>> {
  const m = new Map<string, Set<Stage>>()
  const add = (id: string, s: Stage) => {
    if (!m.has(id)) m.set(id, new Set())
    m.get(id)!.add(s)
  }
  for (const e of events) {
    const to = e.type === 'status' ? String(e.payload.to ?? '') : ''
    if (to === 'sent') add(e.lead_id, 'sent')
    if (e.type === 'reply' || ['replied', 'demo_queued', 'snoozed'].includes(to)) add(e.lead_id, 'replied')
    if (e.type === 'interested' || to === 'demo_queued') add(e.lead_id, 'interested')
    if (to === 'demo_sent') add(e.lead_id, 'demo')
    if (['pilot_onboarding', 'pilot_live', 'pilot_review'].includes(to)) add(e.lead_id, 'pilot')
    if (to === 'won') add(e.lead_id, 'won')
  }
  return m
}

/** Same stages from lead timestamps (used to check the events log is complete). */
export function stagesFromLead(l: Lead): Set<Stage> {
  const s = new Set<Stage>()
  if (l.sent_at) s.add('sent')
  if (l.replied_at) s.add('replied')
  if (l.demo_queued_at) s.add('interested')
  if (l.demo_sent_at) s.add('demo')
  if (['pilot_onboarding', 'pilot_live', 'pilot_review'].includes(l.status)) s.add('pilot')
  if (l.status === 'won') s.add('won')
  return s
}

export type Funnel = Record<Stage, number>

export function funnel(leadIds: string[], stages: Map<string, Set<Stage>>): Funnel {
  const f = { sent: 0, replied: 0, interested: 0, demo: 0, pilot: 0, won: 0 }
  for (const id of leadIds) for (const s of stages.get(id) ?? []) f[s] += 1
  return f
}

export const DIMENSIONS: Record<string, { label: string; key: (l: Lead, tz: string) => string }> = {
  subcategory: { label: 'Subcategory', key: (l) => l.subcategory },
  angle: { label: 'Angle', key: (l) => l.brand?.angle ?? '—' },
  track: { label: 'Track', key: (l) => l.track },
  site_status: { label: 'Site status', key: (l) => l.site_status ?? 'none' },
  top_fact: { label: 'Top fact', key: (l) => l.top_fact_code ?? '—' },
  variant_source: { label: 'Message source', key: (l) => l.variant_source ?? '—' },
  swahili: {
    label: 'Swahili touch',
    key: (l) => (l.message_variants[l.chosen_variant ?? 0]?.swahili_touch ? 'yes' : 'no'),
  },
  send_hour: {
    label: 'Send hour',
    key: (l, tz) => (l.sent_at ? `${String(hourIn(tz, l.sent_at)).padStart(2, '0')}:00` : '—'),
  },
}

export function breakdown(leads: Lead[], stages: Map<string, Set<Stage>>, dim: keyof typeof DIMENSIONS, tz: string) {
  const groups = new Map<string, string[]>()
  for (const l of leads) {
    if (!l.sent_at) continue
    const k = DIMENSIONS[dim].key(l, tz)
    groups.set(k, [...(groups.get(k) ?? []), l.id])
  }
  return [...groups.entries()]
    .map(([key, ids]) => ({ key, ...funnel(ids, stages) }))
    .sort((a, b) => b.sent - a.sent || a.key.localeCompare(b.key))
}

export const pct = (n: number, d: number) => (d ? `${Math.round((n / d) * 100)}%` : '—')
