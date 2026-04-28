"""Tender (anbud) service — structured bidding process for insurance placement.

Flow: Create tender → Add recipients → Send invitations → Collect offers →
AI comparison → Broker makes decision.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from api.db import (
    Tender,
    TenderRecipient,
    TenderOffer,
    TenderStatus,
    TenderRecipientStatus,
    Company,
)

logger = logging.getLogger(__name__)

_COMPARISON_PROMPT = """Du er en ekspert forsikringsmegler. Sammenlign følgende forsikringstilbud og returner en JSON-struktur:

{
  "anbefaling": {
    "forsikringsgiver": "navn på anbefalt selskap",
    "begrunnelse": "kort begrunnelse for anbefalingen"
  },
  "sammenligning": [
    {
      "kategori": "Premie / Dekning / Egenandel / Vilkår / Unntak / Karenstid",
      "felter": [
        {
          "felt": "navn på dekningspunkt",
          "verdier": {"SelskapA": "verdi", "SelskapB": "verdi"},
          "kommentar": "vesentlig forskjell å merke seg",
          "konfidens": "høy/middels/lav"
        }
      ]
    }
  ],
  "nøkkelforskjeller": ["liste over de viktigste forskjellene"],
  "oppsummering": "2-3 setninger om samlet vurdering"
}

