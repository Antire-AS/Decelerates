"""Port (driven) — abstract interface for email notifications."""
from abc import ABC, abstractmethod


class NotificationPort(ABC):
    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    def send_email(self, to: str, subject: str, body_html: str) -> bool: ...

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
