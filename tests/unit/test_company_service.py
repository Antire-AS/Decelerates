"""Unit tests for api/services/company.py — company seeding, profile fetch, narratives."""

import sys
from unittest.mock import MagicMock, patch

sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.services.company import (
    _upsert_company,
    _fetch_financials_with_fallback,
    fetch_org_profile,
)


# ── _seed_pdf_sources ─────────────────────────────────────────────────────────

# ── _upsert_company ──────────────────────────────────────────────────────────


def test_upsert_creates_new_company():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    org = {"orgnr": "123", "navn": "Test AS", "organisasjonsform_kode": "AS"}
    regn = {"sum_driftsinntekter": 1_000_000}
    risk = {"score": 5}
    _upsert_company(db, "123", org, regn, risk, None)
    db.add.assert_called_once()
    db.commit.assert_called()


def test_upsert_updates_existing():
    db = MagicMock()
    existing = MagicMock(orgnr="123")
    db.query.return_value.filter.return_value.first.return_value = existing
    _upsert_company(
        db, "123", {"orgnr": "123", "navn": "Updated"}, {}, {"score": 3}, None
    )
    assert existing.navn == "Updated"
    db.commit.assert_called()


# ── _fetch_financials_with_fallback ──────────────────────────────────────────


@patch(
    "api.services.company.fetch_regnskap_keyfigures",
    return_value={"sum_driftsinntekter": 500},
)
def test_fetch_financials_from_brreg(mock_regn):
    db = MagicMock()
    result = _fetch_financials_with_fallback("123", db)
    assert result["sum_driftsinntekter"] == 500


@patch("api.services.company.fetch_regnskap_keyfigures", return_value={})
def test_fetch_financials_fallback_to_history(mock_regn):
    db = MagicMock()
    hist = MagicMock()
    hist.revenue = 999
    hist.equity = 100
    hist.total_assets = 500
    hist.equity_ratio = 0.2
    hist.antall_ansatte = 10
    hist.year = 2024
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = hist
    result = _fetch_financials_with_fallback("123", db)
    assert result.get("sum_driftsinntekter") == 999 or result.get("revenue") == 999


# ── fetch_org_profile ─────────────────────────────────────────────────────────


@patch("api.services.company.pep_screen_name", return_value={"hit_count": 0})
@patch(
    "api.services.company._fetch_financials_with_fallback",
    return_value={"sum_driftsinntekter": 1000},
)
@patch(
    "api.services.company.fetch_enhet_by_orgnr",
    return_value={"orgnr": "123", "navn": "Test"},
)
def test_fetch_org_profile_success(mock_enhet, mock_fin, mock_pep):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    result = fetch_org_profile("123", db)
    assert result is not None
    assert "org" in result
    assert "regnskap" in result


@patch("api.services.company.fetch_enhet_by_orgnr", return_value=None)
def test_fetch_org_profile_not_found(mock_enhet):
    db = MagicMock()
    result = fetch_org_profile("000", db)
    assert result is None


# ── _build_narrative_prompt ───────────────────────────────────────────────────


# ── list_companies ────────────────────────────────────────────────────────────


# ── _generate_synthetic_financials ────────────────────────────────────────────
