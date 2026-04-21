"""Integration test — Claim lifecycle against real Postgres.

Claim has FK to Policy with ondelete=CASCADE. This test locks in that
behaviour: if someone changes the FK to RESTRICT, broker-side policy
deletes would start rejecting when claims exist, which would silently
break CRM cleanup flows.

Runs only when TEST_DATABASE_URL is set.
"""

import os
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="set TEST_DATABASE_URL=postgresql://... to run integration tests",
)

_FIRM_ID = 88830
_ORGNR = "444555666"


@pytest.fixture
def auth_client(test_db):
    from api.auth import get_current_user
    from api.db import BrokerFirm, Claim, Policy
    from api.dependencies import get_db
    from api.main import app
    from tests.integration.conftest import make_user

    now = datetime.now(timezone.utc)
    if not test_db.query(BrokerFirm).filter(BrokerFirm.id == _FIRM_ID).first():
        test_db.add(
            BrokerFirm(id=_FIRM_ID, name="Claim Lifecycle Firma", created_at=now)
        )
    # Hermetic cleanup: drop any prior policies + claims for this firm.
    test_db.query(Claim).filter(Claim.firm_id == _FIRM_ID).delete()
    test_db.query(Policy).filter(Policy.firm_id == _FIRM_ID).delete()
    test_db.commit()

    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_current_user] = lambda: make_user(
        "claim@lifecycle.test", "oid-claim-lc", _FIRM_ID
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def _create_policy(test_db) -> int:
    """Seed a policy directly via SQLAlchemy — the `/policies` POST route
    carries more validation than the lifecycle test cares about."""
    from api.db import Policy, PolicyStatus

    now = datetime.now(timezone.utc)
    policy = Policy(
        orgnr=_ORGNR,
        firm_id=_FIRM_ID,
        insurer="Testforsikring",
        product_type="Ansvar",
        policy_number="LC-CLM-001",
        start_date=date.today(),
        renewal_date=date.today(),
        coverage_amount_nok=1_000_000,
        annual_premium_nok=10_000,
        status=PolicyStatus.active,
        created_at=now,
        updated_at=now,
    )
    test_db.add(policy)
    test_db.commit()
    test_db.refresh(policy)
    return policy.id


def test_claim_create_read_delete(auth_client, test_db):
    """CRUD roundtrip via the broker-facing claim routes."""
    policy_id = _create_policy(test_db)

    create = auth_client.post(
        f"/org/{_ORGNR}/claims",
        json={
            "policy_id": policy_id,
            "claim_number": "LC-001",
            "description": "Lifecycle test — water damage",
            "estimated_amount_nok": 250_000,
            "status": "open",
        },
    )
    assert create.status_code == 201, create.text
    claim = create.json()
    claim_id = claim["id"]
    assert claim["policy_id"] == policy_id
    assert claim["status"] == "open"

    listing = auth_client.get(f"/org/{_ORGNR}/claims")
    assert listing.status_code == 200
    ids = [c["id"] for c in listing.json()]
    assert claim_id in ids

    delete = auth_client.delete(f"/org/{_ORGNR}/claims/{claim_id}")
    assert delete.status_code == 204


def test_policy_delete_cascades_to_claims(auth_client, test_db):
    """The Claim.policy_id FK has `ondelete=CASCADE`. Deleting the parent
    Policy must remove its Claim children — or CRM cleanup flows would
    leave orphan rows.

    Seeds a policy + 2 claims directly via the ORM (policy-delete route
    may not exist at all test firms' routers), then deletes the policy
    and verifies the cascade fired."""
    from api.db import Claim, ClaimStatus, Policy

    policy_id = _create_policy(test_db)
    now = datetime.now(timezone.utc)
    for n in ("SKD-A", "SKD-B"):
        test_db.add(
            Claim(
                policy_id=policy_id,
                orgnr=_ORGNR,
                firm_id=_FIRM_ID,
                claim_number=n,
                status=ClaimStatus.open,
                description=f"Cascade test {n}",
                created_at=now,
                updated_at=now,
            )
        )
    test_db.commit()

    pre = test_db.query(Claim).filter(Claim.policy_id == policy_id).count()
    assert pre == 2

    test_db.query(Policy).filter(Policy.id == policy_id).delete()
    test_db.commit()

    test_db.expire_all()
    post = test_db.query(Claim).filter(Claim.policy_id == policy_id).count()
    assert post == 0, (
        f"Expected FK cascade to delete claims when policy deleted, found {post} orphans. "
        "Check Claim.policy_id ondelete=CASCADE in api/models/crm.py."
    )
