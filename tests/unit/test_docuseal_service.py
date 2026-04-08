"""Unit tests for api/services/docuseal_service.py.

Mirrors test_signicat_service.py — both providers must satisfy the same
duck-typed protocol so the router can swap between them with a single
env var change. Tests focus on the security-critical bits (HMAC webhook
verification + config gate) and on the response-shape parsing.
"""
import hashlib
import hmac
from unittest.mock import MagicMock, patch

import pytest

from api.services.docuseal_service import (
    DocuSealConfig,
    DocuSealService,
    get_signing_service,
)


def _full_config():
    return DocuSealConfig(
        api_base="https://api.docuseal.example",
        api_key="key-abc",
        webhook_secret="webhook-secret-xyz",
        webhook_url="https://api.broker.example/webhooks/docuseal",
    )


# ── Configuration gate ───────────────────────────────────────────────────────


def test_is_configured_false_by_default():
    assert DocuSealService(DocuSealConfig()).is_configured() is False


def test_is_configured_requires_api_key_and_webhook_secret():
    """webhook_url is optional (some deploys use polling) but the secret is
    required for HMAC verification."""
    cfg = DocuSealConfig(api_base="https://x", api_key="k", webhook_secret="")
    assert DocuSealService(cfg).is_configured() is False
    cfg = DocuSealConfig(api_base="https://x", api_key="k", webhook_secret="s")
    assert DocuSealService(cfg).is_configured() is True


def test_create_signing_session_raises_when_not_configured():
    with pytest.raises(RuntimeError, match="not configured"):
        DocuSealService(DocuSealConfig()).create_signing_session(
            b"pdf", "client@x.no", "Client", "title",
        )


# ── HMAC verification (security-critical) ────────────────────────────────────


