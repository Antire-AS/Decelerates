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


# ── _remind_one_tender (monkeypatched) ───────────────────────────────────────


def _ns(**kwargs):
    from types import SimpleNamespace

    return SimpleNamespace(**kwargs)


def test_remind_one_tender_no_pending_recipients(monkeypatch) -> None:
    """No pending recipients → no emails sent, returns (0, 0)."""
    from api.services import tender_reminders as mod

    monkeypatch.setattr(mod, "_pending_recipients", lambda db, t: [])
    tender = _ns(id=1, orgnr="123456789", title="Anbud")
    assert mod._remind_one_tender(db=None, tender=tender) == (0, 0)


def test_remind_one_tender_counts_sends_and_failures(monkeypatch) -> None:
    """Succeeds → sent++; returns False → failed++."""
    from api.services import tender_reminders as mod

    recips = [
        _ns(id=1, insurer_name="Gjensidige", insurer_email="g@g.no"),
        _ns(id=2, insurer_name="If", insurer_email="i@if.no"),
        _ns(id=3, insurer_name="Tryg", insurer_email="t@tryg.no"),
    ]
    monkeypatch.setattr(mod, "_pending_recipients", lambda db, t: recips)

    class _FakeQuery:
        def filter(self, *_a, **_kw):
            return self

        def first(self):
            return _ns(navn="DNB Bank")

    class _FakeDB:
        def query(self, _model):
            return _FakeQuery()

    calls = iter([True, True, False])
    monkeypatch.setattr(mod, "_send_tender_email", lambda **_kw: next(calls))
    tender = _ns(id=1, orgnr="123456789", title="Anbud")
    sent, failed = mod._remind_one_tender(db=_FakeDB(), tender=tender)
    assert (sent, failed) == (2, 1)


def test_send_deadline_reminders_no_tenders(monkeypatch) -> None:
    """Empty DB → zero-everything summary."""
    from api.services import tender_reminders as mod

    class _FakeQuery:
        def filter(self, *_a, **_kw):
            return self

        def all(self):
            return []

    class _FakeDB:
        def query(self, _model):
            return _FakeQuery()

    result = mod.send_deadline_reminders(db=_FakeDB(), today=date(2026, 4, 20))
    assert result == {
        "tenders_checked": 0,
        "reminders_sent": 0,
        "reminders_failed": 0,
    }
