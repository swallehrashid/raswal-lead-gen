import { useMemo, useState } from 'react'
import { LeadSheet } from '../components/LeadSheet'
import { Badge, Card, Empty, inputCls, Spinner } from '../components/ui'
import { useApp, useData } from '../context'
import { CONTACTED } from '../data/api'
import { label, niceDate, STATUS_TONE } from '../lib/format'
import { displayPhone } from '../lib/phone'

export function Inbox() {
  const { api } = useApp()
  const [q, setQ] = useState('')
  const [open, setOpen] = useState<string | null>(null)
  const { data } = useData(async () => api.leads({ statuses: CONTACTED, limit: 3000 }), [api])
  const results = useMemo(() => {
    if (!data) return []
    const s = q.trim().toLowerCase()
    const digits = s.replace(/\D/g, '')
    if (!s) return [...data].sort((a, b) => (b.replied_at ?? b.sent_at ?? '').localeCompare(a.replied_at ?? a.sent_at ?? '')).slice(0, 30)
    return data.filter((l) => {
      const b = l.business
      return (b.display_name ?? b.name).toLowerCase().includes(s) || b.name.toLowerCase().includes(s)
        || (digits.length >= 3 && (b.phone_e164 ?? '').replace(/\D/g, '').includes(digits.replace(/^0/, '')))
    }).slice(0, 50)
  }, [data, q])
  return (
    <div className="space-y-3">
      <h1 className="text-xl font-extrabold text-navy">Inbox log</h1>
      <input className={inputCls} autoFocus placeholder="Search by business name or phone" value={q} onChange={(e) => setQ(e.target.value)} />
      {!data ? <Spinner /> : !results.length ? <Empty title="No match">Only businesses you've messaged are searchable here.</Empty> : (
        <div className="space-y-2">
          {!q && <div className="text-xs font-semibold uppercase tracking-wide text-navy/50">Recent</div>}
          {results.map((l) => (
            <Card key={l.id} className="p-3">
              <button onClick={() => setOpen(l.id)} className="flex w-full items-center justify-between gap-2 text-left">
                <div className="min-w-0">
                  <div className="truncate font-semibold text-navy">{l.business.display_name}</div>
                  <div className="text-xs text-navy/50">{displayPhone(l.business.phone_e164)} · sent {niceDate(l.sent_at)}{l.reply_type ? ` · replied: ${label(l.reply_type)}` : ''}</div>
                </div>
                <Badge tone={STATUS_TONE[l.status]}>{label(l.status)}</Badge>
              </button>
            </Card>
          ))}
        </div>
      )}
      <LeadSheet leadId={open} onClose={() => setOpen(null)} />
    </div>
  )
}
