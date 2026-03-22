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
