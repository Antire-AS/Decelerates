"""Unit tests for api/routers/deals.py — deal pipeline HTTP layer.

Mocks DealService + auth so we exercise the wiring (status codes, response
shapes, validation) without touching the real service or DB.
"""
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Stub heavy transitive deps before any api.* import.
sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.auth import CurrentUser, get_current_user
from api.db import PipelineStageKind
from api.domain.exceptions import NotFoundError
from api.routers.deals import router, _svc
from api.services.deal_service import DealService


# ── App + fixtures ────────────────────────────────────────────────────────────


_app = FastAPI()
_app.include_router(router)


def _mock_user():
    return CurrentUser(email="b@x.no", name="B", oid="oid", firm_id=10)


def _mock_stage(stage_id=1):
    s = MagicMock()
    s.id = stage_id
    s.firm_id = 10
    s.name = "Lead"
    s.kind = PipelineStageKind.lead
    s.order_index = 0
    s.color = "#94A3B8"
    s.created_at = datetime.now(timezone.utc)
    return s


def _mock_deal(deal_id=1, stage_id=1):
    d = MagicMock()
    d.id = deal_id
    d.firm_id = 10
    d.orgnr = "123456789"
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


@pytest.fixture
def mock_svc():
    return MagicMock(spec=DealService)


@pytest.fixture
def client(mock_svc):
    _app.dependency_overrides[_svc] = lambda: mock_svc
    _app.dependency_overrides[get_current_user] = _mock_user
    yield TestClient(_app)
    _app.dependency_overrides.clear()


# ── Pipeline stages ──────────────────────────────────────────────────────────


def test_list_stages_200(client, mock_svc):
    mock_svc.list_stages.return_value = [_mock_stage(1), _mock_stage(2)]
    resp = client.get("/pipeline/stages")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["kind"] == "lead"


def test_list_stages_scoped_to_user_firm(client, mock_svc):
    mock_svc.list_stages.return_value = []
    client.get("/pipeline/stages")
    mock_svc.list_stages.assert_called_once_with(10)


def test_create_stage_201(client, mock_svc):
    mock_svc.create_stage.return_value = _mock_stage(stage_id=99)
    resp = client.post("/pipeline/stages", json={"name": "Lead", "kind": "lead", "order_index": 0})
    assert resp.status_code == 201
    assert resp.json()["id"] == 99


def test_create_stage_400_on_unknown_kind(client, mock_svc):
    # Pydantic literal blocks "bogus" before the service is even called →
    # 422, not 400. Asserting 422 as the actual API contract.
    resp = client.post("/pipeline/stages", json={"name": "X", "kind": "bogus"})
    assert resp.status_code == 422


def test_update_stage_404(client, mock_svc):
    mock_svc.update_stage.side_effect = NotFoundError("stage not found")
    resp = client.patch("/pipeline/stages/99", json={"name": "X"})
    assert resp.status_code == 404


def test_delete_stage_204(client, mock_svc):
    mock_svc.delete_stage.return_value = None
    resp = client.delete("/pipeline/stages/1")
    assert resp.status_code == 204


def test_delete_stage_409_when_deals_remain(client, mock_svc):
    mock_svc.delete_stage.side_effect = NotFoundError("Stage 5 still has 3 deal(s) — reassign")
    resp = client.delete("/pipeline/stages/5")
    assert resp.status_code == 409


def test_delete_stage_404_when_missing(client, mock_svc):
    mock_svc.delete_stage.side_effect = NotFoundError("Pipeline stage 99 not found")
    resp = client.delete("/pipeline/stages/99")
    assert resp.status_code == 404


# ── Deals ────────────────────────────────────────────────────────────────────


def test_list_deals_200_no_filter(client, mock_svc):
    mock_svc.list_deals.return_value = [_mock_deal(1), _mock_deal(2)]
    resp = client.get("/deals")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_deals_passes_query_filters(client, mock_svc):
    mock_svc.list_deals.return_value = []
    client.get("/deals?stage_id=3&owner_user_id=7&orgnr=987654321")
    args = mock_svc.list_deals.call_args.kwargs
    assert args == {"firm_id": 10, "stage_id": 3, "owner_user_id": 7, "orgnr": "987654321"}


def test_create_deal_201(client, mock_svc):
    mock_svc.create_deal.return_value = _mock_deal(deal_id=42)
    resp = client.post("/deals", json={"orgnr": "123456789", "stage_id": 1, "title": "Q3"})
    assert resp.status_code == 201
    assert resp.json()["id"] == 42


def test_create_deal_400_when_stage_invalid(client, mock_svc):
    mock_svc.create_deal.side_effect = NotFoundError("Pipeline stage 999 not found")
    resp = client.post("/deals", json={"orgnr": "123456789", "stage_id": 999})
    assert resp.status_code == 400


def test_update_deal_404(client, mock_svc):
    mock_svc.update_deal.side_effect = NotFoundError("Deal 1 not found")
    resp = client.patch("/deals/1", json={"title": "X"})
    assert resp.status_code == 404


def test_move_deal_stage_200(client, mock_svc):
    mock_svc.move_to_stage.return_value = _mock_deal(deal_id=1, stage_id=2)
    resp = client.patch("/deals/1/stage", json={"stage_id": 2})
    assert resp.status_code == 200
    assert resp.json()["stage_id"] == 2


def test_lose_deal_200_with_reason(client, mock_svc):
    deal = _mock_deal(deal_id=1)
    deal.lost_at = datetime.now(timezone.utc)
    deal.lost_reason = "Picked competitor"
    mock_svc.lose_deal.return_value = deal
    resp = client.post("/deals/1/lose", json={"reason": "Picked competitor"})
    assert resp.status_code == 200
    assert resp.json()["lost_reason"] == "Picked competitor"


def test_lose_deal_200_without_reason(client, mock_svc):
    deal = _mock_deal(deal_id=1)
    deal.lost_at = datetime.now(timezone.utc)
    mock_svc.lose_deal.return_value = deal
    resp = client.post("/deals/1/lose", json={})
    assert resp.status_code == 200


def test_delete_deal_204(client, mock_svc):
    mock_svc.delete_deal.return_value = None
    resp = client.delete("/deals/1")
    assert resp.status_code == 204
