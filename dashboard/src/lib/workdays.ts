// Working days for follow-up dates. Twin of pipeline/utils/dates.py; both are tested
// against tests/fixtures/workdays_cases.json.
import type { CalendarSettings } from '../data/types'

const KEYS = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat']

export function parseDate(s: string): Date {
  const [y, m, d] = s.slice(0, 10).split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d))
}

export function fmtDate(d: Date): string {
  return d.toISOString().slice(0, 10)
}

export function addDays(s: string, n: number): string {
  const d = parseDate(s)
  d.setUTCDate(d.getUTCDate() + n)
  return fmtDate(d)
}

export function weekdayKey(s: string): string {
  return KEYS[parseDate(s).getUTCDay()]
}

type Cal = Pick<CalendarSettings, 'send_days' | 'holidays' | 'pauses' | 'pauses_block_followups'>

export function pauseFor(cal: Cal, s: string, extra: Array<{ start: string; end: string }> = []): boolean {
  return [...cal.pauses, ...extra].some((p) => p.start <= s && s <= p.end)
}

export function isWorkingDay(cal: Cal, s: string, extraPauses: Array<{ start: string; end: string }> = []): boolean {
  if (!cal.send_days.includes(weekdayKey(s))) return false
  if (cal.holidays.some((h) => h.date === s)) return false
  if (cal.pauses_block_followups && pauseFor(cal, s, extraPauses)) return false
  return true
}

/** The date n working days after start (start itself never counts). */
export function addWorkingDays(cal: Cal, start: string, n: number, extraPauses: Array<{ start: string; end: string }> = []): string {
  let d = start.slice(0, 10)
  let left = n
  while (left > 0) {
    d = addDays(d, 1)
    if (isWorkingDay(cal, d, extraPauses)) left -= 1
  }
  return d
}

/** Today's date in the calendar's timezone (Africa/Nairobi). */
export function todayIn(tz: string, now: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(now)
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? ''
  return `${get('year')}-${get('month')}-${get('day')}`
}

export function hourIn(tz: string, iso: string): number {
  return Number(new Intl.DateTimeFormat('en-GB', { timeZone: tz, hour: '2-digit', hour12: false }).format(new Date(iso)))
}

export function weekdayName(s: string): string {
  return ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'][parseDate(s).getUTCDay()]
}
