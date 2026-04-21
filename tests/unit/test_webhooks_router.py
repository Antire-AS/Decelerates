"""Unit tests for api/routers/webhooks.py — Signicat webhook endpoint."""

import hashlib
import hmac
import json
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

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


# ── DocuSeal webhook — HMAC + tender status transition ───────────────────────


@patch("api.routers.webhooks.DocuSealService")
def test_docuseal_webhook_not_configured(MockService, client):
    MockService.return_value.is_configured.return_value = False
    resp = client.post(
        "/webhooks/docuseal", content=b"{}", headers={"x-docuseal-signature": "x"}
    )
    assert resp.status_code == 503


@patch("api.routers.webhooks.DocuSealService")
def test_docuseal_webhook_invalid_signature(MockService, client):
    svc = MockService.return_value
    svc.is_configured.return_value = True
    svc.verify_webhook.return_value = False
    resp = client.post(
        "/webhooks/docuseal", content=b"{}", headers={"x-docuseal-signature": "bad"}
    )
    assert resp.status_code == 401


@patch("api.routers.webhooks.TenderService")
@patch("api.routers.webhooks.DocuSealService")
def test_docuseal_webhook_marks_tender_signed(MockDocuSeal, MockTender, client):
    ds = MockDocuSeal.return_value
    ds.is_configured.return_value = True
    ds.verify_webhook.return_value = True
    ds.parse_webhook.return_value = {
        "session_id": "sub-42",
        "status": "signed",
        "signed_pdf_url": "https://example/signed.pdf",
        "signed_at": "2026-04-21T08:00:00Z",
    }
    # mark_contract_signed_by_session returns a truthy tender stand-in → matched=True
    MockTender.return_value.mark_contract_signed_by_session.return_value = MagicMock()
    body = json.dumps(
        {"event_type": "form.completed", "data": {"submission_id": "sub-42"}}
    ).encode()
    resp = client.post(
        "/webhooks/docuseal",
        content=body,
        headers={"x-docuseal-signature": "valid-hmac"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload == {"received": True, "matched": True}
    MockTender.return_value.mark_contract_signed_by_session.assert_called_once_with(
        "sub-42"
    )


@patch("api.routers.webhooks.TenderService")
@patch("api.routers.webhooks.DocuSealService")
def test_docuseal_webhook_unknown_session_acks_unmatched(
    MockDocuSeal, MockTender, client
):
    """Replays and out-of-flow submissions must ACK 200 so DocuSeal doesn't
    retry forever — the audit log captures `matched: false` for diagnostics."""
    ds = MockDocuSeal.return_value
    ds.is_configured.return_value = True
    ds.verify_webhook.return_value = True
    ds.parse_webhook.return_value = {
        "session_id": "sub-ghost",
        "status": "signed",
        "signed_pdf_url": None,
        "signed_at": None,
    }
    MockTender.return_value.mark_contract_signed_by_session.return_value = None
    body = json.dumps({"event_type": "form.completed", "data": {}}).encode()
    resp = client.post(
        "/webhooks/docuseal",
        content=body,
        headers={"x-docuseal-signature": "valid"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"received": True, "matched": False}


@patch("api.routers.webhooks.TenderService")
@patch("api.routers.webhooks.DocuSealService")
def test_docuseal_webhook_viewed_event_skips_tender_update(
    MockDocuSeal, MockTender, client
):
    """form.viewed is a tracking ping, not a state change — must not poke the
    tender row."""
    ds = MockDocuSeal.return_value
    ds.is_configured.return_value = True
    ds.verify_webhook.return_value = True
    ds.parse_webhook.return_value = {
        "session_id": "sub-9",
        "status": "viewed",
        "signed_pdf_url": None,
        "signed_at": None,
    }
    body = json.dumps({"event_type": "form.viewed", "data": {}}).encode()
    resp = client.post(
        "/webhooks/docuseal",
        content=body,
        headers={"x-docuseal-signature": "valid"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"received": True, "matched": False}
    MockTender.return_value.mark_contract_signed_by_session.assert_not_called()
