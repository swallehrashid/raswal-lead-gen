import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import type { EventRow, Lead } from '../data/types'
import { stagesFromEvents, stagesFromLead } from './stats'

const path = resolve(__dirname, '../../public/mock/dataset.json')

describe.runIf(existsSync(path))('mock dataset', () => {
  const d = JSON.parse(readFileSync(path, 'utf8')) as { leads: Lead[]; events: EventRow[] }
  it('funnel from the events log matches lead timestamps for every lead', () => {
    const stages = stagesFromEvents(d.events)
    for (const l of d.leads.filter((x) => x.sent_at)) {
      expect([...(stages.get(l.id) ?? [])].sort(), l.business.display_name ?? l.id).toEqual([...stagesFromLead(l)].sort())
    }
  })
  it('every lead has two message variants and the Supabase select shape', () => {
    for (const l of d.leads) {
      expect(l.message_variants.length).toBe(2)
      expect(l.business.place_id).toBe(l.place_id)
    }
  })
})
