"""Client token service — create and look up shareable profile tokens."""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from api.db import ClientToken

logger = logging.getLogger(__name__)

_TOKEN_TTL_DAYS = 30


class ClientTokenService:
    def __init__(self, db: Session):
        self.db = db

    def create_token(self, orgnr: str, label: Optional[str] = None) -> ClientToken:
        now = datetime.now(timezone.utc)
        row = ClientToken(
            token=secrets.token_urlsafe(32),
            orgnr=orgnr,
            label=label,
            expires_at=now + timedelta(days=_TOKEN_TTL_DAYS),
            created_at=now,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_or_create_active(
        self, orgnr: str, label: Optional[str] = None
    ) -> ClientToken:
        now = datetime.now(timezone.utc)
        existing = (
            self.db.query(ClientToken)
            .filter(ClientToken.orgnr == orgnr, ClientToken.expires_at > now)
            .order_by(ClientToken.expires_at.desc())
            .first()
        )
        return existing or self.create_token(orgnr, label)

    def list_active(self, orgnr: str) -> list[ClientToken]:
        now = datetime.now(timezone.utc)
        return (
            self.db.query(ClientToken)
            .filter(ClientToken.orgnr == orgnr, ClientToken.expires_at > now)
            .order_by(ClientToken.created_at.desc())
            .all()
        )


# Backward compat
def create_token(orgnr: str, label, db: Session) -> ClientToken:
    return ClientTokenService(db).create_token(orgnr, label)


def get_or_create_active_token(orgnr: str, label, db: Session) -> ClientToken:
    return ClientTokenService(db).get_or_create_active(orgnr, label)


def list_active_tokens(orgnr: str, db: Session) -> list[ClientToken]:
    return ClientTokenService(db).list_active(orgnr)
