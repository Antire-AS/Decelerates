"""Unit tests for api/services/signicat_service.py.

Focus on the security-critical bits: HMAC webhook signature verification
and the configuration gate. The Signicat REST call is mocked since it
requires a real account and webhook endpoint.

Updated 2026-04-12 for the OAuth2 client_credentials flow (client_id +
client_secret instead of api_key).
"""
import hashlib
import hmac
from unittest.mock import MagicMock, patch

import pytest

from api.services.signicat_service import SignicatConfig, SignicatService


def _full_config():
    return SignicatConfig(
        api_base="https://api.signicat.example",
        client_id="sandbox-test-123",
        client_secret="secret-abc",
        webhook_secret="webhook-secret-xyz",
        webhook_url="https://api.broker.example/webhooks/signicat",
    )


def test_is_configured_false_by_default():
    assert SignicatService(SignicatConfig()).is_configured() is False


def test_is_configured_requires_client_id_and_secret():
    cfg = SignicatConfig(api_base="https://x", client_id="id", client_secret="")
    assert SignicatService(cfg).is_configured() is False
    cfg = SignicatConfig(api_base="https://x", client_id="id", client_secret="s")
    assert SignicatService(cfg).is_configured() is True


def test_is_configured_webhook_not_required():
    """Webhook is optional — signing works without it (broker checks status manually)."""
    cfg = SignicatConfig(api_base="https://x", client_id="id", client_secret="s")
    assert SignicatService(cfg).is_configured() is True


def test_create_signing_session_raises_when_not_configured():
    with pytest.raises(RuntimeError, match="not configured"):
        SignicatService(SignicatConfig()).create_signing_session(
            b"pdf", "client@x.no", "Client", "title",
        )


# ── HMAC verification (security-critical) ────────────────────────────────────


def _signature(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_verify_webhook_accepts_valid_signature():
    svc = SignicatService(_full_config())
    body = b'{"sessionId":"sess-123","sessionStatus":"signed"}'
    sig = _signature(body, "webhook-secret-xyz")
    assert svc.verify_webhook(body, sig) is True


def test_verify_webhook_rejects_invalid_signature():
    svc = SignicatService(_full_config())
    body = b'{"sessionStatus":"signed"}'
    assert svc.verify_webhook(body, "0" * 64) is False


def test_verify_webhook_rejects_tampered_body():
    """Even a 1-byte change in the body must invalidate the signature."""
    svc = SignicatService(_full_config())
    original = b'{"sessionStatus":"signed"}'
    sig = _signature(original, "webhook-secret-xyz")
    tampered = b'{"sessionStatus":"forged"}'
    assert svc.verify_webhook(tampered, sig) is False


def test_verify_webhook_rejects_when_no_secret_configured():
    svc = SignicatService(SignicatConfig(api_base="https://x", client_id="id", client_secret="s"))
    assert svc.verify_webhook(b"anything", "anything") is False


def test_verify_webhook_rejects_missing_signature_header():
    svc = SignicatService(_full_config())
    assert svc.verify_webhook(b"body", "") is False


# ── Webhook payload parsing ──────────────────────────────────────────────────


def test_parse_webhook_extracts_known_fields():
    svc = SignicatService(_full_config())
    payload = {
        "sessionId": "sess-42",
        "sessionStatus": "signed",
        "documentUrl": "https://signicat.example/docs/42.pdf",
        "completedTime": "2026-04-07T12:00:00Z",
    }
    parsed = svc.parse_webhook(payload)
    assert parsed["session_id"] == "sess-42"
    assert parsed["status"] == "signed"
    assert parsed["signed_pdf_url"] == "https://signicat.example/docs/42.pdf"


def test_parse_webhook_falls_back_to_alternate_field_names():
    """Signicat may use 'id' in some responses."""
    svc = SignicatService(_full_config())
    parsed = svc.parse_webhook({"id": "sess-99"})
    assert parsed["session_id"] == "sess-99"


# ── create_signing_session (mocked httpx) ────────────────────────────────────


def test_create_signing_session_posts_pdf_and_returns_session():
    svc = SignicatService(_full_config())
    # Mock the OAuth2 token call + the session creation call
    token_resp = MagicMock()
    token_resp.json.return_value = {"access_token": "test-token"}
    token_resp.raise_for_status = MagicMock()
    session_resp = MagicMock()
    session_resp.json.return_value = {
        "sessionId": "sess-1",
        "signingUrl": "https://signicat.example/sign/sess-1",
    }
    session_resp.raise_for_status = MagicMock()

    with patch("api.services.signicat_service.httpx.Client") as MockClient:
        mock_client = MockClient.return_value.__enter__.return_value
        mock_client.post.side_effect = [token_resp, session_resp]
        result = svc.create_signing_session(
            b"%PDF-1.4 fake", "client@x.no", "Ola Nordmann", "Forsikringstilbud",
        )
    assert result["session_id"] == "sess-1"
    assert result["signing_url"].endswith("sess-1")
