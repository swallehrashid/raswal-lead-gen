"""Prompt building, one Gemini call per finalist, validation, one retry, fallback (brief §12)."""

from __future__ import annotations

import json
import logging
import time

from pydantic import ValidationError

from pipeline.budget import BudgetExhausted
from pipeline.facts import sort_facts
from pipeline.llm import GeminiOutput, LlmUnavailable, RateLimited
from pipeline.models import Candidate, Fact, Variant
from pipeline.score import score_candidate
from pipeline.validate import (
    LeadContext,
    fallback_variants,
    is_swahili,
    review_fact_to_fact,
    swahili_flags,
    validate_pair,
    validate_poster_line,
    validate_review_fact,
    validate_variant,
)

log = logging.getLogger(__name__)

RATE_LIMIT_RETRIES = 3


def system_prompt(cfg) -> str:
    m = cfg.messaging
    examples = "\n\n".join(m.examples)
    return f"""You write short, warm WhatsApp first messages for Swalleh Rashid of Raswal Tech Solutions, a small
web and content studio in Nairobi. Each message is the caption on a preview image of the business's own
website (website track) or sample posts in their colours (content track). You also extract review themes.

STRUCTURE (one paragraph, then the sign-off on its own line):
1. Greeting to the business (never guess a person's name; the number may belong to a receptionist).
2. One specific observation using 1-2 of the provided facts, strongest first. Make it read like a person
   noticed it, not like an audit report. Do not write "I noticed you need".
3. Bridge to the image.
4. ONE low-friction question.
5. The sign-off exactly: {m.signoff}

HARD RULES (a message breaking any rule is rejected):
- {m.length['min']}-{m.length['max']} characters in total, including the sign-off.
- Include the business name exactly as given.
- Only claim what the cited facts say. Every number you write must appear in a fact you cite.
  No prices, units, years in business, awards, staff counts or anything not in the facts.
- No links or URLs. The only domain you may mention is the business's own domain, if a fact names it.
- No "KES", "Ksh" or amounts. No discounts. No urgency. No hype words.
- At most {m.max_emoji} emoji. No "Dear Sir/Madam".
- Never mention a reviewer's name. Never copy {m.review_copy_max_words + 1} or more words in a row from a review.
- Swahili: only a light touch where asked ("Habari", "Asante", "Karibu"). No Sheng.
- used_fact_ids lists the ids of every fact the message relies on, opening fact first.

REVIEW THEMES: from the numbered reviews, return up to 3 themes. paraphrase is at most 12 words, in your
own words, about what the reviewer(s) said, written to the business (e.g. "A reviewer mentioned how
quickly you arranged a viewing."). Say "several" only if 2+ reviews say it. No names, no numbers.
Negative themes: set addressable_by to "website" or "content" only if that would plausibly fix it,
else "none". Review themes get ids R1, R2, R3 in the order you list them and may be cited.

POSTER LINES: 3 short lines (max 8 words each) for social posters in their branding. Only generic
category copy (e.g. "Book a viewing on WhatsApp") or something from the facts or review themes.
No prices, no numbers unless in a fact, no invented claims.

EXAMPLES of good messages (fictional businesses):

{examples}
"""


