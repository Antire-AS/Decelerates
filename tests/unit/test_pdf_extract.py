"""Unit tests for services/pdf_extract.py — pure parsing functions, no HTTP."""
import pytest

from api.services.pdf_extract import _parse_json_financials


def test_parse_json_valid():
    raw = '{"revenue": 1000000, "net_result": 50000, "equity": 200000, "total_assets": 500000}'
    result = _parse_json_financials(raw)
    assert result is not None
    assert result["revenue"] == 1000000
    assert result["net_result"] == 50000


def test_parse_json_markdown_fenced():
    raw = "```json\n{\"revenue\": 2000000, \"equity\": 100000, \"total_assets\": 400000}\n```"
    result = _parse_json_financials(raw)
    assert result is not None
    assert result["revenue"] == 2000000


def test_parse_json_embedded_in_text():
    raw = 'Here is the data: {"revenue": 3000000, "equity": 150000, "total_assets": 600000} — done.'
    result = _parse_json_financials(raw)
    assert result is not None
    assert result["revenue"] == 3000000


def test_parse_json_invalid_returns_none():
    raw = "This is not JSON at all, no braces here."
    result = _parse_json_financials(raw)
    assert result is None


def test_parse_json_equity_ratio_computed():
    raw = '{"revenue": 500000, "equity": 100000, "total_assets": 500000}'
    result = _parse_json_financials(raw)
    assert result is not None
    assert result["equity_ratio"] == pytest.approx(0.2)


def test_parse_json_equity_ratio_none_when_no_assets():
    raw = '{"revenue": 500000, "equity": 100000, "total_assets": 0}'
    result = _parse_json_financials(raw)
    assert result is not None
    assert result["equity_ratio"] is None
