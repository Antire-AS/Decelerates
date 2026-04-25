"""Demo-tender helpers — keeps DB writes out of the admin router.

The /admin/seed-demo-tender endpoint imports `upsert_demo_bergmann`
to ensure the Bergmann Industri AS demo Company row exists. Numbers
match the figures in `docs/demo-data/risk_bergmann_industri.pdf` so
the in-app profile lines up with the downloadable PDF.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from api.db import Company

DEMO_BERGMANN_ORGNR = "987654321"
DEMO_BERGMANN_NAVN = "Bergmann Industri AS"


def upsert_demo_bergmann(db: Session) -> Company:
    """Return the demo Bergmann Company row, creating it if missing.
    Idempotent — repeated calls don't create duplicates."""
    existing = db.query(Company).filter(Company.orgnr == DEMO_BERGMANN_ORGNR).first()
    if existing is not None:
        return existing
    company = Company(
        orgnr=DEMO_BERGMANN_ORGNR,
        navn=DEMO_BERGMANN_NAVN,
        organisasjonsform_kode="AS",
        kommune="Oslo",
        land="Norge",
        naeringskode1="25.110",
        naeringskode1_beskrivelse="Produksjon av metallkonstruksjoner og deler",
        regnskapsår=2024,
        sum_driftsinntekter=78_500_000.0,
        sum_egenkapital=21_400_000.0,
        sum_eiendeler=62_800_000.0,
        equity_ratio=0.34,
        risk_score=6,
        antall_ansatte=54,
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return company
