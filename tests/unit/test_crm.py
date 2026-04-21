"""Unit tests for CRM services — PolicyService, ClaimsService, ActivityService, UserService.

All tests use a MagicMock DB session; no infrastructure required.
"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from api.db import (
    ClaimStatus,
    Policy,
    PolicyStatus,
    Claim,
    Activity,
    User,
    UserRole,
    BrokerFirm,
)
import pydantic
from api.domain.exceptions import ForbiddenError, NotFoundError, ValidationError
from api.schemas import (
    ActivityIn,
    ActivityUpdate,
    ClaimIn,
    ClaimUpdate,
    PolicyIn,
    PolicyUpdate,
    UserRoleUpdate,
)
from api.services.activity_service import ActivityService
from api.services.claims_service import ClaimsService
from api.services.policy_service import PolicyService
from api.services.user_service import UserService


# ── helpers ──────────────────────────────────────────────────────────────────


def _mock_db():
    return MagicMock()


def _policy(overrides=None):
    p = MagicMock(spec=Policy)
    p.id = 1
    p.orgnr = "123456789"
    p.firm_id = 1
    p.insurer = "If Skadeforsikring"
    p.product_type = "Eiendomsforsikring"
    p.policy_number = "POL-001"
    p.annual_premium_nok = 50_000.0
    p.coverage_amount_nok = 5_000_000.0
    p.start_date = date(2025, 1, 1)
    p.renewal_date = date.today() + timedelta(days=20)
    p.status = PolicyStatus.active
    p.contact_person_id = None
    p.notes = None
    p.document_url = None
    p.created_at = datetime.now(timezone.utc)
    p.updated_at = datetime.now(timezone.utc)
    if overrides:
        for k, v in overrides.items():
            setattr(p, k, v)
    return p


# ── PolicyService ─────────────────────────────────────────────────────────────


class TestPolicyServiceCreate:
    def test_create_returns_policy(self):
        db = _mock_db()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock(side_effect=lambda p: None)

        svc = PolicyService(db)
        body = PolicyIn(
            insurer="Gjensidige",
            product_type="Ansvarsforsikring",
            annual_premium_nok=30_000,
        )

        with patch.object(Policy, "__init__", return_value=None):
            svc.create("987654321", firm_id=1, body=body)

        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_create_unknown_status_raises(self):
        # Pydantic now validates status at schema construction time
        with pytest.raises(pydantic.ValidationError):
            PolicyIn(insurer="X", product_type="Y", status="nonexistent")


class TestPolicyServiceList:
    def test_list_by_orgnr_filters_firm(self):
        db = _mock_db()
        mock_q = db.query.return_value
        mock_q.filter.return_value = mock_q
        mock_q.order_by.return_value = mock_q
        mock_q.offset.return_value = mock_q
        mock_q.limit.return_value = mock_q
        mock_q.all.return_value = [_policy()]

        result = PolicyService(db).list_by_orgnr("123456789", firm_id=1)
        assert len(result) == 1

    def test_list_by_firm_returns_all(self):
        db = _mock_db()
        mock_q = db.query.return_value
        mock_q.filter.return_value = mock_q
        mock_q.order_by.return_value = mock_q
        mock_q.offset.return_value = mock_q
        mock_q.limit.return_value = mock_q
        mock_q.all.return_value = [_policy(), _policy()]

        assert len(PolicyService(db).list_by_firm(firm_id=1)) == 2


class TestPolicyServiceAdvanceRenewalStage:
    def test_advance_success(self):
        db = _mock_db()
        existing = _policy()
        mock_q = db.query.return_value
        mock_q.filter.return_value = mock_q
        mock_q.first.return_value = existing

        PolicyService(db).advance_renewal_stage(
            policy_id=1, firm_id=1, new_stage="ready_to_quote"
        )

        db.commit.assert_called_once()

    def test_advance_invalid_stage_raises(self):
        db = _mock_db()
        existing = _policy()
        mock_q = db.query.return_value
        mock_q.filter.return_value = mock_q
        mock_q.first.return_value = existing

        with pytest.raises(ValidationError):
            PolicyService(db).advance_renewal_stage(
                policy_id=1, firm_id=1, new_stage="bogus_stage"
            )

    def test_advance_not_found_raises(self):
        db = _mock_db()
        mock_q = db.query.return_value
        mock_q.filter.return_value = mock_q
        mock_q.first.return_value = None

        with pytest.raises(NotFoundError):
            PolicyService(db).advance_renewal_stage(
                policy_id=99, firm_id=1, new_stage="contacted"
            )


class TestPolicyServiceRenewals:
    def test_get_renewals_within_window(self):
        db = _mock_db()
        mock_q = db.query.return_value
        mock_q.filter.return_value = mock_q
        mock_q.order_by.return_value = mock_q
        mock_q.all.return_value = [_policy()]

        svc = PolicyService(db)
        result = svc.get_renewals(firm_id=1, days=30)

        assert len(result) == 1

    def test_get_renewals_empty_when_no_policies(self):
        db = _mock_db()
        mock_q = db.query.return_value
        mock_q.filter.return_value = mock_q
        mock_q.order_by.return_value = mock_q
        mock_q.all.return_value = []

        svc = PolicyService(db)
        assert svc.get_renewals(firm_id=1, days=30) == []


class TestPolicyServiceUpdate:
    def test_update_sets_fields(self):
        db = _mock_db()
        existing = _policy()
        mock_q = db.query.return_value
        mock_q.filter.return_value = mock_q
        mock_q.first.return_value = existing

        svc = PolicyService(db)
        body = PolicyUpdate(insurer="Fremtind", annual_premium_nok=60_000.0)
        svc.update(policy_id=1, firm_id=1, body=body)

        # Canonicalised since UI audit F06 (2026-04-09).
        assert existing.insurer == "Fremtind Forsikring"
        assert existing.annual_premium_nok == 60_000.0
        db.commit.assert_called_once()

    def test_update_not_found_raises(self):
        db = _mock_db()
        mock_q = db.query.return_value
        mock_q.filter.return_value = mock_q
        mock_q.first.return_value = None

        svc = PolicyService(db)
        with pytest.raises(NotFoundError):
            svc.update(policy_id=99, firm_id=1, body=PolicyUpdate())


class TestPolicyServiceDelete:
    def test_delete_calls_db_delete(self):
        db = _mock_db()
        existing = _policy()
        mock_q = db.query.return_value
        mock_q.filter.return_value = mock_q
        mock_q.first.return_value = existing

        PolicyService(db).delete(policy_id=1, firm_id=1)

        db.delete.assert_called_once_with(existing)
        db.commit.assert_called_once()

    def test_delete_not_found_raises(self):
        db = _mock_db()
        mock_q = db.query.return_value
        mock_q.filter.return_value = mock_q
        mock_q.first.return_value = None

        with pytest.raises(NotFoundError):
            PolicyService(db).delete(policy_id=99, firm_id=1)


# ── ClaimsService ─────────────────────────────────────────────────────────────


class TestClaimsService:
    def _claim(self):
        c = MagicMock(spec=Claim)
        c.id = 1
        c.orgnr = "123456789"
        c.firm_id = 1
        c.status = ClaimStatus.open
        c.created_at = datetime.now(timezone.utc)
        c.updated_at = datetime.now(timezone.utc)
        return c

    def test_create_validates_policy_ownership(self):
        db = _mock_db()
        mock_q = db.query.return_value
        mock_q.filter.return_value = mock_q
        mock_q.first.return_value = None  # policy not found

        svc = ClaimsService(db)
        body = ClaimIn(policy_id=99, status="open")
        with pytest.raises(NotFoundError):
            svc.create("123456789", firm_id=1, body=body)

    def test_update_status(self):
        db = _mock_db()
        existing = self._claim()
        mock_q = db.query.return_value
        mock_q.filter.return_value = mock_q
        mock_q.first.return_value = existing

        svc = ClaimsService(db)
        svc.update(claim_id=1, firm_id=1, body=ClaimUpdate(status="settled"))

        assert existing.status == ClaimStatus.settled
        db.commit.assert_called_once()

    def test_update_unknown_status_raises(self):
        # Pydantic now validates status at schema construction time
        with pytest.raises(pydantic.ValidationError):
            ClaimUpdate(status="bogus")

    def test_list_by_policy(self):
        db = _mock_db()
        mock_q = db.query.return_value
        mock_q.filter.return_value = mock_q
        mock_q.order_by.return_value = mock_q
        mock_q.all.return_value = [self._claim()]

        result = ClaimsService(db).list_by_policy(policy_id=1, firm_id=1)
        assert len(result) == 1

    def test_delete_removes_claim(self):
        db = _mock_db()
        existing = self._claim()
        mock_q = db.query.return_value
        mock_q.filter.return_value = mock_q
        mock_q.first.return_value = existing

        ClaimsService(db).delete(claim_id=1, firm_id=1)
        db.delete.assert_called_once_with(existing)


# ── ActivityService ───────────────────────────────────────────────────────────


class TestActivityService:
    def test_create_unknown_type_raises(self):
        db = _mock_db()
        svc = ActivityService(db)
        body = ActivityIn(activity_type="invalid_type", subject="Test")
        with pytest.raises(NotFoundError):
            svc.create("123456789", firm_id=1, created_by="user@test.com", body=body)

    def test_create_valid_type(self):
        db = _mock_db()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()

        svc = ActivityService(db)
        body = ActivityIn(activity_type="call", subject="Followed up on renewal")
        with patch.object(Activity, "__init__", return_value=None):
            svc.create("123456789", firm_id=1, created_by="user@test.com", body=body)

        db.add.assert_called_once()

    def test_list_respects_limit(self):
        db = _mock_db()
        mock_q = db.query.return_value
        mock_q.filter.return_value = mock_q
        mock_q.order_by.return_value = mock_q
        mock_q.limit.return_value = mock_q
        mock_q.all.return_value = []

        ActivityService(db).list_by_orgnr("123456789", firm_id=1, limit=10)
        mock_q.limit.assert_called_once_with(10)

    def test_update_not_found_raises(self):
        db = _mock_db()
        mock_q = db.query.return_value
        mock_q.filter.return_value = mock_q
        mock_q.first.return_value = None

        with pytest.raises(NotFoundError):
            ActivityService(db).update(99, firm_id=1, body=ActivityUpdate(subject="X"))

    def test_delete_removes_activity(self):
        db = _mock_db()
        act = MagicMock(spec=Activity)
        mock_q = db.query.return_value
        mock_q.filter.return_value = mock_q
        mock_q.first.return_value = act

        ActivityService(db).delete(activity_id=1, firm_id=1)
        db.delete.assert_called_once_with(act)
        db.commit.assert_called_once()

    def test_delete_not_found_raises(self):
        db = _mock_db()
        mock_q = db.query.return_value
        mock_q.filter.return_value = mock_q
        mock_q.first.return_value = None

        with pytest.raises(NotFoundError):
            ActivityService(db).delete(activity_id=99, firm_id=1)


# ── UserService ───────────────────────────────────────────────────────────────


class TestUserService:
    def _firm(self):
        f = MagicMock(spec=BrokerFirm)
        f.id = 1
        return f

    def _user(self, role=UserRole.broker):
        u = MagicMock(spec=User)
        u.id = 1
        u.firm_id = 1
        u.azure_oid = "some-oid"
        u.email = "user@test.com"
        u.name = "Test User"
        u.role = role
        u.created_at = datetime.now(timezone.utc)
        return u

    def test_get_or_create_returns_existing(self):
        db = _mock_db()
        existing = self._user()
        mock_q = db.query.return_value
        mock_q.filter.return_value = mock_q
        mock_q.first.return_value = existing

        result = UserService(db).get_or_create("some-oid", "user@test.com", "Test")
        assert result is existing
        db.add.assert_not_called()

    def test_get_or_create_provisions_new_user(self):
        db = _mock_db()
        calls = [
            None,
            self._firm(),
        ]  # first call (User lookup) → None, second (BrokerFirm) → firm
        mock_q = db.query.return_value
        mock_q.filter.return_value = mock_q
        mock_q.first.side_effect = calls

        UserService(db).get_or_create("new-oid", "new@test.com", "New User")
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_update_role_requires_admin(self):
        db = _mock_db()
        svc = UserService(db)
        with pytest.raises(ForbiddenError):
            svc.update_role(
                1,
                UserRoleUpdate(role="admin"),
                requester_role="broker",
                requester_firm_id=1,
            )

    def test_update_role_unknown_role_raises(self):
        db = _mock_db()
        svc = UserService(db)
        with pytest.raises(NotFoundError):
            svc.update_role(
                1,
                UserRoleUpdate(role="superuser"),
                requester_role="admin",
                requester_firm_id=1,
            )

    def test_update_role_success(self):
        db = _mock_db()
        existing = self._user(role=UserRole.broker)
        mock_q = db.query.return_value
        mock_q.filter.return_value = mock_q
        mock_q.first.return_value = existing

        UserService(db).update_role(
            1, UserRoleUpdate(role="admin"), requester_role="admin", requester_firm_id=1
        )
        assert existing.role == UserRole.admin
        db.commit.assert_called_once()
