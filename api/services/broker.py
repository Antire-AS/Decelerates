"""Broker settings and notes CRUD service."""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session

from api.db import BrokerSettings, BrokerNote
from api.domain.exceptions import NotFoundError
from api.schemas import BrokerSettingsIn, _BrokerNoteBody


class BrokerService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_settings(self) -> Optional[BrokerSettings]:
        return self.db.query(BrokerSettings).filter(BrokerSettings.id == 1).first()

    def save_settings(self, body: BrokerSettingsIn) -> Dict[str, Any]:
        row = self.db.query(BrokerSettings).filter(BrokerSettings.id == 1).first()
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
            self.db.add(row)
        self.db.commit()
        return {"status": "ok", "updated_at": now}

    def list_notes(self, orgnr: str) -> List[BrokerNote]:
        return (
            self.db.query(BrokerNote)
            .filter(BrokerNote.orgnr == orgnr)
            .order_by(BrokerNote.id.desc())
            .all()
        )

    def create_note(self, orgnr: str, body: _BrokerNoteBody) -> BrokerNote:
        note = BrokerNote(
            orgnr=orgnr,
            text=body.text.strip(),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def delete_note(self, note_id: int, orgnr: str) -> None:
        row = (
            self.db.query(BrokerNote)
            .filter(BrokerNote.id == note_id, BrokerNote.orgnr == orgnr)
            .first()
        )
        if not row:
            raise NotFoundError(f"Note {note_id} not found for orgnr {orgnr}")
        self.db.delete(row)
        self.db.commit()
