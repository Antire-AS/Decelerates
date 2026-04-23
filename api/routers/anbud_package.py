"""Anbudspakke-PDF download + email endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from api.container import resolve
from api.db import Company
from api.dependencies import get_db
from api.domain.exceptions import NotFoundError
from api.ports.driven.notification_port import EmailAttachment, NotificationPort
from api.schemas import AnbudspakkeEmailOut, AnbudspakkeEmailRequest
from api.services.audit import log_audit
from api.services.pdf_anbud import build_anbudspakke_data, generate_anbudspakke_pdf

router = APIRouter()


def _get_notification() -> NotificationPort:
    return resolve(NotificationPort)  # type: ignore[return-value]


@router.get("/org/{orgnr}/anbudspakke.pdf")
def download_anbudspakke(orgnr: str, db: Session = Depends(get_db)) -> Response:
    """Return a PDF bundling all underwriting-relevant data about the
    company — one document the broker attaches when soliciting offers
    from insurers. No auth wall beyond what /org/{orgnr} already has."""
    try:
        data = build_anbudspakke_data(orgnr, db)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    pdf_bytes = generate_anbudspakke_pdf(data)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="anbudspakke-{orgnr}.pdf"',
        },
    )


def _default_email_body(client_navn: str, broker_message: str | None) -> str:
    """Build the HTML body for the anbudspakke email. Includes the broker's
    optional free-text message above a short fixed intro that orients the
    insurer (who we are, what the attachment is, what to do next)."""
    prefix = ""
    if broker_message:
        prefix = (
            f"<p style='margin-bottom:16px'>{broker_message}</p>"
            "<hr style='border:none;border-top:1px solid #e5e5e5;margin:16px 0'/>"
        )
    return f"""<html><body style='font-family:Arial,sans-serif;font-size:14px;color:#222'>
{prefix}
<p>Hei,</p>
<p>
Vi sender herved risikounderlag for <strong>{client_navn}</strong> med anmodning om
indikativt forsikringstilbud. Vedlagt PDF inneholder samlet selskapsinformasjon,
5 års finansiell utvikling, Altman-basert risikoprofil, peer-sammenligning,
vurdering av forsikringsbehov, meglers notater og materielle hendelser siste 30 dager.
</p>
<p>
Svar på denne eposten med tilbud og forutsetninger, eller kontakt oss om dere trenger
ytterligere informasjon før prising.
</p>
<p style='margin-top:24px;color:#666;font-size:12px'>
Med vennlig hilsen,<br/>
Broker Accelerator
</p>
</body></html>"""


def _build_email_payload(orgnr: str, body: AnbudspakkeEmailRequest, db: Session):
    """Assemble the PDF bytes, subject line, and HTML body the email send
    call needs. Extracted from the route handler so it stays ≤40 lines."""
    company = db.query(Company).filter(Company.orgnr == orgnr).first()
    if not company:
        raise HTTPException(status_code=404, detail=f"Company {orgnr} not found")
    try:
        data = build_anbudspakke_data(orgnr, db)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    pdf_bytes = generate_anbudspakke_pdf(data)
    navn = company.navn or orgnr
    subject = body.subject or f"Forespørsel om forsikringstilbud — {navn}"
    body_html = _default_email_body(navn, body.message)
    attachment = EmailAttachment(
        filename=f"anbudspakke-{orgnr}.pdf",
        content_type="application/pdf",
        content=pdf_bytes,
    )
    return subject, body_html, attachment


@router.post(
    "/org/{orgnr}/anbudspakke/email",
    response_model=AnbudspakkeEmailOut,
)
def email_anbudspakke(
    orgnr: str,
    body: AnbudspakkeEmailRequest,
    db: Session = Depends(get_db),
    notifier: NotificationPort = Depends(_get_notification),
) -> dict:
    """Generate the anbudspakke PDF and email it as an attachment to the
    insurer. `to` is the insurer email, `subject` and `message` are
    optional overrides. Returns {sent, to, subject}."""
    subject, body_html, attachment = _build_email_payload(orgnr, body, db)
    sent = notifier.send_email_with_attachments(
        to=body.to,
        subject=subject,
        body_html=body_html,
        attachments=[attachment],
        cc=body.cc or None,
    )
    if not sent:
        raise HTTPException(
            status_code=503,
            detail=(
                "Email-tjenesten er ikke konfigurert. Sjekk "
                "AZURE_COMMUNICATION_CONNECTION_STRING."
            ),
        )
    log_audit(
        db,
        "anbudspakke.email_sent",
        orgnr=orgnr,
        detail={"to": body.to, "subject": subject, "cc_count": len(body.cc or [])},
    )
    return {"sent": True, "to": body.to, "subject": subject}
