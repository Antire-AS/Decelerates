"""User management endpoints."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.dependencies import get_db
from api.domain.exceptions import ForbiddenError, NotFoundError
from api.schemas import UserRoleUpdate
from api.services.user_service import UserService

router = APIRouter()
_log = logging.getLogger(__name__)


def _svc(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)


def _serialize(user, include_firm: bool = False) -> dict:
    d = {
        "id":         user.id,
        "email":      user.email,
        "name":       user.name,
        "role":       user.role.value,
        "firm_id":    user.firm_id,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
    return d


@router.get("/users/me")
def get_me(user: CurrentUser = Depends(get_current_user)) -> dict:
    """Return the current user's profile."""
    return {
        "email":   user.email,
        "name":    user.name,
        "oid":     user.oid,
        "firm_id": user.firm_id,
    }


@router.get("/users")
def list_users(
    svc: UserService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    """List all users in the current firm."""
    return [_serialize(u) for u in svc.list_users(user.firm_id)]


@router.put("/users/{user_id}/role")
def update_role(
    user_id: int,
    body: UserRoleUpdate,
    svc: UserService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Change a user's role (admin only)."""
    try:
        updated = svc.update_role(user_id, body, requester_role=user.role if hasattr(user, "role") else "broker")
        return _serialize(updated)
    except ForbiddenError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
