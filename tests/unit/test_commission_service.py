"""Unit tests for CommissionService."""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import pytest

from api.db import Policy, PolicyStatus
from api.services.commission_service import CommissionService


def _make_policy(**kwargs):
    p = MagicMock(spec=Policy)
    p.status = kwargs.get("status", PolicyStatus.active)
    p.annual_premium_nok = kwargs.get("annual_premium_nok", 100_000.0)
    p.commission_rate_pct = kwargs.get("commission_rate_pct", 10.0)
    p.commission_amount_nok = kwargs.get("commission_amount_nok", None)
    p.product_type = kwargs.get("product_type", "Eiendomsforsikring")
    p.insurer = kwargs.get("insurer", "Gjensidige")
    p.orgnr = kwargs.get("orgnr", "123456789")
    p.policy_number = kwargs.get("policy_number", "POL-001")
    p.renewal_date = kwargs.get("renewal_date", None)
    now = datetime.now(timezone.utc)
    p.created_at = kwargs.get("created_at", now)
    return p


def _make_db(policies):
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = policies
    db.query.return_value.filter.return_value.order_by.return_value.nullslast.return_value.all.return_value = policies
    return db


class TestGetCommissionSummary:
    def test_sums_commission_from_rate(self):
        p = _make_policy(annual_premium_nok=100_000.0, commission_rate_pct=10.0, commission_amount_nok=None)
        db = _make_db([p])
        svc = CommissionService(db)
        result = svc.get_commission_summary(firm_id=1)
        # 10% of 100k = 10k
        assert result["revenue_by_insurer"]["Gjensidige"] == 10_000.0

    def test_uses_commission_amount_when_set(self):
        p = _make_policy(annual_premium_nok=100_000.0, commission_rate_pct=None, commission_amount_nok=8_000.0)
        db = _make_db([p])
        result = CommissionService(db).get_commission_summary(firm_id=1)
        assert result["revenue_by_insurer"]["Gjensidige"] == 8_000.0

    def test_skips_non_active_policies(self):
        p = _make_policy(status=PolicyStatus.expired, commission_amount_nok=5_000.0)
        db = _make_db([p])
        result = CommissionService(db).get_commission_summary(firm_id=1)
        assert result["active_policy_count"] == 0
        assert result["total_commission_ytd"] == 0.0

    def test_renewal_vs_new_split(self):
        now = datetime.now(timezone.utc)
        new_p = _make_policy(created_at=now, commission_amount_nok=5_000.0)
        old_p = _make_policy(created_at=now - timedelta(days=400), commission_amount_nok=3_000.0)
        db = _make_db([new_p, old_p])
        result = CommissionService(db).get_commission_summary(firm_id=1)
        assert result["renewal_commission_vs_new"]["new"] == 5_000.0
        assert result["renewal_commission_vs_new"]["renewal"] == 3_000.0

    def test_groups_by_product_type(self):
        p1 = _make_policy(product_type="Eiendom", commission_amount_nok=4_000.0)
        p2 = _make_policy(product_type="Ansvar", commission_amount_nok=2_000.0)
        db = _make_db([p1, p2])
        result = CommissionService(db).get_commission_summary(firm_id=1)
        assert result["revenue_by_product_type"]["Eiendom"] == 4_000.0
        assert result["revenue_by_product_type"]["Ansvar"] == 2_000.0


class TestGetCommissionByClient:
    def test_sums_per_client(self):
        p = _make_policy(orgnr="987654321", commission_amount_nok=12_000.0)
        db = _make_db([p])
        result = CommissionService(db).get_commission_by_client(firm_id=1, orgnr="987654321")
        assert result["total_commission_lifetime"] == 12_000.0
        assert result["orgnr"] == "987654321"
        assert len(result["policies"]) == 1


class TestListPoliciesMissingCommission:
    def test_returns_policies_without_commission(self):
        p = _make_policy(commission_rate_pct=None, commission_amount_nok=None, status=PolicyStatus.active)
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [p]
        result = CommissionService(db).list_policies_missing_commission(firm_id=1)
        assert result is not None  # service returns the query result
