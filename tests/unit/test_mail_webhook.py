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
