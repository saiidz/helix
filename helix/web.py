"""Zero-credit web retrieval for Helix.

Search uses DuckDuckGo's public HTML endpoint and page retrieval uses direct HTTPS/HTTP
GETs. This is intentionally conservative: no JavaScript execution, cookies, redirects,
credentials, private-network targets, or background crawling.
"""
from __future__ import annotations

import html
import ipaddress
import re
import socket
import threading
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote_plus, unquote, urlsplit

import httpx


class WebError(Exception):
    pass


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str


@dataclass(frozen=True)
class WebDocument:
    title: str
    url: str
    text: str


_CACHE_LOCK = threading.Lock()
_CACHE: dict[str, tuple[float, object]] = {}
_CACHE_TTL_SECONDS = 300


def _cache_get(key: str):
    now = time.monotonic()
    with _CACHE_LOCK:
        item = _CACHE.get(key)
        if not item:
            return None
        expires, value = item
        if expires <= now:
            _CACHE.pop(key, None)
            return None
        return value


def _cache_put(key: str, value) -> None:
    with _CACHE_LOCK:
        _CACHE[key] = (time.monotonic() + _CACHE_TTL_SECONDS, value)


def _public_host(hostname: str) -> bool:
    try:
        addresses = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False

    if not addresses:
        return False

    for family, _, _, _, sockaddr in addresses:
        raw = sockaddr[0]
        try:
            addr = ipaddress.ip_address(raw)
        except ValueError:
            return False

        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_multicast
            or addr.is_reserved
            or addr.is_unspecified
        ):
            return False

    return True


def validate_public_url(url: str) -> str:
    value = url.strip()
    if len(value) > 2048:
        raise WebError("Web URL is too long")

    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"}:
        raise WebError("Only HTTP(S) web URLs are allowed")
    if not parsed.hostname or parsed.username or parsed.password:
        raise WebError("Invalid web URL")
    if parsed.port not in {None, 80, 443}:
        raise WebError("Only standard HTTP(S) ports are allowed")
    if not _public_host(parsed.hostname):
        raise WebError("Private or unsafe network targets are blocked")

    return value


class _SearchParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results: list[SearchResult] = []
        self._link = False
        self._snippet = False
        self._href = ""
        self._title_parts: list[str] = []
        self._snippet_parts: list[str] = []
        self._pending: tuple[str, str] | None = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set((attrs.get("class") or "").split())

        if tag == "a" and "result__a" in classes:
            self._link = True
            self._href = attrs.get("href", "")
            self._title_parts = []
        elif tag in {"a", "div"} and "result__snippet" in classes:
            self._snippet = True
            self._snippet_parts = []

    def handle_data(self, data):
        if self._link:
            self._title_parts.append(data)
        elif self._snippet:
            self._snippet_parts.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._link:
            self._link = False
            title = " ".join("".join(self._title_parts).split())
            url = _normalize_ddg_url(self._href)
            if title and url:
                self._pending = (title, url)
                self.results.append(SearchResult(title=title, url=url, snippet=""))
        elif tag in {"a", "div"} and self._snippet:
            self._snippet = False
            snippet = " ".join("".join(self._snippet_parts).split())
            if snippet and self.results and not self.results[-1].snippet:
                last = self.results[-1]
                self.results[-1] = SearchResult(last.title, last.url, snippet)


class _TextParser(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "canvas"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.title_parts: list[str] = []
        self.in_title = False
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip_depth += 1
        elif tag == "title":
            self.in_title = True
        elif tag in {"p", "li", "article", "section", "h1", "h2", "h3", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip_depth:
            self.skip_depth -= 1
        elif tag == "title":
            self.in_title = False
        elif tag in {"p", "li", "article", "section", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.skip_depth:
            return
        if self.in_title:
            self.title_parts.append(data)
        self.parts.append(data)


def _normalize_ddg_url(href: str) -> str:
    if not href:
        return ""

    href = html.unescape(href)
    if href.startswith("//"):
        href = "https:" + href

    parsed = urlsplit(href)
    if parsed.hostname and parsed.hostname.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        values = parse_qs(parsed.query).get("uddg")
        if values:
            return unquote(values[0])

    if parsed.scheme in {"http", "https"}:
        return href

    return ""


def search_web(query: str, limit: int = 5) -> list[SearchResult]:
    query = " ".join(query.split())
    if not query:
        raise WebError("Search query cannot be empty")
    if len(query) > 500:
        raise WebError("Search query is too long")

    limit = max(1, min(limit, 8))
    cache_key = f"search:{query.lower()}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    url = "https://html.duckduckgo.com/html/?q=" + quote_plus(query)
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; HelixLocal/0.2; +https://github.com/saiidz/helix)",
        "Accept": "text/html,application/xhtml+xml",
    }

    try:
        with httpx.Client(
            timeout=httpx.Timeout(12, connect=4),
            trust_env=False,
            follow_redirects=False,
            headers=headers,
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            if len(response.content) > 1_500_000:
                raise WebError("Search response exceeded size limit")
    except httpx.HTTPError as exc:
        raise WebError("Web search is currently unavailable") from exc

    parser = _SearchParser()
    parser.feed(response.text)

    unique: list[SearchResult] = []
    seen: set[str] = set()

    for result in parser.results:
        if result.url in seen:
            continue
        try:
            validate_public_url(result.url)
        except WebError:
            continue
        seen.add(result.url)
        unique.append(result)
        if len(unique) >= limit:
            break

    _cache_put(cache_key, unique)
    return unique


def fetch_web_text(url: str, max_chars: int = 12_000) -> WebDocument:
    url = validate_public_url(url)
    max_chars = max(1000, min(max_chars, 25_000))
    cache_key = f"fetch:{url}:{max_chars}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; HelixLocal/0.2; +https://github.com/saiidz/helix)",
        "Accept": "text/html,text/plain;q=0.9",
    }

    try:
        with httpx.Client(
            timeout=httpx.Timeout(12, connect=4),
            trust_env=False,
            follow_redirects=False,
            headers=headers,
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            content_type = (response.headers.get("content-type") or "").lower()
            if not any(kind in content_type for kind in ("text/html", "text/plain", "application/xhtml+xml")):
                raise WebError("Web page is not readable text")
            if len(response.content) > 2_000_000:
                raise WebError("Web page exceeded size limit")
    except httpx.HTTPError as exc:
        raise WebError("Web page could not be retrieved") from exc

    if "text/html" in content_type or "xhtml" in content_type:
        parser = _TextParser()
        parser.feed(response.text)
        title = " ".join("".join(parser.title_parts).split())
        text = " ".join(" ".join(parser.parts).split())
    else:
        title = urlsplit(url).hostname or url
        text = " ".join(response.text.split())

    document = WebDocument(
        title=title[:300] or (urlsplit(url).hostname or "Web page"),
        url=url,
        text=text[:max_chars],
    )
    _cache_put(cache_key, document)
    return document


def research_web(query: str, search_limit: int = 5, fetch_limit: int = 3) -> tuple[list[SearchResult], list[WebDocument]]:
    results = search_web(query, limit=search_limit)
    documents: list[WebDocument] = []

    for result in results[: max(0, min(fetch_limit, 3))]:
        try:
            documents.append(fetch_web_text(result.url))
        except WebError:
            continue

    return results, documents
