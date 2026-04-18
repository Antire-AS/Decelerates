"""Insurance schemas — insurers, submissions, IDD, recommendations, offers."""

from datetime import date
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class IddBehovsanalyseIn(BaseModel):
    client_name: Optional[str] = None
    client_contact_name: Optional[str] = None
    client_contact_email: Optional[str] = None
    existing_insurance: Optional[List[Dict[str, Any]]] = None
    risk_appetite: Optional[str] = None
    property_owned: bool = False
    has_employees: bool = False
    has_vehicles: bool = False
    has_professional_liability: bool = False
    has_cyber_risk: bool = False
    annual_revenue_nok: Optional[float] = None
    special_requirements: Optional[str] = None
    recommended_products: Optional[List[str]] = None
    advisor_notes: Optional[str] = None
    suitability_basis: Optional[str] = None
    fee_basis: Optional[str] = None
    fee_amount_nok: Optional[float] = None


class InsurerIn(BaseModel):
    name: str
    org_number: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    appetite: Optional[List[str]] = None
    notes: Optional[str] = None


class InsurerUpdate(BaseModel):
    name: Optional[str] = None
    org_number: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    appetite: Optional[List[str]] = None
    notes: Optional[str] = None


class SubmissionIn(BaseModel):
    insurer_id: int
    product_type: str
    requested_at: Optional[date] = None
    status: Literal["pending", "quoted", "declined", "withdrawn"] = "pending"
    premium_offered_nok: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = None


class SubmissionUpdate(BaseModel):
    status: Optional[Literal["pending", "quoted", "declined", "withdrawn"]] = None
    premium_offered_nok: Optional[float] = Field(None, ge=0)
    requested_at: Optional[date] = None
    notes: Optional[str] = None


class RecommendationIn(BaseModel):
    recommended_insurer: str
    submission_ids: Optional[List[int]] = None
    idd_id: Optional[int] = None
    rationale_text: Optional[str] = None


class InsurerOut(BaseModel):
    id: int
    firm_id: int
    name: str
    org_number: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    appetite: List[str] = []
    notes: Optional[str] = None
    created_at: Optional[str] = None


class SubmissionOut(BaseModel):
    id: int
    orgnr: str
    insurer_id: int
    insurer_name: Optional[str] = None
    product_type: str
    requested_at: Optional[str] = None
    status: str
    premium_offered_nok: Optional[float] = None
    notes: Optional[str] = None
    created_by_email: Optional[str] = None
    created_at: Optional[str] = None


class IddBehovsanalyseOut(BaseModel):
    id: int
    orgnr: str
    created_by_email: Optional[str] = None
    created_at: Optional[str] = None
    client_name: Optional[str] = None
    client_contact_name: Optional[str] = None
    client_contact_email: Optional[str] = None
    existing_insurance: List[Any] = []
    risk_appetite: Optional[str] = None
    property_owned: Optional[bool] = None
    has_employees: Optional[bool] = None
    has_vehicles: Optional[bool] = None
    has_professional_liability: Optional[bool] = None
    has_cyber_risk: Optional[bool] = None
    annual_revenue_nok: Optional[float] = None
    special_requirements: Optional[str] = None
    recommended_products: List[str] = []
    advisor_notes: Optional[str] = None
    suitability_basis: Optional[str] = None
    fee_basis: Optional[str] = None
    fee_amount_nok: Optional[float] = None


class SigningSessionOut(BaseModel):
    session_id: str
    signing_url: str


class SignicatWebhookAck(BaseModel):
    received: bool
