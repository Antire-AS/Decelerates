"""Unit tests for api/routers/audit.py — all three endpoints.

Calls endpoint functions directly with MagicMock DB + user; no infrastructure required.
"""
import csv
import io
import json
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from api.routers.audit import export_audit_csv, get_audit_log, get_audit_log_global


# ── helpers ───────────────────────────────────────────────────────────────────

def _mock_user(email="broker@test.no"):
    u = SimpleNamespace(email=email, firm_id=1)
    return u


def _audit_row(action="policy.create", orgnr="123456789", actor_email="broker@test.no",
               detail=None, row_id=1):
    r = MagicMock()
    r.id = row_id
    r.action = action
    r.orgnr = orgnr
    r.actor_email = actor_email
    r.detail = json.dumps(detail) if detail else None
    r.created_at = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    return r


def _mock_db(rows=None):
    db = MagicMock()
    mock_q = db.query.return_value
    mock_q.order_by.return_value = mock_q
    mock_q.filter.return_value = mock_q
    mock_q.limit.return_value = mock_q
    mock_q.offset.return_value = mock_q
    mock_q.all.return_value = rows or []
    mock_q.count.return_value = len(rows or [])
    return db


# All paginated calls share these defaults so we don't have to repeat the
# Optional[…] = None spam in every test. Update plan §🟢 #13.
_PAGE_KW = dict(
    action=None, actor_email=None, from_date=None, to_date=None, offset=0,
)


# ── GET /audit (global) ───────────────────────────────────────────────────────

def test_get_audit_log_global_returns_paginated():
    rows = [_audit_row(row_id=1), _audit_row(action="claim.create", row_id=2)]
    db = _mock_db(rows)
    result = get_audit_log_global(orgnr=None, limit=100, db=db, user=_mock_user(), **_PAGE_KW)
    assert isinstance(result, dict)
    assert len(result["items"]) == 2
    assert result["total"] == 2
    assert result["has_more"] is False


def test_get_audit_log_global_shape():
    db = _mock_db([_audit_row()])
    result = get_audit_log_global(orgnr=None, limit=100, db=db, user=_mock_user(), **_PAGE_KW)
    entry = result["items"][0]
    assert "id" in entry
    assert "orgnr" in entry
    assert "action" in entry
    assert "actor_email" in entry
    assert "created_at" in entry


def test_get_audit_log_global_empty():
    db = _mock_db([])
    result = get_audit_log_global(orgnr=None, limit=100, db=db, user=_mock_user(), **_PAGE_KW)
    assert result["items"] == []
    assert result["total"] == 0


# ── GET /audit/{orgnr} ────────────────────────────────────────────────────────

def test_get_audit_log_orgnr_returns_paginated():
    rows = [_audit_row(orgnr="987654321"), _audit_row(orgnr="987654321", row_id=2)]
    db = _mock_db(rows)
    result = get_audit_log(orgnr="987654321", limit=50, db=db, user=_mock_user(), **_PAGE_KW)
    assert len(result["items"]) == 2


def test_get_audit_log_orgnr_shape():
    db = _mock_db([_audit_row()])
    result = get_audit_log(orgnr="123456789", limit=50, db=db, user=_mock_user(), **_PAGE_KW)
    entry = result["items"][0]
    assert "id" in entry
    assert "action" in entry
    assert "actor_email" in entry
    assert "created_at" in entry
    assert "detail" in entry


def test_get_audit_log_orgnr_empty():
    db = _mock_db([])
    result = get_audit_log(orgnr="000000000", limit=50, db=db, user=_mock_user(), **_PAGE_KW)
    assert result["items"] == []
    assert result["total"] == 0


# ── Pagination & filters (plan §🟢 #13) ──────────────────────────────────────

def test_get_audit_log_returns_has_more_when_total_exceeds_page():
    db = _mock_db([_audit_row(row_id=1)])
    db.query.return_value.count.return_value = 250
    result = get_audit_log_global(orgnr=None, limit=100, db=db, user=_mock_user(), **_PAGE_KW)
    assert result["total"] == 250
    assert result["has_more"] is True


