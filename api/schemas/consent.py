"""GDPR consent schemas."""
from typing import Optional
from pydantic import BaseModel


class ConsentOut(BaseModel):
    id: int
    orgnr: str
    firm_id: int
    created_at: Optional[str] = None
    lawful_basis: str
    purpose: str
    captured_by_email: Optional[str] = None
    withdrawn_at: Optional[str] = None
    withdrawal_reason: Optional[str] = None
