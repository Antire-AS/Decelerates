"""Tests for /admin/metrics + /admin/services-health."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.auth import CurrentUser, get_current_user
from api.dependencies import get_db
from api.routers.admin_metrics import router

_app = FastAPI()
_app.include_router(router)
_USER = CurrentUser(email="admin@local", name="Admin", oid="oid", firm_id=1)


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def client(mock_db):
    _app.dependency_overrides[get_db] = lambda: mock_db
    _app.dependency_overrides[get_current_user] = lambda: _USER
    yield TestClient(_app)
    _app.dependency_overrides.clear()


def test_metrics_returns_expected_keys(client, mock_db):
    q = mock_db.query.return_value
    q.filter.return_value = q
    q.count.side_effect = [14, 3]  # total_users, admin_count
    mock_db.execute.return_value.scalar.return_value = 5_153_960_320  # ~4.8 GB
    resp = client.get("/admin/metrics")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_users"] == 14
    assert body["admin_count"] == 3
    assert body["broker_count"] == 11
    assert body["storage_bytes"] == 5_153_960_320
    assert body["api_calls_24h"] == 0
    assert body["ai_tokens_today"] == 0


def test_services_health_returns_seven_known_services(client):
    with patch(
        "api.routers.admin_metrics._probe",
        return_value={"status": "operational", "latency_ms": 42},
    ):
        resp = client.get("/admin/services-health")
        assert resp.status_code == 200
        names = {s["name"] for s in resp.json()["services"]}
        assert names == {
            "BRREG Enhetsregisteret",
            "BRREG Regnskapsregisteret",
            "Azure AI Foundry",
            "GCP Vertex AI",
            "OpenSanctions PEP",
            "Kartverket Geonorge",
            "Løsøreregisteret",
        }


def test_services_health_includes_latency(client):
    with patch(
        "api.routers.admin_metrics._probe",
        return_value={"status": "operational", "latency_ms": 100},
    ):
        resp = client.get("/admin/services-health")
        body = resp.json()
        assert all(s["latency_ms"] == 100 for s in body["services"])


def test_services_health_marks_losore_as_auth_required():
    """Løsøreregisteret has the Maskinporten note when probe returns auth_required."""
    from api.routers.admin_metrics import _SERVICES

    losore = next(s for s in _SERVICES if s[1] == "Løsøreregisteret")
    assert losore[2] == "Krever Maskinporten"
