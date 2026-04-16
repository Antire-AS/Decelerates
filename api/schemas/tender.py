"""Tender (anbud) schemas."""
from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

TenderStatusLiteral = Literal["draft", "sent", "closed", "analysed"]
TenderRecipientStatusLiteral = Literal["pending", "sent", "received", "declined"]


class TenderRecipientIn(BaseModel):
    insurer_name: str
    insurer_email: Optional[str] = None


class TenderCreate(BaseModel):
    orgnr: str
    title: str
    product_types: List[str]
    deadline: Optional[date] = None
    notes: Optional[str] = None
    recipients: List[TenderRecipientIn] = Field(default_factory=list)


class TenderUpdate(BaseModel):
    title: Optional[str] = None
    product_types: Optional[List[str]] = None
    deadline: Optional[date] = None
    notes: Optional[str] = None
    status: Optional[TenderStatusLiteral] = None


class TenderRecipientOut(BaseModel):
    id: int
    tender_id: int
    insurer_name: str
    insurer_email: Optional[str] = None
    status: TenderRecipientStatusLiteral
    sent_at: Optional[datetime] = None
    response_at: Optional[datetime] = None


class TenderOfferOut(BaseModel):
    id: int
    tender_id: int
    recipient_id: Optional[int] = None
    insurer_name: str
    filename: str
    extracted_data: Optional[Dict[str, Any]] = None
    uploaded_at: datetime


class TenderOut(BaseModel):
    id: int
    orgnr: str
    title: str
    product_types: List[str] = Field(default_factory=list)
    deadline: Optional[date] = None
    notes: Optional[str] = None
    status: TenderStatusLiteral
    analysis_result: Optional[Dict[str, Any]] = None
    recipients: List[TenderRecipientOut] = Field(default_factory=list)
    offers: List[TenderOfferOut] = Field(default_factory=list)
    created_by_email: Optional[str] = None
    created_at: datetime


class TenderListOut(BaseModel):
    id: int
    orgnr: str
    title: str
    product_types: List[str] = Field(default_factory=list)
    deadline: Optional[date] = None
    status: TenderStatusLiteral
    recipient_count: int = 0
    offer_count: int = 0
    created_at: datetime


class TenderAnalysisOut(BaseModel):
    tender_id: int
    analysis: Dict[str, Any]
