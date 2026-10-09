import { useMemo, useState } from 'react'
import { ReviewCard } from '../components/ReviewCard'
import { SendCard, type Flow } from '../components/SendCard'
import { Badge, Card, Empty, Spinner, Tabs } from '../components/ui'
import { useApp, useData } from '../context'
import type { Lead } from '../data/types'
import { niceDate, niceTime } from '../lib/format'

const canShareFiles = () => {
  try {
    return Boolean(navigator.canShare?.({ files: [new File([''], 'x.jpg', { type: 'image/jpeg' })] }))
  } catch {
    return false
  }
}

export function Today() {
  const { api, settings } = useApp()
  const { data, error } = useData(async () => {
    const d = await api.latestListDate()
    return { date: d, leads: d ? await api.leadsForList(d) : [] }
  }, [api])
  const [mode, setMode] = useState<'review' | 'send' | null>(null)
  const [tab, setTab] = useState<'web' | 'content' | 'reserves'>('web')
  const [flow, setFlow] = useState<Flow>(canShareFiles() ? 'phone' : 'desktop')

  if (error) return <Empty title="Could not load today's list">{error}</Empty>
  if (!data) return <Spinner />
  if (!data.date) return <Empty title="No list yet">The first nightly run creates it.</Empty>
  const leads = data.leads
  const sub = leads[0]?.subcategory ?? ''
  const active = (t: string) => leads.filter((l) => l.track === t && !['reserve', 'skipped', 'no_whatsapp'].includes(l.status))
  const reserves = leads.filter((l) => l.status === 'reserve')
  const toReview = leads.filter((l) => l.status === 'shortlisted')
  const approved = leads.filter((l) => l.status === 'approved').sort((a, b) => a.track.localeCompare(b.track) || a.rank - b.rank)
  const sentHere = leads.filter((l) => l.sent_at)
  const currentMode = mode ?? (toReview.length ? 'review' : 'send')
  const targets = settings.daily_targets ?? { web: 20, content: 10 }

  return (
    <div className="space-y-3">
      <Card className="p-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-navy/50">List for {niceDate(data.date)}</div>
            <div className="text-xl font-extrabold text-navy">{settings.subcategories[sub]?.label ?? sub}</div>
          </div>
          <div className="flex flex-wrap gap-1.5 text-sm">
            <Badge tone="navy">Web {active('web').length}/{targets.web}</Badge>
            <Badge tone="gold">Content {active('content').length}/{targets.content}</Badge>
            <Badge>Reserves {reserves.length}</Badge>
          </div>
        </div>
        <div className="mt-3">
          <Tabs value={currentMode} onChange={setMode} items={[
            { value: 'review', label: `Review (${toReview.length})` },
            { value: 'send', label: `Send (${approved.length})` },
          ]} />
        </div>
      </Card>

      {currentMode === 'review' ? (
        <>
          <Tabs value={tab} onChange={setTab} items={[
            { value: 'web', label: 'Website' }, { value: 'content', label: 'Content' }, { value: 'reserves', label: `Reserves (${reserves.length})` },
          ]} />
          <ReviewList leads={tab === 'reserves' ? reserves : leads.filter((l) => l.track === tab && l.status !== 'reserve')} />
        </>
      ) : (
        <>
          <Pacing sent={sentHere} />
          <div className="flex items-center justify-end gap-2 text-sm text-navy/60">
            Flow: <Tabs value={flow} onChange={setFlow} items={[{ value: 'phone', label: 'Phone' }, { value: 'desktop', label: 'WhatsApp Web' }]} />
          </div>
          {approved.length ? approved.map((l) => <SendCard key={l.id} lead={l} flow={flow} />)
            : <Empty title="Nothing approved to send">Approve leads in Review first.</Empty>}
          {sentHere.length > 0 && (
            <details className="rounded-2xl bg-white p-3">
              <summary className="cursor-pointer text-sm font-semibold text-navy">Sent from this list ({sentHere.length})</summary>
              <ul className="mt-2 space-y-1 text-sm">
                {sentHere.map((l) => <li key={l.id} className="flex justify-between"><span>{l.business.display_name}</span><span className="text-navy/50">{niceTime(l.sent_at)}</span></li>)}
              </ul>
            </details>
          )}
        </>
      )}
    </div>
  )
}

function ReviewList({ leads }: { leads: Lead[] }) {
  const ordered = useMemo(() => [...leads].sort((a, b) => Number(a.status !== 'shortlisted') - Number(b.status !== 'shortlisted') || a.rank - b.rank), [leads])
  if (!ordered.length) return <Empty title="Nothing here" />
  return <div className="space-y-3">{ordered.map((l) => <ReviewCard key={l.id} lead={l} />)}</div>
}

function Pacing({ sent }: { sent: Lead[] }) {
  const { api, settings } = useApp()
  const pacing = settings.calendar.pacing
  const tz = settings.calendar.timezone
  const now = new Date(api.now())
  const lastHour = sent.filter((l) => now.getTime() - new Date(l.sent_at!).getTime() < 3600_000).length
  const hhmm = new Intl.DateTimeFormat('en-GB', { timeZone: tz, hour: '2-digit', minute: '2-digit', hour12: false }).format(now)
  const inWindow = pacing.batch_windows.some((w) => w.start <= hhmm && hhmm <= w.end)
  const over = lastHour >= pacing.max_per_hour
  return (
    <Card className={over ? 'border-2 border-amber-400 p-3' : 'p-3'}>
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span><b>{lastHour}</b> sent in the last hour (max {pacing.max_per_hour})</span>
        <span className="text-navy/60">Batches: {pacing.batch_windows.map((w) => `${w.start}–${w.end}`).join(' · ')}
          {inWindow ? <Badge tone="green" className="ml-2">in a batch window</Badge> : <Badge className="ml-2">outside the windows</Badge>}</span>
      </div>
      {over && <p className="mt-1 text-sm font-semibold text-amber-800">Take a break: {pacing.max_per_hour}+ messages in an hour risks the number.</p>}
    </Card>
  )
}
