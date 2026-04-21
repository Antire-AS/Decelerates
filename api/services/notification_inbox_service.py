"""In-app notifications service — plan §🟢 #17.

Named *_inbox_service to avoid colliding with the existing
notification_service.py (which is the legacy ACS-email wrapper from the
hexagonal Phase 1 migration). Phase 2 will collapse the two; until then
the file naming keeps imports unambiguous.
"""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from api.db import Notification, NotificationKind, User
from api.domain.exceptions import NotFoundError
import logging

logger = logging.getLogger(__name__)


class NotificationInboxService:
    """Notifications are scoped via `user_id` — see individual methods."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Read paths ───────────────────────────────────────────────────────────

    def list_for_user(
        self,
        user_id: int,
        unread_only: bool = False,
        limit: int = 50,
    ) -> List[Notification]:
        # FIRM_ID_AUDIT: user_id is stronger scoping than firm_id here —
        # each user belongs to exactly one firm, and the router resolves
        # user_id from the authenticated oid.
        q = self.db.query(Notification).filter(Notification.user_id == user_id)
        if unread_only:
            q = q.filter(Notification.read.is_(False))
        return q.order_by(Notification.created_at.desc()).limit(limit).all()

    def unread_count(self, user_id: int) -> int:
        # FIRM_ID_AUDIT: see list_for_user — user_id scope is strongest.
        return (
            self.db.query(Notification)
            .filter(Notification.user_id == user_id, Notification.read.is_(False))
            .count()
        )

    # ── Write paths ──────────────────────────────────────────────────────────

    def create_for_users(
        self,
        firm_id: int,
        kind: NotificationKind,
        title: str,
        message: Optional[str] = None,
        link: Optional[str] = None,
        orgnr: Optional[str] = None,
        user_ids: Optional[List[int]] = None,
    ) -> int:
        """Fan out a notification to every user in the firm (or to a subset
        when `user_ids` is given). Returns the number of rows inserted. Cron
        jobs use this to mirror their email blasts into the bell-icon panel.
        """
        if user_ids is None:
            user_ids = self._user_ids_for_firm(firm_id)
        if not user_ids:
            return 0
        rows = [
            self._build_notification(uid, firm_id, kind, title, message, link, orgnr)
            for uid in user_ids
        ]
        self.db.add_all(rows)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return len(rows)

    @staticmethod
    def _build_notification(
        uid: int,
        firm_id: int,
        kind: NotificationKind,
        title: str,
        message: Optional[str],
        link: Optional[str],
        orgnr: Optional[str],
    ) -> Notification:
        return Notification(
            user_id=uid,
            firm_id=firm_id,
            orgnr=orgnr,
            kind=kind,
            title=title,
            message=message,
            link=link,
            read=False,
            created_at=datetime.now(timezone.utc),
        )

    def _user_ids_for_firm(self, firm_id: int) -> List[int]:
        return [
            row[0]
            for row in self.db.query(User.id).filter(User.firm_id == firm_id).all()
        ]

    def mark_read(self, notification_id: int, user_id: int) -> Notification:
        """Mark a single notification as read. user_id check prevents one
        broker from marking another's notifications.

        # FIRM_ID_AUDIT: user_id is the per-user scope (stronger than firm_id).
        """
        notif = (
            self.db.query(Notification)
            .filter(Notification.id == notification_id, Notification.user_id == user_id)
            .first()
        )
        if not notif:
            raise NotFoundError(f"Notification {notification_id} not found")
        if not notif.read:
            notif.read = True
            try:
                self.db.commit()
                self.db.refresh(notif)
            except Exception:
                self.db.rollback()
                raise
        return notif

    def mark_all_read(self, user_id: int) -> int:
        """Bulk mark every unread notification for this user. Returns count.

        # FIRM_ID_AUDIT: user_id scope is stronger than firm_id.
        """
        updated = (
            self.db.query(Notification)
            .filter(Notification.user_id == user_id, Notification.read.is_(False))
            .update({Notification.read: True}, synchronize_session=False)
        )
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return updated


def create_notification_for_users_safe(
    db: Session,
    firm_id: int,
    kind: NotificationKind,
    title: str,
    message: Optional[str] = None,
    link: Optional[str] = None,
    orgnr: Optional[str] = None,
) -> int:
    """Best-effort wrapper for cron callers — never raises.

    Notification fan-out failures must NOT roll back or block the email-send
    success path. Mirrors the contract of api.services.audit.log_audit.
    """
    try:
        return NotificationInboxService(db).create_for_users(
            firm_id=firm_id,
            kind=kind,
            title=title,
            message=message,
            link=link,
            orgnr=orgnr,
        )
    except Exception:
        # Best-effort; swallow.
        return 0
