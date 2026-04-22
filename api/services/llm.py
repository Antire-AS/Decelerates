"""LLM and embedding helpers — Antire Azure Foundry primary, Vertex AI for PDFs.

Phase 4.5 cleanup removed the legacy fallback chains here:

  - Voyage AI embeddings (gone — Foundry text-embedding-3-small handles it)
  - Anthropic Claude direct chat (gone — Foundry gpt-5.4-mini handles it)
  - AI Studio API-key Gemini chat (gone — Foundry handles all chat)

Vertex AI is still primary for multimodal PDF analysis (the cost-efficient
native PDF input), and that path uses GOOGLE_APPLICATION_CREDENTIALS. The
agentic IR PDF discovery path in api/services/pdf_agents.py had its
Gemini AI-Studio branches removed on 2026-04-22 (measured 2/20 recall);
it now depends only on ANTHROPIC_API_KEY + AZURE_OPENAI_*.
"""

import json
import logging
import os
import re
import time
from typing import Optional, List

_LLM_TIMEOUT_SECONDS = 30

logger = logging.getLogger(__name__)

from google import genai as google_genai
from google.genai import types as genai_types

from api.constants import GEMINI_MODEL
from api.domain.exceptions import LlmUnavailableError
from api.prompts import CHAT_SYSTEM_PROMPT
from api.telemetry import llm_calls, llm_duration_ms, record_vertex_token_usage


_INJECTION_PATTERNS = re.compile(
    r"(ignore\s+previous|system\s*:|assistant\s*:|human\s*:|<\s*/?system\s*>)",
    re.IGNORECASE,
)


def _sanitize_user_input(text: str, max_chars: int = 4000) -> str:
    """Strip common prompt injection patterns and hard-cap length."""
    sanitized = _INJECTION_PATTERNS.sub("", text)
    return sanitized[:max_chars]


def _validate_llm_json(raw: str, required_keys: list[str]) -> dict:
    """Parse JSON from LLM response and verify required keys are present.

    Raises LlmUnavailableError if the response cannot be parsed or is missing keys.
    """
    parsed = _parse_json_from_llm_response(raw)
    if not isinstance(parsed, dict):
        raise LlmUnavailableError(f"LLM returned non-JSON response: {raw[:200]}")
    missing = [k for k in required_keys if k not in parsed]
    if missing:
        raise LlmUnavailableError(f"LLM JSON missing required keys: {missing}")
    return parsed


def _parse_json_from_llm_response(raw: str) -> Optional[dict]:
    """Extract and parse the first JSON object from an LLM response string."""
    if not raw:
        return None
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)
        try:
            return json.loads(cleaned)
        except Exception:
            m = re.search(r"\{.*\}", cleaned, re.DOTALL)
            return json.loads(m.group(0)) if m else None
    except Exception:
        return None


def _try_foundry_embed(text: str) -> Optional[List[float]]:
    """Attempt an embedding via the configured LlmPort. Returns None on any failure."""
    try:
        from api.container import resolve
        from api.ports.driven.llm_port import LlmPort

        llm: LlmPort = resolve(LlmPort)  # type: ignore[assignment]
        if not llm.embeddings_configured():
            return None
        return llm.embed(text)
    except Exception as exc:
        logger.warning("Foundry embed failed: %s", exc)
        return None


def _embed(text: str) -> List[float]:
    """Return a 512-dim embedding vector via Foundry text-embedding-3-small.

    Returns [] if Foundry isn't configured or the call fails. Phase 4.5
    removed the Voyage and Gemini-API-key fallbacks since Foundry has been
    serving 100% of embedding traffic in prod since 2026-04-08.
    """
    result = _try_foundry_embed(text)
    return result if result is not None else []


def _fmt_nok(value) -> str:
    if value is None:
        return "–"
    try:
        return f"{value / 1_000_000:,.1f} MNOK".replace(",", " ")
    except Exception:
        return str(value)


def _llm_answer_raw(prompt: str) -> Optional[str]:
    """Call LLM with a plain user prompt via Foundry. Used for narrative
    and synthetic data generation. Returns None if Foundry isn't configured
    or the call fails. Phase 4.5 removed the Anthropic + Gemini fallbacks.
    """
    _t0 = time.monotonic()
    _provider = "none"
    _outcome = "success"
    try:
        result = _try_foundry_chat(prompt)
        if result is not None:
            _provider = "azure_foundry"
            return result
        return None
    except Exception:
        _outcome = "error"
        raise
    finally:
        llm_duration_ms.record((time.monotonic() - _t0) * 1000, {"provider": _provider})
        llm_calls.add(1, {"provider": _provider, "outcome": _outcome})


def _compare_offers_with_llm(prompt: str) -> Optional[str]:
    """Run an insurance offer comparison prompt through Foundry.

    Phase 4.5 removed the Gemini-API-key fallback; Foundry handles all
    text comparison now.
    """
    return _try_foundry_chat(prompt, max_tokens=4096)


