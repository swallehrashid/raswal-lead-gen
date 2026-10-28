// Lead state transitions. Each returns the patch to apply plus side effects. The Supabase
// trigger logs every status change to `events`; extra events (reply text, edits) are explicit.
import type { CalendarSettings, Lead, LeadPatch, Track } from '../data/types'
import { addWorkingDays } from './workdays'

export interface Action {
  patch: LeadPatch
  event?: { type: string; payload: Record<string, unknown> }
  promoteReserve?: boolean
  suppress?: { phone_e164: string; place_id: string; reason: string }
}

type Cal = Pick<CalendarSettings, 'send_days' | 'holidays' | 'pauses' | 'pauses_block_followups' | 'followups'>
type Pauses = Array<{ start: string; end: string }>

export const SKIP_REASONS = ['wrong_category', 'too_big', 'too_small', 'looks_closed', 'weak_hook', 'bad_teaser', 'has_agency', 'other'] as const
export const REPLY_TYPES = ['interested', 'question', 'price', 'not_now', 'has_provider', 'stop'] as const
export const LOST_REASONS = ['has_provider', 'price', 'no_budget', 'went_quiet', 'not_a_fit', 'other'] as const

export function approve(lead: Lead, variantIdx: number, message: string, now: string): Action {
  const v = lead.message_variants[variantIdx]
  const edited = v ? v.message !== message : true
  return {
    patch: {
      status: 'approved', approved_at: now, chosen_variant: variantIdx, message_final: message,
      used_fact_ids: v?.used_fact_ids ?? [], variant_source: v?.source ?? lead.variant_source,
    },
    event: edited ? { type: 'edited', payload: { variant: variantIdx } } : undefined,
  }
}

export function unapprove(): Action {
  return { patch: { status: 'shortlisted', approved_at: null } }
}

export function skip(reason: string): Action {
  return { patch: { status: 'skipped', skip_reason: reason }, promoteReserve: true }
}

export function markSent(lead: Lead, now: string, today: string, cal: Cal, extraPauses: Pauses = []): Action {
  return {
    patch: {
      status: 'sent', sent_at: now, message_final: lead.message_final,
      fu1_due: addWorkingDays(cal, today, cal.followups.fu1_working_days, extraPauses),
      fu2_due: addWorkingDays(cal, today, cal.followups.fu2_working_days, extraPauses),
    },
  }
}

export function noWhatsapp(): Action {
  return { patch: { status: 'no_whatsapp' }, promoteReserve: true }
}

export type FollowupKind = 'fu1' | 'fu2' | 'demo_fu1' | 'demo_fu2' | 'snooze'

export function followupSent(lead: Lead, kind: FollowupKind, now: string): Action {
  switch (kind) {
    case 'fu1': return { patch: { fu1_sent_at: now }, event: { type: 'fu1_sent', payload: {} } }
    case 'fu2':
      // After FU2 the lead is never messaged again unless they reply (brief §12.6).
      return { patch: { fu2_sent_at: now, ...(lead.status === 'sent' ? { status: 'no_response' as const } : {}) },
        event: { type: 'fu2_sent', payload: {} } }
    case 'demo_fu1': return { patch: { demo_fu1_sent_at: now }, event: { type: 'demo_fu1_sent', payload: {} } }
    case 'demo_fu2': return { patch: { demo_fu2_sent_at: now }, event: { type: 'demo_fu2_sent', payload: {} } }
    case 'snooze': return { patch: { status: 'replied', snoozed_until: null }, event: { type: 'snooze_checked', payload: {} } }
  }
}

const ADVANCED = new Set(['interested', 'demo_queued', 'demo_sent', 'negotiating', 'won'])

export function logReply(lead: Lead, type: string, text: string, now: string): Action {
  const patch: LeadPatch = { replied_at: lead.replied_at ?? now, reply_type: type }
  if (!ADVANCED.has(lead.status)) patch.status = 'replied'
  return { patch, event: { type: 'reply', payload: { reply_type: type, text: text || undefined } } }
}

export function markInterested(lead: Lead, demoType: Track, now: string): Action {
  return {
    patch: { status: 'demo_queued', demo_type: demoType, demo_queued_at: now, replied_at: lead.replied_at ?? now },
    event: { type: 'interested', payload: { demo_type: demoType } },
  }
}

export function snooze(until: string): Action {
  return { patch: { status: 'snoozed', snoozed_until: until } }
}

export function markLost(reason: string, now: string): Action {
  return { patch: { status: 'lost', lost_reason: reason, closed_at: now } }
}

export function optOut(lead: Lead, now: string): Action {
  return {
    patch: { status: 'opted_out', closed_at: now },
    suppress: lead.business.phone_e164 ? { phone_e164: lead.business.phone_e164, place_id: lead.place_id, reason: 'opted_out' } : undefined,
  }
}

export function setDemoLink(link: string): Action {
  return { patch: { demo_link: link.trim() }, event: { type: 'demo_link', payload: { link: link.trim() } } }
}

export function demoSent(now: string, today: string, cal: Cal, extraPauses: Pauses = []): Action {
  const [d1, d2] = cal.followups.demo_fu_working_days
  return {
    patch: {
      status: 'demo_sent', demo_sent_at: now,
      demo_fu1_due: addWorkingDays(cal, today, d1, extraPauses), demo_fu2_due: addWorkingDays(cal, today, d2, extraPauses),
    },
  }
}

/** Start the pilot: the client said yes to the plan and we are collecting the offer form, access and the KES budget. */
export function startPilot(now: string): Action {
  return { patch: { status: 'pilot_onboarding' }, event: { type: 'pilot_started', payload: { at: now } } }
}

export function pilotLive(): Action {
  return { patch: { status: 'pilot_live' }, event: { type: 'pilot_live', payload: {} } }
}

export function pilotReview(): Action {
  return { patch: { status: 'pilot_review' }, event: { type: 'pilot_day7', payload: {} } }
}

export function negotiating(): Action {
  return { patch: { status: 'negotiating' } }
}

export function won(value: number | null, now: string): Action {
  return { patch: { status: 'won', outcome_value_kes: value, closed_at: now } }
}

export function setNotes(notes: string): Action {
  return { patch: { notes } }
}

export function setAdsOverride(lead: Lead, v: 'active' | 'none' | 'unknown'): Action {
  return { patch: { brand: { ...lead.brand, ads_override: v } } }
}

export function setSocialState(state: Lead['social_state']): Action {
  return { patch: { social_state: state } }
}
