"""SSO firm discovery — maps Azure AD token claims to a BrokerFirm.

Phase 1 foundation: extract tenant_id from the JWT issuer claim and look up
(or auto-provision) a BrokerFirm row. Called from auth.py when a real JWT
is validated (not in AUTH_DISABLED mode).
"""
import logging
import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from api.db import BrokerFirm

_log = logging.getLogger(__name__)

# Azure AD v2.0 issuer format: https://login.microsoftonline.com/{tenant_id}/v2.0
_ISSUER_RE = re.compile(
    r"https://login\.microsoftonline\.com/([0-9a-f-]+)/v2\.0"
)


class SsoService:
    """Resolve a BrokerFirm from Azure AD JWT claims."""

    def resolve_firm_from_token(self, claims: dict, db: Session) -> BrokerFirm:
        """Map Azure AD token claims to a BrokerFirm.

        Strategy:
        1. Extract tenant_id from 'iss' claim (issuer URL contains tenant ID)
        2. Look up BrokerFirm by azure_tenant_id
        3. If not found, auto-provision a new firm
        """
        tenant_id = self._extract_tenant_id(claims)
        if not tenant_id:
            raise ValueError("Cannot extract tenant_id from token claims")

        firm = (
            db.query(BrokerFirm)
            .filter(BrokerFirm.azure_tenant_id == tenant_id)
            .first()
        )
        if firm:
            return firm

        # Auto-provision a new firm for this tenant
        firm_name = claims.get("tid_name") or f"Firm ({tenant_id[:8]}...)"
        firm = BrokerFirm(
            name=firm_name,
            azure_tenant_id=tenant_id,
            is_demo=False,
            created_at=datetime.now(timezone.utc),
        )
        db.add(firm)
        db.commit()
        db.refresh(firm)
        _log.info("Auto-provisioned BrokerFirm id=%d for tenant %s", firm.id, tenant_id)
        return firm

    @staticmethod
    def _extract_tenant_id(claims: dict) -> str | None:
        """Extract the Azure AD tenant ID from token claims.

        Tries 'tid' claim first (standard Azure AD), then falls back to
        parsing the issuer URL.
        """
        # Azure AD tokens always include a 'tid' claim
        tid = claims.get("tid")
        if tid:
            return tid

        # Fallback: parse from issuer URL
        iss = claims.get("iss", "")
        match = _ISSUER_RE.match(iss)
        if match:
            return match.group(1)

        return None
