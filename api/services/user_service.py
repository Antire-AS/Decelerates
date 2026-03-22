"""User provisioning and management service."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from api.db import BrokerFirm, User, UserRole
from api.domain.exceptions import ForbiddenError, NotFoundError
from api.schemas import UserRoleUpdate


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_or_create(self, oid: str, email: str, name: str) -> User:
        """Auto-provision user on first Azure AD login, assigned to the default firm."""
        user = self.db.query(User).filter(User.azure_oid == oid).first()
        if user:
            return user
        firm = self._ensure_default_firm()
        user = User(
            firm_id=firm.id,
            azure_oid=oid,
            email=email,
            name=name,
            role=UserRole.broker,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_by_oid(self, oid: str) -> Optional[User]:
        return self.db.query(User).filter(User.azure_oid == oid).first()

    def list_users(self, firm_id: int) -> list[User]:
        return self.db.query(User).filter(User.firm_id == firm_id).all()

    def update_role(self, user_id: int, body: UserRoleUpdate, requester_role: str) -> User:
        if requester_role != "admin":
            raise ForbiddenError("Only admins can change user roles")
        try:
            new_role = UserRole[body.role]
        except KeyError:
            raise NotFoundError(f"Unknown role: {body.role}")
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise NotFoundError(f"User {user_id} not found")
        user.role = new_role
        self.db.commit()
        self.db.refresh(user)
        return user

    def _ensure_default_firm(self) -> BrokerFirm:
        firm = self.db.query(BrokerFirm).filter(BrokerFirm.id == 1).first()
        if not firm:
            firm = BrokerFirm(id=1, name="Default Firm", created_at=datetime.now(timezone.utc))
            self.db.add(firm)
            self.db.flush()
        return firm
