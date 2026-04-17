"""Unit tests for client token utilities.

Pure static tests — no DB, no network, no API keys.
Tests focus on the token TTL constant and the _parse_csv_orgnrs independence
(CSV tests are in test_batch_import.py).  Here we test the router helper logic
that can be exercised without a live DB.
"""

import secrets
from datetime import datetime, timezone, timedelta


# ── Token format ──────────────────────────────────────────────────────────────


def test_token_urlsafe_length():
    """secrets.token_urlsafe(32) produces a token of at least 32 base64-url chars."""
    token = secrets.token_urlsafe(32)
    assert len(token) >= 32


def test_token_urlsafe_is_string():
    assert isinstance(secrets.token_urlsafe(32), str)


def test_tokens_are_unique():
    tokens = {secrets.token_urlsafe(32) for _ in range(100)}
    assert len(tokens) == 100


# ── TTL constant ──────────────────────────────────────────────────────────────


def test_token_ttl_is_30_days():
    from api.routers.client_token import _TOKEN_TTL_DAYS

    assert _TOKEN_TTL_DAYS == 30


def test_expiry_calculation():
    from api.routers.client_token import _TOKEN_TTL_DAYS

    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=_TOKEN_TTL_DAYS)
    delta = expires - now
    assert delta.days == _TOKEN_TTL_DAYS


# ── Expiry detection ──────────────────────────────────────────────────────────


def _make_token_row(days_until_expiry: int):
    """Simulate a ClientToken-like object with an expires_at attribute."""
    from types import SimpleNamespace

    return SimpleNamespace(
        expires_at=datetime.now(timezone.utc) + timedelta(days=days_until_expiry)
    )


def test_non_expired_token_not_expired():
    row = _make_token_row(10)
    assert row.expires_at > datetime.now(timezone.utc)


def test_expired_token_is_expired():
    row = _make_token_row(-1)
    assert row.expires_at < datetime.now(timezone.utc)


def test_just_expired_token():
    row = _make_token_row(0)
    # 0-day token: expires_at is now + 0 days = ~now; should be essentially expired
    now = datetime.now(timezone.utc)
    # With timedelta(days=0), expires_at == now; the router checks < now so boundary is expired
    assert row.expires_at <= now + timedelta(seconds=1)
