"""Unit tests for tender_reminders service.

The service is called from a daily cron (see .github/workflows/tender-reminders.yml)
and from a manual broker button. We only need to cover the pure helpers here
— the DB-touching code is covered in integration tests.
"""

from datetime import date

from api.services.tender_reminders import _should_remind


def test_should_remind_exactly_7_days_before() -> None:
    today = date(2026, 4, 20)
    deadline = date(2026, 4, 27)
    assert _should_remind(deadline, today) is True


def test_should_remind_exactly_2_days_before() -> None:
    today = date(2026, 4, 20)
    deadline = date(2026, 4, 22)
    assert _should_remind(deadline, today) is True


def test_should_not_remind_other_days() -> None:
    from datetime import timedelta

    today = date(2026, 4, 20)
    for delta in (1, 3, 4, 5, 6, 8, 14, 0, -1):
        deadline = today + timedelta(days=delta)
        assert _should_remind(deadline, today) is False, (
            f"delta={delta} should not trigger"
        )


def test_should_not_remind_past_deadline() -> None:
    """Don't send reminders after the deadline has already passed."""
    today = date(2026, 4, 20)
    deadline = date(2026, 4, 19)
    assert _should_remind(deadline, today) is False
