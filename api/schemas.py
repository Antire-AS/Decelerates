from datetime import date, datetime
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
    activity_type:       str
    subject:             str
    body:                Optional[str] = None
    policy_id:           Optional[int] = None
    claim_id:            Optional[int] = None
    due_date:            Optional[date] = None
    completed:           bool = False
    assigned_to_user_id: Optional[int] = None  # plan §🟢 #14


class ActivityUpdate(BaseModel):
    subject:             Optional[str] = None
    body:                Optional[str] = None
    due_date:            Optional[date] = None
    completed:           Optional[bool] = None
    assigned_to_user_id: Optional[int] = None  # plan §🟢 #14


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


class PdfHistoryOut(BaseModel):
    """Response from POST /org/{orgnr}/pdf-history — single extracted year row."""
    orgnr:     str
    extracted: Dict[str, Any] = Field(default_factory=dict)


class OrgChatOut(BaseModel):
    """Response from POST /org/{orgnr}/chat — RAG/notes-grounded answer."""
    orgnr:      str
    question:   str
    answer:     str
    session_id: str


class DocumentChatOut(BaseModel):
    """Response from POST /insurance-documents/{doc_id}/chat."""
    doc_id:   int
    question: str
    answer:   str


class DocumentRef(BaseModel):
    id:    int
    title: Optional[str] = None


class DocumentCompareOut(BaseModel):
    """Response from POST /insurance-documents/compare. The `structured` payload
    is the LLM JSON output from compare_two_documents — kept loose so the LLM
    schema can evolve without breaking the wrapper."""
    doc_a:      DocumentRef
    doc_b:      DocumentRef
    structured: Dict[str, Any] = Field(default_factory=dict)


class DocumentKeypointsOut(BaseModel):
    """Response from GET /insurance-documents/{doc_id}/keypoints."""
    doc_id:        int
    title:         Optional[str] = None
    summary:       Optional[str] = None
    key_points:    List[str] = Field(default_factory=list)
    extracted_at:  Optional[str] = None
    # Allow forward-compatible LLM fields without breaking the wrapper.
    model_config  = {"extra": "allow"}


class EstimateOut(BaseModel):
    orgnr:     str
    estimated: Dict[str, Any] = Field(default_factory=dict)


class FinancialCommentaryOut(BaseModel):
    orgnr:      str
    commentary: str
    years:      Optional[List[int]] = None


class RiskOfferRecommendation(BaseModel):
    type:            Optional[str] = None
    anbefalt_sum:    Optional[str] = None
    prioritet:       Optional[str] = None
    begrunnelse:     Optional[str] = None
    estimert_premie: Optional[str] = None


class RiskOfferOut(BaseModel):
    orgnr:               str
    navn:                Optional[str] = None
    risk_score:          Optional[int] = None
    risk_factors:        List[str] = Field(default_factory=list)
    sammendrag:          Optional[str] = None
    anbefalinger:        List[RiskOfferRecommendation] = Field(default_factory=list)
    total_premieanslag:  Optional[str] = None


class NarrativeOut(BaseModel):
    orgnr:     str
    narrative: str


class KnowledgeChatOut(BaseModel):
    question:        str
    answer:          str
    sources:         List[str] = Field(default_factory=list)
    source_snippets: Dict[str, str] = Field(default_factory=dict)


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


# ── Deal pipeline (plan §🟢 #9) ──────────────────────────────────────────────
# Convention: every endpoint declares response_model. See plan risk #1
# ("Type erosion in new endpoints").

PipelineStageKindLiteral = Literal["lead", "qualified", "quoted", "bound", "won", "lost"]


class PipelineStageOut(BaseModel):
    """A column in a broker firm's deal pipeline kanban board."""
    id:          int
    firm_id:     int
    name:        str
    kind:        PipelineStageKindLiteral
    order_index: int
    color:       Optional[str] = None
    created_at:  datetime


class PipelineStageCreate(BaseModel):
    name:        str
    kind:        PipelineStageKindLiteral
    order_index: int = 0
    color:       Optional[str] = None


class PipelineStageUpdate(BaseModel):
    name:        Optional[str] = None
    order_index: Optional[int] = None
    color:       Optional[str] = None


class DealOut(BaseModel):
    id:                   int
    firm_id:              int
    orgnr:                str
    stage_id:             int
    owner_user_id:        Optional[int] = None
    title:                Optional[str] = None
    expected_premium_nok: Optional[float] = None
    expected_close_date:  Optional[date] = None
    source:               Optional[str] = None
    notes:                Optional[str] = None
    created_at:           datetime
    updated_at:           datetime
    won_at:               Optional[datetime] = None
    lost_at:              Optional[datetime] = None
    lost_reason:          Optional[str] = None


class DealCreate(BaseModel):
    orgnr:                str
    stage_id:             int
    owner_user_id:        Optional[int] = None
    title:                Optional[str] = None
    expected_premium_nok: Optional[float] = None
    expected_close_date:  Optional[date] = None
    source:               Optional[str] = None
    notes:                Optional[str] = None


class DealUpdate(BaseModel):
    """Generic patch — every field optional. Stage transitions go through
    PATCH /deals/{id}/stage instead so they're auditable as a single op."""
    title:                Optional[str] = None
    owner_user_id:        Optional[int] = None
    expected_premium_nok: Optional[float] = None
    expected_close_date:  Optional[date] = None
    source:               Optional[str] = None
    notes:                Optional[str] = None


class DealStageChange(BaseModel):
    stage_id: int


class DealLose(BaseModel):
    reason: Optional[str] = None


# ── Notifications inbox (plan §🟢 #17) ───────────────────────────────────────

NotificationKindLiteral = Literal[
    "renewal",
    "activity_overdue",
    "mention",
    "claim_new",
    "deal_won",
    "coverage_gap",
    "digest",
]


