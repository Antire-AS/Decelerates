"""Email compose + anbudspakke-email schemas."""

import re
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class EmailComposeIn(BaseModel):
    orgnr: str
    to: str
    subject: str
    body_html: str


class EmailComposeOut(BaseModel):
    sent: bool
    activity_id: int


# Simple RFC-5322-ish email regex — full validation lives in the ACS SDK
# at send time. We just want obvious-garbage rejection at the API boundary
# without pulling in the `email-validator` optional dep for `EmailStr`.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email(value: str) -> str:
    value = (value or "").strip()
    if not _EMAIL_RE.match(value):
        raise ValueError(f"Invalid email address: {value!r}")
    return value


class AnbudspakkeEmailRequest(BaseModel):
    """Body for POST /org/{orgnr}/anbudspakke/email.

    `subject` is optional — a sensible default is derived from the
    company name if omitted. `message` is optional free-text the broker
    wants prefixed to the standard email body. `cc` lets the broker
    loop in colleagues or the client."""

    to: str
    subject: Optional[str] = None
    message: Optional[str] = None
    cc: List[str] = Field(default_factory=list)

    @field_validator("to")
    @classmethod
    def _check_to(cls, v: str) -> str:
        return _validate_email(v)

    @field_validator("cc")
    @classmethod
    def _check_cc(cls, v: List[str]) -> List[str]:
        return [_validate_email(addr) for addr in v]


class AnbudspakkeEmailOut(BaseModel):
    sent: bool
    to: str
    subject: str
