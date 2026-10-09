import { useState } from 'react'
import { useApp, useData } from '../context'
import type { EventRow, Lead, Track } from '../data/types'
import {
  logReply, LOST_REASONS, markInterested, markLost, negotiating, optOut, REPLY_TYPES, setNotes, snooze, won,
} from '../lib/actions'
import { fill } from '../lib/followups'
import { label, niceDate, niceTime } from '../lib/format'
import { waPhoneLink } from '../lib/phone'
import { addDays } from '../lib/workdays'
import { FileImg } from './FileImg'
import { FactList, LeadHeader, ScoreChips } from './LeadBits'
import { Button, CopyButton, Field, inputCls, Sheet, useToast } from './ui'

const CLOSED = new Set(['won', 'lost', 'opted_out'])

export function LeadSheet({ leadId, onClose }: { leadId: string | null; onClose: () => void }) {
  const { api } = useApp()
  const { data } = useData(async () => (leadId ? Promise.all([api.lead(leadId), api.events([leadId])]) : null), [leadId])
  const lead = data?.[0] ?? null
  return (
    <Sheet open={!!leadId} onClose={onClose} title={lead ? lead.business.display_name || lead.business.name : 'Lead'}>
      {!lead ? <p className="text-sm text-navy/50">Loading…</p> : <LeadDetail lead={lead} events={data?.[1] ?? []} />}
    </Sheet>
  )
}

