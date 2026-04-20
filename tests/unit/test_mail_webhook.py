"""Unit tests for the inbound mail webhook helpers.

Covers the pure functions (parsing, token extraction, attachment
classification). DB-dependent routing is covered via integration tests.
"""

import base64

from api.services.mail_webhook import (
    InboundAttachment,
    ParsedMail,
    _decode_attachment,
    _is_offer_attachment,
    extract_recipient_token,
    parse_mail_payload,
)


# ── extract_recipient_token ──────────────────────────────────────────────────


def test_extract_token_from_valid_address() -> None:
    addr = "tender-AbCdEf_1234567890xyz-ABCDEF@broker.example"
    assert extract_recipient_token(addr) == "AbCdEf_1234567890xyz-ABCDEF"


def test_extract_token_plain_address_returns_none() -> None:
    assert extract_recipient_token("hello@broker.example") is None


def test_extract_token_wrong_prefix_returns_none() -> None:
    assert extract_recipient_token("policy-abcdef@broker.example") is None


def test_extract_token_short_token_rejected() -> None:
    """Tokens under 20 chars are almost certainly not from secrets.token_urlsafe(32)."""
    assert extract_recipient_token("tender-short@broker.example") is None


def test_extract_token_empty_string() -> None:
    assert extract_recipient_token("") is None


# ── parse_mail_payload ───────────────────────────────────────────────────────


def test_parse_payload_full() -> None:
    payload = {
        "to": "tender-tok@broker.example",
        "from": "insurer@gjensidige.no",
        "subject": "Re: Anbud DNB",
        "attachments": [
            {
                "filename": "tilbud.pdf",
                "content_type": "application/pdf",
                "content_base64": "AAA=",
            },
            {
                "filename": "ark.xlsx",
                "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "content_base64": "BBB=",
            },
        ],
    }
    mail = parse_mail_payload(payload)
    assert mail.to_address == "tender-tok@broker.example"
    assert mail.from_address == "insurer@gjensidige.no"
    assert mail.subject == "Re: Anbud DNB"
    assert len(mail.attachments) == 2
    assert mail.attachments[0].filename == "tilbud.pdf"


def test_parse_payload_missing_fields_defaults_empty() -> None:
    mail = parse_mail_payload({})
    assert mail.to_address == ""
    assert mail.attachments == []


def test_parse_payload_skips_malformed_attachments() -> None:
    payload = {
        "to": "x@y",
        "attachments": [
            {"filename": "ok.pdf", "content_base64": "AA=="},
            {"filename": "", "content_base64": "AA=="},  # empty filename
            {"filename": "no-content.pdf"},  # missing base64
            "not-a-dict",
        ],
    }
    mail = parse_mail_payload(payload)
    assert [a.filename for a in mail.attachments] == ["ok.pdf"]


# ── _is_offer_attachment ─────────────────────────────────────────────────────


def test_is_offer_pdf_by_extension() -> None:
    att = InboundAttachment(filename="tilbud.pdf", content_type="", content_base64="")
    assert _is_offer_attachment(att) is True


def test_is_offer_xlsx_by_extension() -> None:
    att = InboundAttachment(filename="prising.xlsx", content_type="", content_base64="")
    assert _is_offer_attachment(att) is True


def test_is_offer_by_content_type_even_if_extension_missing() -> None:
    att = InboundAttachment(
        filename="no-ext-file", content_type="application/pdf", content_base64=""
    )
    assert _is_offer_attachment(att) is True


def test_is_not_offer_for_random_image() -> None:
    att = InboundAttachment(
        filename="logo.png", content_type="image/png", content_base64=""
    )
    assert _is_offer_attachment(att) is False


# ── _decode_attachment ───────────────────────────────────────────────────────


def test_decode_valid_base64() -> None:
    original = b"hello world"
    att = InboundAttachment(
        filename="x.pdf",
        content_type="application/pdf",
        content_base64=base64.b64encode(original).decode("ascii"),
    )
    assert _decode_attachment(att) == original


def test_decode_invalid_base64_returns_none() -> None:
    att = InboundAttachment(
        filename="x.pdf", content_type="", content_base64="!!!not-base64!!!"
    )
    assert _decode_attachment(att) is None


# ── integration between ParsedMail + helpers ────────────────────────────────


def test_parsedmail_is_immutable_like_dataclass() -> None:
    """Sanity: ParsedMail is a dataclass with the expected fields."""
    mail = ParsedMail(to_address="a", from_address="b", subject="c", attachments=[])
    assert mail.to_address == "a"


# ── process_inbound_mail (mocked DB) ─────────────────────────────────────────


def test_process_inbound_rejects_address_without_token(monkeypatch) -> None:
    """If the To address isn't `tender-<token>@...`, we return matched=False
    without touching the DB — no lookup, no insert."""
    from api.services import mail_webhook

    called = {"n": 0}

    def _boom(*args, **kwargs):
        called["n"] += 1
        return None

    monkeypatch.setattr(mail_webhook, "find_recipient", _boom)
    mail = ParsedMail(
        to_address="hello@broker.example",
        from_address="x@y",
        subject="",
        attachments=[],
    )
    result = mail_webhook.process_inbound_mail(db=None, mail=mail)  # type: ignore[arg-type]
    assert result == {"matched": False, "reason": "no-token-in-address"}
    assert called["n"] == 0


