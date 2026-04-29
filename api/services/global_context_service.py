"""GlobalContextService — bygger en strukturert norsk kontekst-tekst
om meglerens nåværende situasjon på tvers av hele plattformen.

Brukes av chat_tender-endepunktet for å gi AI-assistenten live tilgang
til anbud, fornyelser, pipeline, aktiviteter, porteføljer og varslinger.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from api.db import Company
from api.models.broker import BrokerSettings
from api.models.compliance import AuditLog
from api.models.crm import Policy, Activity
from api.models.pipeline import Deal, PipelineStage
from api.models.portfolio import Portfolio, PortfolioCompany
from api.models.system import Notification
from api.models.tender import Tender, TenderRecipient


class GlobalContextService:
    def __init__(self, db: Session, firm_id: int, user_email: str = ""):
        self.db = db
        self.firm_id = firm_id
        self.user_email = user_email

    def build(self) -> str:
        parts = [
            self._broker_info(),
            self._recent_companies(),
            self._tenders_summary(),
            self._renewals_summary(),
            self._pipeline_summary(),
            self._activities_summary(),
            self._portfolio_summary(),
            self._notifications_summary(),
        ]
        return "\n\n".join(p for p in parts if p)

    def _companies_by_orgnr(self, orgnrs: list[str]) -> dict[str, Company]:
        if not orgnrs:
            return {}
        rows = self.db.query(Company).filter(Company.orgnr.in_(orgnrs)).all()
        return {c.orgnr: c for c in rows}

    # ── Broker info ──────────────────────────────────────────────────────────

    def _broker_info(self) -> str:
        s = (
            self.db.query(BrokerSettings)
            .filter(BrokerSettings.firm_id == self.firm_id)
            .first()
        )
        if not s:
            return ""
        line = f"Firma: {s.firm_name}"
        if s.orgnr:
            line += f" (orgnr {s.orgnr})"
        if s.contact_name:
            line += f" — kontakt: {s.contact_name}"
        return f"=== MEGLERENS SITUASJON ===\n{line}"

    # ── Recently viewed companies ────────────────────────────────────────────

    def _recent_companies(self) -> str:
        if not self.user_email:
            return ""
        rows = (
            self.db.query(AuditLog.orgnr, AuditLog.created_at)
            .filter(
                AuditLog.actor_email == self.user_email,
                AuditLog.action == "view_company",
                AuditLog.orgnr.isnot(None),
            )
            .order_by(AuditLog.created_at.desc())
            .limit(25)
            .all()
        )
        if not rows:
            return ""

        seen: dict[str, str] = {}
        for orgnr, ts in rows:
            if orgnr not in seen:
                seen[orgnr] = ts.strftime("%d.%m %H:%M") if ts else ""
            if len(seen) >= 5:
                break

        companies = self._companies_by_orgnr(list(seen.keys()))
        lines = ["--- NYLIG BESØKTE SELSKAPER ---"]
        for orgnr, ts in seen.items():
            c = companies.get(orgnr)
            navn = c.navn if c else orgnr
            risk = f" | Risiko: {c.risk_score}/20" if c and c.risk_score else ""
            lines.append(f"• {navn} (orgnr {orgnr}){risk} — sist besøkt {ts}")
        return "\n".join(lines)

    # ── Tenders ──────────────────────────────────────────────────────────────

    def _tenders_summary(self) -> str:
        tenders = (
            self.db.query(Tender)
            .filter(Tender.firm_id == self.firm_id)
            .order_by(Tender.created_at.desc())
            .limit(15)
            .all()
        )
        if not tenders:
            return ""

        # Batch recipient counts in one GROUP BY query
        tender_ids = [t.id for t in tenders]
        counts = dict(
            self.db.query(TenderRecipient.tender_id, func.count(TenderRecipient.id))
            .filter(TenderRecipient.tender_id.in_(tender_ids))
            .group_by(TenderRecipient.tender_id)
            .all()
        )

        today = date.today()
        status_map = {"draft": "Utkast", "sent": "Sendt", "closed": "Lukket", "analysed": "Analysert"}
        lines = [f"--- ANBUD ({len(tenders)} totalt) ---"]
        for t in tenders:
            status_val = t.status.value if hasattr(t.status, "value") else str(t.status)
            status_no = status_map.get(status_val, status_val)
            deadline_str = ""
            if t.deadline:
                d = t.deadline
                days = (d - today).days
                deadline_str = f" | Frist: {d} ({'UTLØPT' if days < 0 else f'{days} dager'})"
            products = ", ".join(t.product_types) if t.product_types else "–"
            rec_count = counts.get(t.id, 0)
            lines.append(f"• {t.title} | {status_no} | {products}{deadline_str} | {rec_count} mottakere")
        return "\n".join(lines)

    # ── Renewals ─────────────────────────────────────────────────────────────

    def _renewals_summary(self) -> str:
        today = date.today()
        cutoff = today + timedelta(days=60)
        policies = (
            self.db.query(Policy)
            .filter(
                Policy.firm_id == self.firm_id,
                Policy.renewal_date >= today,
                Policy.renewal_date <= cutoff,
            )
            .order_by(Policy.renewal_date)
            .limit(10)
            .all()
        )
        if not policies:
            return ""

        companies = self._companies_by_orgnr([p.orgnr for p in policies])
        lines = [f"--- FORNYELSER (neste 60 dager, {len(policies)} stk) ---"]
        for p in policies:
            c = companies.get(p.orgnr)
            client = c.navn if c else p.orgnr
            days = (p.renewal_date - today).days
            premium = f"{int(p.annual_premium_nok):,} NOK".replace(",", " ") if p.annual_premium_nok else "–"
            lines.append(f"• {client} — {p.insurer} | {p.renewal_date} ({days} dager) | {premium}")
        return "\n".join(lines)

    # ── Pipeline ─────────────────────────────────────────────────────────────

    def _pipeline_summary(self) -> str:
        stages = (
            self.db.query(PipelineStage)
            .filter(PipelineStage.firm_id == self.firm_id)
            .order_by(PipelineStage.order_index)
            .all()
        )
        if not stages:
            return ""

        deals = (
            self.db.query(Deal)
            .filter(Deal.firm_id == self.firm_id)
            .limit(200)
            .all()
        )
        if not deals:
            return ""

        stage_map = {s.id: s for s in stages}
        by_stage: dict[str, list[Deal]] = {}
        for d in deals:
            stage = stage_map.get(d.stage_id)
            name = stage.name if stage else "Ukjent"
            by_stage.setdefault(name, []).append(d)

        total_premium = sum(d.expected_premium_nok for d in deals if d.expected_premium_nok)
        parts = [f"{s.name}: {len(by_stage.get(s.name, []))}" for s in stages if by_stage.get(s.name)]
        total_str = f"{int(total_premium):,}".replace(",", " ") if total_premium else "0"
        return f"--- PIPELINE ---\n{' | '.join(parts)} | Total: {total_str} NOK"

    # ── Activities ───────────────────────────────────────────────────────────

    def _activities_summary(self) -> str:
        activities = (
            self.db.query(Activity)
            .filter(
                Activity.firm_id == self.firm_id,
                Activity.completed == False,  # noqa: E712
            )
            .order_by(Activity.due_date.asc().nullslast())
            .limit(8)
            .all()
        )
        if not activities:
            return ""

        orgnrs = [a.orgnr for a in activities if a.orgnr]
        companies = self._companies_by_orgnr(orgnrs)
        today = date.today()
        lines = [f"--- ÅPNE AKTIVITETER ({len(activities)} stk) ---"]
        for a in activities:
            c = companies.get(a.orgnr) if a.orgnr else None
            client = c.navn if c else (a.orgnr or "–")
            atype = a.activity_type.value if hasattr(a.activity_type, "value") else str(a.activity_type)
            due = ""
            if a.due_date:
                days = (a.due_date - today).days
                if days < 0:
                    due = f" | Forfalt ({abs(days)} dager siden)"
                elif days == 0:
                    due = " | I dag"
                else:
                    due = f" | Om {days} dager ({a.due_date})"
            lines.append(f"• [{atype}] {a.subject} — {client}{due}")
        return "\n".join(lines)

    # ── Portfolios ───────────────────────────────────────────────────────────

    def _portfolio_summary(self) -> str:
        portfolios = (
            self.db.query(Portfolio)
            .filter(Portfolio.firm_id == self.firm_id)
            .limit(10)
            .all()
        )
        if not portfolios:
            return ""

        # Batch count per portfolio in one GROUP BY query
        portfolio_ids = [p.id for p in portfolios]
        counts = dict(
            self.db.query(PortfolioCompany.portfolio_id, func.count(PortfolioCompany.orgnr))
            .filter(PortfolioCompany.portfolio_id.in_(portfolio_ids))
            .group_by(PortfolioCompany.portfolio_id)
            .all()
        )
        lines = ["--- PORTEFØLJER ---"]
        for p in portfolios:
            lines.append(f"• {p.name} ({counts.get(p.id, 0)} selskaper)")
        return "\n".join(lines)

    # ── Notifications ────────────────────────────────────────────────────────

    def _notifications_summary(self) -> str:
        notes = (
            self.db.query(Notification)
            .filter(
                Notification.firm_id == self.firm_id,
                Notification.read == False,  # noqa: E712
            )
            .order_by(Notification.created_at.desc())
            .limit(5)
            .all()
        )
        if not notes:
            return ""
        lines = [f"--- ULESTE VARSLINGER ({len(notes)} stk) ---"]
        for n in notes:
            lines.append(f"• {n.title}: {n.message}")
        return "\n".join(lines)