class NotificationOut(BaseModel):
    id:         int
    user_id:    int
    firm_id:    int
    orgnr:      Optional[str] = None
    kind:       NotificationKindLiteral
    title:      str
    message:    Optional[str] = None
    link:       Optional[str] = None
    read:       bool
    created_at: datetime


class NotificationListOut(BaseModel):
    """Wrapper that ships the unread count alongside the rows so the bell icon
    can render `15 unread` without a second round-trip."""
    items:        List[NotificationOut]
    unread_count: int


class NotificationMarkReadOut(BaseModel):
    updated: int


# ── Audit log UI (plan §🟢 #13) ──────────────────────────────────────────────


class AuditLogEntryOut(BaseModel):
    id:          int
    orgnr:       Optional[str] = None
    action:      str
    actor_email: Optional[str] = None
    detail:      Optional[str] = None       # JSON-encoded extras
    created_at:  datetime


class AuditLogPageOut(BaseModel):
    """Paginated audit log response. `total` is the count of rows matching the
    filter (NOT the page); `has_more` is True when more rows exist past `offset
    + items.length`. The frontend uses these to render the 'Page 2 of N' UI."""
    items:    List[AuditLogEntryOut]
    total:    int
    offset:   int
    limit:    int
    has_more: bool


# ── Commission forward projections (plan §🟢 #12) ───────────────────────────


class CommissionProjectionBucket(BaseModel):
    period:              str    # "2026-Q3"
    expected_commission: float
    policy_count:        int


class CommissionProjectionsOut(BaseModel):
    buckets:      List[CommissionProjectionBucket]
    months_ahead: int


# ── Bulk operations (plan §🟢 #18) ───────────────────────────────────────────


class PortfolioBulkAdd(BaseModel):
    orgnrs: List[str]


class PortfolioBulkAddOut(BaseModel):
    added:   int
    skipped: int


class ActivityBulkComplete(BaseModel):
    activity_ids: List[int]


class ActivityBulkCompleteOut(BaseModel):
    updated: int


# ── Saved searches (plan §🟢 #19) ────────────────────────────────────────────


class SavedSearchOut(BaseModel):
    id:         int
    user_id:    int
    name:       str
    params:     Dict[str, Any]
    created_at: datetime


class SavedSearchCreate(BaseModel):
    name:   str
    params: Dict[str, Any] = Field(default_factory=dict)


# ── Email compose (plan §🟢 #10) ─────────────────────────────────────────────


class EmailComposeIn(BaseModel):
    orgnr:     str
    to:        str
    subject:   str
    body_html: str


class EmailComposeOut(BaseModel):
    sent:        bool
    activity_id: int


# ── Signicat e-sign (plan §🟢 #11) ───────────────────────────────────────────


class SigningSessionOut(BaseModel):
    session_id:  str
    signing_url: str


class SignicatWebhookAck(BaseModel):
    received: bool


# ── Coverage Analysis ────────────────────────────────────────────────────────


class CoverageAnalysisOut(BaseModel):
    id:               int
    orgnr:            str
    title:            str
    insurer:          Optional[str] = None
    product_type:     Optional[str] = None
    filename:         Optional[str] = None
    coverage_data:    Optional[Dict[str, Any]] = None
    premium_nok:      Optional[float] = None
    deductible_nok:   Optional[float] = None
    coverage_sum_nok: Optional[float] = None
    status:           str
    created_at:       datetime


# ── Tenders ──────────────────────────────────────────────────────────────────


TenderStatusLiteral = Literal["draft", "sent", "closed", "analysed"]
TenderRecipientStatusLiteral = Literal["pending", "sent", "received", "declined"]


class TenderRecipientIn(BaseModel):
    insurer_name:  str
    insurer_email: Optional[str] = None


class TenderCreate(BaseModel):
    orgnr:         str
    title:         str
    product_types: List[str]
    deadline:      Optional[date] = None
    notes:         Optional[str] = None
    recipients:    List[TenderRecipientIn] = Field(default_factory=list)


class TenderUpdate(BaseModel):
    title:         Optional[str] = None
    product_types: Optional[List[str]] = None
    deadline:      Optional[date] = None
    notes:         Optional[str] = None
    status:        Optional[TenderStatusLiteral] = None


class TenderRecipientOut(BaseModel):
    id:            int
    tender_id:     int
    insurer_name:  str
    insurer_email: Optional[str] = None
    status:        TenderRecipientStatusLiteral
    sent_at:       Optional[datetime] = None
    response_at:   Optional[datetime] = None


class TenderOfferOut(BaseModel):
    id:             int
    tender_id:      int
    recipient_id:   Optional[int] = None
    insurer_name:   str
    filename:       str
    extracted_data: Optional[Dict[str, Any]] = None
    uploaded_at:    datetime


class TenderOut(BaseModel):
    id:               int
    orgnr:            str
    title:            str
    product_types:    List[str] = Field(default_factory=list)
    deadline:         Optional[date] = None
    notes:            Optional[str] = None
    status:           TenderStatusLiteral
    analysis_result:  Optional[Dict[str, Any]] = None
    recipients:       List[TenderRecipientOut] = Field(default_factory=list)
    offers:           List[TenderOfferOut] = Field(default_factory=list)
    created_by_email: Optional[str] = None
    created_at:       datetime


class TenderListOut(BaseModel):
    id:            int
    orgnr:         str
    title:         str
    product_types: List[str] = Field(default_factory=list)
    deadline:      Optional[date] = None
    status:        TenderStatusLiteral
    recipient_count: int = 0
    offer_count:     int = 0
    created_at:      datetime


class TenderAnalysisOut(BaseModel):
    tender_id: int
    analysis:  Dict[str, Any]
