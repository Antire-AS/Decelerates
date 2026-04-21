"""Unit tests for api/services/accounting_service.py — AccountingService."""

import sys
from unittest.mock import MagicMock, patch

sys.modules.setdefault("api.services.pdf_background", MagicMock())


# ── Config detection ─────────────────────────────────────────────────────────


class TestIsTripletexConfigured:
    def test_configured_when_both_set(self):
        with patch("api.services.accounting_service._tripletex_config") as m:
            m.return_value = MagicMock(api_key="key123", company_id="co1")
            from api.services.accounting_service import AccountingService

            svc = AccountingService(db=MagicMock())
        assert svc.is_tripletex_configured() is True

    def test_not_configured_when_key_empty(self):
        with patch("api.services.accounting_service._tripletex_config") as m:
            m.return_value = MagicMock(api_key="", company_id="co1")
            from api.services.accounting_service import AccountingService

            svc = AccountingService(db=MagicMock())
        assert svc.is_tripletex_configured() is False

    def test_not_configured_when_company_id_empty(self):
        with patch("api.services.accounting_service._tripletex_config") as m:
            m.return_value = MagicMock(api_key="key123", company_id="")
            from api.services.accounting_service import AccountingService

            svc = AccountingService(db=MagicMock())
        assert svc.is_tripletex_configured() is False


class TestIsFikenConfigured:
    def test_configured_when_both_set(self):
        with patch("api.services.accounting_service._fiken_config") as m:
            m.return_value = MagicMock(access_token="tok", company_slug="slug")
            from api.services.accounting_service import AccountingService

            svc = AccountingService(db=MagicMock())
        assert svc.is_fiken_configured() is True

    def test_not_configured_when_token_empty(self):
        with patch("api.services.accounting_service._fiken_config") as m:
            m.return_value = MagicMock(access_token="", company_slug="slug")
            from api.services.accounting_service import AccountingService

            svc = AccountingService(db=MagicMock())
        assert svc.is_fiken_configured() is False


# ── Sync operations ──────────────────────────────────────────────────────────


class TestSyncInvoicesToTripletex:
    def test_returns_error_when_not_configured(self):
        with (
            patch("api.services.accounting_service._tripletex_config") as mt,
            patch("api.services.accounting_service._fiken_config") as mf,
        ):
            mt.return_value = MagicMock(api_key="", company_id="")
            mf.return_value = MagicMock(access_token="", company_slug="")
            from api.services.accounting_service import AccountingService

            svc = AccountingService(db=MagicMock())
        result = svc.sync_invoices_to_tripletex(firm_id=1)
        assert result["synced"] == 0
        assert "Tripletex ikke konfigurert" in result["errors"]

    def test_syncs_policies_successfully(self):
        db = MagicMock()
        policy = MagicMock(id=10, commission_amount_nok=5000.0)
        db.query.return_value.filter.return_value.filter.return_value.all.return_value = [
            policy
        ]

        with (
            patch("api.services.accounting_service._tripletex_config") as mt,
            patch("api.services.accounting_service._fiken_config") as mf,
            patch("api.services.accounting_service._create_tripletex_invoice"),
        ):
            mt.return_value = MagicMock(api_key="key", company_id="co1")
            mf.return_value = MagicMock(access_token="", company_slug="")
            from api.services.accounting_service import AccountingService

            svc = AccountingService(db=db)
            result = svc.sync_invoices_to_tripletex(firm_id=1)

        assert result["synced"] == 1
        assert result["errors"] == []

    def test_records_error_when_invoice_creation_fails(self):
        db = MagicMock()
        policy = MagicMock(id=99, commission_amount_nok=1000.0)
        db.query.return_value.filter.return_value.filter.return_value.all.return_value = [
            policy
        ]

        with (
            patch("api.services.accounting_service._tripletex_config") as mt,
            patch("api.services.accounting_service._fiken_config") as mf,
            patch(
                "api.services.accounting_service._create_tripletex_invoice",
                side_effect=RuntimeError("API down"),
            ),
        ):
            mt.return_value = MagicMock(api_key="key", company_id="co1")
            mf.return_value = MagicMock(access_token="", company_slug="")
            from api.services.accounting_service import AccountingService

            svc = AccountingService(db=db)
            result = svc.sync_invoices_to_tripletex(firm_id=1)

        assert result["synced"] == 0
        assert len(result["errors"]) == 1
        assert "Policy 99" in result["errors"][0]


class TestSyncReceiptsToFiken:
    def test_returns_error_when_not_configured(self):
        with (
            patch("api.services.accounting_service._tripletex_config") as mt,
            patch("api.services.accounting_service._fiken_config") as mf,
        ):
            mt.return_value = MagicMock(api_key="", company_id="")
            mf.return_value = MagicMock(access_token="", company_slug="")
            from api.services.accounting_service import AccountingService

            svc = AccountingService(db=MagicMock())
        result = svc.sync_receipts_to_fiken(firm_id=1)
        assert result["synced"] == 0
        assert "Fiken ikke konfigurert" in result["errors"]

    def test_syncs_receipts_successfully(self):
        db = MagicMock()
        policy = MagicMock(id=20, commission_amount_nok=3000.0)
        db.query.return_value.filter.return_value.filter.return_value.all.return_value = [
            policy
        ]

        with (
            patch("api.services.accounting_service._tripletex_config") as mt,
            patch("api.services.accounting_service._fiken_config") as mf,
            patch("api.services.accounting_service._create_fiken_receipt"),
        ):
            mt.return_value = MagicMock(api_key="", company_id="")
            mf.return_value = MagicMock(access_token="tok", company_slug="slug")
            from api.services.accounting_service import AccountingService

            svc = AccountingService(db=db)
            result = svc.sync_receipts_to_fiken(firm_id=1)

        assert result["synced"] == 1
        assert result["errors"] == []


class TestGetSyncStatus:
    def test_returns_status_dict(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value.count.return_value = 5

        with (
            patch("api.services.accounting_service._tripletex_config") as mt,
            patch("api.services.accounting_service._fiken_config") as mf,
        ):
            mt.return_value = MagicMock(api_key="key", company_id="co1")
            mf.return_value = MagicMock(access_token="", company_slug="")
            from api.services.accounting_service import AccountingService

            svc = AccountingService(db=db)
            result = svc.get_sync_status(firm_id=1)

        assert result["tripletex_configured"] is True
        assert result["fiken_configured"] is False
        assert result["policies_with_commission"] == 5
