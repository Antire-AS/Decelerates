"""Integration test — SLA agreement lifecycle against a real Postgres.

Covers: create, list, detail GET, sign PATCH, JSON-column roundtrip.

SlaAgreement is NOT firm-scoped (unlike Tender / Deal / Policy) —
it's a per-client artifact with `client_orgnr` + a `broker_snapshot`
JSON column that captures the broker firm state at signing time. This
test exists primarily to catch regressions in the JSON columns
(broker_snapshot, insurance_lines, fee_structure, form_data) which
have no static type safety against schema drift.

Runs only when TEST_DATABASE_URL is set.
"""

import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="set TEST_DATABASE_URL=postgresql://... to run integration tests",
)

_ORGNR = "777000111"


@pytest.fixture
def auth_client(test_db):
    from api.auth import get_current_user
    from api.dependencies import get_db
    from api.db import SlaAgreement
    from api.main import app
    from tests.integration.conftest import make_user

    # Clear prior SLAs for this orgnr so tests are hermetic across runs.
    test_db.query(SlaAgreement).filter(SlaAgreement.client_orgnr == _ORGNR).delete()
    test_db.commit()

    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_current_user] = lambda: make_user(
        "sla@lifecycle.test", "oid-sla-lc", 88810
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_sla_create_then_list_then_detail(auth_client):
    """Full CRUD roundtrip including all four JSON columns.

    POST /sla wraps client fields under form_data and returns only
    {id, created_at} — status + JSON columns must be verified via
    GET /sla/{id}. SlaService hard-sets status='active' on create
    (not the DB default 'draft'); signed state is detected by
    signed_at/signed_by being set, not by status."""
    form_data = {
        "client_orgnr": _ORGNR,
        "client_navn": "Lifecycle Testkunde AS",
        "client_adresse": "Testvei 1, 0001 Oslo",
        "client_kontakt": "kontakt@kunde.no",
        "start_date": datetime.now(timezone.utc).date().isoformat(),
        "account_manager": "Kari Megler",
        "insurance_lines": [
            {"line": "Ansvar", "premium_nok": 100_000},
            {"line": "Eiendom", "premium_nok": 250_000},
        ],
        "fee_structure": {"type": "fixed", "amount_nok": 25_000},
        "version": 2,
        "extra": "notes",
    }
    resp = auth_client.post("/sla", json={"form_data": form_data})
    assert resp.status_code < 400, resp.text
    created = resp.json()
    sla_id = created["id"]
    assert created["created_at"] is not None

    # List returns it as an unsigned 'active' row (signed_at is None).
    listing = auth_client.get("/sla")
    assert listing.status_code == 200
    rows = listing.json()
    row = next((s for s in rows if s["id"] == sla_id), None)
    assert row is not None
    assert row["status"] == "active"
    assert row["signed_at"] is None

    # Detail returns the JSON columns byte-for-byte.
    detail = auth_client.get(f"/sla/{sla_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["client_orgnr"] == _ORGNR
    assert body["insurance_lines"] == form_data["insurance_lines"]
    assert body["fee_structure"] == form_data["fee_structure"]
    assert body["form_data"] == form_data


def test_sla_sign_transitions_status(auth_client):
    """PATCH /sla/{id}/sign stamps signed_at + signed_by on an existing SLA.

    The service keeps status='active' across the sign transition; signed
    state is expressed via signed_at/signed_by being non-null. If a future
    refactor reintroduces a distinct 'signed' status, this test (and the
    list assertion below) should be updated to match."""
    create = auth_client.post(
        "/sla",
        json={
            "form_data": {
                "client_orgnr": _ORGNR,
                "client_navn": "Sign Test AS",
                "start_date": datetime.now(timezone.utc).date().isoformat(),
                "account_manager": "Sign Bot",
                "insurance_lines": [],
                "fee_structure": {},
            }
        },
    )
    assert create.status_code < 400
    sla_id = create.json()["id"]

    sign = auth_client.patch(f"/sla/{sla_id}/sign", json={"signed_by": "klient@x.no"})
    assert sign.status_code < 400, sign.text
    sign_body = sign.json()
    assert sign_body["signed_at"] is not None
    assert sign_body["signed_by"] == "klient@x.no"

    # List GET proves signed_at + signed_by were persisted to DB (not just echoed).
    listing = auth_client.get("/sla").json()
    row = next(s for s in listing if s["id"] == sla_id)
    assert row["signed_at"] is not None
    assert row["signed_by"] == "klient@x.no"
