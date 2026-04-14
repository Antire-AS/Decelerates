"""Broker-composes-and-sends email — plan §🟢 #10.

POST /email/compose sends a single email via MS Graph + auto-creates an
Activity row of type=email so the timeline reflects what was sent.

Returns 503 when the MS Graph adapter is not configured (env vars missing).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.container import resolve
from api.dependencies import get_db
from api.ports.driven.email_outbound_port import EmailOutboundPort
from api.schemas import EmailComposeIn, EmailComposeOut
from api.services.audit import log_audit
from api.services.email_compose_service import EmailComposeService

router = APIRouter()


def _get_email_port() -> EmailOutboundPort:
    return resolve(EmailOutboundPort)  # type: ignore[return-value]


@router.post("/email/compose", response_model=EmailComposeOut)
def compose_email(
    body: EmailComposeIn,
    db: Session = Depends(get_db),
    email_port: EmailOutboundPort = Depends(_get_email_port),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    if not email_port.is_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "Microsoft Graph e-post er ikke konfigurert. Sett AZURE_AD_TENANT_ID, "
                "AZURE_AD_CLIENT_ID, AZURE_AD_CLIENT_SECRET og MS_GRAPH_SERVICE_MAILBOX."
            ),
        )
    svc = EmailComposeService(db, email_port)
    try:
        activity = svc.compose_and_send(
            orgnr=body.orgnr,
            firm_id=user.firm_id,
            to=body.to,
            subject=body.subject,
            body_html=body.body_html,
            author_email=user.email,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"E-postsending feilet: {exc}")
    log_audit(db, "email.send", orgnr=body.orgnr, detail={"to": body.to, "subject": body.subject})
    return {"sent": True, "activity_id": activity.id}
