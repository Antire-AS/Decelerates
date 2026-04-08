"""PDF parsing and financial data extraction — Gemini native PDF only.

Phase 3 of the LLM-stack consolidation removed the pdfplumber-based text
fallback: it was rarely exercised, gpt-5.4 / Gemini handles even scanned
PDFs better than text-extraction-then-LLM, and "fail loudly when extraction
fails" is a clearer contract for downstream code than silent text fallback.
"""
import json
import logging
import os
import re
import tempfile
from typing import Optional, List, Dict, Any

import requests
from google import genai as google_genai
from google.genai import types as genai_types

from api.constants import (
    GEMINI_PDF_MODELS,
    GEMINI_FILES_API_THRESHOLD,
)
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
    """Send PDF bytes inline to Gemini (≤18 MB)."""
    pdf_part = genai_types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
    resp = client.models.generate_content(model=model_name, contents=[pdf_part, prompt])
    return resp.text


def _gemini_files_api(
    client: Any, model_name: str, pdf_bytes: bytes, orgnr: str, year: int
) -> Optional[str]:
    """Upload PDF via Files API (>18 MB) and generate content, then delete upload."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name
    try:
        uploaded = client.files.upload(
            file=tmp_path,
            config=genai_types.UploadFileConfig(
                mime_type="application/pdf",
                display_name=f"annual_{orgnr}_{year}.pdf",
            ),
        )
        try:
            prompt_text = FINANCIALS_PROMPT.format(orgnr=orgnr, year=year)
            resp = client.models.generate_content(
                model=model_name, contents=[uploaded, prompt_text]
            )
            return resp.text
        finally:
            try:
                client.files.delete(name=uploaded.name)
            except Exception:
                pass
    finally:
        os.unlink(tmp_path)


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
    """Build a list of `genai.Client` instances in priority order.

    Vertex AI (project + location, service account auth via
    GOOGLE_APPLICATION_CREDENTIALS) comes first when configured. Falls back
    to one client per legacy AI-Studio API key.
    """
    clients: List[Any] = []
    project = os.getenv("GCP_VERTEX_AI_PROJECT")
    location = os.getenv("GCP_VERTEX_AI_LOCATION", "europe-west4")
    if project:
        try:
            clients.append(
                google_genai.Client(vertexai=True, project=project, location=location)
            )
        except Exception as exc:
            logger.warning("[extract] Vertex AI client init failed: %s", exc)
    for api_key in _gemini_api_keys():
        try:
            clients.append(google_genai.Client(api_key=api_key))
        except Exception as exc:
            logger.warning("[extract] Legacy Gemini client init failed: %s", exc)
    return clients


def _try_gemini(pdf_bytes: bytes, orgnr: str, year: int) -> Optional[str]:
    """Try every configured Gemini client × every PDF model; return raw text or None.

    Vertex AI is preferred (prod-grade SLA, EU residency). Legacy AI-Studio
    API keys remain as fallback until Phase 4 cleanup. Vertex AI handles
    PDFs of any size inline — the Files API path is only needed for the
    legacy AI-Studio clients which cap at ~18 MB inline.
    """
    prompt = FINANCIALS_PROMPT.format(orgnr=orgnr, year=year)
    use_files_api = len(pdf_bytes) > GEMINI_FILES_API_THRESHOLD

    for client in _build_gemini_clients():
        is_vertex = bool(getattr(getattr(client, "_api_client", None), "vertexai", False))
        for model_name in GEMINI_PDF_MODELS:
            try:
                # Vertex AI accepts inline PDFs of any practical size; the
                # AI-Studio Files API path is only needed for the legacy keys.
                if use_files_api and not is_vertex:
                    raw = _gemini_files_api(client, model_name, pdf_bytes, orgnr, year)
                else:
                    raw = _gemini_inline(client, model_name, pdf_bytes, prompt)
                if raw:
                    return raw
            except Exception as exc:
                msg = str(exc)
                if "quota" in msg.lower() or "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    continue  # try next model or client
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
