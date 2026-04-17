"""Signicat e-sign integration — OAuth2 client credentials flow.

Uses Signicat's Sign API v2 to create document signing sessions.
Auth is OAuth2 client_credentials: client_id + client_secret → access token.

Sandbox:  SIGNICAT_API_BASE = https://api.signicat.io
Prod:     SIGNICAT_API_BASE = https://api.signicat.com

Env vars:
  SIGNICAT_API_BASE         (e.g. https://api.signicat.io)
  SIGNICAT_CLIENT_ID        (e.g. sandbox-stout-tree-619)
  SIGNICAT_CLIENT_SECRET    (the OAuth2 client secret)
  SIGNICAT_WEBHOOK_SECRET   (optional — for webhook HMAC verification)
  SIGNICAT_WEBHOOK_URL      (optional — public URL of POST /webhooks/signicat)
"""

import hashlib
import hmac
import logging
import os
from dataclasses import dataclass
from typing import Optional

import httpx

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SignicatConfig:
    api_base: str = ""
    client_id: str = ""
    client_secret: str = ""
    webhook_secret: str = ""
    webhook_url: str = ""


class SignicatService:
    def __init__(self, config: Optional[SignicatConfig] = None) -> None:
        self.config = config or _config_from_env()
        self._access_token: Optional[str] = None

    def is_configured(self) -> bool:
        c = self.config
        return bool(c.api_base and c.client_id and c.client_secret)

    def _get_access_token(self) -> str:
        """Obtain an OAuth2 access token via client_credentials grant."""
        if self._access_token:
            return self._access_token
        url = f"{self.config.api_base.rstrip('/')}/oauth/connect/token"
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                    "scope": "signicat-api",
                },
            )
        resp.raise_for_status()
        self._access_token = resp.json()["access_token"]
        return self._access_token

    def _auth_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json",
        }

    def create_signing_session(
        self,
        pdf_bytes: bytes,
        signer_email: str,
        signer_name: str,
        document_title: str,
    ) -> dict:
        """Create a Signicat signing session. Returns {session_id, signing_url}."""
        if not self.is_configured():
            raise RuntimeError("Signicat not configured (missing SIGNICAT_* env vars)")
        payload = self._build_session_payload(
            pdf_bytes,
            signer_email,
            signer_name,
            document_title,
        )
        url = f"{self.config.api_base.rstrip('/')}/signing/v2/sessions"
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(url, json=payload, headers=self._auth_headers())
        resp.raise_for_status()
        body = resp.json()
        return {
            "session_id": body.get("sessionId") or body.get("id", ""),
            "signing_url": body.get("signingUrl") or body.get("url", ""),
        }

    def _build_session_payload(
        self,
        pdf_bytes: bytes,
        signer_email: str,
        signer_name: str,
        document_title: str,
    ) -> dict:
        """Build the Signicat Sign API v2 session body."""
        payload: dict = {
            "title": document_title,
            "signers": [
                {
                    "externalSignerId": signer_email,
                    "signerInfo": {
                        "firstName": signer_name.split()[0] if signer_name else "",
                        "lastName": " ".join(signer_name.split()[1:])
                        if signer_name
                        else "",
                        "email": signer_email,
                    },
                    "signatureType": {"mechanism": "pkisignature"},
                }
            ],
            "dataToSign": {
                "title": document_title,
                "base64Content": _b64(pdf_bytes),
                "fileName": f"{document_title}.pdf",
            },
        }
        if self.config.webhook_url:
            payload["notification"] = {
                "webhook": {"url": self.config.webhook_url},
            }
        return payload

    def verify_webhook(self, raw_body: bytes, signature_header: str) -> bool:
        """Verify HMAC-SHA256 on a webhook delivery. Returns False on mismatch."""
        if not self.config.webhook_secret or not signature_header:
            return False
        expected = hmac.new(
            self.config.webhook_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature_header.strip())

    def parse_webhook(self, payload: dict) -> dict:
        """Extract signing status from a Signicat webhook body."""
        return {
            "session_id": payload.get("sessionId") or payload.get("id", ""),
            "status": payload.get("sessionStatus", ""),
            "signed_pdf_url": payload.get("documentUrl"),
            "signed_at": payload.get("completedTime"),
        }


def _config_from_env() -> SignicatConfig:
    return SignicatConfig(
        api_base=os.getenv("SIGNICAT_API_BASE", ""),
        client_id=os.getenv("SIGNICAT_CLIENT_ID", ""),
        client_secret=os.getenv("SIGNICAT_CLIENT_SECRET", ""),
        webhook_secret=os.getenv("SIGNICAT_WEBHOOK_SECRET", ""),
        webhook_url=os.getenv("SIGNICAT_WEBHOOK_URL", ""),
    )


def _b64(data: bytes) -> str:
    import base64

    return base64.b64encode(data).decode("ascii")
