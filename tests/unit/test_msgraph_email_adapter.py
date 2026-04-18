"""Unit tests for api/adapters/msgraph_email_adapter.py.

Mocked httpx; covers the configuration gate, the token fetch, and the
sendMail POST. We don't hit a real Graph endpoint — that requires the
external Azure AD setup documented in the adapter's docstring.
"""

from unittest.mock import MagicMock, patch

import pytest

from api.adapters.msgraph_email_adapter import MsGraphConfig, MsGraphEmailAdapter


def _full_config():
    return MsGraphConfig(
        tenant_id="tenant-id",
        client_id="client-id",
        client_secret="secret",
        service_mailbox="noreply@broker.no",
    )


def test_is_configured_false_when_any_field_blank():
    assert MsGraphEmailAdapter(MsGraphConfig()).is_configured() is False
    assert MsGraphEmailAdapter(MsGraphConfig(tenant_id="t")).is_configured() is False
    assert (
        MsGraphEmailAdapter(
            MsGraphConfig(tenant_id="t", client_id="c", client_secret="s")
        ).is_configured()
        is False
    )


def test_is_configured_true_when_all_set():
    assert MsGraphEmailAdapter(_full_config()).is_configured() is True


def test_send_email_raises_when_not_configured():
    with pytest.raises(RuntimeError, match="not configured"):
        MsGraphEmailAdapter(MsGraphConfig()).send_email(
            "to@x.no", "subj", "<p>body</p>"
        )


def test_send_email_posts_token_then_sendmail():
    """Verifies the call sequence: token request → sendMail POST."""
    adapter = MsGraphEmailAdapter(_full_config())
    token_resp = MagicMock()
    token_resp.json.return_value = {"access_token": "graph-token"}
    token_resp.raise_for_status = MagicMock()
    send_resp = MagicMock()
    send_resp.raise_for_status = MagicMock()

    with patch("api.adapters.msgraph_email_adapter.httpx.Client") as MockClient:
        instance = MockClient.return_value.__enter__.return_value
        instance.post.side_effect = [token_resp, send_resp]
        result = adapter.send_email("client@example.com", "Hello", "<p>body</p>")

    assert result == ""  # sendMail returns no message id
    # Two POSTs: token + sendMail
    assert instance.post.call_count == 2
    # The sendMail body must contain the recipient + HTML body
    send_call = instance.post.call_args_list[1]
    payload = send_call.kwargs["json"]
    assert (
        payload["message"]["toRecipients"][0]["emailAddress"]["address"]
        == "client@example.com"
    )
    assert payload["message"]["body"]["content"] == "<p>body</p>"
    assert payload["message"]["body"]["contentType"] == "HTML"
    assert payload["saveToSentItems"] is True
