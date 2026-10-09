import { useApp, useData } from '../context'
import { niceDate, label } from '../lib/format'

export function Banner() {
  const { api, today, settings } = useApp()
  const { data } = useData(async () => {
    const [runs, cells] = await Promise.all([api.runs(5), api.cellSummary()])
    return { run: runs.find((r) => !r.dry_run) ?? null, cells }
  }, [api])
  if (!data) return null
  const { run, cells } = data
  const low = cells.filter((c) => c.tier1_total && c.tier1_active <= Math.max(1, Math.floor(c.tier1_total / 5)))
  const pause = settings.pause_list?.find((p) => p.start <= today && today <= p.end)
  return (
    <div className="space-y-2">
      {api.mode === 'mock' && (
        <div className="rounded-xl bg-cyan-100 px-3 py-2 text-sm text-[#155675]">
          <b>Mock data</b> from the test fixtures (today is {niceDate(today)}). Set <code>VITE_SUPABASE_URL</code> to use the real backend.
        </div>
      )}
      {pause && <div className="rounded-xl bg-amber-100 px-3 py-2 text-sm text-amber-900"><b>Paused</b> until {niceDate(pause.end)}{pause.note ? ` · ${pause.note}` : ''}. Demos and replies only.</div>}
      {run && run.status === 'failed' && (
        <div className="rounded-xl bg-red-100 px-3 py-2 text-sm text-red-800">
          <b>Last night's run failed</b> ({niceDate(run.list_date)}): {run.errors?.[0]?.error ?? 'see GitHub Actions log'}.
          Re-run: GitHub app → Actions → Nightly → Run workflow.
        </div>
      )}
      {run && run.status === 'ok' && run.list_date > today && (
        <div className="rounded-xl bg-green-100 px-3 py-2 text-sm text-green-900">
          <b>{niceDate(run.list_date)}'s list ready:</b> {run.shipped_web} web / {run.shipped_content} content
          {run.errors?.length ? ` · ${run.errors.length} warning(s)` : ''}
        </div>
      )}
      {run && run.status === 'skipped' && run.list_date >= today && (
        <div className="rounded-xl bg-navy/5 px-3 py-2 text-sm text-navy/70">No list for {niceDate(run.list_date)}: {run.skipped_reason}</div>
      )}
      {low.map((c) => (
        <div key={c.subcategory} className="rounded-xl bg-amber-100 px-3 py-2 text-sm text-amber-900">
          <b>{settings.subcategories[c.subcategory]?.label ?? label(c.subcategory)}</b> is running low on search areas
          ({c.tier1_active} of {c.tier1_total} tier-1 cells left). Tier 2 starts automatically when they run out.
        </div>
      ))}
    </div>
  )
}
