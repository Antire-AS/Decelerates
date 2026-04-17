"""Portfolio schemas."""

from typing import List, Optional
from pydantic import BaseModel


class PortfolioCreate(BaseModel):
    name: str
    description: Optional[str] = ""


class PortfolioAddCompany(BaseModel):
    orgnr: str


class PortfolioBulkAdd(BaseModel):
    orgnrs: List[str]


class PortfolioBulkAddOut(BaseModel):
    added: int
    skipped: int


class ActivityBulkComplete(BaseModel):
    activity_ids: List[int]


class ActivityBulkCompleteOut(BaseModel):
    updated: int
