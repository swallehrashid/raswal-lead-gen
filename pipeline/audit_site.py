"""Website audit and site_status classification (brief §9.1, §9.2).

Order of rules: none → social_as_site → dead → insecure → free_builder → weak → good.
`audit_website` does everything except the PSI-dependent weak check; `finalize_status`
completes classification once PSI has run (or been skipped).
"""

from __future__ import annotations

import re
from datetime import date, datetime
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from dateutil import parser as dtparser

from pipeline.models import Audit, FetchResult
from pipeline.utils.urls import host, host_matches, with_scheme

PENDING = "_pending"    # fetched OK; weak/good decided after PSI

_COPYRIGHT = re.compile(r"(?:©|\(c\)|copyright)(?:\s*(?:©|\(c\)))?\s*(?:by\s+)?((?:19|20)\d{2})(?:\s*[-–—]\s*((?:19|20)\d{2}))?",
                        re.I)
_MONTHS = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"
_DATE_PATTERNS = [
    re.compile(rf"\b(\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTHS},?\s+20\d{{2}})\b", re.I),
    re.compile(rf"\b({_MONTHS}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+20\d{{2}})\b", re.I),
    re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b"),
]


def social_platform(url: str, cfg) -> str | None:
    ac = cfg.audit
    h = host(url)
    if (m := host_matches(h, ac.social_as_site_hosts)) is not None:
        return ac.platform_names.get(m, m)
    path = urlsplit(url if "://" in url else f"http://{url}").path or ""
    if host_matches(h, ["google.com", "google.co.ke"]) and any(path.startswith(p) for p in ac.social_as_site_google_paths):
        return "Google Maps"
    return None


def visible_text(soup: BeautifulSoup) -> str:
    for t in soup(["script", "style", "noscript", "template", "svg"]):
        t.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ")).strip()


def copyright_year(text: str, now: date) -> int | None:
    years = []
    for m in _COPYRIGHT.finditer(text):
        y = int(m.group(2) or m.group(1))
        if 1990 <= y <= now.year + 1:
            years.append(y)
    return max(years) if years else None


def parse_dates(html: str, now: date) -> list[date]:
    soup = BeautifulSoup(html, "lxml")
    found: list[date] = []
    cands = [t.get("datetime") for t in soup.find_all("time") if t.get("datetime")]
    cands += [m.get("content") for m in soup.find_all("meta", attrs={"property": re.compile("published_time|modified_time")})]
    text = soup.get_text(" ")
    for pat in _DATE_PATTERNS:
        cands += pat.findall(text)
    for s in cands:
        try:
            d = dtparser.parse(s, fuzzy=True).date()
        except (ValueError, OverflowError, TypeError):
            continue
        if date(2000, 1, 1) <= d <= now:
            found.append(d)
    return found


def extract_features(page: FetchResult, cfg, now: date) -> dict:
    ac = cfg.audit
    html = page.html or ""
    soup = BeautifulSoup(html, "lxml")
    title = (soup.title.get_text(strip=True) if soup.title else "") or None
    viewport = soup.find("meta", attrs={"name": re.compile("^viewport$", re.I)}) is not None
    links = [a.get("href", "") for a in soup.find_all("a")]
    lower_html = html.lower()
    social: dict[str, str] = {}
    for href in links:
        h = host(href) if href.startswith(("http", "//")) else ""
        if not h:
            continue
        path = urlsplit(href if "://" in href else f"https:{href}").path.lower()
        if any(path.startswith(p) for p in ac.social_ignore_paths):
            continue
        for name, hosts in ac.social_hosts.items():
            if host_matches(h, hosts) and name not in social:
                social[name] = href
    platform = next((p for p, marks in ac.platform_markers.items() if any(m.lower() in lower_html for m in marks)), None)
    has_video = soup.find("video") is not None or any(
        any(v in (f.get("src") or "") for v in ac.video_embed_hosts) for f in soup.find_all(["iframe", "embed"]))
    blog_url = None
    base_host = host(page.final_url or page.url)
    for a in soup.find_all("a"):
        href, txt = a.get("href", ""), a.get_text(" ", strip=True).lower()
        if any(w in href.lower() or w == txt for w in ac.blog_link_words):
            full = urljoin(page.final_url or page.url, href)
            if host(full) == base_host:
                blog_url = full
                break
    text = visible_text(soup)
    return {
        "title": title, "meta_viewport": viewport,
        "copyright_year": copyright_year(text, now),
        "has_whatsapp_link": any(any(m in href.lower() for m in ac.whatsapp_link_markers) for href in links),
        "has_tel_link": any(href.lower().startswith("tel:") for href in links),
        "platform": platform or "custom", "social_links": social, "has_video": has_video,
        "word_count": len(text.split()), "text": text, "blog_url": blog_url,
    }


