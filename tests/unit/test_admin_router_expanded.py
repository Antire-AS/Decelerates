"""Expanded unit tests for api/routers/admin_router.py — email notifications and admin endpoints.

All DB queries, NotificationPort, and external services are mocked.
Tests cover portfolio-digest, renewal-threshold, activity-reminders,
coverage-gap-alerts, refresh-portfolio-risk, debug/status, and dashboard.
"""
import sys
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.auth import CurrentUser, get_current_user
from api.dependencies import get_db
from api.limiter import limiter
from api.routers.admin_router import router, _get_notification

_app = FastAPI()
_app.state.limiter = limiter
_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
_app.include_router(router)

_FAKE_USER = CurrentUser(email="test@local", name="Test", oid="test-oid", firm_id=1)


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_notification():
    n = MagicMock()
    n.is_configured.return_value = True
    n.send_portfolio_digest.return_value = True
    n.send_renewal_digest.return_value = True
    n.send_renewal_threshold_emails.return_value = True
    n.send_activity_reminders.return_value = True
    n.send_email.return_value = True
    return n


@pytest.fixture
def client(mock_db, mock_notification):
    _app.dependency_overrides[get_db] = lambda: mock_db
    _app.dependency_overrides[get_current_user] = lambda: _FAKE_USER
    _app.dependency_overrides[_get_notification] = lambda: mock_notification
    yield TestClient(_app, raise_server_exceptions=False)
    _app.dependency_overrides.clear()


def _mock_settings(email="broker@test.no"):
    s = MagicMock()
    s.contact_email = email
    return s


def _mock_policy(**kw):
    p = MagicMock()
    p.orgnr = kw.get("orgnr", "999100101")
    p.insurer = kw.get("insurer", "If")
    p.product_type = kw.get("product_type", "Ansvar")
    p.annual_premium_nok = kw.get("premium", 50000)
    p.renewal_date = kw.get("renewal_date", date.today() + timedelta(days=20))
    p.firm_id = 1
    p.renewal_brief = kw.get("renewal_brief", None)
    p.renewal_email_draft = kw.get("renewal_email_draft", None)
    p.id = kw.get("id", 1)
    return p


def _mock_activity(**kw):
    a = MagicMock()
    a.orgnr = kw.get("orgnr", "999100101")
    a.subject = kw.get("subject", "Ring kunden")
    a.activity_type = MagicMock()
    a.activity_type.value = kw.get("type_val", "call")
    a.due_date = kw.get("due_date", date.today())
    a.completed = False
    a.firm_id = 1
    a.created_by_email = "demo@broker.no"
    a.created_at = datetime(2026, 1, 1)
    return a


def _mock_firm(firm_id=1):
    f = MagicMock()
    f.id = firm_id
    return f


# ── POST /admin/portfolio-digest ─────────────────────────────────────────────

    with patch("api.routers.admin_router.collect_alerts", return_value=[]), \
         patch("api.routers.admin_router.create_notification_for_users_safe"):
        resp = client.post("/admin/portfolio-digest")
    assert resp.status_code == 200
    body = resp.json()
    assert "recipient" in body



# ── POST /admin/renewal-threshold-emails ─────────────────────────────────────

    mock_policy_svc = MagicMock()
    mock_policy_svc.get_policies_needing_renewal_notification.return_value = [_mock_policy()]
    mock_policy_svc.mark_renewal_notified.return_value = None

    with patch("api.routers.admin_router.PolicyService", return_value=mock_policy_svc), \
         patch("api.routers.admin_router.RenewalAgentService") as mock_ras, \
         patch("api.routers.admin_router.create_notification_for_users_safe"):
        mock_ras.return_value.process_renewals_batch.return_value = None
        resp = client.post("/admin/renewal-threshold-emails")
    assert resp.status_code == 200
    body = resp.json()
    assert body["recipient"] == "broker@test.no"




# ── POST /admin/activity-reminders ───────────────────────────────────────────

    with patch("api.routers.admin_router.create_notification_for_users_safe"):
        resp = client.post("/admin/activity-reminders")
    assert resp.status_code == 200
    body = resp.json()
    assert body["sent"] is True


    resp = client.post("/admin/activity-reminders")
    assert resp.status_code == 200
    assert resp.json()["sent"] is False


# ── POST /admin/trigger-coverage-gap-alerts ──────────────────────────────────

    gaps = [{"orgnr": "123", "navn": "TestCo", "gap_count": 1, "gaps": [{"type": "ansvar"}]}]
    with patch("api.routers.admin_router.get_companies_with_gaps", return_value=gaps), \
         patch("api.routers.admin_router.log_audit"), \
         patch("api.routers.admin_router.create_notification_for_users_safe"):
        resp = client.post("/admin/trigger-coverage-gap-alerts")
    assert resp.status_code == 200
    body = resp.json()
    assert body["companies_with_gaps"] == 1
    assert body["sent"] is True


    with patch("api.routers.admin_router.get_companies_with_gaps", return_value=[]):
        resp = client.post("/admin/trigger-coverage-gap-alerts")
    assert resp.status_code == 200
    assert resp.json()["companies_with_gaps"] == 0


# ── POST /admin/trigger-renewal-digest ───────────────────────────────────────

def test_trigger_renewal_digest_sends(client, mock_db, mock_notification):
    settings = _mock_settings()
    q = mock_db.query.return_value
    q.first.return_value = settings
    q.filter.return_value = q
    q.order_by.return_value = q
    q.all.return_value = [_mock_policy()]
    q.asc.return_value = q

    with patch("api.routers.admin_router.create_notification_for_users_safe"):
        resp = client.post("/admin/trigger-renewal-digest")
    assert resp.status_code == 200
    assert resp.json()["sent"] is True


# ── POST /admin/refresh-portfolio-risk ───────────────────────────────────────


# ── GET /debug/status ────────────────────────────────────────────────────────


# ── GET /dashboard ───────────────────────────────────────────────────────────

def test_dashboard_returns_summary(client, mock_db):
    q = mock_db.query.return_value
    q.filter.return_value = q
    q.all.return_value = []
    q.count.return_value = 0
    q.order_by.return_value = q
    q.desc.return_value = q
    q.limit.return_value = q

    resp = client.get("/dashboard")
    assert resp.status_code == 200
    body = resp.json()
    assert "renewals_30d" in body
    assert "open_claims" in body
    assert "total_premium_book" in body
