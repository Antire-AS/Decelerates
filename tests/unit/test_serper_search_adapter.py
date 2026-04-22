"""Unit tests for the Serper.dev Web Search adapter.

All HTTP is mocked via patch on requests.post so these tests run without
a real Serper API key. Covers: unconfigured no-op, JSON parse, PDF filter,
network error swallowing, HTTP error swallowing.
"""

from unittest.mock import MagicMock, patch

from api.adapters.serper_search_adapter import SerperSearchAdapter, SerperSearchConfig


def _make(api_key: str = "k") -> SerperSearchAdapter:
    return SerperSearchAdapter(SerperSearchConfig(api_key=api_key))


def test_empty_when_not_configured():
    adapter = SerperSearchAdapter(SerperSearchConfig(api_key=None))
    assert adapter.is_configured() is False
    assert adapter.search_pdfs("anything") == []


def test_extracts_pdf_urls_from_organic_results():
    with patch("api.adapters.serper_search_adapter.requests.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "organic": [
                    {"link": "https://x.com/ar.pdf", "title": "AR"},
                    {"link": "https://x.com/page.html", "title": "Page"},
                    {"link": "https://y.com/report.PDF", "title": "R"},
                ]
            },
        )
        mock_post.return_value.raise_for_status = lambda: None
        result = _make().search_pdfs("DNB annual report")
    assert result == ["https://x.com/ar.pdf", "https://y.com/report.PDF"]


def test_appends_filetype_pdf_to_query():
    with patch("api.adapters.serper_search_adapter.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {})
        mock_post.return_value.raise_for_status = lambda: None
        _make().search_pdfs("DNB annual report")
    body = mock_post.call_args.kwargs["json"]
    assert body["q"] == "DNB annual report filetype:pdf"
    assert body["gl"] == "no"


def test_sends_api_key_header():
    with patch("api.adapters.serper_search_adapter.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {})
        mock_post.return_value.raise_for_status = lambda: None
        _make(api_key="secret-key").search_pdfs("test")
    headers = mock_post.call_args.kwargs["headers"]
    assert headers["X-API-KEY"] == "secret-key"
    assert headers["Content-Type"] == "application/json"


def test_swallows_network_error():
    import requests as _requests

    with patch(
        "api.adapters.serper_search_adapter.requests.post",
        side_effect=_requests.ConnectionError("boom"),
    ):
        assert _make().search_pdfs("test") == []


def test_swallows_http_error():
    with patch("api.adapters.serper_search_adapter.requests.post") as mock_post:
        import requests

        mock_resp = MagicMock(status_code=429)
        mock_resp.raise_for_status = MagicMock(
            side_effect=requests.HTTPError("429 rate limited")
        )
        mock_post.return_value = mock_resp
        assert _make().search_pdfs("test") == []


def test_empty_response_returns_empty():
    with patch("api.adapters.serper_search_adapter.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {})
        mock_post.return_value.raise_for_status = lambda: None
        assert _make().search_pdfs("test") == []


def test_no_organic_field_returns_empty():
    with patch("api.adapters.serper_search_adapter.requests.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"answerBox": {"text": "foo"}},
        )
        mock_post.return_value.raise_for_status = lambda: None
        assert _make().search_pdfs("test") == []


def test_max_results_caps_returned_urls():
    with patch("api.adapters.serper_search_adapter.requests.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "organic": [{"link": f"https://x.com/{i}.pdf"} for i in range(20)]
            },
        )
        mock_post.return_value.raise_for_status = lambda: None
        result = _make().search_pdfs("test", max_results=5)
    assert len(result) == 5
