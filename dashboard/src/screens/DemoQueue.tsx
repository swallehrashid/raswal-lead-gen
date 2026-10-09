import { strToU8, zipSync } from 'fflate'
import { useState } from 'react'
import { fetchFileBlob, FileImg } from '../components/FileImg'
import { LeadSheet } from '../components/LeadSheet'
import { Badge, Button, Card, CopyButton, Empty, inputCls, Spinner, useToast } from '../components/ui'
import { useApp, useData } from '../context'
import type { Lead, Track } from '../data/types'
import { demoSent, setDemoLink } from '../lib/actions'
import { niceTime } from '../lib/format'
import { buildLeadPack } from '../lib/leadpack'
import { waPhoneLink } from '../lib/phone'
import { todayIn } from '../lib/workdays'

export function DemoQueue() {
  const { api, settings } = useApp()
  const [open, setOpen] = useState<string | null>(null)
  const { data } = useData(async () => Promise.all([api.leads({ statuses: ['demo_queued'], limit: 500 }), api.leads({ statuses: ['demo_sent', 'negotiating', 'won'], limit: 500 })]), [api])
  if (!data) return <Spinner />
  const tz = settings.calendar.timezone
  const today = api.today()
  const [queued, done] = data
  const sentToday = (t: Track) => done.filter((l) => l.demo_type === t && l.demo_sent_at && todayIn(tz, new Date(l.demo_sent_at)) === today).length
  const cap = settings.demo_cap ?? { web: 3, content: 3 }
  const order = [...queued].sort((a, b) => (a.demo_queued_at ?? '').localeCompare(b.demo_queued_at ?? ''))
  const slots: Record<Track, number> = { web: Math.max(0, cap.web - sentToday('web')), content: Math.max(0, cap.content - sentToday('content')) }
  const holding = settings.quick_replies.find((q) => q.key === 'holding')?.text ?? "Thanks! I'll have it ready for you tomorrow morning."
  return (
    <div className="space-y-3">
      <h1 className="text-xl font-extrabold text-navy">Demo queue</h1>
      <Card className="flex flex-wrap gap-2 p-3 text-sm">
        <Badge tone="navy">Website today {sentToday('web')}/{cap.web}</Badge>
        <Badge tone="gold">Content today {sentToday('content')}/{cap.content}</Badge>
        <span className="text-navy/60">A yes before {settings.calendar.same_day_demo_cutoff} gets its link the same day.</span>
      </Card>
      {!order.length && <Empty title="No demos queued">Mark a lead interested from the Inbox log.</Empty>}
      {order.map((l) => {
        const t = (l.demo_type ?? l.track) as Track
        const today_ = slots[t] > 0
        if (today_) slots[t] -= 1
        return <DemoCard key={l.id} lead={l} today={today_} holding={holding} onOpen={() => setOpen(l.id)} />
      })}
      <LeadSheet leadId={open} onClose={() => setOpen(null)} />
    </div>
  )
}

function DemoCard({ lead, today, holding, onOpen }: { lead: Lead; today: boolean; holding: string; onOpen: () => void }) {
  const { act, api, settings } = useApp()
  const toast = useToast()
  const [link, setLink] = useState(lead.demo_link ?? '')
  const brand = lead.brand ?? {}
  const pack = async () => {
    const [logo, hero, teaser] = await Promise.all([api.fileUrl(brand.logo_path), api.fileUrl(brand.hero_path), api.fileUrl(lead.teaser_path)])
    return buildLeadPack(lead, { logo, hero, teaser })
  }
  const copyJson = async () => {
    await navigator.clipboard.writeText(JSON.stringify(await pack(), null, 2))
    toast('Lead pack JSON copied')
  }
  const downloadZip = async () => {
    const p = await pack()
    const files: Record<string, Uint8Array> = { 'lead-pack.json': strToU8(JSON.stringify({ ...p, brand: { ...p.brand, logo_url: brand.logo_path ? 'logo.png' : p.brand.logo_url, hero_image_url: brand.hero_path ? 'hero.jpg' : p.brand.hero_image_url } }, null, 2)) }
    for (const [name, path] of [['logo.png', brand.logo_path], ['hero.jpg', brand.hero_path], ['teaser.jpg', lead.teaser_path]] as const) {
      const b = await fetchFileBlob(api, path ?? null)
      if (b) files[name] = new Uint8Array(await b.arrayBuffer())
    }
    const zip = zipSync(files, { level: 0 })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([zip as BlobPart], { type: 'application/zip' }))
    a.download = `${lead.slug ?? lead.id}-lead-pack.zip`
    a.click()
    URL.revokeObjectURL(a.href)
  }
  const markSent = async () => {
    if (!/^https?:\/\//.test(link.trim())) return toast('Paste the demo link first', 'err')
    if (link.trim() !== lead.demo_link) await act(lead, setDemoLink(link))
    await act({ ...lead, demo_link: link.trim() }, demoSent(api.now(), api.today(), settings.calendar, settings.pause_list), 'Demo sent; follow-ups scheduled')
  }
  return (
    <Card className="space-y-3 p-4">
      <div className="flex items-start gap-3">
        <FileImg path={lead.teaser_path} alt="" className="h-20 w-16 shrink-0 rounded-lg" />
        <div className="min-w-0 flex-1">
          <button onClick={onOpen} className="text-left text-lg font-bold text-navy hover:underline">{lead.business.display_name}</button>
          <div className="flex flex-wrap items-center gap-1 text-xs">
            <Badge tone={lead.demo_type === 'content' ? 'gold' : 'navy'}>{lead.demo_type === 'content' ? 'Content demo' : 'Website demo'}</Badge>
            <span className="text-navy/50">yes at {niceTime(lead.demo_queued_at)}</span>
            {today ? <Badge tone="green">today</Badge> : <Badge tone="amber">tomorrow</Badge>}
          </div>
        </div>
      </div>
      {!today && (
        <div className="flex items-center justify-between gap-2 rounded-xl bg-amber-50 p-2 text-sm">
          <span className="text-amber-900">Over today's cap. Holding reply: “{holding}”</span>
          <CopyButton size="sm" text={holding} />
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        <Button size="sm" onClick={copyJson}>Copy lead pack JSON</Button>
        <Button size="sm" onClick={downloadZip}>Download ZIP</Button>
        {lead.business.phone_e164 && <a href={waPhoneLink(lead.business.phone_e164)} target="_blank" rel="noreferrer"><Button size="sm" variant="wa">Open chat</Button></a>}
      </div>
      <div className="flex gap-2">
        <input className={inputCls} placeholder={`https://${lead.slug}.raswaltechsolutions.com`} value={link} onChange={(e) => setLink(e.target.value)} />
        {link && <CopyButton size="sm" text={link} label="Copy" />}
      </div>
      <Button variant="gold" className="w-full" onClick={markSent}>Mark demo sent</Button>
    </Card>
  )
}
