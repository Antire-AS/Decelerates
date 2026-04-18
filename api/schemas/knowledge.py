"""Knowledge base schemas."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class KnowledgeChatOut(BaseModel):
    question: str
    answer: str
    sources: List[str] = Field(default_factory=list)
    source_snippets: Dict[str, str] = Field(default_factory=dict)


class DeleteHistoryOut(BaseModel):
    orgnr: str
    deleted_rows: int


class IngestKnowledgeOut(BaseModel):
    orgnr: str
    chunks_stored: int


class KnowledgeStatsOut(BaseModel):
    total_chunks: int
    doc_chunks: int
    video_chunks: int


class KnowledgeIndexOut(BaseModel):
    cleared_chunks: Optional[int] = None
    total_new_chunks: int
    docs_chunks: int
    video_chunks: int


class SeededRegulationItem(BaseModel):
    name: str
    status: str
    chunks: Optional[int] = None


class SeedRegulationsOut(BaseModel):
    seeded: List[SeededRegulationItem]
