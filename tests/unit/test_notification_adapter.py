"""Unit tests for api/adapters/notification_adapter.py — AzureEmailNotificationAdapter.

All ACS SDK calls are mocked; conftest.py already stubs azure.communication.email.
"""
from unittest.mock import MagicMock, patch

import pytest

from api.adapters.notification_adapter import (
    AzureEmailNotificationAdapter,
    NotificationConfig,
    _DEFAULT_SENDER,
)


def _adapter(conn_str="Endpoint=sb://test;SharedAccessKey=abc123"):
    return AzureEmailNotificationAdapter(NotificationConfig(conn_str=conn_str))


def _unconfigured():
    return AzureEmailNotificationAdapter(NotificationConfig(conn_str=None))


# ── is_configured ─────────────────────────────────────────────────────────────

def test_is_configured_true_when_conn_str_set():
    assert _adapter().is_configured() is True


def test_is_configured_false_when_no_conn_str():
    assert _unconfigured().is_configured() is False


def test_is_configured_false_when_placeholder():
    adapter = AzureEmailNotificationAdapter(
        NotificationConfig(conn_str="your_connection_string_here")
    )
    assert adapter.is_configured() is False


def test_is_configured_false_when_empty_string():
    adapter = AzureEmailNotificationAdapter(NotificationConfig(conn_str=""))
    assert adapter.is_configured() is False


# ── send_email ────────────────────────────────────────────────────────────────

def test_send_email_returns_false_when_not_configured():
    assert _unconfigured().send_email("to@test.no", "Subject", "<p>body</p>") is False


def test_send_email_returns_true_on_success():
    adapter = _adapter()
    mock_client = MagicMock()
    mock_client.begin_send.return_value.result.return_value = None
    with patch.object(adapter, "_email_client", return_value=mock_client):
        result = adapter.send_email("to@test.no", "Subject", "<p>body</p>")
    assert result is True
    mock_client.begin_send.assert_called_once()


def test_send_email_returns_false_on_exception():
    adapter = _adapter()
    mock_client = MagicMock()
    mock_client.begin_send.side_effect = Exception("ACS error")
    with patch.object(adapter, "_email_client", return_value=mock_client):
        result = adapter.send_email("to@test.no", "Subject", "<p>body</p>")
    assert result is False


def test_send_email_uses_configured_sender():
    adapter = AzureEmailNotificationAdapter(
        NotificationConfig(conn_str="valid-conn", sender="custom@example.com")
    )
    mock_client = MagicMock()
    with patch.object(adapter, "_email_client", return_value=mock_client):
        adapter.send_email("to@test.no", "Subject", "<p>body</p>")
    sent_message = mock_client.begin_send.call_args[0][0]
    assert sent_message["senderAddress"] == "custom@example.com"


# ── send_sla_generated ────────────────────────────────────────────────────────

def test_send_sla_generated_delegates_to_send_email():
    adapter = _adapter()
    with patch.object(adapter, "send_email", return_value=True) as mock_send:
        result = adapter.send_sla_generated("broker@test.no", "Firma AS")
    assert result is True
    subject, body = mock_send.call_args[0][1], mock_send.call_args[0][2]
    assert "Firma AS" in subject
    assert "Firma AS" in body


# ── send_risk_report_ready ────────────────────────────────────────────────────

def test_send_risk_report_ready_includes_orgnr_and_name():
    adapter = _adapter()
    with patch.object(adapter, "send_email", return_value=True) as mock_send:
        adapter.send_risk_report_ready("broker@test.no", "123456789", "Test AS")
    subject, body = mock_send.call_args[0][1], mock_send.call_args[0][2]
    assert "Test AS" in subject
    assert "123456789" in body


# ── send_portfolio_digest ─────────────────────────────────────────────────────

def test_send_portfolio_digest_returns_false_when_no_alerts():
    assert _adapter().send_portfolio_digest("b@test.no", "My Portfolio", []) is False


def test_send_portfolio_digest_sends_email_with_alerts():
    adapter = _adapter()
    alerts = [
        {"severity": "Kritisk", "navn": "Firma AS", "alert_type": "Høy gjeld",
         "detail": "Gjeld > 80%", "year_from": "2022", "year_to": "2023"}
    ]
    with patch.object(adapter, "send_email", return_value=True) as mock_send:
        result = adapter.send_portfolio_digest("b@test.no", "My Portfolio", alerts)
    assert result is True
    body = mock_send.call_args[0][2]
    assert "Firma AS" in body
    assert "Kritisk" in body


def test_send_portfolio_digest_subject_includes_alert_count():
    adapter = _adapter()
    alerts = [{"severity": "Høy", "navn": "A", "alert_type": "x", "detail": "", "year_from": "", "year_to": ""}]
    with patch.object(adapter, "send_email", return_value=True) as mock_send:
        adapter.send_portfolio_digest("b@test.no", "Portfolio X", alerts)
    subject = mock_send.call_args[0][1]
    assert "1" in subject


