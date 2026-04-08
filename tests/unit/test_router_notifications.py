"""Unit tests for api/routers/notifications.py — bell-icon HTTP layer."""
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Stub heavy transitive deps before any api.* import.
sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.auth import CurrentUser, get_current_user
from api.db import NotificationKind
from api.dependencies import get_db
from api.domain.exceptions import NotFoundError
from api.routers.notifications import router


_app = FastAPI()
_app.include_router(router)


def _mock_user():
    return CurrentUser(email="b@x.no", name="B", oid="oid-42", firm_id=10)


def _mock_user_row(user_id=42):
    u = MagicMock()
    u.id = user_id
    u.azure_oid = "oid-42"
    return u


def _mock_notification(notif_id=1, read=False):
    n = MagicMock()
    n.id = notif_id
    n.user_id = 42
    n.firm_id = 10
    n.orgnr = "123456789"
    n.kind = NotificationKind.renewal
    n.title = "Renewal due"
    n.message = "30 days"
    n.link = "/search/123456789"
    n.read = read
    n.created_at = datetime.now(timezone.utc)
    return n


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def client(mock_db):
    _app.dependency_overrides[get_db] = lambda: mock_db
    _app.dependency_overrides[get_current_user] = _mock_user
    yield TestClient(_app)
    _app.dependency_overrides.clear()


# ── GET /notifications ───────────────────────────────────────────────────────


def test_list_notifications_200(client, mock_db):
    user_row = _mock_user_row(user_id=42)
    mock_db.query.return_value.filter.return_value.first.return_value = user_row
    notifs = [_mock_notification(1), _mock_notification(2)]
    with patch(
        "api.routers.notifications.NotificationInboxService"
    ) as MockSvc:
        instance = MockSvc.return_value
        instance.list_for_user.return_value = notifs
        instance.unread_count.return_value = 5
        resp = client.get("/notifications")
    assert resp.status_code == 200
    body = resp.json()
    assert body["unread_count"] == 5
    assert len(body["items"]) == 2


def test_list_notifications_passes_unread_only_query(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = _mock_user_row()
    with patch("api.routers.notifications.NotificationInboxService") as MockSvc:
        instance = MockSvc.return_value
        instance.list_for_user.return_value = []
        instance.unread_count.return_value = 0
        client.get("/notifications?unread_only=true&limit=20")
    instance.list_for_user.assert_called_once_with(42, unread_only=True, limit=20)


def test_list_notifications_404_when_user_record_missing(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None
    resp = client.get("/notifications")
    assert resp.status_code == 404


# ── PATCH /notifications/{id}/read ───────────────────────────────────────────


def test_mark_read_200(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = _mock_user_row()
    notif = _mock_notification(notif_id=7, read=True)
    with patch("api.routers.notifications.NotificationInboxService") as MockSvc:
        MockSvc.return_value.mark_read.return_value = notif
        resp = client.patch("/notifications/7/read")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == 7
    assert body["read"] is True


def test_mark_read_404_when_other_user(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = _mock_user_row()
    with patch("api.routers.notifications.NotificationInboxService") as MockSvc:
        MockSvc.return_value.mark_read.side_effect = NotFoundError("not found")
        resp = client.patch("/notifications/999/read")
    assert resp.status_code == 404


# ── POST /notifications/read-all ─────────────────────────────────────────────


def test_mark_all_read_200(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = _mock_user_row()
    with patch("api.routers.notifications.NotificationInboxService") as MockSvc:
        MockSvc.return_value.mark_all_read.return_value = 12
        resp = client.post("/notifications/read-all")
    assert resp.status_code == 200
    assert resp.json() == {"updated": 12}
