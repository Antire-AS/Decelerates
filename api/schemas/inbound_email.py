"""Inbound-email log schemas (admin surface)."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class IncomingEmailLogEntryOut(BaseModel):
    id: int
    received_at: datetime
    sender: Optional[str] = None
    recipient: Optional[str] = None
    subject: Optional[str] = None
    tender_ref: Optional[str] = None
    tender_id: Optional[int] = None
    recipient_id: Optional[int] = None
    status: str
    error_message: Optional[str] = None
    attachment_count: int
    offer_id: Optional[int] = None
    message_id: Optional[str] = None


class IncomingEmailLogPageOut(BaseModel):
    items: List[IncomingEmailLogEntryOut]
    total: int
    offset: int
    limit: int
    has_more: bool
