"""Deal pipeline service — kanban-board CRUD + stage transitions.

Plan §🟢 #9. Every state-changing call writes an audit log entry so we have
a Finanstilsynet-grade trail of who moved which deal where, and when.
"""
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from api.db import Deal, PipelineStage, PipelineStageKind
from api.domain.exceptions import NotFoundError
from api.schemas import (
    DealCreate,
    DealUpdate,
    PipelineStageCreate,
    PipelineStageUpdate,
)
from api.services.audit import log_audit
import logging

logger = logging.getLogger(__name__)



class DealService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Pipeline stages ──────────────────────────────────────────────────────

    def list_stages(self, firm_id: int) -> List[PipelineStage]:
        return (
            self.db.query(PipelineStage)
            .filter(PipelineStage.firm_id == firm_id)
            .order_by(PipelineStage.order_index.asc(), PipelineStage.id.asc())
            .all()
        )

    def create_stage(
        self,
        firm_id: int,
        body: PipelineStageCreate,
        actor_email: str,
    ) -> PipelineStage:
        try:
            kind_enum = PipelineStageKind(body.kind)
        except ValueError as exc:
            raise NotFoundError(f"Unknown pipeline stage kind: {body.kind}") from exc
        stage = PipelineStage(
            firm_id=firm_id,
            name=body.name,
            kind=kind_enum,
            order_index=body.order_index,
            color=body.color,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(stage)
        try:
            self.db.commit()
            self.db.refresh(stage)
        except Exception:
            self.db.rollback()
            raise
        log_audit(
            self.db,
            "pipeline_stage.create",
            actor_email=actor_email,
            detail={"stage_id": stage.id, "name": stage.name, "kind": stage.kind.value},
        )
        return stage

    def update_stage(
        self,
        stage_id: int,
        firm_id: int,
        body: PipelineStageUpdate,
        actor_email: str,
    ) -> PipelineStage:
        stage = self._get_stage_or_raise(stage_id, firm_id)
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(stage, field, value)
        try:
            self.db.commit()
            self.db.refresh(stage)
        except Exception:
            self.db.rollback()
            raise
        log_audit(
            self.db,
            "pipeline_stage.update",
            actor_email=actor_email,
            detail={"stage_id": stage_id},
        )
        return stage

    def delete_stage(self, stage_id: int, firm_id: int, actor_email: str) -> None:
        stage = self._get_stage_or_raise(stage_id, firm_id)
        # Block deletion if any deal still references this stage. ondelete=RESTRICT
        # would raise an opaque IntegrityError; this gives a clean 4xx instead.
        in_use = (
            self.db.query(Deal)
            .filter(Deal.stage_id == stage_id, Deal.firm_id == firm_id)
            .count()
        )
        if in_use:
            raise NotFoundError(
                f"Stage {stage_id} still has {in_use} deal(s) — reassign or close them first."
            )
        self.db.delete(stage)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        log_audit(
            self.db,
            "pipeline_stage.delete",
            actor_email=actor_email,
            detail={"stage_id": stage_id},
        )

    # ── Deals ────────────────────────────────────────────────────────────────

    def list_deals(
        self,
        firm_id: int,
        stage_id: Optional[int] = None,
        owner_user_id: Optional[int] = None,
        orgnr: Optional[str] = None,
    ) -> List[Deal]:
        q = self.db.query(Deal).filter(Deal.firm_id == firm_id)
        if stage_id is not None:
            q = q.filter(Deal.stage_id == stage_id)
        if owner_user_id is not None:
            q = q.filter(Deal.owner_user_id == owner_user_id)
        if orgnr:
            q = q.filter(Deal.orgnr == orgnr)
        return q.order_by(Deal.updated_at.desc()).all()

    def create_deal(
        self,
        firm_id: int,
        body: DealCreate,
        actor_email: str,
    ) -> Deal:
        # Validate the target stage belongs to the caller's firm so a malicious
        # client can't move their deals into another firm's pipeline.
        self._get_stage_or_raise(body.stage_id, firm_id)
        now = datetime.now(timezone.utc)
        deal = Deal(
            firm_id=firm_id,
            orgnr=body.orgnr,
            stage_id=body.stage_id,
            owner_user_id=body.owner_user_id,
            title=body.title,
            expected_premium_nok=body.expected_premium_nok,
            expected_close_date=body.expected_close_date,
            source=body.source,
            notes=body.notes,
            created_at=now,
            updated_at=now,
        )
        self.db.add(deal)
        try:
            self.db.commit()
            self.db.refresh(deal)
        except Exception:
            self.db.rollback()
            raise
        log_audit(
            self.db,
            "deal.create",
            orgnr=deal.orgnr,
            actor_email=actor_email,
            detail={"deal_id": deal.id, "stage_id": deal.stage_id, "title": deal.title},
        )
        return deal

    def update_deal(
        self,
        deal_id: int,
        firm_id: int,
        body: DealUpdate,
        actor_email: str,
    ) -> Deal:
        deal = self._get_deal_or_raise(deal_id, firm_id)
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(deal, field, value)
        deal.updated_at = datetime.now(timezone.utc)
        try:
            self.db.commit()
            self.db.refresh(deal)
        except Exception:
            self.db.rollback()
            raise
        log_audit(
            self.db,
            "deal.update",
            orgnr=deal.orgnr,
            actor_email=actor_email,
            detail={"deal_id": deal_id},
        )
        return deal

    def move_to_stage(
        self,
        deal_id: int,
        firm_id: int,
        new_stage_id: int,
        actor_email: str,
    ) -> Deal:
        deal = self._get_deal_or_raise(deal_id, firm_id)
        new_stage = self._get_stage_or_raise(new_stage_id, firm_id)
        old_stage_id = deal.stage_id
        deal.stage_id = new_stage_id
        deal.updated_at = datetime.now(timezone.utc)
        # Stage kind drives auto-timestamps for won/lost so analytics don't
        # need to inspect the audit log.
        if new_stage.kind == PipelineStageKind.won and deal.won_at is None:
            deal.won_at = datetime.now(timezone.utc)
        if new_stage.kind == PipelineStageKind.lost and deal.lost_at is None:
            deal.lost_at = datetime.now(timezone.utc)
        try:
            self.db.commit()
            self.db.refresh(deal)
        except Exception:
            self.db.rollback()
            raise
        log_audit(
            self.db,
            "deal.stage_change",
            orgnr=deal.orgnr,
            actor_email=actor_email,
            detail={
                "deal_id": deal_id,
                "from_stage_id": old_stage_id,
                "to_stage_id": new_stage_id,
                "to_kind": new_stage.kind.value,
            },
        )
        return deal

    def lose_deal(
        self,
        deal_id: int,
        firm_id: int,
        reason: Optional[str],
        actor_email: str,
    ) -> Deal:
        deal = self._get_deal_or_raise(deal_id, firm_id)
        deal.lost_at = datetime.now(timezone.utc)
        deal.lost_reason = reason
        deal.updated_at = datetime.now(timezone.utc)
        # Move to a "lost" stage if one exists in this firm's pipeline. We
        # don't auto-create one — pipelines without an explicit lost column
        # just keep the deal in its current stage with lost_at set.
        lost_stage = (
            self.db.query(PipelineStage)
            .filter(
                PipelineStage.firm_id == firm_id,
                PipelineStage.kind == PipelineStageKind.lost,
            )
            .first()
        )
        if lost_stage:
            deal.stage_id = lost_stage.id
        try:
            self.db.commit()
            self.db.refresh(deal)
        except Exception:
            self.db.rollback()
            raise
        log_audit(
            self.db,
            "deal.lose",
            orgnr=deal.orgnr,
            actor_email=actor_email,
            detail={"deal_id": deal_id, "reason": reason},
        )
        return deal

    def delete_deal(self, deal_id: int, firm_id: int, actor_email: str) -> None:
        deal = self._get_deal_or_raise(deal_id, firm_id)
        orgnr = deal.orgnr
        self.db.delete(deal)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        log_audit(
            self.db,
            "deal.delete",
            orgnr=orgnr,
            actor_email=actor_email,
            detail={"deal_id": deal_id},
        )

    # ── Internals ────────────────────────────────────────────────────────────

    def _get_stage_or_raise(self, stage_id: int, firm_id: int) -> PipelineStage:
        stage = (
            self.db.query(PipelineStage)
            .filter(PipelineStage.id == stage_id, PipelineStage.firm_id == firm_id)
            .first()
        )
        if not stage:
            raise NotFoundError(f"Pipeline stage {stage_id} not found")
        return stage

    def _get_deal_or_raise(self, deal_id: int, firm_id: int) -> Deal:
        deal = (
            self.db.query(Deal)
            .filter(Deal.id == deal_id, Deal.firm_id == firm_id)
            .first()
        )
        if not deal:
            raise NotFoundError(f"Deal {deal_id} not found")
        return deal
