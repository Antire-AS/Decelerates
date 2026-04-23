"""Unit tests for the ACS inbound-email pipeline.

Four tight layers — each small enough that one broken assertion points
straight at what changed:

  1. Event Grid handshake detection
  2. Tender-ref regex (parser ↔ builder symmetry)
  3. MIME parsing (plain text, PDF attachment)
  4. Main dispatcher (orphan, matched happy-path) with mocked DB
"""

from __future__ import annotations

from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import MagicMock, patch

from api.services import inbound_email_service as svc


# ── Event Grid handshake ────────────────────────────────────────────────────


def test_validation_response_returned_for_subscription_event():
    payload = [
        {
            "eventType": "Microsoft.EventGrid.SubscriptionValidationEvent",
            "data": {"validationCode": "abc123"},
        }
    ]
    assert svc.build_validation_response(payload) == {"validationResponse": "abc123"}


def test_validation_response_none_for_regular_events():
    payload = [
        {
            "eventType": "Microsoft.Communication.EmailReceived",
            "data": {"from": "a@b.com"},
        }
    ]
    assert svc.build_validation_response(payload) is None


def test_validation_response_none_for_empty_payload():
    assert svc.build_validation_response([]) is None


# ── Tender-ref regex ────────────────────────────────────────────────────────


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


# ── MIME parsing ────────────────────────────────────────────────────────────


def _build_mime_with_pdf(subject: str, pdf_bytes: bytes = b"%PDF-fake") -> bytes:
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = "insurer@gjensidige.no"
    msg["To"] = "anbud@meglerai.no"
    msg.attach(MIMEText("Takk for tilbudet, se vedlegg.", "plain"))
    part = MIMEApplication(pdf_bytes, _subtype="pdf")
    part.add_header("Content-Disposition", "attachment", filename="tilbud.pdf")
    msg.attach(part)
    return msg.as_bytes()


def test_parse_email_extracts_subject_sender_and_pdf_attachment():
    raw = _build_mime_with_pdf("Re: Anbud [ref: TENDER-1-2]")
    parsed = svc.parse_email_mime(raw)
    assert parsed["subject"] == "Re: Anbud [ref: TENDER-1-2]"
    assert parsed["sender"] == "insurer@gjensidige.no"
    assert parsed["recipient"] == "anbud@meglerai.no"
    assert "Takk for tilbudet" in parsed["text_body"]
    assert len(parsed["attachments"]) == 1
    att = parsed["attachments"][0]
    assert att["filename"] == "tilbud.pdf"
    assert att["content_type"] == "application/pdf"
    assert att["content"].startswith(b"%PDF")


def test_parse_email_with_no_attachments():
    msg = MIMEText("Kort svar uten vedlegg.", "plain")
    msg["Subject"] = "Re: Anbud"
    msg["From"] = "x@y.no"
    raw = msg.as_bytes()
    parsed = svc.parse_email_mime(raw)
    assert parsed["attachments"] == []
    assert "Kort svar" in parsed["text_body"]


def test_parse_email_extracts_message_id_header():
    """MIME Message-ID header is plumbed through as the dedup key."""
    msg = MIMEText("hi", "plain")
    msg["Subject"] = "test"
    msg["From"] = "x@y.no"
    msg["Message-ID"] = "<abc-123@example.com>"
    parsed = svc.parse_email_mime(msg.as_bytes())
    assert parsed["message_id"] == "<abc-123@example.com>"


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


# ── Main dispatcher ─────────────────────────────────────────────────────────


def test_process_event_marks_orphan_when_no_content_url():
    db = MagicMock()
    result = svc.process_email_received_event({"data": {}}, db)
    assert result["status"] == "error"
    assert result["reason"] == "missing_content_url"
    db.add.assert_called_once()  # log row written


def test_process_event_marks_orphan_when_subject_missing_ref():
    """Email that arrives without our tender ref gets logged but not ingested."""
    raw = _build_mime_with_pdf("Re: Hei — spørsmål om vilkår")  # no ref
    db = MagicMock()
    with (
        patch.object(svc, "download_mime", return_value=raw),
    ):
        result = svc.process_email_received_event(
            {"data": {"contentUrl": "https://fake/download"}}, db
        )
    assert result["status"] == "orphaned"
    assert "no_tender_ref" in result["reason"]


def test_process_event_orphans_when_tender_not_in_db():
    raw = _build_mime_with_pdf("Re: Anbud [ref: TENDER-999-999]")
    db = MagicMock()
    db.query.return_value.get.return_value = None  # tender not found
    with patch.object(svc, "download_mime", return_value=raw):
        result = svc.process_email_received_event(
            {"data": {"contentUrl": "https://fake/download"}}, db
        )
    assert result["status"] == "orphaned"


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


def test_process_event_ingests_pdf_and_notifies_on_match():
    """Happy path — subject has ref, tender + recipient exist, PDF attached."""
    raw = _build_mime_with_pdf("Re: Anbud [ref: TENDER-5-42]")
    db = MagicMock()

    # db.query(Tender).get(5) → tender; db.query(TenderRecipient).get(42) → recipient
    def _get_router(model):
        m = MagicMock()
        if model.__name__ == "Tender":
            m.get.return_value = _FakeTender(5, 42, "123456789", "Equinor anbud")
        elif model.__name__ == "TenderRecipient":
            m.get.return_value = _FakeRecipient(42, 5, "Gjensidige")
        return m

    db.query.side_effect = _get_router

    mock_svc = MagicMock()
    mock_offer = MagicMock()
    mock_offer.id = 777
    mock_svc.upload_offer.return_value = mock_offer

    with (
        patch.object(svc, "download_mime", return_value=raw),
        patch.object(svc, "TenderService", return_value=mock_svc),
        patch.object(svc, "_notify_firm_of_offer") as mock_notify,
    ):
        result = svc.process_email_received_event(
            {"data": {"contentUrl": "https://fake/download"}}, db
        )
    assert result["status"] == "matched"
    assert result["tender_id"] == 5
    assert result["recipient_id"] == 42
    assert result["offer_id"] == 777
    assert result["pdf_attachments"] == 1
    mock_svc.upload_offer.assert_called_once()
    mock_notify.assert_called_once()
