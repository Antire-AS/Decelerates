"""Unit tests for api/routers/idd.py.

Calls endpoint functions directly with mocked service + user. Verifies
the _serialize() shape and NotFoundError → 404 conversion. The IddService
itself has its own test suite (test_idd_service.py).
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from api.domain.exceptions import NotFoundError
from api.routers.idd import (
    _serialize,
    create_behovsanalyse,
    delete_behovsanalyse,
    generate_suitability,
    get_behovsanalyse,
    list_all_behovsanalyser,
    list_behovsanalyser,
)


def _user(firm_id=1, email="broker@test.no"):
    return SimpleNamespace(firm_id=firm_id, email=email)


def _row(
    id=1,
    orgnr="123456789",
    client_name="Test AS",
    created_at=None,
    existing_insurance=None,
    recommended_products=None,
):
    r = MagicMock()
    r.id = id
    r.orgnr = orgnr
    r.created_by_email = "broker@test.no"
    r.created_at = created_at or datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    r.client_name = client_name
    r.client_contact_name = "Kari Nordmann"
    r.client_contact_email = "kari@test.no"
    r.existing_insurance = existing_insurance
    r.risk_appetite = "moderat"
    r.property_owned = True
    r.has_employees = True
    r.has_vehicles = False
    r.has_professional_liability = True
    r.has_cyber_risk = True
    r.annual_revenue_nok = 5_000_000
    r.special_requirements = None
    r.recommended_products = recommended_products
    r.advisor_notes = None
    r.suitability_basis = None
    r.fee_basis = "kommisjon"
    r.fee_amount_nok = None
    return r


# ── _serialize ────────────────────────────────────────────────────────────────

def test_serialize_returns_full_dict():
    row = _row()
    result = _serialize(row)
    assert result["id"] == 1
    assert result["orgnr"] == "123456789"
    assert result["client_name"] == "Test AS"
    assert result["created_at"] == "2025-06-01T12:00:00+00:00"
    assert result["existing_insurance"] == []  # None becomes []
    assert result["recommended_products"] == []  # None becomes []
    assert result["risk_appetite"] == "moderat"
    assert result["annual_revenue_nok"] == 5_000_000


def test_serialize_handles_null_created_at():
    row = _row()
    row.created_at = None
    result = _serialize(row)
    assert result["created_at"] is None


def test_serialize_preserves_existing_insurance_list():
    row = _row(existing_insurance=[{"insurer": "If", "type": "Cyber"}])
    result = _serialize(row)
    assert result["existing_insurance"] == [{"insurer": "If", "type": "Cyber"}]


def test_serialize_preserves_recommended_products_list():
    row = _row(recommended_products=["Bedriftsansvar", "Cyber"])
    result = _serialize(row)
    assert result["recommended_products"] == ["Bedriftsansvar", "Cyber"]


# ── list_behovsanalyser ──────────────────────────────────────────────────────

def test_list_for_company_returns_serialized_rows():
    svc = MagicMock()
    svc.list.return_value = [_row(id=1), _row(id=2)]
    result = list_behovsanalyser(orgnr="123456789", user=_user(), svc=svc)
    assert len(result) == 2
    assert result[0]["id"] == 1
    assert result[1]["id"] == 2
    svc.list.assert_called_once_with("123456789", 1)


def test_list_for_company_returns_empty_when_none():
    svc = MagicMock()
    svc.list.return_value = []
    result = list_behovsanalyser(orgnr="123456789", user=_user(), svc=svc)
    assert result == []


# ── list_all_behovsanalyser ──────────────────────────────────────────────────

def test_list_all_uses_firm_id_and_limit():
    svc = MagicMock()
    svc.list_all_for_firm.return_value = [_row(id=1)]
    result = list_all_behovsanalyser(limit=50, user=_user(firm_id=42), svc=svc)
    svc.list_all_for_firm.assert_called_once_with(42, limit=50)
    assert len(result) == 1


# ── create_behovsanalyse ─────────────────────────────────────────────────────

def test_create_returns_serialized_row():
    svc = MagicMock()
    svc.create.return_value = _row(id=99)
    body = MagicMock()
    body.model_dump.return_value = {"client_name": "New AS"}
    result = create_behovsanalyse(orgnr="123", body=body, db=MagicMock(), user=_user(), svc=svc)
    assert result["id"] == 99
    svc.create.assert_called_once_with("123", 1, "broker@test.no", {"client_name": "New AS"})


# ── get_behovsanalyse ────────────────────────────────────────────────────────

def test_get_returns_serialized_row():
    svc = MagicMock()
    svc.get.return_value = _row(id=7)
    result = get_behovsanalyse(orgnr="123", idd_id=7, user=_user(), svc=svc)
    assert result["id"] == 7
    svc.get.assert_called_once_with("123", 1, 7)


def test_get_raises_404_when_not_found():
    svc = MagicMock()
    svc.get.side_effect = NotFoundError("not found")
    with pytest.raises(HTTPException) as exc:
        get_behovsanalyse(orgnr="123", idd_id=999, user=_user(), svc=svc)
    assert exc.value.status_code == 404


# ── delete_behovsanalyse ─────────────────────────────────────────────────────

def test_delete_calls_service():
    svc = MagicMock()
    delete_behovsanalyse(orgnr="123", idd_id=7, db=MagicMock(), user=_user(), svc=svc)
    svc.delete.assert_called_once_with("123", 1, 7)


def test_delete_raises_404_when_not_found():
    svc = MagicMock()
    svc.delete.side_effect = NotFoundError("missing")
    with pytest.raises(HTTPException) as exc:
        delete_behovsanalyse(orgnr="123", idd_id=999, db=MagicMock(), user=_user(), svc=svc)
    assert exc.value.status_code == 404


# ── generate_suitability ─────────────────────────────────────────────────────

def test_generate_suitability_returns_reasoning():
    svc = MagicMock()
    svc.generate_suitability_reasoning.return_value = "Den anbefalte løsningen passer fordi..."
    result = generate_suitability(orgnr="123", idd_id=7, db=MagicMock(), user=_user(), svc=svc)
    assert "Den anbefalte løsningen" in str(result)


def test_generate_suitability_raises_404_when_not_found():
    svc = MagicMock()
    svc.generate_suitability_reasoning.side_effect = NotFoundError("missing")
    with pytest.raises(HTTPException) as exc:
        generate_suitability(orgnr="123", idd_id=999, db=MagicMock(), user=_user(), svc=svc)
    assert exc.value.status_code == 404
