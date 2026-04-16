"""Admin CRUD endpoints — reset, demo seed variants."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from api.limiter import limiter
from api.dependencies import get_db
from api.services.admin_service import AdminService

router = APIRouter()


def _admin_svc(db: Session = Depends(get_db)) -> AdminService:
    return AdminService(db)


@router.delete("/admin/reset")
@limiter.limit("5/hour")
def admin_reset(request: Request, svc: AdminService = Depends(_admin_svc)) -> dict:
    return svc.reset()


@router.post("/admin/demo")
@limiter.limit("10/hour")
def admin_demo(request: Request, svc: AdminService = Depends(_admin_svc)) -> dict:
    return svc.seed_demo()


@router.post("/admin/seed-norway-top100")
@limiter.limit("10/hour")
def admin_seed_norway_top100(request: Request, svc: AdminService = Depends(_admin_svc)) -> dict:
    return svc.seed_norway_top100()


@router.post("/admin/seed-crm-demo")
@limiter.limit("10/hour")
def seed_crm_demo(request: Request, svc: AdminService = Depends(_admin_svc)) -> dict:
    return svc.seed_crm_demo()


@router.post("/admin/seed-demo-documents")
def seed_demo_documents_endpoint(db: Session = Depends(get_db)) -> dict:
    from api.services.demo_documents import seed_demo_documents
    return seed_demo_documents(db)


@router.post("/admin/seed-full-demo")
def seed_full_demo_endpoint(db: Session = Depends(get_db)) -> dict:
    from api.services.demo_seed import seed_full_demo
    return seed_full_demo(db)
