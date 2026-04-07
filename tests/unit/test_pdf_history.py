"""Unit tests for api/services/pdf_history.py — DB upsert and merged history retrieval.

Pure static tests — uses MagicMock DB; no real infrastructure required.
"""
from unittest.mock import MagicMock, patch

import pytest

from api.domain.exceptions import PdfExtractionError
from api.services.pdf_history import (
    _get_full_history,
    _upsert_history_row,
    fetch_history_from_pdf,
)


def _mock_db():
    return MagicMock()


def _mock_history_row(**kwargs):
    row = MagicMock()
    row.year = kwargs.get("year", 2023)
    row.source = kwargs.get("source", "pdf")
    row.currency = kwargs.get("currency", "NOK")
    row.revenue = kwargs.get("revenue", 1_000_000)
    row.net_result = kwargs.get("net_result", 50_000)
    row.equity = kwargs.get("equity", 200_000)
    row.total_assets = kwargs.get("total_assets", 500_000)
    row.equity_ratio = kwargs.get("equity_ratio", 0.4)
    row.short_term_debt = kwargs.get("short_term_debt", 100_000)
    row.long_term_debt = kwargs.get("long_term_debt", 150_000)
    row.antall_ansatte = kwargs.get("antall_ansatte", 25)
    row.raw = kwargs.get("raw", None)
    row.pdf_url = kwargs.get("pdf_url", "http://example.com/r.pdf")
    return row


def _sample_parsed() -> dict:
    return {
        "revenue": 2_000_000,
        "net_result": 100_000,
        "equity": 400_000,
        "total_assets": 1_000_000,
        "equity_ratio": 0.4,
        "short_term_debt": 50_000,
        "long_term_debt": 200_000,
        "antall_ansatte": 30,
        "currency": "NOK",
    }


# ── _upsert_history_row ───────────────────────────────────────────────────────

def test_upsert_history_row_sets_source_pdf():
    existing = MagicMock()
    _upsert_history_row(existing, _sample_parsed(), "http://example.com/r.pdf")
    assert existing.source == "pdf"


def test_upsert_history_row_sets_pdf_url():
    existing = MagicMock()
    _upsert_history_row(existing, _sample_parsed(), "http://example.com/annual.pdf")
    assert existing.pdf_url == "http://example.com/annual.pdf"


def test_upsert_history_row_sets_all_financial_fields():
    existing = MagicMock()
    parsed = _sample_parsed()
    _upsert_history_row(existing, parsed, "http://example.com/r.pdf")
    assert existing.revenue == 2_000_000
    assert existing.net_result == 100_000
    assert existing.equity == 400_000
    assert existing.total_assets == 1_000_000
    assert existing.equity_ratio == 0.4
    assert existing.short_term_debt == 50_000
    assert existing.long_term_debt == 200_000
    assert existing.antall_ansatte == 30
    assert existing.currency == "NOK"


def test_upsert_history_row_defaults_currency_to_nok():
    existing = MagicMock()
    parsed = {k: v for k, v in _sample_parsed().items() if k != "currency"}
    _upsert_history_row(existing, parsed, "http://example.com/r.pdf")
    assert existing.currency == "NOK"


def test_upsert_history_row_stores_raw_dict():
    existing = MagicMock()
    parsed = _sample_parsed()
    _upsert_history_row(existing, parsed, "http://example.com/r.pdf")
    assert existing.raw == parsed


def test_upsert_history_row_handles_missing_optional_fields():
    existing = MagicMock()
    minimal = {"revenue": 500_000}
    _upsert_history_row(existing, minimal, "http://u.com/r.pdf")
    assert existing.net_result is None
    assert existing.equity is None


# ── fetch_history_from_pdf ────────────────────────────────────────────────────

@patch("api.services.pdf_history._parse_financials_from_pdf", return_value=_sample_parsed())
def test_fetch_history_from_pdf_creates_new_row(mock_parse):
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None

    fetch_history_from_pdf("123456789", "http://example.com/r.pdf", 2023, "Årsrapport 2023", db)

    db.add.assert_called_once()
    db.commit.assert_called_once()


@patch("api.services.pdf_history._parse_financials_from_pdf", return_value=_sample_parsed())
def test_fetch_history_from_pdf_updates_existing_row(mock_parse):
    existing = _mock_history_row()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = existing

    fetch_history_from_pdf("123456789", "http://example.com/r.pdf", 2023, "lbl", db)

    db.add.assert_not_called()
    db.commit.assert_called_once()
    assert existing.source == "pdf"


