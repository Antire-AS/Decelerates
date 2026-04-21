"""User provisioning and management service."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from api.db import BrokerFirm, User, UserRole
from api.domain.exceptions import ForbiddenError, NotFoundError
from api.schemas import UserRoleUpdate
import logging

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_or_create(
        self, oid: str, email: str, name: str, firm_id: Optional[int] = None
    ) -> User:
        """Auto-provision user on first Azure AD login.

        If *firm_id* is provided (e.g. from SSO tenant resolution), assign the
        user to that firm. Otherwise fall back to the default firm (id=1).
        """
        user = self.db.query(User).filter(User.azure_oid == oid).first()
        if user:
            return user
        resolved_firm_id = firm_id or self._ensure_default_firm().id
        user = User(
            firm_id=resolved_firm_id,
            azure_oid=oid,
            email=email,
            name=name,
            role=UserRole.broker,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(user)
        try:
            self.db.commit()
            self.db.refresh(user)
        except Exception:
            self.db.rollback()
            raise
        return user

    def get_by_oid(self, oid: str) -> Optional[User]:
        # FIRM_ID_AUDIT: Azure OID is globally unique per user; a firm_id
        # filter would be redundant and block legitimate first-login lookups.
        return self.db.query(User).filter(User.azure_oid == oid).first()

    def list_users(self, firm_id: int) -> list[User]:
        return self.db.query(User).filter(User.firm_id == firm_id).all()

    def update_role(
        self,
        user_id: int,
        body: UserRoleUpdate,
        requester_role: str,
        requester_firm_id: int,
    ) -> User:
        if requester_role != "admin":
            raise ForbiddenError("Only admins can change user roles")
        try:
            new_role = UserRole[body.role]
        except KeyError:
            raise NotFoundError(f"Unknown role: {body.role}")
        # Admins can only update users in their own firm. Without this filter
        # an admin of firm A could flip roles on firm B's users just by
        # guessing user_ids — the tenant-isolation audit caught this.
        user = (
            self.db.query(User)
            .filter(User.id == user_id, User.firm_id == requester_firm_id)
            .first()
        )
        if not user:
            raise NotFoundError(f"User {user_id} not found")
        user.role = new_role  # type: ignore[assignment]
        try:
            self.db.commit()
            self.db.refresh(user)
        except Exception:
            self.db.rollback()
            raise
        return user

    def _ensure_default_firm(self) -> BrokerFirm:
        firm = self.db.query(BrokerFirm).filter(BrokerFirm.id == 1).first()
        if not firm:
            firm = BrokerFirm(
                id=1, name="Default Firm", created_at=datetime.now(timezone.utc)
            )
            self.db.add(firm)
            self.db.flush()
        return firm
