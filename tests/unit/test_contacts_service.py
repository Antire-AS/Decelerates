"""Unit tests for api/services/contacts_service.py — ContactsService.

Pure static tests — uses MagicMock DB; no infrastructure required.
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from api.db import ContactPerson
from api.domain.exceptions import NotFoundError
from api.services.contacts_service import ContactsService


# ── helpers ───────────────────────────────────────────────────────────────────

def _mock_db():
    return MagicMock()


def _mock_contact(**kwargs):
    c = MagicMock(spec=ContactPerson)
    c.id         = kwargs.get("id", 1)
    c.orgnr      = kwargs.get("orgnr", "123456789")
    c.name       = kwargs.get("name", "Ola Nordmann")
    c.email      = kwargs.get("email", "ola@firma.no")
    c.is_primary = kwargs.get("is_primary", False)
    return c


def _contact_in(**kwargs):
    return SimpleNamespace(
        name       = kwargs.get("name", "Ola Nordmann"),
        title      = kwargs.get("title", "CEO"),
        email      = kwargs.get("email", "ola@firma.no"),
        phone      = kwargs.get("phone", None),
        is_primary = kwargs.get("is_primary", False),
        notes      = kwargs.get("notes", None),
    )


def _contact_update(**kwargs):
    data = dict(kwargs)
    return SimpleNamespace(**data, model_dump=lambda exclude_none: data)


# ── list_contacts ─────────────────────────────────────────────────────────────

def test_list_contacts_returns_results():
    db = _mock_db()
    contacts = [_mock_contact(), _mock_contact(id=2)]
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = contacts
    result = ContactsService(db).list_contacts("123456789")
    assert result == contacts


def test_list_contacts_queries_by_orgnr():
    db = _mock_db()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    ContactsService(db).list_contacts("123456789")
    db.query.assert_called_once_with(ContactPerson)


def test_list_contacts_empty_when_none():
    db = _mock_db()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    result = ContactsService(db).list_contacts("000000000")
    assert result == []


# ── create_contact ────────────────────────────────────────────────────────────

def test_create_contact_adds_to_db_and_commits():
    db = _mock_db()
    ContactsService(db).create_contact("123456789", _contact_in())
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_create_contact_sets_orgnr():
    db = _mock_db()
    ContactsService(db).create_contact("123456789", _contact_in())
    added = db.add.call_args[0][0]
    assert added.orgnr == "123456789"


def test_create_contact_sets_name():
    db = _mock_db()
    ContactsService(db).create_contact("123456789", _contact_in(name="Kari Nordmann"))
    added = db.add.call_args[0][0]
    assert added.name == "Kari Nordmann"


def test_create_contact_sets_email():
    db = _mock_db()
    ContactsService(db).create_contact("123456789", _contact_in(email="kari@firma.no"))
    added = db.add.call_args[0][0]
    assert added.email == "kari@firma.no"


def test_create_contact_sets_is_primary_false_by_default():
    db = _mock_db()
    ContactsService(db).create_contact("123456789", _contact_in(is_primary=False))
    added = db.add.call_args[0][0]
    assert added.is_primary is False


def test_create_contact_sets_utc_timestamp():
    db = _mock_db()
    before = datetime.now(timezone.utc)
    ContactsService(db).create_contact("123456789", _contact_in())
    added = db.add.call_args[0][0]
    assert added.created_at >= before


def test_create_primary_contact_clears_existing_primaries():
    db = _mock_db()
    ContactsService(db).create_contact("123456789", _contact_in(is_primary=True))
    # _clear_primary must have called db.query(...).filter(...).update(...)
    db.query.return_value.filter.return_value.update.assert_called_once_with({"is_primary": False})


def test_create_non_primary_contact_does_not_clear_primaries():
    db = _mock_db()
    ContactsService(db).create_contact("123456789", _contact_in(is_primary=False))
    db.query.return_value.filter.return_value.update.assert_not_called()


# ── update_contact ────────────────────────────────────────────────────────────

def test_update_contact_sets_fields():
    contact = _mock_contact()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = contact
    body = _contact_update(name="New Name", is_primary=False)
    ContactsService(db).update_contact(1, "123456789", body)
    assert contact.name == "New Name"


def test_update_contact_commits():
    contact = _mock_contact()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = contact
    body = _contact_update(notes="Updated note", is_primary=False)
    ContactsService(db).update_contact(1, "123456789", body)
    db.commit.assert_called_once()


def test_update_contact_raises_not_found_when_missing():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    body = _contact_update(is_primary=False)
    with pytest.raises(NotFoundError):
        ContactsService(db).update_contact(999, "123456789", body)


def test_update_primary_contact_clears_existing_primaries():
    contact = _mock_contact()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = contact
    body = _contact_update(is_primary=True)
    ContactsService(db).update_contact(1, "123456789", body)
    db.query.return_value.filter.return_value.update.assert_called_once_with({"is_primary": False})


def test_update_non_primary_does_not_clear_primaries():
    contact = _mock_contact()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = contact
    body = _contact_update(is_primary=False)
    ContactsService(db).update_contact(1, "123456789", body)
    db.query.return_value.filter.return_value.update.assert_not_called()


def test_update_contact_returns_contact():
    contact = _mock_contact()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = contact
    body = _contact_update(is_primary=False)
    result = ContactsService(db).update_contact(1, "123456789", body)
    assert result is contact


# ── delete_contact ────────────────────────────────────────────────────────────

def test_delete_contact_calls_db_delete():
    contact = _mock_contact()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = contact
    ContactsService(db).delete_contact(1, "123456789")
    db.delete.assert_called_once_with(contact)


def test_delete_contact_commits():
    contact = _mock_contact()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = contact
    ContactsService(db).delete_contact(1, "123456789")
    db.commit.assert_called_once()


def test_delete_contact_raises_not_found_when_missing():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(NotFoundError):
        ContactsService(db).delete_contact(999, "123456789")


# ── _clear_primary ────────────────────────────────────────────────────────────

def test_clear_primary_updates_is_primary_to_false():
    db = _mock_db()
    ContactsService(db)._clear_primary("123456789")
    db.query.return_value.filter.return_value.update.assert_called_once_with({"is_primary": False})
