import { useState } from 'react'
import { FileImg } from '../components/FileImg'
import { LeadSheet } from '../components/LeadSheet'
import { Badge, Button, Card, CopyButton, Empty, Spinner } from '../components/ui'
import { useApp, useData } from '../context'
import { followupSent } from '../lib/actions'
import { dueFollowups, type Due } from '../lib/followups'
import { niceDate } from '../lib/format'
import { waPhoneLink, waWebLink } from '../lib/phone'

const KIND_LABEL = { fu1: 'FU1', fu2: 'FU2 (last)', demo_fu1: 'Demo follow-up 1', demo_fu2: 'Demo follow-up 2', snooze: 'Snooze check-in' }

export function FollowUps() {
  const { api, today, settings } = useApp()
  const [open, setOpen] = useState<string | null>(null)
  const { data } = useData(async () => api.leads({ statuses: ['sent', 'demo_sent', 'snoozed'], limit: 2000 }), [api])
  if (!data) return <Spinner />
  const due = dueFollowups(data, today, settings)
  const groups: Array<[string, Due[]]> = [
    ['Follow-ups', due.filter((d) => d.kind === 'fu1' || d.kind === 'fu2')],
    ['Demo follow-ups', due.filter((d) => d.kind === 'demo_fu1' || d.kind === 'demo_fu2')],
    ['Snoozes due', due.filter((d) => d.kind === 'snooze')],
  ]
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-extrabold text-navy">Due today · {niceDate(today)}</h1>
      {!due.length && <Empty title="Nothing due today">FU1 goes out 3 working days after the first message, FU2 after 8.</Empty>}
      {groups.map(([title, items]) => items.length > 0 && (
        <section key={title} className="space-y-2">
          <h2 className="font-bold text-navy">{title} <span className="text-navy/40">({items.length})</span></h2>
          {items.map((d) => <DueCard key={`${d.lead.id}-${d.kind}`} d={d} onOpen={() => setOpen(d.lead.id)} />)}
        </section>
      ))}
      <LeadSheet leadId={open} onClose={() => setOpen(null)} />
    </div>
  )
}

function DueCard({ d, onOpen }: { d: Due; onOpen: () => void }) {
  const { act, api } = useApp()
  const [text, setText] = useState(d.message)
  const phone = d.lead.business.phone_e164 ?? ''
  return (
    <Card className="space-y-2 p-3">
      <div className="flex items-start gap-3">
        <FileImg path={d.lead.teaser_path} alt="" className="h-16 w-14 shrink-0 rounded-lg" />
        <div className="min-w-0 flex-1">
          <button onClick={onOpen} className="text-left font-bold text-navy underline-offset-2 hover:underline">{d.lead.business.display_name}</button>
          <div className="flex flex-wrap gap-1 text-xs">
            <Badge tone="navy">{KIND_LABEL[d.kind]}</Badge>
            {d.overdue && <Badge tone="red">due {niceDate(d.due)}</Badge>}
            {d.lead.sent_at && <span className="text-navy/50">first sent {niceDate(d.lead.sent_at)}</span>}
          </div>
        </div>
      </div>
      <textarea className="w-full rounded-xl border border-navy/15 p-2 text-sm" rows={3} value={text} onChange={(e) => setText(e.target.value)} />
      <div className="flex flex-wrap gap-2">
        <a href={waPhoneLink(phone)} target="_blank" rel="noreferrer" className="sm:hidden"><Button size="sm" variant="wa">Open chat</Button></a>
        <a href={waWebLink(phone)} target="_blank" rel="noreferrer" className="hidden sm:block"><Button size="sm" variant="wa">Open chat</Button></a>
        <CopyButton size="sm" text={text} label="Copy message" />
        <Button size="sm" variant="gold" className="ml-auto" onClick={() => act(d.lead, followupSent(d.lead, d.kind, api.now()), 'Marked sent')}>Mark sent ✓</Button>
      </div>
    </Card>
  )
}