Vær nøyaktig. Marker felt med lav konfidens der tallene er usikre.
Returner KUN gyldig JSON."""


class TenderService:
    """Manages the tender lifecycle."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        orgnr: str,
        firm_id: int,
        title: str,
        product_types: list,
        deadline=None,
        notes: Optional[str] = None,
        created_by_email: Optional[str] = None,
        recipients: Optional[list] = None,
    ) -> Tender:
        tender = Tender(
            orgnr=orgnr,
            firm_id=firm_id,
            created_by_email=created_by_email,
            title=title,
            product_types=product_types,
            deadline=deadline,
            notes=notes,
            status=TenderStatus.draft,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(tender)
        self.db.flush()

        for r in recipients or []:
            self.db.add(
                TenderRecipient(
                    tender_id=tender.id,
                    insurer_name=r.get("insurer_name", r.get("name", "")),
                    insurer_email=r.get("insurer_email", r.get("email")),
                    status=TenderRecipientStatus.pending,
                    created_at=datetime.now(timezone.utc),
                )
            )

        self.db.commit()
        self.db.refresh(tender)
        return tender

    def get(self, tender_id: int, firm_id: int) -> Optional[Tender]:
        return (
            self.db.query(Tender)
            .filter(Tender.id == tender_id, Tender.firm_id == firm_id)
            .first()
        )

    def list_all(self, firm_id: int) -> list:
        return (
            self.db.query(Tender)
            .filter(Tender.firm_id == firm_id)
            .order_by(Tender.created_at.desc())
            .all()
        )

    def list_for_company(self, orgnr: str, firm_id: int) -> list:
        return (
            self.db.query(Tender)
            .filter(Tender.orgnr == orgnr, Tender.firm_id == firm_id)
            .order_by(Tender.created_at.desc())
            .all()
        )

    def update(self, tender_id: int, firm_id: int, **kwargs) -> Optional[Tender]:
        tender = self.get(tender_id, firm_id)
        if not tender:
            return None
        for k, v in kwargs.items():
            if v is not None and hasattr(tender, k):
                if k == "status":
                    v = TenderStatus(v)
                setattr(tender, k, v)
        self.db.commit()
        self.db.refresh(tender)
        return tender

    def delete(self, tender_id: int, firm_id: int) -> bool:
        tender = self.get(tender_id, firm_id)
        if not tender:
            return False
        self.db.delete(tender)
        self.db.commit()
        return True

    def mark_contract_signed_by_session(
        self, contract_session_id: str
    ) -> Optional[Tender]:
        """Find the tender that was sent for signature under this provider
        session and flip its status to `analysed` (the terminal state for the
        anbud workflow — contract signed, loop closed).

        Called from the public `/webhooks/docuseal` endpoint, which has no
        auth context and therefore no firm_id. The lookup is by the session
        id alone; the partial unique index on `contract_session_id` (see
        migration `h4i5j6k7l8m9`) guarantees at most one row matches.
        """
        if not contract_session_id:
            return None
        tender = (
            self.db.query(Tender)
            .filter(Tender.contract_session_id == contract_session_id)
            .first()
        )
        if not tender:
            return None
        tender.status = TenderStatus.analysed
        self.db.commit()
        self.db.refresh(tender)
        return tender

    def get_recipients(self, tender_id: int) -> list:
        return (
            self.db.query(TenderRecipient)
            .filter(TenderRecipient.tender_id == tender_id)
            .all()
        )

    def add_recipient(
        self, tender_id: int, insurer_name: str, insurer_email: Optional[str] = None
    ) -> TenderRecipient:
        import secrets as _secrets

        r = TenderRecipient(
            tender_id=tender_id,
            insurer_name=insurer_name,
            insurer_email=insurer_email,
            # Generate access token up-front so the broker can copy-paste the
            # insurer link even before "Send invitations" runs.
            access_token=_secrets.token_urlsafe(32),
            status=TenderRecipientStatus.pending,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(r)
        self.db.commit()
        self.db.refresh(r)
        return r

    def get_recipient_by_token(self, access_token: str) -> Optional[TenderRecipient]:
        """Load a recipient by its public access token. Used by the insurer portal."""
        return (
            self.db.query(TenderRecipient)
            .filter(TenderRecipient.access_token == access_token)
            .first()
        )

    def mark_declined(
        self,
        tender_id: int,
        recipient_id: int,
        reason: str,
        note: Optional[str] = None,
    ) -> TenderRecipient:
        """Flip a recipient to `declined` and persist why."""
        r = (
            self.db.query(TenderRecipient)
            .filter(
                TenderRecipient.id == recipient_id,
                TenderRecipient.tender_id == tender_id,
            )
            .first()
        )
        if r is None:
            raise ValueError(
                f"Recipient {recipient_id} not found on tender {tender_id}"
            )
        r.status = TenderRecipientStatus.declined
        r.decline_reason = reason
        r.decline_note = note
        r.response_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(r)
        return r

    # ── Customer portal ─────────────────────────────────────────────────────
    # Distinct from the insurer-facing access_token flow above. The broker
    # generates a customer token AFTER running the AI analysis, then shares
    # the URL with the end client. Client opens it, reviews, approves or
    # rejects.

    def generate_customer_token(
        self, tender_id: int, firm_id: int, customer_email: str
    ) -> Tender:
        """Mint a customer access token + persist email. Idempotent."""
        import secrets as _secrets

        tender = self.get(tender_id, firm_id)
        if tender is None:
            raise ValueError(f"Tender {tender_id} not found")
        if tender.customer_access_token:
            tender.customer_email = customer_email
        else:
            tender.customer_access_token = _secrets.token_urlsafe(32)
            tender.customer_email = customer_email
            tender.customer_approval_status = "pending"
        self.db.commit()
        self.db.refresh(tender)
        return tender

    def get_tender_by_customer_token(
        self, customer_access_token: str
    ) -> Optional[Tender]:
        # FIRM_ID_AUDIT: token-based public lookup; the unique unguessable
        # token IS the auth boundary, no firm_id available in this context.
        """Public lookup — used by the customer portal page."""
        return (
            self.db.query(Tender)
            .filter(Tender.customer_access_token == customer_access_token)
            .first()
        )

    def record_customer_decision(
        self, customer_access_token: str, status: str
    ) -> Tender:
        # FIRM_ID_AUDIT: token-based public mutation; the unique unguessable
        # token IS the auth boundary, no firm_id available in this context.
        """Flip approval state. status must be 'approved' or 'rejected'."""
        if status not in ("approved", "rejected"):
            raise ValueError(f"Invalid status: {status}")
        tender = self.get_tender_by_customer_token(customer_access_token)
        if tender is None:
            raise ValueError("Invalid token")
        tender.customer_approval_status = status
        tender.customer_approval_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(tender)
        return tender

    def upload_offer_by_token(
        self,
        access_token: str,
        filename: str,
        pdf_content: bytes,
    ) -> TenderOffer:
        """Insurer-facing upload via token portal. No auth required beyond the token.

        The token uniquely identifies (tender, recipient). Each upload adds a
        TenderOffer and flips the recipient status to `received`.
        """
        recipient = self.get_recipient_by_token(access_token)
        if recipient is None:
            raise ValueError("Invalid or expired access token")
        offer = self.upload_offer(
            tender_id=recipient.tender_id,
            insurer_name=recipient.insurer_name,
            filename=filename,
            pdf_bytes=pdf_content,
            recipient_id=recipient.id,
        )
        # upload_offer already flips recipient status via its recipient_id branch,
        # but we also record the response timestamp for portal-originated submits.
        recipient.response_at = datetime.now(timezone.utc)
        self.db.commit()
        return offer

    def send_invitations(self, tender_id: int, firm_id: int) -> Tender:
        """Mark tender as sent and send emails to all recipients."""
        tender = self.get(tender_id, firm_id)
        if not tender:
            raise ValueError(f"Tender {tender_id} not found")

        recipients = self.get_recipients(tender_id)
        company = self.db.query(Company).filter(Company.orgnr == tender.orgnr).first()
        company_name = company.navn if company else tender.orgnr

        for r in recipients:
            if r.insurer_email:
                success = _send_tender_email(
                    to=r.insurer_email,
                    tender=tender,
                    company_name=company_name,
                    insurer_name=r.insurer_name,
                    recipient_id=r.id,
                )
                if success:
                    r.status = TenderRecipientStatus.sent
                    r.sent_at = datetime.now(timezone.utc)

        tender.status = TenderStatus.sent
        self.db.commit()
        self.db.refresh(tender)
        return tender

    def upload_offer(
        self,
        tender_id: int,
        insurer_name: str,
        filename: str,
        pdf_bytes: bytes,
        recipient_id: Optional[int] = None,
    ) -> TenderOffer:
        """Upload a PDF offer from an insurer."""
        from api.services.coverage_service import _extract_text

        extracted_text = _extract_text(pdf_bytes)

        offer = TenderOffer(
            tender_id=tender_id,
            recipient_id=recipient_id,
            insurer_name=insurer_name,
            filename=filename,
            pdf_content=pdf_bytes,
            extracted_text=extracted_text,
            uploaded_at=datetime.now(timezone.utc),
        )
        self.db.add(offer)

        # Mark recipient as received
        if recipient_id:
            r = self.db.query(TenderRecipient).get(recipient_id)
            if r:
                r.status = TenderRecipientStatus.received
                r.response_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(offer)
        return offer

    def get_offers(self, tender_id: int) -> list:
        return (
            self.db.query(TenderOffer).filter(TenderOffer.tender_id == tender_id).all()
        )

    def extract_offer(self, offer_id: int) -> TenderOffer:
        """Run AI extraction on a single offer PDF."""
        offer = self.db.query(TenderOffer).get(offer_id)
        if not offer:
            raise ValueError(f"Offer {offer_id} not found")

        from api.services.coverage_service import _analyse_with_ai

        result = _analyse_with_ai(offer.pdf_content, offer.extracted_text)
        if result:
            offer.extracted_data = result
        self.db.commit()
        self.db.refresh(offer)
        return offer

    def analyse_offers(self, tender_id: int, firm_id: int) -> dict:
        """Compare all offers for a tender using AI."""
        offers = self.get_offers(tender_id)
        if len(offers) < 2:
            raise ValueError("Minst 2 tilbud kreves for sammenligning")

        tender = self.get(tender_id, firm_id)
        if not tender:
            raise ValueError(f"Tender {tender_id} not found")

        # First ensure all offers have extracted data
        for offer in offers:
            if not offer.extracted_data:
                self.extract_offer(offer.id)

        # Reload offers with fresh data
        offers = self.get_offers(tender_id)

        # Build comparison input
        offer_summaries = []
        for o in offers:
            summary = f"## {o.insurer_name}\n"
            if o.extracted_data:
                import json

                summary += json.dumps(o.extracted_data, ensure_ascii=False, indent=2)
            elif o.extracted_text:
                summary += o.extracted_text[:4000]
            else:
                summary += "(Ingen data tilgjengelig)"
            offer_summaries.append(summary)

        combined = "\n\n---\n\n".join(offer_summaries)

        from api.services.llm import _try_foundry_chat, _parse_json_from_llm_response

        raw = _try_foundry_chat(
            f"Her er {len(offers)} forsikringstilbud som skal sammenlignes:\n\n{combined}",
            _COMPARISON_PROMPT,
            max_tokens=4000,
        )

        result = {}
        if raw:
            parsed = _parse_json_from_llm_response(raw)
            if parsed:
                result = parsed

        tender.analysis_result = result
        tender.status = TenderStatus.analysed
        self.db.commit()

        return result


def _send_tender_email(
    to: str, tender, company_name: str, insurer_name: str, recipient_id: int = 0
) -> bool:
    """Send tender invitation email to an insurer.

    `recipient_id` is embedded (along with tender.id) as a
    `[ref: TENDER-<tid>-<rid>]` token in the subject so the inbound
    webhook can route insurer replies back to the right tender. Replies
    preserve the subject (possibly prefixed `Re:`), so the regex parser
    on the inbound side finds the ref regardless of client quoting.
    """
    try:
        from api.container import resolve
        from api.ports.driven.notification_port import NotificationPort
        from api.services.inbound_email_service import format_tender_ref

        notification: NotificationPort = resolve(NotificationPort)  # type: ignore[assignment]

        deadline_str = (
            tender.deadline.strftime("%d.%m.%Y") if tender.deadline else "Ikke satt"
        )
        products = (
            ", ".join(tender.product_types) if tender.product_types else "Diverse"
        )

        body_html = f"""
        <html><body style='font-family:Arial,sans-serif;color:#222'>
        <h2 style='color:#1a252f'>Anbudsforespørsel — {company_name}</h2>
        <p>Hei {insurer_name},</p>
        <p>Vi sender herved en anbudsforespørsel på vegne av vår klient <strong>{company_name}</strong>.</p>
        <table style='border-collapse:collapse;width:100%;font-size:14px;margin:16px 0'>
          <tr style='background:#f5f5f5'>
            <td style='padding:8px;border:1px solid #ddd'><strong>Produkter</strong></td>
            <td style='padding:8px;border:1px solid #ddd'>{products}</td>
          </tr>
          <tr>
            <td style='padding:8px;border:1px solid #ddd'><strong>Anbudsfrist</strong></td>
            <td style='padding:8px;border:1px solid #ddd'>{deadline_str}</td>
          </tr>
        </table>
        {"<p><strong>Kravspesifikasjon:</strong></p><p>" + __import__("html").escape(tender.notes) + "</p>" if tender.notes else ""}
        <p>Vennligst send deres tilbud som PDF-vedlegg til denne e-posten innen fristen.</p>
        <p style='color:#888;font-size:12px'>Sendt via Broker Accelerator — meglerai.no</p>
        </body></html>
        """
        ref_token = (
            f"  {format_tender_ref(tender.id, recipient_id)}" if recipient_id else ""
        )
        subject = f"Anbudsforespørsel: {company_name} — {products}{ref_token}"
        return notification.send_email(to, subject, body_html)
    except Exception as exc:
        logger.warning("Failed to send tender email to %s: %s", to, exc)
        return False
