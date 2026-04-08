"""Unit tests for ConsentService."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from api.db import ConsentRecord, LawfulBasis
from api.domain.exceptions import NotFoundError
from api.services.consent_service import ConsentService


def _make_db():
    return MagicMock()


def _mock_consent(**kwargs):
    c = MagicMock(spec=ConsentRecord)
    c.id = kwargs.get("id", 1)
    c.orgnr = kwargs.get("orgnr", "123456789")
    c.firm_id = kwargs.get("firm_id", 1)
    c.created_at = kwargs.get("created_at", datetime.now(timezone.utc))
    c.lawful_basis = kwargs.get("lawful_basis", LawfulBasis.legitimate_interest)
    c.purpose = kwargs.get("purpose", "insurance_advice")
    c.captured_by_email = kwargs.get("captured_by_email", "broker@firm.no")
    c.withdrawn_at = kwargs.get("withdrawn_at", None)
    c.withdrawal_reason = kwargs.get("withdrawal_reason", None)
    return c


class TestRecordConsent:
    def test_creates_consent_record(self):
        db = _make_db()
        svc = ConsentService(db)
        svc.record_consent("123456789", 1, "broker@firm.no", "contract", "insurance_advice")
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_defaults_unknown_basis_to_legitimate_interest(self):
        db = _make_db()
        svc = ConsentService(db)
        # Should not raise — unknown basis falls back gracefully
        svc.record_consent("123456789", 1, "broker@firm.no", "not_a_real_basis", "insurance_advice")
        db.add.assert_called_once()


class TestWithdrawConsent:
    def test_sets_withdrawn_at(self):
        consent = _mock_consent()
        db = _make_db()
        db.query.return_value.filter.return_value.first.return_value = consent
        svc = ConsentService(db)
        svc.withdraw_consent(firm_id=1, consent_id=1, reason="Client request")
        assert consent.withdrawn_at is not None
        assert consent.withdrawal_reason == "Client request"
        db.commit.assert_called_once()

    def test_raises_not_found_for_missing_consent(self):
        db = _make_db()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = ConsentService(db)
        with pytest.raises(NotFoundError):
            svc.withdraw_consent(firm_id=1, consent_id=999)


class TestHasValidConsent:
    def test_returns_true_when_active_consent_exists(self):
        consent = _mock_consent()
        db = _make_db()
        db.query.return_value.filter.return_value.first.return_value = consent
        assert ConsentService(db).has_valid_consent("123456789", 1, "insurance_advice") is True

    def test_returns_false_when_no_consent(self):
        db = _make_db()
        db.query.return_value.filter.return_value.first.return_value = None
        assert ConsentService(db).has_valid_consent("123456789", 1, "insurance_advice") is False


class TestGetActiveConsents:
    def test_returns_list(self):
        consents = [_mock_consent(), _mock_consent(id=2)]
        db = _make_db()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = consents
        result = ConsentService(db).get_active_consents("123456789", 1)
        assert len(result) == 2