def _dead_marker_for_error(r: FetchResult, cfg) -> str:
    em = cfg.audit.error_markers
    if r.status_code and r.status_code >= 500:
        return em["status_5xx"]
    if r.status_code and r.status_code >= 400:
        return em["status_4xx"].format(status=r.status_code)
    return em.get(r.error or "other", em["other"])


def _parked_marker(text: str, title: str, cfg) -> str | None:
    ac = cfg.audit
    hay = f"{title} {text[:4000]}".lower()
    for marker, phrase in ac.parked_markers.items():
        if marker in hay:
            if marker in ac.default_page_markers and len(text) > ac.default_page_max_text_chars:
                continue
            if marker == "index of /" and not title.lower().startswith("index of /"):
                continue
            return phrase
    if len(text) < ac.coming_soon_max_text_chars:
        for marker, phrase in ac.coming_soon_markers.items():
            if marker in hay:
                return phrase
    return None


def audit_website(url: str | None, fetcher, cfg, now: datetime) -> Audit:
    ac = cfg.audit
    if not url:
        return Audit("none")
    if plat := social_platform(url, cfg):
        return Audit("social_as_site", website_url=url, social_platform=plat)
    if host_matches(host(url), ac.dead_redirect_hosts):
        return Audit("dead", website_url=url, dead_marker=ac.error_markers["business_site"])

    r_https = fetcher.fetch(with_scheme(url, "https"))
    page, https_ok, cert_error = None, False, r_https.error == "ssl"
    if r_https.ok and (r_https.final_url or "").startswith("https://"):
        page, https_ok = r_https, True
    else:
        r_http = fetcher.fetch(with_scheme(url, "http"))
        if r_http.ok:
            page = r_http
            https_ok = (r_http.final_url or "").startswith("https://")
        else:
            failed = r_http if r_http.status_code else r_https
            chain = r_https.redirect_chain + r_http.redirect_chain
            marker = (ac.error_markers["business_site"] if any(host_matches(host(u), ac.dead_redirect_hosts) for u in chain)
                      else _dead_marker_for_error(failed, cfg))
            return Audit("dead", website_url=url, final_url=failed.final_url, status_code=failed.status_code,
                         https_ok=False, cert_error=cert_error, redirect_chain=chain, dead_marker=marker)

    a = Audit(PENDING, website_url=url, final_url=page.final_url, status_code=page.status_code, https_ok=https_ok,
              cert_error=cert_error, redirect_chain=page.redirect_chain, html_bytes=len(page.html.encode()),
              html=page.html)
    if any(host_matches(host(u), ac.dead_redirect_hosts) for u in page.redirect_chain):
        a.site_status, a.dead_marker = "dead", ac.error_markers["business_site"]
        return a
    if host_matches(host(page.final_url), ac.parking_hosts):
        a.site_status, a.dead_marker = "dead", "a parked-domain page"
        return a
    f = extract_features(page, cfg, now.date())
    for k in ("title", "meta_viewport", "copyright_year", "has_whatsapp_link", "has_tel_link", "platform",
              "social_links", "has_video", "word_count"):
        setattr(a, k, f[k])
    if marker := _parked_marker(f["text"], f["title"] or "", cfg):
        a.site_status, a.dead_marker = "dead", marker
        return a
    if not https_ok:
        a.site_status = "insecure"
    elif (fb := host_matches(host(page.final_url), list(ac.free_builder_hosts))) is not None:
        a.site_status, a.free_builder, a.free_host = "free_builder", ac.free_builder_hosts[fb], host(page.final_url)
    if f["blog_url"] and cfg.budget.site_fetch.blog_fetch and a.site_status == PENDING:
        blog = fetcher.fetch(f["blog_url"])
        if blog.ok:
            dates = parse_dates(blog.html, now.date())
            a.blog_last_date = max(dates) if dates else None
    return a


def weak_signals(a: Audit, cfg, now: datetime) -> list[str]:
    w = cfg.scoring.weak_site
    sig = []
    if a.psi_perf is not None and a.psi_perf < w.psi_perf_below:
        sig.append("psi_slow")
    if a.meta_viewport is False:
        sig.append("no_viewport")
    if a.copyright_year is not None and a.copyright_year <= now.year - w.copyright_age_years:
        sig.append("old_copyright")
    if a.has_whatsapp_link is False:
        sig.append("no_whatsapp")
    if a.has_tel_link is False:
        sig.append("no_tel")
    if a.word_count < w.min_words:
        sig.append("thin_text")
    return sig


def finalize_status(a: Audit, cfg, now: datetime) -> Audit:
    """Apply the weak/good rule after PSI. Also records weak signals for insecure/free_builder sites."""
    if a.site_status in ("none", "social_as_site", "dead"):
        return a
    a.weak_signals = weak_signals(a, cfg, now)
    if a.site_status == PENDING:
        a.site_status = "weak" if len(a.weak_signals) >= cfg.scoring.weak_site.min_signals else "good"
    return a


def needs_psi(a: Audit) -> bool:
    return a.site_status in (PENDING, "insecure", "free_builder")
