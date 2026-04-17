"""Unit tests for api/services/deal_service.py — DealService.

Mocked DB; covers stage CRUD, deal CRUD, stage transitions, and the
audit-log calls. Tests are paranoid about firm_id scoping because the
plan flagged this as a load-bearing tenant boundary.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from api.db import Deal, PipelineStage, PipelineStageKind
from api.domain.exceptions import NotFoundError
from api.schemas import (
    DealCreate,
    DealUpdate,
    PipelineStageCreate,
    PipelineStageUpdate,
)
from api.services.deal_service import DealService


# ── helpers ───────────────────────────────────────────────────────────────────


def _mock_db():
    return MagicMock()


def _mock_stage(stage_id=1, firm_id=10, kind=PipelineStageKind.lead, name="Lead"):
    s = MagicMock(spec=PipelineStage)
    s.id = stage_id
    s.firm_id = firm_id
    s.kind = kind
    s.name = name
    s.order_index = 0
    s.color = None
    s.created_at = datetime.now(timezone.utc)
    return s


def _mock_deal(deal_id=1, firm_id=10, stage_id=1, orgnr="123456789"):
    d = MagicMock(spec=Deal)
    d.id = deal_id
    d.firm_id = firm_id
    d.orgnr = orgnr
    d.stage_id = stage_id
    d.owner_user_id = None
    d.title = "Q3 renewal"
    d.expected_premium_nok = 100_000
    d.expected_close_date = None
    d.source = None
    d.notes = None
    d.created_at = datetime.now(timezone.utc)
    d.updated_at = datetime.now(timezone.utc)
    d.won_at = None
    d.lost_at = None
    d.lost_reason = None
    return d


def _stage_filter_returns(db, stage):
    """Wire db.query(PipelineStage).filter(...).first() to return `stage`."""
    db.query.return_value.filter.return_value.first.return_value = stage


# ── list_stages ───────────────────────────────────────────────────────────────


def test_list_stages_filters_by_firm():
    db = _mock_db()
    stages = [_mock_stage(1), _mock_stage(2)]
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
        stages
    )
    result = DealService(db).list_stages(firm_id=10)
    assert result == stages


# ── create_stage ──────────────────────────────────────────────────────────────


def test_create_stage_persists_with_audit():
    db = _mock_db()
    body = PipelineStageCreate(name="Lead", kind="lead", order_index=0, color="#94A3B8")
    with patch("api.services.deal_service.log_audit") as mock_audit:
        stage = DealService(db).create_stage(
            firm_id=10, body=body, actor_email="b@x.no"
        )
    assert stage.firm_id == 10
    assert stage.name == "Lead"
    assert stage.kind == PipelineStageKind.lead
    db.add.assert_called_once()
    db.commit.assert_called_once()
    mock_audit.assert_called_once()
    assert mock_audit.call_args.args[1] == "pipeline_stage.create"


def test_create_stage_rejects_unknown_kind():
    db = _mock_db()
    # Pydantic literal type already blocks "bogus" at construction; bypass
    # to simulate hand-crafted payload reaching the service.
    body = SimpleNamespace(name="X", kind="bogus", order_index=0, color=None)
    with pytest.raises(NotFoundError):
        DealService(db).create_stage(firm_id=10, body=body, actor_email="b@x.no")


# ── update_stage ──────────────────────────────────────────────────────────────


def test_update_stage_renames():
    db = _mock_db()
    stage = _mock_stage(stage_id=5, firm_id=10, name="Old")
    _stage_filter_returns(db, stage)
    body = PipelineStageUpdate(name="New name")
    with patch("api.services.deal_service.log_audit"):
        result = DealService(db).update_stage(5, 10, body, actor_email="b@x.no")
    assert result.name == "New name"


def test_update_stage_404_when_other_firm():
    db = _mock_db()
    _stage_filter_returns(db, None)
    with pytest.raises(NotFoundError):
        DealService(db).update_stage(
            5, 10, PipelineStageUpdate(name="X"), actor_email="b@x.no"
        )


# ── delete_stage ──────────────────────────────────────────────────────────────


def test_delete_stage_blocks_when_deals_remain():
    db = _mock_db()
    stage = _mock_stage(stage_id=5, firm_id=10)
    # First .filter() call resolves the stage; second resolves the deal count.
    db.query.return_value.filter.return_value.first.return_value = stage
    db.query.return_value.filter.return_value.count.return_value = 3
    with pytest.raises(NotFoundError, match="still has 3"):
        DealService(db).delete_stage(5, 10, actor_email="b@x.no")
    db.delete.assert_not_called()


def test_delete_stage_succeeds_when_empty():
    db = _mock_db()
    stage = _mock_stage(stage_id=5, firm_id=10)
    db.query.return_value.filter.return_value.first.return_value = stage
    db.query.return_value.filter.return_value.count.return_value = 0
    with patch("api.services.deal_service.log_audit"):
        DealService(db).delete_stage(5, 10, actor_email="b@x.no")
    db.delete.assert_called_once_with(stage)


# ── list_deals ────────────────────────────────────────────────────────────────


def test_list_deals_scopes_to_firm_only():
    db = _mock_db()
    deals = [_mock_deal(1), _mock_deal(2)]
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
        deals
    )
    result = DealService(db).list_deals(firm_id=10)
    assert result == deals


def test_list_deals_with_stage_filter_chains():
    db = _mock_db()
    chain = db.query.return_value.filter.return_value
    chain.filter.return_value.order_by.return_value.all.return_value = []
    DealService(db).list_deals(firm_id=10, stage_id=3)
    # The 2nd .filter() call (stage_id) chained off the firm_id filter.
    chain.filter.assert_called()


# ── create_deal ───────────────────────────────────────────────────────────────


def test_create_deal_validates_stage_belongs_to_firm():
    db = _mock_db()
    _stage_filter_returns(db, None)  # cross-firm stage_id → 404
    body = DealCreate(orgnr="123456789", stage_id=99)
    with pytest.raises(NotFoundError):
        DealService(db).create_deal(firm_id=10, body=body, actor_email="b@x.no")


def test_create_deal_persists_and_audits():
    db = _mock_db()
    stage = _mock_stage(stage_id=1, firm_id=10)
    _stage_filter_returns(db, stage)
    body = DealCreate(
        orgnr="123456789", stage_id=1, title="Q3", expected_premium_nok=50_000
    )
    with patch("api.services.deal_service.log_audit") as mock_audit:
        deal = DealService(db).create_deal(firm_id=10, body=body, actor_email="b@x.no")
    assert deal.firm_id == 10
    assert deal.orgnr == "123456789"
    assert deal.title == "Q3"
    db.add.assert_called_once()
    db.commit.assert_called_once()
    mock_audit.assert_called_once()
    assert mock_audit.call_args.args[1] == "deal.create"


# ── update_deal ───────────────────────────────────────────────────────────────


def test_update_deal_404_when_cross_firm():
    db = _mock_db()
    _stage_filter_returns(db, None)
    with pytest.raises(NotFoundError):
        DealService(db).update_deal(1, 10, DealUpdate(title="x"), actor_email="b@x.no")


def test_update_deal_applies_only_set_fields():
    db = _mock_db()
    deal = _mock_deal(deal_id=1, firm_id=10)
    deal.notes = "original"
    _stage_filter_returns(db, deal)
    body = DealUpdate(title="New title")  # notes stays None → should NOT clear
    with patch("api.services.deal_service.log_audit"):
        result = DealService(db).update_deal(1, 10, body, actor_email="b@x.no")
    assert result.title == "New title"
    assert result.notes == "original"


# ── move_to_stage ─────────────────────────────────────────────────────────────


def test_move_to_stage_changes_stage_id_and_audits():
    db = _mock_db()
    deal = _mock_deal(deal_id=1, firm_id=10, stage_id=1)
    new_stage = _mock_stage(stage_id=2, firm_id=10, kind=PipelineStageKind.quoted)
    db.query.return_value.filter.return_value.first.side_effect = [deal, new_stage]
    with patch("api.services.deal_service.log_audit") as mock_audit:
        result = DealService(db).move_to_stage(
            1, 10, new_stage_id=2, actor_email="b@x.no"
        )
    assert result.stage_id == 2
    mock_audit.assert_called_once()
    assert mock_audit.call_args.args[1] == "deal.stage_change"


def test_move_to_won_stage_sets_won_at():
    db = _mock_db()
    deal = _mock_deal(deal_id=1, firm_id=10)
    won_stage = _mock_stage(
        stage_id=5, firm_id=10, kind=PipelineStageKind.won, name="Bundet"
    )
    db.query.return_value.filter.return_value.first.side_effect = [deal, won_stage]
    with patch("api.services.deal_service.log_audit"):
        result = DealService(db).move_to_stage(
            1, 10, new_stage_id=5, actor_email="b@x.no"
        )
    assert result.won_at is not None


def test_move_to_lost_stage_sets_lost_at():
    db = _mock_db()
    deal = _mock_deal(deal_id=1, firm_id=10)
    lost_stage = _mock_stage(
        stage_id=6, firm_id=10, kind=PipelineStageKind.lost, name="Tapt"
    )
    db.query.return_value.filter.return_value.first.side_effect = [deal, lost_stage]
    with patch("api.services.deal_service.log_audit"):
        result = DealService(db).move_to_stage(
            1, 10, new_stage_id=6, actor_email="b@x.no"
        )
    assert result.lost_at is not None


# ── lose_deal ─────────────────────────────────────────────────────────────────


def test_lose_deal_records_reason_and_moves_to_lost_stage_when_present():
    db = _mock_db()
    deal = _mock_deal(deal_id=1, firm_id=10, stage_id=2)
    lost_stage = _mock_stage(
        stage_id=99, firm_id=10, kind=PipelineStageKind.lost, name="Tapt"
    )
    # First .first() resolves the deal; second resolves the lost stage lookup.
    db.query.return_value.filter.return_value.first.side_effect = [deal, lost_stage]
    with patch("api.services.deal_service.log_audit") as mock_audit:
        result = DealService(db).lose_deal(
            1,
            10,
            reason="Picked competitor",
            actor_email="b@x.no",
        )
    assert result.lost_reason == "Picked competitor"
    assert result.lost_at is not None
    assert result.stage_id == 99
    assert mock_audit.call_args.args[1] == "deal.lose"


def test_lose_deal_keeps_stage_when_no_lost_column():
    db = _mock_db()
    deal = _mock_deal(deal_id=1, firm_id=10, stage_id=2)
    db.query.return_value.filter.return_value.first.side_effect = [deal, None]
    with patch("api.services.deal_service.log_audit"):
        result = DealService(db).lose_deal(1, 10, reason=None, actor_email="b@x.no")
    assert result.stage_id == 2  # unchanged
    assert result.lost_at is not None


# ── delete_deal ───────────────────────────────────────────────────────────────


def test_delete_deal_404_when_cross_firm():
    db = _mock_db()
    _stage_filter_returns(db, None)
    with pytest.raises(NotFoundError):
        DealService(db).delete_deal(1, 10, actor_email="b@x.no")


def test_delete_deal_audits_after_delete():
    db = _mock_db()
    deal = _mock_deal(deal_id=1, firm_id=10)
    _stage_filter_returns(db, deal)
    with patch("api.services.deal_service.log_audit") as mock_audit:
        DealService(db).delete_deal(1, 10, actor_email="b@x.no")
    db.delete.assert_called_once_with(deal)
    assert mock_audit.call_args.args[1] == "deal.delete"
