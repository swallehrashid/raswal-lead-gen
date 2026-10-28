import { useState } from 'react'
import type { Fact, Lead } from '../data/types'
import { label, SITE_TONE, STATUS_TONE } from '../lib/format'
import { displayPhone } from '../lib/phone'
import { Badge, cx } from './ui'

const ANGLE = { A: 'A · not advertising', B: 'B · advertising', C: 'C · no site' } as const

export function LeadHeader({ lead, showStatus = true }: { lead: Lead; showStatus?: boolean }) {
  const b = lead.business
  return (
    <div className="flex flex-wrap items-start justify-between gap-2">
      <div className="min-w-0">
        <div className="text-lg font-bold leading-tight text-navy">{b.display_name || b.name}</div>
        <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-navy/60">
          <span>{lead.area}</span>
          {b.rating != null && <span>{b.rating}★ · {b.review_count} reviews</span>}
          {b.phone_e164 && <span>{displayPhone(b.phone_e164)}</span>}
          {b.maps_url && <a className="font-semibold text-cyan underline" href={b.maps_url} target="_blank" rel="noreferrer">Maps</a>}
          {b.website_url && <a className="max-w-[16rem] truncate font-semibold text-cyan underline" href={b.website_url} target="_blank" rel="noreferrer">{b.website_url.replace(/^https?:\/\//, '')}</a>}
        </div>
      </div>
      <div className="flex flex-wrap gap-1">
        {lead.site_status && <Badge tone={SITE_TONE[lead.site_status]}>{label(lead.site_status)}</Badge>}
        <Badge tone={lead.subcategory === 'land_developers' ? 'green' : 'navy'}>{lead.subcategory === 'land_developers' ? 'Land' : lead.subcategory === 'property_agency' ? 'Agency' : label(lead.subcategory)} #{lead.rank}</Badge>
        {lead.brand?.angle && <Badge tone={lead.brand.angle === 'B' ? 'gold' : 'cyan'}>{ANGLE[lead.brand.angle]}</Badge>}
        {lead.business.scam_flag && <Badge tone={lead.business.scam_flag === 'hard' ? 'red' : 'amber'}>scam words in reviews</Badge>}
        {showStatus && <Badge tone={STATUS_TONE[lead.status]}>{label(lead.status)}</Badge>}
      </div>
    </div>
  )
}

export function ScoreChips({ lead }: { lead: Lead }) {
  const ev = lead.evaluation
  if (!ev?.score) return null
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-xs">
      <span className="rounded-lg bg-navy px-2 py-1 font-bold text-white">{Math.round(ev.score)}</span>
      {Object.entries(ev.breakdown).map(([k, v]) => (
        <span key={k} className="rounded-lg bg-navy/5 px-2 py-1 text-navy/70">{k} <b>{Math.round(v)}</b></span>
      ))}
      {lead.business.branch_count > 1 && <Badge tone="cyan">{lead.business.branch_count} branches</Badge>}
      {lead.business.manages_listings > 0 && <Badge tone="cyan">{lead.business.manages_listings} listings</Badge>}
    </div>
  )
}

export function FactList({ lead }: { lead: Lead }) {
  const facts = (lead.evaluation?.facts?.facts ?? []).filter((f) => f.track !== 'upsell')
  const used = new Set(lead.message_variants.flatMap((v) => v.used_fact_ids))
  const [open, setOpen] = useState<string | null>(null)
  if (!facts.length) return null
  return (
    <ul className="space-y-1">
      {facts.map((f: Fact) => (
        <li key={f.id}>
          <button onClick={() => setOpen(open === f.id ? null : f.id)} className="flex w-full items-start gap-2 text-left text-sm">
            <span className={cx('mt-0.5 shrink-0 rounded px-1.5 text-[11px] font-bold', f.strength === 'strong' ? 'bg-gold text-navy' : 'bg-navy/10 text-navy/60')}>{f.id}</span>
            <span className={cx('text-navy/80', used.has(f.id) && 'font-semibold text-navy')}>{f.text}</span>
          </button>
          {open === f.id && (
            <pre className="mt-1 ml-8 overflow-x-auto rounded-lg bg-navy/5 p-2 text-[11px] text-navy/70">
              {f.code} · {f.strength} · {f.source}{'\n'}{JSON.stringify(f.evidence, null, 1)}
            </pre>
          )}
        </li>
      ))}
    </ul>
  )
}

export function AdsLine({ lead }: { lead: Lead }) {
  const b = lead.business
  const q = encodeURIComponent(b.display_name || b.name)
  const url = `https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=KE&q=${q}`
  const status = lead.brand?.ads_override ?? b.ads_status ?? 'unknown'
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span className="font-semibold text-navy">Ads:</span>
      {status === 'active'
        ? <span>running {b.ads_active_count ?? ''} {b.ads_longest_days ? `· longest ${b.ads_longest_days} days` : ''}</span>
        : <span className="text-navy/60">{status === 'none' ? 'none found' : 'not checked'}</span>}
      <a className="font-semibold text-cyan underline" href={url} target="_blank" rel="noreferrer">Ad Library ↗</a>
      {b.scam_terms?.length ? <span className="text-red-700">Review words: {b.scam_terms.join(', ')}</span> : null}
    </div>
  )
}

export function SocialLinks({ lead }: { lead: Lead }) {
  const links = lead.business.audit?.social_links ?? {}
  const entries = Object.entries(links)
  if (!entries.length) return <span className="text-sm text-navy/50">No social links on their site.</span>
  return (
    <div className="flex flex-wrap gap-1.5">
      {entries.map(([k, v]) => (
        <a key={k} href={v} target="_blank" rel="noreferrer" className="rounded-lg bg-cyan-100 px-2.5 py-1 text-sm font-semibold capitalize text-[#155675]">{k} ↗</a>
      ))}
    </div>
  )
}

export function CharCount({ text, min = 380, max = 700 }: { text: string; min?: number; max?: number }) {
  const n = text.length
  const ok = n >= min && n <= max
  return <span className={cx('text-xs font-semibold', ok ? 'text-green-700' : 'text-red-600')}>{n} / {min}–{max}</span>
}
