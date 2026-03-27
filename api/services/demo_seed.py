"""Full demo seed — fictional Norwegian companies with 5-year financial history and renewal policies.

These companies are completely fictional (orgnr 999100101–108, not in BRREG).
Financial figures are internally consistent but perturbed ±10% per year to look realistic.
Renewal dates are spread across the next 30/60/90 days for a realistic pipeline demo.
"""
import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from api.db import (
    Company, CompanyHistory, Policy, PolicyStatus,
    Claim, ClaimStatus, Activity, ActivityType, BrokerFirm,
)

random.seed(42)  # Reproducible but looks realistic

# ── Base company data ─────────────────────────────────────────────────────────

_COMPANIES = [
    {
        "orgnr": "999100101", "navn": "Bergstrand Eiendom AS",
        "risk_score": 32, "naeringskode1": "68.209",
        "naeringskode1_beskrivelse": "Utleie av egne boliger og næringslokaler",
        "kommune": "Oslo", "antall_ansatte": 8,
        "base_revenue": 42_000_000, "base_result": 7_500_000,
        "base_assets": 180_000_000, "base_equity": 95_000_000,
        "insurance_type": "Eiendom og ansvarsforsikring",
        "insurer": "Gjensidige Forsikring",
        "renewal_offset_days": 22,
    },
    {
        "orgnr": "999100102", "navn": "Nordvind Teknologi AS",
        "risk_score": 45, "naeringskode1": "62.010",
        "naeringskode1_beskrivelse": "Programmeringsvirksomhet",
        "kommune": "Bergen", "antall_ansatte": 35,
        "base_revenue": 28_000_000, "base_result": 3_200_000,
        "base_assets": 22_000_000, "base_equity": 14_000_000,
        "insurance_type": "Cyberforsikring og ansvar",
        "insurer": "If Skadeforsikring",
        "renewal_offset_days": 48,
    },
    {
        "orgnr": "999100103", "navn": "Fjordbygg Entreprenør AS",
        "risk_score": 72, "naeringskode1": "41.200",
        "naeringskode1_beskrivelse": "Oppføring av bygninger",
        "kommune": "Stavanger", "antall_ansatte": 52,
        "base_revenue": 95_000_000, "base_result": -2_800_000,
        "base_assets": 65_000_000, "base_equity": 12_000_000,
        "insurance_type": "Entreprise og ansvarsforsikring",
        "insurer": "Tryg Forsikring",
        "renewal_offset_days": 15,
    },
    {
        "orgnr": "999100104", "navn": "Solhavn Transport AS",
        "risk_score": 58, "naeringskode1": "49.410",
        "naeringskode1_beskrivelse": "Godstransport på vei",
        "kommune": "Trondheim", "antall_ansatte": 28,
        "base_revenue": 67_000_000, "base_result": 1_100_000,
        "base_assets": 55_000_000, "base_equity": 18_000_000,
        "insurance_type": "Motorvognforsikring og gods",
        "insurer": "Fremtind Forsikring",
        "renewal_offset_days": 62,
    },
    {
        "orgnr": "999100105", "navn": "Dalheimfisk AS",
        "risk_score": 40, "naeringskode1": "03.111",
        "naeringskode1_beskrivelse": "Havfiske",
        "kommune": "Ålesund", "antall_ansatte": 18,
        "base_revenue": 38_000_000, "base_result": 4_600_000,
        "base_assets": 72_000_000, "base_equity": 31_000_000,
        "insurance_type": "Fiskefartøyforsikring",
        "insurer": "Bluewater Insurance",
        "renewal_offset_days": 35,
    },
    {
        "orgnr": "999100106", "navn": "Aker Konsulentgruppen AS",
        "risk_score": 28, "naeringskode1": "70.220",
        "naeringskode1_beskrivelse": "Bedriftsrådgivning",
        "kommune": "Oslo", "antall_ansatte": 22,
        "base_revenue": 32_000_000, "base_result": 5_400_000,
        "base_assets": 28_000_000, "base_equity": 20_000_000,
        "insurance_type": "Profesjonsansvar og D&O",
        "insurer": "AIG Europe",
        "renewal_offset_days": 78,
    },
    {
        "orgnr": "999100107", "navn": "Grønbøl Handel AS",
        "risk_score": 62, "naeringskode1": "47.110",
        "naeringskode1_beskrivelse": "Butikkhandel med bredt vareutvalg",
        "kommune": "Kristiansand", "antall_ansatte": 45,
        "base_revenue": 118_000_000, "base_result": 900_000,
        "base_assets": 48_000_000, "base_equity": 11_000_000,
        "insurance_type": "Innbo, driftsavbrudd og ansvar",
        "insurer": "Codan Forsikring",
        "renewal_offset_days": 91,
    },
    {
        "orgnr": "999100108", "navn": "Vestfjord Shipping AS",
        "risk_score": 50, "naeringskode1": "50.200",
        "naeringskode1_beskrivelse": "Sjøfart langs kysten",
        "kommune": "Haugesund", "antall_ansatte": 31,
        "base_revenue": 84_000_000, "base_result": 3_200_000,
        "base_assets": 145_000_000, "base_equity": 52_000_000,
        "insurance_type": "Kasko og P&I",
        "insurer": "Skuld",
        "renewal_offset_days": 54,
    },
]

