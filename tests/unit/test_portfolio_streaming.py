"""Unit tests for api/services/portfolio_streaming.py — SSE streaming."""
import sys
from unittest.mock import MagicMock, patch

sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.services.portfolio_streaming import stream_seed_norway


@patch("api.services.portfolio_streaming.fetch_enhetsregisteret", return_value=[{"organisasjonsnummer": "123", "navn": "Test"}])
@patch("api.services.portfolio_streaming.fetch_org_profile", return_value={"org": {"orgnr": "123"}})
def test_stream_seed_norway_yields_events(mock_profile, mock_search):
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []
    db.add = MagicMock()
    db.commit = MagicMock()
    events = list(stream_seed_norway(1, db))
    assert len(events) > 0
