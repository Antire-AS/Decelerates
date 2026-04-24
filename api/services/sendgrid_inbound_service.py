"""Inbound email via SendGrid Inbound Parse.

Parallel to `msgraph_inbound_service` but for customers who don't
want to depend on Antire M365 + Graph admin consent. SendGrid's
Inbound Parse service:

  1. Accepts mail at `<local>@<your-domain>` via MX record pointing at
     `mx.sendgrid.net`.
  2. For each message, POSTs `multipart/form-data` to a configured
     webhook URL with parsed fields (from, to, subject, text, html,
     attachments[]).

We normalise the payload to the shared `parsed` dict shape and funnel
into `inbound_email_service.match_and_ingest` — same matching, dedup,
notify logic as the Graph path.

Optional forwarding: if `SENDGRID_FORWARD_TO` is set, we also call
SendGrid's Mail Send API after ingesting to forward a readable copy of
the mail to a personal inbox. Lets the broker see replies in their
normal Outlook/Gmail while the app handles the auto-ingest.
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

_log = logging.getLogger(__name__)

_SENDGRID_SEND_URL = "https://api.sendgrid.com/v3/mail/send"


@dataclass(frozen=True)
class SendGridConfig:
    """Frozen config — read once in api/main.py per the Antire convention."""

    api_key: str = ""
    inbound_token: str = ""  # shared secret in webhook URL query param
    forward_to: str = ""  # optional personal inbox to mirror mail into
    forward_from: str = ""  # envelope-from for forwarded copies


def is_configured(config: SendGridConfig) -> bool:
    """Only the API key is strictly required — the rest gates optional behaviour."""
    return bool(config.api_key)


# ── SendGrid Inbound Parse payload → parsed dict ─────────────────────────────


def _decode_attachment(
    filename: str, content_type: str, payload: Any
) -> Optional[Dict[str, Any]]:
    """SendGrid sends attachments as UploadFile objects (FastAPI parses
    multipart/form-data). Extract bytes; skip non-PDFs later if we want."""
    try:
        if hasattr(payload, "file") and hasattr(payload.file, "read"):
            content = payload.file.read()
        elif isinstance(payload, (bytes, bytearray)):
            content = bytes(payload)
        else:
            return None
    except Exception:
        _log.warning("sendgrid_inbound: could not read attachment %s", filename)
        return None
    return {
        "filename": filename,
        "content_type": content_type or "",
        "content": content,
    }


def _attachments_from_form(form: Dict[str, Any]) -> List[Dict[str, Any]]:
    """SendGrid Inbound Parse lists attachments as attachment1, attachment2,
    ... with a JSON 'attachment-info' field describing filename + type per
    index. We walk the numbered keys and build the list."""
    meta_raw = form.get("attachment-info") or "{}"
    try:
        meta = json.loads(meta_raw) if isinstance(meta_raw, str) else meta_raw
    except Exception:
        meta = {}
    out: List[Dict[str, Any]] = []
    i = 1
    while True:
        key = f"attachment{i}"
        if key not in form:
            break
        info = meta.get(key, {}) if isinstance(meta, dict) else {}
        decoded = _decode_attachment(
            filename=info.get("filename") or f"attachment-{i}.bin",
            content_type=info.get("type") or "",
            payload=form[key],
        )
        if decoded is not None:
            out.append(decoded)
        i += 1
    return out


def normalise_inbound_form(form: Dict[str, Any]) -> Dict[str, Any]:
    """Turn a SendGrid Inbound Parse form payload into the shared `parsed`
    dict. Headers block carries Message-ID which we plumb through as the
    dedup key — same contract as the Graph path."""
    headers_raw = form.get("headers") or ""
    message_id: Optional[str] = None
    for line in headers_raw.splitlines():
        if ":" in line:
            name, _, value = line.partition(":")
            if name.strip().lower() == "message-id":
                message_id = value.strip()
                break
    return {
        "subject": (form.get("subject") or "").strip(),
        "sender": (form.get("from") or "").strip(),
        "recipient": (form.get("to") or "").strip(),
        "text_body": form.get("text") or "",
        "attachments": _attachments_from_form(form),
        "message_id": message_id,
    }


# ── Optional forwarding to personal inbox ────────────────────────────────────


def _build_forward_envelope(
    config: SendGridConfig, parsed: Dict[str, Any]
) -> Dict[str, Any]:
    """Assemble the SendGrid Mail Send payload for a forwarded copy."""
    body_text = (
        f"Forwarded from anbud@<your-domain>\n"
        f"From: {parsed.get('sender')}\n"
        f"To: {parsed.get('recipient')}\n"
        f"Subject: {parsed.get('subject')}\n\n"
        f"{parsed.get('text_body') or ''}"
    )
    envelope: Dict[str, Any] = {
        "personalizations": [{"to": [{"email": config.forward_to}]}],
        "from": {"email": config.forward_from},
        "subject": f"[anbud-fwd] {parsed.get('subject') or '(no subject)'}",
        "content": [{"type": "text/plain", "value": body_text}],
    }
    attachments = parsed.get("attachments") or []
    if attachments:
        envelope["attachments"] = [
            {
                "content": base64.b64encode(a["content"]).decode(),
                "type": a.get("content_type") or "application/octet-stream",
                "filename": a.get("filename") or "attachment.bin",
                "disposition": "attachment",
            }
            for a in attachments
        ]
    return envelope


def forward_copy_via_sendgrid(config: SendGridConfig, parsed: Dict[str, Any]) -> None:
    """Send a plain-text copy of the parsed mail to `forward_to`. Fire-and-
    log-fail — a forward failure must never hold up the webhook ack."""
    if not config.forward_to or not config.api_key:
        return
    if not config.forward_from:
        _log.debug("sendgrid forward skipped — forward_from unset")
        return
    envelope = _build_forward_envelope(config, parsed)
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                _SENDGRID_SEND_URL,
                headers={
                    "Authorization": f"Bearer {config.api_key}",
                    "Content-Type": "application/json",
                },
                json=envelope,
            )
        if resp.status_code >= 300:
            _log.warning(
                "sendgrid forward: non-2xx %s — %s", resp.status_code, resp.text[:200]
            )
    except Exception as exc:
        _log.warning("sendgrid forward failed — %s", exc)
