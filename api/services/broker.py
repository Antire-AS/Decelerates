"""Broker settings and notes CRUD service."""
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session

from api.db import BrokerSettings, BrokerNote, NotificationKind, User
from api.domain.exceptions import NotFoundError
from api.schemas import BrokerSettingsIn, _BrokerNoteBody
import logging

logger = logging.getLogger(__name__)


# @mention parser — accepts @user@firm.no patterns. Matches an `@` followed by
# a standard email; restricts to same-firm via the User lookup downstream.
_MENTION_RE = re.compile(r"@([\w.+-]+@[\w-]+(?:\.[\w-]+)+)")


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
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"status": "ok", "updated_at": now}

    def list_notes(self, orgnr: str) -> List[BrokerNote]:
        return (
            self.db.query(BrokerNote)
            .filter(BrokerNote.orgnr == orgnr)
            .order_by(BrokerNote.id.desc())
            .all()
        )

    def create_note(
        self,
        orgnr: str,
        body: _BrokerNoteBody,
        firm_id: Optional[int] = None,
        author_email: Optional[str] = None,
    ) -> BrokerNote:
        text = body.text.strip()
        # Plan §🟢 #14 — parse @mentions, restrict to same-firm users, persist
        # the resolved emails on the note row, then fan out notifications.
        mentions: List[str] = []
        mentioned_user_ids: List[int] = []
        if firm_id is not None:
            mentions, mentioned_user_ids = self._resolve_mentions(text, firm_id)
        note = BrokerNote(
            orgnr=orgnr,
            text=text,
            mentions=mentions or None,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.db.add(note)
        try:
            self.db.commit()
            self.db.refresh(note)
        except Exception:
            self.db.rollback()
            raise
        if mentioned_user_ids and firm_id is not None:
            self._notify_mentioned(
                firm_id=firm_id,
                orgnr=orgnr,
                text=text,
                author_email=author_email,
                user_ids=mentioned_user_ids,
            )
        return note

    def _notify_mentioned(
        self,
        firm_id: int,
        orgnr: str,
        text: str,
        author_email: Optional[str],
        user_ids: List[int],
    ) -> None:
        """Targeted fan-out to mentioned users only. Best-effort — never raises."""
        from api.services.notification_inbox_service import NotificationInboxService
        preview = text[:120] + ("…" if len(text) > 120 else "")
        try:
            NotificationInboxService(self.db).create_for_users(
                firm_id=firm_id,
                kind=NotificationKind.mention,
                title=f"Du er nevnt av {author_email or 'en megler'}",
                message=preview,
                link=f"/search/{orgnr}?tab=notater",
                orgnr=orgnr,
                user_ids=user_ids,
            )
        except Exception:
            pass

    def _resolve_mentions(self, text: str, firm_id: int) -> tuple[List[str], List[int]]:
        """Extract @mentions from `text` and look up matching same-firm users.
        Returns (verified_emails, user_ids). Anything that doesn't match a real
        same-firm user is silently dropped — prevents leaking notification
        delivery to arbitrary external email addresses."""
        candidates = list(set(_MENTION_RE.findall(text)))
        if not candidates:
            return [], []
        rows = (
            self.db.query(User.id, User.email)
            .filter(User.firm_id == firm_id, User.email.in_(candidates))
            .all()
        )
        return [r[1] for r in rows], [r[0] for r in rows]

    def delete_note(self, note_id: int, orgnr: str) -> None:
        row = (
            self.db.query(BrokerNote)
            .filter(BrokerNote.id == note_id, BrokerNote.orgnr == orgnr)
            .first()
        )
        if not row:
            raise NotFoundError(f"Note {note_id} not found for orgnr {orgnr}")
        self.db.delete(row)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
