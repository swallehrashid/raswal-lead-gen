"""Live HTTP fetcher for a business's OWN website (brief §2.3, §9.1). Never raises."""

from __future__ import annotations

import logging

import httpx

from pipeline.models import FetchResult

log = logging.getLogger(__name__)


def classify_error(e: BaseException) -> str:
    msg = str(e).lower()
    if isinstance(e, httpx.TooManyRedirects):
        return "too_many_redirects"
    if isinstance(e, httpx.TimeoutException):
        return "timeout"
    if "certificate" in msg or "ssl" in msg or "tls" in msg:
        return "ssl"
    if any(s in msg for s in ("name or service not known", "nodename nor servname", "getaddrinfo", "name resolution",
                              "no address associated", "temporary failure in name")):
        return "dns"
    if isinstance(e, httpx.ConnectError | httpx.RemoteProtocolError | httpx.ReadError):
        return "connect"
    return "other"


class LiveFetcher:
    def __init__(self, cfg):
        sf = cfg.budget.site_fetch
        self.max_bytes = sf.max_bytes
        self.client = httpx.Client(
            timeout=sf.timeout_s, follow_redirects=True, max_redirects=sf.max_redirects,
            headers={"User-Agent": cfg.audit.user_agent,
                     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                     "Accept-Language": "en-KE,en;q=0.9"},
        )

    def fetch(self, url: str) -> FetchResult:
        try:
            with self.client.stream("GET", url) as r:
                chunks, size = [], 0
                for chunk in r.iter_bytes():
                    chunks.append(chunk)
                    size += len(chunk)
                    if size >= self.max_bytes:
                        break
                body = b"".join(chunks)
                ctype = r.headers.get("content-type", "")
                html = ""
                if "html" in ctype or "xml" in ctype or not ctype:
                    html = body.decode(r.encoding or "utf-8", errors="replace")
                chain = [str(h.url) for h in r.history] + [str(r.url)]
                return FetchResult(url=url, final_url=str(r.url), status_code=r.status_code, redirect_chain=chain,
                                   html=html, headers={k.lower(): v for k, v in r.headers.items()})
        except Exception as e:  # noqa: BLE001
            return FetchResult(url=url, error=classify_error(e), error_detail=str(e)[:300])

    def fetch_bytes(self, url: str, max_bytes: int = 5_000_000) -> bytes | None:
        try:
            with self.client.stream("GET", url) as r:
                if r.status_code >= 400:
                    return None
                data = b""
                for chunk in r.iter_bytes():
                    data += chunk
                    if len(data) > max_bytes:
                        return None
                return data
        except Exception:  # noqa: BLE001
            return None
