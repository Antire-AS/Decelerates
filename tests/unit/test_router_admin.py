"""Unit tests for api/routers/admin_router.py — admin CRUD, dashboard, notifications."""

import sys
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.routers.admin_router import router
from api.routers.admin_seed import _admin_svc
from api.routers.cron import _get_notification
from api.dependencies import get_db
from api.services.admin_service import AdminService

_app = FastAPI()
_app.include_router(router)


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_svc():
    return MagicMock(spec=AdminService)


@pytest.fixture
def mock_notification():
    n = MagicMock()
    n.is_configured.return_value = True
    return n


@pytest.fixture
def client(mock_db, mock_svc, mock_notification):
    _app.dependency_overrides[get_db] = lambda: mock_db
    _app.dependency_overrides[_admin_svc] = lambda: mock_svc
    _app.dependency_overrides[_get_notification] = lambda: mock_notification
    yield TestClient(_app)
    _app.dependency_overrides.clear()


# ── DELETE /admin/reset ───────────────────────────────────────────────────────


def test_admin_reset_returns_200(client, mock_svc):
    mock_svc.reset.return_value = {"deleted_companies": 5}
    resp = client.delete("/admin/reset")
    assert resp.status_code == 200
    mock_svc.reset.assert_called_once()


def test_admin_reset_returns_service_result(client, mock_svc):
    mock_svc.reset.return_value = {"deleted_companies": 10, "deleted_chunks": 200}
    resp = client.delete("/admin/reset")
    assert resp.json()["deleted_companies"] == 10


# ── POST /admin/demo ──────────────────────────────────────────────────────────


def test_admin_demo_returns_200(client, mock_svc):
    mock_svc.seed_demo.return_value = {"seeded": 8}
    resp = client.post("/admin/demo")
    assert resp.status_code == 200
    mock_svc.seed_demo.assert_called_once()


# ── POST /admin/seed-norway-top100 ────────────────────────────────────────────


def test_admin_seed_norway_top100_returns_200(client, mock_svc):
    mock_svc.seed_norway_top100.return_value = {"seeded": 100}
    resp = client.post("/admin/seed-norway-top100")
    assert resp.status_code == 200
    mock_svc.seed_norway_top100.assert_called_once()


# ── POST /admin/seed-crm-demo ─────────────────────────────────────────────────


def test_seed_crm_demo_returns_200(client, mock_svc):
    mock_svc.seed_crm_demo.return_value = {"policies": 10, "claims": 3}
    resp = client.post("/admin/seed-crm-demo")
    assert resp.status_code == 200
    mock_svc.seed_crm_demo.assert_called_once()


# ── GET /dashboard ────────────────────────────────────────────────────────────


def test_get_dashboard_returns_200(client, mock_db):
    # All DB query chains return empty lists / 0
    q = mock_db.query.return_value
    q.filter.return_value = q
    q.all.return_value = []
    q.count.return_value = 0
    q.order_by.return_value.limit.return_value.all.return_value = []
    resp = client.get("/dashboard")
    assert resp.status_code == 200


def test_get_dashboard_returns_expected_keys(client, mock_db):
    q = mock_db.query.return_value
    q.filter.return_value = q
    q.all.return_value = []
    q.count.return_value = 0
    q.order_by.return_value.limit.return_value.all.return_value = []
    resp = client.get("/dashboard")
    body = resp.json()
    assert "renewals_30d" in body
    assert "renewals_90d" in body
    assert "open_claims" in body
    assert "total_premium_book" in body
    assert "recent_activities" in body


def test_get_dashboard_zero_metrics_on_empty_db(client, mock_db):
    q = mock_db.query.return_value
    q.filter.return_value = q
    q.all.return_value = []
    q.count.return_value = 0
    q.order_by.return_value.limit.return_value.all.return_value = []
    resp = client.get("/dashboard")
    body = resp.json()
    assert body["renewals_30d"] == 0
    assert body["open_claims"] == 0
    assert body["total_premium_book"] == 0


# ── POST /admin/portfolio-digest ─────────────────────────────────────────────


def test_portfolio_digest_returns_422_when_no_broker_email(
    client, mock_db, mock_notification
):
    mock_db.query.return_value.first.return_value = None
    resp = client.post("/admin/portfolio-digest")
    assert resp.status_code == 422


def test_portfolio_digest_returns_503_when_notification_unconfigured(
    client, mock_db, mock_notification
):
    settings = MagicMock()
    settings.contact_email = "broker@firm.no"
    mock_db.query.return_value.first.return_value = settings
    mock_notification.is_configured.return_value = False
    resp = client.post("/admin/portfolio-digest")
    assert resp.status_code == 503


def test_portfolio_digest_sends_to_broker_email(client, mock_db, mock_notification):
    settings = MagicMock()
    settings.contact_email = "broker@firm.no"
    firm = MagicMock()
    firm.id = 1

    # Side-effect chain:
    # 1. BrokerSettings.first → settings
    # 2. BrokerFirm count → 1 (single-firm guard)
    # 3. BrokerFirm.order_by.first → firm
    # 4. Portfolio.filter.all → []
    # 5. Policy.filter.order_by.all → []
    call_count = [0]

    def _query_se(model):
        q = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            q.first.return_value = settings
        elif call_count[0] == 2:
            q.count.return_value = 1
        elif call_count[0] == 3:
            q.order_by.return_value.first.return_value = firm
        else:
            q.filter.return_value.all.return_value = []
            q.filter.return_value.order_by.return_value.all.return_value = []
        return q

    mock_db.query.side_effect = _query_se
    mock_notification.send_renewal_digest.return_value = False

    resp = client.post("/admin/portfolio-digest")
    assert resp.status_code == 200
    body = resp.json()
    assert body["recipient"] == "broker@firm.no"


# ── POST /admin/activity-reminders ────────────────────────────────────────────


def test_activity_reminders_returns_422_when_no_broker_email(
    client, mock_db, mock_notification
):
    mock_db.query.return_value.first.return_value = None
    resp = client.post("/admin/activity-reminders")
    assert resp.status_code == 422


def test_activity_reminders_returns_503_when_notification_unconfigured(
    client, mock_db, mock_notification
):
    settings = MagicMock()
    settings.contact_email = "broker@firm.no"
    mock_db.query.return_value.first.return_value = settings
    mock_notification.is_configured.return_value = False
    resp = client.post("/admin/activity-reminders")
    assert resp.status_code == 503


def test_activity_reminders_returns_no_send_when_no_activities(
    client, mock_db, mock_notification
):
    settings = MagicMock()
    settings.contact_email = "broker@firm.no"
    firm = MagicMock()
    firm.id = 1

    call_count = [0]

    def _query_se(model):
        q = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            q.first.return_value = settings
        elif call_count[0] == 2:
            q.count.return_value = 1
        elif call_count[0] == 3:
            q.order_by.return_value.first.return_value = firm
        else:
            q.filter.return_value.order_by.return_value.all.return_value = []
        return q

    mock_db.query.side_effect = _query_se

    resp = client.post("/admin/activity-reminders")
    assert resp.status_code == 200
    assert resp.json()["sent"] is False
