"""Unit tests for SendGrid inbound pipeline.

Every HTTP call is stubbed via httpx.MockTransport / monkeypatch so tests
run without a SendGrid account or any network.
"""

from __future__ import annotations

import io
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.services import sendgrid_inbound_service as svc


def _fake_upload(content: bytes) -> SimpleNamespace:
    """Mimic FastAPI's UploadFile just enough for our decode helper."""
    return SimpleNamespace(file=io.BytesIO(content))


# ── Payload normalisation ────────────────────────────────────────────────────


def test_normalise_extracts_basic_fields():
    form = {
        "from": "insurer@gjensidige.no",
        "to": "anbud@meglerai.no",
        "subject": "Re: Anbud [ref: TENDER-5-42]",
        "text": "Her er tilbudet vårt.",
        "headers": "Message-ID: <abc-123@example.com>\nX-Spam: low",
    }
    parsed = svc.normalise_inbound_form(form)
    assert parsed["subject"] == "Re: Anbud [ref: TENDER-5-42]"
    assert parsed["sender"] == "insurer@gjensidige.no"
    assert parsed["recipient"] == "anbud@meglerai.no"
    assert parsed["text_body"] == "Her er tilbudet vårt."
    assert parsed["message_id"] == "<abc-123@example.com>"
    assert parsed["attachments"] == []


def test_normalise_message_id_case_insensitive():
    form = {"headers": "MESSAGE-id: <weird-cased@x>\n"}
    parsed = svc.normalise_inbound_form(form)
    assert parsed["message_id"] == "<weird-cased@x>"


def test_normalise_message_id_missing_ok():
    """No Message-ID header → parsed['message_id'] is None (dedup skipped)."""
    form = {"from": "a@b.no", "headers": ""}
    parsed = svc.normalise_inbound_form(form)
    assert parsed["message_id"] is None


def test_normalise_extracts_numbered_attachments():
    form = {
        "subject": "s",
        "headers": "",
        "attachment1": _fake_upload(b"%PDF-1.4 test"),
        "attachment2": _fake_upload(b"other bytes"),
        "attachment-info": json.dumps(
            {
                "attachment1": {"filename": "offer.pdf", "type": "application/pdf"},
                "attachment2": {"filename": "note.txt", "type": "text/plain"},
            }
        ),
    }
    parsed = svc.normalise_inbound_form(form)
    assert len(parsed["attachments"]) == 2
    assert parsed["attachments"][0]["filename"] == "offer.pdf"
    assert parsed["attachments"][0]["content_type"] == "application/pdf"
    assert parsed["attachments"][0]["content"] == b"%PDF-1.4 test"
    assert parsed["attachments"][1]["filename"] == "note.txt"


def test_normalise_handles_missing_attachment_info():
    """Attachments without a matching info entry still come through with
    a synthesised filename — we never drop bytes silently."""
    form = {
        "subject": "s",
        "headers": "",
        "attachment1": _fake_upload(b"bytes"),
    }
    parsed = svc.normalise_inbound_form(form)
    assert len(parsed["attachments"]) == 1
    assert parsed["attachments"][0]["filename"] == "attachment-1.bin"


# ── is_configured ────────────────────────────────────────────────────────────


def test_is_configured_requires_api_key():
    assert svc.is_configured(svc.SendGridConfig(api_key="")) is False
    assert svc.is_configured(svc.SendGridConfig(api_key="SG.xxxx")) is True


# ── Forwarding ───────────────────────────────────────────────────────────────


def test_forward_copy_skips_when_forward_to_unset(monkeypatch: pytest.MonkeyPatch):
    called = {"post": 0}

    real_client = httpx.Client

    def counting_transport() -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            called["post"] += 1
            return httpx.Response(202)

        return httpx.MockTransport(handler)

    def fake_client(*args: Any, **kwargs: Any) -> httpx.Client:
        return real_client(transport=counting_transport(), **kwargs)

    monkeypatch.setattr(httpx, "Client", fake_client)
    cfg = svc.SendGridConfig(api_key="SG.x", forward_to="", forward_from="x@y.no")
    svc.forward_copy_via_sendgrid(
        cfg, {"subject": "hi", "text_body": "", "attachments": []}
    )
    assert called["post"] == 0


