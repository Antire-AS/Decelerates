"""Unit tests for api/routers/client_token.py — TestClient + mocked services."""

import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.auth import CurrentUser, get_current_user, get_optional_user
from api.dependencies import get_db
from api.routers.client_token import router

_app = FastAPI()
_app.include_router(router)

_FAKE_USER = CurrentUser(email="test@local", name="Test", oid="test-oid", firm_id=1)


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def client(mock_db):
    _app.dependency_overrides[get_db] = lambda: mock_db
    _app.dependency_overrides[get_current_user] = lambda: _FAKE_USER
    _app.dependency_overrides[get_optional_user] = lambda: _FAKE_USER
    yield TestClient(_app)
    _app.dependency_overrides.clear()


# ── POST /org/{orgnr}/client-token ───────────────────────────────────────────


def test_create_token_returns_200(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = (
        MagicMock()
    )  # company exists
    token_row = SimpleNamespace(token="abc123")
    with (
        patch("api.routers.client_token.create_token", return_value=token_row),
        patch("api.routers.client_token.log_audit"),
    ):
        resp = client.post("/org/123456789/client-token")
    assert resp.status_code == 200
    assert resp.json()["token"] == "abc123"
    assert resp.json()["orgnr"] == "123456789"


def test_create_token_returns_404_when_company_missing(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None
    resp = client.post("/org/999999999/client-token")
    assert resp.status_code == 404


# ── GET /org/{orgnr}/client-tokens ───────────────────────────────────────────


def test_list_tokens_returns_list(client):
    now = datetime.now(timezone.utc)
    rows = [
        SimpleNamespace(
            token="tok1",
            label="L1",
            expires_at=now + timedelta(days=10),
            created_at=now,
        ),
    ]
    with patch("api.routers.client_token.list_active_tokens", return_value=rows):
        resp = client.get("/org/123456789/client-tokens")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["token"] == "tok1"


def test_list_tokens_returns_empty(client):
    with patch("api.routers.client_token.list_active_tokens", return_value=[]):
        resp = client.get("/org/123456789/client-tokens")
    assert resp.json() == []


# ── GET /client/{token} ─────────────────────────────────────────────────────


def test_get_client_profile_returns_200(client, mock_db):
    now = datetime.now(timezone.utc)
    token_row = SimpleNamespace(
        token="valid-tok",
        orgnr="123456789",
        label="Test",
        expires_at=now + timedelta(days=5),
        created_at=now,
    )
    mock_db.query.return_value.filter.return_value.first.return_value = token_row
    profile = {
        "org": {"navn": "Test AS", "kommune": "Oslo"},
        "risk": {"score": 3, "reasons": []},
        "regnskap": {},
    }

    with (
        patch("api.routers.client_token.fetch_org_profile", return_value=profile),
        patch("api.routers.client_token.log_audit"),
        patch(
            "api.routers.client_token._fetch_crm_snapshot",
            return_value={"policies": [], "claims": [], "documents": []},
        ),
    ):
        resp = client.get("/client/valid-tok")
    assert resp.status_code == 200
    assert resp.json()["orgnr"] == "123456789"


def test_get_client_profile_returns_404_for_unknown_token(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None
    resp = client.get("/client/unknown-tok")
    assert resp.status_code == 404


def test_get_client_profile_returns_410_for_expired_token(client, mock_db):
    expired_row = SimpleNamespace(
        token="expired-tok",
        orgnr="123456789",
        label="Old",
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    mock_db.query.return_value.filter.return_value.first.return_value = expired_row
    resp = client.get("/client/expired-tok")
    assert resp.status_code == 410
