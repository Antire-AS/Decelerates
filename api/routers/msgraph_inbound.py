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
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse
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
