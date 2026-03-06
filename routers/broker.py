from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from domain.exceptions import NotFoundError
from schemas import BrokerSettingsIn, _BrokerNoteBody
from dependencies import get_db
from services.broker import (
    get_broker_settings,
    save_broker_settings,
    list_broker_notes,
    create_broker_note,
    delete_broker_note,
)

router = APIRouter()


@router.get("/broker/settings")
def get_broker_settings_endpoint(db: Session = Depends(get_db)):
    row = get_broker_settings(db)
    if not row:
        return {}
    return {
        "firm_name": row.firm_name,
        "orgnr": row.orgnr,
        "address": row.address,
        "contact_name": row.contact_name,
        "contact_email": row.contact_email,
        "contact_phone": row.contact_phone,
        "updated_at": row.updated_at,
    }


@router.post("/broker/settings")
def save_broker_settings_endpoint(body: BrokerSettingsIn, db: Session = Depends(get_db)):
    return save_broker_settings(body, db)


@router.get("/org/{orgnr}/broker-notes")
def list_broker_notes_endpoint(orgnr: str, db: Session = Depends(get_db)):
    rows = list_broker_notes(orgnr, db)
    return [{"id": r.id, "text": r.text, "created_at": r.created_at} for r in rows]


@router.post("/org/{orgnr}/broker-notes")
def create_broker_note_endpoint(orgnr: str, body: _BrokerNoteBody, db: Session = Depends(get_db)):
    note = create_broker_note(orgnr, body, db)
    return {"id": note.id, "created_at": note.created_at}


@router.delete("/org/{orgnr}/broker-notes/{note_id}")
def delete_broker_note_endpoint(orgnr: str, note_id: int, db: Session = Depends(get_db)):
    try:
        delete_broker_note(note_id, orgnr, db)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"deleted": note_id}