@patch("api.services.pdf_history._parse_financials_from_pdf", return_value=None)
def test_fetch_history_from_pdf_raises_pdf_extraction_error(mock_parse):
    db = _mock_db()
    with pytest.raises(PdfExtractionError):
        fetch_history_from_pdf("123", "http://example.com/r.pdf", 2023, "lbl", db)
    db.commit.assert_not_called()


@patch("api.services.pdf_history._parse_financials_from_pdf", return_value=_sample_parsed())
def test_fetch_history_from_pdf_returns_dict_with_expected_keys(mock_parse):
    existing = _mock_history_row()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = existing

    result = fetch_history_from_pdf("123", "http://example.com/r.pdf", 2023, "label", db)

    assert result["year"] == 2023
    assert result["source"] == "pdf"
    assert result["pdf_url"] == "http://example.com/r.pdf"
    assert result["label"] == "label"
    assert "revenue" in result
    assert "equity_ratio" in result


@patch("api.services.pdf_history._parse_financials_from_pdf", return_value=_sample_parsed())
def test_fetch_history_from_pdf_new_row_sets_orgnr_and_year(mock_parse):
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None

    fetch_history_from_pdf("987654321", "http://example.com/r.pdf", 2022, "lbl", db)

    added = db.add.call_args[0][0]
    assert added.orgnr == "987654321"
    assert added.year == 2022


# ── _get_full_history ─────────────────────────────────────────────────────────

@patch("api.services.pdf_history.fetch_regnskap_history", return_value=[])
def test_get_full_history_returns_db_rows(mock_brreg):
    row = _mock_history_row(year=2023, source="pdf", raw=None)
    db = _mock_db()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [row]

    result = _get_full_history("123456789", db)

    assert len(result) == 1
    assert result[0]["year"] == 2023
    assert result[0]["source"] == "pdf"


@patch("api.services.pdf_history.fetch_regnskap_history", return_value=[
    {"year": 2022, "revenue": 900_000, "net_result": 40_000}
])
def test_get_full_history_merges_brreg_rows(mock_brreg):
    row = _mock_history_row(year=2023, raw=None)
    db = _mock_db()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [row]

    result = _get_full_history("123456789", db)

    years = [r["year"] for r in result]
    assert 2023 in years
    assert 2022 in years


@patch("api.services.pdf_history.fetch_regnskap_history", return_value=[
    {"year": 2023, "revenue": 999_999}
])
def test_get_full_history_db_row_wins_over_brreg_for_same_year(mock_brreg):
    row = _mock_history_row(year=2023, source="pdf", revenue=1_000_000, raw=None)
    db = _mock_db()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [row]

    result = _get_full_history("123456789", db)

    assert len(result) == 1
    assert result[0]["source"] == "pdf"
    assert result[0]["revenue"] == 1_000_000


@patch("api.services.pdf_history.fetch_regnskap_history", return_value=[
    {"year": 2021}, {"year": 2022}, {"year": 2023},
])
def test_get_full_history_sorted_descending(mock_brreg):
    db = _mock_db()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

    result = _get_full_history("123456789", db)

    years = [r["year"] for r in result]
    assert years == sorted(years, reverse=True)


@patch("api.services.pdf_history.fetch_regnskap_history", side_effect=Exception("BRREG unavailable"))
def test_get_full_history_handles_brreg_exception_gracefully(mock_brreg):
    row = _mock_history_row(year=2023, raw=None)
    db = _mock_db()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [row]

    result = _get_full_history("123456789", db)

    assert len(result) == 1
    assert result[0]["year"] == 2023


@patch("api.services.pdf_history.fetch_regnskap_history", return_value=[])
def test_get_full_history_row_with_raw_dict_merged_into_base(mock_brreg):
    row = _mock_history_row(year=2023, raw={"extra_field": "extra_value"})
    db = _mock_db()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [row]

    result = _get_full_history("123456789", db)

    assert result[0]["extra_field"] == "extra_value"
    # Explicit fields override raw dict values
    assert result[0]["year"] == 2023


@patch("api.services.pdf_history.fetch_regnskap_history", return_value=[])
def test_get_full_history_returns_empty_list_when_no_data(mock_brreg):
    db = _mock_db()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

    result = _get_full_history("123456789", db)

    assert result == []


@patch("api.services.pdf_history.fetch_regnskap_history", return_value=[
    {"year": 2020}, {"year": 2021}, {"year": 2022},
])
def test_get_full_history_brreg_rows_tagged_as_brreg_source(mock_brreg):
    db = _mock_db()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

    result = _get_full_history("123456789", db)

    for row in result:
        assert row["source"] == "brreg"
        assert row["currency"] == "NOK"
