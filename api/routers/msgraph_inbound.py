"""Microsoft Graph change-notification webhook for inbound email.

Graph posts here whenever a new message lands in the anbud shared
mailbox's Inbox. Two response modes:

  1. Subscription setup handshake: Graph sends a GET/POST with the query
     string `?validationToken=<token>` and expects the raw token back as
     `text/plain` 200 within 10s. Otherwise the subscription never
     activates. This applies to BOTH subscription create + renew.

  2. Normal delivery: `{ "value": [<notification>, ...] }`. For each
     notification we fetch the message via Graph and run it through
     `inbound_email_service.match_and_ingest`.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session

from api.adapters.msgraph_email_adapter import MsGraphConfig
from api.auth import CurrentUser, require_role
from api.dependencies import get_db
from api.services.inbound_email_service import match_and_ingest
from api.services.msgraph_inbound_service import (
    create_subscription,
    extract_resource_path,
    fetch_and_parse_message,
    fetch_graph_token,
    list_subscriptions,
    renew_subscription,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_msgraph_config() -> MsGraphConfig:
    """Read Graph creds lazily. Kept in the router layer (not main.py)
    because this is Phase 2 infrastructure — the main.py central-env-var
    convention applies only to Phase 1 adapters today."""
    return MsGraphConfig(
        tenant_id=os.getenv("AZURE_AD_TENANT_ID", ""),
        client_id=os.getenv("AZURE_AD_CLIENT_ID", ""),
        client_secret=os.getenv("AZURE_AD_CLIENT_SECRET", ""),
        service_mailbox=os.getenv("MS_GRAPH_SERVICE_MAILBOX", ""),
    )


def _verify_client_state(notifications: List[Dict[str, Any]], expected: str) -> bool:
    """Graph echoes the clientState secret we set at subscription create
    on every callback. If any notification's clientState disagrees, we
    treat the whole batch as spoofed."""
    if not expected:
        # No expected state configured — skip check (first-run / dev).
        return True
    for n in notifications:
        if n.get("clientState") != expected:
            return False
    return True


def _process_notifications(
    notifications: List[Dict[str, Any]],
    token: str,
    db: Session,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for notification in notifications:
        try:
            results.append(_process_one(notification, token, db))
        except Exception as exc:
            logger.exception("Failed to process Graph notification")
            results.append({"status": "error", "reason": str(exc)})
    return results


def _process_one(
    notification: Dict[str, Any], token: str, db: Session
) -> Dict[str, Any]:
    resource = extract_resource_path(notification)
    if not resource:
        return {"status": "skipped", "reason": "no_resource"}
    parsed = fetch_and_parse_message(resource, token)
    return match_and_ingest(parsed, db)


@router.api_route(
    "/webhooks/msgraph/inbound",
    methods=["GET", "POST"],
    include_in_schema=False,
)
async def msgraph_inbound(
    request: Request,
    validationToken: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> Any:
    # Graph's handshake — echo the token as plain text for subscription
    # create + renew. Must happen before we try to parse JSON body.
    if validationToken is not None:
        return PlainTextResponse(content=validationToken, status_code=200)

    try:
        payload = await request.json()
    except Exception:
        return {"processed": 0, "error": "invalid_json"}

    notifications: List[Dict[str, Any]] = payload.get("value") or []
    if not notifications:
        return {"processed": 0, "results": []}

    expected_state = os.getenv("MS_GRAPH_SUBSCRIPTION_CLIENT_STATE", "")
    if not _verify_client_state(notifications, expected_state):
        logger.warning("msgraph_inbound: clientState mismatch — dropping batch")
        return {"processed": 0, "error": "client_state_mismatch"}

    config = _get_msgraph_config()
    if not config.tenant_id or not config.client_id:
        logger.warning("msgraph_inbound: Graph creds missing — skipping batch")
        return {"processed": 0, "error": "graph_not_configured"}

    try:
        token = fetch_graph_token(config)
    except Exception as exc:
        logger.exception("msgraph_inbound: token fetch failed")
        return {"processed": 0, "error": f"token_fetch: {exc}"}

    results = _process_notifications(notifications, token, db)
    return {"processed": len(results), "results": results}


# ── Admin-only management endpoints ──────────────────────────────────────────
#
# One-shot bootstrap for the Graph subscription + a renewal endpoint the
# cron workflow pokes daily. Both require admin role.


@router.post("/admin/msgraph-inbound/create-subscription")
def admin_create_subscription(
    _user: CurrentUser = Depends(require_role("admin")),
) -> Dict[str, Any]:
    """Bootstrap: create the initial subscription pointing at this app's
    webhook. Idempotent caller responsibility — if a subscription already
    exists on the same mailbox, Graph happily creates a second one. Check
    `list-subscriptions` first if unsure."""
    config = _get_msgraph_config()
    notification_url = os.getenv(
        "MS_GRAPH_INBOUND_NOTIFICATION_URL",
        "https://meglerai.no/bapi/webhooks/msgraph/inbound",
    )
    client_state = os.getenv("MS_GRAPH_SUBSCRIPTION_CLIENT_STATE", "")
    if not client_state:
        return {
            "status": "error",
            "reason": "MS_GRAPH_SUBSCRIPTION_CLIENT_STATE unset — refusing to create "
            "unauthenticated subscription",
        }
    return create_subscription(config, notification_url, client_state)


@router.get("/admin/msgraph-inbound/subscriptions")
def admin_list_subscriptions(
    _user: CurrentUser = Depends(require_role("admin")),
) -> Dict[str, Any]:
    """List active Graph subscriptions on this tenant. Read-only."""
    return {"subscriptions": list_subscriptions(_get_msgraph_config())}


@router.post("/admin/msgraph-inbound/renew-subscriptions")
def admin_renew_subscriptions(
    _user: CurrentUser = Depends(require_role("admin")),
) -> Dict[str, Any]:
    """Renew every mail subscription owned by the app. Called daily by
    GH workflow `msgraph-subscription-renew.yml`. Returns per-id status
    so the workflow log shows what happened."""
    config = _get_msgraph_config()
    subs = list_subscriptions(config)
    results: List[Dict[str, Any]] = []
    for s in subs:
        sub_id = s.get("id")
        if not sub_id:
            continue
        try:
            renewed = renew_subscription(config, sub_id)
            results.append(
                {
                    "id": sub_id,
                    "status": "renewed",
                    "expirationDateTime": renewed.get("expirationDateTime"),
                }
            )
        except Exception as exc:
            logger.exception("Failed to renew subscription %s", sub_id)
            results.append({"id": sub_id, "status": "error", "reason": str(exc)})
    return {"count": len(results), "results": results}


# ── Public health check (for uptime monitors) ───────────────────────────────
#
# Unauthenticated so an external monitor (Azure Monitor, UptimeRobot, etc.)
# can poll it without a bearer token. Returns only high-level state; no
# subscription IDs or client-state secrets.

_HEALTH_WARN_MINUTES = 240  # 4h — below this we consider the subscription at
# risk of expiring before the next cron tick picks it up (cron runs daily).


def _parse_graph_expiry(value: Optional[str]) -> Optional[datetime]:
    """Graph returns `expirationDateTime` as ISO-8601 with a trailing `Z`.
    Parse to a tz-aware datetime. Returns None on any parse failure so
    the caller degrades gracefully to 'no active subscription'."""
    if not value:
        return None
    try:
        normalised = value.rstrip("Z")
        dt = datetime.fromisoformat(normalised)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _pick_active_mail_subscription(
    subscriptions: List[Dict[str, Any]], service_mailbox: str
) -> Optional[Dict[str, Any]]:
    """Pick the inbox subscription for our service mailbox. If several
    exist (e.g. orphaned renewals), we prefer the one expiring latest
    so the monitor reports the most optimistic live state."""
    candidates: List[Dict[str, Any]] = []
    mailbox_lower = service_mailbox.lower()
    for sub in subscriptions:
        resource = (sub.get("resource") or "").lower()
        # Match `users/<mailbox>/mailFolders('Inbox')/messages` shape.
        if mailbox_lower in resource and "inbox" in resource and "messages" in resource:
            candidates.append(sub)
    if not candidates:
        return None
    candidates.sort(
        key=lambda s: (
            _parse_graph_expiry(s.get("expirationDateTime"))
            or datetime.min.replace(tzinfo=timezone.utc)
        ),
        reverse=True,
    )
    return candidates[0]


def _degraded(reason: str, **extra: Any) -> JSONResponse:
    """503 payload shared across every failure branch."""
    return JSONResponse(
        status_code=503, content={"status": "degraded", "reason": reason, **extra}
    )


def _compute_health(config: MsGraphConfig) -> JSONResponse:
    """Core health logic — split out so the outer route function stays short."""
    try:
        token = fetch_graph_token(config)
        subs = list_subscriptions(config, token=token)
    except Exception as exc:
        logger.warning("msgraph_inbound health: graph call failed — %s", exc)
        return _degraded(f"graph_unreachable: {exc}")
    active = _pick_active_mail_subscription(subs, config.service_mailbox)
    if active is None:
        return _degraded("no_active_subscription")
    expiry = _parse_graph_expiry(active.get("expirationDateTime"))
    if expiry is None:
        return _degraded("unparseable_expiry")
    minutes_left = int((expiry - datetime.now(timezone.utc)).total_seconds() / 60)
    if minutes_left < _HEALTH_WARN_MINUTES:
        return _degraded("expiring_soon", expires_in_minutes=minutes_left)
    return JSONResponse(
        status_code=200,
        content={"status": "ok", "expires_in_minutes": minutes_left},
    )


@router.get("/health/msgraph-inbound", include_in_schema=False)
def msgraph_inbound_health() -> JSONResponse:
    """Public health probe for uptime monitoring.

    - 200 {status: "ok", expires_in_minutes: N}  when a mail subscription
      exists on the service mailbox and has more than 4h until expiry.
    - 503 otherwise — missing env vars, no active subscription, expired,
      or Graph call failed.
    """
    config = _get_msgraph_config()
    if not config.tenant_id or not config.client_id or not config.service_mailbox:
        return _degraded("graph_not_configured")
    return _compute_health(config)
