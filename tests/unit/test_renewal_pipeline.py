"""Unit tests for the renewal notification pipeline."""
from datetime import date, timedelta
from unittest.mock import MagicMock, call

import pytest

from api.db import Policy, PolicyStatus, RenewalStage
from api.services.policy_service import PolicyService


def _make_policy(policy_id=1, orgnr="123456789", insurer="Gjensidige",
                 product_type="Eiendom", renewal_date=None, premium=100_000.0,
                 policy_number="POL-001", last_notified=None):
    p = MagicMock(spec=Policy)
    p.id = policy_id
    p.orgnr = orgnr
    p.insurer = insurer
    p.product_type = product_type
    p.annual_premium_nok = premium
    p.policy_number = policy_number
    p.renewal_date = renewal_date or date.today() + timedelta(days=25)
    p.last_renewal_notified_days = last_notified
    p.status = PolicyStatus.active
    return p


class TestRunRenewalNotifications:
    def _svc_with_policies(self, policies_by_threshold: dict):
        db = MagicMock()
        svc = PolicyService(db)

        def _policies_needing(firm_id, threshold_days):
            return policies_by_threshold.get(threshold_days, [])

        svc.get_policies_needing_renewal_notification = _policies_needing
        svc.mark_renewal_notified = MagicMock()
        return svc, db

    def test_calls_notification_port_for_matching_threshold(self):
        p = _make_policy()
        svc, db = self._svc_with_policies({30: [p]})
        notif = MagicMock()
        notif.send_renewal_threshold_emails.return_value = True

        result = svc.run_renewal_notifications(
            firm_id=1, notif_port=notif, broker_email="broker@firm.no", db=db
        )

        notif.send_renewal_threshold_emails.assert_called_once()
        call_args = notif.send_renewal_threshold_emails.call_args
        assert call_args[0][1] == 30  # threshold_days
        assert result["notified_count"] == 1
        assert result["skipped_count"] == 0

    def test_marks_policy_notified_after_send(self):
        p = _make_policy()
        svc, db = self._svc_with_policies({30: [p]})
        notif = MagicMock()
        notif.send_renewal_threshold_emails.return_value = True

        svc.run_renewal_notifications(
            firm_id=1, notif_port=notif, broker_email="broker@firm.no", db=db
        )

        svc.mark_renewal_notified.assert_called_once_with(p.id, 30)

    def test_skips_when_notification_send_fails(self):
        p = _make_policy()
        svc, db = self._svc_with_policies({30: [p]})
        notif = MagicMock()
        notif.send_renewal_threshold_emails.return_value = False

        result = svc.run_renewal_notifications(
            firm_id=1, notif_port=notif, broker_email="broker@firm.no", db=db
        )

        svc.mark_renewal_notified.assert_not_called()
        assert result["skipped_count"] == 1
        assert result["notified_count"] == 0

    def test_returns_zero_when_no_policies_due(self):
        svc, db = self._svc_with_policies({})
        notif = MagicMock()

        result = svc.run_renewal_notifications(
            firm_id=1, notif_port=notif, broker_email="broker@firm.no", db=db
        )

        notif.send_renewal_threshold_emails.assert_not_called()
        assert result["notified_count"] == 0
        assert result["skipped_count"] == 0

    def test_handles_multiple_thresholds(self):
        p7 = _make_policy(policy_id=1, renewal_date=date.today() + timedelta(days=5))
        p90 = _make_policy(policy_id=2, renewal_date=date.today() + timedelta(days=85))
        svc, db = self._svc_with_policies({7: [p7], 90: [p90]})
        notif = MagicMock()
        notif.send_renewal_threshold_emails.return_value = True

        result = svc.run_renewal_notifications(
            firm_id=1, notif_port=notif, broker_email="broker@firm.no", db=db
        )

        assert notif.send_renewal_threshold_emails.call_count == 2
        assert result["notified_count"] == 2
