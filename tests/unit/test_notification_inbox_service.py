"""Unit tests for api/services/notification_inbox_service.py.

Mocked DB; covers fan-out, mark-read ownership scoping, mark-all-read,
and the best-effort cron wrapper that must never raise.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from api.db import Notification, NotificationKind
from api.domain.exceptions import NotFoundError
from api.services.notification_inbox_service import (
    NotificationInboxService,
    create_notification_for_users_safe,
)


def _mock_db():
    return MagicMock()


def _mock_notification(notif_id=1, user_id=42, read=False):
    n = MagicMock(spec=Notification)
    n.id = notif_id
    n.user_id = user_id
    n.firm_id = 10
    n.orgnr = "123456789"
    n.kind = NotificationKind.renewal
    n.title = "Renewal due in 30 days"
    n.message = "Policy 12345 renewal date approaching"
    n.link = "/search/123456789?tab=crm"
    n.read = read
    n.created_at = datetime.now(timezone.utc)
    return n


# ── list_for_user ─────────────────────────────────────────────────────────────


def test_list_for_user_returns_recent():
    db = _mock_db()
    notifs = [_mock_notification(1), _mock_notification(2)]
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = notifs
    result = NotificationInboxService(db).list_for_user(user_id=42)
    assert result == notifs


def test_list_for_user_unread_only_chains_filter():
    db = _mock_db()
    chain = db.query.return_value.filter.return_value
    chain.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    NotificationInboxService(db).list_for_user(user_id=42, unread_only=True)
    chain.filter.assert_called()  # the second .filter() is the unread predicate


def test_unread_count_returns_int():
    db = _mock_db()
    db.query.return_value.filter.return_value.count.return_value = 7
    assert NotificationInboxService(db).unread_count(user_id=42) == 7


# ── create_for_users (fan-out) ────────────────────────────────────────────────


def test_create_for_users_fans_out_to_all_firm_users():
    db = _mock_db()
    # User.id query returns 3 rows: (1,), (2,), (3,)
    db.query.return_value.filter.return_value.all.return_value = [(1,), (2,), (3,)]
    count = NotificationInboxService(db).create_for_users(
        firm_id=10,
        kind=NotificationKind.renewal,
        title="Test",
        message="msg",
        link="/x",
    )
    assert count == 3
    # add_all called once with 3 rows
    db.add_all.assert_called_once()
    rows = db.add_all.call_args.args[0]
    assert len(rows) == 3
    assert all(r.firm_id == 10 for r in rows)
    assert all(r.kind == NotificationKind.renewal for r in rows)
    db.commit.assert_called_once()


def test_create_for_users_with_explicit_user_ids_skips_lookup():
    db = _mock_db()
    count = NotificationInboxService(db).create_for_users(
        firm_id=10,
        kind=NotificationKind.mention,
        title="@you",
        user_ids=[7, 8],
    )
    assert count == 2
    db.query.assert_not_called()  # no User lookup needed
    rows = db.add_all.call_args.args[0]
    assert {r.user_id for r in rows} == {7, 8}


def test_create_for_users_returns_zero_when_firm_has_no_users():
    db = _mock_db()
    db.query.return_value.filter.return_value.all.return_value = []
    count = NotificationInboxService(db).create_for_users(
        firm_id=10,
        kind=NotificationKind.digest,
        title="Empty firm",
    )
    assert count == 0
    db.add_all.assert_not_called()
    db.commit.assert_not_called()


# ── mark_read ────────────────────────────────────────────────────────────────


def test_mark_read_flips_read_flag():
    db = _mock_db()
    notif = _mock_notification(notif_id=1, user_id=42, read=False)
    db.query.return_value.filter.return_value.first.return_value = notif
    result = NotificationInboxService(db).mark_read(1, 42)
    assert result.read is True
    db.commit.assert_called_once()


def test_mark_read_idempotent_when_already_read():
    db = _mock_db()
    notif = _mock_notification(notif_id=1, user_id=42, read=True)
    db.query.return_value.filter.return_value.first.return_value = notif
    result = NotificationInboxService(db).mark_read(1, 42)
    assert result.read is True
    db.commit.assert_not_called()  # nothing to commit


def test_mark_read_404_when_other_user():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(NotFoundError):
        NotificationInboxService(db).mark_read(1, 42)


# ── mark_all_read ─────────────────────────────────────────────────────────────


def test_mark_all_read_returns_update_count():
    db = _mock_db()
    db.query.return_value.filter.return_value.update.return_value = 5
    result = NotificationInboxService(db).mark_all_read(user_id=42)
    assert result == 5
    db.commit.assert_called_once()


# ── create_notification_for_users_safe (cron wrapper) ─────────────────────────


def test_safe_wrapper_returns_count_on_success():
    db = _mock_db()
    db.query.return_value.filter.return_value.all.return_value = [(1,), (2,)]
    count = create_notification_for_users_safe(
        db,
        firm_id=10,
        kind=NotificationKind.renewal,
        title="Test",
    )
    assert count == 2


def test_safe_wrapper_swallows_exceptions():
    """Cron callers must NEVER fail because notification fan-out broke.
    The wrapper must return 0 instead of propagating."""
    db = _mock_db()
    db.query.side_effect = RuntimeError("DB exploded")
    count = create_notification_for_users_safe(
        db,
        firm_id=10,
        kind=NotificationKind.renewal,
        title="Test",
    )
    assert count == 0
