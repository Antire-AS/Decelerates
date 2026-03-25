"""Admin operations — reset, demo seeding, CRM seed.

All DB writes live here; routers stay write-free.
"""
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from api.db import (
    Activity, ActivityType, Claim, ClaimStatus,
    Policy, PolicyStatus, Portfolio, PortfolioCompany,
)

_log = logging.getLogger(__name__)

_DEMO_ORGNRS = [
    "984851006",  # DNB Bank ASA
    "995568217",  # Gjensidige Forsikring ASA
    "923609016",  # Equinor ASA
    "979981344",  # Søderberg & Partners Norge AS
    "943753709",  # Kongsberg Gruppen ASA
    "982463718",  # Telenor ASA
    "986228608",  # Yara International ASA
    "989795848",  # Aker BP ASA
]

# (orgnr, insurer, product_type, policy_number, premium, coverage, days_to_renewal, renewal_stage)
_DEMO_POLICIES_DATA = [
    ("984851006", "If Skadeforsikring",   "Ansvarsforsikring",       "POL-DNB-001", 1_200_000,  50_000_000, 22, "ready_to_quote"),
    ("984851006", "Storebrand Forsikring","Styreansvarsforsikring",  "POL-DNB-002",   350_000,  10_000_000, 75, "not_started"),
    ("923609016", "Tryg Forsikring",      "Transportforsikring",     "POL-EQN-001", 2_800_000, 100_000_000,  8, "quoted"),
    ("923609016", "Codan Forsikring",     "Tingsskadeforsikring",    "POL-EQN-002", 5_500_000, 200_000_000, 45, "not_started"),
    ("995568217", "Fremtind Forsikring",  "Yrkesskadeforsikring",    "POL-GJE-001",   890_000,  20_000_000, 18, "ready_to_quote"),
    ("943753709", "If Skadeforsikring",   "Eiendomsforsikring",      "POL-KON-001", 1_800_000,  80_000_000, 30, "quoted"),
    ("982463718", "Tryg Forsikring",      "Cyberforsikring",         "POL-TEL-001", 2_100_000,  30_000_000, 62, "not_started"),
    ("986228608", "Gjensidige Forsikring","Ansvarsforsikring",       "POL-YAR-001", 3_400_000, 120_000_000, 88, "not_started"),
    ("989795848", "Codan Forsikring",     "Driftsavbruddsforsikring","POL-AKB-001", 4_200_000, 150_000_000, 15, "accepted"),
    ("979981344", "Storebrand Forsikring","Eiendomsforsikring",      "POL-SOP-001",   450_000,  25_000_000, 55, "declined"),
]

# (policy_number, orgnr, claim_number, status, description, amount)
_DEMO_CLAIMS_DATA = [
    ("POL-DNB-001","984851006","SKD-2025-001",ClaimStatus.open,   "Skade på kontorbygg — vanninntrenging",  250_000),
    ("POL-EQN-001","923609016","SKD-2025-002",ClaimStatus.open,   "Lasteskade under transport",           1_800_000),
    ("POL-KON-001","943753709","SKD-2024-018",ClaimStatus.settled,"Sprinkleranlegg utløst — vannskade",     380_000),
    ("POL-AKB-001","989795848","SKD-2025-003",ClaimStatus.open,   "Nedetid produksjonsanlegg",            2_500_000),
]

# (orgnr, activity_type, subject, days_delta, completed)
_DEMO_ACTIVITIES_DATA = [
    ("984851006", ActivityType.call,    "Fornyelsessamtale — Ansvarsforsikring",      3,   False),
    ("923609016", ActivityType.meeting, "Gjennomgang forsikringsportefølje",           7,   False),
    ("995568217", ActivityType.email,   "Sendt tilbud Yrkesskadeforsikring",          -5,   True),
    ("989795848", ActivityType.task,    "Følge opp skadekrav SKD-2025-003",            2,   False),
    ("943753709", ActivityType.meeting, "Fornyelsesmøte Eiendomsforsikring",          -10,  True),
    ("982463718", ActivityType.call,    "Avklare dekningsomfang Cyberforsikring",      14,  False),
    ("986228608", ActivityType.email,   "Kvartalsstatus til kunde",                    -3,  True),
]


