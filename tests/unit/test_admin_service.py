"""Unit tests for api/services/admin_service.py — AdminService.

Pure static tests — uses MagicMock DB; no infrastructure required.
External API calls (fetch_enhetsregisteret, fetch_org_profile) are patched.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock


from api.db import (
    Policy, PolicyStatus, Portfolio,
)
from api.services.admin_service import AdminService, _DEMO_POLICIES_DATA


# ── helpers ───────────────────────────────────────────────────────────────────

def _mock_db():
    return MagicMock()


def _mock_portfolio(**kwargs):
    p = MagicMock(spec=Portfolio)
    p.id   = kwargs.get("id", 1)
    p.name = kwargs.get("name", "Demo Portefølje")
    return p


def _mock_policy(**kwargs):
    p = MagicMock(spec=Policy)
    p.id            = kwargs.get("id", 1)
    p.policy_number = kwargs.get("policy_number", "POL-001")
    p.firm_id       = kwargs.get("firm_id", 1)
    return p


# ── reset ─────────────────────────────────────────────────────────────────────

def test_reset_executes_delete_for_each_table():
    db = _mock_db()
    db.execute.return_value.rowcount = 0
    AdminService(db).reset()
    assert db.execute.call_count >= 6  # 6 main tables + company_chunks


def test_reset_commits():
    db = _mock_db()
    db.execute.return_value.rowcount = 0
    AdminService(db).reset()
    db.commit.assert_called_once()


def test_reset_returns_dict_with_reset_true():
    db = _mock_db()
    db.execute.return_value.rowcount = 5
    result = AdminService(db).reset()
    assert result["reset"] is True


def test_reset_returns_deleted_rows_per_table():
    db = _mock_db()
    db.execute.return_value.rowcount = 3
    result = AdminService(db).reset()
    assert "deleted_rows" in result
    assert isinstance(result["deleted_rows"], dict)


def test_reset_includes_companies_table():
    db = _mock_db()
    db.execute.return_value.rowcount = 0
    result = AdminService(db).reset()
    assert "companies" in result["deleted_rows"]


def test_reset_rollbacks_on_commit_error():
    db = _mock_db()
    db.execute.return_value.rowcount = 0
    db.commit.side_effect = RuntimeError("db error")
    import pytest
    with pytest.raises(RuntimeError):
        AdminService(db).reset()
    db.rollback.assert_called_once()


# ── _get_or_create_portfolio ──────────────────────────────────────────────────

def test_get_or_create_portfolio_returns_existing():
    portfolio = _mock_portfolio()
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = portfolio
    result = AdminService(db)._get_or_create_portfolio("Demo Portefølje", "desc")
    assert result is portfolio
    db.add.assert_not_called()


def test_get_or_create_portfolio_creates_when_missing():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    AdminService(db)._get_or_create_portfolio("New Portfolio", "description")
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_get_or_create_portfolio_sets_name():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    AdminService(db)._get_or_create_portfolio("My Portfolio", "desc")
    added = db.add.call_args[0][0]
    assert added.name == "My Portfolio"


def test_get_or_create_portfolio_sets_description():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    AdminService(db)._get_or_create_portfolio("P", "My description")
    added = db.add.call_args[0][0]
    assert added.description == "My description"


def test_get_or_create_portfolio_rollbacks_on_error():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    db.commit.side_effect = RuntimeError("constraint violation")
    import pytest
    with pytest.raises(RuntimeError):
        AdminService(db)._get_or_create_portfolio("P", "d")
    db.rollback.assert_called_once()




# ── _seed_policies ────────────────────────────────────────────────────────────

def test_seed_policies_skips_existing_policy_number():
    db = _mock_db()
    existing_policy = _mock_policy(policy_number=_DEMO_POLICIES_DATA[0][3])
    # All policy queries return "exists"
    db.query.return_value.filter.return_value.first.return_value = existing_policy
    now = datetime.now(timezone.utc)
    created, skipped, policy_map = AdminService(db)._seed_policies(1, now)
    assert created == 0
    assert skipped == len(_DEMO_POLICIES_DATA)


def test_seed_policies_creates_when_not_exists():
    db = _mock_db()
    # All policy queries return None (none exist)
    db.query.return_value.filter.return_value.first.return_value = None
    now = datetime.now(timezone.utc)
    created, skipped, policy_map = AdminService(db)._seed_policies(1, now)
    assert created == len(_DEMO_POLICIES_DATA)
    assert skipped == 0


def test_seed_policies_commits():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    now = datetime.now(timezone.utc)
    AdminService(db)._seed_policies(1, now)
    db.commit.assert_called()


def test_seed_policies_returns_policy_map():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    now = datetime.now(timezone.utc)
    _, _, policy_map = AdminService(db)._seed_policies(1, now)
    # All demo policy numbers should be in the map
    for row in _DEMO_POLICIES_DATA:
        assert row[3] in policy_map


def test_seed_policies_sets_active_status():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    now = datetime.now(timezone.utc)
    AdminService(db)._seed_policies(1, now)
    added_policies = [c[0][0] for c in db.add.call_args_list]
    for p in added_policies:
        assert p.status == PolicyStatus.active


# ── _seed_claims ──────────────────────────────────────────────────────────────

def test_seed_claims_skips_when_policy_not_in_map():
    db = _mock_db()
    # Empty policy_map — no policies to link claims to
    db.query.return_value.filter.return_value.first.return_value = None
    now = datetime.now(timezone.utc)
    created = AdminService(db)._seed_claims({}, 1, now)
    assert created == 0
    db.add.assert_not_called()


def test_seed_claims_skips_existing_claim_number():
    db = _mock_db()
    # Return existing claim for every query
    db.query.return_value.filter.return_value.first.return_value = MagicMock()
    policy_map = {"POL-DNB-001": _mock_policy(), "POL-EQN-001": _mock_policy(id=2),
                  "POL-KON-001": _mock_policy(id=3), "POL-AKB-001": _mock_policy(id=4)}
    now = datetime.now(timezone.utc)
    created = AdminService(db)._seed_claims(policy_map, 1, now)
    assert created == 0


def test_seed_claims_creates_when_not_exists():
    db = _mock_db()
    # No existing claims
    db.query.return_value.filter.return_value.first.return_value = None
    policy_map = {"POL-DNB-001": _mock_policy(), "POL-EQN-001": _mock_policy(id=2),
                  "POL-KON-001": _mock_policy(id=3), "POL-AKB-001": _mock_policy(id=4)}
    now = datetime.now(timezone.utc)
    created = AdminService(db)._seed_claims(policy_map, 1, now)
    assert created == 4  # 4 demo claims


def test_seed_claims_commits():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    policy_map = {"POL-DNB-001": _mock_policy()}
    now = datetime.now(timezone.utc)
    AdminService(db)._seed_claims(policy_map, 1, now)
    db.commit.assert_called()


# ── _seed_activities ──────────────────────────────────────────────────────────

def test_seed_activities_skips_existing():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = MagicMock()
    now = datetime.now(timezone.utc)
    created = AdminService(db)._seed_activities(1, now)
    assert created == 0


def test_seed_activities_creates_when_not_exists():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    now = datetime.now(timezone.utc)
    created = AdminService(db)._seed_activities(1, now)
    assert created == 7  # 7 demo activities


def test_seed_activities_commits():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    now = datetime.now(timezone.utc)
    AdminService(db)._seed_activities(1, now)
    db.commit.assert_called()


def test_seed_activities_sets_demo_email():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = None
    now = datetime.now(timezone.utc)
    AdminService(db)._seed_activities(1, now)
    added = [c[0][0] for c in db.add.call_args_list]
    for activity in added:
        assert activity.created_by_email == "demo@broker.no"


# ── seed_crm_demo ─────────────────────────────────────────────────────────────

def test_seed_crm_demo_returns_summary_dict():
    db = _mock_db()
    # BrokerFirm exists, no policies/claims/activities exist
    db.query.return_value.filter.return_value.first.return_value = MagicMock()
    result = AdminService(db).seed_crm_demo()
    assert "policies_created" in result
    assert "policies_skipped" in result
    assert "claims_created" in result
    assert "activities_created" in result


def test_seed_crm_demo_creates_default_firm_when_missing():
    db = _mock_db()
    # First call (BrokerFirm) → None, rest → existing (skip everything)
    db.query.return_value.filter.return_value.first.side_effect = (
        [None] + [MagicMock()] * 200
    )
    AdminService(db).seed_crm_demo()
    # The BrokerFirm add must have been called
    added_types = [type(c[0][0]).__name__ for c in db.add.call_args_list]
    assert "BrokerFirm" in added_types


def test_seed_crm_demo_does_not_add_firm_when_exists():
    db = _mock_db()
    db.query.return_value.filter.return_value.first.return_value = MagicMock()
    AdminService(db).seed_crm_demo()
    added_types = [type(c[0][0]).__name__ for c in db.add.call_args_list]
    assert "BrokerFirm" not in added_types
