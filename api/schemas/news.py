"""News schemas — surface company_news rows to the frontend."""

from typing import List, Optional

from pydantic import BaseModel, Field


class CompanyNewsItem(BaseModel):
    id: int
    orgnr: str
    headline: str
    url: str
    source: Optional[str] = None
    published_at: Optional[str] = None
    snippet: Optional[str] = None
    summary: Optional[str] = None
    material: bool = False
    event_type: Optional[str] = None
    fetched_at: Optional[str] = None


class CompanyNewsOut(BaseModel):
    orgnr: str
    items: List[CompanyNewsItem] = Field(default_factory=list)


class CompanyNewsRefreshOut(BaseModel):
    orgnr: str
    added: int
