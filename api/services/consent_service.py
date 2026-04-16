"""GDPR consent and lawful-basis management service."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from api.db import ConsentRecord, LawfulBasis
from api.domain.exceptions import NotFoundError
import logging

logger = logging.getLogger(__name__)



class ConsentService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record_consent(
        self,
        orgnr: str,
        firm_id: int,
        actor_email: str,
        lawful_basis: str,
        purpose: str,
    ) -> ConsentRecord:
        try:
            basis_enum = LawfulBasis(lawful_basis)
        except ValueError:
            basis_enum = LawfulBasis.legitimate_interest

        row = ConsentRecord(
            orgnr=orgnr,
            firm_id=firm_id,
            created_at=datetime.now(timezone.utc),
            lawful_basis=basis_enum,
            purpose=purpose,
            captured_by_email=actor_email,
        )
        self.db.add(row)
        try:
            self.db.commit()
            self.db.refresh(row)
        except Exception:
            self.db.rollback()
            raise
        return row

    def withdraw_consent(self, firm_id: int, consent_id: int, reason: Optional[str] = None) -> ConsentRecord:
        row = self._get_or_raise(firm_id, consent_id)
        row.withdrawn_at = datetime.now(timezone.utc)
        row.withdrawal_reason = reason
        try:
            self.db.commit()
            self.db.refresh(row)
        except Exception:
            self.db.rollback()
            raise
        return row

    def get_active_consents(self, orgnr: str, firm_id: int) -> list[ConsentRecord]:
        return (
            self.db.query(ConsentRecord)
            .filter(
                ConsentRecord.orgnr == orgnr,
                ConsentRecord.firm_id == firm_id,
                ConsentRecord.withdrawn_at.is_(None),
            )
            .order_by(ConsentRecord.created_at.desc())
            .all()
        )

    def has_valid_consent(self, orgnr: str, firm_id: int, purpose: str) -> bool:
        return (
            self.db.query(ConsentRecord)
            .filter(
                ConsentRecord.orgnr == orgnr,
                ConsentRecord.firm_id == firm_id,
                ConsentRecord.purpose == purpose,
                ConsentRecord.withdrawn_at.is_(None),
            )
            .first()
        ) is not None

    def _get_or_raise(self, firm_id: int, consent_id: int) -> ConsentRecord:
        row = (
            self.db.query(ConsentRecord)
            .filter(ConsentRecord.id == consent_id, ConsentRecord.firm_id == firm_id)
            .first()
        )
        if not row:
            raise NotFoundError(f"Consent record {consent_id} not found")
        return row
