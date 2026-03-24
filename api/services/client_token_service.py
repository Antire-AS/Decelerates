"""Client token service — create and look up shareable profile tokens."""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from api.db import ClientToken

_TOKEN_TTL_DAYS = 30


def create_token(orgnr: str, label: Optional[str], db: Session) -> ClientToken:
    """Create a fresh 30-day read-only token for an org."""
    now = datetime.now(timezone.utc)
    row = ClientToken(
        token=secrets.token_urlsafe(32),
        orgnr=orgnr,
        label=label,
        expires_at=now + timedelta(days=_TOKEN_TTL_DAYS),
        created_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_or_create_active_token(
    orgnr: str, label: Optional[str], db: Session
) -> ClientToken:
    """Return the newest non-expired token for an org, creating one if none exists."""
    now = datetime.now(timezone.utc)
    existing = (
        db.query(ClientToken)
        .filter(ClientToken.orgnr == orgnr, ClientToken.expires_at > now)
        .order_by(ClientToken.expires_at.desc())
        .first()
    )
    if existing:
        return existing
    return create_token(orgnr, label, db)


def list_active_tokens(orgnr: str, db: Session) -> list[ClientToken]:
    """Return all non-expired tokens for an org, newest first."""
    now = datetime.now(timezone.utc)
    return (
        db.query(ClientToken)
        .filter(ClientToken.orgnr == orgnr, ClientToken.expires_at > now)
        .order_by(ClientToken.created_at.desc())
        .all()
    )
