"""Unit tests for api/services/pdf_parse.py — JSON parsing, Gemini extraction.

Pure static tests — all HTTP and Gemini calls are mocked.
_parse_json_financials basics are already in test_pdf_extract.py; this file
covers the remaining functions and edge cases.
"""
import os
from unittest.mock import MagicMock, patch

import pytest
import requests

from api.services.pdf_parse import (
    _download_pdf_bytes,
    _gemini_api_keys,
    _parse_financials_from_pdf,
    _parse_json_financials,
    _sanity_check_financials,
    _try_gemini_with_retry,
)


# ── _parse_json_financials (edge cases beyond test_pdf_extract.py) ─────────────

def test_parse_json_both_equity_and_assets_none_gives_none_ratio():
    raw = '{"revenue": 500000}'
    result = _parse_json_financials(raw)
    assert result is not None
    assert result["equity_ratio"] is None


def test_parse_json_zero_equity_with_assets_gives_zero_ratio():
    raw = '{"revenue": 500000, "equity": 0, "total_assets": 1000000}'
    result = _parse_json_financials(raw)
    assert result is not None
    assert result["equity_ratio"] is None  # equity is falsy (0), so ratio is None


def test_parse_json_negative_equity_computes_ratio():
    raw = '{"revenue": 500000, "equity": -100000, "total_assets": 500000}'
    result = _parse_json_financials(raw)
    assert result is not None
    assert result["equity_ratio"] == pytest.approx(-0.2)


def test_parse_json_broken_inner_json_returns_none():
    raw = '{"revenue": 500000, "equity: broken'
    result = _parse_json_financials(raw)
    assert result is None


def test_parse_json_preserves_extra_fields():
    raw = '{"revenue": 100, "equity": 50, "total_assets": 200, "currency": "SEK", "antall_ansatte": 42}'
    result = _parse_json_financials(raw)
    assert result["currency"] == "SEK"
    assert result["antall_ansatte"] == 42


# ── _sanity_check_financials ──────────────────────────────────────────────────

def test_sanity_check_all_none_passes():
    assert _sanity_check_financials({}) is True


def test_sanity_check_valid_data_passes():
    data = {"revenue": 1_000_000, "net_result": 50_000, "equity": 200_000, "total_assets": 800_000}
    assert _sanity_check_financials(data) is True


def test_sanity_check_net_result_exceeds_revenue_fails():
    # |net_result| > revenue is implausible
    data = {"revenue": 100_000, "net_result": 500_000, "equity": 100_000, "total_assets": 200_000}
    assert _sanity_check_financials(data) is False


def test_sanity_check_negative_net_result_within_revenue_passes():
    data = {"revenue": 1_000_000, "net_result": -200_000, "equity": 100_000, "total_assets": 500_000}
    assert _sanity_check_financials(data) is True


def test_sanity_check_equity_exceeds_assets_fails():
    data = {"revenue": 100_000, "net_result": 10_000, "equity": 900_000, "total_assets": 500_000}
    assert _sanity_check_financials(data) is False


def test_sanity_check_equity_equals_assets_passes():
    # Borderline: equity == assets is technically allowed
    data = {"equity": 500_000, "total_assets": 500_000}
    assert _sanity_check_financials(data) is True


def test_sanity_check_missing_revenue_skips_net_check():
    # No revenue → net_result check is skipped
    data = {"net_result": 999_000, "equity": 100_000, "total_assets": 500_000}
    assert _sanity_check_financials(data) is True


# ── _gemini_api_keys ──────────────────────────────────────────────────────────

def test_gemini_api_keys_returns_configured_keys():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "key1", "GEMINI_API_KEY_2": "key2"}, clear=False):
        keys = _gemini_api_keys()
    assert "key1" in keys
    assert "key2" in keys


def test_gemini_api_keys_skips_placeholder_value():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "your_key_here"}, clear=False):
        keys = _gemini_api_keys()
    assert "your_key_here" not in keys


def test_gemini_api_keys_deduplicates():
    with patch.dict(os.environ, {
        "GEMINI_API_KEY": "same_key",
        "GEMINI_API_KEY_2": "same_key",
        "GEMINI_API_KEY_3": "other_key",
    }, clear=False):
        keys = _gemini_api_keys()
    assert keys.count("same_key") == 1


