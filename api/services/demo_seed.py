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
    ContactPerson, IddBehovsanalyse, Insurer, Submission, SubmissionStatus,
    Recommendation,
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

# ── Demo insurer data ─────────────────────────────────────────────────────────

_DEMO_INSURERS = [
    {"name": "If Skadeforsikring",     "org_number": "986529551", "contact_name": "Anders Holm",     "contact_email": "anders.holm@if.no",     "appetite": ["Eiendom", "Ansvar", "Cyber", "Motor"]},
    {"name": "Gjensidige Forsikring",  "org_number": "995568217", "contact_name": "Lise Bakke",      "contact_email": "lise.bakke@gjensidige.no","appetite": ["Eiendom", "Ansvar", "Yrkesskade", "Transport"]},
    {"name": "Tryg Forsikring",        "org_number": "991567078", "contact_name": "Mats Eriksen",    "contact_email": "mats.eriksen@tryg.no",   "appetite": ["Eiendom", "Ansvar", "Marine", "Entreprise"]},
    {"name": "Fremtind Forsikring",    "org_number": "921698408", "contact_name": "Nina Strand",     "contact_email": "nina.strand@fremtind.no","appetite": ["Motor", "Eiendom", "Ansvar", "Yrkesskade"]},
    {"name": "Storebrand Forsikring",  "org_number": "930553506", "contact_name": "Erik Lie",        "contact_email": "erik.lie@storebrand.no", "appetite": ["Styreansvar", "Eiendom", "Ansvar", "Cyber"]},
]

# (orgnr, name, title, email, is_primary)
_DEMO_CONTACTS = [
    ("999100101", "Kari Bergstrand",    "Daglig leder",       "kari@bergstrand-eiendom.no",   True),
    ("999100101", "Per Olsen",          "Økonomisjef",        "per.olsen@bergstrand-eiendom.no", False),
    ("999100102", "Jonas Haug",         "CEO",                "jonas@nordvind.no",            True),
    ("999100102", "Silje Nygård",       "Risk Manager",       "silje@nordvind.no",            False),
    ("999100103", "Bjørn Fjord",        "Daglig leder",       "bjorn@fjordbygg.no",           True),
    ("999100104", "Trond Solhavn",      "Eier",               "trond@solhavn-transport.no",   True),
    ("999100105", "Mette Dalheim",      "Administrasjonsleder","mette@dalheimfisk.no",         True),
    ("999100106", "Lars Aker",          "Managing Partner",   "lars@aker-konsulent.no",       True),
    ("999100107", "Anita Grønbøl",      "Butikksjef",         "anita@gronbol.no",             True),
    ("999100108", "Rolf Vestfjord",     "Reder",              "rolf@vestfjord-shipping.no",   True),
]


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


def _seed_insurers(db: Session, firm_id: int, now: datetime) -> dict[str, int]:
    """Seed demo insurers and return name → id map."""
    insurer_map: dict[str, int] = {}
    for ins in _DEMO_INSURERS:
        existing = db.query(Insurer).filter(
            Insurer.firm_id == firm_id, Insurer.name == ins["name"]
        ).first()
        if existing:
            insurer_map[ins["name"]] = existing.id
        else:
            row = Insurer(
                firm_id=firm_id, name=ins["name"], org_number=ins["org_number"],
                contact_name=ins["contact_name"], contact_email=ins["contact_email"],
                appetite=ins["appetite"], created_at=now,
            )
            db.add(row)
            db.flush()
            insurer_map[ins["name"]] = row.id
    return insurer_map


def _seed_contacts(db: Session, now: datetime) -> int:
    """Seed demo contact persons. Returns created count."""
    created = 0
    for orgnr, name, title, email, is_primary in _DEMO_CONTACTS:
        if db.query(ContactPerson).filter(
            ContactPerson.orgnr == orgnr, ContactPerson.email == email
        ).first():
            continue
        db.add(ContactPerson(
            orgnr=orgnr, name=name, title=title, email=email,
            is_primary=is_primary, created_at=now,
        ))
        created += 1
    return created


def _seed_idd(db: Session, firm_id: int, now: datetime) -> int:
    """Seed IDD needs analyses for all demo companies. Returns created count."""
    created = 0
    for c in _COMPANIES:
        orgnr = c["orgnr"]
        if db.query(IddBehovsanalyse).filter(
            IddBehovsanalyse.orgnr == orgnr, IddBehovsanalyse.firm_id == firm_id
        ).first():
            continue
        db.add(IddBehovsanalyse(
            orgnr=orgnr, firm_id=firm_id,
            created_by_email="demo@broker.no", created_at=now,
            client_name=c["navn"],
            risk_appetite="Moderat" if c["risk_score"] < 55 else "Lav",
            has_employees=c["antall_ansatte"] > 0,
            has_vehicles=c["naeringskode1"].startswith("49"),
            has_professional_liability=c["naeringskode1"].startswith("70"),
            has_cyber_risk=c["naeringskode1"].startswith("62"),
            annual_revenue_nok=float(c["base_revenue"]),
            recommended_products=[c["insurance_type"]],
            advisor_notes="Demo-behovsanalyse",
        ))
        created += 1
    return created


