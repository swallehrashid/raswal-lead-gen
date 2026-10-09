import { useState } from 'react'
import { useApp } from '../context'
import type { Lead, SocialState } from '../data/types'
import { approve, setSocialState, skip, SKIP_REASONS, unapprove } from '../lib/actions'
import { label } from '../lib/format'
import { FileImg } from './FileImg'
import { CharCount, FactList, LeadHeader, ScoreChips, SocialLinks } from './LeadBits'
import { Badge, Button, Card, cx } from './ui'

const SOCIAL: SocialState[] = ['none', 'stale', 'active', 'polished']

export function ReviewCard({ lead }: { lead: Lead }) {
  const { act, api, settings } = useApp()
  const [variant, setVariant] = useState(lead.chosen_variant ?? 0)
  const [text, setText] = useState(lead.message_final ?? lead.message_variants[0]?.message ?? '')
  const [skipping, setSkipping] = useState(false)
  const len = settings.messaging?.length ?? { min: 280, max: 480 }
  const approved = lead.status === 'approved'
  const done = lead.status !== 'shortlisted' && lead.status !== 'reserve' && !approved
  const bonus = lead.social_state ? settings.scoring?.social_state_bonus?.[lead.social_state] ?? 0 : 0
  const polished = lead.social_state && settings.scoring?.social_state_skip?.includes(lead.social_state)

  if (approved || done)
    return (
      <Card className="flex items-center justify-between gap-3 p-3">
        <div className="min-w-0">
          <div className="truncate font-semibold text-navy">{lead.business.display_name}</div>
          <div className="text-xs text-navy/50">{lead.area} · {lead.track === 'web' ? 'Website' : 'Content'} #{lead.rank}</div>
        </div>
        {approved ? (
          <div className="flex items-center gap-2"><Badge tone="gold">Approved ✓</Badge>
            <Button size="sm" variant="ghost" onClick={() => act(lead, unapprove(), 'Moved back to review')}>Undo</Button></div>
        ) : <Badge>{label(lead.status)}{lead.skip_reason ? ` · ${label(lead.skip_reason)}` : ''}</Badge>}
      </Card>
    )

  return (
    <Card className="space-y-3 p-4">
      <LeadHeader lead={lead} showStatus={lead.status === 'reserve'} />
      <ScoreChips lead={lead} />
      <div className="grid grid-cols-2 gap-2">
        <figure>
          <FileImg path={lead.business.audit?.current_screenshot_path} alt="Their current site" className="aspect-[1/2] max-h-72 w-full rounded-xl object-top" placeholder={lead.site_status === 'none' ? 'No website' : 'No screenshot'} />
          <figcaption className="mt-1 text-center text-xs text-navy/50">Their site now</figcaption>
        </figure>
        <figure>
          <FileImg path={lead.teaser_path} alt="Teaser" className="aspect-[4/5] max-h-72 w-full rounded-xl" placeholder="No teaser" />
          <figcaption className="mt-1 text-center text-xs text-navy/50">Teaser</figcaption>
        </figure>
      </div>
      <FactList lead={lead} />
      {lead.track === 'content' && (
        <div className="space-y-2 rounded-xl bg-gold-100/60 p-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-navy/50">Check their socials</div>
          <SocialLinks lead={lead} />
          <div className="flex flex-wrap gap-1">
            {SOCIAL.map((s) => (
              <button key={s} onClick={() => act(lead, setSocialState(s))}
                className={cx('rounded-lg px-3 py-1 text-sm font-semibold', lead.social_state === s ? 'bg-navy text-white' : 'bg-white text-navy/70')}>{s}</button>
            ))}
          </div>
          {bonus > 0 && <div className="text-xs text-green-800">+{bonus} on the displayed score ({lead.social_state})</div>}
          {polished && <div className="text-xs font-semibold text-red-700">Polished socials: they probably have an agency. Skip it.</div>}
        </div>
      )}
      <div className="space-y-2">
        <div className="flex gap-2">
          {lead.message_variants.map((v, i) => (
            <label key={i} className={cx('flex flex-1 cursor-pointer items-center gap-2 rounded-xl border px-3 py-2 text-sm font-semibold',
              variant === i ? 'border-navy bg-navy/5' : 'border-navy/10')}>
              <input type="radio" checked={variant === i} onChange={() => { setVariant(i); setText(v.message) }} />
              Variant {'AB'[i]}
              <span className="ml-auto text-[11px] font-normal text-navy/50">{v.source}{v.swahili_touch ? ' · sw' : ''}</span>
            </label>
          ))}
        </div>
        <textarea className="min-h-40 w-full rounded-xl border border-navy/15 bg-white p-3 text-[15px] leading-relaxed outline-none focus:border-cyan"
          value={text} onChange={(e) => setText(e.target.value)} />
        <div className="flex items-center justify-between"><CharCount text={text} min={len.min} max={len.max} />
          {lead.message_variants[variant] && text !== lead.message_variants[variant].message && <span className="text-xs text-navy/50">edited</span>}</div>
      </div>
      {skipping ? (
        <div className="space-y-2">
          <div className="text-sm font-semibold text-navy">Why skip? (this improves the filters)</div>
          <div className="flex flex-wrap gap-1.5">
            {SKIP_REASONS.map((r) => (
              <Button key={r} size="sm" onClick={() => act(lead, skip(r), 'Skipped')}>{label(r)}</Button>
            ))}
            <Button size="sm" variant="ghost" onClick={() => setSkipping(false)}>Cancel</Button>
          </div>
        </div>
      ) : (
        <div className="flex gap-2">
          <Button variant="primary" className="flex-1" disabled={lead.status === 'reserve'}
            onClick={() => act(lead, approve(lead, variant, text, api.now()), 'Approved')}>Approve</Button>
          <Button className="flex-1" onClick={() => setSkipping(true)}>Skip</Button>
        </div>
      )}
      {lead.status === 'reserve' && <p className="text-xs text-navy/50">Reserve: it's promoted automatically when a lead in this track is skipped or has no WhatsApp.</p>}
    </Card>
  )
}
