"""Integration-test helpers — multi-firm auth client wrapper.

When two `TestClient`s with different `get_current_user` overrides are
constructed in the same test, both fixtures write to the same
`app.dependency_overrides[get_current_user]` slot — the second one wins
and BOTH clients end up acting as the second firm. To avoid that, the
user identity for each request is read from a contextvar that the
`AuthClient` wrapper sets per-call.

This file also contains a small but critical session-scoped fixture that
evicts the MagicMock-stubbed `api.rag_chain` many unit tests install via
`sys.modules.setdefault(...)`. Without this, integration tests pick up
the fake module, `chunk_text(...)` returns a MagicMock that iterates as
empty, and /org/{orgnr}/ingest-knowledge silently persists 0 chunks.
"""

import contextvars
import sys

import pytest


@pytest.fixture(scope="session", autouse=True)
def _restore_real_rag_chain_for_integration():
    """Replace the unit-test MagicMock of api.rag_chain with the real module
    AND rebind its symbols on every already-imported caller.

    Unit tests run first (alphabetical dir order) and install a MagicMock
    at `sys.modules["api.rag_chain"]` so they don't need the langchain
    install. By the time integration tests run, every caller
    (`api.services.rag`, `api.routers.knowledge`) has already bound the
    MagicMock's `chunk_text`, `embed_chunks`, `build_rag_chain` into its
    own namespace. Popping the module isn't enough — we have to reimport
    the real module and patch the bindings on each caller.

    Without this, /org/{orgnr}/ingest-knowledge silently stores 0 chunks
    (the MagicMock chunk_text iterates empty) and the RAG chat path
    returns a MagicMock as the answer.
    """
    import importlib

    sys.modules.pop("api.rag_chain", None)
    real = importlib.import_module("api.rag_chain")
    for caller_name in ("api.services.rag", "api.routers.knowledge"):
        caller = sys.modules.get(caller_name)
        if caller is None:
            continue
        for sym in ("chunk_text", "embed_chunks", "build_rag_chain"):
            if hasattr(real, sym):
                setattr(caller, sym, getattr(real, sym))
    yield

_TEST_USER_CTX: contextvars.ContextVar = contextvars.ContextVar(
    "test_user", default=None
)


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
