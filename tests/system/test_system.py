"""
Systemtester — end-to-end smoke tests against a live running API instance.

No mocking. Tests hit a real API over HTTP and verify responses.
Requires a fully running broker-api with a connected database.

Run:
    SYSTEM_TEST_URL=http://localhost:8000 \\
    uv run python -m pytest tests/test_system.py -v -m system

Or against a deployed instance:
    SYSTEM_TEST_URL=https://ca-prod-api.<hash>.norwayeast.azurecontainerapps.io \\
    uv run python -m pytest tests/test_system.py -v -m system
"""

import os

import pytest
import requests as http

_SYSTEM_URL = os.environ.get("SYSTEM_TEST_URL", "").rstrip("/")

pytestmark = pytest.mark.skipif(
    not _SYSTEM_URL,
    reason="set SYSTEM_TEST_URL=http://localhost:8000 to run system tests",
)

# DNB Bank ASA — seeded by _seed_pdf_sources() on every API startup
_SEED_ORGNR = "984851006"
_SEED_NAVN = "DNB BANK ASA"


@pytest.mark.system
class TestSmoke:
    """Basic availability — API is up and core endpoints respond."""

    def test_ping(self):
        resp = http.get(f"{_SYSTEM_URL}/ping", timeout=10)
        assert resp.status_code == 200

    def test_openapi_docs_available(self):
        resp = http.get(f"{_SYSTEM_URL}/docs", timeout=10)
        assert resp.status_code == 200

    def test_companies_endpoint_returns_list(self):
        resp = http.get(f"{_SYSTEM_URL}/companies", timeout=10)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_broker_settings_returns_dict(self):
        resp = http.get(f"{_SYSTEM_URL}/broker/settings", timeout=10)
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)


@pytest.mark.system
class TestSearch:
    """Search hits BRREG and returns structured results."""

    def test_search_dnb_returns_results(self):
        resp = http.get(f"{_SYSTEM_URL}/search", params={"name": "dnb"}, timeout=15)
        assert resp.status_code == 200
        results = resp.json()
        assert isinstance(results, list)
        assert len(results) > 0
        assert all("orgnr" in r and "navn" in r for r in results)

    def test_search_too_short_returns_422(self):
        resp = http.get(f"{_SYSTEM_URL}/search", params={"q": "a"}, timeout=10)
        assert resp.status_code == 422


@pytest.mark.system
class TestSeedData:
    """Verify the seeded DNB company is accessible (proves DB + BRREG integration)."""

    def test_seed_company_profile_returns_200(self):
        resp = http.get(f"{_SYSTEM_URL}/org/{_SEED_ORGNR}", timeout=30)
        assert resp.status_code == 200

    def test_seed_company_has_correct_navn(self):
        data = http.get(f"{_SYSTEM_URL}/org/{_SEED_ORGNR}", timeout=30).json()
        assert data["org"]["navn"] == _SEED_NAVN

    def test_seed_company_has_risk_summary(self):
        data = http.get(f"{_SYSTEM_URL}/org/{_SEED_ORGNR}", timeout=30).json()
        assert "risk_summary" in data
        assert "risk_score" in data["risk_summary"]

    def test_broker_settings_crud(self):
        payload = {"firm_name": "Systemtest Megling AS", "contact_email": "sys@test.no"}
        assert (
            http.post(
                f"{_SYSTEM_URL}/broker/settings", json=payload, timeout=10
            ).status_code
            == 200
        )
        data = http.get(f"{_SYSTEM_URL}/broker/settings", timeout=10).json()
        assert data["firm_name"] == "Systemtest Megling AS"
