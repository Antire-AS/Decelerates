"""Unit tests for the Microsoft Graph inbound email service and router.

All HTTP calls are intercepted via `httpx.MockTransport` so the tests run
without any network dependency or Graph credentials.
"""

from __future__ import annotations

import base64
import json
from typing import Any, Dict
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.adapters.msgraph_email_adapter import MsGraphConfig
from api.services import msgraph_inbound_service as svc

# ── extract_resource_path ────────────────────────────────────────────────────


def test_extract_resource_path_happy():
    n = {"resource": "Users/abc/Messages/xyz"}
    assert svc.extract_resource_path(n) == "Users/abc/Messages/xyz"


def test_extract_resource_path_strips_leading_slash():
    n = {"resource": "/Users/abc/Messages/xyz"}
    assert svc.extract_resource_path(n) == "Users/abc/Messages/xyz"


def test_extract_resource_path_missing():
    assert svc.extract_resource_path({}) is None


def test_extract_resource_path_non_string():
    assert svc.extract_resource_path({"resource": 42}) is None


def test_extract_resource_path_empty():
    assert svc.extract_resource_path({"resource": ""}) is None


# ── _decode_attachment ───────────────────────────────────────────────────────


def test_decode_file_attachment_success():
    raw = b"Hello PDF"
    att = {
        "@odata.type": "#microsoft.graph.fileAttachment",
        "name": "offer.pdf",
        "contentType": "application/pdf",
        "contentBytes": base64.b64encode(raw).decode(),
    }
    out = svc._decode_attachment(att)
    assert out is not None
    assert out["filename"] == "offer.pdf"
    assert out["content_type"] == "application/pdf"
    assert out["content"] == raw


def test_decode_attachment_skips_item_type():
    att = {
        "@odata.type": "#microsoft.graph.itemAttachment",
        "name": "inner.msg",
    }
    assert svc._decode_attachment(att) is None


def test_decode_attachment_handles_bad_base64():
    att = {
        "@odata.type": "#microsoft.graph.fileAttachment",
        "name": "bad.bin",
        "contentType": "application/octet-stream",
        "contentBytes": "not-base64!!!",
    }
    # Fallback: returns None but does not raise.
    assert svc._decode_attachment(att) is None


# ── fetch_graph_token (with mock transport) ──────────────────────────────────


def _token_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "login.microsoftonline.com"
        assert b"client_credentials" in request.content
        return httpx.Response(200, json={"access_token": "tok-123"})

    return httpx.MockTransport(handler)


def test_fetch_graph_token(monkeypatch: pytest.MonkeyPatch):
    cfg = MsGraphConfig(
        tenant_id="t", client_id="c", client_secret="s", service_mailbox="m"
    )

    real_client = httpx.Client

    def fake_client(*args: Any, **kwargs: Any) -> httpx.Client:
        return real_client(transport=_token_transport(), **kwargs)

    monkeypatch.setattr(httpx, "Client", fake_client)
    assert svc.fetch_graph_token(cfg) == "tok-123"


# ── fetch_and_parse_message ──────────────────────────────────────────────────


def _message_transport():
    pdf_bytes = b"%PDF-1.4 pretend"

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/attachments"):
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "@odata.type": "#microsoft.graph.fileAttachment",
                            "name": "offer.pdf",
                            "contentType": "application/pdf",
                            "contentBytes": base64.b64encode(pdf_bytes).decode(),
                        }
                    ]
                },
            )
        # Message fetch
        return httpx.Response(
            200,
            json={
                "subject": "Re: anbud [ref: TENDER-5-42]",
                "from": {"emailAddress": {"address": "insurer@example.com"}},
                "toRecipients": [{"emailAddress": {"address": "anbud@meglerai.no"}}],
                "body": {"contentType": "text", "content": "Here's our offer"},
                "hasAttachments": True,
            },
        )

    return httpx.MockTransport(handler)