def test_gemini_api_keys_returns_empty_when_none_set():
    env_without_keys = {k: v for k, v in os.environ.items()
                        if k not in ("GEMINI_API_KEY", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3")}
    with patch.dict(os.environ, env_without_keys, clear=True):
        keys = _gemini_api_keys()
    assert keys == []


# ── _download_pdf_bytes ───────────────────────────────────────────────────────

def test_download_pdf_bytes_returns_content_on_success():
    mock_resp = MagicMock()
    mock_resp.content = b"PDF bytes here"
    mock_resp.raise_for_status.return_value = None
    with patch("api.services.pdf_parse.requests.get", return_value=mock_resp):
        result = _download_pdf_bytes("http://example.com/r.pdf")
    assert result == b"PDF bytes here"


def test_download_pdf_bytes_returns_none_on_timeout():
    with patch("api.services.pdf_parse.requests.get", side_effect=requests.Timeout):
        result = _download_pdf_bytes("http://slow.example.com/r.pdf")
    assert result is None


def test_download_pdf_bytes_returns_none_on_404():
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    exc = requests.HTTPError()
    exc.response = mock_resp
    mock_resp.raise_for_status.side_effect = exc
    with patch("api.services.pdf_parse.requests.get", return_value=mock_resp):
        result = _download_pdf_bytes("http://example.com/missing.pdf")
    assert result is None


def test_download_pdf_bytes_returns_none_on_non_404_http_error():
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    exc = requests.HTTPError()
    exc.response = mock_resp
    mock_resp.raise_for_status.side_effect = exc
    with patch("api.services.pdf_parse.requests.get", return_value=mock_resp):
        result = _download_pdf_bytes("http://example.com/server-error.pdf")
    assert result is None


def test_download_pdf_bytes_returns_none_on_unexpected_exception():
    with patch("api.services.pdf_parse.requests.get", side_effect=ConnectionError("no route")):
        result = _download_pdf_bytes("http://unreachable.example.com/r.pdf")
    assert result is None


# ── _try_gemini_with_retry ────────────────────────────────────────────────────

@patch("api.services.pdf_parse._sanity_check_financials", return_value=True)
@patch("api.services.pdf_parse._parse_json_financials", return_value={"revenue": 1_000_000, "equity_ratio": 0.3})
@patch("api.services.pdf_parse._try_gemini", return_value='{"revenue": 1000000}')
def test_try_gemini_with_retry_returns_on_first_pass(mock_try, mock_parse, mock_sanity):
    result = _try_gemini_with_retry(b"pdf", "123", 2023)
    assert result == {"revenue": 1_000_000, "equity_ratio": 0.3}
    assert mock_try.call_count == 1


@patch("api.services.pdf_parse._try_gemini", return_value=None)
def test_try_gemini_with_retry_returns_none_when_gemini_fails(mock_try):
    result = _try_gemini_with_retry(b"pdf", "123", 2023)
    assert result is None


@patch("api.services.pdf_parse._sanity_check_financials", side_effect=[False, True])
@patch("api.services.pdf_parse._parse_json_financials", return_value={"revenue": 500_000, "equity_ratio": 0.1})
@patch("api.services.pdf_parse._try_gemini", return_value='{"revenue": 500000}')
def test_try_gemini_with_retry_retries_on_sanity_fail(mock_try, mock_parse, mock_sanity):
    result = _try_gemini_with_retry(b"pdf", "123", 2023)
    assert result is not None
    assert mock_try.call_count == 2


@patch("api.services.pdf_parse._sanity_check_financials", return_value=False)
@patch("api.services.pdf_parse._parse_json_financials", return_value={"revenue": 500_000})
@patch("api.services.pdf_parse._try_gemini", return_value='{"revenue": 500000}')
def test_try_gemini_with_retry_returns_none_when_both_attempts_fail_sanity(mock_try, mock_parse, mock_sanity):
    result = _try_gemini_with_retry(b"pdf", "123", 2023)
    assert result is None


@patch("api.services.pdf_parse._parse_json_financials", return_value=None)
@patch("api.services.pdf_parse._try_gemini", return_value="not valid json")
def test_try_gemini_with_retry_returns_none_when_parse_fails(mock_try, mock_parse):
    result = _try_gemini_with_retry(b"pdf", "123", 2023)
    assert result is None


# ── _parse_financials_from_pdf ────────────────────────────────────────────────

@patch("api.services.pdf_parse._download_pdf_bytes", return_value=None)
def test_parse_financials_from_pdf_returns_none_when_download_fails(mock_dl):
    result = _parse_financials_from_pdf("http://example.com/r.pdf", "123", 2023)
    assert result is None
    mock_dl.assert_called_once()


@patch("api.services.pdf_parse._try_gemini_with_retry",
       return_value={"revenue": 1_000_000, "equity_ratio": 0.3})
@patch("api.services.pdf_parse._download_pdf_bytes", return_value=b"pdf bytes")
def test_parse_financials_from_pdf_returns_gemini_result(mock_dl, mock_gemini):
    result = _parse_financials_from_pdf("http://example.com/r.pdf", "123", 2023)
    assert result == {"revenue": 1_000_000, "equity_ratio": 0.3}
    mock_gemini.assert_called_once()


@patch("api.services.pdf_parse._try_gemini_with_retry", return_value=None)
@patch("api.services.pdf_parse._download_pdf_bytes", return_value=b"pdf bytes")
def test_parse_financials_from_pdf_returns_none_when_gemini_fails(mock_dl, mock_gemini):
    """Phase 3 — pdfplumber fallback removed; Gemini failure now propagates as None."""
    result = _parse_financials_from_pdf("http://example.com/r.pdf", "123", 2023)
    assert result is None
