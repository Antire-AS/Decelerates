"""Unit tests for offer status update service helper.

Pure static tests — uses MagicMock DB; no infrastructure required.
"""
from unittest.mock import MagicMock


from api.db import InsuranceOffer, OfferStatus
from api.services.documents import update_offer_status


def _mock_offer(orgnr="123456789", **kwargs):
    offer = MagicMock(spec=InsuranceOffer)
    offer.id = kwargs.get("id", 1)
    offer.orgnr = orgnr
    offer.status = OfferStatus.pending
    return offer


def _mock_db(offer=None):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = offer
    return db


# ── Happy path ────────────────────────────────────────────────────────────────

def test_update_to_accepted():
    offer = _mock_offer()
    db = _mock_db(offer)
    assert update_offer_status(1, "123456789", "accepted", db) is True
    assert offer.status == OfferStatus.accepted
    db.commit.assert_called_once()


def test_update_to_rejected():
    offer = _mock_offer()
    db = _mock_db(offer)
    assert update_offer_status(1, "123456789", "rejected", db) is True
    assert offer.status == OfferStatus.rejected


def test_update_to_negotiating():
    offer = _mock_offer()
    db = _mock_db(offer)
    assert update_offer_status(1, "123456789", "negotiating", db) is True
    assert offer.status == OfferStatus.negotiating


def test_update_to_pending():
    offer = _mock_offer()
    db = _mock_db(offer)
    assert update_offer_status(1, "123456789", "pending", db) is True
    assert offer.status == OfferStatus.pending


def test_all_valid_statuses_return_true():
    for status in ["pending", "accepted", "rejected", "negotiating"]:
        offer = _mock_offer()
        db = _mock_db(offer)
        assert update_offer_status(1, "123456789", status, db) is True


# ── Not found / invalid ───────────────────────────────────────────────────────

def test_returns_false_when_offer_not_found():
    db = _mock_db(offer=None)
    assert update_offer_status(999, "123456789", "accepted", db) is False
    db.commit.assert_not_called()


def test_returns_false_for_invalid_status():
    offer = _mock_offer()
    db = _mock_db(offer)
    assert update_offer_status(1, "123456789", "won", db) is False
    db.commit.assert_not_called()


def test_returns_false_for_empty_status():
    offer = _mock_offer()
    db = _mock_db(offer)
    assert update_offer_status(1, "123456789", "", db) is False


def test_returns_false_for_uppercase_status():
    """Status enum values are lowercase — 'ACCEPTED' is not a valid value."""
    offer = _mock_offer()
    db = _mock_db(offer)
    assert update_offer_status(1, "123456789", "ACCEPTED", db) is False


# ── DB commit behaviour ───────────────────────────────────────────────────────

def test_commit_called_exactly_once_on_success():
    offer = _mock_offer()
    db = _mock_db(offer)
    update_offer_status(1, "123456789", "accepted", db)
    db.commit.assert_called_once()


def test_commit_not_called_when_not_found():
    db = _mock_db(offer=None)
    update_offer_status(1, "123456789", "accepted", db)
    db.commit.assert_not_called()