_RATIONALE_TEMPLATES: dict[str, str] = {
    "Eiendom og ansvarsforsikring": (
        "Selskapet eier næringseiendom verdt over 100 MNOK og har leieinntekter "
        "som hovedinntekt. {insurer} ble valgt fordi de tilbyr fullverdiforsikring "
        "med leietap-dekning og har lavest premie per kvadratmeter for porteføljen. "
        "Gjenstandsdekning og ansvar er inkludert i én polise."
    ),
    "Cyberforsikring og ansvar": (
        "Som programvareselskap behandler kunden personopplysninger og driftskritiske "
        "systemer for kundene sine. {insurer}s cyberprodukt dekker både første- og "
        "tredjepart, inkluderer DPO-rådgivning ved hendelse og har 4 timers responstid. "
        "Premien er konkurransedyktig sammenlignet med tre andre tilbud."
    ),
    "Entreprise og ansvarsforsikring": (
        "Entreprenørvirksomhet med flere parallelle byggeprosjekter krever bred dekning. "
        "{insurer} har spesialisert entreprise-team og dekker både CAR (Contractor's All "
        "Risks), prosjektansvar og produktansvar i én polise. Premie justert for "
        "skadehistorikk de siste 3 år."
    ),
    "Motorvognforsikring og gods": (
        "Transportselskap med 18 lastebiler trenger flåteforsikring kombinert med "
        "godsansvar (CMR). {insurer} ga best totalpris og har integrasjon med "
        "fleet-management for automatisk premiejustering basert på kjørelengde."
    ),
    "Fiskefartøyforsikring": (
        "Havfiskefartøy med betydelig kaskoverdi krever spesialisert dekning. "
        "{insurer} er ledende i markedet for fiskerinæringen og har fast samarbeid "
        "med klassesselskap. Inkluderer P&I og besetningsforsikring."
    ),
    "Profesjonsansvar og D&O": (
        "Konsulentvirksomhet med honorarbasert inntekt har høy eksponering for "
        "profesjonsansvarskrav. {insurer} tilbyr kombinert profesjonsansvar og "
        "styreansvar (D&O) med høy forsikringssum og global dekning."
    ),
    "Innbo, driftsavbrudd og ansvar": (
        "Detaljhandel med stor varelagerverdi og publikum i lokalene krever "
        "kombinert pakke. {insurer} dekker innbo, driftsavbrudd ved skade, "
        "ansvar overfor kunder og glassbrudd i én polise. Lavere premie enn dagens "
        "leverandør."
    ),
    "Kasko og P&I": (
        "Kystfartsselskap krever H&M kasko og P&I (Protection and Indemnity) for "
        "miljøansvar. {insurer} er anerkjent P&I-club med sterk balanse og global "
        "dekning. Anbefaling støttes av risikorapport fra DNV."
    ),
}

_DEFAULT_RATIONALE = (
    "{insurer} ble valgt basert på beste forhold mellom dekning, premie og servicegrad."
)


def _seed_recommendations(db: Session, firm_id: int, now: datetime) -> int:
    """Seed an anbefalingsbrev for each demo company referencing the chosen insurer
    and a realistic-sounding rationale. Returns created count."""
    created = 0
    for c in _COMPANIES:
        orgnr = c["orgnr"]
        if db.query(Recommendation).filter(
            Recommendation.orgnr == orgnr, Recommendation.firm_id == firm_id
        ).first():
            continue
        template = _RATIONALE_TEMPLATES.get(c["insurance_type"], _DEFAULT_RATIONALE)
        db.add(Recommendation(
            orgnr=orgnr,
            firm_id=firm_id,
            recommended_insurer=c["insurer"],
            rationale_text=template.format(insurer=c["insurer"]),
            created_by_email="demo@broker.no",
            created_at=now,
        ))
        created += 1
    return created


def _seed_submissions(db: Session, firm_id: int, insurer_map: dict[str, int], now: datetime) -> int:
    """Seed market submissions (one quoted submission per company). Returns created count."""
    created = 0
    for c in _COMPANIES:
        orgnr = c["orgnr"]
        insurer_id = insurer_map.get(c["insurer"])
        if not insurer_id:
            continue
        if db.query(Submission).filter(
            Submission.orgnr == orgnr, Submission.firm_id == firm_id,
            Submission.insurer_id == insurer_id,
        ).first():
            continue
        premium = round(c["base_revenue"] * random.uniform(0.015, 0.025) / 1000) * 1000
        db.add(Submission(
            orgnr=orgnr, firm_id=firm_id, insurer_id=insurer_id,
            product_type=c["insurance_type"],
            requested_at=date.today() - timedelta(days=random.randint(5, 20)),
            status=SubmissionStatus.quoted,
            premium_offered_nok=float(premium),
            notes="Demo-tilbud mottatt",
            created_by_email="demo@broker.no", created_at=now,
        ))
        created += 1
    return created


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

    insurer_map = _seed_insurers(db, firm_id, now)
    contacts_created = _seed_contacts(db, now)

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

    idd_created = _seed_idd(db, firm_id, now)
    submissions_created = _seed_submissions(db, firm_id, insurer_map, now)
    recommendations_created = _seed_recommendations(db, firm_id, now)

    db.commit()
    return {
        "companies_created": companies_created,
        "history_rows_created": history_created,
        "policies_created": policies_created,
        "claims_created": claims_created,
        "activities_created": activities_created,
        "contacts_created": contacts_created,
        "insurers_created": len([k for k in insurer_map]),
        "idd_created": idd_created,
        "submissions_created": submissions_created,
        "recommendations_created": recommendations_created,
        "message": (
            f"Demo-data seeded: {companies_created} selskaper, "
            f"{history_created} historikkrader, {policies_created} poliser, "
            f"{contacts_created} kontakter, {idd_created} IDD-analyser, "
            f"{recommendations_created} anbefalingsbrev"
        ),
    }