def test_forward_copy_posts_sendgrid_send(monkeypatch: pytest.MonkeyPatch):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization", "")
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(202)

    real_client = httpx.Client

    def fake_client(*args: Any, **kwargs: Any) -> httpx.Client:
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(httpx, "Client", fake_client)
    cfg = svc.SendGridConfig(
        api_key="SG.xxxx",
        forward_to="tharu@example.com",
        forward_from="noreply@meglerai.no",
    )
    parsed = {
        "subject": "Re: Anbud",
        "sender": "insurer@x.no",
        "recipient": "anbud@meglerai.no",
        "text_body": "Vi har svart!",
        "attachments": [
            {"filename": "o.pdf", "content_type": "application/pdf", "content": b"%PDF"}
        ],
    }
    svc.forward_copy_via_sendgrid(cfg, parsed)
    assert "mail/send" in captured["url"]
    assert captured["auth"] == "Bearer SG.xxxx"
    body = captured["body"]
    assert body["personalizations"][0]["to"][0]["email"] == "tharu@example.com"
    assert body["from"]["email"] == "noreply@meglerai.no"
    assert body["subject"].startswith("[anbud-fwd]")
    assert body["attachments"][0]["filename"] == "o.pdf"


def test_forward_copy_swallows_http_errors(monkeypatch: pytest.MonkeyPatch):
    """A SendGrid 5xx on forward must not bubble up — ingest has already
    committed the TenderOffer before we forward."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="oops")

    real_client = httpx.Client

    def fake_client(*args: Any, **kwargs: Any) -> httpx.Client:
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(httpx, "Client", fake_client)
    cfg = svc.SendGridConfig(api_key="SG.x", forward_to="x@y.no", forward_from="a@b.no")
    # Should not raise.
    svc.forward_copy_via_sendgrid(
        cfg, {"subject": "s", "text_body": "", "attachments": []}
    )


# ── Router integration ──────────────────────────────────────────────────────


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    from api.dependencies import get_db
    from api.routers import sendgrid_inbound as router_mod

    monkeypatch.setenv("SENDGRID_API_KEY", "SG.test")
    monkeypatch.setenv("SENDGRID_INBOUND_TOKEN", "secret-token")
    app = FastAPI()
    app.include_router(router_mod.router)
    app.dependency_overrides[get_db] = lambda: MagicMock()
    # Stub downstream so we only test the router layer.
    monkeypatch.setattr(
        router_mod, "match_and_ingest", lambda parsed, db: {"status": "orphaned"}
    )
    monkeypatch.setattr(router_mod, "forward_copy_via_sendgrid", lambda cfg, p: None)
    return TestClient(app)


def test_router_rejects_without_token(client: TestClient):
    resp = client.post("/webhooks/sendgrid/inbound", data={"from": "a@b.no"})
    assert resp.status_code == 200
    assert resp.json()["reason"] == "token_mismatch"


def test_router_accepts_with_correct_token(client: TestClient):
    resp = client.post(
        "/webhooks/sendgrid/inbound?token=secret-token",
        data={
            "from": "a@b.no",
            "to": "anbud@meglerai.no",
            "subject": "s",
            "headers": "Message-ID: <m1@x>",
            "text": "",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "orphaned"


def test_router_short_circuits_when_sendgrid_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
):
    from api.dependencies import get_db
    from api.routers import sendgrid_inbound as router_mod

    monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
    app = FastAPI()
    app.include_router(router_mod.router)
    app.dependency_overrides[get_db] = lambda: MagicMock()
    c = TestClient(app)
    resp = c.post("/webhooks/sendgrid/inbound", data={"from": "a@b.no"})
    assert resp.status_code == 200
    assert resp.json()["reason"] == "sendgrid_not_configured"
