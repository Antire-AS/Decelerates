"""Seed demo tenders from docs/demo-data into the local database."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime, timezone, date, timedelta
from api.models._base import SessionLocal
from api.models.tender import Tender, TenderRecipient, TenderStatus, TenderRecipientStatus

FIRM_ID = 1

DEMO_TENDERS = [
    {
        "orgnr": "987654321",
        "title": "Totalforsikring Bergmann Industri 2026",
        "product_types": ["Yrkesskade", "Ansvarsforsikring", "Eiendomsforsikring", "Motorvogn"],
        "deadline": date.today() + timedelta(days=21),
        "notes": "Metallproduksjonsbedrift med 54 ansatte. Risikoscore 6 (moderat).",
        "status": TenderStatus.sent,
        "recipients": [
            {"name": "If Skadeforsikring", "email": "anbud@if.no", "status": TenderRecipientStatus.sent},
            {"name": "Gjensidige Forsikring", "email": "anbud@gjensidige.no", "status": TenderRecipientStatus.received},
            {"name": "Tryg Forsikring", "email": "anbud@tryg.no", "status": TenderRecipientStatus.sent},
        ],
    },
    {
        "orgnr": "912345678",
        "title": "Forsikringspakke Nordlys Restaurantgruppe 2026",
        "product_types": ["Ansvarsforsikring", "Eiendomsforsikring", "Personalforsikring"],
        "deadline": date.today() + timedelta(days=14),
        "notes": "Restaurantkjede med 3 lokasjoner. Høy risikoscore 11.",
        "status": TenderStatus.closed,
        "recipients": [
            {"name": "If Skadeforsikring", "email": "anbud@if.no", "status": TenderRecipientStatus.received},
            {"name": "Gjensidige Forsikring", "email": "anbud@gjensidige.no", "status": TenderRecipientStatus.received},
        ],
    },
    {
        "orgnr": "998765432",
        "title": "Rådgiverkonsern Arcticom Consulting — Cyber & Ansvar",
        "product_types": ["Cyber", "Styreansvar (D&O)", "Ansvarsforsikring"],
        "deadline": date.today() + timedelta(days=30),
        "notes": "Rådgivningsfirma, lav risikoscore 3. Fokus på cyber og D&O.",
        "status": TenderStatus.draft,
        "recipients": [],
    },
    {
        "orgnr": "984851006",
        "title": "DNB Bank ASA — Styreansvar og Cyber 2026",
        "product_types": ["Styreansvar (D&O)", "Cyber", "Kriminalitetsforsikring"],
        "deadline": date.today() + timedelta(days=45),
        "notes": "Stor bank. Risikoscore 4 (lav). Fokus på D&O og cyberforsikring.",
        "status": TenderStatus.analysed,
        "recipients": [
            {"name": "If Skadeforsikring", "email": "anbud@if.no", "status": TenderRecipientStatus.received},
            {"name": "Gjensidige Forsikring", "email": "anbud@gjensidige.no", "status": TenderRecipientStatus.received},
            {"name": "Tryg Forsikring", "email": "anbud@tryg.no", "status": TenderRecipientStatus.received},
        ],
    },
    {
        "orgnr": "923609016",
        "title": "Norwegian Air Shuttle — Totalforsikring",
        "product_types": ["Ansvarsforsikring", "Motorvogn", "Reiseforsikring", "Personalforsikring"],
        "deadline": date.today() - timedelta(days=5),
        "notes": "Flyselskap med høy risiko (score 14). Fristen er utløpt.",
        "status": TenderStatus.sent,
        "recipients": [
            {"name": "If Skadeforsikring", "email": "anbud@if.no", "status": TenderRecipientStatus.sent},
            {"name": "Gjensidige Forsikring", "email": "anbud@gjensidige.no", "status": TenderRecipientStatus.pending},
        ],
    },
]

def seed():
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        count = 0
        for t in DEMO_TENDERS:
            exists = db.query(Tender).filter(
                Tender.orgnr == t["orgnr"],
                Tender.firm_id == FIRM_ID,
                Tender.title == t["title"],
            ).first()
            if exists:
                print(f"  Skip (exists): {t['title']}")
                continue

            tender = Tender(
                orgnr=t["orgnr"],
                firm_id=FIRM_ID,
                title=t["title"],
                product_types=t["product_types"],
                deadline=t["deadline"],
                notes=t["notes"],
                status=t["status"],
                created_at=now,
            )
            db.add(tender)
            db.flush()

            for r in t["recipients"]:
                recipient = TenderRecipient(
                    tender_id=tender.id,
                    insurer_name=r["name"],
                    insurer_email=r["email"],
                    status=r["status"],
                    created_at=now,
                )
                db.add(recipient)

            db.commit()
            count += 1
            print(f"  Created: {t['title']}")

        print(f"\nDone — {count} tenders seeded.")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
