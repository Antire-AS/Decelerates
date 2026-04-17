"""Unit tests for api/routers/webhooks.py — Signicat webhook endpoint."""

import hashlib
import hmac
import json
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.dependencies import get_db
from api.routers.webhooks import router

_app = FastAPI()
_app.include_router(router)


@pytest.fixture
def client():
    _app.dependency_overrides[get_db] = lambda: MagicMock()
    yield TestClient(_app)
    _app.dependency_overrides.clear()


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@patch("api.routers.webhooks.SignicatService")
def test_webhook_not_configured(MockService, client):
    MockService.return_value.is_configured.return_value = False
    resp = client.post(
        "/webhooks/signicat", content=b"{}", headers={"x-signicat-signature": "x"}
    )
    assert resp.status_code == 503


@patch("api.routers.webhooks.SignicatService")
def test_webhook_invalid_signature(MockService, client):
    svc = MockService.return_value
    svc.is_configured.return_value = True
    svc.verify_webhook.return_value = False
    resp = client.post(
        "/webhooks/signicat", content=b"{}", headers={"x-signicat-signature": "bad"}
    )
    assert resp.status_code == 401


@patch("api.routers.webhooks.SignicatService")
def test_webhook_valid_signature(MockService, client):
    svc = MockService.return_value
    svc.is_configured.return_value = True
    svc.verify_webhook.return_value = True
    svc.parse_webhook.return_value = {
        "session_id": "sess-1",
        "status": "signed",
        "signed_pdf_url": "https://x",
        "signed_at": "2026-04-12",
    }
    body = json.dumps({"sessionId": "sess-1", "sessionStatus": "signed"}).encode()
    resp = client.post(
        "/webhooks/signicat", content=body, headers={"x-signicat-signature": "valid"}
    )
    assert resp.status_code == 200
    assert resp.json()["received"] is True
