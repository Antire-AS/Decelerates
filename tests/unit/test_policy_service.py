"""Unit tests for api/services/policy_service.py — PolicyService.

Pure static tests — uses MagicMock DB; no infrastructure required.
"""

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from api.db import Policy, PolicyStatus, RenewalStage
from api.domain.exceptions import NotFoundError, ValidationError
from api.services.policy_service import PolicyService


# ── helpers ───────────────────────────────────────────────────────────────────


def _mock_db():
    return MagicMock()


def _mock_policy(**kwargs):
    p = MagicMock(spec=Policy)
    p.id = kwargs.get("id", 1)
    p.orgnr = kwargs.get("orgnr", "123456789")
    p.firm_id = kwargs.get("firm_id", 10)
    p.status = kwargs.get("status", PolicyStatus.active)
    p.renewal_stage = kwargs.get("renewal_stage", RenewalStage.not_started)
    p.renewal_date = kwargs.get("renewal_date", date(2027, 1, 1))
    p.insurer = kwargs.get("insurer", "Gjensidige")
    p.product_type = kwargs.get("product_type", "Ting")
    p.annual_premium_nok = kwargs.get("annual_premium_nok", 25_000.0)
    p.last_renewal_notified_days = kwargs.get("last_renewal_notified_days", None)
    return p


def _policy_in(**kwargs):
    return SimpleNamespace(
        contact_person_id=kwargs.get("contact_person_id", None),
        policy_number=kwargs.get("policy_number", "POL-001"),
        insurer=kwargs.get("insurer", "Gjensidige"),
        product_type=kwargs.get("product_type", "Ting"),
        coverage_amount_nok=kwargs.get("coverage_amount_nok", 1_000_000.0),
        annual_premium_nok=kwargs.get("annual_premium_nok", 25_000.0),
        start_date=kwargs.get("start_date", date(2026, 1, 1)),
        renewal_date=kwargs.get("renewal_date", date(2027, 1, 1)),
        status=kwargs.get("status", "active"),
        renewal_stage=kwargs.get("renewal_stage", None),
        notes=kwargs.get("notes", None),
        commission_rate_pct=kwargs.get("commission_rate_pct", None),
        commission_amount_nok=kwargs.get("commission_amount_nok", None),
    )


def _policy_update(**kwargs):
    return SimpleNamespace(
        **{k: v for k, v in kwargs.items()},
        model_dump=lambda exclude_none=False: kwargs,
    )


# ── list_by_orgnr ─────────────────────────────────────────────────────────────


def test_list_by_orgnr_returns_query_results():
    db = _mock_db()
    policies = [_mock_policy(), _mock_policy(id=2)]
    db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = policies
    result = PolicyService(db).list_by_orgnr("123456789", 10)
    assert result == policies


def test_list_by_orgnr_default_pagination():
    db = _mock_db()
    db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
    PolicyService(db).list_by_orgnr("123456789", 10)
    chain = db.query.return_value.filter.return_value.order_by.return_value
    chain.offset.assert_called_once_with(0)
    chain.offset.return_value.limit.assert_called_once_with(100)


# ── list_by_firm ──────────────────────────────────────────────────────────────


def test_list_by_firm_returns_query_results():
    db = _mock_db()
    policies = [_mock_policy()]
    db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = policies
    result = PolicyService(db).list_by_firm(10)
    assert result == policies


# ── create ────────────────────────────────────────────────────────────────────


def test_create_calls_add_and_commit():
    db = _mock_db()
    PolicyService(db).create("123456789", 10, _policy_in())
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_create_sets_orgnr():
    db = _mock_db()
    PolicyService(db).create("123456789", 10, _policy_in())
    added = db.add.call_args[0][0]
    assert added.orgnr == "123456789"


def test_create_sets_firm_id():
    db = _mock_db()
    PolicyService(db).create("123456789", 42, _policy_in())
    added = db.add.call_args[0][0]
    assert added.firm_id == 42


def test_create_sets_insurer():
    db = _mock_db()
    PolicyService(db).create("123456789", 10, _policy_in(insurer="If Skadeforsikring"))
    added = db.add.call_args[0][0]
    assert added.insurer == "If Skadeforsikring"


def test_create_parses_status_enum():
    db = _mock_db()
    PolicyService(db).create("123456789", 10, _policy_in(status="active"))
    added = db.add.call_args[0][0]
    assert added.status == PolicyStatus.active


def test_create_defaults_renewal_stage_when_none():
    db = _mock_db()
    PolicyService(db).create("123456789", 10, _policy_in(renewal_stage=None))
    added = db.add.call_args[0][0]
    assert added.renewal_stage == RenewalStage.not_started


def test_create_parses_renewal_stage_when_provided():
    db = _mock_db()
    PolicyService(db).create("123456789", 10, _policy_in(renewal_stage="quoted"))
    added = db.add.call_args[0][0]
    assert added.renewal_stage == RenewalStage.quoted