def test_process_inbound_rejects_unknown_token(monkeypatch) -> None:
    """Address has the right shape but token doesn't map to a recipient."""
    from api.services import mail_webhook

    monkeypatch.setattr(mail_webhook, "find_recipient", lambda _db, _token: None)
    mail = ParsedMail(
        to_address="tender-AbCdEf_1234567890xyz-ABCDEF@broker.example",
        from_address="x@y",
        subject="",
        attachments=[],
    )
    result = mail_webhook.process_inbound_mail(db=None, mail=mail)  # type: ignore[arg-type]
    assert result == {"matched": False, "reason": "token-unknown"}


def test_process_inbound_happy_path_stores_offers(monkeypatch) -> None:
    """Valid token + a PDF attachment → upload_offer called, status → received."""
    from api.services import mail_webhook
    from types import SimpleNamespace

    # Fake recipient + tender
    recipient = SimpleNamespace(
        id=42,
        tender_id=7,
        insurer_name="Gjensidige",
        status=None,
        response_at=None,
    )
    monkeypatch.setattr(mail_webhook, "find_recipient", lambda _db, _token: recipient)

    uploaded_offers: list = []

    class _FakeSvc:
        def __init__(self, _db):
            pass

        def upload_offer(
            self, tender_id, insurer_name, filename, pdf_bytes, recipient_id
        ):
            uploaded_offers.append(
                {
                    "tender_id": tender_id,
                    "insurer_name": insurer_name,
                    "filename": filename,
                    "size": len(pdf_bytes),
                    "recipient_id": recipient_id,
                }
            )
            return SimpleNamespace(id=100 + len(uploaded_offers))

    monkeypatch.setattr(mail_webhook, "TenderService", _FakeSvc)

    class _FakeDB:
        def __init__(self):
            self.commits = 0

        def commit(self):
            self.commits += 1

    db = _FakeDB()

    mail = ParsedMail(
        to_address="tender-AbCdEf_1234567890xyz-ABCDEF@broker.example",
        from_address="insurer@gjensidige.no",
        subject="Re: Anbud DNB",
        attachments=[
            InboundAttachment(
                filename="tilbud.pdf",
                content_type="application/pdf",
                content_base64=base64.b64encode(b"%PDF-1.4 fake").decode("ascii"),
            ),
            InboundAttachment(
                filename="logo.png",
                content_type="image/png",
                content_base64=base64.b64encode(b"notpdf").decode("ascii"),
            ),
        ],
    )
    result = mail_webhook.process_inbound_mail(db=db, mail=mail)  # type: ignore[arg-type]

    # One PDF stored, one skipped (image)
    assert result["matched"] is True
    assert result["tender_id"] == 7
    assert result["recipient_id"] == 42
    assert len(result["stored_offer_ids"]) == 1
    assert len(result["skipped"]) == 1
    assert "logo.png" in result["skipped"][0]
    # Recipient flipped to received
    from api.models.tender import TenderRecipientStatus

    assert recipient.status == TenderRecipientStatus.received
    assert recipient.response_at is not None
    assert db.commits == 1
    # upload_offer called with the right args
    assert uploaded_offers[0]["tender_id"] == 7
    assert uploaded_offers[0]["filename"] == "tilbud.pdf"


def test_process_inbound_skips_undecodable_attachment(monkeypatch) -> None:
    """Bad base64 → skipped with 'decode failed' reason, no DB write."""
    from api.services import mail_webhook
    from types import SimpleNamespace

    recipient = SimpleNamespace(
        id=42, tender_id=7, insurer_name="If", status=None, response_at=None
    )
    monkeypatch.setattr(mail_webhook, "find_recipient", lambda _db, _token: recipient)

    class _FakeSvc:
        def __init__(self, _db):
            pass

        def upload_offer(self, **_kwargs):
            raise AssertionError("should not upload undecodable")

    monkeypatch.setattr(mail_webhook, "TenderService", _FakeSvc)

    class _FakeDB:
        def commit(self):
            pass

    mail = ParsedMail(
        to_address="tender-AbCdEf_1234567890xyz-ABCDEF@broker.example",
        from_address="x@y",
        subject="",
        attachments=[
            InboundAttachment(
                filename="broken.pdf",
                content_type="application/pdf",
                content_base64="!!!not-base64!!!",
            )
        ],
    )
    result = mail_webhook.process_inbound_mail(db=_FakeDB(), mail=mail)  # type: ignore[arg-type]
    assert result["stored_offer_ids"] == []
    assert len(result["skipped"]) == 1
    assert "decode failed" in result["skipped"][0]
    # Recipient NOT flipped because nothing was stored
    assert recipient.status is None
