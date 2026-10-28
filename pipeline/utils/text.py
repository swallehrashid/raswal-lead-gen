"""Name normalisation, word matching, slugs and display names (brief §7.2)."""

from __future__ import annotations

import re
import unicodedata

_LEGAL = {"limited": "ltd", "ltd": "ltd", "co": "ltd", "company": "ltd", "coy": "ltd", "plc": "ltd", "llc": "ltd", "inc": "ltd"}
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"\s+")


def ascii_fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")


def basic_norm(s: str) -> str:
    """lowercase, '&' → 'and', apostrophes dropped, punctuation → space, whitespace collapsed."""
    s = ascii_fold(s or "").lower().replace("&", " and ").replace("'", "").replace("’", "")
    s = _PUNCT.sub(" ", s).replace("_", " ")
    return _WS.sub(" ", s).strip()


def name_norm(name: str) -> str:
    """Canonical name: legal suffixes (limited/ltd/co./company) collapse to a single 'ltd'."""
    out: list[str] = []
    for tok in basic_norm(name).split():
        tok = _LEGAL.get(tok, tok)
        if tok == "ltd" and out and out[-1] == "ltd":
            continue
        out.append(tok)
    return " ".join(out)


def name_key(norm: str, area_names: list[str] = ()) -> str:
    """Brand key for branch detection: name_norm without legal suffix and trailing area names."""
    toks = [t for t in norm.split() if t != "ltd"]
    s = " ".join(toks)
    for area in sorted((basic_norm(a) for a in area_names), key=len, reverse=True):
        if area and (s.endswith(" " + area) and s != area):
            s = s[: -len(area) - 1].strip()
    return s


def contains_phrase(text_norm: str, phrase: str) -> bool:
    """Whole-word phrase match on normalised text."""
    p = basic_norm(phrase)
    return bool(p) and re.search(rf"(?<!\w){re.escape(p)}(?!\w)", text_norm) is not None


def any_phrase(text_norm: str, phrases) -> str | None:
    for p in phrases:
        if contains_phrase(text_norm, p):
            return p
    return None


def remove_phrase(text_norm: str, phrase: str) -> str:
    p = basic_norm(phrase)
    return _WS.sub(" ", re.sub(rf"(?<!\w){re.escape(p)}(?!\w)", " ", text_norm)).strip()


def slugify(norm: str, max_len: int = 30) -> str:
    """Kebab-case slug from name_norm (brief §13.2), at most max_len chars, cut on a word."""
    toks = [t for t in basic_norm(norm).split() if t != "ltd"] or basic_norm(norm).split()
    slug = ""
    for t in toks:
        nxt = f"{slug}-{t}" if slug else t
        if len(nxt) > max_len:
            break
        slug = nxt
    return slug or basic_norm(norm).replace(" ", "-")[:max_len].strip("-") or "business"


_SUFFIX_RE = re.compile(r"[\s,]*(\(?\s*(?:company|co\.?)?\s*(?:limited|ltd\.?|l\.t\.d\.?)\s*\)?)\s*$", re.I)


_TAIL_SEP = re.compile(r"\s+[-–—|:]\s+|\s*[|:]\s+")


def display_name(name: str) -> str:
    """Name used in messages: keyword tail dropped, legal suffix dropped, ALL CAPS fixed. Must appear verbatim."""
    s = _WS.sub(" ", (name or "").strip())
    if len(s) > 34:  # "Avenue Vista Property Center - Houses, Land & Plots…" → "Avenue Vista Property Center"
        head = _TAIL_SEP.split(s, maxsplit=1)[0].strip(" ,-")
        if len([c for c in head if c.isalpha()]) >= 6:
            s = head
    s = _SUFFIX_RE.sub("", s).strip(" ,-") or s
    letters = [c for c in s if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) > 0.8 and len(letters) > 4:
        # keep short all-caps words as acronyms (e.g. "JKL Builders"), title-case the rest
        s = " ".join(w if len(w) <= 3 and w.isalpha() and w not in {"THE", "AND", "OF"} else w.capitalize()
                     for w in s.split())
    return s


def possessive(name: str) -> str:
    return f"{name}'" if name.endswith("s") else f"{name}'s"


def words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", basic_norm(s))
