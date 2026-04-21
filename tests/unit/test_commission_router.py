"""Unit tests for api/routers/commission.py — commission tracking endpoints."""

import sys
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.auth import CurrentUser, get_current_user
from api.routers.commission import router, _svc
from api.services.commission_service import CommissionService

_app = FastAPI()
_app.include_router(router)

_USER = CurrentUser(email="test@local", name="Test", oid="test-oid", firm_id=1)


@pytest.fixture
def mock_svc():
    return MagicMock(spec=CommissionService)


@pytest.fixture
def client(mock_svc):
    _app.dependency_overrides[_svc] = lambda: mock_svc
    _app.dependency_overrides[get_current_user] = lambda: _USER
    yield TestClient(_app)
    _app.dependency_overrides.clear()


def test_get_summary_returns_200(client, mock_svc):
    mock_svc.get_commission_summary.return_value = {
        "total_commission_ytd": 500_000,
        "total_premium_managed": 10_000_000,
        "active_policy_count": 10,
        "revenue_by_product_type": {},
        "revenue_by_insurer": {},
        "renewal_commission_vs_new": {"new": 100_000, "renewal": 400_000},
    }
    resp = client.get("/commission/summary")
    assert resp.status_code == 200
    assert resp.json()["total_commission_ytd"] == 500_000


def test_get_by_client_returns_200(client, mock_svc):
    mock_svc.get_commission_by_client.return_value = {
        "orgnr": "123",
        "policies": [],
        "total_commission_lifetime": 0,
        "total_commission_ytd": 0,
    }
    resp = client.get("/commission/by-client/123")
    assert resp.status_code == 200


def test_get_projections_returns_200(client, mock_svc):
    mock_svc.get_forward_projections.return_value = [
        {"period": "2026-Q2", "expected_commission": 150_000, "policy_count": 5},
    ]
    resp = client.get("/commission/projections?months=12")
    assert resp.status_code == 200
    assert "buckets" in resp.json()


def test_list_missing_commission_returns_list(client, mock_svc):
    policy = MagicMock()
    policy.id = 1
    policy.orgnr = "123"
    policy.policy_number = "P-001"
    policy.product_type = "Eiendom"
    policy.insurer = "If"
    policy.annual_premium_nok = 50_000
    policy.renewal_date = None
    mock_svc.list_policies_missing_commission.return_value = [policy]
    resp = client.get("/commission/missing")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