def user_prompt(c: Candidate, cfg, *, opening: list[str], swahili: list[bool], errors: list[str] | None = None) -> str:
    sub = cfg.subcategories[c.subcategory]
    m = cfg.messaging
    track = c.track or "web"
    facts = [{"id": f.id, "strength": f.strength, "text": f.text} for f in c.facts_for(track)]
    reviews = [{"index": r.index, "rating": r.rating, "text": r.text} for r in c.reviews if r.text]
    bridge = m.bridges[track].format(business=c.display_name, business_possessive=_poss(c.display_name))
    greet = [m.greetings["swahili" if sw else "english"].format(business=c.display_name) for sw in swahili]
    lines = [
        f"Business name (use exactly): {c.display_name}",
        f"Category: {sub.label}",
        f"Area: {c.area}",
        f"Track: {track} ({'website preview' if track == 'web' else 'sample social posts'})",
        "",
        "FACTS (cite by id):",
        json.dumps(facts, ensure_ascii=False, indent=1),
        "",
        "REVIEWS (numbered; do not quote, do not name reviewers):",
        json.dumps(reviews, ensure_ascii=False, indent=1),
        "",
        f"Bridge to the image (adapt lightly): {bridge}",
        f"Question options: {' / '.join(m.questions[track])}",
        "",
        f"Variant A: open with fact {opening[0]}. Greeting like: {greet[0]}"
        + (" (a light Swahili touch is welcome)" if swahili[0] else " (English)"),
        f"Variant B: open with fact {opening[1]}. Greeting like: {greet[1]}"
        + (" (a light Swahili touch is welcome)" if swahili[1] else " (English)"),
        "The two variants must open with different facts and should read differently.",
    ]
    if errors:
        lines += ["", "Your previous answer was rejected for these reasons. Fix every one:"] + [f"- {e}" for e in errors]
    return "\n".join(lines)


def _poss(name: str) -> str:
    return f"{name}'" if name.endswith("s") else f"{name}'s"


def _openers(c: Candidate) -> list[str]:
    facts = c.facts_for(c.track or "web")
    if not facts:
        return ["", ""]
    return [facts[0].id, facts[1].id if len(facts) > 1 else facts[0].id]


