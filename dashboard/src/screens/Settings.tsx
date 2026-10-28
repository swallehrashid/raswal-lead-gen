import { useState } from 'react'
import { Button, Card, Field, inputCls, Spinner, useToast } from '../components/ui'
import { useApp, useData } from '../context'
import type { QuickReply } from '../data/types'
import { label, niceDate } from '../lib/format'
import { displayPhone, normalizeKe } from '../lib/phone'

export function SettingsScreen() {
  const { api, settings, reloadSettings } = useApp()
  const toast = useToast()
  const save = async (key: string, value: unknown) => {
    await api.saveSetting(key, value)
    await reloadSettings()
    toast('Saved')
  }
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-extrabold text-navy">Settings</h1>
      <SuppressionBox />
      <OutreachBox value={settings.outreach_whatsapp ?? ''} onSave={(v) => save('outreach_whatsapp', v)} />
      <NumbersBox title="Daily mix (leads per day)" value={settings.daily_mix ?? {}} onSave={(v) => save('daily_mix', v)} max={40}
        labels={{ land_developers: 'Land developers', property_agency: 'Property agencies' }}
        hint="Used by the next nightly run. Start 20 land + 10 agencies; adjust weekly from the reply rates in Stats." />
      <NumbersBox title="Plans per day" value={{ pilot: 5, ...(settings.demo_cap ?? {}) }} onSave={(v) => save('demo_cap', v)} labels={{ pilot: 'Pilot plans', web: 'Website demos' }} />
      <PauseBox />
      <QuickRepliesBox items={settings.quick_replies} onSave={(v) => save('quick_replies', v)} />
      <TemplatesBox items={settings.followup_templates} onSave={(v) => save('followup_templates', v)} />
      <Card className="space-y-2 p-4 text-sm">
        <div className="font-bold text-navy">Account</div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => api.signOut()}>Sign out</Button>
          {api.mode === 'mock' && api.resetMock && <Button variant="danger" onClick={() => { api.resetMock!(); location.reload() }}>Reset mock data</Button>}
        </div>
      </Card>
    </div>
  )
}

function SuppressionBox() {
  const { api } = useApp()
  const toast = useToast()
  const [phone, setPhone] = useState('')
  const [reason, setReason] = useState('client')
  const [note, setNote] = useState('')
  const { data, reload } = useData(() => api.suppression(), [api])
  const add = async () => {
    const e164 = normalizeKe(phone)
    if (!e164) return toast('That doesn\'t look like a Kenyan phone number', 'err')
    await api.addSuppression({ phone_e164: e164, reason, note: note || null })
    setPhone('')
    setNote('')
    reload()
    toast(`${displayPhone(e164)} will never be listed`)
  }
  return (
    <Card className="space-y-3 p-4">
      <div className="font-bold text-navy">Suppression list</div>
      <p className="text-sm text-navy/60">Existing clients, opt-outs and anyone who must never be messaged.</p>
      <div className="grid gap-2 sm:grid-cols-[1fr_10rem_1fr_auto]">
        <input className={inputCls} placeholder="0722 123 456" value={phone} onChange={(e) => setPhone(e.target.value)} />
        <select className={inputCls} value={reason} onChange={(e) => setReason(e.target.value)}>
          {['client', 'manual', 'do_not_contact', 'opted_out'].map((r) => <option key={r} value={r}>{label(r)}</option>)}
        </select>
        <input className={inputCls} placeholder="Note (e.g. Premar)" value={note} onChange={(e) => setNote(e.target.value)} />
        <Button variant="primary" onClick={add}>Add</Button>
      </div>
      {!data ? <Spinner /> : (
        <ul className="divide-y divide-navy/5 text-sm">
          {data.map((s) => (
            <li key={s.phone_e164} className="flex items-center justify-between py-1.5">
              <span><b>{displayPhone(s.phone_e164)}</b> · {label(s.reason)}{s.note ? ` · ${s.note}` : ''} <span className="text-navy/40">{niceDate(s.added_at)}</span></span>
              <Button size="sm" variant="ghost" onClick={async () => { if (confirm('Remove from suppression?')) { await api.removeSuppression(s.phone_e164); reload() } }}>Remove</Button>
            </li>
          ))}
          {!data.length && <li className="py-2 text-navy/50">Empty</li>}
        </ul>
      )}
    </Card>
  )
}

function OutreachBox({ value, onSave }: { value: string; onSave: (v: string) => void }) {
  const [v, setV] = useState(value)
  const digits = v.replace(/\D/g, '')
  return (
    <Card className="space-y-2 p-4">
      <div className="font-bold text-navy">Outreach WhatsApp number</div>
      <p className="text-sm text-navy/60">The number clients message when they tap Start on their plan. International format, digits only.</p>
      <div className="flex flex-wrap items-end gap-2">
        <input className={`${inputCls} w-56`} inputMode="numeric" placeholder="254114129809" value={v} onChange={(e) => setV(e.target.value)} />
        <Button disabled={digits.length < 11 || digits === value} onClick={() => onSave(digits)}>Save</Button>
        {digits && <a className="text-sm font-semibold text-cyan underline" href={`https://wa.me/${digits}`} target="_blank" rel="noreferrer">Test link ↗</a>}
      </div>
    </Card>
  )
}

