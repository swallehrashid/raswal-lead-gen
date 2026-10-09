"""Message validator (brief §12.5), review-fact validator (§11.3) and deterministic fallback.

A variant is rejected if ANY rule fails. Every specific claim must trace to a stored fact.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Any

from pipeline.models import Candidate, Fact, Variant
from pipeline.utils.text import basic_norm, possessive
from pipeline.utils.urls import host

# ---------------------------------------------------------------- patterns

_URL = re.compile(r"(https?://|www\.)\S+", re.I)
_DOMAIN = re.compile(r"\b((?:[a-z0-9-]+\.)+(?:com|co\.ke|ke|net|org|info|biz|africa|io|co|me|site|page|ee|ly))\b", re.I)
_MONEY = [re.compile(r"\b(?:kes|kshs?|ksh)\b", re.I),
          re.compile(r"\b(?:sh|shs)\.?\s?\d", re.I),
          re.compile(r"\d[\d,]*\s?(?:/-|bob\b)", re.I),
          re.compile(r"[$€£]\s?\d"),
          re.compile(r"\b\d+(?:\.\d+)?\s?k\b", re.I)]
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
# Emoji: pictographs, symbols & dingbats. ★/☆ are allowed (used in the rating fact).
_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⭐⭕⬛⬜⤴⤵〰〽]")
_NOT_EMOJI = {"★", "☆", "✓", "✔"}  # ★ ☆ ✓ ✔
_SEVERAL = re.compile(r"\b(several|many|most|all|lots of|plenty of)\b", re.I)


def count_emoji(text: str) -> int:
    """Emoji count; a ZWJ sequence, variation selector or skin tone counts as one."""
    t = re.sub("\u200d[\U0001F000-\U0001FAFF\u2600-\u27BF]", "", text)
    t = re.sub("[\ufe0f\U0001F3FB-\U0001F3FF]", "", t)
    return sum(1 for ch in t if ch not in _NOT_EMOJI and _EMOJI.match(ch))


def _norm_num(s: str) -> str:
    s = s.replace(",", ".")
    try:
        f = float(s)
    except ValueError:
        return s
    return str(int(f)) if f == int(f) else str(round(f, 2))


def _numbers_in(value: Any) -> set[str]:
    out: set[str] = set()
    if isinstance(value, dict):
        for v in value.values():
            out |= _numbers_in(v)
    elif isinstance(value, list | tuple):
        for v in value:
            out |= _numbers_in(v)
    elif value is not None and not isinstance(value, bool):
        out |= {_norm_num(m) for m in _NUMBER.findall(str(value))}
    return out


def _ngrams(words: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def _words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", s.lower())


# ---------------------------------------------------------------- context

@dataclass
class LeadContext:
    business: str                        # exact display name that must appear
    track: str
    domain: str | None                   # the lead's own domain (may be mentioned)
    area: str
    facts: dict[str, Fact]
    review_texts: list[str] = field(default_factory=list)
    reviewer_names: list[str] = field(default_factory=list)
    own_domains: set[str] = field(default_factory=set)

    @classmethod
    def from_candidate(cls, c: Candidate) -> LeadContext:
        own: set[str] = set()
        if c.audit and c.audit.site_status not in ("none", "social_as_site"):
            own = {h for h in (host(c.website_url), host(c.audit.final_url), c.audit.free_host) if h}
        return cls(business=c.display_name, track=c.track or "web", domain=host(c.website_url) or None,
                   own_domains=own, area=c.area,
                   facts={f.id: f for f in c.facts_for(c.track or "web")},
                   review_texts=[r.text for r in c.reviews if r.text],
                   reviewer_names=[r.author for r in c.reviews if r.author])


def _name_hits(text: str, names: list[str], exclude: str) -> list[str]:
    """Reviewer names in text: the full name, or any name part (≥3 letters) as a capitalised word."""
    hits = []
    excl = set(_words(exclude))
    for name in names:
        if name and name.lower() in text.lower():
            hits.append(name)
            continue
        for part in re.findall(r"[A-Za-z']+", name):
            if len(part) >= 3 and part.lower() not in excl and re.search(rf"\b{re.escape(part.capitalize())}\b", text):
                hits.append(part)
    return hits


def copied_from_review(text: str, reviews: list[str], max_words: int) -> bool:
    n = max_words + 1
    mine = _ngrams(_words(text), n)
    return any(mine & _ngrams(_words(r), n) for r in reviews)


# ---------------------------------------------------------------- variant rules

def validate_variant(message: str, used_fact_ids: list[str], ctx: LeadContext, cfg) -> list[str]:
    m = cfg.messaging
    errors: list[str] = []
    n = len(message)
    if not (m.length["min"] <= n <= m.length["max"]):
        errors.append(f"length {n} is outside {m.length['min']}–{m.length['max']} characters")
    if ctx.business not in message:
        errors.append(f"the exact business name '{ctx.business}' is missing")
    if m.signoff not in message:
        errors.append(f"the sign-off '{m.signoff}' is missing")
    if _URL.search(message):
        errors.append("contains a URL or link (no links in the first message)")
    if any(p.search(message) for p in _MONEY):
        errors.append("mentions money or a price (KES/Ksh/amount)")
    low = message.lower()
    banned = [b for b in m.banned_phrases if b.lower() in low]
    if banned:
        errors.append(f"contains banned phrase(s): {', '.join(banned)}")
    if count_emoji(message) > m.max_emoji:
        errors.append(f"has more than {m.max_emoji} emoji")
    if not used_fact_ids:
        errors.append("used_fact_ids is empty")
    unknown = [f for f in used_fact_ids if f not in ctx.facts]
    if unknown:
        errors.append(f"used_fact_ids references unknown fact(s): {', '.join(unknown)}")
    used = [ctx.facts[f] for f in used_fact_ids if f in ctx.facts]
    allowed = set()
    for f in used:
        allowed |= _numbers_in(f.text) | _numbers_in(f.evidence)
    allowed |= _numbers_in(ctx.business) | _numbers_in(ctx.area)
    stray = sorted({_norm_num(x) for x in _NUMBER.findall(message.replace(m.signoff, ""))} - allowed)
    if stray:
        errors.append(f"number(s) {', '.join(stray)} are not in the cited facts")
    for d in {d.lower() for d in _DOMAIN.findall(message)}:
        d0 = d[4:] if d.startswith("www.") else d
        if d0 not in {x.lower() for x in (ctx.own_domains or ({ctx.domain} if ctx.domain else set()))}:
            errors.append(f"mentions the domain '{d}', which is not the lead's own")
    names = _name_hits(message, ctx.reviewer_names, exclude=f"{ctx.business} {ctx.area} Swalleh Raswal Tech Solutions")
    if names:
        errors.append(f"contains a reviewer's name ({', '.join(sorted(set(names)))})")
    if copied_from_review(message, ctx.review_texts, m.review_copy_max_words):
        errors.append(f"copies {m.review_copy_max_words + 1}+ consecutive words from a review")
    return errors


def validate_pair(variants: list[Variant], ctx: LeadContext) -> list[str]:
    if len(variants) < 2:
        return ["two variants are required"]
    a, b = variants[0].used_fact_ids, variants[1].used_fact_ids
    if a and b and a[0] == b[0] and len(ctx.facts) > 1:
        return ["the two variants must open with different facts"]
    return []


# ---------------------------------------------------------------- review facts (§11.3)

def validate_review_fact(rf: dict, ctx: LeadContext, cfg, n_reviews: int) -> list[str]:
    errors = []
    idx = rf.get("review_index")
    if not isinstance(idx, int) or not (1 <= idx <= n_reviews):
        errors.append(f"review_index {idx} does not exist")
    para = (rf.get("paraphrase") or "").strip()
    if not para:
        errors.append("empty paraphrase")
    if len(para.split()) > cfg.messaging.paraphrase_max_words:
        errors.append(f"paraphrase longer than {cfg.messaging.paraphrase_max_words} words")
    if _name_hits(para, ctx.reviewer_names, exclude=f"{ctx.business} {ctx.area}"):
        errors.append("paraphrase contains the reviewer's name")
    if copied_from_review(para, ctx.review_texts, cfg.messaging.review_copy_max_words):
        errors.append("paraphrase copies the review verbatim")
    if _NUMBER.search(para):
        errors.append("paraphrase contains a number")
    if _SEVERAL.search(para) and n_reviews < 2:
        errors.append("paraphrase claims several reviews")
    if rf.get("sentiment") == "negative" and rf.get("addressable_by") in (None, "none"):
        errors.append("pain theme that a website/content would not address")
    return errors


def review_fact_to_fact(rf: dict, fid: str, track: str, cfg) -> Fact | None:
    sentiment = rf.get("sentiment")
    theme = (rf.get("theme") or "").strip()
    para = rf["paraphrase"].strip()
    if not para.endswith((".", "!")):
        para += "."
    if sentiment == "negative":
        fixable = rf.get("addressable_by")
        want = "website" if track == "web" else "content"
        return Fact(id=fid, code="REVIEW_PAIN", strength="strong" if fixable == want else "medium", text=para,
                    evidence={"review_index": rf["review_index"], "theme": theme, "sentiment": sentiment,
                              "addressable_by": fixable}, track="web" if fixable == "website" else "content",
                    source="llm")
    generic = basic_norm(theme) in {basic_norm(g) for g in cfg.scoring.facts.generic_themes}
    strong = sentiment == "positive" and not generic and len(para.split()) >= 4
    return Fact(id=fid, code="REVIEW_THEME", strength="strong" if strong else "medium", text=para,
                evidence={"review_index": rf["review_index"], "theme": theme, "sentiment": sentiment}, track="any",
                source="llm")


def validate_poster_line(line: str, ctx: LeadContext) -> bool:
    if not line or len(line.split()) > 10 or _URL.search(line) or _DOMAIN.search(line) or \
            any(p.search(line) for p in _MONEY):
        return False
    allowed = set()
    for f in ctx.facts.values():
        allowed |= _numbers_in(f.text)
    if {_norm_num(x) for x in _NUMBER.findall(line)} - allowed - _numbers_in(ctx.business):
        return False
    return not _name_hits(line, ctx.reviewer_names, exclude=ctx.business)


# ---------------------------------------------------------------- deterministic fallback

def swahili_flags(place_id: str, rate: float) -> list[bool]:
    return [random.Random(f"{place_id}:{i}").random() < rate for i in range(2)]


def is_swahili(message: str) -> bool:
    return bool(re.search(r"\b(habari|asante|karibu)\b", message, re.I))


def _greeting(cfg, business: str, swahili: bool, emoji: bool) -> str:
    g = cfg.messaging.greetings
    key = ("swahili" if swahili else "english") + ("" if emoji else "_plain")
    return g[key].format(business=business)


def fallback_message(fact: Fact, extra: list[Fact], ctx: LeadContext, cfg, *, swahili: bool, question_idx: int,
                     emoji: bool = True) -> Variant:
    m = cfg.messaging
    track = ctx.track
    tpl = m.fallback.by_code.get(fact.code) or (m.fallback.default_web if track == "web" else m.fallback.default_content)
    question = m.questions[track][question_idx % len(m.questions[track])]
    if swahili:
        question = f"{question} {m.swahili_closers[question_idx % len(m.swahili_closers)]}"
    fields = {**{k: v for k, v in fact.evidence.items() if v is not None},
              "greeting": _greeting(cfg, ctx.business, swahili, emoji), "observation": fact.text,
              "business": ctx.business, "business_possessive": possessive(ctx.business), "question": question,
              "signoff": m.signoff}
    used = [fact.id]

    def render(extra_text: str) -> str:
        return re.sub(r"[ \t]+", " ", tpl.format(**{**fields, "extra": extra_text})).replace(" \n", "\n").strip()

    extra_text = ""
    msg = render("")
    for e in extra:                                   # add facts until it's long enough
        if len(msg) >= m.length["min"]:
            break
        longer = render(f"{extra_text}{e.text} ")
        if len(longer) <= m.length["max"]:
            extra_text, msg = f"{extra_text}{e.text} ", longer
            used.append(e.id)
    if len(msg) < m.length["min"]:                    # still short: generic filler (makes no claim)
        msg = render(f"{extra_text}{m.fallback.filler[track]}")
    if len(msg) > m.length["max"] and emoji:
        return fallback_message(fact, [], ctx, cfg, swahili=swahili, question_idx=question_idx, emoji=False)
    v = Variant(message=msg, used_fact_ids=used, source="fallback", swahili_touch=is_swahili(msg))
    v.errors = validate_variant(v.message, v.used_fact_ids, ctx, cfg)
    return v


def fallback_variants(ctx: LeadContext, cfg, place_id: str, ordered: list[Fact]) -> list[Variant]:
    """Two variants opening with different facts (strongest first)."""
    sw = swahili_flags(place_id, cfg.messaging.swahili_touch_rate)
    if not ordered:
        return []
    first = ordered[0]
    second = ordered[1] if len(ordered) > 1 else ordered[0]
    a = fallback_message(first, [f for f in ordered if f is not first], ctx, cfg, swahili=sw[0], question_idx=0)
    b = fallback_message(second, [f for f in ordered if f not in (first, second)] or ([first] if second is not first else []),
                         ctx, cfg, swahili=sw[1], question_idx=1)
    return [a, b]
