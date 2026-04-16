"""DocuSeal e-sign integration — open-source alternative to Signicat (plan §🟢 #11).

DocuSeal (https://www.docuseal.com) is an open-source DocuSign clone. It provides
AdES (Advanced Electronic Signature) via email + audit trail — sufficient for
broker recommendation letters under eIDAS Article 25. It does NOT provide
BankID/QES; if your compliance team requires a qualified electronic signature
linked to a Norwegian national ID, use SignicatService or Criipto instead.

PUBLIC INTERFACE matches SignicatService 1:1 — drop-in via the
`get_signing_service()` factory in this module. Switch providers with the
`ESIGN_PROVIDER` env var.

REQUIRES external setup before activation:

  Option A — DocuSeal Cloud (zero ops, paid above free tier):
    1. Sign up at https://www.docuseal.com (free tier: ~3 docs/month)
    2. Get API key from Settings → API
    3. Configure a webhook in Settings → Webhooks pointing to /webhooks/docuseal
    4. Note the webhook secret DocuSeal generates
    5. Set env vars on ca-api:
         ESIGN_PROVIDER=docuseal
         DOCUSEAL_API_BASE=https://api.docuseal.com
         DOCUSEAL_API_KEY=<from portal>
         DOCUSEAL_WEBHOOK_SECRET=<from webhook config>
         DOCUSEAL_WEBHOOK_URL=https://ca-api.../webhooks/docuseal

  Option B — Self-hosted (zero per-signature cost):
    1. Run as a Container App sidecar in rg-broker-accelerator-prod:
         az containerapp create --name ca-docuseal --resource-group rg-broker-accelerator-prod \\
           --environment cae-broker-accelerator-prod --image docuseal/docuseal:latest \\
           --target-port 3000 --ingress external
    2. Open the deployed URL in a browser → create admin user
    3. Generate API key in Settings → API
    4. Configure webhook → copy the secret
    5. Set the same DOCUSEAL_* env vars on ca-api, with DOCUSEAL_API_BASE pointing
       to the new ca-docuseal FQDN.

Until env vars are set, `is_configured()` returns False and the route returns 503.
"""
import base64
import hashlib
import hmac
import os
from dataclasses import dataclass
from typing import Optional

import httpx
import logging

logger = logging.getLogger(__name__)



@dataclass(frozen=True)
class DocuSealConfig:
    """Frozen config — read once in api/main.py per the Antire convention.
    Empty strings are intentional sentinels (vs Optional[str]) so the
    is_configured() check is a simple `all(...)`."""
    api_base:        str = ""
    api_key:         str = ""
    webhook_secret:  str = ""
    webhook_url:     str = ""


