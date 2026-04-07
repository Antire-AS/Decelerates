"""Activity timeline / CRM log service."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from api.db import Activity, ActivityType
from api.domain.exceptions import NotFoundError
from api.schemas import ActivityIn, ActivityUpdate


class ActivityService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_orgnr(
        self,
        orgnr: str,
        firm_id: int,
        limit: int = 50,
        assigned_to_user_id: Optional[int] = None,
    ) -> list[Activity]:
        q = self.db.query(Activity).filter(
            Activity.orgnr == orgnr, Activity.firm_id == firm_id,
        )
        if assigned_to_user_id is not None:
            q = q.filter(Activity.assigned_to_user_id == assigned_to_user_id)
        return q.order_by(Activity.created_at.desc()).limit(limit).all()

    def create(self, orgnr: str, firm_id: int, created_by: str, body: ActivityIn) -> Activity:
        try:
            atype = ActivityType[body.activity_type]
        except KeyError:
            raise NotFoundError(f"Unknown activity type: {body.activity_type}")
        activity = Activity(
            orgnr=orgnr,
            firm_id=firm_id,
            created_by_email=created_by,
            policy_id=body.policy_id,
            claim_id=body.claim_id,
            activity_type=atype,
            subject=body.subject,
            body=body.body,
            due_date=body.due_date,
            completed=body.completed,
            assigned_to_user_id=body.assigned_to_user_id,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(activity)
        try:
            self.db.commit()
            self.db.refresh(activity)
        except Exception:
            self.db.rollback()
            raise
        return activity

    def update(self, activity_id: int, firm_id: int, body: ActivityUpdate) -> Activity:
        activity = self._get_or_raise(activity_id, firm_id)
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(activity, field, value)
        try:
            self.db.commit()
            self.db.refresh(activity)
        except Exception:
            self.db.rollback()
            raise
        return activity

    def delete(self, activity_id: int, firm_id: int) -> None:
        activity = self._get_or_raise(activity_id, firm_id)
        self.db.delete(activity)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def bulk_complete(self, activity_ids: list[int], firm_id: int) -> int:
        """Plan §🟢 #18 — bulk-mark activities completed within the firm.
        firm_id scoping is enforced in the WHERE clause so a malicious caller
        passing arbitrary ids cannot touch other firms' rows."""
        if not activity_ids:
            return 0
        updated = (
            self.db.query(Activity)
            .filter(
                Activity.id.in_(activity_ids),
                Activity.firm_id == firm_id,
            )
            .update({Activity.completed: True}, synchronize_session=False)
        )
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return updated

    def _get_or_raise(self, activity_id: int, firm_id: int) -> Activity:
        a = (
            self.db.query(Activity)
            .filter(Activity.id == activity_id, Activity.firm_id == firm_id)
            .first()
        )
        if not a:
            raise NotFoundError(f"Activity {activity_id} not found")
        return a
