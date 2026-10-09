import { useMemo, useState } from 'react'
import { Card, Empty, Spinner, Tabs } from '../components/ui'
import { useApp, useData } from '../context'
import { mb, niceDate } from '../lib/format'
import { breakdown, DIMENSIONS, funnel, pct, STAGES, stagesFromEvents, stagesFromLead } from '../lib/stats'

const STAGE_LABEL = { sent: 'Sent', replied: 'Replied', interested: 'Interested', demo: 'Demo sent', won: 'Won' }

export function Stats() {
  const { api, settings } = useApp()
  const month = api.today().slice(0, 7)
  const { data } = useData(async () => {
    const leads = await api.leads({ sentOnly: true, limit: 5000 })
    const [events, runs, usage, storage] = await Promise.all([
      api.events(), api.runs(30), api.apiUsage(month), api.usageStats(),
    ])
    return { leads, events, runs, usage, storage }
  }, [api, month])
  const [dim, setDim] = useState<keyof typeof DIMENSIONS>('subcategory')
  const stages = useMemo(() => (data ? stagesFromEvents(data.events) : new Map()), [data])
  if (!data) return <Spinner />
  const tz = settings.calendar.timezone
  const ids = data.leads.map((l) => l.id)
  const f = funnel(ids, stages)
  const mismatches = data.leads.filter((l) => {
    const a = [...stagesFromLead(l)].sort().join()
    const b = [...(stages.get(l.id) ?? [])].sort().join()
    return a !== b
  }).length
  const rows = breakdown(data.leads, stages, dim, tz)
  const b = settings.budget

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-extrabold text-navy">Stats</h1>
      {!ids.length ? <Empty title="No messages sent yet" /> : (
        <Card className="space-y-3 p-4">
          <div className="flex items-baseline justify-between">
            <h2 className="font-bold text-navy">Funnel (all time)</h2>
            <span className="text-xs text-navy/50">from the events log{mismatches ? ` · ${mismatches} lead(s) differ from their timestamps` : ' · matches lead timestamps'}</span>
          </div>
          <div className="space-y-2" role="list">
            {STAGES.map((s, i) => {
              const prev = i ? f[STAGES[i - 1]] : f.sent
              return (
                <div key={s} role="listitem" className="grid grid-cols-[6.5rem_1fr_6.5rem] items-center gap-3 text-sm"
                  title={`${STAGE_LABEL[s]}: ${f[s]} (${pct(f[s], f.sent)} of sent${i ? `, ${pct(f[s], prev)} of ${STAGE_LABEL[STAGES[i - 1]].toLowerCase()}` : ''})`}>
                  <span className="text-navy/70">{STAGE_LABEL[s]}</span>
                  <div className="h-5 rounded bg-navy/5">
                    <div className="h-5 rounded bg-navy" style={{ width: `${f.sent ? Math.max(1, (f[s] / f.sent) * 100) : 0}%` }} />
                  </div>
                  <span className="tabular-nums text-navy"><b>{f[s]}</b> <span className="text-navy/50">{i ? pct(f[s], prev) : ''}</span></span>
                </div>
              )
            })}
          </div>
        </Card>
      )}

      {ids.length > 0 && (
        <Card className="space-y-3 p-4">
          <h2 className="font-bold text-navy">Rates by</h2>
          <div className="overflow-x-auto"><Tabs value={dim} onChange={setDim} items={Object.entries(DIMENSIONS).map(([k, v]) => ({ value: k as keyof typeof DIMENSIONS, label: v.label }))} /></div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm tabular-nums">
              <thead className="text-left text-xs uppercase tracking-wide text-navy/50">
                <tr><th className="py-1 pr-2">{DIMENSIONS[dim].label}</th><th className="px-2 text-right">Sent</th><th className="px-2 text-right">Reply</th>
                  <th className="px-2 text-right">Interested</th><th className="px-2 text-right">Demo</th><th className="pl-2 text-right">Won</th></tr>
              </thead>
              <tbody className="divide-y divide-navy/5">
                {rows.map((r) => (
                  <tr key={r.key}>
                    <td className="py-1.5 pr-2 font-semibold text-navy">{dim === 'subcategory' ? settings.subcategories[r.key]?.label ?? r.key : r.key.replaceAll('_', ' ')}</td>
                    <td className="px-2 text-right">{r.sent}</td>
                    <td className="px-2 text-right">{pct(r.replied, r.sent)}</td>
                    <td className="px-2 text-right">{pct(r.interested, r.sent)}</td>
                    <td className="px-2 text-right">{pct(r.demo, r.sent)}</td>
                    <td className="pl-2 text-right">{r.won}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-navy/50">Make 1–2 config changes a week at most, so you can tell what worked.</p>
        </Card>
      )}

      <Card className="space-y-3 p-4">
        <h2 className="font-bold text-navy">Nightly runs & gate rejections</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm tabular-nums">
            <thead className="text-left text-xs uppercase tracking-wide text-navy/50">
              <tr><th className="py-1 pr-2">List</th><th className="px-2">Status</th><th className="px-2 text-right">Found</th><th className="px-2 text-right">Passed</th>
                <th className="px-2 text-right">Shipped</th><th className="pl-2">Top rejections</th></tr>
            </thead>
            <tbody className="divide-y divide-navy/5">
              {data.runs.map((r) => (
                <tr key={r.id} className="align-top">
                  <td className="py-1.5 pr-2 whitespace-nowrap">{niceDate(r.list_date)}<div className="text-xs text-navy/50">{settings.subcategories[r.subcategory ?? '']?.label ?? r.subcategory}{r.dry_run ? ' · dry run' : ''}</div></td>
                  <td className="px-2">{r.status}{r.skipped_reason ? <div className="text-xs text-navy/50">{r.skipped_reason}</div> : null}</td>
                  <td className="px-2 text-right">{r.raw_candidates}</td>
                  <td className="px-2 text-right">{r.passed_gates}</td>
                  <td className="px-2 text-right">{r.shipped_web}+{r.shipped_content}</td>
                  <td className="pl-2 text-xs text-navy/70">{Object.entries(r.gate_counts ?? {}).sort((a, b) => b[1] - a[1]).slice(0, 4).map(([k, v]) => `${k.toLowerCase()} ${v}`).join(' · ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card className="space-y-3 p-4">
        <h2 className="font-bold text-navy">Free-tier usage</h2>
        <Meter label={`Places calls (${month})`} value={sum(data.usage, 'places')} cap={b.places_calls_per_month} unit="" />
        <Meter label={`PageSpeed calls (${month})`} value={sum(data.usage, 'psi')} cap={null} unit="" note="25,000/day free" />
        <Meter label={`Gemini calls (${month})`} value={sum(data.usage, 'gemini')} cap={null} unit="" note={`≤ ${b.gemini_calls_per_night}/night`} />
        {data.storage ? (
          <>
            <Meter label="Supabase database" value={data.storage.db_bytes / 1e6} cap={b.db_cap_mb} unit=" MB" note="free plan 500 MB" />
            <Meter label={`Supabase storage (${data.storage.storage_files} files)`} value={data.storage.storage_bytes / 1e6} cap={b.storage_cap_mb} unit=" MB" note="free plan 1 GB" />
          </>
        ) : <p className="text-sm text-navy/50">Storage usage unavailable.</p>}
        <p className="text-xs text-navy/50">Caps are our own (config/budget.yaml), set below the free allowances. {data.storage ? `DB ${mb(data.storage.db_bytes)}.` : ''}</p>
      </Card>
    </div>
  )
}

function sum(rows: Array<{ api: string; count: number }>, api: string) {
  return rows.filter((r) => r.api === api).reduce((a, r) => a + r.count, 0)
}

function Meter({ label, value, cap, unit, note }: { label: string; value: number; cap: number | null; unit: string; note?: string }) {
  const share = cap ? value / cap : 0
  const state = share >= 1 ? 'over cap' : share >= 0.8 ? 'near cap' : null
  return (
    <div title={`${label}: ${Math.round(value)}${unit}${cap ? ` of ${cap}${unit}` : ''}`}>
      <div className="flex justify-between text-sm">
        <span className="text-navy/70">{label}</span>
        <span className="tabular-nums text-navy"><b>{Math.round(value).toLocaleString()}{unit}</b>{cap ? <span className="text-navy/50"> / {cap.toLocaleString()}{unit}</span> : null}
          {state && <span className={share >= 1 ? 'ml-2 font-semibold text-red-700' : 'ml-2 font-semibold text-amber-700'}>{share >= 1 ? '⚠ ' : '▲ '}{state}</span>}</span>
      </div>
      {cap ? (
        <div className="mt-1 h-2 rounded bg-navy/5">
          <div className={share >= 1 ? 'h-2 rounded bg-red-600' : share >= 0.8 ? 'h-2 rounded bg-amber-500' : 'h-2 rounded bg-navy'} style={{ width: `${Math.min(100, Math.max(1, share * 100))}%` }} />
        </div>
      ) : note ? null : null}
      {note && <div className="text-xs text-navy/40">{note}</div>}
    </div>
  )
}
