"""Tests for GET /dashboard/premium-trend."""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.auth import CurrentUser, get_current_user
from api.dependencies import get_db
from api.routers.dashboard import router

_app = FastAPI()
_app.include_router(router)
_USER = CurrentUser(email="test@local", name="Test", oid="test-oid", firm_id=1)


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def client(mock_db):
    _app.dependency_overrides[get_db] = lambda: mock_db
    _app.dependency_overrides[get_current_user] = lambda: _USER
    yield TestClient(_app)
    _app.dependency_overrides.clear()


def test_schema_imports_from_api_schemas():
    """Schema must be re-exported from api.schemas top-level."""
    from api.schemas import PremiumTrendOut, PremiumTrendPoint  # noqa: F401


def test_empty_db_returns_12_zero_months(client, mock_db):
    """With no policies, all 12 months should be zero and yoy_delta_pct is None."""
    q = mock_db.query.return_value
    q.filter.return_value = q
    q.scalar.return_value = None  # SUM over empty rows is None in SQLAlchemy
    resp = client.get("/dashboard/premium-trend")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["months"]) == 12
    assert all(m["premium_book"] == 0 for m in body["months"])
    assert body["yoy_delta_pct"] is None
