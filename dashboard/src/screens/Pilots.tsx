import { useState } from 'react'
import { LeadSheet } from '../components/LeadSheet'
import { Badge, Button, Card, CopyButton, Empty, Field, inputCls, Spinner, useToast } from '../components/ui'
import { useApp, useData } from '../context'
import type { Lead, Pilot, PilotDay, PilotRoute } from '../data/types'
import { pilotLive, pilotReview, won as wonAction, markLost } from '../lib/actions'
import { costPerChat, dailyUpdate, dayReport, fmt, overStopRule, stageOf, totals } from '../lib/pilot'
import { waPhoneLink } from '../lib/phone'

const ROUTES: Array<[PilotRoute, string]> = [['A', 'A · already advertises (their ad account)'], ['B', 'B · has a Page (our ad account)'], ['C', 'C · no Page (create it with them)'], ['backup', 'Backup · wa.me link']]
const OFFER_KEYS = ['project', 'price_cash', 'deposit', 'months', 'title_label', 'visit_day']

export function Pilots() {
  const { api } = useApp()
  const [open, setOpen] = useState<string | null>(null)
  const { data, reload } = useData(async () => {
    const pilots = await api.pilots()
    const leads = await Promise.all(pilots.map((p) => api.lead(p.lead_id)))
    return pilots.map((p, i) => ({ pilot: p, lead: leads[i] })).filter((x): x is { pilot: Pilot; lead: Lead } => !!x.lead)
  }, [api])
  if (!data) return <Spinner />
  return (
    <div className="space-y-3">
      <h1 className="text-xl font-extrabold text-navy">Pilots</h1>
      {!data.length && <Empty title="No pilots yet">When a client says yes to their plan, open the lead and tap “Start the pilot”.</Empty>}
      {data.map(({ pilot, lead }) => <PilotCard key={pilot.id} pilot={pilot} lead={lead} onChanged={reload} onOpen={() => setOpen(lead.id)} />)}
      <LeadSheet leadId={open} onClose={() => setOpen(null)} />
    </div>
  )
}