_CURRENT_YEAR = date.today().year
_HISTORY_YEARS = [_CURRENT_YEAR - i for i in range(1, 6)]  # 5 years back


def _perturb(value: float, pct: float = 0.10) -> float:
    """Apply ±pct% random noise to keep numbers looking authentic."""
    return round(value * random.uniform(1 - pct, 1 + pct))


def _build_history_rows(c: dict) -> list[dict]:
    """Generate 5 years of financial history with realistic growth and perturbation."""
    rows = []
    rev = float(c["base_revenue"])
    net = float(c["base_result"])
    assets = float(c["base_assets"])
    equity = float(c["base_equity"])

    for i, year in enumerate(sorted(_HISTORY_YEARS)):
        # Apply compound growth / decay each year
        growth = random.uniform(0.96, 1.08)
        rev = _perturb(rev * growth)
        net = _perturb(net * growth, pct=0.20)  # results are more volatile
        assets = _perturb(assets * random.uniform(0.98, 1.05))
        equity = _perturb(equity + net * 0.7)   # retain ~70% of net result

        eq_ratio = round(equity / assets, 3) if assets else 0.0
        rows.append({
            "year": year,
            "revenue": rev,
            "net_result": net,
            "equity": equity,
            "total_assets": assets,
            "equity_ratio": eq_ratio,
        })
    return rows


