"""Unit tests for api/routers/gdpr.py.

Calls endpoint functions directly with mocked services + user. Verifies
the _serialize_consent() shape and NotFoundError → 404 conversion. The
GdprService and ConsentService have their own test suites.
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from api.domain.exceptions import NotFoundError
from api.routers.gdpr import (
    ConsentIn,
    ConsentWithdrawIn,
    _serialize_consent,
    erase_company,
    export_company_data,
    get_active_consents,
    purge_old_deletions,
    record_consent,
    withdraw_consent,
)


def _user(firm_id=1, email="broker@test.no"):
    return SimpleNamespace(firm_id=firm_id, email=email)


def _consent_row(
    id=1,
    orgnr="123456789",
    firm_id=1,
    lawful_basis="consent",
    purpose="insurance_advice",
    withdrawn_at=None,
    withdrawal_reason=None,
):
    r = MagicMock()
    r.id = id
    r.orgnr = orgnr
    r.firm_id = firm_id
    r.created_at = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    r.lawful_basis = SimpleNamespace(value=lawful_basis)
    r.purpose = purpose
    r.captured_by_email = "broker@test.no"
    r.withdrawn_at = withdrawn_at
    r.withdrawal_reason = withdrawal_reason
    return r


# ── _serialize_consent ────────────────────────────────────────────────────────

def test_serialize_consent_returns_full_dict():
    row = _consent_row()
    result = _serialize_consent(row)
    assert result["id"] == 1
    assert result["orgnr"] == "123456789"
    assert result["firm_id"] == 1
    assert result["lawful_basis"] == "consent"
    assert result["purpose"] == "insurance_advice"
    assert result["created_at"] == "2025-06-01T12:00:00+00:00"
    assert result["captured_by_email"] == "broker@test.no"
    assert result["withdrawn_at"] is None
    assert result["withdrawal_reason"] is None


def test_serialize_consent_handles_withdrawn():
    row = _consent_row(
        withdrawn_at=datetime(2025, 7, 1, 10, 30, 0, tzinfo=timezone.utc),
        withdrawal_reason="Customer requested",
    )
    result = _serialize_consent(row)
    assert result["withdrawn_at"] == "2025-07-01T10:30:00+00:00"
    assert result["withdrawal_reason"] == "Customer requested"


def test_serialize_consent_handles_null_created_at():
    row = _consent_row()
    row.created_at = None
    result = _serialize_consent(row)
    assert result["created_at"] is None


# ── erase_company (GDPR Art. 17 right to erasure) ─────────────────────────────

def test_erase_company_returns_service_result():
    svc = MagicMock()
    svc.erase_company.return_value = {"erased": True, "orgnr": "123456789"}
    result = erase_company(orgnr="123456789", db=MagicMock(), svc=svc, user=_user())
    assert result["erased"] is True
    svc.erase_company.assert_called_once_with("123456789")


def test_erase_company_raises_404_when_not_found():
    svc = MagicMock()
    svc.erase_company.side_effect = NotFoundError("not found")
    with pytest.raises(HTTPException) as exc:
        erase_company(orgnr="999", db=MagicMock(), svc=svc, user=_user())
    assert exc.value.status_code == 404
    assert "not found" in str(exc.value.detail).lower()


# ── export_company_data (GDPR Art. 20 portability) ───────────────────────────

def test_export_returns_service_result():
    svc = MagicMock()
    svc.export_company_data.return_value = {"orgnr": "123", "data": {"companies": []}}
    result = export_company_data(orgnr="123", db=MagicMock(), svc=svc, user=_user())
    assert "data" in result
    svc.export_company_data.assert_called_once_with("123")


def test_export_raises_404_when_not_found():
    svc = MagicMock()
    svc.export_company_data.side_effect = NotFoundError("missing")
    with pytest.raises(HTTPException) as exc:
        export_company_data(orgnr="999", db=MagicMock(), svc=svc, user=_user())
    assert exc.value.status_code == 404


# ── purge_old_deletions ──────────────────────────────────────────────────────

def test_purge_returns_count_dict():
    svc = MagicMock()
    svc.purge_old_deletions.return_value = 7
    result = purge_old_deletions(svc=svc, user=_user())
    assert result == {"purged": 7}


def test_purge_zero_when_nothing_to_purge():
    svc = MagicMock()
    svc.purge_old_deletions.return_value = 0
    result = purge_old_deletions(svc=svc, user=_user())
    assert result == {"purged": 0}


# ── record_consent ────────────────────────────────────────────────────────────

def test_record_consent_serializes_returned_row():
    svc = MagicMock()
    svc.record_consent.return_value = _consent_row(id=42)
    body = ConsentIn(lawful_basis="consent", purpose="insurance_advice")
    result = record_consent(orgnr="123", body=body, db=MagicMock(), svc=svc, user=_user())
    assert result["id"] == 42
    svc.record_consent.assert_called_once_with(
        "123", 1, "broker@test.no", "consent", "insurance_advice"
    )


# ── get_active_consents ──────────────────────────────────────────────────────

def test_get_active_consents_returns_serialized_list():
    svc = MagicMock()
    svc.get_active_consents.return_value = [
        _consent_row(id=1),
        _consent_row(id=2, purpose="marketing"),
    ]
    result = get_active_consents(orgnr="123", svc=svc, user=_user())
    assert len(result) == 2
    assert result[0]["id"] == 1
    assert result[1]["purpose"] == "marketing"
    svc.get_active_consents.assert_called_once_with("123", 1)


def test_get_active_consents_returns_empty_when_none():
    svc = MagicMock()
    svc.get_active_consents.return_value = []
    result = get_active_consents(orgnr="123", svc=svc, user=_user())
    assert result == []


# ── withdraw_consent (GDPR Art. 7.3) ──────────────────────────────────────────

def test_withdraw_consent_returns_serialized_withdrawn_row():
    svc = MagicMock()
    svc.withdraw_consent.return_value = _consent_row(
        id=7,
        withdrawn_at=datetime(2025, 7, 1, 10, 30, 0, tzinfo=timezone.utc),
        withdrawal_reason="No longer needed",
    )
    body = ConsentWithdrawIn(reason="No longer needed")
    result = withdraw_consent(orgnr="123", consent_id=7, body=body, db=MagicMock(), svc=svc, user=_user())
    assert result["id"] == 7
    assert result["withdrawal_reason"] == "No longer needed"
    svc.withdraw_consent.assert_called_once_with(1, 7, "No longer needed")


def test_withdraw_consent_raises_404_when_not_found():
    svc = MagicMock()
    svc.withdraw_consent.side_effect = NotFoundError("missing")
    body = ConsentWithdrawIn(reason="x")
    with pytest.raises(HTTPException) as exc:
        withdraw_consent(orgnr="123", consent_id=999, body=body, db=MagicMock(), svc=svc, user=_user())
    assert exc.value.status_code == 404


def test_withdraw_consent_accepts_null_reason():
    svc = MagicMock()
    svc.withdraw_consent.return_value = _consent_row(id=7)
    body = ConsentWithdrawIn()  # no reason
    withdraw_consent(orgnr="123", consent_id=7, body=body, db=MagicMock(), svc=svc, user=_user())
    svc.withdraw_consent.assert_called_once_with(1, 7, None)
