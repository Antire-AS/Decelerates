"""Unit tests for services/company.py — mocked DB and external APIs."""
from unittest.mock import MagicMock, patch

from api.services.company import (
    _seed_pdf_sources,
    _upsert_company,
    _fetch_financials_with_fallback,
)


# ── _seed_pdf_sources ─────────────────────────────────────────────────────────

def _make_db():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    return db


def test_seed_pdf_sources_inserts_new():
    seed = {"123456789": [{"year": 2023, "pdf_url": "https://example.com/ar.pdf", "label": "AR 2023"}]}
    db = _make_db()

    with patch("api.services.company.PDF_SEED_DATA", seed):
        _seed_pdf_sources(db)

    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_seed_pdf_sources_updates_url():
    seed = {"123456789": [{"year": 2023, "pdf_url": "https://example.com/new.pdf", "label": "New"}]}
    existing = MagicMock()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = existing

    with patch("api.services.company.PDF_SEED_DATA", seed):
        _seed_pdf_sources(db)

    # Should NOT add a new row — just update URL on existing
    db.add.assert_not_called()
    assert existing.pdf_url == "https://example.com/new.pdf"
    db.commit.assert_called_once()


# ── _upsert_company ───────────────────────────────────────────────────────────

def test_upsert_company_creates_new():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    org = {"navn": "Test AS", "organisasjonsform_kode": "AS", "kommune": "Oslo", "land": "Norge",
           "naeringskode1": "64.11", "naeringskode1_beskrivelse": "Sentralbankvirksomhet"}
    regn = {"regnskapsår": 2023, "sum_driftsinntekter": 1_000_000,
            "sum_egenkapital": 200_000, "sum_eiendeler": 500_000}
    risk = {"equity_ratio": 0.4, "score": 2}

    _upsert_company(db, "123456789", org, regn, risk, None)

    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_upsert_company_updates_existing():
    existing = MagicMock()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = existing

    org = {"navn": "Updated AS", "organisasjonsform_kode": "AS", "kommune": "Bergen", "land": "Norge",
           "naeringskode1": "46.90", "naeringskode1_beskrivelse": "Engroshandel"}
    regn = {"regnskapsår": 2024, "sum_driftsinntekter": 2_000_000,
            "sum_egenkapital": 400_000, "sum_eiendeler": 1_000_000}
    risk = {"equity_ratio": 0.4, "score": 1}

    _upsert_company(db, "123456789", org, regn, risk, None)

    # Should NOT create a new row
    db.add.assert_not_called()
    assert existing.navn == "Updated AS"
    db.commit.assert_called_once()


# ── _fetch_financials_with_fallback ───────────────────────────────────────────

def test_fetch_financials_fallback_to_history():
    """When BRREG returns empty, fall back to most recent CompanyHistory row."""
    hist = MagicMock()
    hist.year = 2022
    hist.revenue = 500_000.0
    hist.net_result = 25_000.0
    hist.equity = 100_000.0
    hist.total_assets = 400_000.0
    hist.equity_ratio = 0.25
    hist.antall_ansatte = 10
    hist.raw = {"sum_driftsinntekter": 500_000}

    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = hist

    with patch("api.services.company.fetch_regnskap_keyfigures", return_value={}):
        result = _fetch_financials_with_fallback("123456789", db)

    assert result["_source"] == "pdf_history"
    assert result["regnskapsår"] == 2022
    assert result["sum_driftsinntekter"] == 500_000
    assert result["equity_ratio"] == 0.25
