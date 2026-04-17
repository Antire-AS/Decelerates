"""Contact person endpoints for a client company."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth import CurrentUser, get_current_user
from api.dependencies import get_db
from api.domain.exceptions import NotFoundError
from api.schemas import ContactPersonIn, ContactPersonUpdate
from api.services.audit import log_audit
from api.services.contacts_service import ContactsService

router = APIRouter()


def _svc(db: Session = Depends(get_db)) -> ContactsService:
    return ContactsService(db)


def _serialize(c) -> dict:
    return {
        "id": c.id,
        "orgnr": c.orgnr,
        "name": c.name,
        "title": c.title,
        "email": c.email,
        "phone": c.phone,
        "is_primary": c.is_primary,
        "notes": c.notes,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@router.get("/org/{orgnr}/contacts")
def list_contacts(
    orgnr: str,
    svc: ContactsService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    return [_serialize(c) for c in svc.list_contacts(orgnr)]


@router.post("/org/{orgnr}/contacts", status_code=201)
def create_contact(
    orgnr: str,
    body: ContactPersonIn,
    db: Session = Depends(get_db),
    svc: ContactsService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    c = svc.create_contact(orgnr, body)
    log_audit(
        db,
        "contact.create",
        orgnr=orgnr,
        detail={"contact_id": c.id, "name": body.name},
    )
    return _serialize(c)


@router.put("/org/{orgnr}/contacts/{contact_id}")
def update_contact(
    orgnr: str,
    contact_id: int,
    body: ContactPersonUpdate,
    db: Session = Depends(get_db),
    svc: ContactsService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    try:
        c = svc.update_contact(contact_id, orgnr, body)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    log_audit(db, "contact.update", orgnr=orgnr, detail={"contact_id": contact_id})
    return _serialize(c)


@router.delete("/org/{orgnr}/contacts/{contact_id}", status_code=204)
def delete_contact(
    orgnr: str,
    contact_id: int,
    db: Session = Depends(get_db),
    svc: ContactsService = Depends(_svc),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    try:
        svc.delete_contact(contact_id, orgnr)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    log_audit(db, "contact.delete", orgnr=orgnr, detail={"contact_id": contact_id})