def test_fetch_and_parse_message_happy(monkeypatch: pytest.MonkeyPatch):
    real_client = httpx.Client

    def fake_client(*args: Any, **kwargs: Any) -> httpx.Client:
        return real_client(transport=_message_transport(), **kwargs)

    monkeypatch.setattr(httpx, "Client", fake_client)
    parsed = svc.fetch_and_parse_message("Users/u/Messages/m", "tok")
    assert parsed["subject"] == "Re: anbud [ref: TENDER-5-42]"
    assert parsed["sender"] == "insurer@example.com"
    assert parsed["recipient"] == "anbud@meglerai.no"
    assert parsed["text_body"] == "Here's our offer"
    assert len(parsed["attachments"]) == 1
    assert parsed["attachments"][0]["filename"] == "offer.pdf"
    assert parsed["attachments"][0]["content"] == b"%PDF-1.4 pretend"


def test_fetch_and_parse_message_includes_internet_message_id(
    monkeypatch: pytest.MonkeyPatch,
):
    """internetMessageId is plumbed through as the dedup key."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert "internetMessageId" in str(request.url)
        return httpx.Response(
            200,
            json={
                "subject": "hi",
                "from": {"emailAddress": {"address": "a@b.no"}},
                "toRecipients": [],
                "body": {"contentType": "text", "content": ""},
                "hasAttachments": False,
                "internetMessageId": "<graph-msg@example.com>",
            },
        )

    real_client = httpx.Client

    def fake_client(*args: Any, **kwargs: Any) -> httpx.Client:
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(httpx, "Client", fake_client)
    parsed = svc.fetch_and_parse_message("Users/u/Messages/m", "tok")
    assert parsed["message_id"] == "<graph-msg@example.com>"


def test_fetch_and_parse_message_no_attachments(monkeypatch: pytest.MonkeyPatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/Messages/m")
        return httpx.Response(
            200,
            json={
                "subject": "hello",
                "from": {"emailAddress": {"address": "a@b.no"}},
                "toRecipients": [],
                "body": {"contentType": "html", "content": "<p>hi</p>"},
                "hasAttachments": False,
            },
        )

    real_client = httpx.Client

    def fake_client(*args: Any, **kwargs: Any) -> httpx.Client:
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(httpx, "Client", fake_client)
    parsed = svc.fetch_and_parse_message("Users/u/Messages/m", "tok")
    assert parsed["attachments"] == []
    # HTML body is intentionally dropped — we only match on subject.
    assert parsed["text_body"] == ""


# ── Subscription helpers ─────────────────────────────────────────────────────


def test_create_subscription_posts_expected_body(monkeypatch: pytest.MonkeyPatch):
    captured: Dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1.0/subscriptions"
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"id": "sub-1", **json.loads(request.content)})

    real_client = httpx.Client

    def fake_client(*args: Any, **kwargs: Any) -> httpx.Client:
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(httpx, "Client", fake_client)
    cfg = MsGraphConfig(
        tenant_id="t",
        client_id="c",
        client_secret="s",
        service_mailbox="anbud@meglerai.no",
    )
    result = svc.create_subscription(
        cfg,
        "https://meglerai.no/bapi/webhooks/msgraph/inbound",
        "secret-state",
        token="tok",
    )
    assert result["id"] == "sub-1"
    assert captured["changeType"] == "created"
    assert captured["resource"].endswith("Inbox')/messages")
    assert captured["clientState"] == "secret-state"
    assert captured["notificationUrl"].endswith("/webhooks/msgraph/inbound")


# ── Router integration (validation handshake + client-state gate) ────────────


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Build a tiny FastAPI app with just the msgraph_inbound router
    mounted so we don't drag in the full main.py startup."""
    monkeypatch.setenv("AZURE_AD_TENANT_ID", "t")
    monkeypatch.setenv("AZURE_AD_CLIENT_ID", "c")
    monkeypatch.setenv("AZURE_AD_CLIENT_SECRET", "s")
    monkeypatch.setenv("MS_GRAPH_SERVICE_MAILBOX", "anbud@meglerai.no")
    from api.routers import msgraph_inbound as router_mod
    from api.dependencies import get_db

    app = FastAPI()
    app.include_router(router_mod.router)
    app.dependency_overrides[get_db] = lambda: MagicMock()
    return TestClient(app)


