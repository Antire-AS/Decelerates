"""Admin CRUD endpoints — reset, demo seed variants. Requires admin role."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.db import UserRole
from api.limiter import limiter
from api.dependencies import get_db
from api.services.admin_service import AdminService

router = APIRouter()


def _admin_svc(db: Session = Depends(get_db)) -> AdminService:
    return AdminService(db)


def _require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Gate all admin endpoints behind admin role."""
    if hasattr(user, "role") and user.role not in (UserRole.admin, "admin"):
        raise HTTPException(status_code=403, detail="Admin-tilgang kreves")
    return user


@router.delete("/admin/reset")
@limiter.limit("5/hour")
def admin_reset(request: Request, svc: AdminService = Depends(_admin_svc), _user=Depends(_require_admin)) -> dict:
    return svc.reset()


@router.post("/admin/demo")
@limiter.limit("10/hour")
def admin_demo(request: Request, svc: AdminService = Depends(_admin_svc), _user=Depends(_require_admin)) -> dict:
    return svc.seed_demo()


@router.post("/admin/seed-norway-top100")
@limiter.limit("10/hour")
def admin_seed_norway_top100(request: Request, svc: AdminService = Depends(_admin_svc), _user=Depends(_require_admin)) -> dict:
    return svc.seed_norway_top100()


@router.post("/admin/seed-crm-demo")
@limiter.limit("10/hour")
def seed_crm_demo(request: Request, svc: AdminService = Depends(_admin_svc), _user=Depends(_require_admin)) -> dict:
    return svc.seed_crm_demo()


@router.post("/admin/seed-demo-documents")
def seed_demo_documents_endpoint(db: Session = Depends(get_db), _user=Depends(_require_admin)) -> dict:
    from api.services.demo_documents import seed_demo_documents
    return seed_demo_documents(db)


@router.post("/admin/seed-full-demo")
def seed_full_demo_endpoint(db: Session = Depends(get_db), _user=Depends(_require_admin)) -> dict:
    from api.services.demo_seed import seed_full_demo
    return seed_full_demo(db)
