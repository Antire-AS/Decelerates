"""Insurer and Submission CRUD service."""
from datetime import datetime, timezone, date as date_type
from typing import Optional

from sqlalchemy.orm import Session

from api.db import Insurer, Submission, SubmissionStatus
from api.domain.exceptions import NotFoundError


class InsurerService:
    def __init__(self, db: Session):
        self.db = db

    # ── Insurers ──────────────────────────────────────────────────────────────

    def list_insurers(self, firm_id: int) -> list[Insurer]:
        return (
            self.db.query(Insurer)
            .filter(Insurer.firm_id == firm_id)
            .order_by(Insurer.name)
            .all()
        )

    def create_insurer(self, firm_id: int, data: dict) -> Insurer:
        row = Insurer(
            firm_id=firm_id,
            created_at=datetime.now(timezone.utc),
            **data,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update_insurer(self, firm_id: int, insurer_id: int, data: dict) -> Insurer:
        row = self._get_insurer_or_raise(firm_id, insurer_id)
        for key, val in data.items():
            if val is not None:
                setattr(row, key, val)
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_insurer(self, firm_id: int, insurer_id: int) -> None:
        row = self._get_insurer_or_raise(firm_id, insurer_id)
        self.db.delete(row)
        self.db.commit()

    def _get_insurer_or_raise(self, firm_id: int, insurer_id: int) -> Insurer:
        row = (
            self.db.query(Insurer)
            .filter(Insurer.id == insurer_id, Insurer.firm_id == firm_id)
            .first()
        )
        if not row:
            raise NotFoundError(f"Insurer {insurer_id} not found")
        return row

    # ── Submissions ───────────────────────────────────────────────────────────

    def list_submissions(self, orgnr: str, firm_id: int) -> list[Submission]:
        return (
            self.db.query(Submission)
            .filter(Submission.orgnr == orgnr, Submission.firm_id == firm_id)
            .order_by(Submission.created_at.desc())
            .all()
        )

    def create_submission(
        self, orgnr: str, firm_id: int, created_by_email: str, data: dict
    ) -> Submission:
        status_val = data.pop("status", "pending")
        try:
            status_enum = SubmissionStatus(status_val)
        except ValueError:
            status_enum = SubmissionStatus.pending

        row = Submission(
            orgnr=orgnr,
            firm_id=firm_id,
            created_by_email=created_by_email,
            created_at=datetime.now(timezone.utc),
            status=status_enum,
            **data,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update_submission(self, firm_id: int, submission_id: int, data: dict) -> Submission:
        row = self._get_submission_or_raise(firm_id, submission_id)
        if "status" in data and data["status"] is not None:
            try:
                data["status"] = SubmissionStatus(data["status"])
            except ValueError:
                pass
        for key, val in data.items():
            if val is not None:
                setattr(row, key, val)
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_submission(self, firm_id: int, submission_id: int) -> None:
        row = self._get_submission_or_raise(firm_id, submission_id)
        self.db.delete(row)
        self.db.commit()

    def _get_submission_or_raise(self, firm_id: int, submission_id: int) -> Submission:
        row = (
            self.db.query(Submission)
            .filter(Submission.id == submission_id, Submission.firm_id == firm_id)
            .first()
        )
        if not row:
            raise NotFoundError(f"Submission {submission_id} not found")
        return row
