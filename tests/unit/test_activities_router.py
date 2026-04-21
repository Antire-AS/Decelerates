"""Unit tests for api/routers/activities.py — activity timeline / CRM log endpoints.

Uses a minimal FastAPI app with the router mounted; ActivityService is injected
as a MagicMock — no real DB required.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Stub heavy transitive deps before any api.* import
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.auth import CurrentUser, get_current_user
from api.dependencies import get_db
from api.domain.exceptions import NotFoundError
from api.routers.activities import router, _svc

# ── App fixture ───────────────────────────────────────────────────────────────

_app = FastAPI()
_app.include_router(router)

_FAKE_USER = CurrentUser(
    email="test@local", name="Test User", oid="test-oid", firm_id=1
)


def _mock_activity(**kw):
    a = MagicMock()
    a.id = kw.get("id", 1)
    a.orgnr = kw.get("orgnr", "123456789")
    a.firm_id = 1
    a.policy_id = None
    a.claim_id = None
    a.created_by_email = "test@local"
    a.assigned_to_user_id = None
    a.activity_type = MagicMock(value=kw.get("activity_type", "call"))
    a.subject = kw.get("subject", "Test activity")
    a.body = kw.get("body", None)
    a.due_date = MagicMock(isoformat=lambda: "2026-04-15")
    a.completed = kw.get("completed", False)
    a.created_at = MagicMock(isoformat=lambda: "2026-04-01T12:00:00")
    return a


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_activity_svc():
    return MagicMock()


@pytest.fixture
def client(mock_db, mock_activity_svc):
    _app.dependency_overrides[get_db] = lambda: mock_db
    _app.dependency_overrides[_svc] = lambda: mock_activity_svc
    _app.dependency_overrides[get_current_user] = lambda: _FAKE_USER
    yield TestClient(_app, raise_server_exceptions=False)
    _app.dependency_overrides.clear()


# ── GET /org/{orgnr}/activities ──────────────────────────────────────────────


def test_list_activities_returns_200(client, mock_activity_svc):
    mock_activity_svc.list_by_orgnr.return_value = []
    resp = client.get("/org/123456789/activities")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_activities_returns_items(client, mock_activity_svc):
    mock_activity_svc.list_by_orgnr.return_value = [
        _mock_activity(id=5, subject="Follow-up")
    ]
    resp = client.get("/org/123456789/activities")
    items = resp.json()
    assert len(items) == 1
    assert items[0]["id"] == 5
    assert items[0]["subject"] == "Follow-up"


# ── POST /org/{orgnr}/activities ─────────────────────────────────────────────


@patch("api.routers.activities.log_audit")
def test_create_activity_returns_201(mock_audit, client, mock_activity_svc):
    mock_activity_svc.create.return_value = _mock_activity(id=10)
    resp = client.post(
        "/org/123456789/activities",
        json={"activity_type": "call", "subject": "Ring kunden"},
    )
    assert resp.status_code == 201
    assert resp.json()["id"] == 10


@patch("api.routers.activities.log_audit")
def test_create_activity_returns_404_when_not_found(
    mock_audit, client, mock_activity_svc
):
    mock_activity_svc.create.side_effect = NotFoundError("Policy not found")
    resp = client.post(
        "/org/123456789/activities",
        json={"activity_type": "call", "subject": "Test"},
    )
    assert resp.status_code == 404


# ── PUT /org/{orgnr}/activities/{activity_id} ────────────────────────────────


@patch("api.routers.activities.log_audit")
def test_update_activity_returns_200(mock_audit, client, mock_activity_svc):
    mock_activity_svc.update.return_value = _mock_activity(id=3, subject="Updated")
    resp = client.put(
        "/org/123456789/activities/3",
        json={"subject": "Updated"},
    )
    assert resp.status_code == 200
    assert resp.json()["subject"] == "Updated"


@patch("api.routers.activities.log_audit")
def test_update_activity_returns_404(mock_audit, client, mock_activity_svc):
    mock_activity_svc.update.side_effect = NotFoundError("not found")
    resp = client.put(
        "/org/123456789/activities/999",
        json={"subject": "X"},
    )
    assert resp.status_code == 404


# ── DELETE /org/{orgnr}/activities/{activity_id} ─────────────────────────────


@patch("api.routers.activities.log_audit")
def test_delete_activity_returns_204(mock_audit, client, mock_activity_svc):
    mock_activity_svc.delete.return_value = None
    resp = client.delete("/org/123456789/activities/7")
    assert resp.status_code == 204


@patch("api.routers.activities.log_audit")
def test_delete_activity_returns_404(mock_audit, client, mock_activity_svc):
    mock_activity_svc.delete.side_effect = NotFoundError("not found")
    resp = client.delete("/org/123456789/activities/999")
    assert resp.status_code == 404


# ── POST /activities/bulk-complete ───────────────────────────────────────────


@patch("api.routers.activities.log_audit")
def test_bulk_complete_returns_200(mock_audit, client, mock_activity_svc):
    mock_activity_svc.bulk_complete.return_value = 3
    resp = client.post("/activities/bulk-complete", json={"activity_ids": [1, 2, 3]})
    assert resp.status_code == 200
    assert resp.json()["updated"] == 3
