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
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="set TEST_DATABASE_URL=postgresql://... to run integration tests",
)

# ── Shared mock data ───────────────────────────────────────────────────────────

# Shape matches api.services.brreg_client.fetch_enhet_by_orgnr's return value
# — flattened, not the raw BRREG nested response. See _build_enhet_dict at
# api/services/brreg_client.py:14.
_MOCK_ORG_BRREG = {
    "orgnr": "987654321",
    "navn": "Integrasjonstest AS",
    "organisasjonsform": "Aksjeselskap",
    "organisasjonsform_kode": "AS",
    "kommune": "Oslo",
    "postnummer": "0150",
    "land": "Norge",
    "naeringskode1": "62.010",
    "naeringskode1_beskrivelse": "Programvareutvikling",
    "kommunenummer": "0301",
    "poststed": "Oslo",
    "adresse": ["Testgata 1"],
    "stiftelsesdato": None,
    "hjemmeside": None,
    "konkurs": False,
    "under_konkursbehandling": False,
    "under_avvikling": False,
}

_MOCK_REGNSKAP = {
    "sum_driftsinntekter": 5_000_000,
    "sum_egenkapital": 2_000_000,
    "sum_eiendeler": 4_000_000,
    "equity_ratio": 0.5,
}

_PROFILE_PATCHES = (
    patch(
        "api.services.external_apis.fetch_enhet_by_orgnr", return_value=_MOCK_ORG_BRREG
    ),
    patch(
        "api.services.external_apis.fetch_regnskap_keyfigures",
        return_value=_MOCK_REGNSKAP,
    ),
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

        assert (
            client.delete(f"/org/{self.ORGNR}/broker-notes/{note_id}").status_code
            == 200
        )
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
            "api.routers.company.fetch_enhetsregisteret",
            return_value=mock_results,
        ):
            # Endpoint expects `name`, not `q` — see api/routers/company.py:26
            resp = client.get("/search", params={"name": "dnb"})

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
        # fetch_org_profile imports cached_fetch_enhet locally from
        # api.services.caching, so patch it at the caching module (where the
        # name is defined). Clear the cache first so a prior test's result
        # doesn't leak through.
        from api.services.caching import clear_enhet_cache

        clear_enhet_cache()
        with (
            patch(
                "api.services.caching.cached_fetch_enhet",
                return_value=_MOCK_ORG_BRREG,
            ),
            patch(
                "api.services.company.fetch_regnskap_keyfigures",
                return_value=_MOCK_REGNSKAP,
            ),
            patch("api.services.company.pep_screen_name", return_value=[]),
            patch("api.services.pdf_extract._auto_extract_pdf_sources"),
        ):
            resp = client.get(f"/org/{self.ORGNR}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["org"]["navn"] == "Integrasjonstest AS"
        assert "risk_summary" in data

    def test_unknown_org_returns_404(self, client):
        from api.services.caching import clear_enhet_cache

        clear_enhet_cache()
        with (
            patch("api.services.caching.cached_fetch_enhet", return_value=None),
            patch("api.services.company.fetch_regnskap_keyfigures", return_value={}),
            patch("api.services.company.pep_screen_name", return_value=[]),
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


# ── Helpers for CRM test data ──────────────────────────────────────────────────


def _ensure_firm(db, firm_id: int = 1):
    from api.db import BrokerFirm

    firm = db.query(BrokerFirm).filter(BrokerFirm.id == firm_id).first()
    if not firm:
        firm = BrokerFirm(
            id=firm_id, name="Test Megling AS", created_at=datetime.now(timezone.utc)
        )
        db.add(firm)
        db.flush()
    return firm


def _make_policy(db, orgnr: str, **kwargs):
    from api.db import Policy, PolicyStatus

    _ensure_firm(db)
    # Policy has both created_at and updated_at NOT NULL columns — set both.
    now = datetime.now(timezone.utc)
    p = Policy(
        orgnr=orgnr,
        firm_id=1,
        insurer=kwargs.get("insurer", "Gjensidige"),
        product_type=kwargs.get("product_type", "Eiendomsforsikring"),
        status=kwargs.get("status", PolicyStatus.active),
        annual_premium_nok=kwargs.get("annual_premium_nok", 100_000.0),
        commission_rate_pct=kwargs.get("commission_rate_pct", 10.0),
        commission_amount_nok=kwargs.get("commission_amount_nok", None),
        created_at=now,
        updated_at=now,
    )
    db.add(p)
    db.flush()
    return p


# ── Commission endpoints ────────────────────────────────────────────────────────


class TestCommission:
    ORGNR = "555666777"

    def test_summary_returns_expected_fields(self, client, test_db):
        _make_policy(test_db, self.ORGNR)
        resp = client.get("/commission/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_commission_ytd" in data
        assert "total_premium_managed" in data
        assert "active_policy_count" in data
        assert "revenue_by_product_type" in data
        assert "revenue_by_insurer" in data
        assert "renewal_commission_vs_new" in data

    def test_summary_counts_active_policy(self, client, test_db):
        _make_policy(
            test_db, self.ORGNR, annual_premium_nok=200_000.0, commission_rate_pct=5.0
        )
        resp = client.get("/commission/summary")
        assert resp.json()["active_policy_count"] >= 1
        assert resp.json()["total_premium_managed"] >= 200_000.0

    def test_by_client_returns_policy_list(self, client, test_db):
        _make_policy(
            test_db, self.ORGNR, commission_amount_nok=8_000.0, commission_rate_pct=None
        )
        resp = client.get(f"/commission/by-client/{self.ORGNR}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["orgnr"] == self.ORGNR
        assert data["total_commission_lifetime"] >= 8_000.0
        assert len(data["policies"]) >= 1

    def test_missing_returns_policy_without_commission(self, client, test_db):
        from api.db import PolicyStatus

        _make_policy(
            test_db,
            self.ORGNR,
            commission_rate_pct=None,
            commission_amount_nok=None,
            status=PolicyStatus.active,
        )
        resp = client.get("/commission/missing")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert any(p["orgnr"] == self.ORGNR for p in resp.json())


# ── Consent endpoints ───────────────────────────────────────────────────────────


class TestConsent:
    ORGNR = "666777888"

    @pytest.fixture(autouse=True)
    def _seed_firm(self, test_db):
        """consent_records.firm_id is a FK to broker_firms; seed it before
        every test in this class so INSERT doesn't hit a ForeignKeyViolation."""
        _ensure_firm(test_db)
        test_db.commit()

    def test_record_consent_returns_201_with_fields(self, client):
        resp = client.post(
            f"/gdpr/company/{self.ORGNR}/consent",
            json={"lawful_basis": "consent", "purpose": "insurance_advice"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["orgnr"] == self.ORGNR
        assert data["lawful_basis"] == "consent"
        assert data["purpose"] == "insurance_advice"
        assert data["withdrawn_at"] is None

    def test_list_consents_includes_created(self, client):
        client.post(
            f"/gdpr/company/{self.ORGNR}/consent",
            json={"lawful_basis": "contract", "purpose": "insurance_advice"},
        )
        resp = client.get(f"/gdpr/company/{self.ORGNR}/consents")
        assert resp.status_code == 200
        assert any(c["purpose"] == "insurance_advice" for c in resp.json())

    def test_withdraw_consent_sets_withdrawn_at(self, client):
        consent_id = client.post(
            f"/gdpr/company/{self.ORGNR}/consent",
            json={"lawful_basis": "consent", "purpose": "marketing"},
        ).json()["id"]

        # Starlette TestClient.delete() doesn't accept a json kwarg; use
        # request() for DELETE-with-body.
        resp = client.request(
            "DELETE",
            f"/gdpr/company/{self.ORGNR}/consent/{consent_id}",
            json={"reason": "customer request"},
        )
        assert resp.status_code == 200
        assert resp.json()["withdrawn_at"] is not None

    def test_withdrawn_consent_excluded_from_list(self, client):
        consent_id = client.post(
            f"/gdpr/company/{self.ORGNR}/consent",
            json={"lawful_basis": "consent", "purpose": "credit_check"},
        ).json()["id"]
        # Endpoint requires a body (reason). Use request() for DELETE-with-body.
        client.request(
            "DELETE",
            f"/gdpr/company/{self.ORGNR}/consent/{consent_id}",
            json={"reason": "customer request"},
        )

        active = client.get(f"/gdpr/company/{self.ORGNR}/consents").json()
        assert all(c["id"] != consent_id for c in active)


# ── Win/loss endpoints ──────────────────────────────────────────────────────────


class TestWinLoss:
    def _seed(self, db):
        from api.db import Insurer, Submission, SubmissionStatus

        _ensure_firm(db)
        insurer = Insurer(
            firm_id=1,
            name="Tryg Forsikring",
            created_at=datetime.now(timezone.utc),
        )
        db.add(insurer)
        db.flush()
        db.add(
            Submission(
                orgnr="777888999",
                firm_id=1,
                insurer_id=insurer.id,
                product_type="Eiendom",
                status=SubmissionStatus.quoted,
                created_at=datetime.now(timezone.utc),
            )
        )
        db.add(
            Submission(
                orgnr="777888999",
                firm_id=1,
                insurer_id=insurer.id,
                product_type="Eiendom",
                status=SubmissionStatus.declined,
                created_at=datetime.now(timezone.utc),
            )
        )
        db.flush()
        return insurer

    def test_win_loss_returns_expected_fields(self, client, test_db):
        self._seed(test_db)
        resp = client.get("/insurers/win-loss")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_submissions" in data
        assert "win_rate_pct" in data
        assert "by_insurer" in data
        assert "by_product_type" in data

    def test_win_rate_calculated_correctly(self, client, test_db):
        self._seed(test_db)
        data = client.get("/insurers/win-loss").json()
        # 1 quoted out of 2 total = 50%
        assert data["total_submissions"] >= 2
        assert data["win_rate_pct"] <= 100.0

    def test_by_insurer_keyed_by_name(self, client, test_db):
        self._seed(test_db)
        data = client.get("/insurers/win-loss").json()
        assert "Tryg Forsikring" in data["by_insurer"]
