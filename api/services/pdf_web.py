"""Web fetching utilities for PDF discovery — DuckDuckGo search and HTML scraping."""

import logging
import re
from typing import Any, Dict, List, Optional

import requests

from api.constants import PDF_URL_LIMIT

logger = logging.getLogger(__name__)

_DDG_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


# ── DuckDuckGo search ─────────────────────────────────────────────────────────


def _extract_pdfs_from_html(html: str) -> List[str]:
    """Extract PDF links from DuckDuckGo HTML (direct URLs + uddg= encoded links)."""
    found = []
    found += re.findall(r"https?://[^\s\"'<>]+\.pdf(?:[?#][^\s\"'<>]*)?", html)
    encoded = re.findall(r"uddg=(https?%3A%2F%2F[^&\"]+)", html)
    for u in encoded:
        decoded = requests.utils.unquote(u)
        if ".pdf" in decoded.lower():
            found.append(decoded)
    return list(dict.fromkeys(found))


def _ddg_query(query: str) -> List[str]:
    """Run a single DuckDuckGo HTML query and return PDF URLs found."""
    try:
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": _DDG_UA},
            timeout=15,
        )
        return _extract_pdfs_from_html(resp.text)
    except requests.Timeout:
        logger.warning("[ddg] Timeout querying DuckDuckGo for %r", query)
        return []
    except requests.HTTPError as exc:
        logger.warning("[ddg] HTTP error querying DuckDuckGo for %r: %s", query, exc)
        return []
    except Exception as exc:
        logger.error("[ddg] Unexpected error for query %r: %s", query, exc)
        return []


def _search_for_pdfs(navn: str, hjemmeside: Optional[str], year: int) -> List[str]:
    """Search DuckDuckGo HTML for annual report PDF URLs for a given company + year."""
    queries = []
    if hjemmeside:
        domain = re.sub(r"^https?://", "", hjemmeside).rstrip("/").split("/")[0]
        queries.append(f'site:{domain} "annual report" {year} filetype:pdf')
    queries.append(f"{navn} annual report {year} filetype:pdf")

    all_urls: List[str] = []
    for query in queries:
        if len(all_urls) >= PDF_URL_LIMIT:
            break
        all_urls += _ddg_query(query)
        all_urls = list(dict.fromkeys(all_urls))

    return all_urls[:PDF_URL_LIMIT]


def _build_search_queries(navn: str, hjemmeside: Optional[str]) -> List[str]:
    """Build the 1-2 search queries to try for a company's annual reports."""
    queries = []
    if hjemmeside:
        domain = re.sub(r"^https?://", "", hjemmeside).rstrip("/").split("/")[0]
        queries.append(f'site:{domain} "annual report"')
    queries.append(f'{navn} "annual report"')
    return queries


def _port_search_pdfs(queries: List[str]) -> List[str]:
    """Try the configured WebSearchPort adapter (Serper.dev) for each query.
    Returns [] if not configured or errors — caller falls through to DDG."""
    try:
        from api.container import resolve
        from api.ports.driven.web_search_port import WebSearchPort

        search: WebSearchPort = resolve(WebSearchPort)
        if search is None or not search.is_configured():
            return []
        urls: List[str] = []
        for query in queries:
            urls += search.search_pdfs(query, max_results=20)
            urls = list(dict.fromkeys(urls))
            if len(urls) >= 20:
                break
        return urls[:20]
    except Exception as exc:  # pragma: no cover - defence in depth
        logger.warning("[search] Port path errored, falling back to DDG: %s", exc)
        return []


def _search_all_annual_pdfs(navn: str, hjemmeside: Optional[str]) -> List[str]:
    """Search for all annual report PDFs for a company (no year filter).

    Tries the configured WebSearchPort (Serper.dev by default) first; falls
    back to DDG HTML scrape if not configured. DDG has been returning HTTP 202
    anti-bot pages since ~2026-04 and is effectively dead — it's kept only
    as a local-dev convenience for developers without a Serper key.
    """
    queries = _build_search_queries(navn, hjemmeside)

    urls = _port_search_pdfs(queries)
    if urls:
        return urls

    # DDG fallback — currently broken (HTTP 202). Kept for local dev.
    all_urls: List[str] = []
    for query in queries:
        all_urls += _ddg_query(f"{query} filetype:pdf")
        all_urls = list(dict.fromkeys(all_urls))
        if len(all_urls) >= 20:
            break
    return all_urls[:20]


