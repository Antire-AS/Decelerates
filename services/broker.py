"""Broker settings and notes CRUD service."""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session

from db import BrokerSettings, BrokerNote
from domain.exceptions import NotFoundError
from schemas import BrokerSettingsIn, _BrokerNoteBody


def get_broker_settings(db: Session) -> Optional[BrokerSettings]:
    return db.query(BrokerSettings).filter(BrokerSettings.id == 1).first()


def save_broker_settings(body: BrokerSettingsIn, db: Session) -> Dict[str, Any]:
    row = db.query(BrokerSettings).filter(BrokerSettings.id == 1).first()
    now = datetime.now(timezone.utc).isoformat()
    if row:
        row.firm_name = body.firm_name
        row.orgnr = body.orgnr
        row.address = body.address
        row.contact_name = body.contact_name
        row.contact_email = body.contact_email
        row.contact_phone = body.contact_phone
        row.updated_at = now
    else:
        row = BrokerSettings(
            id=1,
            firm_name=body.firm_name,
            orgnr=body.orgnr,
            address=body.address,
            contact_name=body.contact_name,
            contact_email=body.contact_email,
            contact_phone=body.contact_phone,
            updated_at=now,
        )
        db.add(row)
    db.commit()
    return {"status": "ok", "updated_at": now}


def list_broker_notes(orgnr: str, db: Session) -> List[BrokerNote]:
    return (
        db.query(BrokerNote)
        .filter(BrokerNote.orgnr == orgnr)
        .order_by(BrokerNote.id.desc())
        .all()
    )


def create_broker_note(orgnr: str, body: _BrokerNoteBody, db: Session) -> BrokerNote:
    note = BrokerNote(
        orgnr=orgnr,
        text=body.text.strip(),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def delete_broker_note(note_id: int, orgnr: str, db: Session) -> None:
    row = db.query(BrokerNote).filter(BrokerNote.id == note_id, BrokerNote.orgnr == orgnr).first()
    if not row:
        raise NotFoundError(f"Note {note_id} not found for orgnr {orgnr}")
    db.delete(row)
    db.commit()
