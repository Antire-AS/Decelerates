"""Integration tests — Deal pipeline CRUD + stage transitions.

Requires TEST_DATABASE_URL. Auth is bypassed via dependency override.
Run:
    TEST_DATABASE_URL=postgresql://... uv run python -m pytest tests/integration/test_deals.py -v
"""

import os
from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="set TEST_DATABASE_URL=postgresql://... to run integration tests",
)

_FIRM_ID = 20
_ORGNR = "888999000"

# ── Shared fixtures ─────────────────────────────────────────────────────────────

from tests.integration.conftest import AuthClient, make_user, resolve_user_factory


@pytest.fixture
def auth_client(test_db):
    from fastapi.testclient import TestClient
    from api.main import app
    from api.auth import get_current_user
    from api.dependencies import get_db

    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_current_user] = resolve_user_factory(
        "deals@firm.no",
        "oid-20",
        _FIRM_ID,
    )
    yield AuthClient(TestClient(app), make_user("deals@firm.no", "oid-20", _FIRM_ID))
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def seed_broker_firm(test_db):
    from api.db import BrokerFirm

    if not test_db.query(BrokerFirm).filter(BrokerFirm.id == _FIRM_ID).first():
        test_db.add(
            BrokerFirm(
                id=_FIRM_ID,
                name="Deal Test Firma AS",
                created_at=datetime.now(timezone.utc),
            )
        )
        test_db.commit()


# ── Pipeline stages ──────────────────────────────────────────────────────────


class TestPipelineStages:
    def test_list_stages_returns_list(self, auth_client):
        resp = auth_client.get("/pipeline/stages")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_stage_returns_201(self, auth_client):
        resp = auth_client.post(
            "/pipeline/stages",
            json={
                "name": "Nytt lead",
                "kind": "lead",
                "order_index": 0,
                "color": "#4A6FA5",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Nytt lead"
        assert data["kind"] == "lead"
        assert data["firm_id"] == _FIRM_ID
        assert data["color"] == "#4A6FA5"

    def test_create_duplicate_name_fails(self, auth_client):
        auth_client.post(
            "/pipeline/stages",
            json={
                "name": "Duplikat",
                "kind": "lead",
                "order_index": 0,
            },
        )
        resp = auth_client.post(
            "/pipeline/stages",
            json={
                "name": "Duplikat",
                "kind": "qualified",
                "order_index": 1,
            },
        )
        # Unique constraint on (firm_id, name) should cause a 400 or 500
        assert resp.status_code >= 400


# ── Deals CRUD ───────────────────────────────────────────────────────────────


def _create_stage(auth_client, name="Test stage", kind="lead") -> int:
    """Helper to create a stage and return its id."""
    resp = auth_client.post(
        "/pipeline/stages",
        json={
            "name": name,
            "kind": kind,
            "order_index": 0,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


class TestDeals:
    def test_create_deal_returns_201(self, auth_client):
        stage_id = _create_stage(auth_client, "Create deal stage")
        resp = auth_client.post(
            "/deals",
            json={
                "orgnr": _ORGNR,
                "stage_id": stage_id,
                "title": "Ny forsikringsdeal",
                "expected_premium_nok": 250_000,
                "source": "Inbound",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["orgnr"] == _ORGNR
        assert data["title"] == "Ny forsikringsdeal"
        assert data["expected_premium_nok"] == 250_000
        assert data["firm_id"] == _FIRM_ID

    def test_list_deals_includes_created(self, auth_client):
        stage_id = _create_stage(auth_client, "List deals stage")
        auth_client.post(
            "/deals",
            json={
                "orgnr": _ORGNR,
                "stage_id": stage_id,
                "title": "Listbar deal",
            },
        )
        resp = auth_client.get("/deals")
        assert resp.status_code == 200
        deals = resp.json()
        assert isinstance(deals, list)
        assert any(d["title"] == "Listbar deal" for d in deals)

    def test_list_deals_filter_by_orgnr(self, auth_client):
        stage_id = _create_stage(auth_client, "Filter stage")
        auth_client.post(
            "/deals",
            json={
                "orgnr": "111222333",
                "stage_id": stage_id,
                "title": "Other org",
            },
        )
        auth_client.post(
            "/deals",
            json={
                "orgnr": _ORGNR,
                "stage_id": stage_id,
                "title": "Target org",
            },
        )
        resp = auth_client.get("/deals", params={"orgnr": _ORGNR})
        assert resp.status_code == 200
        deals = resp.json()
        assert all(d["orgnr"] == _ORGNR for d in deals)

    def test_update_deal(self, auth_client):
        stage_id = _create_stage(auth_client, "Update deal stage")
        deal_id = auth_client.post(
            "/deals",
            json={
                "orgnr": _ORGNR,
                "stage_id": stage_id,
                "title": "Gammel tittel",
            },
        ).json()["id"]

        resp = auth_client.patch(
            f"/deals/{deal_id}",
            json={
                "title": "Ny tittel",
                "notes": "Oppdaterte notater",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Ny tittel"
        assert data["notes"] == "Oppdaterte notater"

    def test_move_deal_to_stage(self, auth_client):
        stage1 = _create_stage(auth_client, "Stage A", "lead")
        stage2 = _create_stage(auth_client, "Stage B", "qualified")
        deal_id = auth_client.post(
            "/deals",
            json={
                "orgnr": _ORGNR,
                "stage_id": stage1,
                "title": "Flyttes",
            },
        ).json()["id"]

        resp = auth_client.patch(
            f"/deals/{deal_id}/stage",
            json={
                "stage_id": stage2,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["stage_id"] == stage2

    def test_lose_deal_sets_lost_fields(self, auth_client):
        stage_id = _create_stage(auth_client, "Lose deal stage")
        deal_id = auth_client.post(
            "/deals",
            json={
                "orgnr": _ORGNR,
                "stage_id": stage_id,
                "title": "Tapt deal",
            },
        ).json()["id"]

        resp = auth_client.post(
            f"/deals/{deal_id}/lose",
            json={
                "reason": "For dyr premie",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["lost_at"] is not None
        assert data["lost_reason"] == "For dyr premie"

    def test_delete_deal(self, auth_client):
        stage_id = _create_stage(auth_client, "Delete deal stage")
        deal_id = auth_client.post(
            "/deals",
            json={
                "orgnr": _ORGNR,
                "stage_id": stage_id,
                "title": "Slettes",
            },
        ).json()["id"]

        resp = auth_client.delete(f"/deals/{deal_id}")
        assert resp.status_code == 204

        # Verify it's gone
        deals = auth_client.get("/deals").json()
        assert all(d["id"] != deal_id for d in deals)

    def test_delete_nonexistent_deal_returns_404(self, auth_client):
        resp = auth_client.delete("/deals/999999")
        assert resp.status_code == 404

    def test_create_deal_with_invalid_stage_returns_400(self, auth_client):
        resp = auth_client.post(
            "/deals",
            json={
                "orgnr": _ORGNR,
                "stage_id": 999999,
                "title": "Bad stage",
            },
        )
        assert resp.status_code == 400