def _build_gemini_clients(timeout: int = 120) -> list:
    """Build the Vertex AI `genai.Client` for multimodal PDF analysis.

    Returns a list (length 0 or 1) so callers can iterate uniformly.
    Phase 4.5 removed the legacy AI-Studio API-key fallback — Vertex AI
    has been serving 100% of multimodal traffic in prod since 2026-04-08.
    Auth is via GOOGLE_APPLICATION_CREDENTIALS, set up by api/main.py from
    the GCP_VERTEX_AI_SA_JSON_B64 env var at startup.
    """
    project = os.getenv("GCP_VERTEX_AI_PROJECT")
    location = os.getenv("GCP_VERTEX_AI_LOCATION", "europe-west4")
    if not project:
        return []
    try:
        return [
            google_genai.Client(
                vertexai=True,
                project=project,
                location=location,
                http_options={"timeout": timeout},
            )
        ]
    except Exception as exc:
        logger.warning("Vertex AI client init failed: %s", exc)
        return []


def _gemini_generate_with_fallback(
    parts: list, timeout: int = 120, system_instruction: Optional[str] = None
) -> Optional[str]:
    """Try each Gemini client × model in order. Returns first successful text.

    Vertex AI is preferred when configured; legacy AI-Studio API key acts as
    fallback. Will be reduced to Vertex-only in Phase 4.5 once stable in prod.
    """
    clients = _build_gemini_clients(timeout=timeout)
    if not clients:
        return None
    config = (
        genai_types.GenerateContentConfig(system_instruction=system_instruction)
        if system_instruction
        else None
    )
    for client in clients:
        for model in ["gemini-2.5-flash", "gemini-1.5-flash", GEMINI_MODEL]:
            try:
                resp = client.models.generate_content(
                    model=model, contents=parts, config=config
                )
                # Phase 4 follow-up: surface Vertex AI token cost in OTel
                # so Gemini prompt regressions are visible alongside Foundry.
                record_vertex_token_usage(resp, model)
                return resp.text
            except Exception as exc:
                logger.warning("Gemini model %s failed: %s", model, exc)
                continue
    return None


def _analyze_document_with_gemini(pdf_bytes: bytes, prompt: str) -> Optional[str]:
    """Send a PDF to Gemini for analysis. Tries multiple models; returns text or None."""
    pdf_part = genai_types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
    return _gemini_generate_with_fallback([pdf_part, prompt], timeout=120)


def _compare_documents_with_gemini(
    pdf_bytes_a: bytes, pdf_bytes_b: bytes, prompt: str
) -> Optional[str]:
    """Send two PDFs to Gemini for comparison. Tries multiple models; returns text or None."""
    pdf_a = genai_types.Part.from_bytes(data=pdf_bytes_a, mime_type="application/pdf")
    pdf_b = genai_types.Part.from_bytes(data=pdf_bytes_b, mime_type="application/pdf")
    # 360s: two large PDFs routinely push past 280s on cold model instances.
    return _gemini_generate_with_fallback([pdf_a, pdf_b, prompt], timeout=360)


def _try_foundry_chat(
    user_prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 1024
) -> Optional[str]:
    """Attempt a chat call via the configured LlmPort. Returns None on any failure."""
    try:
        from api.container import resolve
        from api.ports.driven.llm_port import LlmPort

        llm: LlmPort = resolve(LlmPort)  # type: ignore[assignment]
        if not llm.is_configured():
            return None
        return llm.chat(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            max_completion_tokens=max_tokens,
        )
    except Exception as exc:
        logger.warning("Foundry chat failed: %s", exc)
        return None


def _llm_answer(context: str, question: str) -> str:
    """Answer a question about a company via Foundry chat. Phase 4.5
    removed the Anthropic + Gemini-API-key fallbacks.
    """
    user_prompt = f"Company data:\n{context}\n\nQuestion: {question}"
    result = _try_foundry_chat(user_prompt, CHAT_SYSTEM_PROMPT, max_tokens=1024)
    if result:
        return result
    raise LlmUnavailableError(
        "No LLM provider configured (set AZURE_FOUNDRY_BASE_URL + AZURE_FOUNDRY_API_KEY)"
    )


# ── Service class wrapper ──────────────────────────────────────────────────────


class LlmService:
    """Thin class wrapper around module-level LLM helpers for DI-friendly access."""

    def embed(self, text: str):
        return _embed(text)

    def answer_raw(self, prompt: str):
        return _llm_answer_raw(prompt)

    def answer(self, context: str, question: str) -> str:
        return _llm_answer(context, question)

    def compare_offers(self, prompt: str):
        return _compare_offers_with_llm(prompt)

    def parse_json(self, raw: str):
        return _parse_json_from_llm_response(raw)
