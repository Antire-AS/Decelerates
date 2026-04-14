"""Unit tests for api/services/portfolio_ingest.py — mocked DB and external APIs."""
import sys
from unittest.mock import MagicMock, patch


sys.modules.setdefault("api.rag_chain", MagicMock())
sys.modules.setdefault("api.services.pdf_background", MagicMock())

from api.services.portfolio_ingest import (
    ingest_companies,
    seed_norway_top100,
    enrich_pdfs_background,
)


# ── ingest_companies ─────────────────────────────────────────────────────────

def test_ingest_skips_existing_companies():
    pc = MagicMock(orgnr="123456789")
    existing = MagicMock(navn="Existing AS")
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [pc]
    db.query.return_value.filter.return_value.first.return_value = existing

    result = ingest_companies(portfolio_id=1, db=db)
    assert result["skipped"] == 1
    assert result["fetched"] == 0


def test_ingest_fetches_new_companies():
    pc = MagicMock(orgnr="123456789")
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [pc]
    db.query.return_value.filter.return_value.first.return_value = None

    with patch("api.services.portfolio_ingest.fetch_org_profile") as mock_fetch:
        result = ingest_companies(portfolio_id=1, db=db)
    assert result["fetched"] == 1
    mock_fetch.assert_called_once_with("123456789", db)


def test_ingest_counts_failures():
    pc = MagicMock(orgnr="123456789")
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [pc]
    db.query.return_value.filter.return_value.first.return_value = None

    with patch("api.services.portfolio_ingest.fetch_org_profile", side_effect=RuntimeError("boom")):
        result = ingest_companies(portfolio_id=1, db=db)
    assert result["failed"] == 1
    assert result["fetched"] == 0


# ── seed_norway_top100 ───────────────────────────────────────────────────────

def test_seed_top100_adds_new_companies():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []

    with patch("api.constants.TOP_100_NO_NAMES", ["DNB ASA"]), \
         patch("api.services.portfolio_ingest.fetch_enhetsregisteret",
               return_value=[{"orgnr": "984851006"}]):
        result = seed_norway_top100(portfolio_id=1, db=db)
    assert result["added"] == 1
    assert result["not_found"] == 0
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_seed_top100_skips_existing():
    pc = MagicMock(orgnr="984851006")
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [pc]

    with patch("api.constants.TOP_100_NO_NAMES", ["DNB ASA"]), \
         patch("api.services.portfolio_ingest.fetch_enhetsregisteret",
               return_value=[{"orgnr": "984851006"}]):
        result = seed_norway_top100(portfolio_id=1, db=db)
    assert result["already_present"] == 1
    assert result["added"] == 0


def test_seed_top100_counts_not_found():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []

    with patch("api.constants.TOP_100_NO_NAMES", ["Unknown Corp"]), \
         patch("api.services.portfolio_ingest.fetch_enhetsregisteret", return_value=[]):
        result = seed_norway_top100(portfolio_id=1, db=db)
    assert result["not_found"] == 1
    assert result["added"] == 0


# ── enrich_pdfs_background ───────────────────────────────────────────────────

def test_enrich_pdfs_returns_queued_count():
    pc1 = MagicMock(orgnr="111")
    pc2 = MagicMock(orgnr="222")
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [pc1, pc2]

    with patch("api.services.portfolio_ingest.fetch_enhet_by_orgnr"), \
         patch("api.services.portfolio_ingest._auto_extract_pdf_sources"), \
         patch("api.services.portfolio_ingest.ThreadPoolExecutor") as mock_pool:
        mock_pool.return_value.__enter__ = MagicMock()
        mock_pool.return_value.__exit__ = MagicMock()
        result = enrich_pdfs_background(portfolio_id=1, db=db)
    assert result["queued"] == 2


def test_enrich_pdfs_empty_portfolio():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []

    with patch("api.services.portfolio_ingest.ThreadPoolExecutor") as mock_pool:
        mock_pool.return_value.__enter__ = MagicMock()
        mock_pool.return_value.__exit__ = MagicMock()
        result = enrich_pdfs_background(portfolio_id=1, db=db)
    assert result["queued"] == 0
