"""PDF parsing and financial data extraction — Vertex AI Gemini only.

Phase 3 removed the pdfplumber-based text fallback (rarely exercised; Gemini
handles scanned PDFs better than text-extract-then-LLM). Phase 4.5 removed
the legacy AI-Studio API-key Gemini clients and the Files API path that
went with them — Vertex AI accepts inline PDFs of any practical size, and
has been serving 100% of extraction in prod since 2026-04-08.

Note: `_gemini_api_keys()` is kept here as a re-exported helper because
the agentic IR PDF discovery in api/services/pdf_agents.py still uses the
legacy API-key Gemini for its tool-use loop (separate cleanup pending).
"""
import json
import logging
import os
import re
from typing import Optional, List, Dict, Any

import requests
from google import genai as google_genai
from google.genai import types as genai_types

from api.constants import GEMINI_PDF_MODELS
from api.domain.exceptions import PdfExtractionError  # noqa: F401 — re-exported
from api.prompts import FINANCIALS_PROMPT

logger = logging.getLogger(__name__)

# User-Agent shared with pdf_web.py for PDF downloads
_PDF_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _parse_json_financials(raw: str) -> Optional[Dict[str, Any]]:
    """Parse and validate the JSON financial dict returned by any LLM."""
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group())
        except (json.JSONDecodeError, ValueError):
            return None
    eq = data.get("equity")
    assets = data.get("total_assets")
    data["equity_ratio"] = (eq / assets) if (eq and assets) else None
    return data


# ── Gemini PDF extraction ──────────────────────────────────────────────────────

def _gemini_inline(client: Any, model_name: str, pdf_bytes: bytes, prompt: str) -> Optional[str]:
    """Send PDF bytes inline to Vertex AI Gemini.

    Vertex AI accepts PDFs of any practical size inline; the AI-Studio
    Files API path was needed for the legacy API-key clients (≤18 MB inline
    cap) and was removed in Phase 4.5 along with those clients.
    """
    pdf_part = genai_types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
    resp = client.models.generate_content(model=model_name, contents=[pdf_part, prompt])
    return resp.text


def _gemini_api_keys() -> List[str]:
    """Return all configured legacy Gemini API keys (primary + fallbacks), deduped.

    Legacy AI-Studio API-key path. Used as fallback when Vertex AI is not
    configured. Will be removed once Vertex AI is stable in prod.
    """
    keys = []
    for var in ("GEMINI_API_KEY", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3"):
        k = os.getenv(var)
        if k and k != "your_key_here" and k not in keys:
            keys.append(k)
    return keys


def _build_gemini_clients() -> List[Any]:
    """Build the Vertex AI `genai.Client` for PDF extraction.

    Returns a list (length 0 or 1) so callers can iterate uniformly.
    Phase 4.5 removed the legacy AI-Studio API-key fallback — Vertex AI
    has been serving 100% of PDF extraction in prod since 2026-04-08.
    Auth via GOOGLE_APPLICATION_CREDENTIALS, set up by api/main.py at
    startup from the GCP_VERTEX_AI_SA_JSON_B64 env var.
    """
    project = os.getenv("GCP_VERTEX_AI_PROJECT")
    location = os.getenv("GCP_VERTEX_AI_LOCATION", "europe-west4")
    if not project:
        return []
    try:
        return [google_genai.Client(vertexai=True, project=project, location=location)]
    except Exception as exc:
        logger.warning("[extract] Vertex AI client init failed: %s", exc)
        return []


def _try_gemini(pdf_bytes: bytes, orgnr: str, year: int) -> Optional[str]:
    """Try every configured Gemini PDF model via Vertex AI; return raw text or None.

    Vertex AI accepts inline PDFs of any practical size — the AI-Studio
    Files API path is no longer needed since Phase 4.5 dropped the legacy
    API-key clients.
    """
    prompt = FINANCIALS_PROMPT.format(orgnr=orgnr, year=year)
    for client in _build_gemini_clients():
        for model_name in GEMINI_PDF_MODELS:
            try:
                raw = _gemini_inline(client, model_name, pdf_bytes, prompt)
                if raw:
                    return raw
            except Exception as exc:
                msg = str(exc)
                if "quota" in msg.lower() or "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    continue  # try next model
                break  # non-quota error on this client, skip remaining models
    return None


def _sanity_check_financials(data: Dict[str, Any]) -> bool:
    """Return True if extracted financials pass basic plausibility checks."""
    rev = data.get("revenue")
    net = data.get("net_result")
    eq = data.get("equity")
    assets = data.get("total_assets")
    if rev and net and rev > 0 and abs(net) > abs(rev):
        logger.warning("[extract] Sanity fail: |net_result| > revenue — likely parent-only figures")
        return False
    if eq and assets and assets > 0 and eq > assets:
        logger.warning("[extract] Sanity fail: equity > total_assets")
        return False
    return True


def _download_pdf_bytes(pdf_url: str) -> Optional[bytes]:
    """Download a PDF from *pdf_url* and return raw bytes, or None on failure."""
    try:
        resp = requests.get(pdf_url, timeout=60, headers={"User-Agent": _PDF_UA})
        resp.raise_for_status()
        return resp.content
    except requests.Timeout:
        logger.warning("[extract] Timeout downloading PDF %s — skipping", pdf_url)
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            logger.warning("[extract] PDF not found (404): %s", pdf_url)
        else:
            logger.error("[extract] HTTP error downloading %s: %s", pdf_url, exc)
    except Exception as exc:
        logger.error("[extract] Unexpected error downloading %s: %s", pdf_url, exc)
    return None


def _try_gemini_with_retry(pdf_bytes: bytes, orgnr: str, year: int) -> Optional[Dict[str, Any]]:
    """Try Gemini PDF extraction up to 2 times, sanity-checking each result."""
    for attempt in range(2):
        raw = _try_gemini(pdf_bytes, orgnr, year)
        if raw:
            result = _parse_json_financials(raw)
            if result and _sanity_check_financials(result):
                return result
            if result and attempt == 0:
                logger.warning(
                    "[extract] Attempt 1 failed sanity check for %s year %d — retrying", orgnr, year
                )
                continue
        break
    return None


def _parse_financials_from_pdf(pdf_url: str, orgnr: str, year: int) -> Optional[Dict[str, Any]]:
    """Extract key financials from an annual report PDF using Gemini native PDF.

    Returns None on failure — callers should treat that as "couldn't extract,
    surface a manual upload prompt to the broker." There is no text-extraction
    fallback as of Phase 3 (pdfplumber path removed).
    """
    pdf_bytes = _download_pdf_bytes(pdf_url)
    if pdf_bytes is None:
        return None
    return _try_gemini_with_retry(pdf_bytes, orgnr, year)
