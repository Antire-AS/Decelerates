"""Unit tests for the anbudspakke-email endpoint + adapter attachment path.

Three layers:
  1. Schema validation — EmailStr-style checks without the extra dep
  2. Default email body builder — HTML shape + broker-message prefix
  3. ACS adapter base64 encoding of the PDF bytes
"""

from __future__ import annotations

import base64
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from api.schemas.email import AnbudspakkeEmailRequest, _validate_email


# ── Email validation ────────────────────────────────────────────────────────


def test_validate_email_accepts_standard_form():
    assert _validate_email("demo@example.com") == "demo@example.com"


def test_validate_email_trims_whitespace():
    assert _validate_email("  broker@firma.no  ") == "broker@firma.no"


def test_validate_email_rejects_missing_at_sign():
    with pytest.raises(ValueError):
        _validate_email("broker-firma.no")


def test_validate_email_rejects_empty():
    with pytest.raises(ValueError):
        _validate_email("")


def test_request_allows_cc_list():
    r = AnbudspakkeEmailRequest(
        to="insurer@gjensidige.no",
        cc=["partner@firma.no", "colleague@firma.no"],
    )
    assert r.cc == ["partner@firma.no", "colleague@firma.no"]


def test_request_rejects_invalid_cc():
    with pytest.raises(ValidationError):
        AnbudspakkeEmailRequest(
            to="insurer@gjensidige.no",
            cc=["not-an-email"],
        )


def test_request_subject_and_message_optional():
    r = AnbudspakkeEmailRequest(to="x@y.no")
    assert r.subject is None
    assert r.message is None
    assert r.cc == []


# ── Default email body ──────────────────────────────────────────────────────


def test_default_body_includes_client_name():
    from api.routers.anbud_package import _default_email_body

    html = _default_email_body("Equinor ASA", None)
    assert "Equinor ASA" in html
    assert "<html>" in html.lower()


def test_default_body_prefixes_broker_message_above_horizontal_rule():
    from api.routers.anbud_package import _default_email_body

    html = _default_email_body("Equinor ASA", "Hei — her er risikounderlaget.")
    # Broker message appears before the <hr> separator
    assert "Hei — her er risikounderlaget." in html
    msg_idx = html.index("Hei")
    hr_idx = html.index("<hr")
    assert msg_idx < hr_idx


def test_default_body_no_empty_prefix_when_message_omitted():
    from api.routers.anbud_package import _default_email_body

    html = _default_email_body("Equinor ASA", None)
    # No <hr> separator in the bare-default case
    assert "<hr" not in html


# ── ACS attachment encoding ─────────────────────────────────────────────────


@pytest.fixture
def _real_azure_email_client():
    """conftest stubs `azure.communication.email`. This test needs to
    verify the adapter wraps attachments in a specific message shape —
    we patch the EmailClient so we can inspect what's sent to begin_send."""
    # The adapter imports lazily inside _email_client, so we just need the
    # module to exist. The stub from conftest is fine for that.
    yield


def test_adapter_encodes_attachment_as_base64(_real_azure_email_client):
    """Attachment bytes must hit ACS as base64 in `contentInBase64`."""
    from api.adapters.notification_adapter import (
        AzureEmailNotificationAdapter,
        NotificationConfig,
    )
    from api.ports.driven.notification_port import EmailAttachment

    adapter = AzureEmailNotificationAdapter(
        NotificationConfig(
            conn_str="endpoint=https://fake.comm.azure.com/;accesskey=AAAA=="
        )
    )
    captured_message = {}

    class _FakePoller:
        def result(self):
            return {"id": "fake"}

    class _FakeClient:
        def begin_send(self, message):
            captured_message.update(message)
            return _FakePoller()

    with patch.object(adapter, "_email_client", return_value=_FakeClient()):
        ok = adapter.send_email_with_attachments(
            to="insurer@example.com",
            subject="Test",
            body_html="<p>hi</p>",
            attachments=[
                EmailAttachment(
                    filename="anbudspakke-123.pdf",
                    content_type="application/pdf",
                    content=b"%PDF-1.3\nfake",
                ),
            ],
        )
    assert ok is True
    assert captured_message["recipients"]["to"] == [{"address": "insurer@example.com"}]
    atts = captured_message["attachments"]
    assert len(atts) == 1
    assert atts[0]["name"] == "anbudspakke-123.pdf"
    assert atts[0]["contentType"] == "application/pdf"
    # Base64 roundtrip gives us back the original bytes
    assert base64.b64decode(atts[0]["contentInBase64"]) == b"%PDF-1.3\nfake"


def test_adapter_returns_false_when_not_configured():
    from api.adapters.notification_adapter import (
        AzureEmailNotificationAdapter,
        NotificationConfig,
    )
    from api.ports.driven.notification_port import EmailAttachment

    adapter = AzureEmailNotificationAdapter(NotificationConfig(conn_str=None))
    ok = adapter.send_email_with_attachments(
        to="x@y.com",
        subject="S",
        body_html="b",
        attachments=[EmailAttachment("a.pdf", "application/pdf", b"x")],
    )
    assert ok is False


def test_adapter_includes_cc_when_given(_real_azure_email_client):
    from api.adapters.notification_adapter import (
        AzureEmailNotificationAdapter,
        NotificationConfig,
    )

    adapter = AzureEmailNotificationAdapter(
        NotificationConfig(conn_str="endpoint=https://fake/;accesskey=A==")
    )
    captured_message = {}

    class _FakePoller:
        def result(self):
            return None

    class _FakeClient:
        def begin_send(self, message):
            captured_message.update(message)
            return _FakePoller()

    with patch.object(adapter, "_email_client", return_value=_FakeClient()):
        adapter.send_email_with_attachments(
            to="insurer@example.com",
            subject="S",
            body_html="<p/>",
            attachments=[],
            cc=["cc1@firma.no", "cc2@firma.no"],
        )
    assert captured_message["recipients"]["cc"] == [
        {"address": "cc1@firma.no"},
        {"address": "cc2@firma.no"},
    ]
