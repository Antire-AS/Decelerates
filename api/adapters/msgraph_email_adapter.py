"""Microsoft Graph email adapter — plan §🟢 #10.

Implements the EmailOutboundPort using MSAL client credentials flow against
the broker firm's Azure AD tenant. Sends through a service mailbox with the
`Mail.Send` application permission.

REQUIRES external setup before activation:
  1. Register an app in Azure AD with `Mail.Send` application permission
  2. Grant tenant-wide consent
  3. Provision a service mailbox (e.g. noreply@<broker-firm>.no)
  4. Set env vars in deploy.yml:
       AZURE_AD_TENANT_ID
       AZURE_AD_CLIENT_ID
       AZURE_AD_CLIENT_SECRET
       MS_GRAPH_SERVICE_MAILBOX
Until these are set, `is_configured()` returns False and the route returns
503 — no spurious failures during local dev or staging.

Phase 2 (deferred per plan): swap to MSAL on-behalf-of for "send as user"
delegated flow so emails appear in the broker's own Sent items folder.
"""

from dataclasses import dataclass
from typing import Optional

import httpx

from api.ports.driven.email_outbound_port import EmailOutboundPort


@dataclass(frozen=True)
class MsGraphConfig:
    """Frozen config — read once in api/main.py per the Antire convention.
    Empty strings are intentional sentinels (vs Optional[str]) so the
    is_configured() check is a simple `all(...)`."""

    tenant_id: str = ""
    client_id: str = ""
    client_secret: str = ""
    service_mailbox: str = ""


_GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_TOKEN_URL_TMPL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
_GRAPH_SCOPE = "https://graph.microsoft.com/.default"


class MsGraphEmailAdapter(EmailOutboundPort):
    def __init__(self, config: MsGraphConfig) -> None:
        self.config = config

    def is_configured(self) -> bool:
        c = self.config
        return bool(
            c.tenant_id and c.client_id and c.client_secret and c.service_mailbox
        )

    def send_email(
        self,
        to: str,
        subject: str,
        body_html: str,
        on_behalf_of_email: Optional[str] = None,  # noqa: ARG002 (Phase 2)
    ) -> str:
        if not self.is_configured():
            raise RuntimeError(
                "MS Graph email is not configured (missing AZURE_AD_* env vars)"
            )
        token = self._fetch_token()
        return self._post_send_mail(token, to, subject, body_html)

    def _fetch_token(self) -> str:
        """MSAL client credentials grant — single POST, no library required."""
        token_url = _TOKEN_URL_TMPL.format(tenant=self.config.tenant_id)
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                token_url,
                data={
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                    "scope": _GRAPH_SCOPE,
                    "grant_type": "client_credentials",
                },
            )
        resp.raise_for_status()
        return resp.json()["access_token"]

    def _post_send_mail(self, token: str, to: str, subject: str, body_html: str) -> str:
        url = f"{_GRAPH_BASE}/users/{self.config.service_mailbox}/sendMail"
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": body_html},
                "toRecipients": [{"emailAddress": {"address": to}}],
            },
            "saveToSentItems": True,
        }
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
        resp.raise_for_status()
        # Graph sendMail returns 202 Accepted with no body. There's no
        # message id surfaced — return empty string and rely on the broker's
        # Sent items for audit. Phase 2 will use createMessage + send pattern
        # which DOES return a message id.
        return ""
