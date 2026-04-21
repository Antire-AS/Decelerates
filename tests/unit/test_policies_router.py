"""Unit tests for api/routers/policies.py — policy CRUD + renewals + certificates."""

import sys
from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.auth import CurrentUser, get_current_user
from api.domain.exceptions import NotFoundError
from api.routers.policies import router, _svc, _get_notification
from api.services.policy_service import PolicyService

_app = FastAPI()
_app.include_router(router)

_USER = CurrentUser(email="test@local", name="Test", oid="test-oid", firm_id=1)


def _policy_mock(**kw):
    p = MagicMock()
    p.id = kw.get("id", 1)
    p.orgnr = kw.get("orgnr", "123456789")
    p.firm_id = kw.get("firm_id", 1)
    p.contact_person_id = None
    p.policy_number = kw.get("policy_number", "P-001")
    p.insurer = kw.get("insurer", "If Skadeforsikring")
    p.product_type = kw.get("product_type", "Eiendom")
    p.coverage_amount_nok = 1_000_000
    p.annual_premium_nok = 50_000
    p.start_date = date(2025, 1, 1)
    p.renewal_date = kw.get("renewal_date", date(2026, 6, 1))
    p.status = MagicMock(value="active")
    p.renewal_stage = MagicMock(value="not_started")
    p.notes = None
    p.document_url = None
    p.commission_rate_pct = 10.0
    p.commission_amount_nok = 5_000
    p.renewal_brief = kw.get("renewal_brief", None)
    p.renewal_email_draft = kw.get("renewal_email_draft", None)
    p.created_at = MagicMock(isoformat=lambda: "2025-01-01T00:00:00")
    p.updated_at = MagicMock(isoformat=lambda: "2025-01-01T00:00:00")
    return p


@pytest.fixture
def mock_svc():
    return MagicMock(spec=PolicyService)


@pytest.fixture
def mock_notification():
    return MagicMock()


@pytest.fixture
def client(mock_svc, mock_notification):
    _app.dependency_overrides[_svc] = lambda: mock_svc
    _app.dependency_overrides[get_current_user] = lambda: _USER
    _app.dependency_overrides[_get_notification] = lambda: mock_notification
    yield TestClient(_app)
    _app.dependency_overrides.clear()


# ── GET /org/{orgnr}/policies ─────────────────────────────────────────────────


def test_list_policies_returns_200(client, mock_svc):
    mock_svc.list_by_orgnr.return_value = [_policy_mock()]
    resp = client.get("/org/123456789/policies")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_list_policies_empty(client, mock_svc):
    mock_svc.list_by_orgnr.return_value = []
    resp = client.get("/org/123456789/policies")
    assert resp.status_code == 200
    assert resp.json() == []


# ── POST /org/{orgnr}/policies ────────────────────────────────────────────────


def test_create_policy_returns_201(client, mock_svc):
    mock_svc.create.return_value = _policy_mock()
    resp = client.post(
        "/org/123456789/policies",
        json={
            "insurer": "If",
            "product_type": "Eiendom",
            "annual_premium_nok": 50_000,
        },
    )
    assert resp.status_code == 201


def test_create_policy_validation_error(client, mock_svc):
    from api.domain.exceptions import ValidationError

    mock_svc.create.side_effect = ValidationError("bad")
    resp = client.post(
        "/org/123456789/policies",
        json={
            "insurer": "If",
            "product_type": "Eiendom",
        },
    )
    assert resp.status_code == 422


# ── PUT /org/{orgnr}/policies/{id} ───────────────────────────────────────────


def test_update_policy_returns_200(client, mock_svc):
    mock_svc.update.return_value = _policy_mock()
    resp = client.put("/org/123456789/policies/1", json={"insurer": "Gjensidige"})
    assert resp.status_code == 200


def test_update_policy_not_found(client, mock_svc):
    mock_svc.update.side_effect = NotFoundError("not found")
    resp = client.put("/org/123456789/policies/999", json={"insurer": "X"})
    assert resp.status_code == 404


# ── DELETE /org/{orgnr}/policies/{id} ─────────────────────────────────────────


def test_delete_policy_returns_204(client, mock_svc):
    mock_svc.delete.return_value = None
    resp = client.delete("/org/123456789/policies/1")
    assert resp.status_code == 204


# ── GET /policies ─────────────────────────────────────────────────────────────


def test_list_all_policies(client, mock_svc):
    mock_svc.list_by_firm.return_value = [_policy_mock(), _policy_mock(id=2)]
    resp = client.get("/policies")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# ── GET /renewals ─────────────────────────────────────────────────────────────


def test_get_renewals(client, mock_svc):
    p = _policy_mock(renewal_date=date(2026, 6, 1))
    mock_svc.get_renewals.return_value = [p]
    mock_svc.db = MagicMock()
    mock_svc.db.query.return_value.filter.return_value.all.return_value = []
    resp = client.get("/renewals?days=90")
    assert resp.status_code == 200


# ── POST /policies/{id}/renewal/advance ───────────────────────────────────────


def test_advance_renewal_stage(client, mock_svc):
    mock_svc.advance_renewal_stage.return_value = _policy_mock()
    resp = client.post("/policies/1/renewal/advance", json={"stage": "quoted"})
    assert resp.status_code == 200


def test_advance_renewal_not_found(client, mock_svc):
    mock_svc.advance_renewal_stage.side_effect = NotFoundError("nope")
    resp = client.post("/policies/999/renewal/advance", json={"stage": "quoted"})
    assert resp.status_code == 404
