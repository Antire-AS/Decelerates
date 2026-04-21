"""Integration test — full tender (anbud) lifecycle against a real Postgres.

Covers the workflow from broker creating a draft tender through inviting
recipients and checking the final status. Real Postgres catches: FK
cascade deletes, unique constraints on access tokens, JSON column quirks,
transaction boundaries — all things the MagicMock-DB unit tests skip.

Runs only when TEST_DATABASE_URL is set.
"""

import os
from datetime import date, datetime, timezone

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="set TEST_DATABASE_URL=postgresql://... to run integration tests",
)

_FIRM_ID = 88800
_ORGNR = "555000999"


@pytest.fixture
def auth_client(test_db):
    from fastapi.testclient import TestClient
    from api.main import app
    from api.auth import get_current_user
    from api.dependencies import get_db
    from api.db import BrokerFirm, Tender, TenderRecipient, TenderOffer
    from tests.integration.conftest import make_user

    # Seed firm + clear any prior tender state for this firm.
    now = datetime.now(timezone.utc)
    if not test_db.query(BrokerFirm).filter(BrokerFirm.id == _FIRM_ID).first():
        test_db.add(
            BrokerFirm(id=_FIRM_ID, name="Tender Lifecycle Firma", created_at=now)
        )
    # Cascade deletes would miss if we skip this prior-state cleanup.
    tender_ids = [
        t.id for t in test_db.query(Tender).filter(Tender.firm_id == _FIRM_ID).all()
    ]
    for tid in tender_ids:
        test_db.query(TenderOffer).filter(TenderOffer.tender_id == tid).delete()
        test_db.query(TenderRecipient).filter(TenderRecipient.tender_id == tid).delete()
    test_db.query(Tender).filter(Tender.firm_id == _FIRM_ID).delete()
    test_db.commit()

    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_current_user] = lambda: make_user(
        "lifecycle@tender.test", "oid-tender-lc", _FIRM_ID
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_tender_create_then_read_then_delete(auth_client):
    """Create → GET → GET list → DELETE → 404. Exercises the write/read
    cycle against a real Postgres, including the JSON product_types column
    and the Tender→TenderRecipient FK."""
    resp = auth_client.post(
        "/tenders",
        json={
            "orgnr": _ORGNR,
            "title": "Lifecycle smoke",
            "product_types": ["Ansvar", "Eiendom"],
            "recipients": [
                {"insurer_name": "If", "insurer_email": "if@test.no"},
                {"insurer_name": "Gjensidige"},
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    tender = resp.json()
    tender_id = tender["id"]
    assert tender["title"] == "Lifecycle smoke"
    assert tender["product_types"] == ["Ansvar", "Eiendom"]
    assert tender["status"] == "draft"

    # GET detail
    detail = auth_client.get(f"/tenders/{tender_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == tender_id
    # Detail view also returns recipients + offers (JSON-column roundtrip).
    assert len(detail.json().get("recipients", [])) == 2

    # LIST includes the new tender
    listing = auth_client.get("/tenders")
    assert listing.status_code == 200
    ids = [t["id"] for t in listing.json()]
    assert tender_id in ids

    # DELETE → 204-or-OK, then GET is 404
    del_resp = auth_client.delete(f"/tenders/{tender_id}")
    assert del_resp.status_code < 400
    missing = auth_client.get(f"/tenders/{tender_id}")
    assert missing.status_code == 404


def test_tender_recipients_cascade_delete(auth_client, test_db):
    """Deleting a Tender must cascade-delete its TenderRecipient rows (the
    FK is declared with ondelete=CASCADE). Without the real-DB test we'd
    have no coverage for the cascade behavior."""
    from api.db import TenderRecipient

    resp = auth_client.post(
        "/tenders",
        json={
            "orgnr": _ORGNR,
            "title": "Cascade check",
            "product_types": ["Cyber"],
            "recipients": [
                {"insurer_name": "Tryg"},
                {"insurer_name": "Fremtind"},
                {"insurer_name": "Codan"},
            ],
        },
    )
    assert resp.status_code == 200
    tender_id = resp.json()["id"]

    # Verify recipients landed in the DB.
    pre = (
        test_db.query(TenderRecipient)
        .filter(TenderRecipient.tender_id == tender_id)
        .count()
    )
    assert pre == 3

    auth_client.delete(f"/tenders/{tender_id}")

    # After the Tender delete, the 3 recipient rows must be gone.
    test_db.expire_all()  # force a fresh read through the session
    post = (
        test_db.query(TenderRecipient)
        .filter(TenderRecipient.tender_id == tender_id)
        .count()
    )
    assert post == 0, (
        f"FK cascade didn't fire — {post} orphan recipient rows remain. "
        "Check the ondelete=CASCADE on TenderRecipient.tender_id."
    )


def test_tender_status_defaults_to_draft_on_create(auth_client):
    """A freshly created tender is status=draft until send-invitations runs.
    This is the contract the `/tenders` list filter and the frontend badge
    both depend on."""
    resp = auth_client.post(
        "/tenders",
        json={
            "orgnr": _ORGNR,
            "title": "Draft status",
            "product_types": ["Ansvar"],
            "recipients": [{"insurer_name": "If"}],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "draft"


def test_tender_with_deadline_roundtrips_iso_date(auth_client):
    """Tender.deadline is a DATE column. Verify it survives JSON → Pydantic
    → SQLAlchemy → Postgres → back with the correct ISO format (no TZ
    clipping, no off-by-one)."""
    deadline_iso = date.today().isoformat()
    resp = auth_client.post(
        "/tenders",
        json={
            "orgnr": _ORGNR,
            "title": "Deadline roundtrip",
            "product_types": ["Ansvar"],
            "deadline": deadline_iso,
            "recipients": [],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["deadline"] == deadline_iso
