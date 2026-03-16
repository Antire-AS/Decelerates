from typing import Any, Dict, List, Optional
from pydantic import BaseModel


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