def test_validation_token_handshake(client: TestClient):
    resp = client.post("/webhooks/msgraph/inbound?validationToken=handshake-abc")
    assert resp.status_code == 200
    assert resp.text == "handshake-abc"
    assert resp.headers["content-type"].startswith("text/plain")


def test_empty_value_returns_processed_zero(client: TestClient):
    resp = client.post(
        "/webhooks/msgraph/inbound",
        json={"value": []},
    )
    assert resp.status_code == 200
    assert resp.json() == {"processed": 0, "results": []}


def test_client_state_mismatch_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("MS_GRAPH_SUBSCRIPTION_CLIENT_STATE", "expected")
    resp = client.post(
        "/webhooks/msgraph/inbound",
        json={
            "value": [
                {
                    "clientState": "WRONG",
                    "resource": "Users/u/Messages/m",
                }
            ]
        },
    )
    assert resp.status_code == 200
    assert resp.json()["error"] == "client_state_mismatch"
    assert resp.json()["processed"] == 0


def test_happy_path_end_to_end(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MS_GRAPH_SUBSCRIPTION_CLIENT_STATE", "ok")
    # Stub Graph HTTP layer + downstream match_and_ingest
    fake_token = "tok-xyz"
    monkeypatch.setattr(svc, "fetch_graph_token", lambda config: fake_token)
    monkeypatch.setattr(
        svc,
        "fetch_and_parse_message",
        lambda resource, token: {
            "subject": "Re: [ref: TENDER-1-2]",
            "sender": "x@y.no",
            "recipient": "anbud@meglerai.no",
            "text_body": "",
            "attachments": [],
        },
    )
    # Patch the router's imported reference too (import-time binding)
    from api.routers import msgraph_inbound as router_mod

    monkeypatch.setattr(router_mod, "fetch_graph_token", lambda config: fake_token)
    monkeypatch.setattr(
        router_mod,
        "fetch_and_parse_message",
        lambda resource, token: {
            "subject": "Re: [ref: TENDER-1-2]",
            "sender": "x@y.no",
            "recipient": "anbud@meglerai.no",
            "text_body": "",
            "attachments": [],
        },
    )
    monkeypatch.setattr(
        router_mod,
        "match_and_ingest",
        lambda parsed, db: {
            "status": "matched",
            "tender_id": 1,
            "recipient_id": 2,
            "offer_id": None,
            "pdf_attachments": 0,
        },
    )
    resp = client.post(
        "/webhooks/msgraph/inbound",
        json={
            "value": [
                {
                    "clientState": "ok",
                    "resource": "Users/anbud@meglerai.no/Messages/abc",
                }
            ]
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["processed"] == 1
    assert body["results"][0]["status"] == "matched"


# ── /health/msgraph-inbound ─────────────────────────────────────────────────


def test_health_degraded_when_config_missing(
    monkeypatch: pytest.MonkeyPatch,
):
    """With no env vars set, the health probe must 503 with
    graph_not_configured — never silently report healthy."""
    monkeypatch.delenv("AZURE_AD_TENANT_ID", raising=False)
    monkeypatch.delenv("AZURE_AD_CLIENT_ID", raising=False)
    monkeypatch.delenv("AZURE_AD_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("MS_GRAPH_SERVICE_MAILBOX", raising=False)
    from api.routers import msgraph_inbound as router_mod

    app = FastAPI()
    app.include_router(router_mod.router)
    client = TestClient(app)

    resp = client.get("/health/msgraph-inbound")
    assert resp.status_code == 503
    assert resp.json()["reason"] == "graph_not_configured"


def _configured_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("AZURE_AD_TENANT_ID", "t")
    monkeypatch.setenv("AZURE_AD_CLIENT_ID", "c")
    monkeypatch.setenv("AZURE_AD_CLIENT_SECRET", "s")
    monkeypatch.setenv("MS_GRAPH_SERVICE_MAILBOX", "anbud@meglerai.no")
    from api.routers import msgraph_inbound as router_mod

    monkeypatch.setattr(router_mod, "fetch_graph_token", lambda config: "tok")
    app = FastAPI()
    app.include_router(router_mod.router)
    return TestClient(app)


def test_health_ok_when_subscription_has_plenty_of_runway(
    monkeypatch: pytest.MonkeyPatch,
):
    from datetime import datetime, timedelta, timezone

    from api.routers import msgraph_inbound as router_mod

    client = _configured_client(monkeypatch)
    expiry = datetime.now(timezone.utc) + timedelta(hours=60)
    monkeypatch.setattr(
        router_mod,
        "list_subscriptions",
        lambda config, token=None: [
            {
                "id": "sub-1",
                "resource": "users/anbud@meglerai.no/mailFolders('Inbox')/messages",
                "expirationDateTime": expiry.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        ],
    )
    resp = client.get("/health/msgraph-inbound")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["expires_in_minutes"] > 3000


def test_health_degraded_when_no_active_subscription(
    monkeypatch: pytest.MonkeyPatch,
):
    from api.routers import msgraph_inbound as router_mod

    client = _configured_client(monkeypatch)
    monkeypatch.setattr(router_mod, "list_subscriptions", lambda config, token=None: [])
    resp = client.get("/health/msgraph-inbound")
    assert resp.status_code == 503
    assert resp.json()["reason"] == "no_active_subscription"


def test_health_degraded_when_subscription_expiring_soon(
    monkeypatch: pytest.MonkeyPatch,
):
    """<4h to expiry trips the alert so we get paged before silence."""
    from datetime import datetime, timedelta, timezone

    from api.routers import msgraph_inbound as router_mod

    client = _configured_client(monkeypatch)
    expiry = datetime.now(timezone.utc) + timedelta(hours=2)
    monkeypatch.setattr(
        router_mod,
        "list_subscriptions",
        lambda config, token=None: [
            {
                "id": "sub-1",
                "resource": "users/anbud@meglerai.no/mailFolders('Inbox')/messages",
                "expirationDateTime": expiry.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        ],
    )
    resp = client.get("/health/msgraph-inbound")
    assert resp.status_code == 503
    body = resp.json()
    assert body["reason"] == "expiring_soon"
    assert body["expires_in_minutes"] < 240


def test_health_ignores_subscriptions_for_other_mailboxes(
    monkeypatch: pytest.MonkeyPatch,
):
    """A subscription on a different mailbox must not be counted as ours."""
    from datetime import datetime, timedelta, timezone

    from api.routers import msgraph_inbound as router_mod

    client = _configured_client(monkeypatch)
    other_expiry = datetime.now(timezone.utc) + timedelta(hours=60)
    monkeypatch.setattr(
        router_mod,
        "list_subscriptions",
        lambda config, token=None: [
            {
                "id": "sub-other",
                "resource": "users/someone-else@meglerai.no/mailFolders('Inbox')/messages",
                "expirationDateTime": other_expiry.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        ],
    )
    resp = client.get("/health/msgraph-inbound")
    assert resp.status_code == 503
    assert resp.json()["reason"] == "no_active_subscription"


def test_health_degraded_when_graph_unreachable(
    monkeypatch: pytest.MonkeyPatch,
):
    from api.routers import msgraph_inbound as router_mod

    client = _configured_client(monkeypatch)

    def _boom(config, token=None):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(router_mod, "list_subscriptions", _boom)
    resp = client.get("/health/msgraph-inbound")
    assert resp.status_code == 503
    assert resp.json()["reason"].startswith("graph_unreachable")
