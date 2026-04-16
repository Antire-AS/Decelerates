"""Document schemas — chat, compare, keypoints, coverage analysis."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DocumentChatOut(BaseModel):
    doc_id: int
    question: str
    answer: str


class DocumentRef(BaseModel):
    id: int
    title: Optional[str] = None


class DocumentCompareOut(BaseModel):
    doc_a: DocumentRef
    doc_b: DocumentRef
    structured: Dict[str, Any] = Field(default_factory=dict)


class DocumentKeypointsOut(BaseModel):
    doc_id: int
    title: Optional[str] = None
    summary: Optional[str] = None
    key_points: List[str] = Field(default_factory=list)
    extracted_at: Optional[str] = None
    model_config = {"extra": "allow"}


class CoverageAnalysisOut(BaseModel):
    id: int
    orgnr: str
    title: str
    insurer: Optional[str] = None
    product_type: Optional[str] = None
    filename: Optional[str] = None
    coverage_data: Optional[Dict[str, Any]] = None
    premium_nok: Optional[float] = None
    deductible_nok: Optional[float] = None
    coverage_sum_nok: Optional[float] = None
    status: str
    created_at: datetime
