import { describe, expect, it } from 'vitest'
import type { Pilot, PilotDay } from '../data/types'
import { costPerChat, dailyUpdate, dayReport, overStopRule, stageOf, totals } from './pilot'

const day = (n: number, spend: number, chats: number, extra: Partial<PilotDay> = {}): PilotDay => ({
  pilot_id: 'p', day: n, date: null, spend_kes: spend, reach: 1000, chats, serious: 1, visits: 0, ad_breakdown: null, note: null, ...extra })
const cfg = { stop_rule: { max_cost_per_chat_kes: 250, after_hours: 48 }, pricing: { engine_intro_kes: 10000, engine_standard_kes: 15000, website_setup_kes: 5000, website_monthly_kes: 4000, december_pack_kes: 12000 } }
const base = { id: 'p', lead_id: 'l', route: null, offer: null, budget_kes: 5000, mpesa_ref: null, paid_at: null, access_granted_at: null, submitted_at: null,
  live_at: null, ends_at: null, targets: null, winner_ad: null, outcome: null, plan_price_kes: null, notes: null, created_at: '', updated_at: '' } as Pilot

describe('pilot helpers', () => {
  it('totals and cost per chat', () => {
    const t = totals([day(1, 700, 6), day(2, 700, 8)])
    expect(t).toMatchObject({ spend: 1400, chats: 14 })
    expect(costPerChat(1400, 14)).toBe(100)
    expect(costPerChat(500, 0)).toBeNull()
  })
  it('stop rule only bites after 48 hours and only over the limit', () => {
    expect(overStopRule([day(1, 1000, 2), day(2, 1000, 2)], cfg)).toBe(false)           // too early
    expect(overStopRule([day(1, 800, 4), day(2, 800, 4), day(3, 800, 4)], cfg)).toBe(false) // 200 per chat
    expect(overStopRule([day(1, 1000, 3), day(2, 1000, 3), day(3, 1000, 3)], cfg)).toBe(true) // 333 per chat
  })
  it('stage follows the timestamps', () => {
    expect(stageOf(base, false)).toBe('Onboarding')
    expect(stageOf(base, true)).toBe('Offer in')
    expect(stageOf({ ...base, access_granted_at: 'x' }, true)).toBe('Access granted')
    expect(stageOf({ ...base, access_granted_at: 'x', paid_at: 'x' }, true)).toBe('Paid')
    expect(stageOf({ ...base, submitted_at: 'x' }, true)).toBe('Submitted')
    expect(stageOf({ ...base, live_at: 'x', ends_at: '2999-01-01T00:00:00Z' }, true)).toBe('Live')
    expect(stageOf({ ...base, outcome: 'converted' }, true)).toBe('Converted')
  })
  it('daily update and day-7 report read like the copy bank', () => {
    const days = [day(1, 700, 6), day(2, 700, 8, { visits: 2 })]
    const u = dailyUpdate('Ardhi Bora', days, days[1], 'site visit', 'The Offer', 'Tomorrow we put more budget behind it')
    expect(u).toContain('Day 2 update: KES 1,400 spent so far · 8 new WhatsApp chats today (14 total)')
    expect(u).toContain('about KES 100 per chat') ; expect(u).toContain('2 site visits booked'); expect(u).toContain('"The Offer"')
    const r = dayReport('Ardhi Bora', days, 'site visit', 'The Offer', cfg)
    expect(r).toContain('KES 1,400 → 14 WhatsApp chats (about KES 100 each)')
    expect(r).toContain("If the ads stop, next week's enquiries stop.")
    expect(r).toContain('KES 10,000/month, introductory')
  })
})
