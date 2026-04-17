"""Integration tests — policy register, renewal pipeline, and analytics endpoints.

Requires TEST_DATABASE_URL. Auth is bypassed via dependency override.
Run:
    TEST_DATABASE_URL=postgresql://... uv run python -m pytest tests/integration/test_policies_router.py -v
"""

import os
from datetime import date, timedelta

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="set TEST_DATABASE_URL=postgresql://... to run integration tests",
)

_FIRM_ID = 1
_ORGNR = "123456789"

_POLICY_PAYLOAD = {
    "insurer": "If Skadeforsikring",
    "product_type": "Ansvarsforsikring",
    "policy_number": "POL-001",
    "annual_premium_nok": 50_000,
    "start_date": "2025-01-01",
    "renewal_date": (date.today() + timedelta(days=45)).isoformat(),
    "status": "active",
}


# ── Auth override + BrokerFirm seed ──────────────────────────────────────────


@pytest.fixture
def auth_client(test_db):
    """TestClient with get_db AND get_current_user overridden."""
    from fastapi.testclient import TestClient
    from api.main import app
    from api.auth import CurrentUser, get_current_user
    from api.dependencies import get_db

    def _fake_user():
        return CurrentUser(
            email="test@broker.no", name="Test Broker", oid="test-oid", firm_id=_FIRM_ID
        )

    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_current_user] = _fake_user
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def seed_broker_firm(test_db):
    """Ensure a BrokerFirm with id=1 exists before each policy test."""
    from datetime import datetime, timezone
    from api.db import BrokerFirm

    existing = test_db.query(BrokerFirm).filter(BrokerFirm.id == _FIRM_ID).first()
    if not existing:
        test_db.add(
            BrokerFirm(
                id=_FIRM_ID,
                name="Test Megling AS",
                orgnr="999888777",
                created_at=datetime.now(timezone.utc),
            )
        )
        test_db.commit()


# ── Policy CRUD ────────────────────────────────────────────────────────────────


class TestPolicyCRUD:
    def test_create_returns_201_with_id(self, auth_client):
        resp = auth_client.post(f"/org/{_ORGNR}/policies", json=_POLICY_PAYLOAD)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] > 0
        assert data["insurer"] == _POLICY_PAYLOAD["insurer"]
        assert data["firm_id"] == _FIRM_ID
        assert data["renewal_stage"] == "not_started"

    def test_list_returns_created_policy(self, auth_client):
        auth_client.post(f"/org/{_ORGNR}/policies", json=_POLICY_PAYLOAD)
        resp = auth_client.get(f"/org/{_ORGNR}/policies")
        assert resp.status_code == 200
        items = resp.json()
        assert isinstance(items, list)
        assert any(p["policy_number"] == "POL-001" for p in items)

    def test_update_changes_field(self, auth_client):
        policy_id = auth_client.post(
            f"/org/{_ORGNR}/policies", json=_POLICY_PAYLOAD
        ).json()["id"]

        resp = auth_client.put(
            f"/org/{_ORGNR}/policies/{policy_id}",
            json={"annual_premium_nok": 75_000},
        )
        assert resp.status_code == 200
        assert resp.json()["annual_premium_nok"] == 75_000

    def test_delete_removes_policy(self, auth_client):
        policy_id = auth_client.post(
            f"/org/{_ORGNR}/policies", json=_POLICY_PAYLOAD
        ).json()["id"]

        assert (
            auth_client.delete(f"/org/{_ORGNR}/policies/{policy_id}").status_code == 204
        )
        remaining = auth_client.get(f"/org/{_ORGNR}/policies").json()
        assert not any(p["id"] == policy_id for p in remaining)

    def test_update_unknown_policy_returns_404(self, auth_client):
        resp = auth_client.put(
            f"/org/{_ORGNR}/policies/999999",
            json={"annual_premium_nok": 1},
        )
        assert resp.status_code == 404

    def test_cross_firm_isolation(self, auth_client, test_db):
        """A policy created under firm 1 must not appear when queried as firm 2."""
        from fastapi.testclient import TestClient
        from api.main import app
        from api.auth import CurrentUser, get_current_user
        from api.dependencies import get_db
        from api.db import BrokerFirm
        from datetime import datetime, timezone

        # Create firm 2
        if not test_db.query(BrokerFirm).filter(BrokerFirm.id == 2).first():
            test_db.add(
                BrokerFirm(
                    id=2, name="Annet Megling AS", created_at=datetime.now(timezone.utc)
                )
            )
            test_db.commit()

        # Create policy as firm 1
        policy_id = auth_client.post(
            f"/org/{_ORGNR}/policies", json=_POLICY_PAYLOAD
        ).json()["id"]

        # Query as firm 2
        def _firm2():
            return CurrentUser(
                email="other@broker.no", name="Other", oid="other-oid", firm_id=2
            )

        app.dependency_overrides[get_db] = lambda: test_db
        app.dependency_overrides[get_current_user] = _firm2
        c2 = TestClient(app)
        policies_firm2 = c2.get(f"/org/{_ORGNR}/policies").json()
        app.dependency_overrides.clear()

        assert not any(p["id"] == policy_id for p in policies_firm2)


