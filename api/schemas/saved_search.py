"""Saved search schemas."""

from datetime import datetime
from typing import Any, Dict
from pydantic import BaseModel, Field


class SavedSearchOut(BaseModel):
    id: int
    user_id: int
    name: str
    params: Dict[str, Any]
    created_at: datetime


class SavedSearchCreate(BaseModel):
    name: str
    params: Dict[str, Any] = Field(default_factory=dict)
