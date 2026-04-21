"""Integration sweep — every `@limiter.limit(...)` decorator must actually
trigger 429 when exceeded.

slowapi decorators are easy to mis-wire: if the function signature doesn't
include a `request: Request` parameter slowapi silently no-ops the limit
and the route allows unlimited traffic. This test proves the wiring is
correct by hitting the endpoint N+1 times and asserting the final call
returns 429.

We deliberately pick routes with:
- a low limit (fast to exceed inside a test)
- cheap failure path (404 short-circuits don't waste LLM/DB budget)
- idempotent GET where possible (safe to spam)

Run: `TEST_DATABASE_URL=postgresql://... uv run python -m pytest
tests/integration/test_rate_limits.py -v`
"""

import os

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="set TEST_DATABASE_URL=postgresql://... to run integration tests",
)

# Table-driven coverage. Each entry: (method, path, limit_per_minute).
# The route must be safe to spam at `limit + 1` times (non-mutating / 404
# short-circuit / no LLM spend). Routes that require complex body setup
# are intentionally omitted — we only need enough coverage to prove the
# slowapi wiring works. If a decorator is mis-configured, a single
# un-limited route in the table flushes out the same bug class.
_LIMITED_ROUTES = [
    # GET /tenders/{id} is firm-scoped; 999999 → 404, but 404 still counts
    # toward the bucket. Limit 30/min — 31 calls settle in under 2s.
    ("GET", "/tenders/999999", 30),
    # GET /coverage/{id} same pattern — firm-scoped 404 counts.
    ("GET", "/coverage/999999", 30),
]


@pytest.fixture
def app_with_stub_user(test_db):
    """Mount the app with get_db overridden and a canonical test user
    injected so the route short-circuits on the 404 check before hitting
    any real business logic."""
    from api.auth import CurrentUser, get_current_user
    from api.dependencies import get_db
    from api.main import app

    app.dependency_overrides[get_db] = lambda: test_db
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        email="ratelimit@test",
        name="RL Bot",
        oid="rl-oid",
        firm_id=1,
    )
    yield app
    app.dependency_overrides.clear()


@pytest.mark.parametrize("method,path,limit", _LIMITED_ROUTES)
def test_rate_limit_triggers_429(app_with_stub_user, method, path, limit):
    """Hit the route `limit + 1` times; the final one must be 429. Reset the
    limiter's in-memory store between parametrize cases so the tests are
    independent (slowapi defaults to an in-memory MovingWindow store; we
    empty it via a direct reset to avoid cross-parameter pollution)."""
    from api.limiter import limiter

    # Fresh bucket per test case.
    limiter.reset()

    client = TestClient(app_with_stub_user)
    for i in range(limit):
        resp = client.request(method, path)
        assert resp.status_code != 429, (
            f"early 429 at {i + 1}/{limit} on {path}; limit wiring may be off"
        )

    final = client.request(method, path)
    assert final.status_code == 429, (
        f"expected 429 after {limit + 1} calls to {path}, "
        f"got {final.status_code} — slowapi decorator likely mis-wired"
    )
