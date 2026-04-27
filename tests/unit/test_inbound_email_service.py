"""Unit tests for the shared inbound-email ingest pipeline.

The pipeline is provider-agnostic — both SendGrid and Graph funnel into
`match_and_ingest` with a normalised `parsed` dict. Tests here cover
the shared layer; provider-specific normalisation is tested in
`test_sendgrid_inbound_service.py` and `test_msgraph_inbound_service.py`.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from api.services import inbound_email_service as svc


# ── Tender-ref regex (parser ↔ builder symmetry) ────────────────────────────


def test_format_and_parse_tender_ref_roundtrip():
    token = svc.format_tender_ref(5, 42)
    assert token == "[ref: TENDER-5-42]"
    parsed = svc.extract_tender_ref(f"Re: Anbud — Equinor {token}")
    assert parsed == (5, 42, "[ref: TENDER-5-42]")


def test_tender_ref_tolerates_whitespace_variants():
    for s in (
        "[ref:TENDER-12-34]",
        "[ref:  TENDER-12-34]",
        "[ref: TENDER-12-34 ]",
        "[REF: tender-12-34]",
    ):
        assert svc.extract_tender_ref(s) is not None


def test_tender_ref_none_when_absent():
    assert svc.extract_tender_ref("Re: Anbud — Equinor") is None


def test_tender_ref_none_when_subject_none():
    assert svc.extract_tender_ref(None) is None


# ── Dedup via message_id ────────────────────────────────────────────────────


def test_match_and_ingest_dedups_replayed_message_id():
    """Second call with the same message_id returns status=dedup and does
    NOT call TenderService.upload_offer."""
    parsed = {
        "subject": "Re: Anbud [ref: TENDER-5-42]",
        "sender": "insurer@x.no",
        "recipient": "anbud@meglerai.no",
        "text_body": "",
        "attachments": [],
        "message_id": "<replayed-msg@example.com>",
    }
    db = MagicMock()
    existing = MagicMock()
    existing.id = 999
    existing.offer_id = 777
    db.query.return_value.filter.return_value.first.return_value = existing

    with patch.object(svc, "_resolve_tender") as mock_resolve:
        result = svc.match_and_ingest(parsed, db)

    assert result["status"] == "dedup"
    assert result["existing_log_id"] == 999
    assert result["offer_id"] == 777
    mock_resolve.assert_not_called()  # short-circuit before tender lookup


def test_match_and_ingest_no_dedup_when_message_id_missing():
    """Without a message_id the dedup check is skipped and downstream
    resolution proceeds (here it orphans because the DB is mocked empty)."""
    parsed = {
        "subject": "Re: Anbud [ref: TENDER-5-42]",
        "sender": "insurer@x.no",
        "recipient": "anbud@meglerai.no",
        "text_body": "",
        "attachments": [],
        # no message_id at all
    }
    db = MagicMock()
    db.query.return_value.get.return_value = None  # tender not found

    result = svc.match_and_ingest(parsed, db)
    assert result["status"] == "orphaned"


def test_find_existing_by_message_id_returns_none_when_unset():
    """Missing message_id short-circuits to None without hitting the DB."""
    db = MagicMock()
    assert svc._find_existing_by_message_id(db, None) is None
    assert svc._find_existing_by_message_id(db, "") is None
    db.query.assert_not_called()


# ── match_and_ingest orphan paths ───────────────────────────────────────────


def test_match_and_ingest_orphans_when_subject_missing_ref():
    """No `[ref: TENDER-...]` in subject → status=orphaned, log written."""
    parsed = {
        "subject": "Re: Hei — spørsmål om vilkår",  # no ref token
        "sender": "insurer@x.no",
        "recipient": "anbud@meglerai.no",
        "text_body": "",
        "attachments": [],
        "message_id": None,
    }
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None  # no dedup hit

    result = svc.match_and_ingest(parsed, db)
    assert result["status"] == "orphaned"
    assert "no_tender_ref" in result["reason"]


def test_match_and_ingest_orphans_when_tender_not_in_db():
    """Ref token present but tender/recipient don't exist → status=orphaned."""
    parsed = {
        "subject": "Re: Anbud [ref: TENDER-999-999]",
        "sender": "insurer@x.no",
        "recipient": "anbud@meglerai.no",
        "text_body": "",
        "attachments": [],
        "message_id": None,
    }
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.get.return_value = None  # tender not found

    result = svc.match_and_ingest(parsed, db)
    assert result["status"] == "orphaned"
    assert result["reason"] == "unknown_tender"


# ── match_and_ingest matched paths ──────────────────────────────────────────


class _FakeRecipient:
    def __init__(self, rid: int, tender_id: int, insurer_name: str):
        self.id = rid
        self.tender_id = tender_id
        self.insurer_name = insurer_name


class _FakeTender:
    def __init__(self, tid: int, firm_id: int, orgnr: str, title: str):
        self.id = tid
        self.firm_id = firm_id
        self.orgnr = orgnr
        self.title = title


def _matched_db_mock() -> MagicMock:
    db = MagicMock()

    def _query_router(model):
        m = MagicMock()
        if model.__name__ == "Tender":
            m.get.return_value = _FakeTender(5, 42, "123456789", "Equinor anbud")
        elif model.__name__ == "TenderRecipient":
            m.get.return_value = _FakeRecipient(42, 5, "Gjensidige")
        elif model.__name__ == "IncomingEmailLog":
            m.filter.return_value.first.return_value = None  # no dedup hit
        return m

    db.query.side_effect = _query_router
    return db


def test_match_and_ingest_with_pdf_uploads_offer_and_notifies():
    """Happy path — ref matches tender, PDF attachment, offer uploaded."""
    parsed = {
        "subject": "Re: Anbud [ref: TENDER-5-42]",
        "sender": "insurer@gjensidige.no",
        "recipient": "anbud@meglerai.no",
        "text_body": "Her er tilbudet vårt",
        "attachments": [
            {
                "filename": "tilbud.pdf",
                "content_type": "application/pdf",
                "content": b"%PDF-fake",
            }
        ],
        "message_id": "<matched@example.com>",
    }
    db = _matched_db_mock()
    mock_svc = MagicMock()
    mock_offer = MagicMock()
    mock_offer.id = 777
    mock_svc.upload_offer.return_value = mock_offer

    with (
        patch.object(svc, "TenderService", return_value=mock_svc),
        patch.object(svc, "_notify_firm_of_reply") as mock_notify,
    ):
        result = svc.match_and_ingest(parsed, db)

    assert result["status"] == "matched"
    assert result["offer_id"] == 777
    assert result["pdf_attachments"] == 1
    mock_svc.upload_offer.assert_called_once()
    mock_notify.assert_called_once()
    assert mock_notify.call_args.kwargs.get("has_pdf") is True


def test_match_and_ingest_without_pdf_still_notifies():
    """Reply with no PDF — broker still notified, has_pdf=False flag."""
    parsed = {
        "subject": "Re: Anbud [ref: TENDER-5-42]",
        "sender": "insurer@gjensidige.no",
        "recipient": "anbud@meglerai.no",
        "text_body": "Kommer tilbake med tilbud i morgen.",
        "attachments": [],
        "message_id": "<no-pdf@example.com>",
    }
    db = _matched_db_mock()

    with patch.object(svc, "_notify_firm_of_reply") as mock_notify:
        result = svc.match_and_ingest(parsed, db)

    assert result["status"] == "matched"
    assert result["offer_id"] is None
    assert result["pdf_attachments"] == 0
    mock_notify.assert_called_once()
    assert mock_notify.call_args.kwargs.get("has_pdf") is False