def seed_full_demo(db: Session) -> dict:
    """Insert fictional demo companies + history + policies. Idempotent (skips existing orgnrs)."""
    today = date.today()
    now = datetime.now(timezone.utc)

    # Resolve default firm (first in DB) — required for all CRM records
    firm = db.query(BrokerFirm).order_by(BrokerFirm.id).first()
    if not firm:
        firm = BrokerFirm(name="Demo Meglerfirma", created_at=now)
        db.add(firm)
        db.flush()
    firm_id = firm.id

    companies_created = 0
    history_created = 0
    policies_created = 0
    claims_created = 0
    activities_created = 0

    for c in _COMPANIES:
        orgnr = c["orgnr"]

        # ── Company ──────────────────────────────────────────────────────────

        existing = db.query(Company).filter(Company.orgnr == orgnr).first()
        if not existing:
            latest_rev = c["base_revenue"]
            latest_eq = c["base_equity"]
            latest_assets = c["base_assets"]
            eq_ratio = round(latest_eq / latest_assets, 3) if latest_assets else 0.0
            db.add(Company(
                orgnr=orgnr,
                navn=c["navn"],
                organisasjonsform_kode="AS",
                kommune=c["kommune"],
                land="Norge",
                naeringskode1=c["naeringskode1"],
                naeringskode1_beskrivelse=c["naeringskode1_beskrivelse"],
                regnskapsår=_CURRENT_YEAR - 1,
                sum_driftsinntekter=float(latest_rev),
                sum_egenkapital=float(latest_eq),
                sum_eiendeler=float(latest_assets),
                equity_ratio=eq_ratio,
                risk_score=c["risk_score"],
                antall_ansatte=c["antall_ansatte"],
            ))
            companies_created += 1

        # ── Financial history ─────────────────────────────────────────────────

        for row in _build_history_rows(c):
            exists = (
                db.query(CompanyHistory)
                .filter(CompanyHistory.orgnr == orgnr, CompanyHistory.year == row["year"])
                .first()
            )
            if not exists:
                db.add(CompanyHistory(
                    orgnr=orgnr,
                    year=row["year"],
                    source="demo",
                    revenue=row["revenue"],
                    net_result=row["net_result"],
                    equity=row["equity"],
                    total_assets=row["total_assets"],
                    equity_ratio=row["equity_ratio"],
                    currency="NOK",
                ))
                history_created += 1

        # ── Policy (primary) ──────────────────────────────────────────────────

        existing_policy = (
            db.query(Policy)
            .filter(Policy.orgnr == orgnr, Policy.product_type == c["insurance_type"])
            .first()
        )
        policy_id = None
        if not existing_policy:
            renewal_date = today + timedelta(days=c["renewal_offset_days"])
            start_date = renewal_date.replace(year=renewal_date.year - 1)
            premium = round(c["base_revenue"] * random.uniform(0.015, 0.025) / 1000) * 1000

            policy = Policy(
                orgnr=orgnr,
                firm_id=firm_id,
                product_type=c["insurance_type"],
                insurer=c["insurer"],
                policy_number=f"POL-{orgnr[-4:]}-{random.randint(1000, 9999)}",
                annual_premium_nok=float(premium),
                coverage_amount_nok=float(c["base_assets"] * random.uniform(1.0, 2.5)),
                start_date=start_date,
                renewal_date=renewal_date,
                status=PolicyStatus.active,
                notes="Demo-polise",
                created_at=now,
                updated_at=now,
            )
            db.add(policy)
            db.flush()
            policy_id = policy.id
            policies_created += 1
        else:
            policy_id = existing_policy.id

        # ── Claim (for high-risk companies) ──────────────────────────────────

        if c["risk_score"] >= 60:
            existing_claim = db.query(Claim).filter(Claim.orgnr == orgnr).first()
            if not existing_claim:
                incident_date = today - timedelta(days=random.randint(30, 120))
                db.add(Claim(
                    orgnr=orgnr,
                    firm_id=firm_id,
                    policy_id=policy_id,
                    status=ClaimStatus.open,
                    incident_date=incident_date,
                    reported_date=incident_date + timedelta(days=random.randint(1, 5)),
                    estimated_amount_nok=float(random.randint(50_000, 500_000)),
                    description="Demo-skademelding",
                    notes="Under behandling",
                    created_at=now,
                    updated_at=now,
                ))
                claims_created += 1

        # ── Activity ──────────────────────────────────────────────────────────

        existing_activity = db.query(Activity).filter(Activity.orgnr == orgnr).first()
        if not existing_activity:
            due = today + timedelta(days=random.randint(3, 21))
            db.add(Activity(
                orgnr=orgnr,
                firm_id=firm_id,
                created_by_email="demo@broker.no",
                activity_type=ActivityType.call,
                subject=f"Fornyelsessamtale — {c['navn']}",
                body=f"Ta kontakt med kunden angående fornyelse {c['renewal_offset_days']} dager frem i tid.",
                due_date=due,
                completed=False,
                created_at=now,
            ))
            activities_created += 1

    db.commit()
    return {
        "companies_created": companies_created,
        "history_rows_created": history_created,
        "policies_created": policies_created,
        "claims_created": claims_created,
        "activities_created": activities_created,
        "message": (
            f"Demo-data seeded: {companies_created} selskaper, "
            f"{history_created} historikkrader, {policies_created} poliser"
        ),
    }
