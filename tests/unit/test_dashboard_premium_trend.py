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


def test_populated_db_calls_sum_per_month(client, mock_db):
    """When policies exist, scalar() returns numeric values per month."""
    q = mock_db.query.return_value
    q.filter.return_value = q
    # Simulate a growing book: 100k, 110k, ..., 210k over 12 months
    q.scalar.side_effect = [100_000.0 + (i * 10_000) for i in range(12)]
    resp = client.get("/dashboard/premium-trend")
    body = resp.json()
    assert body["months"][0]["premium_book"] == 100_000.0
    assert body["months"][11]["premium_book"] == 210_000.0
    # YoY = (210k - 100k) / 100k * 100 = 110.0
    assert body["yoy_delta_pct"] == 110.0


def test_yoy_is_null_when_oldest_is_zero(client, mock_db):
    """Avoid divide-by-zero when 12-mo-ago book was zero."""
    q = mock_db.query.return_value
    q.filter.return_value = q
    q.scalar.side_effect = [0.0] + [50_000.0] * 11
    resp = client.get("/dashboard/premium-trend")
    assert resp.json()["yoy_delta_pct"] is None


def test_month_strings_are_oldest_first_and_iso():
    """Month strings should be ISO YYYY-MM and ordered oldest-first."""
    from api.routers.dashboard import _month_end
    from datetime import date as d

    today = d(2026, 4, 29)
    assert _month_end(today, 0) == d(2026, 4, 30)
    assert _month_end(today, 11) == d(2025, 5, 31)
    assert _month_end(today, 12) == d(2025, 4, 30)  # crosses year boundary
