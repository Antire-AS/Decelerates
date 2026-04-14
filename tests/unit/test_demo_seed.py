"""Unit tests for api/services/demo_seed.py — fictional company seeding."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from api.services.demo_seed import (
    _seed_default_pipeline_stages,
    seed_full_demo,
)


def test_seed_pipeline_stages_creates_5_stages():
    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = 0
    now = datetime.now(timezone.utc)
    count = _seed_default_pipeline_stages(db, 1, now)
    assert count == 5
    assert db.add.call_count == 5


def test_seed_pipeline_stages_skips_if_exist():
    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = 3
    now = datetime.now(timezone.utc)
    count = _seed_default_pipeline_stages(db, 1, now)
    assert count == 0
    db.add.assert_not_called()


@patch("api.services.demo_seed._seed_demo_deals", return_value=6)
@patch("api.services.demo_seed._seed_default_pipeline_stages", return_value=5)
@patch("api.services.demo_seed._seed_recommendations", return_value=0)
@patch("api.services.demo_seed._seed_submissions", return_value=0)
@patch("api.services.demo_seed._seed_idd", return_value=0)
@patch("api.services.demo_seed._seed_contacts", return_value=0)
@patch("api.services.demo_seed._seed_insurers", return_value={})
@patch("api.services.demo_seed._resolve_default_firm", return_value=MagicMock(id=1))
def test_seed_full_demo_returns_summary(*mocks):
    db = MagicMock()
    # Mock all the per-company helpers
    with patch("api.services.demo_seed._seed_company_row", return_value=True), \
         patch("api.services.demo_seed._seed_history_rows", return_value=5), \
         patch("api.services.demo_seed._seed_primary_policy", return_value=(1, True)), \
         patch("api.services.demo_seed._seed_demo_claim", return_value=True), \
         patch("api.services.demo_seed._seed_demo_activity", return_value=True):
        result = seed_full_demo(db)
    assert "message" in result
    assert result["companies_created"] > 0
    db.commit.assert_called_once()
