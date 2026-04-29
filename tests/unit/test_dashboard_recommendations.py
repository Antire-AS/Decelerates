"""Tests for GET /dashboard/recommendations."""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.auth import CurrentUser, get_current_user
from api.dependencies import get_db
from api.routers.dashboard import router

_app = FastAPI()
_app.include_router(router)
_USER = CurrentUser(email="t@l", name="T", oid="o", firm_id=1)


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def client(mock_db):
    _app.dependency_overrides[get_db] = lambda: mock_db
    _app.dependency_overrides[get_current_user] = lambda: _USER
    yield TestClient(_app)
    _app.dependency_overrides.clear()


def test_endpoint_returns_200_with_empty_items_v1(client, mock_db):
    """v1 stub passes empty inputs to engine; expect items=[]."""
    resp = client.get("/dashboard/recommendations")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"items": []}
