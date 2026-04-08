"""Integration tests — portfolio CRUD, firm_id isolation, analytics, concentration.

Requires TEST_DATABASE_URL. Auth is bypassed via dependency override.
Run:
    TEST_DATABASE_URL=postgresql://... uv run python -m pytest tests/integration/test_portfolio.py -v
"""
import os
from datetime import date, timedelta

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="set TEST_DATABASE_URL=postgresql://... to run integration tests",
)

_FIRM_ID  = 1
_FIRM2_ID = 2
_ORGNR    = "111222333"


# ── Shared fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def auth_client(test_db):
    from fastapi.testclient import TestClient
    from api.main import app
    from api.auth import CurrentUser, get_current_user
    from api.dependencies import get_db

    def _fake_user():
        return CurrentUser(email="test@broker.no", name="Test", oid="oid-1", firm_id=_FIRM_ID)

    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_current_user] = _fake_user
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def auth_client_firm2(test_db):
    from fastapi.testclient import TestClient
    from api.main import app
    from api.auth import CurrentUser, get_current_user
    from api.dependencies import get_db

    def _fake_user():
        return CurrentUser(email="other@broker.no", name="Other", oid="oid-2", firm_id=_FIRM2_ID)

    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_current_user] = _fake_user
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def seed_broker_firms(test_db):
    from datetime import datetime, timezone
    from api.db import BrokerFirm

    for fid, name in [(_FIRM_ID, "Test Megling AS"), (_FIRM2_ID, "Annet Megling AS")]:
        if not test_db.query(BrokerFirm).filter(BrokerFirm.id == fid).first():
            test_db.add(BrokerFirm(id=fid, name=name, created_at=datetime.now(timezone.utc)))
            test_db.commit()


# ── Portfolio CRUD ─────────────────────────────────────────────────────────────

class TestPortfolioCRUD:
    def test_create_returns_id_and_name(self, auth_client):
        resp = auth_client.post("/portfolio", json={"name": "Test Portfolio"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] > 0
        assert data["name"] == "Test Portfolio"

    def test_list_includes_created_portfolio(self, auth_client):
        auth_client.post("/portfolio", json={"name": "Listed Portfolio"})
        resp = auth_client.get("/portfolio")
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()]
        assert "Listed Portfolio" in names

    def test_delete_removes_portfolio(self, auth_client):
        pid = auth_client.post("/portfolio", json={"name": "To Delete"}).json()["id"]
        assert auth_client.delete(f"/portfolio/{pid}").status_code == 200
        names = [p["name"] for p in auth_client.get("/portfolio").json()]
        assert "To Delete" not in names

    def test_delete_unknown_portfolio_returns_404(self, auth_client):
        assert auth_client.delete("/portfolio/999999").status_code == 404

    def test_add_company_and_list_risk(self, auth_client):
        pid = auth_client.post("/portfolio", json={"name": "Risk Test"}).json()["id"]
        resp = auth_client.post(f"/portfolio/{pid}/companies", json={"orgnr": _ORGNR})
        assert resp.status_code == 200
        risk = auth_client.get(f"/portfolio/{pid}/risk").json()
        assert isinstance(risk, list)
        orgnrs = [r["orgnr"] for r in risk]
        assert _ORGNR in orgnrs

    def test_remove_company(self, auth_client):
        pid = auth_client.post("/portfolio", json={"name": "Remove Test"}).json()["id"]
        auth_client.post(f"/portfolio/{pid}/companies", json={"orgnr": _ORGNR})
        auth_client.delete(f"/portfolio/{pid}/companies/{_ORGNR}")
        risk = auth_client.get(f"/portfolio/{pid}/risk").json()
        assert not any(r["orgnr"] == _ORGNR for r in risk)


# ── Firm isolation ─────────────────────────────────────────────────────────────


class TestFirmIsolation:
    def test_portfolio_not_visible_to_other_firm(self, auth_client, auth_client_firm2):
        pid = auth_client.post("/portfolio", json={"name": "Firm1 Portfolio"}).json()["id"]
        firm2_portfolios = auth_client_firm2.get("/portfolio").json()
        assert not any(p["id"] == pid for p in firm2_portfolios)

    def test_delete_other_firms_portfolio_returns_404(self, auth_client, auth_client_firm2):
        pid = auth_client.post("/portfolio", json={"name": "Only Firm1"}).json()["id"]
        assert auth_client_firm2.delete(f"/portfolio/{pid}").status_code == 404

    def test_analytics_scoped_to_firm(self, auth_client, auth_client_firm2, test_db):
        """Policies created under firm 1 must not appear in firm 2's analytics."""
        from datetime import datetime, timezone
        from api.db import Policy, PolicyStatus
        pid = auth_client.post("/portfolio", json={"name": "Analytics Isolation"}).json()["id"]
        auth_client.post(f"/portfolio/{pid}/companies", json={"orgnr": _ORGNR})
        # Directly insert a policy for firm 1
        now = datetime.now(timezone.utc)
        test_db.add(Policy(
            orgnr=_ORGNR, firm_id=_FIRM_ID, insurer="TestIns", product_type="Ting",
            annual_premium_nok=100_000, status=PolicyStatus.active,
            created_at=now, updated_at=now,
        ))
        test_db.commit()
        firm1_analytics = auth_client.get(f"/portfolio/{pid}/analytics").json()
        assert firm1_analytics["total_annual_premium_nok"] == 100_000

        # Firm 2 cannot access this portfolio
        resp = auth_client_firm2.get(f"/portfolio/{pid}/analytics")
        assert resp.status_code == 404


