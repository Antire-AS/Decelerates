"""Expanded unit tests for api/auth.py — JWKS, token validation, get_optional_user.

Complements test_auth_safety.py which covers the prod-safety gate. These tests
cover the JWT validation mechanics and the optional-user code path.
"""
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

import api.auth as auth_mod
from api.auth import (
    _get_jwks,
    _validate_token,
    get_optional_user,
)


# ── _get_jwks ────────────────────────────────────────────────────────────────

def test_get_jwks_fetches_and_caches(monkeypatch):
    auth_mod._jwks_cache = None  # reset cache
    fake_jwks = {"keys": [{"kid": "abc", "kty": "RSA"}]}
    mock_resp = MagicMock()
    mock_resp.json.return_value = fake_jwks

    with patch("api.auth.requests.get", return_value=mock_resp) as mock_get:
        result = _get_jwks("tenant-123")
        assert result == fake_jwks
        # Second call should use cache — no additional HTTP request
        result2 = _get_jwks("tenant-123")
        assert result2 == fake_jwks
        mock_get.assert_called_once()

    auth_mod._jwks_cache = None  # cleanup


def test_get_jwks_raises_on_http_error(monkeypatch):
    auth_mod._jwks_cache = None
    import requests as _req
    with patch("api.auth.requests.get", side_effect=_req.HTTPError("fail")):
        with pytest.raises(_req.HTTPError):
            _get_jwks("tenant-123")
    auth_mod._jwks_cache = None


# ── _validate_token ──────────────────────────────────────────────────────────

def test_validate_token_raises_when_tenant_id_missing(monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", "")
    monkeypatch.setenv("AUTH_AUDIENCE", "aud-123")
    with pytest.raises(ValueError, match="AZURE_TENANT_ID"):
        _validate_token("some.jwt.token")


def test_validate_token_raises_when_audience_missing(monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant-123")
    monkeypatch.delenv("AUTH_AUDIENCE", raising=False)
    monkeypatch.setenv("AZURE_CLIENT_ID", "")
    with pytest.raises(ValueError, match="AUTH_AUDIENCE"):
        _validate_token("some.jwt.token")


def test_validate_token_raises_on_no_matching_kid(monkeypatch):
    import jwt as _jwt
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant-123")
    monkeypatch.setenv("AUTH_AUDIENCE", "aud-123")
    auth_mod._jwks_cache = None

    fake_jwks = {"keys": [{"kid": "other-kid", "kty": "RSA"}]}
    with patch("api.auth.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = fake_jwks
        mock_get.return_value = mock_resp
        with patch("api.auth.jwt.get_unverified_header", return_value={"kid": "missing-kid"}):
            with pytest.raises(_jwt.InvalidTokenError, match="No matching key"):
                _validate_token("fake.jwt.token")
    auth_mod._jwks_cache = None


def test_validate_token_multi_tenant_skips_issuer(monkeypatch):
    """When AZURE_TENANT_ID=common, issuer verification is skipped."""
    monkeypatch.setenv("AZURE_TENANT_ID", "common")
    monkeypatch.setenv("AUTH_AUDIENCE", "aud-123")
    auth_mod._jwks_cache = None

    fake_jwks = {"keys": [{"kid": "key1", "kty": "RSA", "n": "abc", "e": "AQAB"}]}
    fake_claims = {"oid": "user-1", "preferred_username": "u@t.com", "name": "U"}
    mock_resp = MagicMock()
    mock_resp.json.return_value = fake_jwks

    with patch("api.auth.requests.get", return_value=mock_resp), \
         patch("api.auth.jwt.get_unverified_header", return_value={"kid": "key1"}), \
         patch("api.auth.jwt.algorithms.RSAAlgorithm.from_jwk", return_value="fake-key"), \
         patch("api.auth.jwt.decode", return_value=fake_claims) as mock_decode:
        result = _validate_token("token")
    # Verify that verify_iss=False was passed for multi-tenant
    decode_kwargs = mock_decode.call_args
    assert decode_kwargs[1].get("options", {}).get("verify_iss") is False
    assert result == fake_claims
    auth_mod._jwks_cache = None


# ── get_optional_user ────────────────────────────────────────────────────────

def test_get_optional_user_returns_dev_user_when_auth_disabled(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("AUTH_DISABLED", "1")
    fake_user_row = MagicMock(firm_id=1)
    fake_svc = MagicMock()
    fake_svc.get_or_create.return_value = fake_user_row
    with patch("api.services.user_service.UserService", return_value=fake_svc):
        user = get_optional_user(creds=None, db=MagicMock())
    assert user.email == "dev@local"


def test_get_optional_user_returns_none_without_creds(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("AUTH_DISABLED", raising=False)
    user = get_optional_user(creds=None, db=MagicMock())
    assert user is None


def test_get_optional_user_returns_none_on_invalid_token(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("AUTH_DISABLED", raising=False)
    creds = MagicMock()
    creds.credentials = "bad-token"
    with patch("api.auth._validate_token", side_effect=Exception("invalid")):
        user = get_optional_user(creds=creds, db=MagicMock())
    assert user is None


def test_get_optional_user_returns_user_on_valid_token(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("AUTH_DISABLED", raising=False)
    claims = {"oid": "oid-1", "preferred_username": "user@org.com", "name": "User"}
    creds = MagicMock()
    creds.credentials = "valid-token"
    fake_user_row = MagicMock(firm_id=2)
    fake_svc = MagicMock()
    fake_svc.get_or_create.return_value = fake_user_row
    with patch("api.auth._validate_token", return_value=claims), \
         patch("api.services.user_service.UserService", return_value=fake_svc):
        user = get_optional_user(creds=creds, db=MagicMock())
    assert user.email == "user@org.com"
    assert user.firm_id == 2
