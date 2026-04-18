"""Deal pipeline endpoints — kanban CRUD + stage transitions.

Plan §🟢 #9. Every endpoint declares response_model so the api-types-fresh
CI gate locks the contract end-to-end. Audit logging happens inside the
service so the audit trail can't be skipped by adding a new caller.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.dependencies import get_db
from api.domain.exceptions import NotFoundError
from api.schemas import (
    DealCreate,
    DealLose,
    DealOut,
    DealStageChange,
    DealUpdate,
    PipelineStageCreate,
    PipelineStageOut,
    PipelineStageUpdate,
)
from api.services.audit import log_audit
from api.services.deal_service import DealService

router = APIRouter()


def _svc(db: Session = Depends(get_db)) -> DealService:
    return DealService(db)


def _serialize_stage(s) -> dict:
    return {
        "id": s.id,
        "firm_id": s.firm_id,
        "name": s.name,
        "kind": s.kind.value,
        "order_index": s.order_index,
        "color": s.color,
        "created_at": s.created_at,
    }


def _serialize_deal(d) -> dict:
    return {
        "id": d.id,
        "firm_id": d.firm_id,
        "orgnr": d.orgnr,
        "stage_id": d.stage_id,
        "owner_user_id": d.owner_user_id,
        "title": d.title,
        "expected_premium_nok": d.expected_premium_nok,
        "expected_close_date": d.expected_close_date,
        "source": d.source,
        "notes": d.notes,
        "created_at": d.created_at,
        "updated_at": d.updated_at,
        "won_at": d.won_at,
        "lost_at": d.lost_at,
        "lost_reason": d.lost_reason,
    }


# ── Pipeline stages ──────────────────────────────────────────────────────────


@router.get("/pipeline/stages", response_model=List[PipelineStageOut])
def list_stages(
    svc: DealService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    return [_serialize_stage(s) for s in svc.list_stages(user.firm_id)]


@router.post("/pipeline/stages", response_model=PipelineStageOut, status_code=201)
def create_stage(
    body: PipelineStageCreate,
    db: Session = Depends(get_db),
    svc: DealService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    try:
        stage = svc.create_stage(user.firm_id, body, user.email)
    except NotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    log_audit(db, "stage.create", detail={"stage_id": stage.id, "name": body.name})
    return _serialize_stage(stage)


@router.patch("/pipeline/stages/{stage_id}", response_model=PipelineStageOut)
def update_stage(
    stage_id: int,
    body: PipelineStageUpdate,
    db: Session = Depends(get_db),
    svc: DealService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    try:
        stage = svc.update_stage(stage_id, user.firm_id, body, user.email)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    log_audit(db, "stage.update", detail={"stage_id": stage_id})
    return _serialize_stage(stage)


@router.delete("/pipeline/stages/{stage_id}", status_code=204)
def delete_stage(
    stage_id: int,
    db: Session = Depends(get_db),
    svc: DealService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    try:
        svc.delete_stage(stage_id, user.firm_id, user.email)
    except NotFoundError as exc:
        # NotFoundError covers both "doesn't exist" and "still has deals" — the
        # message disambiguates for the caller.
        status = 409 if "still has" in str(exc) else 404
        raise HTTPException(status_code=status, detail=str(exc))
    log_audit(db, "stage.delete", detail={"stage_id": stage_id})


# ── Deals ────────────────────────────────────────────────────────────────────


@router.get("/deals", response_model=List[DealOut])
def list_deals(
    stage_id: Optional[int] = Query(default=None),
    owner_user_id: Optional[int] = Query(default=None),
    orgnr: Optional[str] = Query(default=None),
    svc: DealService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    deals = svc.list_deals(
        firm_id=user.firm_id,
        stage_id=stage_id,
        owner_user_id=owner_user_id,
        orgnr=orgnr,
    )
    return [_serialize_deal(d) for d in deals]


@router.post("/deals", response_model=DealOut, status_code=201)
def create_deal(
    body: DealCreate,
    db: Session = Depends(get_db),
    svc: DealService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    try:
        deal = svc.create_deal(user.firm_id, body, user.email)
    except NotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    log_audit(db, "deal.create", orgnr=body.orgnr, detail={"deal_id": deal.id})
    return _serialize_deal(deal)


@router.patch("/deals/{deal_id}", response_model=DealOut)
def update_deal(
    deal_id: int,
    body: DealUpdate,
    db: Session = Depends(get_db),
    svc: DealService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    try:
        deal = svc.update_deal(deal_id, user.firm_id, body, user.email)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    log_audit(db, "deal.update", orgnr=deal.orgnr, detail={"deal_id": deal_id})
    return _serialize_deal(deal)


@router.patch("/deals/{deal_id}/stage", response_model=DealOut)
def move_deal_stage(
    deal_id: int,
    body: DealStageChange,
    db: Session = Depends(get_db),
    svc: DealService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    try:
        deal = svc.move_to_stage(deal_id, user.firm_id, body.stage_id, user.email)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    log_audit(
        db,
        "deal.move",
        orgnr=deal.orgnr,
        detail={"deal_id": deal_id, "stage_id": body.stage_id},
    )
    return _serialize_deal(deal)


@router.post("/deals/{deal_id}/lose", response_model=DealOut)
def lose_deal(
    deal_id: int,
    body: DealLose,
    db: Session = Depends(get_db),
    svc: DealService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    try:
        deal = svc.lose_deal(deal_id, user.firm_id, body.reason, user.email)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    log_audit(
        db,
        "deal.lose",
        orgnr=deal.orgnr,
        detail={"deal_id": deal_id, "reason": body.reason},
    )
    return _serialize_deal(deal)


@router.delete("/deals/{deal_id}", status_code=204)
def delete_deal(
    deal_id: int,
    db: Session = Depends(get_db),
    svc: DealService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    try:
        svc.delete_deal(deal_id, user.firm_id, user.email)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    log_audit(db, "deal.delete", detail={"deal_id": deal_id})