def test_create_sets_timestamps():
    db = _mock_db()
    before = datetime.now(timezone.utc)
    PolicyService(db).create("123456789", 10, _policy_in())
    added = db.add.call_args[0][0]
    assert added.created_at >= before
    assert added.updated_at >= before


# ── update ────────────────────────────────────────────────────────────────────


def test_update_sets_field_on_policy():
    policy = _mock_policy()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = policy
    body = SimpleNamespace(model_dump=lambda exclude_none: {"insurer": "Codan"})
    PolicyService(db).update(1, 10, body)
    # PolicyService.update routes insurer through canonical_insurer_name
    # since UI audit F06 (2026-04-09); "Codan" → "Codan Forsikring".
    assert policy.insurer == "Codan Forsikring"


def test_update_commits():
    policy = _mock_policy()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = policy
    body = SimpleNamespace(model_dump=lambda exclude_none: {"notes": "updated"})
    PolicyService(db).update(1, 10, body)
    db.commit.assert_called_once()


def test_update_raises_not_found_when_missing():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    body = SimpleNamespace(model_dump=lambda exclude_none: {})
    with pytest.raises(NotFoundError):
        PolicyService(db).update(999, 10, body)


def test_update_parses_status_string():
    policy = _mock_policy()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = policy
    body = SimpleNamespace(model_dump=lambda exclude_none: {"status": "expired"})
    PolicyService(db).update(1, 10, body)
    assert policy.status == PolicyStatus.expired


def test_update_parses_renewal_stage_string():
    policy = _mock_policy()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = policy
    body = SimpleNamespace(
        model_dump=lambda exclude_none: {"renewal_stage": "accepted"}
    )
    PolicyService(db).update(1, 10, body)
    assert policy.renewal_stage == RenewalStage.accepted


def test_update_stamps_updated_at():
    policy = _mock_policy()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = policy
    body = SimpleNamespace(model_dump=lambda exclude_none: {})
    before = datetime.now(timezone.utc)
    PolicyService(db).update(1, 10, body)
    assert policy.updated_at >= before


# ── advance_renewal_stage ─────────────────────────────────────────────────────


def test_advance_renewal_stage_updates_stage():
    policy = _mock_policy()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = policy
    PolicyService(db).advance_renewal_stage(1, 10, "ready_to_quote")
    assert policy.renewal_stage == RenewalStage.ready_to_quote


def test_advance_renewal_stage_commits():
    policy = _mock_policy()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = policy
    PolicyService(db).advance_renewal_stage(1, 10, "quoted")
    db.commit.assert_called_once()


def test_advance_renewal_stage_raises_not_found():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(NotFoundError):
        PolicyService(db).advance_renewal_stage(999, 10, "quoted")


def test_advance_renewal_stage_invalid_stage_raises():
    policy = _mock_policy()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = policy
    with pytest.raises(ValidationError):
        PolicyService(db).advance_renewal_stage(1, 10, "nonexistent_stage")


# ── delete ────────────────────────────────────────────────────────────────────


def test_delete_calls_db_delete():
    policy = _mock_policy()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = policy
    PolicyService(db).delete(1, 10)
    db.delete.assert_called_once_with(policy)


def test_delete_commits():
    policy = _mock_policy()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = policy
    PolicyService(db).delete(1, 10)
    db.commit.assert_called_once()


def test_delete_raises_not_found_when_missing():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(NotFoundError):
        PolicyService(db).delete(999, 10)


# ── mark_renewal_notified ─────────────────────────────────────────────────────


def test_mark_renewal_notified_updates_and_commits():
    db = _mock_db()
    PolicyService(db).mark_renewal_notified(1, 30)
    db.query.return_value.filter.return_value.update.assert_called_once_with(
        {"last_renewal_notified_days": 30}
    )
    db.commit.assert_called_once()


# ── _parse_status ─────────────────────────────────────────────────────────────


def test_parse_status_active():
    assert PolicyService._parse_status("active") == PolicyStatus.active


def test_parse_status_expired():
    assert PolicyService._parse_status("expired") == PolicyStatus.expired


def test_parse_status_cancelled():
    assert PolicyService._parse_status("cancelled") == PolicyStatus.cancelled


def test_parse_status_invalid_raises_validation_error():
    with pytest.raises(ValidationError, match="Unknown policy status"):
        PolicyService._parse_status("unknown_status")


# ── _parse_renewal_stage ──────────────────────────────────────────────────────


def test_parse_renewal_stage_not_started():
    assert PolicyService._parse_renewal_stage("not_started") == RenewalStage.not_started


def test_parse_renewal_stage_accepted():
    assert PolicyService._parse_renewal_stage("accepted") == RenewalStage.accepted


def test_parse_renewal_stage_invalid_raises_validation_error():
    with pytest.raises(ValidationError, match="Unknown renewal stage"):
        PolicyService._parse_renewal_stage("bad_stage")
