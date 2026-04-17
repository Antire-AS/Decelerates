from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.domain.exceptions import NotFoundError
from api.schemas import BrokerSettingsIn, _BrokerNoteBody
from api.dependencies import get_db
from api.services.audit import log_audit
from api.services.broker import BrokerService

router = APIRouter()


def _get_broker_service(db: Session = Depends(get_db)) -> BrokerService:
    return BrokerService(db)


@router.get("/broker/settings")
def get_broker_settings_endpoint(
    svc: BrokerService = Depends(_get_broker_service),
) -> dict:
    row = svc.get_settings()
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
def save_broker_settings_endpoint(
    body: BrokerSettingsIn,
    svc: BrokerService = Depends(_get_broker_service),
    db: Session = Depends(get_db),
):
    result = svc.save_settings(body)
    log_audit(db, "broker.settings.update", detail={"firm_name": body.firm_name})
    return result


@router.get("/org/{orgnr}/broker-notes")
def list_broker_notes_endpoint(
    orgnr: str, svc: BrokerService = Depends(_get_broker_service)
) -> list:
    rows = svc.list_notes(orgnr)
    return [{"id": r.id, "text": r.text, "created_at": r.created_at} for r in rows]


@router.post("/org/{orgnr}/broker-notes")
def create_broker_note_endpoint(
    orgnr: str,
    body: _BrokerNoteBody,
    db: Session = Depends(get_db),
    svc: BrokerService = Depends(_get_broker_service),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    note = svc.create_note(orgnr, body, firm_id=user.firm_id, author_email=user.email)
    log_audit(db, "broker.notes.create", orgnr=orgnr, detail={"note_id": note.id})
    return {
        "id": note.id,
        "created_at": note.created_at,
        "mentions": note.mentions or [],
    }


@router.delete("/org/{orgnr}/broker-notes/{note_id}")
def delete_broker_note_endpoint(
    orgnr: str,
    note_id: int,
    db: Session = Depends(get_db),
    svc: BrokerService = Depends(_get_broker_service),
) -> dict:
    try:
        svc.delete_note(note_id, orgnr)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Note not found")
    log_audit(db, "broker.notes.delete", orgnr=orgnr, detail={"note_id": note_id})
    return {"deleted": note_id}
