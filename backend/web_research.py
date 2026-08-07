from __future__ import annotations

import hashlib
import html
import ipaddress
import json
import os
import re
import socket
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field


DEFAULT_SEARXNG_URL = "http://127.0.0.1:8888"
MAX_QUERY_CHARS = 500
MAX_RESULTS = 20
MAX_QUERIES = 8
MAX_PAGES = 24
MAX_PAGE_BYTES = 2_000_000
MAX_EXCERPT_CHARS = 18_000
MAX_CONTEXT_CHARS = 60_000
USER_AGENT = "AI-Workspace-LocalResearch/1.0 (+local-first; contact=workspace-owner)"


class WebResearchError(RuntimeError):
    def __init__(self, detail: str, failure_class: str) -> None:
        self.detail = detail
        self.failure_class = failure_class
        super().__init__(detail)


class WebSearchInput(BaseModel):
    query: str = Field(min_length=1, max_length=MAX_QUERY_CHARS)
    categories: str = Field(default="general", max_length=80)
    time_range: str = Field(default="", max_length=20)
    language: str = Field(default="en", max_length=20)
    safe_search: int = Field(default=1, ge=0, le=2)
    max_results: int = Field(default=10, ge=1, le=MAX_RESULTS)
    domains: list[str] = Field(default_factory=list, max_length=10)


class ExtractWebPageInput(BaseModel):
    url: str = Field(min_length=8, max_length=2_000)
    max_chars: int = Field(default=MAX_EXCERPT_CHARS, ge=1_000, le=MAX_EXCERPT_CHARS)


class DeepResearchInput(BaseModel):
    query: str = Field(default="", max_length=MAX_QUERY_CHARS)
    queries: list[str] = Field(default_factory=list, max_length=MAX_QUERIES)
    categories: str = Field(default="general", max_length=80)
    time_range: str = Field(default="", max_length=20)
    language: str = Field(default="en", max_length=20)
    safe_search: int = Field(default=1, ge=0, le=2)
    max_results_per_query: int = Field(default=8, ge=1, le=MAX_RESULTS)
    max_pages: int = Field(default=12, ge=1, le=MAX_PAGES)
    per_domain: int = Field(default=2, ge=1, le=5)
    extract_pages: bool = True


