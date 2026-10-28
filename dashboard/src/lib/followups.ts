import type { Lead, Settings } from '../data/types'
import type { FollowupKind } from './actions'
import { weekdayName } from './workdays'

export interface Due { lead: Lead; kind: FollowupKind; due: string; message: string; overdue: boolean }

export function fill(tpl: string, lead: Lead): string {
  const name = lead.business.display_name || lead.business.name
  return tpl
    .replaceAll('{business}', name)
    .replaceAll('{weekday}', lead.sent_at ? weekdayName(lead.sent_at.slice(0, 10)) : 'Monday')
}

export function dueFollowups(leads: Lead[], today: string, settings: Settings): Due[] {
  const t = settings.followup_templates
  const out: Due[] = []
  const add = (lead: Lead, kind: FollowupKind, due: string | null, tpl: string) => {
    if (due && due <= today) out.push({ lead, kind, due, message: fill(tpl, lead), overdue: due < today })
  }
  for (const l of leads) {
    if (l.status === 'sent') {
      if (!l.fu1_sent_at) add(l, 'fu1', l.fu1_due, t.fu1)
      if (!l.fu2_sent_at && (l.fu1_sent_at || (l.fu2_due ?? '') <= today))
        add(l, 'fu2', l.fu2_due, t.fu2)
    }
    if (l.status === 'demo_sent') {
      if (!l.demo_fu1_sent_at) add(l, 'demo_fu1', l.demo_fu1_due, t.demo_fu1)
      else if (!l.demo_fu2_sent_at) add(l, 'demo_fu2', l.demo_fu2_due, t.demo_fu2)
    }
    if (l.status === 'snoozed') add(l, 'snooze', l.snoozed_until, 'Hi {business} team, checking back as promised. Is now a better time to look at the preview? — Swalleh')
  }
  const order: Record<FollowupKind, number> = { fu1: 0, fu2: 1, demo_fu1: 2, demo_fu2: 3, snooze: 4 }
  return out.sort((a, b) => a.due.localeCompare(b.due) || order[a.kind] - order[b.kind])
}
