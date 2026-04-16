"""CRM schemas — contacts, policies, claims, activities."""
from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, Field


class ContactPersonIn(BaseModel):
    name: str
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    is_primary: bool = False
    notes: Optional[str] = None


class ContactPersonUpdate(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    is_primary: Optional[bool] = None
    notes: Optional[str] = None


class PolicyIn(BaseModel):
    insurer: str
    product_type: str
    policy_number: Optional[str] = None
    contact_person_id: Optional[int] = None
    coverage_amount_nok: Optional[float] = Field(None, ge=0)
    annual_premium_nok: Optional[float] = Field(None, ge=0)
    start_date: Optional[date] = None
    renewal_date: Optional[date] = None
    status: Literal["active", "expired", "cancelled", "pending"] = "active"
    renewal_stage: Optional[Literal["not_started", "ready_to_quote", "quoted", "accepted", "declined"]] = None
    notes: Optional[str] = None
    document_url: Optional[str] = None
    commission_rate_pct: Optional[float] = Field(None, ge=0, le=100)
    commission_amount_nok: Optional[float] = Field(None, ge=0)


class PolicyUpdate(BaseModel):
    insurer: Optional[str] = None
    product_type: Optional[str] = None
    policy_number: Optional[str] = None
    contact_person_id: Optional[int] = None
    coverage_amount_nok: Optional[float] = Field(None, ge=0)
    annual_premium_nok: Optional[float] = Field(None, ge=0)
    start_date: Optional[date] = None
    renewal_date: Optional[date] = None
    status: Optional[Literal["active", "expired", "cancelled", "pending"]] = None
    renewal_stage: Optional[Literal["not_started", "ready_to_quote", "quoted", "accepted", "declined"]] = None
    notes: Optional[str] = None
    document_url: Optional[str] = None
    commission_rate_pct: Optional[float] = Field(None, ge=0, le=100)
    commission_amount_nok: Optional[float] = Field(None, ge=0)


class ClaimIn(BaseModel):
    policy_id: int
    claim_number: Optional[str] = None
    incident_date: Optional[date] = None
    reported_date: Optional[date] = None
    status: Literal["open", "in_review", "settled", "rejected"] = "open"
    description: Optional[str] = None
    estimated_amount_nok: Optional[float] = Field(None, ge=0)
    insurer_contact: Optional[str] = None
    notes: Optional[str] = None


class ClaimUpdate(BaseModel):
    claim_number: Optional[str] = None
    incident_date: Optional[date] = None
    reported_date: Optional[date] = None
    status: Optional[Literal["open", "in_review", "settled", "rejected"]] = None
    description: Optional[str] = None
    estimated_amount_nok: Optional[float] = Field(None, ge=0)
    settled_amount_nok: Optional[float] = Field(None, ge=0)
    insurer_contact: Optional[str] = None
    notes: Optional[str] = None


class ActivityIn(BaseModel):
    activity_type: str
    subject: str
    body: Optional[str] = None
    policy_id: Optional[int] = None
    claim_id: Optional[int] = None
    due_date: Optional[date] = None
    completed: bool = False
    assigned_to_user_id: Optional[int] = None


class ActivityUpdate(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    due_date: Optional[date] = None
    completed: Optional[bool] = None
    assigned_to_user_id: Optional[int] = None


class RenewalAdvanceIn(BaseModel):
    stage: str
    notify_email: Optional[str] = None
