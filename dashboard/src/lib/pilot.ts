// Pilot helpers: stage, cost per chat, and the WhatsApp texts (daily update, day-7 report). Pure functions.
import type { Pilot, PilotConfig, PilotDay } from '../data/types'

export type PilotStage = 'Onboarding' | 'Offer in' | 'Access granted' | 'Paid' | 'Submitted' | 'Live' | 'Day 7' | 'Converted' | 'Declined'

export function stageOf(p: Pilot, hasOffer: boolean): PilotStage {
  if (p.outcome === 'converted') return 'Converted'
  if (p.outcome === 'declined') return 'Declined'
  if (p.live_at && p.ends_at && p.ends_at <= new Date().toISOString()) return 'Day 7'
  if (p.live_at) return 'Live'
  if (p.submitted_at) return 'Submitted'
  if (p.paid_at) return 'Paid'
  if (p.access_granted_at) return 'Access granted'
  return hasOffer ? 'Offer in' : 'Onboarding'
}

export const num = (n: number | null | undefined) => n ?? 0
export const fmt = (n: number) => Math.round(n).toLocaleString('en-US')

export function totals(days: PilotDay[]) {
  const t = { spend: 0, reach: 0, chats: 0, serious: 0, visits: 0 }
  for (const d of days) { t.spend += num(d.spend_kes); t.reach += num(d.reach); t.chats += num(d.chats); t.serious += num(d.serious); t.visits += num(d.visits) }
  return t
}

/** KES per WhatsApp chat (null until there is a chat). */
export function costPerChat(spend: number, chats: number): number | null {
  return chats > 0 ? Math.round(spend / chats) : null
}

/** The stop rule: after `after_hours` (48 h = from day 3) a chat costing more than the limit means change the creative or audience today. */
export function overStopRule(days: PilotDay[], cfg: Pick<PilotConfig, 'stop_rule'>): boolean {
  const t = totals(days)
  const cpc = costPerChat(t.spend, t.chats)
  const day = Math.max(0, ...days.map((d) => d.day))
  return cpc !== null && day >= Math.ceil(cfg.stop_rule.after_hours / 24) + 1 && cpc > cfg.stop_rule.max_cost_per_chat_kes
}

export function dailyUpdate(name: string, days: PilotDay[], today: PilotDay, noun: string, winner: string | null, next: string): string {
  const t = totals(days)
  const cpc = costPerChat(t.spend, t.chats)
  return `Habari ${name} 👋 Day ${today.day} update: KES ${fmt(t.spend)} spent so far · ${num(today.chats)} new WhatsApp chats today (${t.chats} total) · ` +
    `${cpc ? `about KES ${fmt(cpc)} per chat` : 'cost per chat after the first chat'} · ${t.visits} ${noun}s booked. ` +
    `${winner ? `Best ad so far: "${winner}". ` : ''}${next}. Asante! — Swalleh`
}

export function dayReport(name: string, days: PilotDay[], noun: string, winner: string | null, cfg: Pick<PilotConfig, 'pricing'>): string {
  const t = totals(days)
  const cpc = costPerChat(t.spend, t.chats)
  return `Habari ${name} 🙏 Your 7-day pilot is done:\n• KES ${fmt(t.spend)} → ${t.chats} WhatsApp chats${cpc ? ` (about KES ${fmt(cpc)} each)` : ''}\n` +
    `• ${t.serious} serious buyers · ${t.visits} ${noun}s booked\n${winner ? `• Winning ad: "${winner}"\n` : ''}` +
    `If the ads stop, next week's enquiries stop. Shall we keep them running on the Enquiry Engine (KES ${fmt(cfg.pricing.engine_intro_kes)}/month, introductory), with fresh ads every week?`
}
