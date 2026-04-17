"""Unit tests for api/services/user_service.py — UserService.

Pure static tests — uses MagicMock DB; no infrastructure required.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from api.db import BrokerFirm, User, UserRole
from api.domain.exceptions import ForbiddenError, NotFoundError
from api.services.user_service import UserService


# ── helpers ───────────────────────────────────────────────────────────────────


def _mock_db():
    return MagicMock()


def _mock_user(**kwargs):
    u = MagicMock(spec=User)
    u.id = kwargs.get("id", 1)
    u.azure_oid = kwargs.get("azure_oid", "oid-abc-123")
    u.email = kwargs.get("email", "broker@firma.no")
    u.name = kwargs.get("name", "Ola Nordmann")
    u.firm_id = kwargs.get("firm_id", 1)
    u.role = kwargs.get("role", UserRole.broker)
    return u


def _mock_firm(**kwargs):
    f = MagicMock(spec=BrokerFirm)
    f.id = kwargs.get("id", 1)
    f.name = kwargs.get("name", "Default Firm")
    return f


def _role_update(role: str):
    return SimpleNamespace(role=role)


# ── get_or_create — existing user ─────────────────────────────────────────────


def test_get_or_create_returns_existing_user():
    user = _mock_user()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = user
    result = UserService(db).get_or_create("oid-abc-123", "broker@firma.no", "Ola")
    assert result is user


def test_get_or_create_does_not_add_when_user_exists():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = _mock_user()
    UserService(db).get_or_create("oid-abc-123", "broker@firma.no", "Ola")
    db.add.assert_not_called()


# ── get_or_create — new user ──────────────────────────────────────────────────


def _db_for_new_user(firm=None):
    """Mock DB that returns None for user lookup, then a firm."""
    db = _mock_db()
    firm = firm or _mock_firm()
    # First call: user lookup → None; second call: firm lookup → firm
    db.query.return_value.filter.return_value.first.side_effect = [None, firm]
    return db


def test_get_or_create_adds_user_when_not_found():
    db = _db_for_new_user()
    UserService(db).get_or_create("new-oid", "new@firma.no", "Ny Bruker")
    db.add.assert_called()


def test_get_or_create_commits_new_user():
    db = _db_for_new_user()
    UserService(db).get_or_create("new-oid", "new@firma.no", "Ny Bruker")
    db.commit.assert_called()


def test_get_or_create_sets_azure_oid():
    db = _db_for_new_user()
    UserService(db).get_or_create("new-oid-xyz", "new@firma.no", "Ny Bruker")
    added = db.add.call_args_list[0][0][0]
    assert added.azure_oid == "new-oid-xyz"


def test_get_or_create_sets_email():
    db = _db_for_new_user()
    UserService(db).get_or_create("new-oid", "me@firma.no", "Ny Bruker")
    added = db.add.call_args_list[0][0][0]
    assert added.email == "me@firma.no"


def test_get_or_create_sets_name():
    db = _db_for_new_user()
    UserService(db).get_or_create("new-oid", "new@firma.no", "Kari Nordmann")
    added = db.add.call_args_list[0][0][0]
    assert added.name == "Kari Nordmann"


def test_get_or_create_assigns_broker_role():
    db = _db_for_new_user()
    UserService(db).get_or_create("new-oid", "new@firma.no", "Ny Bruker")
    added = db.add.call_args_list[0][0][0]
    assert added.role == UserRole.broker


def test_get_or_create_sets_utc_timestamp():
    db = _db_for_new_user()
    before = datetime.now(timezone.utc)
    UserService(db).get_or_create("new-oid", "new@firma.no", "Ny Bruker")
    added = db.add.call_args_list[0][0][0]
    assert added.created_at >= before


def test_get_or_create_assigns_firm_id():
    firm = _mock_firm(id=7)
    db = _db_for_new_user(firm=firm)
    UserService(db).get_or_create("new-oid", "new@firma.no", "Ny Bruker")
    added = db.add.call_args_list[0][0][0]
    assert added.firm_id == 7


# ── get_by_oid ────────────────────────────────────────────────────────────────


def test_get_by_oid_returns_user_when_found():
    user = _mock_user()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = user
    result = UserService(db).get_by_oid("oid-abc-123")
    assert result is user


def test_get_by_oid_returns_none_when_not_found():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    result = UserService(db).get_by_oid("unknown-oid")
    assert result is None


# ── list_users ────────────────────────────────────────────────────────────────


def test_list_users_returns_users_for_firm():
    users = [_mock_user(), _mock_user(id=2)]
    db = _mock_db()
    db.query.return_value.filter.return_value.all.return_value = users
    result = UserService(db).list_users(1)
    assert result == users


def test_list_users_returns_empty_list_when_none():
    db = _mock_db()
    db.query.return_value.filter.return_value.all.return_value = []
    result = UserService(db).list_users(99)
    assert result == []


# ── update_role ───────────────────────────────────────────────────────────────


def test_update_role_raises_forbidden_when_not_admin():
    db = _mock_db()
    with pytest.raises(ForbiddenError, match="Only admins"):
        UserService(db).update_role(1, _role_update("broker"), requester_role="broker")


def test_update_role_raises_not_found_for_unknown_role():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = _mock_user()
    with pytest.raises(NotFoundError, match="Unknown role"):
        UserService(db).update_role(
            1, _role_update("superuser"), requester_role="admin"
        )


def test_update_role_raises_not_found_for_missing_user():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(NotFoundError, match="User 999 not found"):
        UserService(db).update_role(999, _role_update("admin"), requester_role="admin")


def test_update_role_sets_new_role():
    user = _mock_user(role=UserRole.broker)
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = user
    UserService(db).update_role(1, _role_update("admin"), requester_role="admin")
    assert user.role == UserRole.admin


def test_update_role_commits():
    user = _mock_user()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = user
    UserService(db).update_role(1, _role_update("viewer"), requester_role="admin")
    db.commit.assert_called_once()


def test_update_role_returns_updated_user():
    user = _mock_user()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = user
    result = UserService(db).update_role(
        1, _role_update("admin"), requester_role="admin"
    )
    assert result is user


@pytest.mark.parametrize("role", ["admin", "broker", "viewer"])
def test_update_role_accepts_all_valid_roles(role):
    user = _mock_user()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = user
    UserService(db).update_role(1, _role_update(role), requester_role="admin")
    assert user.role == UserRole[role]


# ── _ensure_default_firm ──────────────────────────────────────────────────────


def test_ensure_default_firm_returns_existing_firm():
    firm = _mock_firm()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = firm
    result = UserService(db)._ensure_default_firm()
    assert result is firm


def test_ensure_default_firm_creates_when_missing():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    UserService(db)._ensure_default_firm()
    db.add.assert_called_once()
    db.flush.assert_called_once()


def test_ensure_default_firm_new_firm_has_id_1():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    UserService(db)._ensure_default_firm()
    added = db.add.call_args[0][0]
    assert added.id == 1


def test_ensure_default_firm_new_firm_has_default_name():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    UserService(db)._ensure_default_firm()
    added = db.add.call_args[0][0]
    assert added.name == "Default Firm"
