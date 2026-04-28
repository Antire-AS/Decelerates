"""Unit tests for tender customer-portal service helpers."""

import sys
from unittest.mock import MagicMock

import pytest

sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.services.tender_service import TenderService


@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
def svc(db):
    return TenderService(db)


class TestGenerateCustomerToken:
    def test_unknown_tender_raises(self, svc, db):
        q = MagicMock()
        q.filter.return_value.first.return_value = None
        db.query.return_value = q
        with pytest.raises(ValueError):
            svc.generate_customer_token(999, firm_id=1, customer_email="kunde@x.no")

    def test_mints_new_token_and_persists_email(self, svc, db):
        tender = MagicMock()
        tender.customer_access_token = None
        q = MagicMock()
        q.filter.return_value.first.return_value = tender
        db.query.return_value = q

        result = svc.generate_customer_token(
            42, firm_id=1, customer_email="kunde@bergmann.no"
        )

        assert result is tender
        assert tender.customer_access_token
        assert tender.customer_email == "kunde@bergmann.no"
        assert tender.customer_approval_status == "pending"
        db.commit.assert_called_once()

    def test_idempotent_keeps_existing_token(self, svc, db):
        tender = MagicMock()
        tender.customer_access_token = "EXISTING_TOKEN"
        q = MagicMock()
        q.filter.return_value.first.return_value = tender
        db.query.return_value = q

        svc.generate_customer_token(42, firm_id=1, customer_email="ny@x.no")

        assert tender.customer_access_token == "EXISTING_TOKEN"
        assert tender.customer_email == "ny@x.no"


class TestRecordCustomerDecision:
    def test_invalid_status_raises(self, svc, db):
        with pytest.raises(ValueError):
            svc.record_customer_decision("tok", "maybe")

    def test_unknown_token_raises(self, svc, db):
        q = MagicMock()
        q.filter.return_value.first.return_value = None
        db.query.return_value = q
        with pytest.raises(ValueError):
            svc.record_customer_decision("bad_tok", "approved")

    def test_records_approval_with_timestamp(self, svc, db):
        tender = MagicMock()
        tender.customer_approval_status = "pending"
        tender.customer_approval_at = None
        q = MagicMock()
        q.filter.return_value.first.return_value = tender
        db.query.return_value = q

        result = svc.record_customer_decision("good_tok", "approved")

        assert result is tender
        assert tender.customer_approval_status == "approved"
        assert tender.customer_approval_at is not None
        db.commit.assert_called_once()

    def test_records_rejection(self, svc, db):
        tender = MagicMock()
        q = MagicMock()
        q.filter.return_value.first.return_value = tender
        db.query.return_value = q

        svc.record_customer_decision("good_tok", "rejected")
        assert tender.customer_approval_status == "rejected"
