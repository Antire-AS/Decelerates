"""Unit tests for api/routers/coverage.py — coverage gap endpoint."""

import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.auth import CurrentUser, get_current_user
from api.dependencies import get_db
from api.routers.coverage import router

_app = FastAPI()
_app.include_router(router)

_USER = CurrentUser(email="test@local", name="Test", oid="test-oid", firm_id=1)


@pytest.fixture
def client():
    _app.dependency_overrides[get_current_user] = lambda: _USER
    _app.dependency_overrides[get_db] = lambda: MagicMock()
    yield TestClient(_app)
    _app.dependency_overrides.clear()


@patch("api.routers.coverage.analyze_coverage_gap")
def test_coverage_gap_returns_result(mock_gap, client):
    mock_gap.return_value = {
        "orgnr": "123",
        "items": [],
        "covered_count": 3,
        "gap_count": 0,
        "total_count": 3,
    }
    resp = client.get("/org/123/coverage-gap")
    assert resp.status_code == 200
    assert resp.json()["gap_count"] == 0


@patch("api.routers.coverage.analyze_coverage_gap")
def test_coverage_gap_with_gaps(mock_gap, client):
    mock_gap.return_value = {
        "orgnr": "123",
        "items": [{"type": "Cyber", "status": "gap", "priority": "Høy"}],
        "covered_count": 2,
        "gap_count": 1,
        "total_count": 3,
    }
    resp = client.get("/org/123/coverage-gap")
    assert resp.status_code == 200
    assert resp.json()["gap_count"] == 1