# ── Analytics endpoint ─────────────────────────────────────────────────────────

class TestPortfolioAnalytics:
    def _make_portfolio_with_policies(self, auth_client, test_db):
        from datetime import datetime, timezone
        from api.db import Policy, PolicyStatus
        # Clean up any leftover policies from prior test runs to keep aggregate
        # assertions deterministic. test_db.rollback() in the fixture is a no-op
        # because the service layer commits inside each request.
        test_db.query(Policy).filter(
            Policy.orgnr == _ORGNR, Policy.firm_id == _FIRM_ID,
        ).delete(synchronize_session=False)
        test_db.commit()
        pid = auth_client.post("/portfolio", json={"name": "Analytics Test"}).json()["id"]
        auth_client.post(f"/portfolio/{pid}/companies", json={"orgnr": _ORGNR})
        now = datetime.now(timezone.utc)
        for insurer, product, premium, days in [
            ("If", "Ting", 200_000, 30),
            ("If", "Ansvar", 100_000, 120),
            ("Gjensidige", "Cyber", 50_000, 60),
        ]:
            test_db.add(Policy(
                orgnr=_ORGNR, firm_id=_FIRM_ID, insurer=insurer, product_type=product,
                annual_premium_nok=float(premium), status=PolicyStatus.active,
                renewal_date=date.today() + timedelta(days=days),
                created_at=now, updated_at=now,
            ))
        test_db.commit()
        return pid

    def test_analytics_response_shape(self, auth_client, test_db):
        pid = self._make_portfolio_with_policies(auth_client, test_db)
        data = auth_client.get(f"/portfolio/{pid}/analytics").json()
        for key in ("total_annual_premium_nok", "active_policy_count",
                    "insurer_concentration", "product_concentration",
                    "upcoming_renewals_90d", "upcoming_renewals_30d"):
            assert key in data, f"missing key: {key}"

    def test_analytics_sums_premiums(self, auth_client, test_db):
        pid = self._make_portfolio_with_policies(auth_client, test_db)
        data = auth_client.get(f"/portfolio/{pid}/analytics").json()
        assert data["total_annual_premium_nok"] == 350_000
        assert data["active_policy_count"] == 3

    def test_analytics_insurer_concentration_sorted(self, auth_client, test_db):
        pid = self._make_portfolio_with_policies(auth_client, test_db)
        data = auth_client.get(f"/portfolio/{pid}/analytics").json()
        insurers = [r["insurer"] for r in data["insurer_concentration"]]
        assert insurers[0] == "If"  # highest premium first

    def test_analytics_share_pct_present(self, auth_client, test_db):
        pid = self._make_portfolio_with_policies(auth_client, test_db)
        data = auth_client.get(f"/portfolio/{pid}/analytics").json()
        total = sum(r["share_pct"] for r in data["insurer_concentration"])
        assert abs(total - 100.0) < 0.5

    def test_analytics_renewals_counted(self, auth_client, test_db):
        pid = self._make_portfolio_with_policies(auth_client, test_db)
        data = auth_client.get(f"/portfolio/{pid}/analytics").json()
        # 30d policy: 1 in 30d, 2 in 90d (30 + 60 days)
        assert data["upcoming_renewals_30d"] == 1
        assert data["upcoming_renewals_90d"] == 2

    def test_empty_portfolio_analytics_returns_zeros(self, auth_client):
        pid = auth_client.post("/portfolio", json={"name": "Empty"}).json()["id"]
        data = auth_client.get(f"/portfolio/{pid}/analytics").json()
        assert data["total_annual_premium_nok"] == 0
        assert data["active_policy_count"] == 0
        assert data["insurer_concentration"] == []


# ── Concentration endpoint ─────────────────────────────────────────────────────

class TestPortfolioConcentration:
    def test_concentration_response_shape(self, auth_client, test_db):
        from api.db import Company
        pid = auth_client.post("/portfolio", json={"name": "Conc Test"}).json()["id"]
        auth_client.post(f"/portfolio/{pid}/companies", json={"orgnr": _ORGNR})
        if not test_db.query(Company).filter(Company.orgnr == _ORGNR).first():
            # Company has no created_at column (see api/db.py:28-50)
            test_db.add(Company(
                orgnr=_ORGNR, navn="Test AS",
                naeringskode1="47.110", kommune="Oslo",
                sum_driftsinntekter=50_000_000,
            ))
            test_db.commit()
        data = auth_client.get(f"/portfolio/{pid}/concentration").json()
        for key in ("portfolio_id", "total_companies", "total_revenue",
                    "by_industry", "by_geography", "by_size"):
            assert key in data, f"missing key: {key}"

    def test_concentration_unknown_portfolio_returns_404(self, auth_client):
        assert auth_client.get("/portfolio/999999/concentration").status_code == 404