function NumbersBox({ title, value, onSave, hint, labels, max }: { title: string; value: Record<string, number>; onSave: (v: Record<string, number>) => void; hint?: string; labels?: Record<string, string>; max?: number }) {
  const [v, setV] = useState(value)
  const total = Object.values(v).reduce((a, b) => a + (Number(b) || 0), 0)
  const over = max != null && total > max
  return (
    <Card className="space-y-2 p-4">
      <div className="font-bold text-navy">{title}</div>
      <div className="flex flex-wrap items-end gap-2">
        {Object.keys(v).map((k) => (
          <Field key={k} label={labels?.[k] ?? label(k)}><input type="number" min={0} className={`${inputCls} w-24`} value={v[k]} onChange={(e) => setV({ ...v, [k]: Math.max(0, Number(e.target.value)) })} /></Field>
        ))}
        <Button disabled={over} onClick={() => onSave(v)}>Save</Button>
      </div>
      {max != null && <p className={`text-xs ${over ? 'font-semibold text-red-700' : 'text-navy/50'}`}>Total {total}{over ? ` (max ${max} a day keeps the number safe)` : ` of ${max}`}</p>}
      {hint && <p className="text-xs text-navy/50">{hint}</p>}
    </Card>
  )
}

function PauseBox() {
  const { api, settings, reloadSettings } = useApp()
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [note, setNote] = useState('')
  const list = settings.pause_list ?? []
  const save = async (v: typeof list) => {
    await api.saveSetting('pause_list', v)
    await reloadSettings()
  }
  return (
    <Card className="space-y-2 p-4">
      <div className="font-bold text-navy">Pause (holiday)</div>
      <p className="text-sm text-navy/60">No list is built for paused days, and follow-up dates skip them.</p>
      <div className="flex flex-wrap items-end gap-2">
        <Field label="From"><input type="date" className={inputCls} value={start} onChange={(e) => setStart(e.target.value)} /></Field>
        <Field label="To"><input type="date" className={inputCls} value={end} onChange={(e) => setEnd(e.target.value)} /></Field>
        <Field label="Note"><input className={inputCls} value={note} onChange={(e) => setNote(e.target.value)} /></Field>
        <Button disabled={!start || !end || end < start} onClick={() => { void save([...list, { start, end, note }]); setStart(''); setEnd(''); setNote('') }}>Add</Button>
      </div>
      <ul className="text-sm">
        {list.map((p, i) => (
          <li key={i} className="flex items-center justify-between py-1">{niceDate(p.start)} – {niceDate(p.end)} {p.note}
            <Button size="sm" variant="ghost" onClick={() => save(list.filter((_, j) => j !== i))}>Remove</Button></li>
        ))}
      </ul>
    </Card>
  )
}

function QuickRepliesBox({ items, onSave }: { items: QuickReply[]; onSave: (v: QuickReply[]) => void }) {
  const [v, setV] = useState(items)
  const upd = (i: number, patch: Partial<QuickReply>) => setV(v.map((q, j) => (j === i ? { ...q, ...patch } : q)))
  return (
    <Card className="space-y-3 p-4">
      <div className="font-bold text-navy">Quick replies</div>
      {v.map((q, i) => (
        <div key={i} className="space-y-1 border-t border-navy/5 pt-2 first:border-0 first:pt-0">
          <div className="flex gap-2">
            <input className={inputCls} value={q.label} onChange={(e) => upd(i, { label: e.target.value })} />
            <select className={`${inputCls} w-44`} value={q.action ?? ''} onChange={(e) => upd(i, { action: e.target.value || null })}>
              <option value="">no action</option><option value="lost_has_provider">mark lost</option><option value="snooze">snooze</option><option value="opt_out">opt out</option>
            </select>
            <Button size="sm" variant="ghost" onClick={() => setV(v.filter((_, j) => j !== i))}>✕</Button>
          </div>
          <textarea className={inputCls} rows={2} value={q.text} onChange={(e) => upd(i, { text: e.target.value })} />
        </div>
      ))}
      <div className="flex gap-2">
        <Button size="sm" onClick={() => setV([...v, { key: `custom_${Date.now()}`, label: 'New reply', text: '' }])}>Add reply</Button>
        <Button size="sm" variant="primary" onClick={() => onSave(v)}>Save quick replies</Button>
      </div>
      <p className="text-xs text-navy/50">{'{business}'} is replaced with the business name.</p>
    </Card>
  )
}

function TemplatesBox({ items, onSave }: { items: Record<string, string>; onSave: (v: Record<string, string>) => void }) {
  const [v, setV] = useState(items)
  return (
    <Card className="space-y-3 p-4">
      <div className="font-bold text-navy">Follow-up templates</div>
      {Object.entries(v).map(([k, t]) => (
        <Field key={k} label={label(k)}><textarea className={inputCls} rows={3} value={t} onChange={(e) => setV({ ...v, [k]: e.target.value })} /></Field>
      ))}
      <Button size="sm" variant="primary" onClick={() => onSave(v)}>Save templates</Button>
      <p className="text-xs text-navy/50">{'{business}'} and {'{weekday}'} (day of the first message) are filled in.</p>
    </Card>
  )
}