function LeadDetail({ lead, events }: { lead: Lead; events: EventRow[] }) {
  const { act, api, today, settings } = useApp()
  const toast = useToast()
  const [replyType, setReplyType] = useState<string>('question')
  const [replyText, setReplyText] = useState('')
  const [snoozeUntil, setSnoozeUntil] = useState(today.slice(0, 4) === '2026' ? '2027-01-04' : addDays(today, 60))
  const [lostReason, setLostReason] = useState<string>('has_provider')
  const [value, setValue] = useState<string>(lead.outcome_value_kes ? String(lead.outcome_value_kes) : '')
  const [notes, setNotesText] = useState(lead.notes ?? '')
  const closed = CLOSED.has(lead.status)
  const now = api.now()

  const doReply = async () => {
    if (replyType === 'interested') return toast('Use “Mark interested” below to pick the demo type')
    await act(lead, logReply(lead, replyType, replyText, now), 'Reply logged')
    if (replyType === 'not_now') await act(lead, snooze(snoozeUntil), `Snoozed until ${niceDate(snoozeUntil)}`)
    if (replyType === 'has_provider') await act(lead, markLost('has_provider', now), 'Marked lost (has provider)')
    if (replyType === 'stop' && confirm('Opt out: they will never be contacted again. Continue?'))
      await act(lead, optOut(lead, now), 'Opted out and suppressed')
    setReplyText('')
  }
  const interested = async (t: Track) => {
    await act(lead, markInterested(lead, t, now), 'Moved to the demo queue')
  }
  const quick = async (q: { text: string; action?: string | null }) => {
    const t = fill(q.text, lead)
    await navigator.clipboard?.writeText(t).catch(() => undefined)
    toast('Reply copied')
    if (q.action === 'lost_has_provider') await act(lead, markLost('has_provider', now), 'Marked lost (has provider)')
    if (q.action === 'snooze') await act(lead, snooze(snoozeUntil), `Snoozed until ${niceDate(snoozeUntil)}`)
    if (q.action === 'opt_out' && confirm('Opt out: they will never be contacted again. Continue?'))
      await act(lead, optOut(lead, now), 'Opted out and suppressed')
  }

  return (
    <div className="space-y-4">
      <LeadHeader lead={lead} />
      <ScoreChips lead={lead} />
      <div className="flex gap-3">
        <FileImg path={lead.teaser_path} alt="Teaser" className="aspect-[4/5] w-24 shrink-0 rounded-xl" />
        <div className="min-w-0 space-y-2">
          <p className="whitespace-pre-wrap text-sm text-navy/80">{lead.message_final ?? lead.message_variants[0]?.message}</p>
          {lead.business.phone_e164 && <a href={waPhoneLink(lead.business.phone_e164)} target="_blank" rel="noreferrer"><Button size="sm" variant="wa">Open chat</Button></a>}
        </div>
      </div>
      <details><summary className="cursor-pointer text-sm font-semibold text-navy/60">Facts</summary><div className="mt-2"><FactList lead={lead} /></div></details>

      {!closed && (
        <section className="space-y-2 rounded-2xl bg-white p-3">
          <div className="font-semibold text-navy">Log reply</div>
          <div className="flex flex-wrap gap-1.5">
            {REPLY_TYPES.map((t) => (
              <Button key={t} size="sm" variant={replyType === t ? 'primary' : 'outline'} onClick={() => setReplyType(t)}>{label(t)}</Button>
            ))}
          </div>
          {replyType === 'not_now' && <Field label="Check back on"><input type="date" className={inputCls} value={snoozeUntil} onChange={(e) => setSnoozeUntil(e.target.value)} /></Field>}
          <textarea className={inputCls} rows={2} placeholder="Paste their reply (optional)" value={replyText} onChange={(e) => setReplyText(e.target.value)} />
          <Button variant="primary" onClick={doReply}>Save reply</Button>
        </section>
      )}

      <section className="space-y-2 rounded-2xl bg-white p-3">
        <div className="font-semibold text-navy">Quick replies</div>
        {settings.quick_replies.map((q) => (
          <div key={q.key} className="flex items-start gap-2 border-t border-navy/5 pt-2 first:border-0 first:pt-0">
            <div className="min-w-0 flex-1">
              <div className="text-xs font-semibold text-navy/50">{q.label}{q.action ? ` · then ${label(q.action)}` : ''}</div>
              <div className="text-sm text-navy/80">{fill(q.text, lead)}</div>
            </div>
            <Button size="sm" onClick={() => quick(q)}>Copy</Button>
          </div>
        ))}
      </section>

      {!closed && !['demo_queued', 'demo_sent', 'negotiating'].includes(lead.status) && (
        <section className="space-y-2 rounded-2xl bg-white p-3">
          <div className="font-semibold text-navy">Mark interested → demo queue</div>
          <div className="flex gap-2">
            <Button variant="gold" className="flex-1" onClick={() => interested('web')}>Website demo</Button>
            <Button variant="gold" className="flex-1" onClick={() => interested('content')}>Content demo</Button>
          </div>
        </section>
      )}

      {['demo_sent', 'negotiating', 'replied', 'demo_queued'].includes(lead.status) && (
        <section className="space-y-2 rounded-2xl bg-white p-3">
          <div className="font-semibold text-navy">Outcome</div>
          <div className="flex flex-wrap gap-2">
            {lead.status !== 'negotiating' && <Button onClick={() => act(lead, negotiating(), 'Negotiating')}>Negotiating</Button>}
            <input className={`${inputCls} w-36`} inputMode="numeric" placeholder="Value KES" value={value} onChange={(e) => setValue(e.target.value.replace(/\D/g, ''))} />
            <Button variant="gold" onClick={() => act(lead, won(value ? Number(value) : null, now), 'Won 🎉')}>Won</Button>
          </div>
          <div className="flex flex-wrap gap-2">
            <select className={`${inputCls} w-48`} value={lostReason} onChange={(e) => setLostReason(e.target.value)}>
              {LOST_REASONS.map((r) => <option key={r} value={r}>{label(r)}</option>)}
            </select>
            <Button onClick={() => act(lead, markLost(lostReason, now), 'Marked lost')}>Lost</Button>
          </div>
        </section>
      )}

      {!closed && lead.status !== 'opted_out' && (
        <Button variant="danger" size="sm" onClick={async () => {
          if (confirm('Opt out: they will never be contacted again. Continue?')) await act(lead, optOut(lead, now), 'Opted out and suppressed')
        }}>Opt out (stop)</Button>
      )}

      <section className="space-y-2">
        <Field label="Notes"><textarea className={inputCls} rows={2} value={notes} onChange={(e) => setNotesText(e.target.value)} /></Field>
        {notes !== (lead.notes ?? '') && <Button size="sm" onClick={() => act(lead, setNotes(notes), 'Notes saved')}>Save notes</Button>}
        {lead.demo_link && <div className="text-sm">Demo: <a className="text-cyan underline" href={lead.demo_link} target="_blank" rel="noreferrer">{lead.demo_link}</a> <CopyButton size="sm" text={lead.demo_link} /></div>}
      </section>

      <section>
        <div className="mb-1 font-semibold text-navy">Timeline</div>
        <ol className="space-y-1 border-l-2 border-navy/10 pl-3 text-sm">
          {events.map((e) => (
            <li key={String(e.id)}>
              <span className="text-navy/50">{niceTime(e.at)}</span>{' '}
              <b className="text-navy">{e.type === 'status' ? `${label(String(e.payload.from ?? ''))} → ${label(String(e.payload.to))}` : label(e.type)}</b>
              {e.type === 'reply' && <span className="text-navy/70"> · {label(String(e.payload.reply_type))}{e.payload.text ? `: “${String(e.payload.text)}”` : ''}</span>}
              {e.type === 'demo_link' && <span className="text-navy/70"> · {String(e.payload.link)}</span>}
            </li>
          ))}
          {!events.length && <li className="text-navy/50">No events yet.</li>}
        </ol>
      </section>
    </div>
  )
}
