"""Unit tests for api/services/tender_service.py — tender lifecycle."""

import sys
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.db import Tender, TenderRecipientStatus
from api.services.tender_service import TenderService


@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
def svc(db):
    return TenderService(db)


class TestCreate:
    def test_creates_tender_with_recipients(self, svc, db):
        db.flush = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()

        svc.create(
            orgnr="984851006",
            firm_id=1,
            title="Test Tender",
            product_types=["Eiendom", "Ansvar"],
            deadline=date(2026, 6, 1),
            notes="Test notes",
            created_by_email="test@test.com",
            recipients=[
                {"insurer_name": "If", "insurer_email": "if@if.no"},
                {"insurer_name": "Gjensidige"},
            ],
        )
        assert db.add.call_count >= 3  # 1 tender + 2 recipients
        db.commit.assert_called_once()

    def test_creates_tender_without_recipients(self, svc, db):
        db.flush = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()

        svc.create(
            orgnr="123456789",
            firm_id=1,
            title="Empty",
            product_types=["Cyber"],
        )
        assert db.add.call_count == 1  # only tender
        db.commit.assert_called_once()


class TestGet:
    def test_get_filters_by_firm_id(self, svc, db):
        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        svc.get(42, firm_id=1)
        db.query.assert_called_once_with(Tender)
        # Verify filter was called (firm_id check)
        mock_query.filter.assert_called_once()

    def test_get_returns_none_for_wrong_firm(self, svc, db):
        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        result = svc.get(42, firm_id=999)
        assert result is None


class TestListAll:
    def test_filters_by_firm_id(self, svc, db):
        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        svc.list_all(firm_id=1)
        mock_query.filter.assert_called_once()


class TestListForCompany:
    def test_filters_by_orgnr_and_firm_id(self, svc, db):
        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        svc.list_for_company("984851006", firm_id=1)
        mock_query.filter.assert_called_once()


class TestUpdate:
    def test_update_returns_none_for_missing(self, svc, db):
        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        result = svc.update(999, firm_id=1, title="New Title")
        assert result is None

    def test_update_sets_fields(self, svc, db):
        tender = MagicMock()
        tender.id = 1
        tender.firm_id = 1
        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = tender

        svc.update(1, firm_id=1, title="Updated")
        assert tender.title == "Updated"
        db.commit.assert_called_once()


class TestDelete:
    def test_delete_returns_false_for_missing(self, svc, db):
        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        assert svc.delete(999, firm_id=1) is False

    def test_delete_removes_and_commits(self, svc, db):
        tender = MagicMock()
        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = tender

        assert svc.delete(1, firm_id=1) is True
        db.delete.assert_called_once_with(tender)
        db.commit.assert_called_once()


class TestMarkContractSignedBySession:
    def test_empty_session_id_returns_none_without_query(self, svc, db):
        assert svc.mark_contract_signed_by_session("") is None
        db.query.assert_not_called()

    def test_unknown_session_returns_none(self, svc, db):
        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        assert svc.mark_contract_signed_by_session("sub-nope") is None
        db.commit.assert_not_called()

    def test_flips_status_to_analysed_and_commits(self, svc, db):
        from api.db import TenderStatus

        tender = MagicMock()
        tender.status = TenderStatus.sent
        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = tender

        result = svc.mark_contract_signed_by_session("sub-42")
        assert result is tender
        assert tender.status == TenderStatus.analysed
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(tender)


class TestUploadOffer:
    @patch("api.services.coverage_service._extract_text", return_value="sample text")
    def test_upload_stores_pdf(self, mock_extract, svc, db):
        db.commit = MagicMock()
        db.refresh = MagicMock()

        svc.upload_offer(
            tender_id=1,
            insurer_name="If",
            filename="tilbud.pdf",
            pdf_bytes=b"%PDF-test",
        )
        db.add.assert_called_once()
        db.commit.assert_called_once()

    @patch("api.services.coverage_service._extract_text", return_value="text")
    def test_upload_marks_recipient_received(self, mock_extract, svc, db):
        recipient = MagicMock()
        recipient.status = TenderRecipientStatus.sent
        db.query.return_value.get.return_value = recipient
        db.commit = MagicMock()
        db.refresh = MagicMock()

        svc.upload_offer(
            tender_id=1,
            insurer_name="If",
            filename="tilbud.pdf",
            pdf_bytes=b"%PDF-test",
            recipient_id=5,
        )
        assert recipient.status == TenderRecipientStatus.received


class TestSendInvitations:
    def test_raises_for_missing_tender(self, svc, db):
        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        with pytest.raises(ValueError, match="not found"):
            svc.send_invitations(999, firm_id=1)


class TestAnalyseOffers:
    def test_raises_for_too_few_offers(self, svc, db):
        mock_query = MagicMock()
        db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [MagicMock()]  # only 1

        with pytest.raises(ValueError, match="Minst 2"):
            svc.analyse_offers(1, firm_id=1)


class TestSendTenderEmail:
    @patch("api.container.resolve")
    def test_sends_email(self, mock_resolve):
        from api.services.tender_service import _send_tender_email

        mock_notification = MagicMock()
        mock_notification.send_email.return_value = True
        mock_resolve.return_value = mock_notification

        tender = MagicMock()
        tender.product_types = ["Eiendom"]
        tender.deadline = date(2026, 6, 1)
        tender.notes = "Test <script>alert(1)</script>"

        result = _send_tender_email("test@test.no", tender, "DNB", "If")
        assert result is True
        call_args = mock_notification.send_email.call_args
        # Verify XSS is escaped
        assert "<script>" not in call_args[0][2]

    @patch("api.container.resolve", side_effect=Exception("no port"))
    def test_returns_false_on_error(self, mock_resolve):
        from api.services.tender_service import _send_tender_email

        tender = MagicMock()
        tender.product_types = []
        tender.deadline = None
        tender.notes = None
        result = _send_tender_email("test@test.no", tender, "DNB", "If")
        assert result is False
