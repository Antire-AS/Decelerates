"""Integration-test helpers — multi-firm auth client wrapper.

When two `TestClient`s with different `get_current_user` overrides are
constructed in the same test, both fixtures write to the same
`app.dependency_overrides[get_current_user]` slot — the second one wins
and BOTH clients end up acting as the second firm. To avoid that, the
user identity for each request is read from a contextvar that the
`AuthClient` wrapper sets per-call.
"""
import contextvars

_TEST_USER_CTX: contextvars.ContextVar = contextvars.ContextVar("test_user", default=None)


def make_user(email: str, oid: str, firm_id: int):
    from api.auth import CurrentUser
    return CurrentUser(email=email, name="Test", oid=oid, firm_id=firm_id)


def resolve_user_factory(default_email: str, default_oid: str, default_firm_id: int):
    """Returns a `get_current_user` override that prefers the contextvar's user."""
    def _resolve_user():
        u = _TEST_USER_CTX.get()
        return u or make_user(default_email, default_oid, default_firm_id)
    return _resolve_user


class AuthClient:
    """TestClient wrapper that swaps the active user via a contextvar before each call."""

    def __init__(self, client, user):
        self._c = client
        self._u = user

    def _wrap(self, method_name: str):
        def _call(*args, **kwargs):
            token = _TEST_USER_CTX.set(self._u)
            try:
                return getattr(self._c, method_name)(*args, **kwargs)
            finally:
                _TEST_USER_CTX.reset(token)
        return _call

    def __getattr__(self, name):
        if name in ("get", "post", "put", "delete", "patch", "head", "options"):
            return self._wrap(name)
        return getattr(self._c, name)
