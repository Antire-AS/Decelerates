"""IDD (Insurance Distribution Directive) service — behovsanalyse CRUD."""
# PEP 563 deferred annotation evaluation. Required because this class has a
# `list` method that shadows the builtin `list` mid-class-body, which would
# otherwise break the `-> list[IddBehovsanalyse]` annotations on later methods
# (defined after `def list(self, ...)`) at class-definition time on Python <3.14.
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from api.db import IddBehovsanalyse
from api.domain.exceptions import NotFoundError


class IddService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, orgnr: str, firm_id: int, created_by_email: str, data: dict) -> IddBehovsanalyse:
        row = IddBehovsanalyse(
            orgnr=orgnr,
            firm_id=firm_id,
            created_by_email=created_by_email,
            created_at=datetime.now(timezone.utc),
            **data,
        )
        self.db.add(row)
        try:
            self.db.commit()
            self.db.refresh(row)
        except Exception:
            self.db.rollback()
            raise
        return row

    def list(self, orgnr: str, firm_id: int) -> list[IddBehovsanalyse]:
        return (
            self.db.query(IddBehovsanalyse)
            .filter(IddBehovsanalyse.orgnr == orgnr, IddBehovsanalyse.firm_id == firm_id)
            .order_by(IddBehovsanalyse.created_at.desc())
            .all()
        )

    def list_all_for_firm(self, firm_id: int, limit: int = 100) -> list[IddBehovsanalyse]:
        """All IDD analyses for a firm across every company. Used by /idd list view."""
        return (
            self.db.query(IddBehovsanalyse)
            .filter(IddBehovsanalyse.firm_id == firm_id)
            .order_by(IddBehovsanalyse.created_at.desc())
            .limit(limit)
            .all()
        )

    def get(self, orgnr: str, firm_id: int, idd_id: int) -> IddBehovsanalyse:
        return self._get_or_raise(orgnr, firm_id, idd_id)

    def delete(self, orgnr: str, firm_id: int, idd_id: int) -> None:
        row = self._get_or_raise(orgnr, firm_id, idd_id)
        self.db.delete(row)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def generate_suitability_reasoning(self, orgnr: str, firm_id: int, idd_id: int) -> str:
        """Use LLM to explain why recommended products are suitable for this client."""
        from api.services.llm import _llm_answer_raw
        row = self._get_or_raise(orgnr, firm_id, idd_id)
        products = ", ".join(row.recommended_products or []) or "ikke spesifisert"
        prompt = (
            f"Du er en forsikringsrådgiver. Forklar på norsk (2-3 setninger) "
            f"hvorfor følgende forsikringsprodukter er egnet for denne kunden:\n"
            f"Produkter: {products}\n"
            f"Risikoappetitt: {row.risk_appetite or 'middels'}\n"
            f"Har ansatte: {'ja' if row.has_employees else 'nei'}\n"
            f"Har eiendom: {'ja' if row.property_owned else 'nei'}\n"
            f"Cyber-risiko: {'ja' if row.has_cyber_risk else 'nei'}\n"
            f"Årsomsetning: {int(row.annual_revenue_nok or 0):,} NOK\n"
            f"Spesielle krav: {row.special_requirements or 'ingen'}\n\n"
            "Svar med kun egnethetsvurderingen, ingen introduksjon."
        )
        reasoning = _llm_answer_raw(prompt) or ""
        row.suitability_basis = reasoning
        try:
            self.db.commit()
            self.db.refresh(row)
        except Exception:
            self.db.rollback()
            raise
        return reasoning

    def _get_or_raise(self, orgnr: str, firm_id: int, idd_id: int) -> IddBehovsanalyse:
        row = (
            self.db.query(IddBehovsanalyse)
            .filter(
                IddBehovsanalyse.id == idd_id,
                IddBehovsanalyse.orgnr == orgnr,
                IddBehovsanalyse.firm_id == firm_id,
            )
            .first()
        )
        if not row:
            raise NotFoundError(f"Behovsanalyse {idd_id} not found")
        return row
