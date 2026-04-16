"""Notification schemas."""
from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel

NotificationKindLiteral = Literal[
    "renewal", "activity_overdue", "mention", "claim_new",
    "deal_won", "coverage_gap", "digest",
]


class NotificationOut(BaseModel):
    id: int
    user_id: int
    firm_id: int
    orgnr: Optional[str] = None
    kind: NotificationKindLiteral
    title: str
    message: Optional[str] = None
    link: Optional[str] = None
    read: bool
    created_at: datetime


class NotificationListOut(BaseModel):
    items: List[NotificationOut]
    unread_count: int


class NotificationMarkReadOut(BaseModel):
    updated: int