def _ddg_search_results(query: str) -> List[Dict[str, Any]]:
    """General DuckDuckGo search — returns [{title, url, snippet}], not PDF-filtered."""
    try:
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": _DDG_UA},
            timeout=15,
        )
        html = resp.text
    except requests.Timeout:
        logger.warning("[ddg] Timeout on general search for %r", query)
        return []
    except requests.HTTPError as exc:
        logger.warning("[ddg] HTTP error on general search for %r: %s", query, exc)
        return []
    except Exception as exc:
        logger.error("[ddg] Unexpected error on general search for %r: %s", query, exc)
        return []

    results = []
    for m in re.finditer(
        r'class=["\']result__a["\'][^>]*href=["\']([^"\']+)["\'][^>]*>([^<]+)<', html
    ):
        raw_href, title = m.group(1), m.group(2).strip()
        uddg = re.search(r"uddg=(https?%3A%2F%2F[^&\"]+)", raw_href)
        url = requests.utils.unquote(uddg.group(1)) if uddg else raw_href
        results.append({"title": title, "url": url, "snippet": ""})

    snippets = re.findall(r'class=["\']result__snippet["\'][^>]*>([^<]+)<', html)
    for i, snip in enumerate(snippets):
        if i < len(results):
            results[i]["snippet"] = snip.strip()

    return results[:8]


# ── HTML fetching (Playwright + requests fallback) ─────────────────────────────


def _fetch_html_requests(url: str) -> Optional[str]:
    """Requests fallback for _fetch_html when Playwright is unavailable."""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; BrokerAccelerator/1.0)"},
            timeout=12,
        )
        return resp.text
    except requests.Timeout:
        logger.warning("[fetch_html] Timeout fetching %s", url)
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            logger.warning("[fetch_html] Not found (404): %s", url)
        else:
            logger.error("[fetch_html] HTTP error fetching %s: %s", url, exc)
    except Exception as exc:
        logger.error("[fetch_html] Unexpected error fetching %s: %s", url, exc)
    return None


def _fetch_html(url: str) -> Optional[str]:
    """Fetch raw HTML — Playwright first, requests fallback."""
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                ctx = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                )
                page = ctx.new_page()
                try:
                    page.goto(url, timeout=20000, wait_until="domcontentloaded")
                    page.wait_for_load_state("networkidle", timeout=10000)
                except PWTimeout:
                    pass  # use whatever content loaded so far
                return page.content()
            finally:
                browser.close()
    except ImportError:
        pass  # Playwright not installed
    except Exception as exc:
        logger.warning("[fetch_html] Playwright failed for %s: %s", url, exc)
    return _fetch_html_requests(url)


def _parse_html_for_agent(html: str, base_url: str) -> Dict[str, Any]:
    """Extract text, PDF links, and IR-relevant page links from raw HTML."""
    from urllib.parse import urlparse

    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()[:3000]

    pdf_links = list(
        dict.fromkeys(
            re.findall(r'https?://[^\s"\'<>]+\.pdf(?:[?#][^\s"\'<>]*)?', html, re.I)
        )
    )[:20]

    ir_keywords = re.compile(
        r"annual|report|arsrapport|investor|ir\b|financial|results|downloads", re.I
    )
    base = urlparse(base_url)
    page_links = []
    for m in re.finditer(r'href=["\']([^"\']+)["\']', html):
        href = m.group(1)
        if not ir_keywords.search(href):
            continue
        if href.startswith("http"):
            page_links.append(href)
        elif href.startswith("/"):
            page_links.append(f"{base.scheme}://{base.netloc}{href}")
    page_links = list(dict.fromkeys(page_links))[:15]

    return {"text": text, "pdf_links": pdf_links, "page_links": page_links}


def _fetch_url_content(url: str) -> Dict[str, Any]:
    """Fetch a URL and return {text, pdf_links, page_links} for the agent."""
    html = _fetch_html(url)
    if not html:
        return {"text": "Error: could not fetch URL", "pdf_links": [], "page_links": []}
    return _parse_html_for_agent(html, url)


def _parse_agent_pdf_list(raw: str) -> List[Dict[str, Any]]:
    """Extract and validate a JSON array of {year, pdf_url, label} from agent output."""
    import json

    if not raw:
        return []
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
    for pattern in (cleaned, re.search(r"\[.*\]", cleaned, re.DOTALL)):
        text = (
            pattern
            if isinstance(pattern, str)
            else (pattern.group() if pattern else None)
        )
        if not text:
            continue
        try:
            result = json.loads(text)
            if isinstance(result, list):
                return [
                    r
                    for r in result
                    if isinstance(r.get("year"), int)
                    and isinstance(r.get("pdf_url"), str)
                    and r["pdf_url"].startswith("http")
                ]
        except (json.JSONDecodeError, ValueError):
            continue
    return []
