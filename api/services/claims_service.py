"""Claims tracking service."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from api.db import Claim, ClaimStatus, Policy
from api.domain.exceptions import NotFoundError
from api.schemas import ClaimIn, ClaimUpdate
import logging

logger = logging.getLogger(__name__)


class ClaimsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_orgnr(
        self, orgnr: str, firm_id: int, skip: int = 0, limit: int = 100
    ) -> list[Claim]:
        return (
            self.db.query(Claim)
            .filter(Claim.orgnr == orgnr, Claim.firm_id == firm_id)
            .order_by(Claim.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_by_policy(self, policy_id: int, firm_id: int) -> list[Claim]:
        return (
            self.db.query(Claim)
            .filter(Claim.policy_id == policy_id, Claim.firm_id == firm_id)
            .order_by(Claim.created_at.desc())
            .all()
        )

    def create(self, orgnr: str, firm_id: int, body: ClaimIn) -> Claim:
        policy = self._get_policy_or_raise(body.policy_id, firm_id)
        now = datetime.now(timezone.utc)
        claim = Claim(
            policy_id=policy.id,
            orgnr=orgnr,
            firm_id=firm_id,
            claim_number=body.claim_number,
            incident_date=body.incident_date,
            reported_date=body.reported_date,
            status=self._parse_status(body.status),
            description=body.description,
            estimated_amount_nok=body.estimated_amount_nok,
            insurer_contact=body.insurer_contact,
            notes=body.notes,
            created_at=now,
            updated_at=now,
        )
        self.db.add(claim)
        try:
            self.db.commit()
            self.db.refresh(claim)
        except Exception:
            self.db.rollback()
            raise
        return claim

    def update(self, claim_id: int, firm_id: int, body: ClaimUpdate) -> Claim:
        claim = self._get_or_raise(claim_id, firm_id)
        data = body.model_dump(exclude_none=True)
        if "status" in data:
            data["status"] = self._parse_status(data["status"])
        for field, value in data.items():
            setattr(claim, field, value)
        claim.updated_at = datetime.now(timezone.utc)
        try:
            self.db.commit()
            self.db.refresh(claim)
        except Exception:
            self.db.rollback()
            raise
        return claim

    def delete(self, claim_id: int, firm_id: int) -> None:
        claim = self._get_or_raise(claim_id, firm_id)
        self.db.delete(claim)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _get_or_raise(self, claim_id: int, firm_id: int) -> Claim:
        c = (
            self.db.query(Claim)
            .filter(Claim.id == claim_id, Claim.firm_id == firm_id)
            .first()
        )
        if not c:
            raise NotFoundError(f"Claim {claim_id} not found")
        return c

    def _get_policy_or_raise(self, policy_id: int, firm_id: int) -> Policy:
        p = (
            self.db.query(Policy)
            .filter(Policy.id == policy_id, Policy.firm_id == firm_id)
            .first()
        )
        if not p:
            raise NotFoundError(f"Policy {policy_id} not found")
        return p

    @staticmethod
    def _parse_status(value: str) -> ClaimStatus:
        try:
            return ClaimStatus[value]
        except KeyError:
            raise NotFoundError(f"Unknown claim status: {value}")
