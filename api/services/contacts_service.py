"""Contact persons CRUD service."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from api.db import ContactPerson
from api.domain.exceptions import NotFoundError
from api.schemas import ContactPersonIn, ContactPersonUpdate
import logging

logger = logging.getLogger(__name__)


class ContactsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_contacts(self, orgnr: str) -> list[ContactPerson]:
        return (
            self.db.query(ContactPerson)
            .filter(ContactPerson.orgnr == orgnr)
            .order_by(ContactPerson.is_primary.desc(), ContactPerson.name)
            .all()
        )

    def create_contact(self, orgnr: str, body: ContactPersonIn) -> ContactPerson:
        if body.is_primary:
            self._clear_primary(orgnr)
        contact = ContactPerson(
            orgnr=orgnr,
            name=body.name,
            title=body.title,
            email=body.email,
            phone=body.phone,
            is_primary=body.is_primary,
            notes=body.notes,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(contact)
        try:
            self.db.commit()
            self.db.refresh(contact)
        except Exception:
            self.db.rollback()
            raise
        return contact

    def update_contact(
        self, contact_id: int, orgnr: str, body: ContactPersonUpdate
    ) -> ContactPerson:
        contact = self._get_or_raise(contact_id, orgnr)
        if body.is_primary:
            self._clear_primary(orgnr)
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(contact, field, value)
        try:
            self.db.commit()
            self.db.refresh(contact)
        except Exception:
            self.db.rollback()
            raise
        return contact

    def delete_contact(self, contact_id: int, orgnr: str) -> None:
        contact = self._get_or_raise(contact_id, orgnr)
        self.db.delete(contact)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _get_or_raise(self, contact_id: int, orgnr: str) -> ContactPerson:
        c = (
            self.db.query(ContactPerson)
            .filter(ContactPerson.id == contact_id, ContactPerson.orgnr == orgnr)
            .first()
        )
        if not c:
            raise NotFoundError(f"Contact {contact_id} not found for orgnr {orgnr}")
        return c

    def _clear_primary(self, orgnr: str) -> None:
        self.db.query(ContactPerson).filter(
            ContactPerson.orgnr == orgnr,
            ContactPerson.is_primary.is_(True),
        ).update({"is_primary": False})
