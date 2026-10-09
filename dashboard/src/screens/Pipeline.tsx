import { useMemo, useState } from 'react'
import { LeadSheet } from '../components/LeadSheet'
import { Badge, Card, cx, Empty, inputCls, Spinner } from '../components/ui'
import { useApp, useData } from '../context'
import type { LeadStatus, Track } from '../data/types'
import { label, niceDate, STATUS_TONE } from '../lib/format'

const STATUSES: LeadStatus[] = ['shortlisted', 'approved', 'sent', 'replied', 'snoozed', 'demo_queued', 'demo_sent', 'negotiating',
  'won', 'lost', 'no_response', 'opted_out', 'skipped', 'no_whatsapp', 'reserve']

export function Pipeline() {
  const { api, settings } = useApp()
  const [statuses, setStatuses] = useState<LeadStatus[]>(['sent', 'replied', 'snoozed', 'demo_queued', 'demo_sent', 'negotiating'])
  const [sub, setSub] = useState('')
  const [track, setTrack] = useState<'' | Track>('')
  const [from, setFrom] = useState('')
  const [open, setOpen] = useState<string | null>(null)
  const { data } = useData(async () => api.leads({ statuses, subcategory: sub || undefined, track: track || undefined, from: from || undefined, limit: 2000 }),
    [api, statuses.join(','), sub, track, from])
  const counts = useMemo(() => {
    const m: Record<string, number> = {}
    for (const l of data ?? []) m[l.status] = (m[l.status] ?? 0) + 1
    return m
  }, [data])
  const toggle = (s: LeadStatus) => setStatuses((x) => (x.includes(s) ? x.filter((y) => y !== s) : [...x, s]))
  return (
    <div className="space-y-3">
      <h1 className="text-xl font-extrabold text-navy">Pipeline</h1>
      <div className="flex flex-wrap gap-1.5">
        {STATUSES.map((s) => (
          <button key={s} onClick={() => toggle(s)} className={cx('rounded-full px-3 py-1 text-xs font-semibold', statuses.includes(s) ? 'bg-navy text-white' : 'bg-white text-navy/60 ring-1 ring-navy/10')}>
            {label(s)}{counts[s] ? ` ${counts[s]}` : ''}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-3 gap-2">
        <select className={inputCls} value={sub} onChange={(e) => setSub(e.target.value)}>
          <option value="">All subcategories</option>
          {Object.entries(settings.subcategories).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
        <select className={inputCls} value={track} onChange={(e) => setTrack(e.target.value as Track | '')}>
          <option value="">Both tracks</option><option value="web">Website</option><option value="content">Content</option>
        </select>
        <input type="date" className={inputCls} value={from} onChange={(e) => setFrom(e.target.value)} title="Listed from" />
      </div>
      {!data ? <Spinner /> : !data.length ? <Empty title="No leads match" /> : (
        <div className="space-y-2">
          {data.map((l) => (
            <Card key={l.id} className="p-3">
              <button className="flex w-full items-center justify-between gap-2 text-left" onClick={() => setOpen(l.id)}>
                <div className="min-w-0">
                  <div className="truncate font-semibold text-navy">{l.business.display_name}</div>
                  <div className="text-xs text-navy/50">{settings.subcategories[l.subcategory]?.label ?? l.subcategory} · {l.track} · listed {niceDate(l.list_date)}
                    {l.outcome_value_kes ? ` · KES ${l.outcome_value_kes.toLocaleString()}` : ''}{l.lost_reason ? ` · ${label(l.lost_reason)}` : ''}</div>
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
