"""Inbound email via Microsoft Graph change notifications.

Azure Communication Services does NOT publish an EmailReceived event
(outbound-only). We therefore run the anbud shared mailbox as an
Exchange Online mailbox and subscribe to Graph change notifications
for new messages in its Inbox. The webhook itself is in
`api/routers/msgraph_inbound.py`.

Flow per notification:

  1. Graph POSTs `{value: [{resource, changeType, ...}]}` to our webhook.
  2. We fetch an app-only token (MSAL client_credentials) and GET the
     message + attachments from `/v1.0/<resource>`.
  3. We normalise to the same `parsed` dict shape the ACS pipeline uses
     (subject, sender, recipient, text_body, attachments) and delegate
     to `inbound_email_service.match_and_ingest`.

Subscription lifecycle:
  Graph mail subscriptions expire after max 4230 min (~70h). Renewal is
  handled by a separate cron — see `create_subscription` /
  `renew_subscription` helpers below.
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

from api.adapters.msgraph_email_adapter import MsGraphConfig

_log = logging.getLogger(__name__)

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_TOKEN_URL_TMPL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
_GRAPH_SCOPE = "https://graph.microsoft.com/.default"

# Graph caps mail subscriptions at 4230 minutes — renew every 60h with
# a 10h margin to cover cron jitter + transient failures.
_SUBSCRIPTION_LIFETIME = timedelta(hours=60)


# ── Auth ─────────────────────────────────────────────────────────────────────


def fetch_graph_token(config: MsGraphConfig) -> str:
    """MSAL client credentials grant — returns a short-lived bearer token
    for application-scoped Graph calls. Raises on non-200."""
    token_url = _TOKEN_URL_TMPL.format(tenant=config.tenant_id)
    with httpx.Client(timeout=10.0) as client:
        resp = client.post(
            token_url,
            data={
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "scope": _GRAPH_SCOPE,
                "grant_type": "client_credentials",
            },
        )
    resp.raise_for_status()
    return resp.json()["access_token"]


# ── Notification payload → parsed dict ───────────────────────────────────────


def extract_resource_path(notification: Dict[str, Any]) -> Optional[str]:
    """Graph notifications carry `resource` like `Users/<id>/Messages/<id>`.
    Returns that path or None if the payload is malformed."""
    resource = notification.get("resource")
    if not isinstance(resource, str) or not resource:
        return None
    return resource.strip("/")


def _extract_sender(msg: Dict[str, Any]) -> str:
    from_field = msg.get("from") or {}
    email_addr = from_field.get("emailAddress") or {}
    return email_addr.get("address") or ""


def _extract_recipients(msg: Dict[str, Any]) -> str:
    out: List[str] = []
    for r in msg.get("toRecipients") or []:
        addr = (r.get("emailAddress") or {}).get("address")
        if addr:
            out.append(addr)
    return ",".join(out)


def _extract_body_text(msg: Dict[str, Any]) -> str:
    body = msg.get("body") or {}
    if body.get("contentType") == "text":
        return body.get("content") or ""
    # HTML bodies: return empty so downstream ref matching stays subject-based.
    # The ACS code only uses text_body for logging, not matching.
    return ""


def _decode_attachment(att: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if att.get("@odata.type") != "#microsoft.graph.fileAttachment":
        return None
    content_b64 = att.get("contentBytes") or ""
    try:
        content = base64.b64decode(content_b64)
    except Exception:
        _log.warning("msgraph_inbound: could not decode attachment %s", att.get("name"))
        return None
    return {
        "filename": att.get("name") or "untitled.bin",
        "content_type": att.get("contentType") or "",
        "content": content,
    }


def _fetch_attachments(
    resource_path: str, token: str, client: httpx.Client
) -> List[Dict[str, Any]]:
    url = f"{_GRAPH_BASE}/{resource_path}/attachments"
    resp = client.get(url, headers={"Authorization": f"Bearer {token}"})
    resp.raise_for_status()
    out: List[Dict[str, Any]] = []
    for att in resp.json().get("value") or []:
        decoded = _decode_attachment(att)
        if decoded is not None:
            out.append(decoded)
    return out


def fetch_and_parse_message(resource_path: str, token: str) -> Dict[str, Any]:
    """Given a Graph resource path, fetch the full message + attachments
    and build the `parsed` dict consumed by the inbound pipeline.

    `internetMessageId` is the RFC822 Message-ID — used downstream as the
    dedup key so replayed Graph notifications don't create duplicate
    TenderOffer rows."""
    msg_url = (
        f"{_GRAPH_BASE}/{resource_path}"
        "?$select=subject,from,toRecipients,body,hasAttachments,internetMessageId"
    )
    with httpx.Client(timeout=30.0) as client:
        msg_resp = client.get(msg_url, headers={"Authorization": f"Bearer {token}"})
        msg_resp.raise_for_status()
        msg = msg_resp.json()
        attachments: List[Dict[str, Any]] = []
        if msg.get("hasAttachments"):
            attachments = _fetch_attachments(resource_path, token, client)
    return {
        "subject": msg.get("subject") or "",
        "sender": _extract_sender(msg),
        "recipient": _extract_recipients(msg),
        "text_body": _extract_body_text(msg),
        "attachments": attachments,
        "message_id": msg.get("internetMessageId") or None,
    }


# ── Subscription management (for the renewal cron) ───────────────────────────


def _subscription_expiry_iso() -> str:
    # Graph wants ISO-8601 UTC with a trailing Z; +00:00 rejected.
    return (datetime.now(timezone.utc) + _SUBSCRIPTION_LIFETIME).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def create_subscription(
    config: MsGraphConfig,
    notification_url: str,
    client_state: str,
    token: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a change-notification subscription on the service mailbox's
    Inbox. `notification_url` is our webhook; `client_state` is a shared
    secret Graph echoes back on every callback so we can verify origin."""
    if token is None:
        token = fetch_graph_token(config)
    body = {
        "changeType": "created",
        "notificationUrl": notification_url,
        "resource": f"users/{config.service_mailbox}/mailFolders('Inbox')/messages",
        "expirationDateTime": _subscription_expiry_iso(),
        "clientState": client_state,
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{_GRAPH_BASE}/subscriptions",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=body,
        )
    resp.raise_for_status()
    return resp.json()


def renew_subscription(
    config: MsGraphConfig, subscription_id: str, token: Optional[str] = None
) -> Dict[str, Any]:
    """Extend an existing subscription's expiry. Called by the renewal
    cron well before the current expiry hits."""
    if token is None:
        token = fetch_graph_token(config)
    with httpx.Client(timeout=30.0) as client:
        resp = client.patch(
            f"{_GRAPH_BASE}/subscriptions/{subscription_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"expirationDateTime": _subscription_expiry_iso()},
        )
    resp.raise_for_status()
    return resp.json()


def list_subscriptions(
    config: MsGraphConfig, token: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Return all subscriptions visible to the app. Used by the renewal
    cron to find mail subscriptions and the admin page to surface state."""
    if token is None:
        token = fetch_graph_token(config)
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(
            f"{_GRAPH_BASE}/subscriptions",
            headers={"Authorization": f"Bearer {token}"},
        )
    resp.raise_for_status()
    return resp.json().get("value") or []
