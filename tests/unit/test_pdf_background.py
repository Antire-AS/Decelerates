"""Unit tests for api/services/pdf_background.py — URL validation + PdfExtractService.

Mocks requests.head for URL validation and DB session for service class.
No real network, Gemini, or PostgreSQL required.
"""
import sys
from unittest.mock import MagicMock, patch


# Stub heavy transitive deps before any api.* import
sys.modules.setdefault("api.rag_chain", MagicMock())

# Need to stub telemetry and pdf sub-modules BEFORE importing pdf_background
_mock_telemetry = MagicMock()
sys.modules.setdefault("api.telemetry", _mock_telemetry)
sys.modules.setdefault("api.services.pdf_agents", MagicMock())
sys.modules.setdefault("api.services.pdf_history", MagicMock())
sys.modules.setdefault("api.services.pdf_parse", MagicMock())
sys.modules.setdefault("api.services.pdf_web", MagicMock())

from api.services.pdf_background import _validate_pdf_urls, PdfExtractService


# -- _validate_pdf_urls --------------------------------------------------------

@patch("api.services.pdf_background.requests")
def test_validate_pdf_urls_keeps_200(mock_requests):
    mock_requests.head.return_value = MagicMock(status_code=200)
    items = [{"pdf_url": "https://example.com/report.pdf", "year": 2024}]
    result = _validate_pdf_urls(items)
    assert len(result) == 1


@patch("api.services.pdf_background.requests")
def test_validate_pdf_urls_drops_404(mock_requests):
    mock_requests.head.return_value = MagicMock(status_code=404)
    items = [{"pdf_url": "https://example.com/gone.pdf", "year": 2024}]
    result = _validate_pdf_urls(items)
    assert len(result) == 0


@patch("api.services.pdf_background.requests")
def test_validate_pdf_urls_drops_on_exception(mock_requests):
    mock_requests.head.side_effect = ConnectionError("timeout")
    items = [{"pdf_url": "https://example.com/slow.pdf", "year": 2024}]
    result = _validate_pdf_urls(items)
    assert len(result) == 0


@patch("api.services.pdf_background.requests")
def test_validate_pdf_urls_mixed_results(mock_requests):
    responses = [MagicMock(status_code=200), MagicMock(status_code=403)]
    mock_requests.head.side_effect = responses
    items = [
        {"pdf_url": "https://example.com/ok.pdf", "year": 2023},
        {"pdf_url": "https://example.com/denied.pdf", "year": 2024},
    ]
    result = _validate_pdf_urls(items)
    assert len(result) == 1
    assert result[0]["year"] == 2023


def test_validate_pdf_urls_empty_list():
    assert _validate_pdf_urls([]) == []


# -- PdfExtractService ---------------------------------------------------------

@patch("api.services.pdf_background.fetch_history_from_pdf")
def test_service_fetch_history_delegates(mock_fetch):
    mock_fetch.return_value = {"year": 2024}
    db = MagicMock()
    svc = PdfExtractService(db)
    svc.fetch_history_from_pdf("123456789", "https://x.pdf", 2024, "annual")
    mock_fetch.assert_called_once_with("123456789", "https://x.pdf", 2024, "annual", db)


@patch("api.services.pdf_background._get_full_history")
def test_service_get_full_history_delegates(mock_hist):
    mock_hist.return_value = [{"year": 2024}]
    db = MagicMock()
    PdfExtractService(db).get_full_history("123456789")
    mock_hist.assert_called_once_with("123456789", db)


@patch("api.services.pdf_background._parse_financials_from_pdf")
def test_service_parse_financials_delegates(mock_parse):
    mock_parse.return_value = {"revenue": 1000}
    db = MagicMock()
    PdfExtractService(db).parse_financials_from_pdf("https://x.pdf", "123", 2024)
    mock_parse.assert_called_once_with("https://x.pdf", "123", 2024)