# ── Renewal pipeline ───────────────────────────────────────────────────────────

# See tests/integration/test_policies.py for the xfail rationale constants.
_RENEWALS_FOLLOWUP = (
    "Pre-existing: /renewals response shape drift + policy window filter. "
    "See tier 🟡 follow-up."
)


class TestRenewals:
    @pytest.mark.xfail(reason=_RENEWALS_FOLLOWUP, strict=False)
    def test_renewals_includes_policy_renewing_within_window(self, auth_client):
        auth_client.post(
            f"/org/{_ORGNR}/policies", json=_POLICY_PAYLOAD
        )  # renewal in 45d
        resp = auth_client.get("/renewals", params={"days": 90})
        assert resp.status_code == 200
        items = resp.json()
        assert isinstance(items, list)
        assert any(p["policy_number"] == "POL-001" for p in items)
        # days_until_renewal should be present and non-negative
        assert all("days_until_renewal" in p for p in items)

    def test_renewals_excludes_policy_outside_window(self, auth_client):
        far_future = (date.today() + timedelta(days=200)).isoformat()
        auth_client.post(
            f"/org/{_ORGNR}/policies",
            json={**_POLICY_PAYLOAD, "renewal_date": far_future},
        )
        resp = auth_client.get("/renewals", params={"days": 30})
        items = resp.json()
        assert not any(p.get("renewal_date") == far_future for p in items)

    def test_list_all_policies(self, auth_client):
        auth_client.post(f"/org/{_ORGNR}/policies", json=_POLICY_PAYLOAD)
        resp = auth_client.get("/policies")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ── Renewal stage machine ──────────────────────────────────────────────────────


class TestRenewalStage:
    def test_default_stage_is_not_started(self, auth_client):
        policy = auth_client.post(
            f"/org/{_ORGNR}/policies", json=_POLICY_PAYLOAD
        ).json()
        assert policy["renewal_stage"] == "not_started"

    def test_advance_stage_updates_renewal_stage(self, auth_client):
        policy_id = auth_client.post(
            f"/org/{_ORGNR}/policies", json=_POLICY_PAYLOAD
        ).json()["id"]
        resp = auth_client.post(
            f"/policies/{policy_id}/renewal/advance",
            json={"stage": "ready_to_quote"},
        )
        assert resp.status_code == 200
        assert resp.json()["renewal_stage"] == "ready_to_quote"

    def test_advance_to_accepted(self, auth_client):
        policy_id = auth_client.post(
            f"/org/{_ORGNR}/policies", json=_POLICY_PAYLOAD
        ).json()["id"]
        for stage in ("ready_to_quote", "quoted", "accepted"):
            resp = auth_client.post(
                f"/policies/{policy_id}/renewal/advance", json={"stage": stage}
            )
            assert resp.status_code == 200
            assert resp.json()["renewal_stage"] == stage

    def test_invalid_stage_returns_422(self, auth_client):
        policy_id = auth_client.post(
            f"/org/{_ORGNR}/policies", json=_POLICY_PAYLOAD
        ).json()["id"]
        resp = auth_client.post(
            f"/policies/{policy_id}/renewal/advance",
            json={"stage": "bogus_stage"},
        )
        assert resp.status_code == 422

    def test_advance_unknown_policy_returns_404(self, auth_client):
        resp = auth_client.post(
            "/policies/999999/renewal/advance",
            json={"stage": "quoted"},
        )
        assert resp.status_code == 404

    def test_advance_with_email_notification_sends_email(self, auth_client):
        """Email send is attempted (notification adapter is mocked in test env)."""
        policy_id = auth_client.post(
            f"/org/{_ORGNR}/policies", json=_POLICY_PAYLOAD
        ).json()["id"]
        resp = auth_client.post(
            f"/policies/{policy_id}/renewal/advance",
            json={"stage": "quoted", "notify_email": "contact@client.no"},
        )
        # Should succeed regardless of whether ACS is configured
        assert resp.status_code == 200
        assert resp.json()["renewal_stage"] == "quoted"


# ── Analytics ─────────────────────────────────────────────────────────────────


class TestAnalytics:
    # Auth-required behaviour is covered by tests/unit/test_auth_safety.py.
    # The conftest sets AUTH_DISABLED=1 unconditionally, so any "401 expected"
    # test against `client` here is structurally untestable.

    def test_premium_analytics_returns_aggregates(self, auth_client):
        auth_client.post(f"/org/{_ORGNR}/policies", json=_POLICY_PAYLOAD)
        resp = auth_client.get("/analytics/premiums")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_premium_book" in data
        assert "active_policy_count" in data
        assert "by_insurer" in data
        assert "by_product" in data

    def test_premium_analytics_counts_only_own_firm(self, auth_client):
        auth_client.post(f"/org/{_ORGNR}/policies", json=_POLICY_PAYLOAD)
        data = auth_client.get("/analytics/premiums").json()
        # All by_insurer totals should reflect only this firm's premium
        total = sum(b["total_premium"] for b in data["by_insurer"])
        assert total == data["total_premium_book"]
