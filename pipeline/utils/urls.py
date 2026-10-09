"""URL / domain helpers. tldextract runs from its bundled suffix list (no network)."""

from __future__ import annotations

from urllib.parse import urlsplit

import tldextract

# include_psl_private_domains: acme.wixsite.com and bob.blogspot.com are separate sites, not "wixsite.com"
_extract = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None, include_psl_private_domains=True)


def ensure_scheme(url: str) -> str:
    url = (url or "").strip()
    return url if "://" in url else f"http://{url}"


def host(url: str | None) -> str:
    if not url:
        return ""
    h = (urlsplit(ensure_scheme(url)).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def registered_domain(url: str | None) -> str:
    if not url:
        return ""
    ext = _extract(host(url))
    return ext.top_domain_under_public_suffix or ext.fqdn or host(url)


def host_matches(h: str, candidates) -> str | None:
    """Return the candidate that h equals or is a subdomain of."""
    h = (h or "").lower()
    for c in candidates:
        c = c.lower()
        if h == c or h.endswith("." + c):
            return c
    return None


def with_scheme(url: str, scheme: str) -> str:
    parts = urlsplit(ensure_scheme(url))
    rest = parts.netloc + (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    return f"{scheme}://{rest}"
