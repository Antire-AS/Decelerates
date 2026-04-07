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


class PolicyCommissionOut(BaseModel):
    id:                    int
    policy_number:         Optional[str] = None
    product_type:          str
    insurer:               str
    status:                str
    annual_premium_nok:    Optional[float] = None
    commission_rate_pct:   Optional[float] = None
    commission_amount_nok: float


class CommissionSummaryOut(BaseModel):
    total_commission_ytd:       float
    total_premium_managed:      float
    active_policy_count:        int
    revenue_by_product_type:    dict
    revenue_by_insurer:         dict
    renewal_commission_vs_new:  dict


class CommissionClientOut(BaseModel):
    orgnr:                      str
    total_commission_lifetime:  float
    total_commission_ytd:       float
    policies:                   List[PolicyCommissionOut]


class PolicyMissingOut(BaseModel):
    id:                 int
    orgnr:              str
    policy_number:      Optional[str] = None
    product_type:       str
    insurer:            str
    annual_premium_nok: Optional[float] = None
    renewal_date:       Optional[str] = None


class InsurerOut(BaseModel):
    id:            int
    firm_id:       int
    name:          str
    org_number:    Optional[str] = None
    contact_name:  Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    appetite:      List[str] = []
    notes:         Optional[str] = None
    created_at:    Optional[str] = None


class SubmissionOut(BaseModel):
    id:                  int
    orgnr:               str
    insurer_id:          int
    insurer_name:        Optional[str] = None
    product_type:        str
    requested_at:        Optional[str] = None
    status:              str
    premium_offered_nok: Optional[float] = None
    notes:               Optional[str] = None
    created_by_email:    Optional[str] = None
    created_at:          Optional[str] = None


class IddBehovsanalyseOut(BaseModel):
    id:                         int
    orgnr:                      str
    created_by_email:           Optional[str] = None
    created_at:                 Optional[str] = None
    client_name:                Optional[str] = None
    client_contact_name:        Optional[str] = None
    client_contact_email:       Optional[str] = None
    existing_insurance:         List[Any] = []
    risk_appetite:              Optional[str] = None
    property_owned:             Optional[bool] = None
    has_employees:              Optional[bool] = None
    has_vehicles:               Optional[bool] = None
    has_professional_liability: Optional[bool] = None
    has_cyber_risk:             Optional[bool] = None
    annual_revenue_nok:         Optional[float] = None
    special_requirements:       Optional[str] = None
    recommended_products:       List[str] = []
    advisor_notes:              Optional[str] = None
    suitability_basis:          Optional[str] = None
    fee_basis:                  Optional[str] = None
    fee_amount_nok:             Optional[float] = None


class ConsentOut(BaseModel):
    id:                int
    orgnr:             str
    firm_id:           int
    created_at:        Optional[str] = None
    lawful_basis:      str
    purpose:           str
    captured_by_email: Optional[str] = None
    withdrawn_at:      Optional[str] = None
    withdrawal_reason: Optional[str] = None


# ── BRREG enrichment / company profile response models ────────────────────────
# These are the endpoint outputs the frontend reads heavily. Keeping these
# typed (instead of bare `dict`) means OpenAPI codegen produces accurate TS
# types and field-name typos fail at the backend instead of silently breaking
# the UI. See CLAUDE.md "Architecture Deviations" for context.

class BankruptcyOut(BaseModel):
    orgnr:                    str
    konkurs:                  bool = False
    under_konkursbehandling:  bool = False
    under_avvikling:          bool = False


class BoardMember(BaseModel):
    group:       Optional[str] = None
    role:        Optional[str] = None
    name:        Optional[str] = None
    birth_year:  Optional[int] = None
    deceased:    bool = False
    resigned:    bool = False


class BoardMembersOut(BaseModel):
    orgnr:   str
    members: List[BoardMember]


class LicenseItem(BaseModel):
    orgnr:                Optional[str]   = None
    name:                 Optional[str]   = None
    country:              Optional[str]   = None
    entity_type:          Optional[str]   = None
    license_id:           Optional[str]   = None
    license_type:         Optional[str]   = None
    license_status:       Optional[str]   = None
    license_from:         Optional[str]   = None
    license_to:           Optional[str]   = None
    license_description:  Optional[str]   = None


