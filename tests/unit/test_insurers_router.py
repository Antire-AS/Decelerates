"""Unit tests for api/routers/insurers.py.

Calls endpoint functions directly with mocked InsurerService + db. Verifies
the two _serialize_* shapes (insurer + submission) and NotFoundError → 404
conversion across all six 404 paths. The InsurerService itself has its own
test suite.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from api.domain.exceptions import NotFoundError
from api.routers.insurers import (
    _serialize_insurer,
    _serialize_submission,
    create_insurer,
    create_submission,
    delete_insurer,
    delete_submission,
    draft_submission_email,
    get_win_loss_summary,
    list_insurers,
    list_submissions,
    match_appetite,
    update_insurer,
    update_submission,
)


def _user(firm_id=1, email="broker@test.no"):
    return SimpleNamespace(firm_id=firm_id, email=email)


def _insurer_row(id=1, name="If Skadeforsikring", appetite=None):
    r = MagicMock()
    r.id = id
    r.firm_id = 1
    r.name = name
    r.org_number = "910508192"
    r.contact_name = "Ola Nordmann"
    r.contact_email = "ola@if.no"
    r.contact_phone = "+47 12345678"
    r.appetite = appetite
    r.notes = "Norway-based, focuses on SMB"
    r.created_at = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    return r


def _submission_row(id=1, insurer_id=1, premium=100000):
    r = MagicMock()
    r.id = id
    r.orgnr = "123456789"
    r.insurer_id = insurer_id
    r.product_type = "Bedriftsansvar"
    r.requested_at = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    r.status = SimpleNamespace(value="quoted")
    r.premium_offered_nok = premium
    r.notes = None
    r.created_by_email = "broker@test.no"
    r.created_at = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    return r


# ── _serialize_insurer ────────────────────────────────────────────────────────


def test_serialize_insurer_returns_full_dict():
    row = _insurer_row()
    result = _serialize_insurer(row)
    assert result["id"] == 1
    assert result["name"] == "If Skadeforsikring"
    assert result["appetite"] == []  # None becomes []
    assert result["created_at"] == "2025-06-01T12:00:00+00:00"


def test_serialize_insurer_preserves_appetite_list():
    row = _insurer_row(appetite=["Bedriftsansvar", "Cyber"])
    result = _serialize_insurer(row)
    assert result["appetite"] == ["Bedriftsansvar", "Cyber"]


def test_serialize_insurer_handles_null_created_at():
    row = _insurer_row()
    row.created_at = None
    result = _serialize_insurer(row)
    assert result["created_at"] is None


# ── _serialize_submission ─────────────────────────────────────────────────────


def test_serialize_submission_includes_insurer_name():
    row = _submission_row()
    result = _serialize_submission(row, insurer_name="If")
    assert result["insurer_name"] == "If"
    assert result["status"] == "quoted"
    assert result["premium_offered_nok"] == 100000


def test_serialize_submission_handles_null_status():
    row = _submission_row()
    row.status = None
    result = _serialize_submission(row, insurer_name="If")
    assert result["status"] == "pending"  # default for null status


def test_serialize_submission_accepts_none_insurer_name():
    row = _submission_row()
    result = _serialize_submission(row, insurer_name=None)
    assert result["insurer_name"] is None


# ── Insurer CRUD ──────────────────────────────────────────────────────────────


def test_list_insurers_serializes_rows():
    svc = MagicMock()
    svc.list_insurers.return_value = [_insurer_row(id=1), _insurer_row(id=2)]
    result = list_insurers(user=_user(firm_id=42), svc=svc)
    assert len(result) == 2
    svc.list_insurers.assert_called_once_with(42)


def test_create_insurer_returns_serialized_row():
    svc = MagicMock()
    svc.create_insurer.return_value = _insurer_row(id=99)
    body = MagicMock()
    body.model_dump.return_value = {"name": "New Insurer"}
    result = create_insurer(body=body, user=_user(), svc=svc, db=MagicMock())
    assert result["id"] == 99
    svc.create_insurer.assert_called_once_with(1, {"name": "New Insurer"})


def test_update_insurer_returns_serialized_row():
    svc = MagicMock()
    svc.update_insurer.return_value = _insurer_row(id=7)
    body = MagicMock()
    body.model_dump.return_value = {"name": "Updated"}
    result = update_insurer(
        insurer_id=7, body=body, user=_user(), svc=svc, db=MagicMock()
    )
    assert result["id"] == 7


def test_update_insurer_raises_404_when_not_found():
    svc = MagicMock()
    svc.update_insurer.side_effect = NotFoundError("missing")
    body = MagicMock()
    body.model_dump.return_value = {}
    with pytest.raises(HTTPException) as exc:
        update_insurer(insurer_id=999, body=body, user=_user(), svc=svc, db=MagicMock())
    assert exc.value.status_code == 404


def test_delete_insurer_calls_service():
    svc = MagicMock()
    delete_insurer(insurer_id=7, user=_user(), svc=svc, db=MagicMock())
    svc.delete_insurer.assert_called_once_with(1, 7)


def test_delete_insurer_raises_404_when_not_found():
    svc = MagicMock()
    svc.delete_insurer.side_effect = NotFoundError("missing")
    with pytest.raises(HTTPException) as exc:
        delete_insurer(insurer_id=999, user=_user(), svc=svc, db=MagicMock())
    assert exc.value.status_code == 404


# ── Submission CRUD ───────────────────────────────────────────────────────────


def test_list_submissions_returns_enriched_serialized_list():
    svc = MagicMock()
    svc.list_submissions_enriched.return_value = [
        (_submission_row(id=1), "If"),
        (_submission_row(id=2), "Tryg"),
    ]
    result = list_submissions(orgnr="123", user=_user(), svc=svc)
    assert len(result) == 2
    assert result[0]["insurer_name"] == "If"
    assert result[1]["insurer_name"] == "Tryg"


def test_create_submission_resolves_insurer_name():
    svc = MagicMock()
    svc.create_submission.return_value = _submission_row(id=42, insurer_id=7)
    db = MagicMock()
    insurer = MagicMock()
    insurer.name = "If"
    db.query.return_value.filter.return_value.first.return_value = insurer
    body = MagicMock()
    body.model_dump.return_value = {"insurer_id": 7, "product_type": "Cyber"}
    result = create_submission(orgnr="123", body=body, user=_user(), svc=svc, db=db)
    assert result["id"] == 42
    assert result["insurer_name"] == "If"


def test_create_submission_handles_missing_insurer():
    svc = MagicMock()
    svc.create_submission.return_value = _submission_row(id=42, insurer_id=999)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    body = MagicMock()
    body.model_dump.return_value = {}
    result = create_submission(orgnr="123", body=body, user=_user(), svc=svc, db=db)
    assert result["insurer_name"] is None


def test_update_submission_returns_serialized_row():
    svc = MagicMock()
    svc.update_submission.return_value = _submission_row(id=7)
    db = MagicMock()
    insurer = MagicMock()
    insurer.name = "If"
    db.query.return_value.filter.return_value.first.return_value = insurer
    body = MagicMock()
    body.model_dump.return_value = {"status": "won"}
    result = update_submission(submission_id=7, body=body, user=_user(), svc=svc, db=db)
    assert result["id"] == 7
    assert result["insurer_name"] == "If"


def test_update_submission_raises_404_when_not_found():
    svc = MagicMock()
    svc.update_submission.side_effect = NotFoundError("missing")
    db = MagicMock()
    body = MagicMock()
    body.model_dump.return_value = {}
    with pytest.raises(HTTPException) as exc:
        update_submission(submission_id=999, body=body, user=_user(), svc=svc, db=db)
    assert exc.value.status_code == 404


def test_delete_submission_calls_service():
    svc = MagicMock()
    delete_submission(submission_id=7, user=_user(), svc=svc, db=MagicMock())
    svc.delete_submission.assert_called_once_with(1, 7)


def test_delete_submission_raises_404_when_not_found():
    svc = MagicMock()
    svc.delete_submission.side_effect = NotFoundError("missing")
    with pytest.raises(HTTPException) as exc:
        delete_submission(submission_id=999, user=_user(), svc=svc, db=MagicMock())
    assert exc.value.status_code == 404


# ── Analytics ─────────────────────────────────────────────────────────────────


def test_match_appetite_returns_serialized_insurers():
    svc = MagicMock()
    svc.match_appetite.return_value = [_insurer_row(id=1), _insurer_row(id=2)]
    result = match_appetite(product_type="Cyber", user=_user(), svc=svc)
    assert len(result) == 2
    svc.match_appetite.assert_called_once_with(1, "Cyber")


def test_get_win_loss_summary_returns_service_result():
    svc = MagicMock()
    svc.get_win_loss_summary.return_value = {"won": 5, "lost": 2, "pending": 3}
    result = get_win_loss_summary(user=_user(), svc=svc)
    assert result["won"] == 5
    svc.get_win_loss_summary.assert_called_once_with(1)


def test_draft_submission_email_returns_payload():
    svc = MagicMock()
    svc.draft_submission_email.return_value = "Hei, vi ønsker å innhente tilbud..."
    result = draft_submission_email(
        submission_id=7, user=_user(), svc=svc, db=MagicMock()
    )
    assert result["submission_id"] == 7
    assert "Hei" in result["draft_email"]


def test_draft_submission_email_raises_404_when_not_found():
    svc = MagicMock()
    svc.draft_submission_email.side_effect = NotFoundError("missing")
    with pytest.raises(HTTPException) as exc:
        draft_submission_email(submission_id=999, user=_user(), svc=svc, db=MagicMock())
    assert exc.value.status_code == 404
