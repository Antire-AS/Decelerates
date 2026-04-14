"""Expanded unit tests for api/services/demo_seed.py — individual seed helpers.

All DB operations are mocked. Tests cover _seed_company_row, _seed_history_rows,
_seed_primary_policy, _seed_demo_claim, _seed_demo_activity, _seed_demo_deals,
_build_history_rows, _resolve_default_firm, and seed_full_demo.
"""
from datetime import date, datetime, timezone
from unittest.mock import MagicMock



# ── Sample company dict for tests ────────────────────────────────────────────

def _sample_company(**overrides):
    base = {
        "orgnr": "999100101",
        "navn": "Bergstrand Eiendom AS",
        "risk_score": 32,
        "naeringskode1": "68.209",
        "naeringskode1_beskrivelse": "Utleie av egne boliger og naeringslokaler",
        "kommune": "Oslo",
        "antall_ansatte": 8,
        "base_revenue": 42_000_000,
        "base_result": 7_500_000,
        "base_assets": 180_000_000,
        "base_equity": 95_000_000,
        "insurance_type": "Eiendom og ansvarsforsikring",
        "insurer": "Gjensidige Forsikring",
        "renewal_offset_days": 22,
    }
    base.update(overrides)
    return base


# ── _build_history_rows ──────────────────────────────────────────────────────

def test_build_history_rows_returns_five_years():
    from api.services.demo_seed import _build_history_rows
    rows = _build_history_rows(_sample_company())
    assert len(rows) == 5
    years = [r["year"] for r in rows]
    assert years == sorted(years)


def test_build_history_rows_has_required_fields():
    from api.services.demo_seed import _build_history_rows
    rows = _build_history_rows(_sample_company())
    for row in rows:
        assert "year" in row
        assert "revenue" in row
        assert "net_result" in row
        assert "equity" in row
        assert "total_assets" in row
        assert "equity_ratio" in row


# ── _seed_company_row ────────────────────────────────────────────────────────

def test_seed_company_row_skips_existing():
    from api.services.demo_seed import _seed_company_row
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = MagicMock()  # exists
    assert _seed_company_row(db, _sample_company()) is False
    db.add.assert_not_called()


def test_seed_company_row_creates_new():
    from api.services.demo_seed import _seed_company_row
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None  # not found
    assert _seed_company_row(db, _sample_company()) is True
    db.add.assert_called_once()


def test_seed_company_row_handles_zero_assets():
    from api.services.demo_seed import _seed_company_row
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    c = _sample_company(base_assets=0, base_equity=0)
    assert _seed_company_row(db, c) is True


# ── _seed_history_rows ───────────────────────────────────────────────────────

def test_seed_history_rows_creates_five_when_none_exist():
    from api.services.demo_seed import _seed_history_rows
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None  # nothing exists
    count = _seed_history_rows(db, _sample_company())
    assert count == 5
    assert db.add.call_count == 5


def test_seed_history_rows_skips_existing_years():
    from api.services.demo_seed import _seed_history_rows
    db = MagicMock()
    # First year exists, rest don't
    db.query.return_value.filter.return_value.first.side_effect = [MagicMock(), None, None, None, None]
    count = _seed_history_rows(db, _sample_company())
    assert count == 4


def test_seed_history_rows_returns_zero_when_all_exist():
    from api.services.demo_seed import _seed_history_rows
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = MagicMock()  # all exist
    count = _seed_history_rows(db, _sample_company())
    assert count == 0


# ── _seed_primary_policy ─────────────────────────────────────────────────────

def test_seed_primary_policy_skips_existing():
    from api.services.demo_seed import _seed_primary_policy
    db = MagicMock()
    existing = MagicMock()
    existing.id = 42
    db.query.return_value.filter.return_value.first.return_value = existing
    policy_id, created = _seed_primary_policy(db, _sample_company(), 1, date.today(), datetime.now(timezone.utc))
    assert policy_id == 42
    assert created is False


def test_seed_primary_policy_creates_new():
    from api.services.demo_seed import _seed_primary_policy
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    # flush sets id on the object
    def _flush():
        for c in db.add.call_args_list:
            obj = c[0][0]
            if not hasattr(obj, 'id') or obj.id is None:
                obj.id = 99
    db.flush.side_effect = _flush
    policy_id, created = _seed_primary_policy(db, _sample_company(), 1, date.today(), datetime.now(timezone.utc))
    assert created is True
    db.add.assert_called_once()


# ── _seed_demo_claim ─────────────────────────────────────────────────────────

