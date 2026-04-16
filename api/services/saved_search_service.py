"""Saved searches service — plan §🟢 #19. Per-user filter persistence."""
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from api.db import SavedSearch
from api.domain.exceptions import NotFoundError
import logging

logger = logging.getLogger(__name__)



class SavedSearchService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_user(self, user_id: int) -> List[SavedSearch]:
        return (
            self.db.query(SavedSearch)
            .filter(SavedSearch.user_id == user_id)
            .order_by(SavedSearch.created_at.desc())
            .all()
        )

    def create(self, user_id: int, name: str, params: Dict[str, Any]) -> SavedSearch:
        row = SavedSearch(
            user_id=user_id,
            name=name,
            params=params,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(row)
        try:
            self.db.commit()
            self.db.refresh(row)
        except Exception:
            self.db.rollback()
            raise
        return row

    def delete(self, search_id: int, user_id: int) -> None:
        """user_id check prevents one user from deleting another's searches."""
        row = (
            self.db.query(SavedSearch)
            .filter(SavedSearch.id == search_id, SavedSearch.user_id == user_id)
            .first()
        )
        if not row:
            raise NotFoundError(f"Saved search {search_id} not found")
        self.db.delete(row)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
