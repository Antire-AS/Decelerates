"""Unit tests for the Bing Web Search adapter.

All HTTP is mocked via patch on requests.get so these tests run without
a real Bing resource or API key. Covers: unconfigured no-op, JSON parse,
PDF filter, network error swallowing.
"""

from unittest.mock import MagicMock, patch

from api.adapters.bing_search_adapter import BingSearchAdapter, BingSearchConfig


def _make(api_key: str = "k") -> BingSearchAdapter:
    return BingSearchAdapter(
        BingSearchConfig(
            endpoint="https://api.bing.microsoft.com/v7.0/search",
            api_key=api_key,
        )
    )


def test_empty_when_not_configured():
    adapter = BingSearchAdapter(BingSearchConfig(endpoint="", api_key=None))
    assert adapter.is_configured() is False
    assert adapter.search_pdfs("anything") == []


def test_extracts_pdf_urls_from_response():
    with patch("api.adapters.bing_search_adapter.requests.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "webPages": {
                    "value": [
                        {"url": "https://x.com/ar.pdf"},
                        {"url": "https://x.com/page.html"},
                        {"url": "https://y.com/report.PDF"},
                    ]
                }
            },
        )
        mock_get.return_value.raise_for_status = lambda: None
        result = _make().search_pdfs("DNB annual report")
    assert result == ["https://x.com/ar.pdf", "https://y.com/report.PDF"]


def test_appends_filetype_pdf_to_query():
    with patch("api.adapters.bing_search_adapter.requests.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {})
        mock_get.return_value.raise_for_status = lambda: None
        _make().search_pdfs("DNB annual report")
    call_params = mock_get.call_args.kwargs["params"]
    assert call_params["q"] == "DNB annual report filetype:pdf"
    assert call_params["responseFilter"] == "Webpages"


def test_sends_api_key_header():
    with patch("api.adapters.bing_search_adapter.requests.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {})
        mock_get.return_value.raise_for_status = lambda: None
        _make(api_key="secret-key").search_pdfs("test")
    headers = mock_get.call_args.kwargs["headers"]
    assert headers["Ocp-Apim-Subscription-Key"] == "secret-key"


def test_swallows_network_error():
    import requests as _requests

    with patch(
        "api.adapters.bing_search_adapter.requests.get",
        side_effect=_requests.ConnectionError("boom"),
    ):
        assert _make().search_pdfs("test") == []


def test_swallows_http_error():
    with patch("api.adapters.bing_search_adapter.requests.get") as mock_get:
        mock_resp = MagicMock(status_code=429)
        import requests

        mock_resp.raise_for_status = MagicMock(
            side_effect=requests.HTTPError("429 rate limited")
        )
        mock_get.return_value = mock_resp
        assert _make().search_pdfs("test") == []


def test_empty_response_returns_empty():
    with patch("api.adapters.bing_search_adapter.requests.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {})
        mock_get.return_value.raise_for_status = lambda: None
        assert _make().search_pdfs("test") == []


def test_no_webpages_field_returns_empty():
    with patch("api.adapters.bing_search_adapter.requests.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"relatedSearches": {"value": []}},
        )
        mock_get.return_value.raise_for_status = lambda: None
        assert _make().search_pdfs("test") == []


def test_max_results_caps_returned_urls():
    with patch("api.adapters.bing_search_adapter.requests.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "webPages": {
                    "value": [{"url": f"https://x.com/{i}.pdf"} for i in range(20)]
                }
            },
        )
        mock_get.return_value.raise_for_status = lambda: None
        result = _make().search_pdfs("test", max_results=5)
    assert len(result) == 5
