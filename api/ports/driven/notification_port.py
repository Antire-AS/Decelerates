"""Port (driven) — abstract interface for email notifications."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class EmailAttachment:
    """One file attached to an outbound email.

    `content` is the raw bytes of the file; the adapter handles whatever
    encoding the underlying provider expects (ACS wants base64). Kept
    provider-agnostic so future migrations don't need port changes."""

    filename: str
    content_type: str  # e.g. "application/pdf"
    content: bytes


class NotificationPort(ABC):
    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    def send_email(self, to: str, subject: str, body_html: str) -> bool: ...

    @abstractmethod
    def send_email_with_attachments(
        self,
        to: str,
        subject: str,
        body_html: str,
        attachments: List[EmailAttachment],
        cc: Optional[List[str]] = None,
    ) -> bool:
        """Send an email with one or more attached files.

        Returns True on successful queue-for-delivery (provider-level ack),
        not on recipient delivery. `attachments` may be empty — in which
        case this is equivalent to `send_email` with optional cc."""

    @abstractmethod
    def send_sla_generated(self, to: str, client_navn: str) -> bool: ...

    @abstractmethod
    def send_risk_report_ready(self, to: str, orgnr: str, navn: str) -> bool: ...

    @abstractmethod
    def send_portfolio_digest(
        self, to: str, portfolio_name: str, alerts: list[dict]
    ) -> bool: ...

    @abstractmethod
    def send_renewal_digest(self, to: str, renewals: list[dict]) -> bool: ...

    @abstractmethod
    def send_activity_reminders(
        self, to: str, overdue: list[dict], due_today: list[dict]
    ) -> bool: ...

    @abstractmethod
    def send_forsikringstilbud(
        self, to: str, client_navn: str, orgnr: str, share_url: str
    ) -> bool: ...

    @abstractmethod
    def send_renewal_stage_change(
        self, to: str, policy_number: str, insurer: str, product_type: str, stage: str
    ) -> bool: ...

    @abstractmethod
    def send_renewal_threshold_emails(
        self, to: str, threshold_days: int, policies: list[dict]
    ) -> bool: ...
