"""Unit tests for api/services/idd.py — IddService.

Pure static tests — uses MagicMock DB; no infrastructure required.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from api.db import IddBehovsanalyse
from api.domain.exceptions import NotFoundError
from api.services.idd import IddService


# ── helpers ───────────────────────────────────────────────────────────────────


def _mock_db():
    return MagicMock()


def _mock_row(**kwargs):
    row = MagicMock(spec=IddBehovsanalyse)
    row.id = kwargs.get("id", 1)
    row.orgnr = kwargs.get("orgnr", "123456789")
    row.firm_id = kwargs.get("firm_id", 10)
    row.created_by_email = kwargs.get("created_by_email", "broker@firma.no")
    row.client_name = kwargs.get("client_name", "Test AS")
    row.risk_appetite = kwargs.get("risk_appetite", "medium")
    return row


def _idd_data(**kwargs):
    return {
        "client_name": kwargs.get("client_name", "Test AS"),
        "client_contact_name": kwargs.get("client_contact_name", "Ola"),
        "client_contact_email": kwargs.get("client_contact_email", "ola@test.no"),
        "risk_appetite": kwargs.get("risk_appetite", "medium"),
        "property_owned": kwargs.get("property_owned", True),
        "has_employees": kwargs.get("has_employees", True),
        "has_vehicles": kwargs.get("has_vehicles", False),
        "has_professional_liability": kwargs.get("has_professional_liability", False),
        "has_cyber_risk": kwargs.get("has_cyber_risk", False),
        "existing_insurance": kwargs.get("existing_insurance", []),
        "recommended_products": kwargs.get("recommended_products", []),
    }


# ── create ────────────────────────────────────────────────────────────────────


def test_create_adds_to_db_and_commits():
    db = _mock_db()
    IddService(db).create("123456789", 10, "broker@firma.no", _idd_data())
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_create_refreshes_row():
    db = _mock_db()
    IddService(db).create("123456789", 10, "broker@firma.no", _idd_data())
    db.refresh.assert_called_once()


def test_create_sets_orgnr():
    db = _mock_db()
    IddService(db).create("987654321", 10, "broker@firma.no", _idd_data())
    added = db.add.call_args[0][0]
    assert added.orgnr == "987654321"


def test_create_sets_firm_id():
    db = _mock_db()
    IddService(db).create("123456789", 42, "broker@firma.no", _idd_data())
    added = db.add.call_args[0][0]
    assert added.firm_id == 42


def test_create_sets_created_by_email():
    db = _mock_db()
    IddService(db).create("123456789", 10, "meg@firma.no", _idd_data())
    added = db.add.call_args[0][0]
    assert added.created_by_email == "meg@firma.no"


def test_create_sets_utc_timestamp():
    db = _mock_db()
    before = datetime.now(timezone.utc)
    IddService(db).create("123456789", 10, "broker@firma.no", _idd_data())
    added = db.add.call_args[0][0]
    assert added.created_at >= before


def test_create_spreads_data_dict():
    db = _mock_db()
    IddService(db).create(
        "123456789", 10, "broker@firma.no", _idd_data(client_name="Acme AS")
    )
    added = db.add.call_args[0][0]
    assert added.client_name == "Acme AS"


def test_create_returns_refreshed_row():
    db = _mock_db()
    db.refresh = MagicMock()
    result = IddService(db).create("123456789", 10, "broker@firma.no", _idd_data())
    # After refresh, the row returned by add is the same object passed to refresh
    assert result is db.add.call_args[0][0]


# ── get ───────────────────────────────────────────────────────────────────────


def test_get_returns_row_when_found():
    row = _mock_row()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = row
    result = IddService(db).get("123456789", 10, 1)
    assert result is row


def test_get_raises_not_found_when_missing():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(NotFoundError, match="Behovsanalyse 99 not found"):
        IddService(db).get("123456789", 10, 99)


def test_get_queries_idd_behovsanalyse():
    row = _mock_row()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = row
    IddService(db).get("123456789", 10, 1)
    db.query.assert_called_once_with(IddBehovsanalyse)


# ── delete ────────────────────────────────────────────────────────────────────


def test_delete_calls_db_delete():
    row = _mock_row()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = row
    IddService(db).delete("123456789", 10, 1)
    db.delete.assert_called_once_with(row)


def test_delete_commits():
    row = _mock_row()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = row
    IddService(db).delete("123456789", 10, 1)
    db.commit.assert_called_once()


def test_delete_raises_not_found_when_missing():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(NotFoundError):
        IddService(db).delete("123456789", 10, 999)


def test_delete_does_not_commit_when_not_found():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(NotFoundError):
        IddService(db).delete("123456789", 10, 999)
    db.commit.assert_not_called()


# ── firm/orgnr scoping ────────────────────────────────────────────────────────


def test_get_returns_none_for_wrong_firm():
    """Row for a different firm_id should not be returned."""
    db = _mock_db()
    # Simulate: filter returns nothing for this firm_id combo
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(NotFoundError):
        IddService(db).get("123456789", 99, 1)


def test_delete_raises_for_wrong_orgnr():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(NotFoundError):
        IddService(db).delete("000000000", 10, 1)
