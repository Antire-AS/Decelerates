"""Company domain schemas — org profile, history, board, coordinates, benchmarks."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class BankruptcyOut(BaseModel):
    orgnr: str
    konkurs: bool = False
    under_konkursbehandling: bool = False
    under_avvikling: bool = False


class BoardMember(BaseModel):
    group: Optional[str] = None
    role: Optional[str] = None
    name: Optional[str] = None
    birth_year: Optional[int] = None
    deceased: bool = False
    resigned: bool = False


class BoardMembersOut(BaseModel):
    orgnr: str
    members: List[BoardMember]


class LicenseItem(BaseModel):
    orgnr: Optional[str] = None
    name: Optional[str] = None
    country: Optional[str] = None
    entity_type: Optional[str] = None
    license_id: Optional[str] = None
    license_type: Optional[str] = None
    license_status: Optional[str] = None
    license_from: Optional[str] = None
    license_to: Optional[str] = None
    license_description: Optional[str] = None


class LicensesOut(BaseModel):
    orgnr: str
    licenses: List[LicenseItem]


class CoordinatesOut(BaseModel):
    lat: float
    lon: float


class KoordinaterOut(BaseModel):
    orgnr: str
    coordinates: Optional[CoordinatesOut] = None


class StrukturParent(BaseModel):
    orgnr: Optional[str] = None
    navn: Optional[str] = None
    organisasjonsform: Optional[str] = None
    kommune: Optional[str] = None


class StrukturSubUnit(BaseModel):
    orgnr: Optional[str] = None
    navn: Optional[str] = None
    kommune: Optional[str] = None
    antall_ansatte: Optional[int] = None


class StrukturOut(BaseModel):
    orgnr: str
    parent: Optional[StrukturParent] = None
    sub_units: List[StrukturSubUnit] = Field(default_factory=list)
    total_sub_units: Optional[int] = None


class BenchmarkOut(BaseModel):
    orgnr: str
    nace_code: Optional[str] = None
    benchmark: Dict[str, Any] = Field(default_factory=dict)


class PeerMetric(BaseModel):
    company: Optional[float] = None
    peer_avg: Optional[float] = None
    percentile: Optional[int] = None


class PeerBenchmarkMetrics(BaseModel):
    equity_ratio: PeerMetric
    revenue: PeerMetric
    risk_score: PeerMetric


class PeerBenchmarkOut(BaseModel):
    orgnr: str
    nace_section: str
    peer_count: int
    metrics: PeerBenchmarkMetrics
    source: Literal["db_peers", "ssb_ranges"]


class HistoryRowOut(BaseModel):
    year: int
    source: Optional[str] = None
    currency: Optional[str] = None
    revenue: Optional[float] = None
    arsresultat: Optional[float] = None
    sumDriftsinntekter: Optional[float] = None
    sumEgenkapital: Optional[float] = None
    sumEiendeler: Optional[float] = None
    total_assets: Optional[float] = None
    equity_ratio: Optional[float] = None
    antallAnsatte: Optional[int] = None
    antall_ansatte: Optional[int] = None
    sumKortsiktigGjeld: Optional[float] = None
    sumLangsiktigGjeld: Optional[float] = None
    model_config = {"extra": "allow"}


class HistoryOut(BaseModel):
    orgnr: str
    years: List[HistoryRowOut]


class ExtractionStatusOut(BaseModel):
    orgnr: str
    status: Literal["no_sources", "extracting", "no_data", "done"]
    source_years: List[int]
    done_years: List[int]
    pending_years: List[int]
    missing_target_years: List[int]


class PdfSourceItem(BaseModel):
    year: int
    pdf_url: str
    label: Optional[str] = None
    added_at: Optional[Any] = None


class PdfSourcesOut(BaseModel):
    orgnr: str
    sources: List[PdfSourceItem]


class PdfHistoryOut(BaseModel):
    orgnr: str
    extracted: Dict[str, Any] = Field(default_factory=dict)


class OrgChatOut(BaseModel):
    orgnr: str
    question: str
    answer: str
    session_id: str


class EstimateOut(BaseModel):
    orgnr: str
    estimated: Dict[str, Any] = Field(default_factory=dict)


class FinancialCommentaryOut(BaseModel):
    orgnr: str
    commentary: str
    years: Optional[List[int]] = None