def test_get_audit_log_filters_chain_when_provided():
    """Each filter param adds a .filter() call. We only assert filter() was
    called multiple times (vs once for the order_by); exact predicates would
    couple the test to SQLAlchemy internals."""
    db = _mock_db([])
    get_audit_log_global(
        orgnr="123456789", action="policy.create",
        actor_email="b@x.no", from_date=date(2026, 1, 1), to_date=date(2026, 12, 31),
        limit=100, offset=0, db=db, user=_mock_user(),
    )
    # 5 filter predicates + the .order_by is on a chain — filter() was called.
    assert db.query.return_value.filter.call_count >= 5


# ── GET /audit/export (CSV) ───────────────────────────────────────────────────

def _read_body(streaming_response) -> bytes:
    """Consume a StreamingResponse body_iterator (may be async or sync)."""
    import asyncio

    async def _drain():
        chunks = []
        async for chunk in streaming_response.body_iterator:
            chunks.append(chunk)
        return b"".join(chunks)

    return asyncio.run(_drain())


def _parse_csv(streaming_response) -> list[dict]:
    content = _read_body(streaming_response)
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


def test_export_audit_csv_returns_streaming_response():
    from fastapi.responses import StreamingResponse
    db = _mock_db([_audit_row()])
    response = export_audit_csv(orgnr=None, action=None, actor_email=None, from_date=None, to_date=None, limit=500, db=db, user=_mock_user())
    assert isinstance(response, StreamingResponse)
    assert "text/csv" in response.media_type


def test_export_audit_csv_content_type_header():
    db = _mock_db([_audit_row()])
    response = export_audit_csv(orgnr=None, action=None, actor_email=None, from_date=None, to_date=None, limit=500, db=db, user=_mock_user())
    assert response.media_type == "text/csv"


def test_export_audit_csv_has_bom_for_excel():
    """CSV must start with UTF-8 BOM (\xef\xbb\xbf) for Excel compatibility."""
    db = _mock_db([_audit_row()])
    response = export_audit_csv(orgnr=None, action=None, actor_email=None, from_date=None, to_date=None, limit=500, db=db, user=_mock_user())
    content = _read_body(response)
    assert content[:3] == b"\xef\xbb\xbf", "Missing UTF-8 BOM"


def test_export_audit_csv_correct_columns():
    db = _mock_db([_audit_row()])
    response = export_audit_csv(orgnr=None, action=None, actor_email=None, from_date=None, to_date=None, limit=500, db=db, user=_mock_user())
    rows = _parse_csv(response)
    assert len(rows) == 1
    assert set(rows[0].keys()) == {"id", "created_at", "orgnr", "action", "actor_email", "detail"}


def test_export_audit_csv_correct_values():
    row = _audit_row(action="policy.create", orgnr="123456789", actor_email="a@b.no")
    db = _mock_db([row])
    response = export_audit_csv(orgnr=None, action=None, actor_email=None, from_date=None, to_date=None, limit=500, db=db, user=_mock_user())
    rows = _parse_csv(response)
    assert rows[0]["action"] == "policy.create"
    assert rows[0]["orgnr"] == "123456789"
    assert rows[0]["actor_email"] == "a@b.no"


def test_export_audit_csv_orgnr_filter_passes_to_query():
    db = _mock_db([])
    export_audit_csv(
        orgnr="999888777", action=None, actor_email=None,
        from_date=None, to_date=None, limit=500, db=db, user=_mock_user(),
    )
    # When orgnr is supplied the query chain calls .filter() an extra time
    assert db.query.return_value.filter.called


def test_export_audit_csv_empty_returns_header_only():
    db = _mock_db([])
    response = export_audit_csv(orgnr=None, action=None, actor_email=None, from_date=None, to_date=None, limit=500, db=db, user=_mock_user())
    rows = _parse_csv(response)
    assert rows == []
