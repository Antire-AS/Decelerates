"""Unit tests for AzureEmailNotificationAdapter — HTML content + configuration.

Tests exercise the adapter without sending real emails (conn_str=None → not configured).
"""

from api.adapters.notification_adapter import (
    AzureEmailNotificationAdapter,
    NotificationConfig,
)


def _adapter(conn_str=None, sender=None):
    cfg = NotificationConfig(
        conn_str=conn_str,
        sender=sender or "noreply@test.azurecomm.net",
    )
    return AzureEmailNotificationAdapter(cfg)


# ── is_configured ─────────────────────────────────────────────────────────────

def test_not_configured_when_conn_str_none():
    assert _adapter(conn_str=None).is_configured() is False


def test_not_configured_when_conn_str_empty():
    assert _adapter(conn_str="").is_configured() is False


def test_not_configured_when_placeholder_value():
    assert _adapter(conn_str="your_connection_string_here").is_configured() is False


def test_configured_when_real_conn_str():
    assert _adapter(conn_str="endpoint=https://acs.example.com;accesskey=abc").is_configured() is True


# ── send_email returns False when not configured ──────────────────────────────

def test_send_email_returns_false_when_not_configured():
    result = _adapter().send_email("to@test.com", "Subject", "<p>body</p>")
    assert result is False


# ── send_forsikringstilbud ────────────────────────────────────────────────────

def test_send_forsikringstilbud_returns_false_when_not_configured():
    result = _adapter().send_forsikringstilbud(
        "to@test.com", "Norsk AS", "123456789", "https://app.example.com/?token=abc"
    )
    assert result is False


def test_send_forsikringstilbud_generates_html_with_name(monkeypatch):
    """When configured, the generated email HTML contains the client name."""
    sent_messages = []

    def _fake_send(self, to, subject, body_html):
        sent_messages.append({"to": to, "subject": subject, "body": body_html})
        return True

    monkeypatch.setattr(AzureEmailNotificationAdapter, "send_email", _fake_send)
    monkeypatch.setattr(AzureEmailNotificationAdapter, "is_configured", lambda self: True)

    _adapter(conn_str="fake").send_forsikringstilbud(
        "client@firma.no", "Norsk AS", "984851006", "https://app.example.com/?token=xyz"
    )
    assert sent_messages
    body = sent_messages[0]["body"]
    assert "Norsk AS" in body
    assert "984851006" in body
    assert "https://app.example.com/?token=xyz" in body


def test_send_forsikringstilbud_subject_contains_client_name(monkeypatch):
    sent = []
    monkeypatch.setattr(AzureEmailNotificationAdapter, "send_email",
                        lambda self, to, subject, body: sent.append(subject) or True)
    monkeypatch.setattr(AzureEmailNotificationAdapter, "is_configured", lambda self: True)
    _adapter(conn_str="fake").send_forsikringstilbud(
        "x@x.no", "MinBedrift AS", "111222333", "https://app.example.com"
    )
    assert "MinBedrift AS" in sent[0]


# ── send_sla_generated ────────────────────────────────────────────────────────

def test_send_sla_generated_returns_false_when_not_configured():
    assert _adapter().send_sla_generated("to@test.com", "Client AS") is False


def test_send_sla_generated_html_contains_client_name(monkeypatch):
    bodies = []
    monkeypatch.setattr(AzureEmailNotificationAdapter, "send_email",
                        lambda self, to, subject, body: bodies.append(body) or True)
    monkeypatch.setattr(AzureEmailNotificationAdapter, "is_configured", lambda self: True)
    _adapter(conn_str="fake").send_sla_generated("x@x.no", "Client AS")
    assert "Client AS" in bodies[0]


# ── send_activity_reminders ───────────────────────────────────────────────────

def test_send_activity_reminders_empty_returns_false():
    assert _adapter().send_activity_reminders("to@test.com", [], []) is False


def test_send_activity_reminders_returns_false_when_not_configured():
    overdue = [{"due_date": "2026-01-01", "activity_type": "call",
                "subject": "Call client", "orgnr": "123456789"}]
    assert _adapter().send_activity_reminders("to@test.com", overdue, []) is False


def test_activity_row_contains_due_date():
    row_html = AzureEmailNotificationAdapter._activity_row(
        {"due_date": "2026-04-15", "activity_type": "meeting",
         "subject": "Møte med klient", "orgnr": "984851006"},
        "#c0392b",
    )
    assert "2026-04-15" in row_html
    assert "Meeting" in row_html
    assert "Møte med klient" in row_html
    assert "984851006" in row_html


def test_activity_row_missing_orgnr_shows_dash():
    row_html = AzureEmailNotificationAdapter._activity_row(
        {"due_date": "2026-04-15", "activity_type": "task",
         "subject": "Follow up", "orgnr": None},
        "#e67e22",
    )
    assert "–" in row_html


# ── send_portfolio_digest ─────────────────────────────────────────────────────

def test_send_portfolio_digest_empty_returns_false():
    assert _adapter().send_portfolio_digest("to@test.com", "My Portfolio", []) is False


def test_send_portfolio_digest_returns_false_when_not_configured():
    alerts = [{"navn": "Test AS", "severity": "Høy", "alert_type": "Inntektsvekst",
               "detail": "+25%", "year_from": 2023, "year_to": 2024}]
    assert _adapter().send_portfolio_digest("to@test.com", "My Portfolio", alerts) is False


# ── send_renewal_digest ───────────────────────────────────────────────────────

def test_send_renewal_digest_empty_returns_false():
    assert _adapter().send_renewal_digest("to@test.com", []) is False


def test_send_renewal_digest_returns_false_when_not_configured():
    renewals = [{"orgnr": "123456789", "insurer": "If", "product_type": "Ting",
                 "annual_premium_nok": 50000, "renewal_date": "2026-05-01",
                 "days_to_renewal": 40}]
    assert _adapter().send_renewal_digest("to@test.com", renewals) is False


# ── send_risk_report_ready ────────────────────────────────────────────────────

def test_send_risk_report_ready_returns_false_when_not_configured():
    assert _adapter().send_risk_report_ready("to@test.com", "984851006", "DNB Bank ASA") is False
