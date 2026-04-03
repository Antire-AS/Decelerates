"""IDD (Insurance Distribution Directive) service — behovsanalyse CRUD."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from api.db import IddBehovsanalyse
from api.domain.exceptions import NotFoundError


class IddService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, orgnr: str, firm_id: int, created_by_email: str, data: dict) -> IddBehovsanalyse:
        row = IddBehovsanalyse(
            orgnr=orgnr,
            firm_id=firm_id,
            created_by_email=created_by_email,
            created_at=datetime.now(timezone.utc),
            **data,
        )
        self.db.add(row)
        try:
            self.db.commit()
            self.db.refresh(row)
        except Exception:
            self.db.rollback()
            raise
        return row

    def get(self, orgnr: str, firm_id: int, idd_id: int) -> IddBehovsanalyse:
        return self._get_or_raise(orgnr, firm_id, idd_id)

    def delete(self, orgnr: str, firm_id: int, idd_id: int) -> None:
        row = self._get_or_raise(orgnr, firm_id, idd_id)
        self.db.delete(row)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _get_or_raise(self, orgnr: str, firm_id: int, idd_id: int) -> IddBehovsanalyse:
        row = (
            self.db.query(IddBehovsanalyse)
            .filter(
                IddBehovsanalyse.id == idd_id,
                IddBehovsanalyse.orgnr == orgnr,
                IddBehovsanalyse.firm_id == firm_id,
            )
            .first()
        )
        if not row:
            raise NotFoundError(f"Behovsanalyse {idd_id} not found")
        return row
