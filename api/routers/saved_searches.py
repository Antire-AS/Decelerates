"""Saved searches endpoints — plan §🟢 #19.

Per-user filter persistence for /prospecting. Tightly scoped: every read AND
write enforces user_id == current user, so a broker can never see or modify
another user's saved searches.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.db import SavedSearch, User
from api.dependencies import get_db
from api.domain.exceptions import NotFoundError
from api.schemas import SavedSearchCreate, SavedSearchOut
from api.services.audit import log_audit
from api.services.saved_search_service import SavedSearchService

router = APIRouter()


def _svc(db: Session = Depends(get_db)) -> SavedSearchService:
    return SavedSearchService(db)


def _resolve_user_id(db: Session, user: CurrentUser) -> int:
    row = db.query(User).filter(User.azure_oid == user.oid).first()
    if not row:
        raise HTTPException(status_code=404, detail="User record not found")
    return row.id  # type: ignore[return-value]


def _serialize(s: SavedSearch) -> dict:
    return {
        "id": s.id,
        "user_id": s.user_id,
        "name": s.name,
        "params": s.params,
        "created_at": s.created_at,
    }


@router.get("/saved-searches", response_model=List[SavedSearchOut])
def list_saved_searches(
    db: Session = Depends(get_db),
    svc: SavedSearchService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    user_id = _resolve_user_id(db, user)
    return [_serialize(r) for r in svc.list_for_user(user_id)]


@router.post("/saved-searches", response_model=SavedSearchOut, status_code=201)
def create_saved_search(
    body: SavedSearchCreate,
    db: Session = Depends(get_db),
    svc: SavedSearchService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    user_id = _resolve_user_id(db, user)
    row = svc.create(user_id, body.name, body.params)
    log_audit(db, "search.create", detail={"search_id": row.id, "name": body.name})
    return _serialize(row)


@router.delete("/saved-searches/{search_id}", status_code=204)
def delete_saved_search(
    search_id: int,
    db: Session = Depends(get_db),
    svc: SavedSearchService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    user_id = _resolve_user_id(db, user)
    try:
        svc.delete(search_id, user_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    log_audit(db, "search.delete", detail={"search_id": search_id})