class Drafter:
    def __init__(self, cfg, llm, budget, *, sleep=time.sleep):
        self.cfg, self.llm, self.budget, self.sleep = cfg, llm, budget, sleep
        self.stats = {"llm_calls": 0, "llm_ok": 0, "fallback": 0, "retries": 0}

    # -- LLM call with budget + per-minute retries
    def _call(self, c: Candidate, prompt: str, context: dict) -> dict:
        if self.llm is None:
            raise LlmUnavailable("--no-llm")
        for attempt in range(RATE_LIMIT_RETRIES):
            try:
                self.budget.spend("gemini")
            except BudgetExhausted as e:
                raise LlmUnavailable(str(e)) from e
            self.stats["llm_calls"] += 1
            try:
                return self.llm.generate_json(system_prompt(self.cfg), prompt, GeminiOutput, context=context)
            except RateLimited as e:
                log.info("Gemini rate limited (attempt %d): %s", attempt + 1, e)
                self.sleep(15 * (attempt + 1))
        raise LlmUnavailable("Gemini rate limit persisted")

    def _context(self, c: Candidate, opening, swahili) -> dict:
        m = self.cfg.messaging
        track = c.track or "web"
        return {"place_id": c.place_id, "business": c.display_name, "track": track, "area": c.area,
                "subcategory": c.subcategory,
                "facts": [f.to_dict() for f in c.facts_for(track)],
                "reviews": [{"index": r.index, "rating": r.rating, "text": r.text} for r in c.reviews if r.text],
                "opening": opening, "swahili": swahili, "signoff": m.signoff,
                "bridge": m.bridges[track].format(business=c.display_name, business_possessive=_poss(c.display_name)),
                "questions": m.questions[track],
                "greetings": m.greetings,
                "generic_poster_lines": self.cfg.subcategories[c.subcategory].generic_poster_lines}

    def _apply_review_facts(self, c: Candidate, out: GeminiOutput) -> None:
        ctx = LeadContext.from_candidate(c)
        n_reviews = len([r for r in c.reviews if r.text])
        kept: list[Fact] = []
        c.review_facts = []
        for i, rf in enumerate(out.review_facts[:3], start=1):
            d = rf.model_dump()
            errs = validate_review_fact(d, ctx, self.cfg, n_reviews)
            d["id"], d["errors"] = f"R{i}", errs
            c.review_facts.append(d)
            if errs:
                continue
            if f := review_fact_to_fact(d, f"R{i}", c.track or "web", self.cfg):
                kept.append(f)
        c.facts = sort_facts([f for f in c.facts if f.source != "llm"] + kept, self.cfg)

    def draft(self, c: Candidate) -> None:
        """Fill c.variants (2), c.poster_lines, c.variant_source; may add review facts."""
        cfg = self.cfg
        swahili = swahili_flags(c.place_id, cfg.messaging.swahili_touch_rate)
        opening = _openers(c)
        errors: list[str] | None = None
        llm_variants: list[Variant | None] = [None, None]
        out: GeminiOutput | None = None
        for attempt in range(2):                                 # first try + one retry with errors
            try:
                raw = self._call(c, user_prompt(c, cfg, opening=opening, swahili=swahili, errors=errors),
                                 {**self._context(c, opening, swahili), "attempt": attempt, "errors": errors})
                out = GeminiOutput.model_validate(raw)
            except LlmUnavailable as e:
                log.debug("LLM unavailable for %s: %s", c.name, e)
                break
            except (ValidationError, ValueError, TypeError) as e:
                errors = [f"the JSON did not match the schema: {str(e)[:200]}"]
                self.stats["retries"] += attempt == 0
                continue
            self._apply_review_facts(c, out)     # each answer's variants cite its own R1..R3
            ctx = LeadContext.from_candidate(c)
            errors = []
            cand_variants = []
            for i, v in enumerate(out.variants[:2]):
                errs = validate_variant(v.message.strip(), v.used_fact_ids, ctx, cfg)
                var = Variant(v.message.strip(), v.used_fact_ids, "llm", is_swahili(v.message), errs)
                cand_variants.append(var)
                if errs:
                    errors += [f"variant {'AB'[i]}: {e}" for e in errs]
                elif llm_variants[i] is None:
                    llm_variants[i] = var
            if len(out.variants) < 2:
                errors.append("return exactly two variants")
            if len(cand_variants) == 2 and not errors:
                errors += validate_pair(cand_variants, ctx)
                if errors:
                    llm_variants[1] = None
            if not errors:
                break
            self.stats["retries"] += attempt == 0
        ctx = LeadContext.from_candidate(c)
        for i, v in enumerate(llm_variants):        # a variant kept from the first answer must still hold
            if v is not None and validate_variant(v.message, v.used_fact_ids, ctx, cfg):
                llm_variants[i] = None
        ordered = c.facts_for(c.track or "web")
        fb = fallback_variants(ctx, cfg, c.place_id, ordered) if any(v is None for v in llm_variants) else [None, None]
        c.variants = [llm_variants[i] or fb[i] for i in range(2) if (llm_variants[i] or fb[i]) is not None]
        if len(c.variants) == 2 and c.variants[0].source != c.variants[1].source:
            # mixed: make sure the pair still opens with different facts
            if validate_pair(c.variants, ctx):
                c.variants = fb
        c.variant_source = c.variants[0].source if c.variants else None
        self.stats["llm_ok" if c.variant_source == "llm" else "fallback"] += 1
        lines = [ln.strip() for ln in (out.poster_lines if out else []) if validate_poster_line(ln.strip(), ctx)]
        generic = cfg.subcategories[c.subcategory].generic_poster_lines
        c.poster_lines = (lines + [g for g in generic if g not in lines])[:3]
        for v in c.variants:
            if v.errors:
                log.warning("%s: variant still has validator errors: %s", c.name, v.errors)


def make_draft_finalizer(cfg, drafter: Drafter, now):
    """For select(): draft each accepted candidate; reject it if it still has no strong fact."""

    def finalize(c: Candidate) -> bool:
        track = c.track or "web"
        has_strong = any(f.strength == "strong" for f in c.facts_for(track))
        if not has_strong and (drafter.llm is None or not any(r.text for r in c.reviews)):
            return False            # only a Gemini review theme could add a strong fact
        drafter.draft(c)
        if not any(f.strength == "strong" for f in c.facts_for(track)):
            return False
        score_candidate(c, cfg, now)        # hook points may have changed
        c.track = track                     # keep the track it was selected for
        return True

    return finalize
