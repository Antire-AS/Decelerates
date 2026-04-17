"""Unit tests for api/services/activity_service.py — ActivityService.

Pure static tests — uses MagicMock DB; no infrastructure required.
"""

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from api.db import Activity, ActivityType
from api.domain.exceptions import NotFoundError
from api.services.activity_service import ActivityService


# ── helpers ───────────────────────────────────────────────────────────────────


def _mock_db():
    return MagicMock()


def _mock_activity(**kwargs):
    a = MagicMock(spec=Activity)
    a.id = kwargs.get("id", 1)
    a.orgnr = kwargs.get("orgnr", "123456789")
    a.firm_id = kwargs.get("firm_id", 10)
    a.activity_type = kwargs.get("activity_type", ActivityType.note)
    a.subject = kwargs.get("subject", "Follow-up call")
    a.completed = kwargs.get("completed", False)
    return a


def _activity_in(**kwargs):
    return SimpleNamespace(
        activity_type=kwargs.get("activity_type", "note"),
        subject=kwargs.get("subject", "Follow-up call"),
        body=kwargs.get("body", None),
        due_date=kwargs.get("due_date", None),
        completed=kwargs.get("completed", False),
        policy_id=kwargs.get("policy_id", None),
        claim_id=kwargs.get("claim_id", None),
        assigned_to_user_id=kwargs.get("assigned_to_user_id", None),
    )


# ── list_by_orgnr ─────────────────────────────────────────────────────────────


def test_list_by_orgnr_returns_results():
    db = _mock_db()
    activities = [_mock_activity(), _mock_activity(id=2)]
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = activities
    result = ActivityService(db).list_by_orgnr("123456789", 10)
    assert result == activities


def test_list_by_orgnr_applies_limit():
    db = _mock_db()
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    ActivityService(db).list_by_orgnr("123456789", 10, limit=25)
    chain = db.query.return_value.filter.return_value.order_by.return_value
    chain.limit.assert_called_once_with(25)


def test_list_by_orgnr_default_limit_is_50():
    db = _mock_db()
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    ActivityService(db).list_by_orgnr("123456789", 10)
    chain = db.query.return_value.filter.return_value.order_by.return_value
    chain.limit.assert_called_once_with(50)


# ── create ────────────────────────────────────────────────────────────────────


def test_create_adds_to_db_and_commits():
    db = _mock_db()
    ActivityService(db).create("123456789", 10, "broker@firma.no", _activity_in())
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_create_sets_orgnr():
    db = _mock_db()
    ActivityService(db).create("987654321", 10, "broker@firma.no", _activity_in())
    added = db.add.call_args[0][0]
    assert added.orgnr == "987654321"


def test_create_sets_firm_id():
    db = _mock_db()
    ActivityService(db).create("123456789", 42, "broker@firma.no", _activity_in())
    added = db.add.call_args[0][0]
    assert added.firm_id == 42


def test_create_sets_created_by_email():
    db = _mock_db()
    ActivityService(db).create("123456789", 10, "meg@firma.no", _activity_in())
    added = db.add.call_args[0][0]
    assert added.created_by_email == "meg@firma.no"


def test_create_parses_activity_type_enum():
    db = _mock_db()
    ActivityService(db).create(
        "123456789", 10, "broker@firma.no", _activity_in(activity_type="call")
    )
    added = db.add.call_args[0][0]
    assert added.activity_type == ActivityType.call


def test_create_sets_subject():
    db = _mock_db()
    ActivityService(db).create(
        "123456789", 10, "broker@firma.no", _activity_in(subject="Renewal meeting")
    )
    added = db.add.call_args[0][0]
    assert added.subject == "Renewal meeting"


def test_create_sets_utc_timestamp():
    db = _mock_db()
    before = datetime.now(timezone.utc)
    ActivityService(db).create("123456789", 10, "broker@firma.no", _activity_in())
    added = db.add.call_args[0][0]
    assert added.created_at >= before


def test_create_sets_due_date():
    db = _mock_db()
    due = date(2027, 3, 1)
    ActivityService(db).create(
        "123456789", 10, "broker@firma.no", _activity_in(due_date=due)
    )
    added = db.add.call_args[0][0]
    assert added.due_date == due


def test_create_sets_completed_false_by_default():
    db = _mock_db()
    ActivityService(db).create("123456789", 10, "broker@firma.no", _activity_in())
    added = db.add.call_args[0][0]
    assert added.completed is False


def test_create_sets_completed_true_when_specified():
    db = _mock_db()
    ActivityService(db).create(
        "123456789", 10, "broker@firma.no", _activity_in(completed=True)
    )
    added = db.add.call_args[0][0]
    assert added.completed is True


def test_create_invalid_activity_type_raises_not_found():
    db = _mock_db()
    with pytest.raises(NotFoundError, match="Unknown activity type"):
        ActivityService(db).create(
            "123456789", 10, "broker@firma.no", _activity_in(activity_type="invalid")
        )


def test_create_links_policy_id():
    db = _mock_db()
    ActivityService(db).create(
        "123456789", 10, "broker@firma.no", _activity_in(policy_id=7)
    )
    added = db.add.call_args[0][0]
    assert added.policy_id == 7


def test_create_links_claim_id():
    db = _mock_db()
    ActivityService(db).create(
        "123456789", 10, "broker@firma.no", _activity_in(claim_id=3)
    )
    added = db.add.call_args[0][0]
    assert added.claim_id == 3


# ── all activity types parse correctly ────────────────────────────────────────


@pytest.mark.parametrize("atype", ["call", "email", "meeting", "note", "task"])
def test_create_all_valid_activity_types(atype):
    db = _mock_db()
    ActivityService(db).create(
        "123456789", 10, "broker@firma.no", _activity_in(activity_type=atype)
    )
    added = db.add.call_args[0][0]
    assert added.activity_type == ActivityType[atype]


# ── update ────────────────────────────────────────────────────────────────────


def test_update_sets_fields():
    activity = _mock_activity()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = activity
    body = SimpleNamespace(
        model_dump=lambda exclude_none: {
            "subject": "Updated subject",
            "completed": True,
        }
    )
    ActivityService(db).update(1, 10, body)
    assert activity.subject == "Updated subject"
    assert activity.completed is True


def test_update_commits():
    activity = _mock_activity()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = activity
    body = SimpleNamespace(model_dump=lambda exclude_none: {"completed": True})
    ActivityService(db).update(1, 10, body)
    db.commit.assert_called_once()


def test_update_raises_not_found_when_missing():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    body = SimpleNamespace(model_dump=lambda exclude_none: {})
    with pytest.raises(NotFoundError):
        ActivityService(db).update(999, 10, body)


def test_update_returns_activity():
    activity = _mock_activity()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = activity
    body = SimpleNamespace(model_dump=lambda exclude_none: {})
    result = ActivityService(db).update(1, 10, body)
    assert result is activity


# ── delete ────────────────────────────────────────────────────────────────────


def test_delete_calls_db_delete():
    activity = _mock_activity()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = activity
    ActivityService(db).delete(1, 10)
    db.delete.assert_called_once_with(activity)


def test_delete_commits():
    activity = _mock_activity()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = activity
    ActivityService(db).delete(1, 10)
    db.commit.assert_called_once()


def test_delete_raises_not_found_when_missing():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(NotFoundError):
        ActivityService(db).delete(999, 10)
