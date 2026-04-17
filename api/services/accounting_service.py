"""Accounting integration service — Tripletex and Fiken.

Provides two-way sync between the broker's policy/commission data and
external accounting systems. Currently a foundation skeleton — actual
API calls require sandbox credentials:

  - Tripletex: REST API with API key auth (tripletex.no/v2-docs)
  - Fiken: REST API with OAuth2 (fiken.no/api-docs)

Usage:
  Set TRIPLETEX_API_KEY + TRIPLETEX_COMPANY_ID for Tripletex
  Set FIKEN_ACCESS_TOKEN + FIKEN_COMPANY_SLUG for Fiken
"""

import logging
import os
from dataclasses import dataclass

from sqlalchemy.orm import Session

from api.db import Policy, PolicyStatus

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TripletexConfig:
    api_key: str = ""
    company_id: str = ""
    base_url: str = "https://tripletex.no/v2"


@dataclass(frozen=True)
class FikenConfig:
    access_token: str = ""
    company_slug: str = ""
    base_url: str = "https://api.fiken.no/api/v2"


class AccountingService:
    """Sync policies and commissions to external accounting systems."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.tripletex = _tripletex_config()
        self.fiken = _fiken_config()

    def is_tripletex_configured(self) -> bool:
        return bool(self.tripletex.api_key and self.tripletex.company_id)

    def is_fiken_configured(self) -> bool:
        return bool(self.fiken.access_token and self.fiken.company_slug)

    def sync_invoices_to_tripletex(self, firm_id: int) -> dict:
        """Create Tripletex invoices for active policies with commission.

        Returns {synced: int, skipped: int, errors: list}.
        Currently a skeleton — needs Tripletex sandbox for real implementation.
        """
        if not self.is_tripletex_configured():
            return {"synced": 0, "skipped": 0, "errors": ["Tripletex ikke konfigurert"]}

        policies = (
            self.db.query(Policy)
            .filter(Policy.firm_id == firm_id, Policy.status == PolicyStatus.active)
            .filter(Policy.commission_amount_nok.isnot(None))
            .all()
        )

        synced = 0
        errors = []
        for p in policies:
            try:
                _create_tripletex_invoice(self.tripletex, p)
                synced += 1
            except Exception as exc:
                errors.append(f"Policy {p.id}: {exc}")

        return {"synced": synced, "skipped": len(policies) - synced, "errors": errors}

    def sync_receipts_to_fiken(self, firm_id: int) -> dict:
        """Create Fiken receipts for commission payments.

        Returns {synced: int, skipped: int, errors: list}.
        Currently a skeleton — needs Fiken OAuth2 token.
        """
        if not self.is_fiken_configured():
            return {"synced": 0, "skipped": 0, "errors": ["Fiken ikke konfigurert"]}

        policies = (
            self.db.query(Policy)
            .filter(Policy.firm_id == firm_id, Policy.status == PolicyStatus.active)
            .filter(Policy.commission_amount_nok.isnot(None))
            .all()
        )

        synced = 0
        errors = []
        for p in policies:
            try:
                _create_fiken_receipt(self.fiken, p)
                synced += 1
            except Exception as exc:
                errors.append(f"Policy {p.id}: {exc}")

        return {"synced": synced, "skipped": len(policies) - synced, "errors": errors}

    def get_sync_status(self, firm_id: int) -> dict:
        """Return current sync status for both providers."""
        policies_with_commission = (
            self.db.query(Policy)
            .filter(Policy.firm_id == firm_id, Policy.status == PolicyStatus.active)
            .filter(Policy.commission_amount_nok.isnot(None))
            .count()
        )
        return {
            "tripletex_configured": self.is_tripletex_configured(),
            "fiken_configured": self.is_fiken_configured(),
            "policies_with_commission": policies_with_commission,
        }


def _create_tripletex_invoice(config: TripletexConfig, policy: Policy) -> None:
    """Create a Tripletex invoice for a policy commission.

    TODO: Replace with actual Tripletex API call when sandbox is available.
    POST /v2/invoice with:
      - customer: policy.orgnr (map to Tripletex customer ID)
      - invoiceDate: today
      - lines: [{description: product_type, unitPrice: commission_amount_nok}]
    """
    _log.info(
        "Tripletex invoice stub: policy %d, %.2f NOK",
        policy.id,
        policy.commission_amount_nok or 0,
    )
    # When sandbox is ready:
    # import httpx
    # resp = httpx.post(f"{config.base_url}/invoice", ...)


def _create_fiken_receipt(config: FikenConfig, policy: Policy) -> None:
    """Create a Fiken receipt for a commission payment.

    TODO: Replace with actual Fiken API call when OAuth2 token is available.
    POST /api/v2/companies/{slug}/sales with:
      - date: today
      - lines: [{description: f"Provisjon: {policy.insurer} {policy.product_type}", net: commission_amount_nok}]
    """
    _log.info(
        "Fiken receipt stub: policy %d, %.2f NOK",
        policy.id,
        policy.commission_amount_nok or 0,
    )


def _tripletex_config() -> TripletexConfig:
    return TripletexConfig(
        api_key=os.getenv("TRIPLETEX_API_KEY", ""),
        company_id=os.getenv("TRIPLETEX_COMPANY_ID", ""),
    )


def _fiken_config() -> FikenConfig:
    return FikenConfig(
        access_token=os.getenv("FIKEN_ACCESS_TOKEN", ""),
        company_slug=os.getenv("FIKEN_COMPANY_SLUG", ""),
    )
