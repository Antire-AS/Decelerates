"""Production safety tests for api/auth.py::_is_auth_disabled.

These tests are the load-bearing guarantee that AUTH_DISABLED cannot
silently turn off auth in production. If anyone introduces a regression
that lets ENVIRONMENT=production accept AUTH_DISABLED=1, these tests fail
and the PR is blocked.

See plan §🔴 #2 for the original incident context.
"""

import pytest

from api.auth import _is_auth_disabled, get_current_user


def _set_env(monkeypatch, environment, auth_disabled):
    """Helper: explicitly set both env vars (or delete if None)."""
    if environment is None:
        monkeypatch.delenv("ENVIRONMENT", raising=False)
    else:
        monkeypatch.setenv("ENVIRONMENT", environment)
    if auth_disabled is None:
        monkeypatch.delenv("AUTH_DISABLED", raising=False)
    else:
        monkeypatch.setenv("AUTH_DISABLED", auth_disabled)


# ── _is_auth_disabled — pure logic ────────────────────────────────────────────

def test_auth_cannot_be_disabled_in_production(monkeypatch):
    """The whole point of the gate: prod ignores AUTH_DISABLED entirely."""
    _set_env(monkeypatch, "production", "1")
    assert _is_auth_disabled() is False

    _set_env(monkeypatch, "production", "true")
    assert _is_auth_disabled() is False

    _set_env(monkeypatch, "production", "yes")
    assert _is_auth_disabled() is False

    _set_env(monkeypatch, "PRODUCTION", "1")  # case-insensitive
    assert _is_auth_disabled() is False


def test_auth_on_by_default_in_dev(monkeypatch):
    """No AUTH_DISABLED env var → auth is on, even in dev."""
    _set_env(monkeypatch, "development", None)
    assert _is_auth_disabled() is False

    _set_env(monkeypatch, None, None)  # no ENVIRONMENT either
    assert _is_auth_disabled() is False


def test_auth_disabled_in_dev_with_explicit_optin(monkeypatch):
    """Dev/staging + explicit AUTH_DISABLED=1 → bypass active."""
    _set_env(monkeypatch, "development", "1")
    assert _is_auth_disabled() is True

    _set_env(monkeypatch, "staging", "true")
    assert _is_auth_disabled() is True

    _set_env(monkeypatch, "staging", "yes")
    assert _is_auth_disabled() is True


def test_auth_disabled_rejects_invalid_values(monkeypatch):
    """AUTH_DISABLED only accepts 1/true/yes — anything else means off."""
    for bad in ("0", "false", "no", "", "off", "disable", "wat"):
        _set_env(monkeypatch, "development", bad)
        assert _is_auth_disabled() is False, f"AUTH_DISABLED={bad!r} should not bypass"


# ── get_current_user — end-to-end gate behavior ───────────────────────────────

def test_get_current_user_returns_dev_user_when_disabled(monkeypatch):
    """Bypass mode returns the canonical dev user without touching JWT."""
    _set_env(monkeypatch, "development", "1")
    user = get_current_user(creds=None, db=None)
    assert user.email == "dev@local"
    assert user.oid == "dev-oid"
    assert user.firm_id == 1


def test_get_current_user_requires_token_in_production(monkeypatch):
    """In prod, even with AUTH_DISABLED=1 the gate must demand a token."""
    from fastapi import HTTPException

    _set_env(monkeypatch, "production", "1")
    with pytest.raises(HTTPException) as excinfo:
        get_current_user(creds=None, db=None)
    assert excinfo.value.status_code == 401


def test_get_current_user_requires_token_in_dev_without_optin(monkeypatch):
    """Default dev (no AUTH_DISABLED) also requires a token."""
    from fastapi import HTTPException

    _set_env(monkeypatch, "development", None)
    with pytest.raises(HTTPException) as excinfo:
        get_current_user(creds=None, db=None)
    assert excinfo.value.status_code == 401
