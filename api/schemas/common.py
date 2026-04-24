"""Common request schemas used across multiple routers."""

from typing import List, Optional
from pydantic import BaseModel


class ChatRequest(BaseModel):
    question: str
    context: Optional[str] = None  # optional extra context injected by the caller


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


# Backward compat alias
_BrokerNoteBody = BrokerNoteBody