function PilotCard({ pilot, lead, onChanged, onOpen }: { pilot: Pilot; lead: Lead; onChanged: () => void; onOpen: () => void }) {
  const { api, act, settings } = useApp()
  const toast = useToast()
  const cfg = settings.pilot
  const now = api.now()
  const { data: days, reload } = useData(() => api.pilotDays(pilot.id), [api, pilot.id])
  const offer = (pilot.offer ?? {}) as Record<string, string>
  const hasOffer = OFFER_KEYS.every((k) => offer[k])
  const stage = stageOf(pilot, hasOffer)
  const noun = lead.subcategory === 'land_developers' ? 'site visit' : 'viewing'
  const name = lead.business.display_name || lead.business.name
  const save = async (patch: Partial<Pilot>) => { await api.savePilot({ ...patch, id: pilot.id, lead_id: pilot.lead_id }); onChanged() }
  const [mpesa, setMpesa] = useState(pilot.mpesa_ref ?? '')
  const [draft, setDraft] = useState<Record<string, string>>({})
  const nextDay = Math.min(14, 1 + Math.max(0, ...(days ?? []).map((d) => d.day)))
  const [form, setForm] = useState({ spend: '', reach: '', chats: '', serious: '', visits: '', note: '' })
  const [winner, setWinner] = useState(pilot.winner_ad ?? '')
  const [price, setPrice] = useState(String(pilot.plan_price_kes ?? cfg?.pricing.engine_intro_kes ?? 10000))
  const t = totals(days ?? [])
  const cpc = costPerChat(t.spend, t.chats)
  const over = cfg && overStopRule(days ?? [], cfg)
  const check = (k: keyof Pilot, label_: string, extra?: React.ReactNode) => (
    <label className="flex flex-wrap items-center gap-2 text-sm">
      <input type="checkbox" checked={!!pilot[k]} onChange={(e) => save({ [k]: e.target.checked ? now : null } as Partial<Pilot>)} />
      <span className={pilot[k] ? 'font-semibold text-navy' : 'text-navy/70'}>{label_}</span>{extra}
    </label>
  )
  const addDay = async () => {
    const n = (s: string) => (s === '' ? null : Number(s))
    const d: PilotDay = { pilot_id: pilot.id, day: nextDay, date: api.today(), spend_kes: n(form.spend), reach: n(form.reach), chats: n(form.chats), serious: n(form.serious), visits: n(form.visits), ad_breakdown: null, note: form.note || null }
    await api.savePilotDay(d)
    setForm({ spend: '', reach: '', chats: '', serious: '', visits: '', note: '' })
    reload()
    toast(`Day ${d.day} saved`)
  }
  const goLive = async () => {
    const ends = new Date(Date.parse(now) + (cfg?.pilot_days ?? 7) * 86400_000).toISOString()
    await save({ live_at: now, ends_at: ends })
    await act(lead, pilotLive(), 'Pilot is live')
  }
  const todayRow = (days ?? []).find((d) => d.day === Math.max(0, ...(days ?? []).map((x) => x.day)))
  const update = todayRow ? dailyUpdate(name, days!, todayRow, noun, pilot.winner_ad, over ? 'We are changing the creative today' : 'Tomorrow we keep pushing the best ad') : ''
  const report = cfg ? dayReport(name, days ?? [], noun, pilot.winner_ad, cfg) : ''
  return (
    <Card className="space-y-3 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <button onClick={onOpen} className="text-left text-lg font-bold text-navy hover:underline">{name}</button>
          <div className="text-xs text-navy/50">{lead.area} · {lead.subcategory === 'land_developers' ? 'Land' : 'Agency'}</div>
        </div>
        <div className="flex gap-1"><Badge tone={stage === 'Live' ? 'green' : stage === 'Converted' ? 'green' : stage === 'Declined' ? 'red' : 'amber'}>{stage}</Badge>
          {lead.business.phone_e164 && <a href={waPhoneLink(lead.business.phone_e164)} target="_blank" rel="noreferrer"><Button size="sm" variant="wa">Chat</Button></a>}</div>
      </div>

      <section className="space-y-2 rounded-xl bg-navy/5 p-3">
        <div className="text-xs font-bold uppercase tracking-wide text-navy/50">Onboarding (24-hour clock)</div>
        <select className={inputCls} value={pilot.route ?? ''} onChange={(e) => save({ route: (e.target.value || null) as PilotRoute | null })}>
          <option value="">Route: pick after the 5 questions</option>{ROUTES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
        <details className="text-sm"><summary className="cursor-pointer font-semibold text-navy">Offer form {hasOffer ? '✓' : '(not complete)'}</summary>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {OFFER_KEYS.map((k) => <Field key={k} label={k.replaceAll('_', ' ')}><input className={inputCls} defaultValue={offer[k] ?? ''} onChange={(e) => setDraft({ ...draft, [k]: e.target.value })} /></Field>)}
          </div>
          <Button size="sm" className="mt-2" onClick={() => save({ offer: { ...offer, ...draft } })}>Save offer</Button>
          <p className="mt-1 text-xs text-navy/50">Then run <code>python -m pipeline generate --lead-id {lead.id.slice(0, 8)}… --final --offer offer.json</code> on your PC for the final videos and Ads Manager kit.</p>
        </details>
        {check('access_granted_at', 'Access granted + WhatsApp linked to their Page')}
        {check('paid_at', `KES ${fmt(pilot.budget_kes)} received (M-Pesa)`, <input className={`${inputCls} w-40`} placeholder="M-Pesa ref" value={mpesa} onChange={(e) => setMpesa(e.target.value)} onBlur={() => mpesa !== (pilot.mpesa_ref ?? '') && save({ mpesa_ref: mpesa || null })} />)}
        {check('submitted_at', 'Campaign built and submitted in Ads Manager')}
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="gold" disabled={!!pilot.live_at || !pilot.submitted_at} onClick={goLive}>{pilot.live_at ? 'Live ✓' : 'Mark live (starts the 7 days)'}</Button>
          <span className="text-xs text-navy/50">Greeting + quick replies set up on their WhatsApp (call script in docs/pilot-kit/04).</span>
        </div>
      </section>

      {pilot.live_at && (
        <section className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="text-sm"><b>KES {fmt(t.spend)}</b> spent · <b>{t.chats}</b> chats · <b>{cpc ? `KES ${cpc}` : '—'}</b> per chat · <b>{t.visits}</b> {noun}s</div>
            {over && <Badge tone="red">Over KES {cfg?.stop_rule.max_cost_per_chat_kes}/chat: change the creative or audience today</Badge>}
          </div>
          <table className="w-full text-xs"><thead><tr className="text-left text-navy/50"><th>Day</th><th>Spend</th><th>Reach</th><th>Chats</th><th>Serious</th><th>{noun}s</th><th>KES/chat</th></tr></thead>
            <tbody>{(days ?? []).map((d) => { const c = costPerChat(d.spend_kes ?? 0, d.chats ?? 0); return (
              <tr key={d.day} className="border-t border-navy/5"><td>{d.day}</td><td>{fmt(d.spend_kes ?? 0)}</td><td>{fmt(d.reach ?? 0)}</td><td>{d.chats ?? 0}</td><td>{d.serious ?? 0}</td><td>{d.visits ?? 0}</td><td className={c && cfg && c > cfg.stop_rule.max_cost_per_chat_kes ? 'font-bold text-red-700' : ''}>{c ?? '—'}</td></tr>) })}</tbody></table>
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
            {(['spend', 'reach', 'chats', 'serious', 'visits'] as const).map((k) => <Field key={k} label={`Day ${nextDay} ${k}`}><input className={inputCls} inputMode="numeric" value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value.replace(/\D/g, '') })} /></Field>)}
            <div className="flex items-end"><Button variant="primary" className="w-full" onClick={addDay}>Save day</Button></div>
          </div>
          <Field label="Winning ad so far"><input className={inputCls} value={winner} placeholder="e.g. The Offer" onChange={(e) => setWinner(e.target.value)} onBlur={() => winner !== (pilot.winner_ad ?? '') && save({ winner_ad: winner || null })} /></Field>
          <div className="flex flex-wrap gap-2">
            {update && <CopyButton size="sm" text={update} label="Copy daily update" />}
            {report && (days ?? []).length > 0 && <CopyButton size="sm" text={report} label="Copy day-7 report" />}
            <Button size="sm" onClick={() => act(lead, pilotReview(), 'Moved to review')}>Day 7 done</Button>
          </div>
          {update && <pre className="whitespace-pre-wrap rounded-xl bg-navy/5 p-2 text-xs text-navy/80">{update}</pre>}
        </section>
      )}

      {pilot.live_at && (
        <section className="flex flex-wrap items-end gap-2 border-t border-navy/10 pt-3">
          <Field label="Enquiry Engine KES/month"><input className={`${inputCls} w-32`} inputMode="numeric" value={price} onChange={(e) => setPrice(e.target.value.replace(/\D/g, ''))} /></Field>
          <Button variant="gold" onClick={async () => { await save({ outcome: 'converted', plan_price_kes: Number(price) }); await act(lead, wonAction(Number(price) || null, now), 'Converted 🎉') }}>Converted</Button>
          <Button onClick={() => save({ outcome: 'extended' })}>Extend</Button>
          <Button variant="danger" onClick={async () => { await save({ outcome: 'declined' }); await act(lead, markLost('not_a_fit', now), 'Declined') }}>Declined</Button>
        </section>
      )}
    </Card>
  )
}