# ── send_activity_reminders ───────────────────────────────────────────────────

def test_send_activity_reminders_returns_false_when_both_empty():
    assert _adapter().send_activity_reminders("b@test.no", [], []) is False


def test_send_activity_reminders_sends_when_overdue_present():
    adapter = _adapter()
    overdue = [{"due_date": "2024-01-01", "activity_type": "call", "subject": "Follow up", "orgnr": "123"}]
    with patch.object(adapter, "send_email", return_value=True) as mock_send:
        result = adapter.send_activity_reminders("b@test.no", overdue, [])
    assert result is True
    body = mock_send.call_args[0][2]
    assert "Follow up" in body


def test_send_activity_reminders_sends_when_due_today_present():
    adapter = _adapter()
    due_today = [{"due_date": "2026-04-03", "activity_type": "email", "subject": "Send proposal", "orgnr": "456"}]
    with patch.object(adapter, "send_email", return_value=True) as mock_send:
        result = adapter.send_activity_reminders("b@test.no", [], due_today)
    assert result is True


# ── send_forsikringstilbud ────────────────────────────────────────────────────

def test_send_forsikringstilbud_includes_share_url():
    adapter = _adapter()
    with patch.object(adapter, "send_email", return_value=True) as mock_send:
        adapter.send_forsikringstilbud("client@test.no", "Firma AS", "123456789", "https://share.url/xyz")
    body = mock_send.call_args[0][2]
    assert "https://share.url/xyz" in body
    assert "Firma AS" in body


# ── send_renewal_stage_change ─────────────────────────────────────────────────

def test_send_renewal_stage_change_translates_stage_label():
    adapter = _adapter()
    with patch.object(adapter, "send_email", return_value=True) as mock_send:
        adapter.send_renewal_stage_change("b@test.no", "POL-001", "Gjensidige", "Ansvar", "accepted")
    body = mock_send.call_args[0][2]
    assert "Akseptert" in body


def test_send_renewal_stage_change_includes_policy_details():
    adapter = _adapter()
    with patch.object(adapter, "send_email", return_value=True) as mock_send:
        adapter.send_renewal_stage_change("b@test.no", "POL-999", "Storebrand", "Ting", "quoted")
    subject = mock_send.call_args[0][1]
    body = mock_send.call_args[0][2]
    assert "POL-999" in subject
    assert "Storebrand" in body


# ── send_renewal_threshold_emails ─────────────────────────────────────────────

def test_send_renewal_threshold_emails_returns_false_when_no_policies():
    assert _adapter().send_renewal_threshold_emails("b@test.no", 30, []) is False


def test_send_renewal_threshold_emails_includes_policy_details():
    adapter = _adapter()
    policies = [{"orgnr": "123", "insurer": "Gjensidige", "product_type": "Ansvar",
                 "annual_premium_nok": 50000, "renewal_date": "2026-06-01", "days_to_renewal": 28}]
    with patch.object(adapter, "send_email", return_value=True) as mock_send:
        result = adapter.send_renewal_threshold_emails("b@test.no", 30, policies)
    assert result is True
    body = mock_send.call_args[0][2]
    assert "Gjensidige" in body


# ── send_renewal_digest ───────────────────────────────────────────────────────

def test_send_renewal_digest_returns_false_when_no_renewals():
    assert _adapter().send_renewal_digest("b@test.no", []) is False


def test_send_renewal_digest_sends_email_with_renewal_data():
    adapter = _adapter()
    renewals = [{"orgnr": "123", "insurer": "If", "product_type": "Bil",
                 "annual_premium_nok": 12000, "renewal_date": "2026-05-01", "days_to_renewal": 45}]
    with patch.object(adapter, "send_email", return_value=True) as mock_send:
        result = adapter.send_renewal_digest("b@test.no", renewals)
    assert result is True
    body = mock_send.call_args[0][2]
    assert "If" in body


def test_send_renewal_digest_subject_includes_count():
    adapter = _adapter()
    renewals = [
        {"orgnr": "1", "insurer": "A", "product_type": "X", "annual_premium_nok": 1000,
         "renewal_date": "2026-05-01", "days_to_renewal": 20},
        {"orgnr": "2", "insurer": "B", "product_type": "Y", "annual_premium_nok": 2000,
         "renewal_date": "2026-05-15", "days_to_renewal": 35},
    ]
    with patch.object(adapter, "send_email", return_value=True) as mock_send:
        adapter.send_renewal_digest("b@test.no", renewals)
    subject = mock_send.call_args[0][1]
    assert "2" in subject
