"""Unit tests for api/services/claims_service.py — ClaimsService.

Pure static tests — uses MagicMock DB; no infrastructure required.
"""

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from api.db import Claim, ClaimStatus, Policy
from api.domain.exceptions import NotFoundError
from api.services.claims_service import ClaimsService


# ── helpers ───────────────────────────────────────────────────────────────────


def _mock_db():
    return MagicMock()


def _mock_policy(**kwargs):
    p = MagicMock(spec=Policy)
    p.id = kwargs.get("id", 5)
    p.firm_id = kwargs.get("firm_id", 10)
    return p


def _mock_claim(**kwargs):
    c = MagicMock(spec=Claim)
    c.id = kwargs.get("id", 1)
    c.orgnr = kwargs.get("orgnr", "123456789")
    c.firm_id = kwargs.get("firm_id", 10)
    c.policy_id = kwargs.get("policy_id", 5)
    c.status = kwargs.get("status", ClaimStatus.open)
    return c


def _claim_in(**kwargs):
    return SimpleNamespace(
        policy_id=kwargs.get("policy_id", 5),
        claim_number=kwargs.get("claim_number", "CLM-001"),
        incident_date=kwargs.get("incident_date", date(2026, 1, 15)),
        reported_date=kwargs.get("reported_date", date(2026, 1, 20)),
        status=kwargs.get("status", "open"),
        description=kwargs.get("description", "Water damage"),
        estimated_amount_nok=kwargs.get("estimated_amount_nok", 50_000.0),
        insurer_contact=kwargs.get("insurer_contact", None),
        notes=kwargs.get("notes", None),
    )


def _db_with_policy_and_claim(policy=None, claim=None):
    """Return a mock DB that yields a policy on first query and claim on second."""
    db = _mock_db()
    policy = policy or _mock_policy()
    claim = claim or _mock_claim()
    db.query.return_value.filter.return_value.first.side_effect = [policy, claim]
    return db


# ── list_by_orgnr ─────────────────────────────────────────────────────────────


def test_list_by_orgnr_returns_results():
    db = _mock_db()
    claims = [_mock_claim(), _mock_claim(id=2)]
    db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = claims
    result = ClaimsService(db).list_by_orgnr("123456789", 10)
    assert result == claims


def test_list_by_orgnr_default_pagination():
    db = _mock_db()
    db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
    ClaimsService(db).list_by_orgnr("123456789", 10)
    chain = db.query.return_value.filter.return_value.order_by.return_value
    chain.offset.assert_called_once_with(0)
    chain.offset.return_value.limit.assert_called_once_with(100)


# ── list_by_policy ────────────────────────────────────────────────────────────


def test_list_by_policy_returns_results():
    db = _mock_db()
    claims = [_mock_claim()]
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
        claims
    )
    result = ClaimsService(db).list_by_policy(5, 10)
    assert result == claims


# ── create ────────────────────────────────────────────────────────────────────


def test_create_validates_policy_exists():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = _mock_policy()
    ClaimsService(db).create("123456789", 10, _claim_in())
    # First query must be for Policy
    db.query.assert_any_call(Policy)


def test_create_raises_not_found_when_policy_missing():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(NotFoundError, match="Policy"):
        ClaimsService(db).create("123456789", 10, _claim_in(policy_id=999))


def test_create_adds_to_db_and_commits():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = _mock_policy()
    ClaimsService(db).create("123456789", 10, _claim_in())
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_create_sets_orgnr():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = _mock_policy()
    ClaimsService(db).create("987654321", 10, _claim_in())
    added = db.add.call_args[0][0]
    assert added.orgnr == "987654321"


def test_create_sets_firm_id():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = _mock_policy()
    ClaimsService(db).create("123456789", 42, _claim_in())
    added = db.add.call_args[0][0]
    assert added.firm_id == 42


def test_create_parses_status_enum():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = _mock_policy()
    ClaimsService(db).create("123456789", 10, _claim_in(status="open"))
    added = db.add.call_args[0][0]
    assert added.status == ClaimStatus.open


def test_create_sets_timestamps():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = _mock_policy()
    before = datetime.now(timezone.utc)
    ClaimsService(db).create("123456789", 10, _claim_in())
    added = db.add.call_args[0][0]
    assert added.created_at >= before
    assert added.updated_at >= before


def test_create_sets_description():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = _mock_policy()
    ClaimsService(db).create("123456789", 10, _claim_in(description="Fire damage"))
    added = db.add.call_args[0][0]
    assert added.description == "Fire damage"


# ── update ────────────────────────────────────────────────────────────────────


def test_update_sets_field_on_claim():
    claim = _mock_claim()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = claim
    body = SimpleNamespace(
        model_dump=lambda exclude_none: {"description": "Updated description"}
    )
    ClaimsService(db).update(1, 10, body)
    assert claim.description == "Updated description"


def test_update_commits():
    claim = _mock_claim()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = claim
    body = SimpleNamespace(model_dump=lambda exclude_none: {"notes": "note"})
    ClaimsService(db).update(1, 10, body)
    db.commit.assert_called_once()


def test_update_raises_not_found_when_missing():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    body = SimpleNamespace(model_dump=lambda exclude_none: {})
    with pytest.raises(NotFoundError):
        ClaimsService(db).update(999, 10, body)


def test_update_parses_status_string():
    claim = _mock_claim()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = claim
    body = SimpleNamespace(model_dump=lambda exclude_none: {"status": "settled"})
    ClaimsService(db).update(1, 10, body)
    assert claim.status == ClaimStatus.settled


def test_update_stamps_updated_at():
    claim = _mock_claim()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = claim
    body = SimpleNamespace(model_dump=lambda exclude_none: {})
    before = datetime.now(timezone.utc)
    ClaimsService(db).update(1, 10, body)
    assert claim.updated_at >= before


# ── delete ────────────────────────────────────────────────────────────────────


def test_delete_calls_db_delete():
    claim = _mock_claim()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = claim
    ClaimsService(db).delete(1, 10)
    db.delete.assert_called_once_with(claim)


def test_delete_commits():
    claim = _mock_claim()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = claim
    ClaimsService(db).delete(1, 10)
    db.commit.assert_called_once()


def test_delete_raises_not_found_when_missing():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(NotFoundError):
        ClaimsService(db).delete(999, 10)


# ── _parse_status ─────────────────────────────────────────────────────────────


def test_parse_status_open():
    assert ClaimsService._parse_status("open") == ClaimStatus.open


def test_parse_status_settled():
    assert ClaimsService._parse_status("settled") == ClaimStatus.settled


def test_parse_status_in_review():
    assert ClaimsService._parse_status("in_review") == ClaimStatus.in_review


def test_parse_status_rejected():
    assert ClaimsService._parse_status("rejected") == ClaimStatus.rejected


def test_parse_status_invalid_raises():
    with pytest.raises(NotFoundError, match="Unknown claim status"):
        ClaimsService._parse_status("nonexistent")
