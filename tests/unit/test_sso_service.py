"""Unit tests for api/services/sso_service.py — SsoService."""
import sys
from unittest.mock import MagicMock, patch

sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

import pytest

from api.services.sso_service import SsoService


# ── _extract_tenant_id ────────────────────────────────────────────────────────


class TestExtractTenantId:
    def test_extracts_from_tid_claim(self):
        claims = {"tid": "abc-123-def"}
        result = SsoService._extract_tenant_id(claims)
        assert result == "abc-123-def"

    def test_extracts_from_issuer_url(self):
        claims = {"iss": "https://login.microsoftonline.com/11112222-3333-4444-5555-666677778888/v2.0"}
        result = SsoService._extract_tenant_id(claims)
        assert result == "11112222-3333-4444-5555-666677778888"

    def test_tid_takes_precedence_over_iss(self):
        claims = {
            "tid": "from-tid",
            "iss": "https://login.microsoftonline.com/from-iss/v2.0",
        }
        result = SsoService._extract_tenant_id(claims)
        assert result == "from-tid"

    def test_returns_none_for_empty_claims(self):
        result = SsoService._extract_tenant_id({})
        assert result is None

    def test_returns_none_for_non_azure_issuer(self):
        claims = {"iss": "https://accounts.google.com/o/oauth2/v2/auth"}
        result = SsoService._extract_tenant_id(claims)
        assert result is None


# ── resolve_firm_from_token ──────────────────────────────────────────────────


class TestResolveFirmFromToken:
    def test_returns_existing_firm(self):
        db = MagicMock()
        existing_firm = MagicMock(id=1, name="Existing Firm")
        db.query.return_value.filter.return_value.first.return_value = existing_firm

        svc = SsoService()
        claims = {"tid": "tenant-aaa"}
        result = svc.resolve_firm_from_token(claims, db)

        assert result == existing_firm
        db.add.assert_not_called()

    def test_auto_provisions_new_firm(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        svc = SsoService()
        claims = {"tid": "tenant-bbb", "tid_name": "New Corp AS"}
        result = svc.resolve_firm_from_token(claims, db)

        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once()
        added_firm = db.add.call_args[0][0]
        assert added_firm.name == "New Corp AS"
        assert added_firm.azure_tenant_id == "tenant-bbb"
        assert added_firm.is_demo is False

    def test_auto_provision_uses_fallback_name(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        svc = SsoService()
        claims = {"tid": "tenant-ccc"}
        svc.resolve_firm_from_token(claims, db)

        added_firm = db.add.call_args[0][0]
        assert "tenant-c" in added_firm.name

    def test_raises_on_missing_tenant_id(self):
        db = MagicMock()
        svc = SsoService()
        with pytest.raises(ValueError, match="Cannot extract tenant_id"):
            svc.resolve_firm_from_token({}, db)
