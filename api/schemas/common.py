"""Common request schemas used across multiple routers."""

from typing import List
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


class BrokerNoteBody(BaseModel):
    text: str


class TenderChatRequest(BaseModel):
    question: str
    tender_context: Optional[str] = None
    session_id: Optional[int] = None
    pre_thinking: Optional[str] = None  # thinking from pass 1, skip re-generation


# Backward compat alias
_BrokerNoteBody = BrokerNoteBody
