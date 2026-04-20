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


# ── Tender-mail webhook — shared-secret verification ─────────────────────────


from fastapi import HTTPException

from api.routers.webhooks import _verify_mail_webhook_secret


def test_verify_mail_secret_passes_when_env_matches(monkeypatch):
    monkeypatch.setenv("MAIL_WEBHOOK_SECRET", "s3cret-42")
    _verify_mail_webhook_secret("s3cret-42")  # no raise


def test_verify_mail_secret_503_when_env_unset(monkeypatch):
    monkeypatch.delenv("MAIL_WEBHOOK_SECRET", raising=False)
    with pytest.raises(HTTPException) as exc:
        _verify_mail_webhook_secret("anything")
    assert exc.value.status_code == 503


def test_verify_mail_secret_503_when_env_blank(monkeypatch):
    monkeypatch.setenv("MAIL_WEBHOOK_SECRET", "   ")
    with pytest.raises(HTTPException) as exc:
        _verify_mail_webhook_secret("anything")
    assert exc.value.status_code == 503


def test_verify_mail_secret_401_when_header_missing(monkeypatch):
    monkeypatch.setenv("MAIL_WEBHOOK_SECRET", "s3cret")
    with pytest.raises(HTTPException) as exc:
        _verify_mail_webhook_secret("")
    assert exc.value.status_code == 401


def test_verify_mail_secret_401_when_header_wrong(monkeypatch):
    monkeypatch.setenv("MAIL_WEBHOOK_SECRET", "s3cret")
    with pytest.raises(HTTPException) as exc:
        _verify_mail_webhook_secret("wrong-value")
    assert exc.value.status_code == 401
