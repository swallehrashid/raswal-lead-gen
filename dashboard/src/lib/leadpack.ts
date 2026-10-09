import type { Lead } from '../data/types'

/** Lead pack for the web-demo / content-demo repos (brief §15.3). */
export function buildLeadPack(lead: Lead, urls: { logo?: string | null; hero?: string | null; teaser?: string | null } = {}) {
  const b = lead.business
  const facts = lead.evaluation?.facts?.facts ?? []
  const used = new Set(lead.used_fact_ids)
  const reviewThemes = (lead.evaluation?.facts?.review_facts ?? [])
    .filter((r) => !(r.errors as unknown[] | undefined)?.length)
    .map((r) => ({ theme: String(r.theme ?? ''), paraphrase: String(r.paraphrase ?? '') }))
  const slug = lead.slug ?? ''
  return {
    lead_id: lead.id,
    track: lead.demo_type ?? lead.track,
    subcategory: lead.subcategory,
    template_id: lead.subcategory,
    business: {
      name: b.display_name || b.name, slug, area: lead.area ?? b.area ?? '', address: b.address ?? '',
      phone_e164: b.phone_e164 ?? '', website_url: b.website_url ?? '', maps_url: b.maps_url ?? '',
    },
    brand: {
      logo_url: urls.logo ?? b.audit?.logo_url ?? null,
      primary: lead.brand?.primary ?? b.audit?.colours?.primary ?? null,
      accent: lead.brand?.accent ?? b.audit?.colours?.accent ?? null,
      hero_image_url: urls.hero ?? b.audit?.hero_image_url ?? null,
    },
    facts: facts.filter((f) => used.size === 0 || used.has(f.id) || f.strength === 'strong').map((f) => ({ code: f.code, text: f.text })),
    review_themes: reviewThemes,
    poster_lines: lead.poster_lines ?? [],
    preview_domain: `${slug}.raswaltechsolutions.com`,
  }
}

export type LeadPack = ReturnType<typeof buildLeadPack>