class LicensesOut(BaseModel):
    orgnr:    str
    licenses: List[LicenseItem]


class CoordinatesOut(BaseModel):
    lat: float
    lon: float


class KoordinaterOut(BaseModel):
    orgnr:       str
    coordinates: Optional[CoordinatesOut] = None


class StrukturParent(BaseModel):
    orgnr:             Optional[str] = None
    navn:              Optional[str] = None
    organisasjonsform: Optional[str] = None
    kommune:           Optional[str] = None


class StrukturSubUnit(BaseModel):
    orgnr:           Optional[str] = None
    navn:            Optional[str] = None
    kommune:         Optional[str] = None
    antall_ansatte:  Optional[int] = None


class StrukturOut(BaseModel):
    orgnr:           str
    parent:          Optional[StrukturParent]   = None
    sub_units:       List[StrukturSubUnit]      = Field(default_factory=list)
    total_sub_units: Optional[int]              = None


class BenchmarkOut(BaseModel):
    orgnr:     str
    nace_code: Optional[str]            = None
    benchmark: Dict[str, Any]           = Field(default_factory=dict)


class PeerMetric(BaseModel):
    company:    Optional[float] = None
    peer_avg:   Optional[float] = None
    percentile: Optional[int]   = None


class PeerBenchmarkMetrics(BaseModel):
    equity_ratio: PeerMetric
    revenue:      PeerMetric
    risk_score:   PeerMetric


class PeerBenchmarkOut(BaseModel):
    orgnr:        str
    nace_section: str
    peer_count:   int
    metrics:      PeerBenchmarkMetrics
    source:       Literal["db_peers", "ssb_ranges"]


class HistoryRowOut(BaseModel):
    """One year of financial history. Sparse — most fields are optional because
    BRREG-vs-PDF sources populate different subsets. The frontend expects
    these exact field names."""
    year:                 int
    source:               Optional[str]   = None
    currency:             Optional[str]   = None
    revenue:              Optional[float] = None
    arsresultat:          Optional[float] = None
    sumDriftsinntekter:   Optional[float] = None
    sumEgenkapital:       Optional[float] = None
    sumEiendeler:         Optional[float] = None
    total_assets:         Optional[float] = None
    equity_ratio:         Optional[float] = None
    antallAnsatte:        Optional[int]   = None
    antall_ansatte:       Optional[int]   = None
    sumKortsiktigGjeld:   Optional[float] = None
    sumLangsiktigGjeld:   Optional[float] = None

    model_config = {"extra": "allow"}  # PDF rows can carry many extra fields


class HistoryOut(BaseModel):
    orgnr: str
    years: List[HistoryRowOut]


class ExtractionStatusOut(BaseModel):
    orgnr:                 str
    status:                Literal["no_sources", "extracting", "no_data", "done"]
    source_years:          List[int]
    done_years:            List[int]
    pending_years:         List[int]
    missing_target_years:  List[int]


class PdfSourceItem(BaseModel):
    year:     int
    pdf_url:  str
    label:    Optional[str] = None
    added_at: Optional[Any] = None


class PdfSourcesOut(BaseModel):
    orgnr:   str
    sources: List[PdfSourceItem]


class EstimateOut(BaseModel):
    orgnr:     str
    estimated: Dict[str, Any] = Field(default_factory=dict)


class FinancialCommentaryOut(BaseModel):
    orgnr:      str
    commentary: str
    years:      Optional[List[int]] = None


class DeleteHistoryOut(BaseModel):
    orgnr:        str
    deleted_rows: int


class IngestKnowledgeOut(BaseModel):
    orgnr:         str
    chunks_stored: int


class KnowledgeStatsOut(BaseModel):
    total_chunks: int
    doc_chunks:   int
    video_chunks: int


class KnowledgeIndexOut(BaseModel):
    cleared_chunks:   Optional[int] = None
    total_new_chunks: int
    docs_chunks:      int
    video_chunks:     int


class SeededRegulationItem(BaseModel):
    name:   str
    status: str
    chunks: Optional[int] = None


class SeedRegulationsOut(BaseModel):
    seeded: List[SeededRegulationItem]