class DocuSealService:
    """Drop-in alternative to SignicatService with the same public interface.

    Routers should call `get_signing_service()` from this module rather than
    instantiating either provider directly — that keeps the swap to a single
    env var change.
    """

    def __init__(self, config: Optional[DocuSealConfig] = None) -> None:
        # Same convention as SignicatService — single-purpose service, no
        # port+adapter abstraction needed for v1.
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
        """Create a DocuSeal submission for the given PDF. Returns
        {"session_id": ..., "signing_url": ...}.

        Uses DocuSeal's submission-with-inline-document flow — no pre-existing
        template required. DocuSeal accepts the PDF as base64 and creates a
        single-signer submission. The signer receives an email with the
        signing link AND we get the embed_src URL back so the broker can also
        push the client straight into the signing iframe in our UI.
        """
        if not self.is_configured():
            raise RuntimeError("DocuSeal is not configured (missing DOCUSEAL_* env vars)")
        payload = self._build_submission_payload(
            pdf_bytes, signer_email, signer_name, document_title,
        )
        url = f"{self.config.api_base.rstrip('/')}/submissions"
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                url,
                json=payload,
                headers={
                    "X-Auth-Token": self.config.api_key,
                    "Content-Type": "application/json",
                },
            )
        resp.raise_for_status()
        body = resp.json()
        return self._parse_submission_response(body)

    def _build_submission_payload(
        self,
        pdf_bytes: bytes,
        signer_email: str,
        signer_name: str,
        document_title: str,
    ) -> dict:
        """DocuSeal submission shape: provide the PDF inline (base64) and
        a single submitter. DocuSeal auto-creates a one-off template + signing
        flow. `send_email=True` triggers the email delivery; if you set this
        to False you must use the embed_src URL only.
        """
        return {
            "send_email": True,
            "submitters": [
                {
                    "email": signer_email,
                    "name":  signer_name,
                    "role":  "Signer",
                }
            ],
            "documents": [
                {
                    "name": document_title,
                    "file": base64.b64encode(pdf_bytes).decode("ascii"),
                }
            ],
        }

    def _parse_submission_response(self, body) -> dict:
        """DocuSeal returns either a list of submitters (one per signer) or
        an object wrapping them. We always have a single signer for broker
        recommendation letters, so return the first one's session id and
        signing URL. Tolerates both shapes so we don't break on minor API
        version drift.
        """
        if isinstance(body, list):
            submitter = body[0] if body else {}
        else:
            submitters = body.get("submitters") or []
            submitter = submitters[0] if submitters else body
        return {
            "session_id":  str(submitter.get("submission_id") or submitter.get("id", "")),
            "signing_url": submitter.get("embed_src") or submitter.get("url", ""),
        }

    def verify_webhook(self, raw_body: bytes, signature_header: str) -> bool:
        """Verify HMAC-SHA256 signature on a DocuSeal webhook delivery.

        DocuSeal sends the signature in the X-Docuseal-Signature header as a
        plain hex digest. Returns False rather than raising so the route can
        return a clean 401. Constant-time compare so a side-channel timing
        attack can't leak the secret.
        """
        if not self.config.webhook_secret or not signature_header:
            return False
        expected = hmac.new(
            self.config.webhook_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature_header.strip())

    def parse_webhook(self, payload: dict) -> dict:
        """Extract relevant fields from a DocuSeal webhook body.

        DocuSeal event types we care about:
          - form.completed: all submitters have signed → fetch documents
          - form.declined:  submitter declined → mark recommendation as rejected
          - form.viewed:    submitter opened the link (not a state change)
        """
        event = payload.get("event_type", "")
        data  = payload.get("data") or {}
        status_map = {
            "form.completed": "signed",
            "form.declined":  "rejected",
            "form.viewed":    "viewed",
        }
        first_doc = (data.get("documents") or [{}])[0]
        return {
            "session_id":     str(data.get("submission_id") or data.get("id", "")),
            "status":         status_map.get(event, event or "unknown"),
            "signed_pdf_url": first_doc.get("url"),
            "signed_at":      data.get("completed_at") or data.get("submitted_at"),
        }


def _config_from_env() -> DocuSealConfig:
    return DocuSealConfig(
        api_base=os.getenv("DOCUSEAL_API_BASE", ""),
        api_key=os.getenv("DOCUSEAL_API_KEY", ""),
        webhook_secret=os.getenv("DOCUSEAL_WEBHOOK_SECRET", ""),
        webhook_url=os.getenv("DOCUSEAL_WEBHOOK_URL", ""),
    )


# ── Provider factory ─────────────────────────────────────────────────────────
#
# Routers import `get_signing_service()` from this module instead of
# instantiating SignicatService or DocuSealService directly. The choice is
# made by the ESIGN_PROVIDER env var:
#
#   ESIGN_PROVIDER=signicat  → SignicatService (default for backwards-compat)
#   ESIGN_PROVIDER=docuseal  → DocuSealService
#
# Both implementations satisfy the same duck-typed protocol (is_configured,
# create_signing_session, verify_webhook, parse_webhook) so the router code
# is identical regardless of choice.

def get_signing_service():
    """Return the configured e-sign provider instance.

    Defaults to Signicat for backwards compatibility — the routers were
    originally wired to SignicatService. Set ESIGN_PROVIDER=docuseal to swap.
    """
    provider = os.getenv("ESIGN_PROVIDER", "signicat").lower()
    if provider == "docuseal":
        return DocuSealService()
    # Lazy import so DocuSeal-only deployments don't pull Signicat config.
    from api.services.signicat_service import SignicatService
    return SignicatService()
