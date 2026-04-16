"""Email compose schemas."""
from pydantic import BaseModel


class EmailComposeIn(BaseModel):
    orgnr: str
    to: str
    subject: str
    body_html: str


class EmailComposeOut(BaseModel):
    sent: bool
    activity_id: int
