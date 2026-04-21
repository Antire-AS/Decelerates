"""Integration sweep — seed two firms with overlapping orgnrs, hit each
authenticated list/detail route as firm A, assert firm B's data never
appears in the response bodies.

This is the runtime complement to `tests/unit/test_firm_id_audit.py` —
the static audit catches most missing filters at parse time, but the
sweep catches bugs that static analysis can't see (join misconfiguration,
eager loading that pulls sibling rows, etc.).
"""

import os
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="set TEST_DATABASE_URL=postgresql://... to run integration tests",
)

_FIRM_A = 99901
_FIRM_B = 99902
_ORGNR = "999111222"
_SECRET_A = "ISOLATION_SECRET_A_98765"
_SECRET_B = "ISOLATION_SECRET_B_12345"


@pytest.fixture
def two_firms_db(test_db):
    """Seed both firms with overlapping data so the sweep has real rows to
    leak. Each secret string is firm-unique; finding firm B's secret in
    firm A's response is a failure."""
    from api.db import (
        BrokerFirm,
        Deal,
        PipelineStage,
        Policy,
        Tender,
        TenderStatus,
    )

    now = datetime.now(timezone.utc)
    for fid in (_FIRM_A, _FIRM_B):
        if not test_db.query(BrokerFirm).filter(BrokerFirm.id == fid).first():
            test_db.add(BrokerFirm(id=fid, name=f"IsoFirm {fid}", created_at=now))
    test_db.commit()

    # Clear prior tenant-isolation fixtures across runs.
    for fid in (_FIRM_A, _FIRM_B):
        test_db.query(Deal).filter(Deal.firm_id == fid).delete()
        test_db.query(PipelineStage).filter(PipelineStage.firm_id == fid).delete()
        test_db.query(Tender).filter(Tender.firm_id == fid).delete()
        test_db.query(Policy).filter(Policy.firm_id == fid).delete()
    test_db.commit()

    # Seed a Tender, PipelineStage, and Deal for each firm — all sharing
    # the same orgnr so orgnr alone cannot discriminate.
    for fid, secret in ((_FIRM_A, _SECRET_A), (_FIRM_B, _SECRET_B)):
        tender = Tender(
            orgnr=_ORGNR,
            firm_id=fid,
            title=secret,
            product_types=["Ansvar"],
            created_at=now,
            status=TenderStatus.draft,
        )
        stage = PipelineStage(
            firm_id=fid,
            name=f"Stage {secret}",
            kind="lead",
            order_index=0,
            created_at=now.isoformat(),
        )
        policy = Policy(
            firm_id=fid,
            orgnr=_ORGNR,
            insurer=secret,
            product_type="Ansvar",
            policy_number=secret,
            start_date=date.today(),
            renewal_date=date.today() + timedelta(days=60),
            coverage_amount_nok=1_000_000,
            annual_premium_nok=10_000,
            status="active",
            created_at=now,
            updated_at=now,
        )
        test_db.add_all([tender, stage, policy])
    test_db.commit()
    yield test_db


def _client_as_firm(app, firm_id: int) -> TestClient:
    """Build a TestClient that authenticates as a user in `firm_id`."""
    from api.auth import get_current_user
    from tests.integration.conftest import make_user

    user = make_user(f"user{firm_id}@iso.test", f"oid-iso-{firm_id}", firm_id)
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


@pytest.fixture
def app_with_firm_a_db(two_firms_db):
    from api.main import app
    from api.dependencies import get_db

    app.dependency_overrides[get_db] = lambda: two_firms_db
    yield app
    app.dependency_overrides.clear()


# Routes to sweep. Extend as new firm-scoped list endpoints ship.
# Each tuple: (method, path, optional body). All are firm-scoped list
# endpoints — firm A's client must never see firm B's secret in the body.
_ROUTES = [
    ("GET", "/tenders", None),
    ("GET", "/deals", None),
    ("GET", "/pipeline/stages", None),
    ("GET", f"/org/{_ORGNR}/contacts", None),
    ("GET", "/insurance-documents", None),
    ("GET", "/sla/agreements", None),
    ("GET", "/users", None),
    ("GET", "/portfolios", None),
    ("GET", f"/org/{_ORGNR}/claims", None),
    ("GET", f"/org/{_ORGNR}/activities", None),
]


@pytest.mark.parametrize("method,path,body", _ROUTES)
def test_firm_a_cannot_see_firm_b_secrets(app_with_firm_a_db, method, path, body):
    """Hit each firm-scoped list endpoint as firm A and confirm firm B's
    unique secret markers NEVER appear in the response body."""
    client = _client_as_firm(app_with_firm_a_db, _FIRM_A)
    resp = client.request(method, path, json=body)
    # Not all routes exist in every build; 404 is an acceptable outcome.
    # Anything else in the 2xx/4xx range is fine — we only care about the
    # body content.
    assert resp.status_code < 500, f"{path}: unexpected 5xx {resp.status_code}"
    body_text = resp.text
    assert _SECRET_B not in body_text, (
        f"tenant isolation violation on {path}: firm A saw firm B's secret"
    )