class BuildResearchContextInput(BaseModel):
    sources: list[dict[str, Any]] = Field(default_factory=list, max_length=24)
    context_text: str = Field(default="", max_length=MAX_CONTEXT_CHARS)
    max_chars: int = Field(default=30_000, ge=2_000, le=MAX_CONTEXT_CHARS)


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript", "svg", "template", "head"}:
            self._skip_depth += 1
        elif lowered == "title" and self._skip_depth == 0:
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered == "title":
            self._in_title = False
        if lowered in {"script", "style", "noscript", "svg", "template", "head"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = html.unescape(data).strip()
        if not text:
            return
        if self._in_title:
            self.title_parts.append(text)
        self.text_parts.append(text)


def _error(failure_class: str, detail: str) -> str:
    return json.dumps({"status": "error", "failure_class": failure_class, "detail": detail}, ensure_ascii=False)


def _searxng_url() -> str:
    raw = os.getenv("SEARXNG_URL", DEFAULT_SEARXNG_URL).strip().rstrip("/")
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise WebResearchError("SEARXNG_URL is malformed", "search_backend_invalid") from exc
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise WebResearchError("SEARXNG_URL must be an unauthenticated loopback HTTP URL", "search_backend_invalid")
    if port is None:
        port = 80
    path = parsed.path.rstrip("/")
    return urlunsplit(("http", "127.0.0.1", f"{port}" if port != 80 else "", path, ""))


def _is_public_address(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
        return address.is_global
    except ValueError:
        pass
    lowered = host.lower().rstrip(".")
    if lowered in {"localhost", "localhost.localdomain"} or lowered.endswith((".localhost", ".local", ".internal")):
        return False
    try:
        infos = socket.getaddrinfo(lowered, None, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise WebResearchError("the page host could not be resolved", "url_dns_failed") from exc
    addresses = {str(item[4][0]) for item in infos if item[4]}
    if not addresses or not all(ipaddress.ip_address(address).is_global for address in addresses):
        return False
    return True


def _public_url(raw_url: str) -> str:
    raw = str(raw_url or "").strip()
    try:
        parsed = urlsplit(raw)
        parsed.port
    except ValueError as exc:
        raise WebResearchError("only public HTTP(S) URLs without credentials are allowed", "url_denied") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query and len(parsed.query) > 4_000:
        raise WebResearchError("only public HTTP(S) URLs without credentials are allowed", "url_denied")
    if not _is_public_address(parsed.hostname):
        raise WebResearchError("private, loopback, or non-public page hosts are blocked", "url_private_denied")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, ""))


def _domain(url: str) -> str:
    return str(urlsplit(url).hostname or "").lower()


def _source_id(url: str) -> str:
    return f"S{hashlib.sha256(url.encode('utf-8')).hexdigest()[:10]}"


def _normalize_query_list(query: str, queries: list[str]) -> list[str]:
    raw = [str(item).strip() for item in queries if str(item).strip()]
    if query.strip():
        raw.insert(0, query.strip())
    deduped: list[str] = []
    seen: set[str] = set()
    for item in raw:
        key = item.casefold()
        if key not in seen:
            seen.add(key)
            deduped.append(item[:MAX_QUERY_CHARS])
        if len(deduped) >= MAX_QUERIES:
            break
    if not deduped:
        raise WebResearchError("at least one research query is required", "query_missing")
    return deduped


def _search_searxng(query: str, *, categories: str, time_range: str, language: str, safe_search: int, max_results: int, domains: list[str]) -> dict[str, Any]:
    base = _searxng_url()
    bounded_query = query.strip()[:MAX_QUERY_CHARS]
    if domains:
        site_terms = " ".join(f"site:{domain.strip()}" for domain in domains if re.fullmatch(r"[A-Za-z0-9.-]{1,253}", domain.strip()))
        bounded_query = f"{bounded_query} {site_terms}".strip()[:MAX_QUERY_CHARS]
    params: dict[str, Any] = {
        "q": bounded_query,
        "format": "json",
        "categories": categories or "general",
        "language": language or "en",
        "safesearch": safe_search,
    }
    if time_range:
        params["time_range"] = time_range
    try:
        with httpx.Client(base_url=f"{base}/", timeout=8.0, trust_env=False, headers={"User-Agent": USER_AGENT}) as client:
            response = client.get("search", params=params)
            response.raise_for_status()
            payload = response.json()
    except httpx.ConnectError as exc:
        raise WebResearchError("local SearXNG is unavailable", "search_backend_unavailable") from exc
    except httpx.TimeoutException as exc:
        raise WebResearchError("local SearXNG timed out", "search_backend_timeout") from exc
    except httpx.HTTPStatusError as exc:
        raise WebResearchError("local SearXNG rejected the search request", "search_backend_failed") from exc
    except (httpx.RequestError, ValueError) as exc:
        raise WebResearchError("local SearXNG returned an invalid response", "search_backend_invalid_response") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise WebResearchError("local SearXNG response did not contain results", "search_backend_invalid_response")
    results: list[dict[str, Any]] = []
    for rank, item in enumerate(payload["results"][: max(1, min(max_results, MAX_RESULTS))], start=1):
        if not isinstance(item, dict):
            continue
        try:
            url = _public_url(str(item.get("url") or ""))
        except WebResearchError:
            continue
        results.append({
            "source_id": _source_id(url),
            "rank": rank,
            "title": str(item.get("title") or "")[:500],
            "url": url,
            "domain": _domain(url),
            "snippet": str(item.get("content") or item.get("snippet") or "")[:2_000],
            "engine": str(item.get("engine") or item.get("template") or "searxng")[:100],
            "published_date": str(item.get("publishedDate") or "")[:80],
        })
    return {"status": "ok", "backend": "searxng-local", "query": bounded_query, "result_count": len(results), "results": results}


def _robots_allowed(client: httpx.Client, url: str) -> None:
    parsed = urlsplit(url)
    robots_url = urlunsplit((parsed.scheme, parsed.netloc, "/robots.txt", "", ""))
    try:
        response = client.get(robots_url, follow_redirects=False)
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        raise WebResearchError("robots.txt could not be evaluated", "robots_unavailable") from exc
    if response.status_code == 404:
        return
    if response.status_code >= 400 or response.status_code in {301, 302, 303, 307, 308}:
        raise WebResearchError("robots.txt could not be evaluated safely", "robots_unavailable")
    parser_lines = response.text[:100_000].splitlines()
    from urllib.robotparser import RobotFileParser
    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(parser_lines)
    if not parser.can_fetch(USER_AGENT, url):
        raise WebResearchError("the target page is disallowed by robots.txt", "robots_denied")


def _fetch_page(url: str, max_chars: int) -> dict[str, Any]:
    current = _public_url(url)
    redirects = 0
    try:
        with httpx.Client(timeout=12.0, trust_env=False, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain,application/xhtml+xml"}) as client:
            while True:
                _robots_allowed(client, current)
                response = client.get(current, follow_redirects=False)
                if response.status_code in {301, 302, 303, 307, 308}:
                    redirects += 1
                    if redirects > 3:
                        raise WebResearchError("page redirect limit exceeded", "redirect_limit")
                    location = response.headers.get("location")
                    if not location:
                        raise WebResearchError("page redirect did not include a destination", "redirect_invalid")
                    current = _public_url(urljoin(current, location))
                    continue
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").lower()
                if content_type and not any(kind in content_type for kind in ("text/", "html", "xml", "json")):
                    raise WebResearchError("page content type is not readable text", "content_type_denied")
                body = bytearray()
                for chunk in response.iter_bytes(64 * 1024):
                    body.extend(chunk)
                    if len(body) > MAX_PAGE_BYTES:
                        raise WebResearchError("page response exceeded the size limit", "page_too_large")
                raw = bytes(body)
    except WebResearchError:
        raise
    except httpx.TimeoutException as exc:
        raise WebResearchError("page fetch timed out", "page_timeout") from exc
    except httpx.HTTPStatusError as exc:
        raise WebResearchError("page fetch returned an HTTP error", "page_http_error") from exc
    except httpx.RequestError as exc:
        raise WebResearchError("page fetch failed", "page_fetch_failed") from exc
    try:
        text = raw.decode(response.encoding or "utf-8", errors="replace")
    except (LookupError, UnicodeError):
        text = raw.decode("utf-8", errors="replace")
    parser = _VisibleTextParser()
    try:
        parser.feed(text)
    except Exception as exc:
        raise WebResearchError("page HTML could not be parsed", "page_parse_failed") from exc
    visible = re.sub(r"\s+", " ", " ".join(parser.text_parts)).strip()
    if not visible:
        raise WebResearchError("page did not contain readable text", "page_text_empty")
    title = re.sub(r"\s+", " ", " ".join(parser.title_parts)).strip()[:500]
    return {"status": "ok", "source_id": _source_id(current), "url": current, "domain": _domain(current), "title": title, "text": visible[:max_chars], "char_count": len(visible), "redirects": redirects}


def _json_result(call: Any) -> str:
    try:
        serialized = json.dumps(call, ensure_ascii=False)
        if len(serialized) <= 180_000:
            return serialized
        if isinstance(call, dict) and isinstance(call.get("sources"), list):
            compact = dict(call)
            compact["sources"] = []
            for source in call["sources"]:
                if not isinstance(source, dict):
                    continue
                item = dict(source)
                if "text" in item:
                    item["text"] = str(item["text"])[:4_000]
                compact["sources"].append(item)
                candidate = json.dumps(compact, ensure_ascii=False)
                if len(candidate) > 180_000:
                    compact["sources"].pop()
                    break
            compact["output_truncated"] = True
            return json.dumps(compact, ensure_ascii=False)
        return json.dumps({"status": "error", "failure_class": "result_too_large", "detail": "web result exceeded the bounded output size"}, ensure_ascii=False)
    except (TypeError, ValueError):
        return _error("serialization_failed", "web result could not be serialized")


@tool("search_web", args_schema=WebSearchInput)
def search_web(query: str, categories: str = "general", time_range: str = "", language: str = "en", safe_search: int = 1, max_results: int = 10, domains: list[str] | None = None) -> str:
    """Search through the local loopback SearXNG JSON API and return normalized public sources."""
    try:
        return _json_result(_search_searxng(query, categories=categories, time_range=time_range, language=language, safe_search=safe_search, max_results=max_results, domains=domains or []))
    except WebResearchError as exc:
        return _error(exc.failure_class, exc.detail)


@tool("extract_web_page", args_schema=ExtractWebPageInput)
def extract_web_page(url: str, max_chars: int = MAX_EXCERPT_CHARS) -> str:
    """Fetch one public page only after URL, redirect, DNS, and robots checks."""
    try:
        return _json_result(_fetch_page(url, max_chars))
    except WebResearchError as exc:
        return _error(exc.failure_class, exc.detail)


@tool("deep_research", args_schema=DeepResearchInput)
def deep_research(query: str = "", queries: list[str] | None = None, categories: str = "general", time_range: str = "", language: str = "en", safe_search: int = 1, max_results_per_query: int = 8, max_pages: int = 12, per_domain: int = 2, extract_pages: bool = True) -> str:
    """Run bounded multi-query local SearXNG research and optionally extract selected public pages."""
    try:
        query_list = _normalize_query_list(query, queries or [])
        bounded_pages = min(max(int(max_pages), 1), MAX_PAGES)
        source_map: dict[str, dict[str, Any]] = {}
        search_receipts: list[dict[str, Any]] = []
        for item in query_list:
            receipt = _search_searxng(item, categories=categories, time_range=time_range, language=language, safe_search=safe_search, max_results=max_results_per_query, domains=[])
            search_receipts.append({"query": item, "result_count": receipt["result_count"]})
            for source in receipt["results"]:
                source_map.setdefault(str(source["url"]), source)
        selected: list[dict[str, Any]] = []
        domains: dict[str, int] = {}
        for source in source_map.values():
            domain = str(source.get("domain") or "")
            if domains.get(domain, 0) >= max(1, min(int(per_domain), 5)):
                continue
            domains[domain] = domains.get(domain, 0) + 1
            selected.append(dict(source))
            if len(selected) >= bounded_pages:
                break
        failures: list[dict[str, Any]] = []
        if extract_pages:
            for source in selected:
                try:
                    page = _fetch_page(str(source["url"]), MAX_EXCERPT_CHARS)
                    source.update({"extraction_status": "ok", "title": page.get("title") or source.get("title"), "text": page.get("text", ""), "final_url": page.get("url", source["url"])})
                except WebResearchError as exc:
                    source["extraction_status"] = "error"
                    source["failure_class"] = exc.failure_class
                    failures.append({"url": source.get("url"), "failure_class": exc.failure_class})
        return _json_result({"status": "completed", "backend": "searxng-local", "queries": search_receipts, "query_count": len(query_list), "result_count": len(source_map), "selected_count": len(selected), "domain_count": len(domains), "sources": selected, "failures": failures, "synthesis": {"status": "not_requested", "model": None}})
    except WebResearchError as exc:
        return _error(exc.failure_class, exc.detail)


@tool("build_research_context", args_schema=BuildResearchContextInput)
def build_research_context(sources: list[dict[str, Any]] | None = None, context_text: str = "", max_chars: int = 30_000) -> str:
    """Build a bounded citation-preserving context packet from selected research sources."""
    limit = min(max(int(max_chars), 2_000), MAX_CONTEXT_CHARS)
    records = sources or []
    if not records and context_text.strip():
        try:
            parsed = json.loads(context_text)
        except (TypeError, ValueError):
            parsed = None
        if isinstance(parsed, dict) and isinstance(parsed.get("sources"), list):
            records = [item for item in parsed["sources"] if isinstance(item, dict)]
    sections: list[str] = []
    citations: list[dict[str, str]] = []
    for index, source in enumerate(records, start=1):
        if not isinstance(source, dict):
            continue
        url = str(source.get("final_url") or source.get("url") or "").strip()
        if not url:
            continue
        source_id = str(source.get("source_id") or f"S{index}")[:80]
        title = str(source.get("title") or source.get("domain") or "Untitled source")[:500]
        excerpt = str(source.get("text") or source.get("excerpt") or source.get("snippet") or "")
        if not excerpt:
            continue
        citations.append({"source_id": source_id, "title": title, "url": url})
        sections.append(f"[{source_id}] {title}\nURL: {url}\nEvidence excerpt:\n{excerpt[:MAX_EXCERPT_CHARS]}")
    if context_text.strip():
        sections.insert(0, f"[USER-CONTEXT]\n{context_text.strip()[:MAX_EXCERPT_CHARS]}")
    packet = "\n\n---\n\n".join(sections)
    truncated = len(packet) > limit
    packet = packet[:limit]
    packet_hash = hashlib.sha256(packet.encode("utf-8")).hexdigest()
    return _json_result({"status": "completed", "context_id": f"ctx-{packet_hash[:12]}", "packet_sha256": packet_hash, "char_count": len(packet), "truncated": truncated, "sources": citations, "citations": [item["source_id"] for item in citations], "context": packet, "provenance": "local-searxng-selected-public-pages"})


WEB_TOOLS = [search_web, extract_web_page, deep_research, build_research_context]
WEB_TOOL_CATALOG = [
    {"name": "search_web", "description": "Search the local loopback SearXNG JSON API and return normalized public sources.", "requires_approval": False, "scope": "local-search"},
    {"name": "extract_web_page", "description": "Fetch one selected public page with redirect, DNS, size, and robots enforcement.", "requires_approval": True, "scope": "public-web-read"},
    {"name": "deep_research", "description": "Run bounded multi-query SearXNG research with optional selected-page extraction.", "requires_approval": True, "scope": "public-web-research"},
    {"name": "build_research_context", "description": "Build a bounded citation-preserving context packet for downstream workflow nodes.", "requires_approval": False, "scope": "research-context"},
]
WEB_TOOL_NAMES = {item["name"] for item in WEB_TOOL_CATALOG}
WEB_APPROVAL_REQUIRED_TOOLS = {item["name"] for item in WEB_TOOL_CATALOG if item["requires_approval"]}


def web_preflight() -> dict[str, Any]:
    try:
        base = _searxng_url()
    except WebResearchError as exc:
        return {"ready": False, "failure_class": exc.failure_class, "detail": exc.detail}
    try:
        with httpx.Client(base_url=f"{base}/", timeout=1.5, trust_env=False, headers={"User-Agent": USER_AGENT}) as client:
            response = client.get("search", params={"q": "workspace readiness", "format": "json", "categories": "general", "safesearch": 1})
            if response.status_code >= 400:
                return {"ready": False, "failure_class": "search_backend_http_error", "detail": f"SearXNG returned HTTP {response.status_code}"}
        return {"ready": True, "backend": "searxng-local", "url": base}
    except httpx.TimeoutException:
        return {"ready": False, "failure_class": "search_backend_timeout", "detail": "local SearXNG preflight timed out"}
    except httpx.RequestError:
        return {"ready": False, "failure_class": "search_backend_unavailable", "detail": "local SearXNG is unavailable"}


__all__ = [
    "WEB_APPROVAL_REQUIRED_TOOLS",
    "WEB_TOOL_CATALOG",
    "WEB_TOOL_NAMES",
    "WEB_TOOLS",
    "build_research_context",
    "deep_research",
    "extract_web_page",
    "search_web",
    "web_preflight",
]
