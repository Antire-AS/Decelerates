"""Unit tests for api/services/gdpr_service.py — GdprService.

Pure static tests — uses MagicMock DB; no real infrastructure required.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from api.domain.exceptions import NotFoundError
from api.services.gdpr_service import GdprService


def _mock_db():
    return MagicMock()


def _mock_company(**kwargs):
    c = MagicMock()
    c.orgnr = kwargs.get("orgnr", "123456789")
    c.navn = kwargs.get("navn", "Test AS")
    c.kommune = kwargs.get("kommune", "Oslo")
    c.naeringskode1_beskrivelse = kwargs.get("desc", "IT-tjenester")
    c.risk_score = kwargs.get("risk_score", 5)
    c.deleted_at = kwargs.get("deleted_at", None)
    c.pep_raw = kwargs.get("pep_raw", {"hit_count": 0})
    return c


# ── _get_company ──────────────────────────────────────────────────────────────

def test_get_company_raises_not_found_when_missing():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(NotFoundError):
        GdprService(db)._get_company("999999999")


def test_get_company_returns_company_when_found():
    company = _mock_company()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = company
    result = GdprService(db)._get_company("123456789")
    assert result is company


# ── erase_company ─────────────────────────────────────────────────────────────

def test_erase_company_raises_not_found_when_missing():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(NotFoundError):
        GdprService(db).erase_company("999999999")


def test_erase_company_sets_deleted_at():
    company = _mock_company()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = company
    db.query.return_value.filter.return_value.delete.return_value = 3

    before = datetime.now(timezone.utc)
    GdprService(db).erase_company("123456789")

    assert company.deleted_at is not None
    assert company.deleted_at >= before


def test_erase_company_clears_pii_fields():
    company = _mock_company(navn="Test AS", pep_raw={"hit_count": 1})
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = company
    db.query.return_value.filter.return_value.delete.return_value = 0

    GdprService(db).erase_company("123456789")

    assert company.pep_raw is None
    assert company.navn is None


def test_erase_company_deletes_rag_chunks():
    company = _mock_company()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = company
    db.query.return_value.filter.return_value.delete.return_value = 5

    GdprService(db).erase_company("123456789")

    db.commit.assert_called_once()


def test_erase_company_returns_summary_dict():
    company = _mock_company(orgnr="123456789")
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = company
    db.query.return_value.filter.return_value.delete.return_value = 7

    result = GdprService(db).erase_company("123456789")

    assert result["orgnr"] == "123456789"
    assert "deleted_at" in result
    assert result["chunks_removed"] == 7


# ── _serialize_export ─────────────────────────────────────────────────────────

def _mock_records():
    history = MagicMock()
    history.year = 2023
    history.source = "pdf"
    history.sum_driftsinntekter = 1_000_000

    note = MagicMock()
    note.question = "Hva er risikoen?"
    note.answer = "Lav risiko."

    source = MagicMock()
    source.year = 2023
    source.pdf_url = "http://example.com/r.pdf"

    policy = MagicMock()
    policy.insurer = "Gjensidige"
    policy.product_type = "Ansvar"
    policy.renewal_date = None

    claim = MagicMock()
    claim.claim_number = "CLM-001"
    claim.status = MagicMock()
    claim.status.value = "open"

    activity = MagicMock()
    activity.subject = "Follow up"
    activity.activity_type = MagicMock()
    activity.activity_type.value = "call"

    return {
        "history": [history],
        "notes": [note],
        "sources": [source],
        "policies": [policy],
        "claims": [claim],
        "activities": [activity],
    }


def test_serialize_export_includes_all_sections():
    company = _mock_company()
    result = GdprService._serialize_export(company, _mock_records())
    assert "company" in result
    assert "financial_history" in result
    assert "notes" in result
    assert "pdf_sources" in result
    assert "policies" in result
    assert "claims" in result
    assert "activities" in result


def test_serialize_export_company_fields():
    company = _mock_company(orgnr="123456789", navn="Firma AS", risk_score=8)
    result = GdprService._serialize_export(company, _mock_records())
    assert result["company"]["orgnr"] == "123456789"
    assert result["company"]["navn"] == "Firma AS"
    assert result["company"]["risk_score"] == 8


def test_serialize_export_financial_history_entries():
    company = _mock_company()
    result = GdprService._serialize_export(company, _mock_records())
    assert len(result["financial_history"]) == 1
    assert result["financial_history"][0]["year"] == 2023


def test_serialize_export_notes_entries():
    company = _mock_company()
    result = GdprService._serialize_export(company, _mock_records())
    assert result["notes"][0]["question"] == "Hva er risikoen?"
    assert result["notes"][0]["answer"] == "Lav risiko."


def test_serialize_export_deleted_at_none_when_not_set():
    company = _mock_company(deleted_at=None)
    result = GdprService._serialize_export(company, _mock_records())
    assert result["company"]["deleted_at"] is None


def test_serialize_export_deleted_at_iso_when_set():
    now = datetime.now(timezone.utc)
    company = _mock_company(deleted_at=now)
    result = GdprService._serialize_export(company, _mock_records())
    assert result["company"]["deleted_at"] == now.isoformat()


# ── purge_old_deletions ───────────────────────────────────────────────────────

def test_purge_old_deletions_returns_zero_when_no_old_companies():
    db = _mock_db()
    db.query.return_value.filter.return_value.all.return_value = []
    count = GdprService(db).purge_old_deletions()
    assert count == 0
    db.commit.assert_called_once()


def test_purge_old_deletions_hard_deletes_company_and_related_records():
    company = _mock_company(orgnr="123456789")
    db = _mock_db()
    db.query.return_value.filter.return_value.all.return_value = [company]
    db.query.return_value.filter.return_value.delete.return_value = 0

    count = GdprService(db).purge_old_deletions()

    assert count == 1
    db.delete.assert_called_once_with(company)
    db.commit.assert_called_once()


def test_purge_old_deletions_deletes_related_tables():
    company1 = _mock_company(orgnr="111222333")
    company2 = _mock_company(orgnr="444555666")
    db = _mock_db()
    db.query.return_value.filter.return_value.all.return_value = [company1, company2]
    db.query.return_value.filter.return_value.delete.return_value = 0

    count = GdprService(db).purge_old_deletions()

    assert count == 2
    # db.delete called once per company
    assert db.delete.call_count == 2


def test_purge_old_deletions_commits_at_end():
    company = _mock_company()
    db = _mock_db()
    db.query.return_value.filter.return_value.all.return_value = [company]
    db.query.return_value.filter.return_value.delete.return_value = 0

    GdprService(db).purge_old_deletions()

    db.commit.assert_called_once()
