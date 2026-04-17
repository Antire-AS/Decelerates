"""Unit tests for api/services/pdf_web.py — DuckDuckGo search and HTML scraping.

All HTTP requests and Playwright calls are mocked. No network, no browser.
"""

import sys
from unittest.mock import MagicMock, patch


sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.services.pdf_web import (
    _extract_pdfs_from_html,
    _ddg_query,
    _search_for_pdfs,
    _search_all_annual_pdfs,
    _ddg_search_results,
    _fetch_html_requests,
    _parse_html_for_agent,
    _fetch_url_content,
    _parse_agent_pdf_list,
)


# ── _extract_pdfs_from_html ──────────────────────────────────────────────────


def test_extract_pdfs_finds_direct_pdf_urls():
    html = '<a href="https://example.com/report.pdf">Download</a>'
    result = _extract_pdfs_from_html(html)
    assert "https://example.com/report.pdf" in result


def test_extract_pdfs_finds_uddg_encoded_urls():
    html = 'href="?uddg=https%3A%2F%2Fexample.com%2Fdoc.pdf"'
    result = _extract_pdfs_from_html(html)
    assert "https://example.com/doc.pdf" in result


def test_extract_pdfs_deduplicates():
    html = (
        '<a href="https://example.com/a.pdf">1</a>'
        '<a href="https://example.com/a.pdf">2</a>'
    )
    result = _extract_pdfs_from_html(html)
    assert result.count("https://example.com/a.pdf") == 1


def test_extract_pdfs_ignores_non_pdf_uddg():
    html = 'href="?uddg=https%3A%2F%2Fexample.com%2Fpage.html"'
    result = _extract_pdfs_from_html(html)
    assert result == []


# ── _ddg_query ───────────────────────────────────────────────────────────────


def test_ddg_query_returns_pdf_urls():
    html = '<a href="https://corp.no/annual2023.pdf">report</a>'
    mock_resp = MagicMock()
    mock_resp.text = html
    with patch("api.services.pdf_web.requests.get", return_value=mock_resp):
        result = _ddg_query("test query")
    assert len(result) == 1
    assert "annual2023.pdf" in result[0]


def test_ddg_query_returns_empty_on_timeout():
    import requests as _req

    with patch("api.services.pdf_web.requests.get", side_effect=_req.Timeout):
        result = _ddg_query("timeout query")
    assert result == []


def test_ddg_query_returns_empty_on_http_error():
    import requests as _req

    with patch("api.services.pdf_web.requests.get", side_effect=_req.HTTPError):
        result = _ddg_query("fail query")
    assert result == []


# ── _search_for_pdfs ─────────────────────────────────────────────────────────


def test_search_for_pdfs_uses_site_query_when_hjemmeside_provided():
    calls = []

    def fake_ddg(query):
        calls.append(query)
        return ["https://example.com/ar.pdf"]

    with patch("api.services.pdf_web._ddg_query", side_effect=fake_ddg):
        result = _search_for_pdfs("DNB ASA", "https://www.dnb.no", 2023)
    assert any("site:www.dnb.no" in q for q in calls)
    assert len(result) >= 1


def test_search_for_pdfs_works_without_hjemmeside():
    with patch("api.services.pdf_web._ddg_query", return_value=[]):
        result = _search_for_pdfs("DNB ASA", None, 2023)
    assert result == []


# ── _search_all_annual_pdfs ──────────────────────────────────────────────────


def test_search_all_annual_pdfs_caps_at_20():
    urls = [f"https://example.com/{i}.pdf" for i in range(30)]
    with patch("api.services.pdf_web._ddg_query", return_value=urls):
        result = _search_all_annual_pdfs("Test AS", None)
    assert len(result) <= 20


# ── _ddg_search_results ──────────────────────────────────────────────────────


