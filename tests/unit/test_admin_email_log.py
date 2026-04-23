"""Unit tests for GET /admin/email-log.

Only the pure transformation path is tested here — auth + SQL are covered
in integration tests. We mock the DB query and verify paging + filters
translate correctly into the response shape.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies import get_db
from api.routers import admin_email_log as mod


def _fake_row(i: int, status: str = "matched") -> SimpleNamespace:
    return SimpleNamespace(
        id=i,
        received_at=datetime(2026, 4, 23, 12, 0, 0, tzinfo=timezone.utc),
        sender=f"a{i}@b.no",
        recipient="anbud@meglerai.no",
        subject=f"subj-{i}",
        tender_ref=f"[ref: TENDER-{i}-{i}]",
        tender_id=i,
        recipient_id=i,
        status=status,
        error_message=None,
        attachment_count=1,
        offer_id=i if status == "matched" else None,
        message_id=f"<m{i}@x>",
    )


def _build_client(db: MagicMock, monkeypatch):
    # Bypass require_role("admin") by dependency-overriding the inner dep.
    from api.auth import get_current_user

    app = FastAPI()
    app.include_router(mod.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1, email="admin@x", role="admin", firm_id=1
    )
    return TestClient(app)


def test_list_returns_items_and_pagination_meta(monkeypatch):
    rows = [_fake_row(i) for i in range(5)]
    db = MagicMock()
    query = db.query.return_value
    query.order_by.return_value = query
    query.count.return_value = 5
    query.offset.return_value = query
    query.limit.return_value.all.return_value = rows

    client = _build_client(db, monkeypatch)
    r = client.get("/admin/email-log?limit=5&offset=0")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 5
    assert body["offset"] == 0
    assert body["limit"] == 5
    assert body["has_more"] is False
    assert len(body["items"]) == 5
    assert body["items"][0]["sender"] == "a0@b.no"
    assert body["items"][0]["status"] == "matched"


def test_has_more_when_total_exceeds_page(monkeypatch):
    rows = [_fake_row(i) for i in range(10)]
    db = MagicMock()
    query = db.query.return_value
    query.order_by.return_value = query
    query.count.return_value = 50
    query.offset.return_value = query
    query.limit.return_value.all.return_value = rows

    client = _build_client(db, monkeypatch)
    r = client.get("/admin/email-log?limit=10&offset=0")
    assert r.status_code == 200
    assert r.json()["has_more"] is True


def test_status_filter_applied(monkeypatch):
    db = MagicMock()
    query = db.query.return_value
    query.order_by.return_value = query
    query.filter.return_value = query
    query.count.return_value = 1
    query.offset.return_value = query
    query.limit.return_value.all.return_value = [_fake_row(1, status="error")]

    client = _build_client(db, monkeypatch)
    r = client.get("/admin/email-log?status=error&limit=10")
    assert r.status_code == 200
    # filter() was called once — the status filter is applied
    assert query.filter.called


def test_unknown_status_ignored(monkeypatch):
    """Invalid status values shouldn't 500 — just return everything."""
    db = MagicMock()
    query = db.query.return_value
    query.order_by.return_value = query
    query.count.return_value = 0
    query.offset.return_value = query
    query.limit.return_value.all.return_value = []

    client = _build_client(db, monkeypatch)
    r = client.get("/admin/email-log?status=bogus")
    assert r.status_code == 200
    # filter() NOT called for unknown status
    assert not query.filter.called
