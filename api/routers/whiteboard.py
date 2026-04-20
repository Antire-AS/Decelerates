"""HTTP endpoints for the per-user, per-company focus whiteboard.

GET    /org/{orgnr}/whiteboard           — load the current user's whiteboard
PUT    /org/{orgnr}/whiteboard           — upsert items + notes
DELETE /org/{orgnr}/whiteboard           — clear
POST   /org/{orgnr}/whiteboard/ai-summary — generate AI sparring summary
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.db import Company
from api.dependencies import get_db
from api.services.whiteboard import WhiteboardService

router = APIRouter()


class WhiteboardItem(BaseModel):
    id: str
    label: str
    value: str
    source_tab: Optional[str] = None


class WhiteboardIn(BaseModel):
    items: list[WhiteboardItem]
    notes: Optional[str] = None


def _svc(db: Session = Depends(get_db)) -> WhiteboardService:
    return WhiteboardService(db)


def _serialise_whiteboard(wb) -> dict:
    return {
        "orgnr": wb.orgnr,
        "items": wb.items or [],
        "notes": wb.notes or "",
        "ai_summary": wb.ai_summary or "",
        "updated_at": wb.updated_at.isoformat() if wb.updated_at else None,
    }


@router.get("/org/{orgnr}/whiteboard")
def get_whiteboard(
    orgnr: str,
    user: CurrentUser = Depends(get_current_user),
    svc: WhiteboardService = Depends(_svc),
) -> dict:
    wb = svc.get(orgnr, user.oid)
    if not wb:
        return {
            "orgnr": orgnr,
            "items": [],
            "notes": "",
            "ai_summary": "",
            "updated_at": None,
        }
    return _serialise_whiteboard(wb)


@router.put("/org/{orgnr}/whiteboard")
def save_whiteboard(
    orgnr: str,
    body: WhiteboardIn,
    user: CurrentUser = Depends(get_current_user),
    svc: WhiteboardService = Depends(_svc),
) -> dict:
    items = [item.model_dump() for item in body.items]
    wb = svc.upsert(orgnr, user.oid, items, body.notes)
    return _serialise_whiteboard(wb)


@router.delete("/org/{orgnr}/whiteboard")
def delete_whiteboard(
    orgnr: str,
    user: CurrentUser = Depends(get_current_user),
    svc: WhiteboardService = Depends(_svc),
) -> dict:
    deleted = svc.delete(orgnr, user.oid)
    return {"deleted": deleted}


@router.post("/org/{orgnr}/whiteboard/ai-summary")
def generate_whiteboard_ai_summary(
    orgnr: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    svc: WhiteboardService = Depends(_svc),
) -> dict:
    company = db.query(Company).filter(Company.orgnr == orgnr).first()
    company_name = company.navn if company else orgnr
    summary = svc.generate_ai_summary(orgnr, user.oid, company_name=company_name)
    if summary is None:
        raise HTTPException(
            status_code=400,
            detail="Whiteboard er tomt eller AI-tjenesten er ikke tilgjengelig akkurat nå.",
        )
    return {"ai_summary": summary}