def test_ddg_search_results_parses_html():
    html = (
        '<a class="result__a" href="?uddg=https%3A%2F%2Fexample.com%2Fpage">Example Title</a>'
        '<span class="result__snippet">A snippet here</span>'
    )
    mock_resp = MagicMock()
    mock_resp.text = html
    with patch("api.services.pdf_web.requests.get", return_value=mock_resp):
        results = _ddg_search_results("test")
    assert len(results) == 1
    assert results[0]["title"] == "Example Title"
    assert results[0]["url"] == "https://example.com/page"
    assert results[0]["snippet"] == "A snippet here"


def test_ddg_search_results_returns_empty_on_timeout():
    import requests as _req

    with patch("api.services.pdf_web.requests.get", side_effect=_req.Timeout):
        assert _ddg_search_results("q") == []


# ── _fetch_html_requests ─────────────────────────────────────────────────────


def test_fetch_html_requests_returns_text():
    mock_resp = MagicMock()
    mock_resp.text = "<html>hello</html>"
    with patch("api.services.pdf_web.requests.get", return_value=mock_resp):
        result = _fetch_html_requests("https://example.com")
    assert result == "<html>hello</html>"


def test_fetch_html_requests_returns_none_on_timeout():
    import requests as _req

    with patch("api.services.pdf_web.requests.get", side_effect=_req.Timeout):
        assert _fetch_html_requests("https://example.com") is None


# ── _fetch_html (Playwright → requests fallback) ────────────────────────────


# ── _parse_html_for_agent ────────────────────────────────────────────────────


def test_parse_html_for_agent_extracts_pdf_links():
    html = '<a href="https://cdn.example.com/report.pdf">report</a>'
    result = _parse_html_for_agent(html, "https://example.com")
    assert "https://cdn.example.com/report.pdf" in result["pdf_links"]


def test_parse_html_for_agent_extracts_ir_page_links():
    html = '<a href="/investor-relations">IR</a><a href="/contact">Contact</a>'
    result = _parse_html_for_agent(html, "https://example.com")
    assert "https://example.com/investor-relations" in result["page_links"]
    # /contact has no IR keywords, should not be included
    assert all("contact" not in link for link in result["page_links"])


def test_parse_html_for_agent_truncates_text():
    html = "<p>" + "x" * 5000 + "</p>"
    result = _parse_html_for_agent(html, "https://example.com")
    assert len(result["text"]) <= 3000


# ── _fetch_url_content ───────────────────────────────────────────────────────


def test_fetch_url_content_returns_error_on_fetch_failure():
    with patch("api.services.pdf_web._fetch_html", return_value=None):
        result = _fetch_url_content("https://example.com")
    assert "Error" in result["text"]
    assert result["pdf_links"] == []


# ── _parse_agent_pdf_list ────────────────────────────────────────────────────


def test_parse_agent_pdf_list_extracts_valid_entries():
    raw = (
        '[{"year": 2023, "pdf_url": "https://example.com/ar.pdf", "label": "AR 2023"}]'
    )
    result = _parse_agent_pdf_list(raw)
    assert len(result) == 1
    assert result[0]["year"] == 2023


def test_parse_agent_pdf_list_strips_markdown_fences():
    raw = (
        '```json\n[{"year": 2024, "pdf_url": "https://x.com/r.pdf", "label": "R"}]\n```'
    )
    result = _parse_agent_pdf_list(raw)
    assert len(result) == 1


def test_parse_agent_pdf_list_rejects_invalid_entries():
    raw = '[{"year": "not-int", "pdf_url": "https://x.com/r.pdf"}]'
    result = _parse_agent_pdf_list(raw)
    assert result == []


def test_parse_agent_pdf_list_returns_empty_for_empty_input():
    assert _parse_agent_pdf_list("") == []
    assert _parse_agent_pdf_list(None) == []


def test_parse_agent_pdf_list_rejects_non_http_urls():
    raw = '[{"year": 2023, "pdf_url": "ftp://x.com/r.pdf", "label": "R"}]'
    result = _parse_agent_pdf_list(raw)
    assert result == []
