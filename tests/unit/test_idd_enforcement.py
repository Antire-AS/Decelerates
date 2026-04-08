"""Unit tests for IDD enforcement gate and suitability reasoning."""
import sys
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

# Stub heavy transitive deps before any api.* import
sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())
sys.modules.setdefault("api.telemetry", MagicMock())

from api.routers.recommendations import router, _get_svc
from api.services.recommendation_service import RecommendationService

_app = FastAPI()
_app.include_router(router)


def _make_mock_svc():
    svc = MagicMock(spec=RecommendationService)
    svc.list.return_value = []
    svc.create.return_value = MagicMock(
        id=1, orgnr="123456789", created_by_email="broker@firm.no",
        created_at=None, idd_id=1, submission_ids=[], recommended_insurer="Gjensidige",
        rationale_text="Good coverage", pdf_content=None,
    )
    return svc


class TestIddGate:
    def _client_with_mocks(self, has_idd: bool):
        mock_svc = _make_mock_svc()
        mock_user = MagicMock()
        mock_user.email = "broker@firm.no"
        mock_user.firm_id = 1

        mock_db = MagicMock()
        # IDD check query
        idd_query = MagicMock()
        if has_idd:
            idd_query.first.return_value = MagicMock(id=1)
        else:
            idd_query.first.return_value = None
        idd_query.order_by.return_value = idd_query
        idd_query.filter.return_value = idd_query

        # Company query
        company_query = MagicMock()
        company_query.filter.return_value = company_query
        company_query.first.return_value = None

        def _query_side(model):
            from api.db import IddBehovsanalyse
            if model is IddBehovsanalyse:
                return idd_query
            return company_query
        mock_db.query.side_effect = _query_side

        from api.auth import get_current_user
        from api.dependencies import get_db

        _app.dependency_overrides[get_db] = lambda: mock_db
        _app.dependency_overrides[get_current_user] = lambda: mock_user
        _app.dependency_overrides[_get_svc] = lambda: mock_svc
        client = TestClient(_app, raise_server_exceptions=False)
        return client

    def teardown_method(self):
        _app.dependency_overrides.clear()

    def test_returns_422_without_idd(self):
        client = self._client_with_mocks(has_idd=False)
        resp = client.post(
            "/org/123456789/recommendations",
            json={"recommended_insurer": "Gjensidige"},
        )
        assert resp.status_code == 422
        assert "IDD" in resp.text or "behovsanalyse" in resp.text.lower()

    def test_proceeds_with_idd(self):
        client = self._client_with_mocks(has_idd=True)
        resp = client.post(
            "/org/123456789/recommendations",
            json={"recommended_insurer": "Gjensidige"},
        )
        assert resp.status_code == 201


class TestSuitabilityReasoning:
    def test_generate_suitability_calls_llm_and_stores(self):
        from api.services.idd import IddService
        from api.db import IddBehovsanalyse

        mock_idd = MagicMock(spec=IddBehovsanalyse)
        mock_idd.id = 1
        mock_idd.orgnr = "123456789"
        mock_idd.firm_id = 1
        mock_idd.risk_appetite = "middels"
        mock_idd.has_employees = True
        mock_idd.property_owned = False
        mock_idd.has_cyber_risk = True
        mock_idd.annual_revenue_nok = 10_000_000.0
        mock_idd.special_requirements = None
        mock_idd.recommended_products = ["Ansvarsforsikring", "Cyberforsikring"]
        mock_idd.suitability_basis = None

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = mock_idd

        with patch("api.services.llm._llm_answer_raw", return_value="Kunden har cyber-risiko fordi..."):
            svc = IddService(db)
            result = svc.generate_suitability_reasoning("123456789", 1, 1)

        assert "cyber" in result.lower() or result  # LLM returned something
        assert mock_idd.suitability_basis == result
        db.commit.assert_called_once()
