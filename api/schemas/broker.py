"""Broker settings and SLA schemas."""
from typing import Any, Dict, Optional
from pydantic import BaseModel


class BrokerSettingsIn(BaseModel):
    firm_name: str
    orgnr: Optional[str] = None
    address: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None


class SlaIn(BaseModel):
    form_data: Dict[str, Any]


class UserRoleUpdate(BaseModel):
    role: str
