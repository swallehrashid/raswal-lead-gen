import { parseDate } from './workdays'

export function niceDate(s: string | null | undefined): string {
  if (!s) return '—'
  const d = parseDate(s.slice(0, 10))
  return d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' })
}

export function niceTime(iso: string | null | undefined, tz = 'Africa/Nairobi'): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('en-GB', { timeZone: tz, weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

export const label = (s: string | null | undefined) => (s ?? '').replaceAll('_', ' ')

export function mb(bytes: number) {
  return `${(bytes / 1e6).toFixed(0)} MB`
}

export const STATUS_TONE: Record<string, string> = {
  shortlisted: 'cyan', reserve: 'grey', approved: 'gold', skipped: 'grey', sent: 'navy', no_whatsapp: 'grey',
  replied: 'cyan', interested: 'green', demo_queued: 'gold', demo_sent: 'gold', negotiating: 'green', won: 'green',
  lost: 'red', no_response: 'grey', snoozed: 'amber', opted_out: 'red',
  pilot_onboarding: 'amber', pilot_live: 'green', pilot_review: 'gold',
}

export const SITE_TONE: Record<string, string> = {
  none: 'grey', social_as_site: 'amber', dead: 'red', insecure: 'red', free_builder: 'amber', weak: 'amber', good: 'green',
}
