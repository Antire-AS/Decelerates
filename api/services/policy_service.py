"""Policy register and renewal pipeline service."""
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from api.db import Policy, PolicyStatus, RenewalStage
from api.domain.exceptions import NotFoundError, ValidationError
from api.schemas import PolicyIn, PolicyUpdate


class PolicyService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_orgnr(self, orgnr: str, firm_id: int, skip: int = 0, limit: int = 100) -> list[Policy]:
        return (
            self.db.query(Policy)
            .filter(Policy.orgnr == orgnr, Policy.firm_id == firm_id)
            .order_by(Policy.renewal_date.asc().nullslast())
            .offset(skip).limit(limit)
            .all()
        )

    def list_by_firm(self, firm_id: int, skip: int = 0, limit: int = 100) -> list[Policy]:
        return (
            self.db.query(Policy)
            .filter(Policy.firm_id == firm_id)
            .order_by(Policy.renewal_date.asc().nullslast())
            .offset(skip).limit(limit)
            .all()
        )

    def create(self, orgnr: str, firm_id: int, body: PolicyIn) -> Policy:
        now = datetime.now(timezone.utc)
        policy = Policy(
            orgnr=orgnr,
            firm_id=firm_id,
            contact_person_id=body.contact_person_id,
            policy_number=body.policy_number,
            insurer=body.insurer,
            product_type=body.product_type,
            coverage_amount_nok=body.coverage_amount_nok,
            annual_premium_nok=body.annual_premium_nok,
            start_date=body.start_date,
            renewal_date=body.renewal_date,
            status=self._parse_status(body.status),
            renewal_stage=self._parse_renewal_stage(body.renewal_stage) if body.renewal_stage else RenewalStage.not_started,
            notes=body.notes,
            created_at=now,
            updated_at=now,
        )
        self.db.add(policy)
        self.db.commit()
        self.db.refresh(policy)
        return policy

    def update(self, policy_id: int, firm_id: int, body: PolicyUpdate) -> Policy:
        policy = self._get_or_raise(policy_id, firm_id)
        data = body.model_dump(exclude_none=True)
        if "status" in data:
            data["status"] = self._parse_status(data["status"])
        if "renewal_stage" in data:
            data["renewal_stage"] = self._parse_renewal_stage(data["renewal_stage"])
        for field, value in data.items():
            setattr(policy, field, value)
        policy.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(policy)
        return policy

    def advance_renewal_stage(self, policy_id: int, firm_id: int, new_stage: str) -> Policy:
        policy = self._get_or_raise(policy_id, firm_id)
        policy.renewal_stage = self._parse_renewal_stage(new_stage)
        policy.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(policy)
        return policy

    def delete(self, policy_id: int, firm_id: int) -> None:
        policy = self._get_or_raise(policy_id, firm_id)
        self.db.delete(policy)
        self.db.commit()

    def get_renewals(self, firm_id: int, days: int = 90) -> list[Policy]:
        today  = date.today()
        cutoff = today + timedelta(days=days)
        return (
            self.db.query(Policy)
            .filter(
                Policy.firm_id == firm_id,
                Policy.status == PolicyStatus.active,
                Policy.renewal_date >= today,
                Policy.renewal_date <= cutoff,
            )
            .order_by(Policy.renewal_date.asc())
            .all()
        )

    def _get_or_raise(self, policy_id: int, firm_id: int) -> Policy:
        p = (
            self.db.query(Policy)
            .filter(Policy.id == policy_id, Policy.firm_id == firm_id)
            .first()
        )
        if not p:
            raise NotFoundError(f"Policy {policy_id} not found")
        return p

    @staticmethod
    def _parse_status(value: str) -> PolicyStatus:
        try:
            return PolicyStatus[value]
        except KeyError:
            raise ValidationError(f"Unknown policy status: '{value}'")

    @staticmethod
    def _parse_renewal_stage(value: str) -> RenewalStage:
        try:
            return RenewalStage[value]
        except KeyError:
            raise ValidationError(f"Unknown renewal stage: '{value}'")
