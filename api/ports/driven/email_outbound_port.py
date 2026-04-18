"""Port (driven) — outbound email send via Microsoft Graph (plan §🟢 #10).

Distinct from `notification_port` which is the legacy ACS-based event email
port (cron digests etc.). This port is for the broker-composes-and-sends
flow: a real human-authored message to a real client recipient, sent through
the broker firm's MS 365 tenant.
"""

from abc import ABC, abstractmethod
from typing import Optional


class EmailOutboundPort(ABC):
    @abstractmethod
    def is_configured(self) -> bool:
        """True only if all four AZURE_AD_* env vars + service mailbox are set."""

    @abstractmethod
    def send_email(
        self,
        to: str,
        subject: str,
        body_html: str,
        on_behalf_of_email: Optional[str] = None,
    ) -> str:
        """Send an HTML email via Microsoft Graph.

        Returns the Graph message id (or empty string on failure). Raises
        on auth/network failures so the caller can decide whether to retry.
        `on_behalf_of_email` is reserved for the Phase 2 delegated flow —
        the current implementation always sends from the service mailbox.
        """