def _signature(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_verify_webhook_accepts_valid_signature():
    svc = DocuSealService(_full_config())
    body = b'{"event_type":"form.completed","data":{"submission_id":42}}'
    sig = _signature(body, "webhook-secret-xyz")
    assert svc.verify_webhook(body, sig) is True


def test_verify_webhook_rejects_invalid_signature():
    svc = DocuSealService(_full_config())
    body = b'{"event_type":"form.completed"}'
    assert svc.verify_webhook(body, "0" * 64) is False


def test_verify_webhook_rejects_tampered_body():
    """Even a 1-byte change in the body must invalidate the signature."""
    svc = DocuSealService(_full_config())
    original = b'{"event_type":"form.completed"}'
    sig = _signature(original, "webhook-secret-xyz")
    tampered = b'{"event_type":"form.declined"}'
    assert svc.verify_webhook(tampered, sig) is False


def test_verify_webhook_rejects_when_no_secret_configured():
    svc = DocuSealService(DocuSealConfig(api_base="https://x", api_key="k"))
    assert svc.verify_webhook(b"anything", "anything") is False


def test_verify_webhook_rejects_missing_signature_header():
    svc = DocuSealService(_full_config())
    assert svc.verify_webhook(b"body", "") is False


# ── Webhook payload parsing ──────────────────────────────────────────────────


def test_parse_webhook_completed_maps_to_signed_status():
    svc = DocuSealService(_full_config())
    payload = {
        "event_type": "form.completed",
        "data": {
            "submission_id": 42,
            "completed_at":  "2026-04-08T12:00:00Z",
            "documents": [
                {"name": "anbefaling.pdf", "url": "https://docuseal.example/d/42.pdf"}
            ],
        },
    }
    parsed = svc.parse_webhook(payload)
    assert parsed["session_id"]     == "42"
    assert parsed["status"]         == "signed"
    assert parsed["signed_pdf_url"] == "https://docuseal.example/d/42.pdf"
    assert parsed["signed_at"]      == "2026-04-08T12:00:00Z"


def test_parse_webhook_declined_maps_to_rejected_status():
    svc = DocuSealService(_full_config())
    parsed = svc.parse_webhook({
        "event_type": "form.declined",
        "data": {"submission_id": 7},
    })
    assert parsed["status"] == "rejected"


def test_parse_webhook_unknown_event_passes_through():
    """Unknown DocuSeal event types should not crash — pass through as-is."""
    svc = DocuSealService(_full_config())
    parsed = svc.parse_webhook({"event_type": "form.brand_new_event", "data": {}})
    assert parsed["status"] == "form.brand_new_event"


def test_parse_webhook_handles_empty_data_gracefully():
    """A malformed webhook with no data block should not crash."""
    svc = DocuSealService(_full_config())
    parsed = svc.parse_webhook({"event_type": "form.completed"})
    assert parsed["session_id"] == ""
    assert parsed["status"] == "signed"
    assert parsed["signed_pdf_url"] is None


# ── create_signing_session (mocked httpx) ────────────────────────────────────


def test_create_signing_session_posts_pdf_and_returns_session():
    """Happy-path: DocuSeal returns a list-of-submitters response shape."""
    svc = DocuSealService(_full_config())
    resp = MagicMock()
    resp.json.return_value = [
        {
            "id":            123,
            "submission_id": 42,
            "email":         "client@x.no",
            "embed_src":     "https://docuseal.example/sign/abc123",
        }
    ]
    resp.raise_for_status = MagicMock()
    with patch("api.services.docuseal_service.httpx.Client") as MockClient:
        MockClient.return_value.__enter__.return_value.post.return_value = resp
        result = svc.create_signing_session(
            b"%PDF-1.4 fake", "client@x.no", "Client Name", "Anbefaling",
        )
    assert result["session_id"]  == "42"
    assert result["signing_url"] == "https://docuseal.example/sign/abc123"


def test_create_signing_session_handles_object_response_shape():
    """DocuSeal API version drift: some endpoints wrap submitters in an object."""
    svc = DocuSealService(_full_config())
    resp = MagicMock()
    resp.json.return_value = {
        "submitters": [{"id": 99, "url": "https://docuseal.example/sign/xyz"}],
    }
    resp.raise_for_status = MagicMock()
    with patch("api.services.docuseal_service.httpx.Client") as MockClient:
        MockClient.return_value.__enter__.return_value.post.return_value = resp
        result = svc.create_signing_session(
            b"%PDF-1.4 fake", "c@x.no", "Client", "Title",
        )
    assert result["session_id"]  == "99"
    assert result["signing_url"] == "https://docuseal.example/sign/xyz"


def test_create_signing_session_sends_pdf_as_base64_in_documents_field():
    """Verify the PDF is base64-encoded into the `documents[].file` field
    (not multipart, not raw bytes) — DocuSeal's submission API requires base64."""
    import base64
    svc = DocuSealService(_full_config())
    resp = MagicMock()
    resp.json.return_value = [{"id": 1, "url": "https://x"}]
    resp.raise_for_status = MagicMock()
    captured = {}
    def _post(url, json=None, headers=None):  # noqa: ARG001
        captured["json"] = json
        captured["headers"] = headers
        return resp
    with patch("api.services.docuseal_service.httpx.Client") as MockClient:
        MockClient.return_value.__enter__.return_value.post = _post
        svc.create_signing_session(b"hello world", "x@y.no", "X", "Title")
    file_b64 = captured["json"]["documents"][0]["file"]
    assert base64.b64decode(file_b64) == b"hello world"
    assert captured["headers"]["X-Auth-Token"] == "key-abc"


# ── Provider factory ─────────────────────────────────────────────────────────


def test_get_signing_service_defaults_to_signicat(monkeypatch):
    """Backwards-compat: existing deployments without ESIGN_PROVIDER set
    must keep getting Signicat."""
    monkeypatch.delenv("ESIGN_PROVIDER", raising=False)
    from api.services.signicat_service import SignicatService
    assert isinstance(get_signing_service(), SignicatService)


def test_get_signing_service_returns_docuseal_when_env_set(monkeypatch):
    monkeypatch.setenv("ESIGN_PROVIDER", "docuseal")
    assert isinstance(get_signing_service(), DocuSealService)


def test_get_signing_service_is_case_insensitive(monkeypatch):
    monkeypatch.setenv("ESIGN_PROVIDER", "DocuSeal")
    assert isinstance(get_signing_service(), DocuSealService)