class AdminService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def reset(self) -> dict:
        """Delete all company-owned data so it will be re-fetched fresh."""
        from sqlalchemy import text
        deleted = {}
        for table in ["portfolio_companies", "portfolios", "company_history",
                      "company_pdf_sources", "company_notes", "companies"]:
            result = self.db.execute(text(f"DELETE FROM {table}"))  # noqa: S608
            deleted[table] = result.rowcount
        result = self.db.execute(text("DELETE FROM company_chunks WHERE orgnr != 'knowledge'"))
        deleted["company_chunks"] = result.rowcount
        self.db.commit()
        return {"reset": True, "deleted_rows": deleted}

    def _get_or_create_portfolio(self, name: str, description: str) -> Portfolio:
        portfolio = self.db.query(Portfolio).filter(Portfolio.name == name).first()
        if not portfolio:
            portfolio = Portfolio(name=name, description=description,
                                  created_at=datetime.now(timezone.utc).isoformat())
            self.db.add(portfolio)
            self.db.commit()
            self.db.refresh(portfolio)
        return portfolio

    def _add_demo_companies(self, portfolio_id: int) -> tuple[int, int]:
        from api.services.company import fetch_org_profile
        existing = {
            pc.orgnr for pc in
            self.db.query(PortfolioCompany)
            .filter(PortfolioCompany.portfolio_id == portfolio_id).all()
        }
        fetched, skipped = 0, 0
        for orgnr in _DEMO_ORGNRS:
            if orgnr not in existing:
                self.db.add(PortfolioCompany(portfolio_id=portfolio_id, orgnr=orgnr,
                                             added_at=datetime.now(timezone.utc).isoformat()))
            try:
                fetch_org_profile(orgnr, self.db)
                fetched += 1
            except Exception as exc:
                _log.warning("Demo seed: failed for %s — %s", orgnr, exc)
                skipped += 1
        self.db.commit()
        return fetched, skipped

    def seed_demo(self) -> dict:
        """Create demo portfolio with 8 major Norwegian companies, trigger PDF extraction."""
        from api.services.portfolio import PortfolioService
        portfolio = self._get_or_create_portfolio(
            "Demo Portefølje", "Norges største selskaper — klar for demo"
        )
        fetched, skipped = self._add_demo_companies(portfolio.id)
        PortfolioService(self.db).enrich_pdfs_background(portfolio.id)
        return {
            "portfolio_id": portfolio.id, "portfolio_name": portfolio.name,
            "companies": len(_DEMO_ORGNRS), "fetched": fetched, "skipped": skipped,
            "pdf_extraction": "started in background",
        }

    def _add_top100_companies(self, portfolio_id: int) -> tuple[int, int, int]:
        from api.constants import TOP_100_NO_NAMES
        from api.services.company import fetch_org_profile
        from api.services.external_apis import fetch_enhetsregisteret
        existing = {
            pc.orgnr for pc in
            self.db.query(PortfolioCompany)
            .filter(PortfolioCompany.portfolio_id == portfolio_id).all()
        }
        lookup_added, lookup_failed = 0, 0
        for name in TOP_100_NO_NAMES:
            try:
                results = fetch_enhetsregisteret(name, size=1)
                if not results:
                    lookup_failed += 1
                    continue
                orgnr = results[0]["orgnr"]
                if orgnr not in existing:
                    self.db.add(PortfolioCompany(portfolio_id=portfolio_id, orgnr=orgnr,
                                                 added_at=datetime.now(timezone.utc).isoformat()))
                    existing.add(orgnr)
                    lookup_added += 1
                try:
                    fetch_org_profile(orgnr, self.db)
                except Exception as exc:
                    _log.warning("Top100 profile fetch failed for %s: %s", orgnr, exc)
            except Exception as exc:
                _log.warning("Top100 BRREG lookup failed for '%s': %s", name, exc)
                lookup_failed += 1
        self.db.commit()
        return lookup_added, lookup_failed, len(existing)

    def seed_norway_top100(self) -> dict:
        """Create Norges Topp 100 portfolio, fetch BRREG profiles, queue PDF extraction."""
        from api.constants import TOP_100_NO_NAMES
        from api.services.portfolio import PortfolioService
        portfolio = self._get_or_create_portfolio(
            "Norges Topp 100", "Norges 100 største selskaper — automatisk innhentet"
        )
        lookup_added, lookup_failed, total_in_portfolio = self._add_top100_companies(portfolio.id)
        PortfolioService(self.db).enrich_pdfs_background(portfolio.id)
        return {
            "portfolio_id": portfolio.id, "portfolio_name": portfolio.name,
            "total_names": len(TOP_100_NO_NAMES), "added_to_portfolio": lookup_added,
            "already_present": total_in_portfolio - lookup_added, "lookup_failed": lookup_failed,
            "pdf_agent_queued": total_in_portfolio,
            "message": "PDF-innhenting via nett kjører i bakgrunnen (3 samtidige). Sjekk portefølje for fremgang.",
        }

    def _seed_policies(self, firm_id: int, now: datetime) -> tuple[int, int, dict]:
        today = date.today()
        created, skipped, policy_map = 0, 0, {}
        for orgnr, insurer, product_type, pol_nr, premium, coverage, days_to_renewal, stage in _DEMO_POLICIES_DATA:
            exists = self.db.query(Policy).filter(
                Policy.policy_number == pol_nr, Policy.firm_id == firm_id
            ).first()
            if exists:
                policy_map[pol_nr] = exists
                skipped += 1
                continue
            from api.db import RenewalStage
            renewal_stage = RenewalStage[stage] if stage else RenewalStage.not_started
            p = Policy(
                orgnr=orgnr, firm_id=firm_id, policy_number=pol_nr,
                insurer=insurer, product_type=product_type,
                annual_premium_nok=float(premium), coverage_amount_nok=float(coverage),
                start_date=today - timedelta(days=365 - days_to_renewal),
                renewal_date=today + timedelta(days=days_to_renewal),
                status=PolicyStatus.active, renewal_stage=renewal_stage,
                created_at=now, updated_at=now,
            )
            self.db.add(p)
            self.db.flush()
            policy_map[pol_nr] = p
            created += 1
        self.db.commit()
        return created, skipped, policy_map

    def _seed_claims(self, policy_map: dict, firm_id: int, now: datetime) -> int:
        today = date.today()
        created = 0
        for pol_nr, orgnr, claim_nr, status, desc, amount in _DEMO_CLAIMS_DATA:
            pol = policy_map.get(pol_nr)
            if not pol:
                continue
            if self.db.query(Claim).filter(Claim.claim_number == claim_nr, Claim.firm_id == firm_id).first():
                continue
            self.db.add(Claim(
                policy_id=pol.id, orgnr=orgnr, firm_id=firm_id,
                claim_number=claim_nr, incident_date=today - timedelta(days=30),
                reported_date=today - timedelta(days=25), status=status,
                description=desc, estimated_amount_nok=float(amount),
                created_at=now, updated_at=now,
            ))
            created += 1
        self.db.commit()
        return created

    def _seed_activities(self, firm_id: int, now: datetime) -> int:
        today = date.today()
        created = 0
        for orgnr, atype, subject, days_delta, completed in _DEMO_ACTIVITIES_DATA:
            if self.db.query(Activity).filter(
                Activity.orgnr == orgnr, Activity.subject == subject, Activity.firm_id == firm_id
            ).first():
                continue
            self.db.add(Activity(
                orgnr=orgnr, firm_id=firm_id, activity_type=atype,
                subject=subject, due_date=today + timedelta(days=days_delta),
                completed=completed, created_by="demo@broker.no",
                created_at=now, updated_at=now,
            ))
            created += 1
        self.db.commit()
        return created

    def seed_crm_demo(self) -> dict:
        """Seed realistic demo policies, claims, and activities for the demo companies."""
        import traceback
        try:
            from api.db import BrokerFirm
            if not self.db.query(BrokerFirm).filter(BrokerFirm.id == 1).first():
                self.db.add(BrokerFirm(id=1, name="Default Firm", created_at=datetime.now(timezone.utc)))
                self.db.flush()
            now = datetime.now(timezone.utc)
            policies_created, policies_skipped, policy_map = self._seed_policies(1, now)
            claims_created = self._seed_claims(policy_map, 1, now)
            activities_created = self._seed_activities(1, now)
            return {
                "policies_created": policies_created, "policies_skipped": policies_skipped,
                "claims_created": claims_created, "activities_created": activities_created,
            }
        except Exception as exc:
            self.db.rollback()
            return {"error": str(exc), "trace": traceback.format_exc()}
