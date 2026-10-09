import { describe, expect, it } from 'vitest'
import vectors from '../../../tests/fixtures/workdays_cases.json'
import { addWorkingDays, todayIn } from './workdays'

// Same calendar as config/calendar.yaml (Oct 2026 – Jan 2027 holidays + December break)
const cal = {
  send_days: ['mon', 'tue', 'wed', 'thu', 'fri'],
  holidays: [
    { date: '2026-10-10', name: 'Utamaduni' }, { date: '2026-10-20', name: 'Mashujaa' },
    { date: '2026-12-12', name: 'Jamhuri' }, { date: '2026-12-25', name: 'Christmas' },
    { date: '2026-12-26', name: 'Boxing' }, { date: '2027-01-01', name: "New Year's" },
  ],
  pauses: [{ start: '2026-12-21', end: '2027-01-01', name: 'December break' }],
  pauses_block_followups: true,
}

describe('working days (shared vectors with the Python pipeline)', () => {
  for (const c of vectors.cases) {
    it(c.name, () => {
      expect(addWorkingDays({ ...cal, pauses_block_followups: c.pauses_block_followups }, c.start, c.n)).toBe(c.expect)
    })
  }
})

describe('todayIn', () => {
  it('uses Nairobi time', () => {
    expect(todayIn('Africa/Nairobi', new Date('2026-10-11T21:30:00Z'))).toBe('2026-10-12')
  })
})
