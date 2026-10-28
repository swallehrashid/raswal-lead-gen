import { describe, expect, it } from 'vitest'
import type { EventRow, Lead } from '../data/types'
import { demoSent, followupSent, logReply, markInterested, markSent, optOut, skip } from './actions'
import { dueFollowups } from './followups'
import { buildLeadPack } from './leadpack'
import { normalizeKe } from './phone'
import { funnel, stagesFromEvents, stagesFromLead } from './stats'

const cal = {
  send_days: ['mon', 'tue', 'wed', 'thu', 'fri'],
  holidays: [{ date: '2026-10-20', name: 'Mashujaa Day' }, { date: '2026-12-25', name: 'Christmas' }],
  pauses: [{ start: '2026-12-21', end: '2027-01-01', name: 'December break' }],
  pauses_block_followups: true,
  followups: { fu1_working_days: 3, fu2_working_days: 8, demo_fu_working_days: [1, 4] },
}

function lead(over: Partial<Lead> = {}): Lead {
  return {
    id: 'L1', place_id: 'P1', list_date: '2026-10-16', subcategory: 'property_agency', track: 'web', rank: 1,
    status: 'approved', site_status: 'dead', area: 'Kilimani', top_fact_code: 'SITE_DEAD',
    message_variants: [{ message: 'A', used_fact_ids: ['F1'], source: 'llm', swahili_touch: false }],
    message_final: 'A', chosen_variant: 0, used_fact_ids: ['F1'], variant_source: 'llm', poster_lines: ['x'],
    teaser_path: 't.jpg', slug: 'kilima-homes', social_state: null, brand: { primary: '#123456' }, skip_reason: null,
    notes: null, approved_at: null, sent_at: null, fu1_due: null, fu1_sent_at: null, fu2_due: null, fu2_sent_at: null,
    replied_at: null, reply_type: null, snoozed_until: null, demo_type: null, demo_queued_at: null, demo_link: null,
    demo_sent_at: null, demo_fu1_due: null, demo_fu1_sent_at: null, demo_fu2_due: null, demo_fu2_sent_at: null,
    outcome_value_kes: null, lost_reason: null, closed_at: null, created_at: '', updated_at: '',
    business: { place_id: 'P1', name: 'Kilima Homes Ltd', display_name: 'Kilima Homes', area: 'Kilimani', address: 'Rd',
      phone_e164: '+254722123456', website_url: 'http://kilimahomes.co.ke', maps_url: 'https://maps', rating: 4.6,
      review_count: 62, branch_count: 1, manages_listings: 0, audit: null },
    evaluation: { score: 80, breakdown: {}, facts: { facts: [{ id: 'F1', code: 'SITE_DEAD', strength: 'strong', text: 'dead', evidence: {}, track: 'web', source: 'audit' }], review_facts: [] } },
    ...over,
  }
}

describe('transitions', () => {
  it('markSent computes FU1/FU2 across Mashujaa Day', () => {
    const a = markSent(lead(), '2026-10-16T07:00:00Z', '2026-10-16', cal)
    expect(a.patch).toMatchObject({ status: 'sent', fu1_due: '2026-10-22', fu2_due: '2026-10-29' })
  })
  it('markSent across Christmas and the December break', () => {
    const a = markSent(lead(), '2026-12-17T07:00:00Z', '2026-12-17', cal)
    expect(a.patch.fu1_due).toBe('2027-01-05')
  })
  it('skip and no-whatsapp promote a reserve', () => {
    expect(skip('too_big').promoteReserve).toBe(true)
  })
  it('opt-out suppresses the phone immediately', () => {
    expect(optOut(lead(), 'now').suppress).toEqual({ phone_e164: '+254722123456', place_id: 'P1', reason: 'opted_out' })
  })
  it('FU2 ends the sequence', () => {
    expect(followupSent(lead({ status: 'sent' }), 'fu2', 'now').patch.status).toBe('no_response')
  })
  it('demo follow-ups at +1 and +4 working days', () => {
    expect(demoSent('t', '2026-10-19', cal).patch).toMatchObject({ demo_fu1_due: '2026-10-21', demo_fu2_due: '2026-10-26' })
  })
  it('a reply never moves an interested lead backwards', () => {
    expect(logReply(lead({ status: 'demo_queued' }), 'question', '', 'n').patch.status).toBeUndefined()
    expect(markInterested(lead(), 'content', 'n').patch).toMatchObject({ status: 'demo_queued', demo_type: 'content' })
  })
})

describe('follow-up queue', () => {
  const settings = { followup_templates: { fu1: 'FU1 {business} {weekday}', fu2_web: 'FU2W', fu2_content: 'FU2C', demo_fu1: 'D1', demo_fu2: 'D2' } } as never
  it('lists FU1 due today with the weekday of the first message', () => {
    const l = lead({ status: 'sent', sent_at: '2026-10-16T07:00:00Z', fu1_due: '2026-10-22', fu2_due: '2026-10-29' })
    expect(dueFollowups([l], '2026-10-21', settings)).toHaveLength(0)
    const d = dueFollowups([l], '2026-10-22', settings)
    expect(d[0].kind).toBe('fu1')
    expect(d[0].message).toBe('FU1 Kilima Homes Friday')
  })
  it('lists FU2 once its date arrives', () => {
    const l = lead({ status: 'sent', sent_at: '2026-10-16T07:00:00Z', fu1_due: '2026-10-22', fu1_sent_at: 'x', fu2_due: '2026-10-29' })
    expect(dueFollowups([l], '2026-10-29', settings)[0]).toMatchObject({ kind: 'fu2', message: 'FU2W' })
  })
})

describe('lead pack', () => {
  it('has the §15.3 shape', () => {
    const p = buildLeadPack(lead({ demo_type: 'web' }))
    expect(Object.keys(p)).toEqual(['lead_id', 'track', 'subcategory', 'template_id', 'business', 'brand', 'facts', 'review_themes', 'poster_lines', 'preview_domain'])
    expect(p.business.name).toBe('Kilima Homes')
    expect(p.preview_domain).toBe('kilima-homes.raswaltechsolutions.co.ke')
  })
})

describe('stats funnel matches the events log', () => {
  it('counts each stage once per lead', () => {
    const ev = (lead_id: string, type: string, payload: Record<string, unknown>): EventRow => ({ id: Math.random(), lead_id, at: '', type, payload })
    const events = [
      ev('a', 'status', { to: 'sent' }), ev('a', 'reply', {}), ev('a', 'status', { to: 'replied' }),
      ev('a', 'status', { to: 'demo_queued' }), ev('a', 'status', { to: 'demo_sent' }), ev('a', 'status', { to: 'won' }),
      ev('b', 'status', { to: 'sent' }), ev('c', 'status', { to: 'sent' }), ev('c', 'reply', {}),
    ]
    expect(funnel(['a', 'b', 'c'], stagesFromEvents(events))).toEqual({ sent: 3, replied: 2, interested: 1, demo: 1, won: 1 })
    expect([...stagesFromLead(lead({ sent_at: 'x', replied_at: 'y' }))]).toEqual(['sent', 'replied'])
  })
})

describe('phones', () => {
  it('normalises Kenyan formats', () => {
    expect(normalizeKe('0722 123 456')).toBe('+254722123456')
    expect(normalizeKe('254722123456')).toBe('+254722123456')
    expect(normalizeKe('+254 110 123456')).toBe('+254110123456')
    expect(normalizeKe('722123456')).toBe('+254722123456')
    expect(normalizeKe('12')).toBeNull()
  })
})
