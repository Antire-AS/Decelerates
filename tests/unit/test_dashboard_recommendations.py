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


def test_endpoint_returns_200_when_no_companies(client, mock_db):
    """No policies → empty companies + claims → engine emits nothing."""
    q = mock_db.query.return_value
    q.filter.return_value = q
    q.distinct.return_value = q
    q.all.return_value = []
    q.group_by.return_value.all.return_value = []
    resp = client.get("/dashboard/recommendations")
    assert resp.status_code == 200
    assert resp.json() == {"items": []}


def test_endpoint_fires_pep_recommendation_for_company_with_hits(client, mock_db):
    """A company with pep_raw.hit_count > 0 should produce a "pep" item."""
    from datetime import datetime, timezone

    q = mock_db.query.return_value
    q.filter.return_value = q

    fake_company = MagicMock()
    fake_company.orgnr = "111111111"
    fake_company.navn = "Foo AS"
    fake_company.pep_raw = {"hit_count": 2}

    # First .all() call (orgnr distinct query) → return one orgnr tuple.
    # Second .all() call (Company.in_(...)) → return the fake company.
    # Third .all() call (claims groupby) → empty.
    distinct_mock = MagicMock()
    distinct_mock.all.return_value = [("111111111",)]
    q.distinct.return_value = distinct_mock
    # .all() across multiple calls — first for company-rows, then would-be for groupby
    q.all.side_effect = [[fake_company]]
    q.group_by.return_value.all.return_value = []

    resp = client.get("/dashboard/recommendations")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(i["kind"] == "pep" and i["orgnr"] == "111111111" for i in items)
    # Avoid unused-import warning
    _ = datetime, timezone
