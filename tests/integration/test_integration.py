"""
Integrasjonstester — verify that routers, services, and database work together.

Uses FastAPI TestClient with a real PostgreSQL test database.
External HTTP calls (BRREG, Gemini, OpenSanctions, etc.) are patched so
the tests run without network access.

Run:
    TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/brokerdb_test \\
    uv run python -m pytest tests/test_integration.py -v

In CI: TEST_DATABASE_URL is set automatically by the workflow.
"""
import os
from unittest.mock import patch, MagicMock

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="set TEST_DATABASE_URL=postgresql://... to run integration tests",
)

# ── Shared mock data ───────────────────────────────────────────────────────────

_MOCK_ORG_BRREG = {
    "organisasjonsnummer": "987654321",
    "navn": "Integrasjonstest AS",
    "organisasjonsform": {"kode": "AS", "beskrivelse": "Aksjeselskap"},
    "forretningsadresse": {
        "poststed": "Oslo",
        "postnummer": "0150",
        "adresse": ["Testgata 1"],
        "kommune": "Oslo",
        "land": "Norge",
    },
    "naeringskode1": {"kode": "62.010", "beskrivelse": "Programvareutvikling"},
    "konkurs": False,
    "underAvvikling": False,
    "antallAnsatte": 10,
}

_MOCK_REGNSKAP = {
    "sum_driftsinntekter": 5_000_000,
    "sum_egenkapital": 2_000_000,
    "sum_eiendeler": 4_000_000,
    "equity_ratio": 0.5,
}

_PROFILE_PATCHES = (
    patch("api.services.external_apis.fetch_enhet_by_orgnr", return_value=_MOCK_ORG_BRREG),
    patch("api.services.external_apis.fetch_regnskap_keyfigures", return_value=_MOCK_REGNSKAP),
    patch("api.services.external_apis.pep_screen_name", return_value=[]),
    patch("api.services.pdf_extract._auto_extract_pdf_sources"),
)


# ── Healthcheck ───────────────────────────────────────────────────────────────

class TestHealthcheck:
    def test_ping_returns_ok(self, client):
        resp = client.get("/ping")
        assert resp.status_code == 200


# ── Broker settings ────────────────────────────────────────────────────────────

class TestBrokerSettings:
    def test_get_returns_dict(self, client):
        resp = client.get("/broker/settings")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)

    def test_post_persists_and_get_retrieves(self, client):
        payload = {
            "firm_name": "Integrasjonstest Megling AS",
            "orgnr": "123456789",
            "contact_email": "test@example.no",
        }
        assert client.post("/broker/settings", json=payload).status_code == 200

        data = client.get("/broker/settings").json()
        assert data["firm_name"] == "Integrasjonstest Megling AS"
        assert data["contact_email"] == "test@example.no"


# ── Broker notes ───────────────────────────────────────────────────────────────

class TestBrokerNotes:
    ORGNR = "111222333"

    def test_create_note_returns_id(self, client):
        resp = client.post(
            f"/org/{self.ORGNR}/broker-notes",
            json={"text": "Integrasjonstest notat"},
        )
        assert resp.status_code == 200
        assert "id" in resp.json()

    def test_list_contains_created_note(self, client):
        client.post(f"/org/{self.ORGNR}/broker-notes", json={"text": "Liste-notat"})
        notes = client.get(f"/org/{self.ORGNR}/broker-notes").json()
        assert isinstance(notes, list)
        assert any(n["text"] == "Liste-notat" for n in notes)

    def test_delete_removes_note(self, client):
        note_id = client.post(
            f"/org/{self.ORGNR}/broker-notes", json={"text": "Slett meg"}
        ).json()["id"]

        assert client.delete(f"/org/{self.ORGNR}/broker-notes/{note_id}").status_code == 200
        ids = [n["id"] for n in client.get(f"/org/{self.ORGNR}/broker-notes").json()]
        assert note_id not in ids

    def test_delete_unknown_note_returns_404(self, client):
        resp = client.delete(f"/org/{self.ORGNR}/broker-notes/999999")
        assert resp.status_code == 404


# ── Companies ─────────────────────────────────────────────────────────────────

class TestCompanies:
    def test_list_companies_returns_list(self, client):
        resp = client.get("/companies")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ── Search ────────────────────────────────────────────────────────────────────

class TestSearch:
    def test_search_returns_list(self, client):
        mock_results = [
            {
                "orgnr": "984851006",
                "navn": "DNB Bank ASA",
                "organisasjonsform": "Allmennaksjeselskap",
                "organisasjonsform_kode": "ASA",
                "kommune": "Oslo",
            }
        ]
        with patch(
            "api.services.external_apis.fetch_enhetsregisteret",
            return_value=mock_results,
        ):
            resp = client.get("/search", params={"q": "dnb"})

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert data[0]["orgnr"] == "984851006"

    def test_search_without_query_returns_422(self, client):
        assert client.get("/search").status_code == 422


# ── Org profile ────────────────────────────────────────────────────────────────

class TestOrgProfile:
    ORGNR = "987654321"

    def test_profile_returns_org_and_risk(self, client):
        with (
            patch("api.services.external_apis.fetch_enhet_by_orgnr", return_value=_MOCK_ORG_BRREG),
            patch("api.services.external_apis.fetch_regnskap_keyfigures", return_value=_MOCK_REGNSKAP),
            patch("api.services.external_apis.pep_screen_name", return_value=[]),
            patch("api.services.pdf_extract._auto_extract_pdf_sources"),
        ):
            resp = client.get(f"/org/{self.ORGNR}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["org"]["navn"] == "Integrasjonstest AS"
        assert "risk_summary" in data

    def test_unknown_org_returns_404(self, client):
        with (
            patch("api.services.external_apis.fetch_enhet_by_orgnr", return_value=None),
            patch("api.services.external_apis.fetch_regnskap_keyfigures", return_value={}),
            patch("api.services.external_apis.pep_screen_name", return_value=[]),
            patch("api.services.pdf_extract._auto_extract_pdf_sources"),
        ):
            resp = client.get("/org/000000000")

        assert resp.status_code == 404


# ── Financial history ──────────────────────────────────────────────────────────

class TestHistory:
    ORGNR = "444555666"

    def test_empty_history_returns_list(self, client):
        resp = client.get(f"/org/{self.ORGNR}/history")
        assert resp.status_code == 200
        body = resp.json()
        assert body["orgnr"] == self.ORGNR
        assert isinstance(body["years"], list)
