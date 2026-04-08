"""Signicat e-sign integration — plan §🟢 #11.

Direct httpx calls against Signicat's REST API. Webhook signature verification
is HMAC-SHA256 over the raw body, comparing against the X-Signicat-Signature
header. Invalid signatures return 401 — never trust an unsigned webhook.

REQUIRES external setup before activation:
  1. Signicat account + REST API key
  2. Webhook secret shared between Signicat and our app
  3. Set env vars in deploy.yml:
       SIGNICAT_API_BASE       (e.g. https://api.signicat.com/eid)
       SIGNICAT_API_KEY
       SIGNICAT_WEBHOOK_SECRET
       SIGNICAT_WEBHOOK_URL    (the public URL of POST /webhooks/signicat)

Until these are set, `is_configured()` returns False and the route returns 503.
"""
import hashlib
import hmac
import os
from dataclasses import dataclass
from typing import Optional

import httpx


@dataclass(frozen=True)
class SignicatConfig:
    api_base:        str = ""
    api_key:         str = ""
    webhook_secret:  str = ""
    webhook_url:     str = ""


class SignicatService:
    def __init__(self, config: Optional[SignicatConfig] = None) -> None:
        # Allows the route to construct one with defaults from env without
        # plumbing through the DI container — Signicat is single-purpose enough
        # that a port+adapter abstraction would be over-engineering for v1.
        self.config = config or _config_from_env()

    def is_configured(self) -> bool:
        c = self.config
        return bool(c.api_base and c.api_key and c.webhook_secret)

    def create_signing_session(
        self,
        pdf_bytes: bytes,
        signer_email: str,
        signer_name: str,
        document_title: str,
    ) -> dict:
        """Create a Signicat signing session for the given PDF. Returns
        {"session_id": ..., "signing_url": ...}. Raises on Signicat REST
        failures so the route returns a real 5xx."""
        if not self.is_configured():
            raise RuntimeError("Signicat is not configured (missing SIGNICAT_* env vars)")
        payload = self._build_session_payload(pdf_bytes, signer_email, signer_name, document_title)
        url = f"{self.config.api_base.rstrip('/')}/sessions"
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
            )
        resp.raise_for_status()
        body = resp.json()
        return {
            "session_id":  body.get("session_id") or body.get("id", ""),
            "signing_url": body.get("signing_url") or body.get("url", ""),
        }

    def _build_session_payload(
        self,
        pdf_bytes: bytes,
        signer_email: str,
        signer_name: str,
        document_title: str,
    ) -> dict:
        """Build the Signicat sessions POST body. Extracted so create_signing_session
        stays under the 40-line limit and so the payload shape is testable in
        isolation once we have a real Signicat sandbox to align against."""
        return {
            "document": {
                "title": document_title,
                "content_base64": _b64(pdf_bytes),
                "mime_type": "application/pdf",
            },
            "signer": {
                "email": signer_email,
                "name": signer_name,
            },
            "callback_url": self.config.webhook_url,
            "redirect_url": None,
        }

    def verify_webhook(self, raw_body: bytes, signature_header: str) -> bool:
        """Verify HMAC-SHA256 signature on a webhook delivery. Returns False
        rather than raising so the route can return a clean 401."""
        if not self.config.webhook_secret or not signature_header:
            return False
        expected = hmac.new(
            self.config.webhook_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        # Constant-time comparison — never use `==` on an HMAC.
        return hmac.compare_digest(expected, signature_header.strip())

    def parse_webhook(self, payload: dict) -> dict:
        """Extract the bits we care about from a Signicat webhook body.
        Field names are guesses based on common Signicat shapes — finalise
        once we have a real test event."""
        return {
            "session_id":     payload.get("session_id") or payload.get("id", ""),
            "status":         payload.get("status", ""),
            "signed_pdf_url": payload.get("signed_pdf_url") or payload.get("document_url"),
            "signed_at":      payload.get("signed_at"),
        }


def _config_from_env() -> SignicatConfig:
    return SignicatConfig(
        api_base=os.getenv("SIGNICAT_API_BASE", ""),
        api_key=os.getenv("SIGNICAT_API_KEY", ""),
        webhook_secret=os.getenv("SIGNICAT_WEBHOOK_SECRET", ""),
        webhook_url=os.getenv("SIGNICAT_WEBHOOK_URL", ""),
    )


def _b64(data: bytes) -> str:
    import base64
    return base64.b64encode(data).decode("ascii")
