"""Audit log schemas."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class AuditLogEntryOut(BaseModel):
    id: int
    orgnr: Optional[str] = None
    action: str
    actor_email: Optional[str] = None
    detail: Optional[str] = None
    created_at: datetime


class AuditLogPageOut(BaseModel):
    items: List[AuditLogEntryOut]
    total: int
    offset: int
    limit: int
    has_more: bool
