"""Unit tests for api/routers/email_compose.py."""
import sys
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.auth import CurrentUser, get_current_user
from api.dependencies import get_db
from api.routers.email_compose import router, _get_email_port

_app = FastAPI()
_app.include_router(router)

_USER = CurrentUser(email="test@local", name="Test", oid="test-oid", firm_id=1)


@pytest.fixture
def mock_port():
    port = MagicMock()
    port.is_configured.return_value = True
    return port


@pytest.fixture
def client(mock_port):
    _app.dependency_overrides[get_current_user] = lambda: _USER
    _app.dependency_overrides[get_db] = lambda: MagicMock()
    _app.dependency_overrides[_get_email_port] = lambda: mock_port
    yield TestClient(_app)
    _app.dependency_overrides.clear()


def test_compose_email_success(client, mock_port):
    activity = MagicMock(id=1)
    with MagicMock() as svc_mock:
        svc_mock.compose_and_send.return_value = activity
        from unittest.mock import patch
        with patch("api.routers.email_compose.EmailComposeService", return_value=svc_mock):
            resp = client.post("/email/compose", json={
                "to": "client@example.no",
                "subject": "Fornyelse",
                "body_html": "<p>Hei</p>",
                "orgnr": "123",
            })
    assert resp.status_code == 200
    assert resp.json()["sent"] is True


def test_compose_email_not_configured():
    unconfigured_port = MagicMock()
    unconfigured_port.is_configured.return_value = False
    _app.dependency_overrides[get_current_user] = lambda: _USER
    _app.dependency_overrides[get_db] = lambda: MagicMock()
    _app.dependency_overrides[_get_email_port] = lambda: unconfigured_port
    try:
        c = TestClient(_app)
        resp = c.post("/email/compose", json={
            "to": "x@x.no", "subject": "X", "body_html": "<p>X</p>", "orgnr": "123",
        })
        assert resp.status_code == 503
        assert "ikke konfigurert" in resp.json()["detail"]
    finally:
        _app.dependency_overrides.clear()