def test_seed_demo_claim_skips_low_risk():
    from api.services.demo_seed import _seed_demo_claim
    db = MagicMock()
    c = _sample_company(risk_score=30)  # below 60
    assert _seed_demo_claim(db, c, 1, 99, date.today(), datetime.now(timezone.utc)) is False
    db.add.assert_not_called()


def test_seed_demo_claim_creates_for_high_risk():
    from api.services.demo_seed import _seed_demo_claim
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    c = _sample_company(risk_score=72)
    assert _seed_demo_claim(db, c, 1, 99, date.today(), datetime.now(timezone.utc)) is True
    db.add.assert_called_once()


def test_seed_demo_claim_skips_if_claim_exists():
    from api.services.demo_seed import _seed_demo_claim
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = MagicMock()  # exists
    c = _sample_company(risk_score=72)
    assert _seed_demo_claim(db, c, 1, 99, date.today(), datetime.now(timezone.utc)) is False


# ── _seed_demo_activity ──────────────────────────────────────────────────────

def test_seed_demo_activity_creates_new():
    from api.services.demo_seed import _seed_demo_activity
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    assert _seed_demo_activity(db, _sample_company(), 1, date.today(), datetime.now(timezone.utc)) is True
    db.add.assert_called_once()


def test_seed_demo_activity_skips_existing():
    from api.services.demo_seed import _seed_demo_activity
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = MagicMock()
    assert _seed_demo_activity(db, _sample_company(), 1, date.today(), datetime.now(timezone.utc)) is False


# ── _seed_demo_deals ─────────────────────────────────────────────────────────

def test_seed_demo_deals_creates_deals():
    from api.services.demo_seed import _seed_demo_deals, PipelineStageKind
    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = 0  # no existing deals
    # Return mock stages
    stage = MagicMock()
    stage.kind = PipelineStageKind.lead
    stage.id = 10
    stage2 = MagicMock()
    stage2.kind = PipelineStageKind.qualified
    stage2.id = 11
    stage3 = MagicMock()
    stage3.kind = PipelineStageKind.quoted
    stage3.id = 12
    stage4 = MagicMock()
    stage4.kind = PipelineStageKind.bound
    stage4.id = 13
    db.query.return_value.filter.return_value.all.return_value = [stage, stage2, stage3, stage4]

    count = _seed_demo_deals(db, 1, datetime.now(timezone.utc))
    assert count >= 1
    assert db.add.call_count >= 1


def test_seed_demo_deals_skips_when_deals_exist():
    from api.services.demo_seed import _seed_demo_deals
    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = 5  # existing deals
    count = _seed_demo_deals(db, 1, datetime.now(timezone.utc))
    assert count == 0


# ── _resolve_default_firm ────────────────────────────────────────────────────

def test_resolve_default_firm_returns_existing():
    from api.services.demo_seed import _resolve_default_firm
    db = MagicMock()
    firm = MagicMock()
    firm.id = 7
    db.query.return_value.order_by.return_value.first.return_value = firm
    assert _resolve_default_firm(db, datetime.now(timezone.utc)) == 7


def test_resolve_default_firm_creates_when_none_exist():
    from api.services.demo_seed import _resolve_default_firm
    db = MagicMock()
    db.query.return_value.order_by.return_value.first.return_value = None
    db.flush.side_effect = lambda: None
    _resolve_default_firm(db, datetime.now(timezone.utc))
    db.add.assert_called_once()


# ── seed_full_demo ───────────────────────────────────────────────────────────

def test_seed_full_demo_returns_summary():
    from api.services.demo_seed import seed_full_demo
    db = MagicMock()
    # All queries return "not found" so everything gets created
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.count.return_value = 0
    db.query.return_value.order_by.return_value.first.return_value = None
    db.query.return_value.filter.return_value.all.return_value = []
    db.flush.side_effect = lambda: None

    result = seed_full_demo(db)
    assert "message" in result
    assert result["companies_created"] == 8
    db.commit.assert_called_once()


def test_seed_full_demo_idempotent():
    from api.services.demo_seed import seed_full_demo
    db = MagicMock()
    # All queries return "found" so nothing gets created
    existing = MagicMock()
    existing.id = 1
    db.query.return_value.filter.return_value.first.return_value = existing
    db.query.return_value.filter.return_value.count.return_value = 5
    db.query.return_value.order_by.return_value.first.return_value = existing
    db.query.return_value.filter.return_value.all.return_value = []

    result = seed_full_demo(db)
    assert result["companies_created"] == 0
    assert result["history_rows_created"] == 0
