"""Unit tests for api/services/sla_service.py — SlaService.

Pure static tests — uses MagicMock DB; no infrastructure required.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock


from api.db import SlaAgreement
from api.services.sla_service import SlaService


def _mock_db():
    return MagicMock()


def _mock_sla(**kwargs):
    sla = MagicMock(spec=SlaAgreement)
    sla.id = kwargs.get("id", 1)
    sla.client_orgnr = kwargs.get("client_orgnr", "123456789")
    sla.client_navn = kwargs.get("client_navn", "Test AS")
    sla.status = kwargs.get("status", "draft")
    sla.signed_at = kwargs.get("signed_at", None)
    sla.signed_by = kwargs.get("signed_by", None)
    return sla


# ── mark_signed ───────────────────────────────────────────────────────────────

def test_mark_signed_returns_none_when_not_found():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    svc = SlaService(db)
    result = svc.mark_signed(999)
    assert result is None
    db.commit.assert_not_called()


def test_mark_signed_sets_timestamp():
    sla = _mock_sla()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = sla
    before = datetime.now(timezone.utc)
    svc = SlaService(db)
    svc.mark_signed(1)
    assert sla.signed_at is not None
    assert sla.signed_at >= before


def test_mark_signed_stores_signer_name():
    sla = _mock_sla()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = sla
    SlaService(db).mark_signed(1, signed_by="Ola Nordmann")
    assert sla.signed_by == "Ola Nordmann"


def test_mark_signed_accepts_none_signer():
    sla = _mock_sla()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = sla
    SlaService(db).mark_signed(1, signed_by=None)
    assert sla.signed_by is None


def test_mark_signed_sets_status_active():
    sla = _mock_sla(status="draft")
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = sla
    SlaService(db).mark_signed(1)
    assert sla.status == "active"


def test_mark_signed_commits():
    sla = _mock_sla()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = sla
    SlaService(db).mark_signed(1)
    db.commit.assert_called_once()


def test_mark_signed_returns_updated_sla():
    sla = _mock_sla()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = sla
    result = SlaService(db).mark_signed(1)
    assert result is sla


# ── create_agreement ──────────────────────────────────────────────────────────

def _sla_in(overrides=None):
    """Build a minimal SlaIn-like mock."""
    from types import SimpleNamespace
    fd = {
        "client_orgnr": "123456789",
        "client_navn": "Test AS",
        "client_adresse": "Testveien 1, 0001 Oslo",
        "client_kontakt": "Ola Nordmann",
        "start_date": "2026-01-01",
        "account_manager": "Broker Name",
        "insurance_lines": ["Ting", "Ansvar"],
        "fee_structure": {"lines": []},
    }
    if overrides:
        fd.update(overrides)
    body = SimpleNamespace(form_data=fd)
    return body


def test_create_agreement_adds_to_db():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    SlaService(db).create_agreement(_sla_in())
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_create_agreement_sets_client_orgnr():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    db.refresh = MagicMock()
    svc = SlaService(db)
    svc.create_agreement(_sla_in())
    # The db.add call should have received an SlaAgreement with the right orgnr
    added = db.add.call_args[0][0]
    assert added.client_orgnr == "123456789"


def test_create_agreement_with_broker_snapshot():
    broker = MagicMock()
    broker.firm_name = "Broker AS"
    broker.orgnr = "987654321"
    broker.address = "Brokerveien 1"
    broker.contact_name = "Broker Person"
    broker.contact_email = "broker@broker.no"
    broker.contact_phone = "12345678"
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = broker
    db.refresh = MagicMock()
    svc = SlaService(db)
    svc.create_agreement(_sla_in())
    added = db.add.call_args[0][0]
    assert added.broker_snapshot["firm_name"] == "Broker AS"


def test_create_agreement_sets_status_active():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    db.refresh = MagicMock()
    svc = SlaService(db)
    svc.create_agreement(_sla_in())
    added = db.add.call_args[0][0]
    assert added.status == "active"
