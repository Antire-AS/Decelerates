from datetime import date
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str


class IngestKnowledgeRequest(BaseModel):
    text: str
    source: str = "custom_note"


class PdfHistoryRequest(BaseModel):
    pdf_url: str
    year: int
    label: str = ""


class DocChatRequest(BaseModel):
    question: str


class DocCompareRequest(BaseModel):
    doc_ids: List[int]


class ForsikringstilbudRequest(BaseModel):
    anbefalinger: list = []
    total_premieanslag: str = ""
    sammendrag: str = ""


class _BrokerNoteBody(BaseModel):
    text: str


class BrokerSettingsIn(BaseModel):
    firm_name: str
    orgnr: Optional[str] = None
    address: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None


class SlaIn(BaseModel):
    form_data: Dict[str, Any]


class PortfolioCreate(BaseModel):
    name: str
    description: Optional[str] = ""


class PortfolioAddCompany(BaseModel):
    orgnr: str


# ── Contacts ────────────────────────────────────────────────────────────────

class ContactPersonIn(BaseModel):
    name:       str
    title:      Optional[str] = None
    email:      Optional[str] = None
    phone:      Optional[str] = None
    is_primary: bool = False
    notes:      Optional[str] = None


class ContactPersonUpdate(BaseModel):
    name:       Optional[str] = None
    title:      Optional[str] = None
    email:      Optional[str] = None
    phone:      Optional[str] = None
    is_primary: Optional[bool] = None
    notes:      Optional[str] = None


# ── Policies ────────────────────────────────────────────────────────────────

class PolicyIn(BaseModel):
    insurer:              str
    product_type:         str
    policy_number:        Optional[str] = None
    contact_person_id:    Optional[int] = None
    coverage_amount_nok:  Optional[float] = Field(None, ge=0)
    annual_premium_nok:   Optional[float] = Field(None, ge=0)
    start_date:           Optional[date] = None
    renewal_date:         Optional[date] = None
    status:               Literal["active", "expired", "cancelled", "pending"] = "active"
    renewal_stage:        Optional[Literal["not_started", "ready_to_quote", "quoted", "accepted", "declined"]] = None
    notes:                Optional[str] = None
    document_url:         Optional[str] = None
    commission_rate_pct:  Optional[float] = Field(None, ge=0, le=100)
    commission_amount_nok: Optional[float] = Field(None, ge=0)


class PolicyUpdate(BaseModel):
    insurer:              Optional[str] = None
    product_type:         Optional[str] = None
    policy_number:        Optional[str] = None
    contact_person_id:    Optional[int] = None
    coverage_amount_nok:  Optional[float] = Field(None, ge=0)
    annual_premium_nok:   Optional[float] = Field(None, ge=0)
    start_date:           Optional[date] = None
    renewal_date:         Optional[date] = None
    status:               Optional[Literal["active", "expired", "cancelled", "pending"]] = None
    renewal_stage:        Optional[Literal["not_started", "ready_to_quote", "quoted", "accepted", "declined"]] = None
    notes:                Optional[str] = None
    document_url:         Optional[str] = None
    commission_rate_pct:  Optional[float] = Field(None, ge=0, le=100)
    commission_amount_nok: Optional[float] = Field(None, ge=0)


class IddBehovsanalyseIn(BaseModel):
    client_name:                Optional[str] = None
    client_contact_name:        Optional[str] = None
    client_contact_email:       Optional[str] = None
    existing_insurance:         Optional[List[Dict[str, Any]]] = None
    risk_appetite:              Optional[str] = None  # lav / middels / høy
    property_owned:             bool = False
    has_employees:              bool = False
    has_vehicles:               bool = False
    has_professional_liability: bool = False
    has_cyber_risk:             bool = False
    annual_revenue_nok:         Optional[float] = None
    special_requirements:       Optional[str] = None
    recommended_products:       Optional[List[str]] = None
    advisor_notes:              Optional[str] = None
    suitability_basis:          Optional[str] = None
    fee_basis:                  Optional[str] = None  # provisjon / honorar / begge
    fee_amount_nok:             Optional[float] = None


class RenewalAdvanceIn(BaseModel):
    stage:        str            # not_started | ready_to_quote | quoted | accepted | declined
    notify_email: Optional[str] = None  # if set, send stage-change email to this address


# ── Claims ──────────────────────────────────────────────────────────────────

class ClaimIn(BaseModel):
    policy_id:            int
    claim_number:         Optional[str] = None
    incident_date:        Optional[date] = None
    reported_date:        Optional[date] = None
    status:               Literal["open", "in_review", "settled", "rejected"] = "open"
    description:          Optional[str] = None
    estimated_amount_nok: Optional[float] = Field(None, ge=0)
    insurer_contact:      Optional[str] = None
    notes:                Optional[str] = None


class ClaimUpdate(BaseModel):
    claim_number:         Optional[str] = None
    incident_date:        Optional[date] = None
    reported_date:        Optional[date] = None
    status:               Optional[Literal["open", "in_review", "settled", "rejected"]] = None
    description:          Optional[str] = None
    estimated_amount_nok: Optional[float] = Field(None, ge=0)
    settled_amount_nok:   Optional[float] = Field(None, ge=0)
    insurer_contact:      Optional[str] = None
    notes:                Optional[str] = None


# ── Activities ───────────────────────────────────────────────────────────────

class ActivityIn(BaseModel):
    activity_type: str
    subject:       str
    body:          Optional[str] = None
    policy_id:     Optional[int] = None
    claim_id:      Optional[int] = None
    due_date:      Optional[date] = None
    completed:     bool = False


class ActivityUpdate(BaseModel):
    subject:   Optional[str] = None
    body:      Optional[str] = None
    due_date:  Optional[date] = None
    completed: Optional[bool] = None


# ── Users ────────────────────────────────────────────────────────────────────

class UserRoleUpdate(BaseModel):
    role: str  # "admin" | "broker" | "viewer"


# ── Insurers ─────────────────────────────────────────────────────────────────

class InsurerIn(BaseModel):
    name:          str
    org_number:    Optional[str] = None
    contact_name:  Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    appetite:      Optional[List[str]] = None
    notes:         Optional[str] = None


class InsurerUpdate(BaseModel):
    name:          Optional[str] = None
    org_number:    Optional[str] = None
    contact_name:  Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    appetite:      Optional[List[str]] = None
    notes:         Optional[str] = None


# ── Submissions ───────────────────────────────────────────────────────────────

class SubmissionIn(BaseModel):
    insurer_id:          int
    product_type:        str
    requested_at:        Optional[date] = None
    status:              Literal["pending", "quoted", "declined", "withdrawn"] = "pending"
    premium_offered_nok: Optional[float] = Field(None, ge=0)
    notes:               Optional[str] = None


class SubmissionUpdate(BaseModel):
    status:              Optional[Literal["pending", "quoted", "declined", "withdrawn"]] = None
    premium_offered_nok: Optional[float] = Field(None, ge=0)
    requested_at:        Optional[date] = None
    notes:               Optional[str] = None


# ── Recommendations ───────────────────────────────────────────────────────────

class RecommendationIn(BaseModel):
    recommended_insurer: str
    submission_ids:      Optional[List[int]] = None
    idd_id:              Optional[int] = None
    rationale_text:      Optional[str] = None   # broker can override LLM draft
