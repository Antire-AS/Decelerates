"""LLM and embedding helpers — Claude, Gemini, Voyage AI."""
import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Optional, List

_LLM_TIMEOUT_SECONDS = 30

logger = logging.getLogger(__name__)

import anthropic
import voyageai
from google import genai as google_genai
from google.genai import types as genai_types

from api.constants import CLAUDE_MODEL, GEMINI_MODEL, VOYAGE_MODEL
from api.domain.exceptions import LlmUnavailableError, QuotaError
from api.prompts import CHAT_SYSTEM_PROMPT
from api.telemetry import llm_calls, llm_duration_ms


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


def _is_key_set(key: Optional[str]) -> bool:
    return bool(key) and key != "your_key_here"


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
    """Return a 512-dim embedding vector. Foundry primary, Voyage/Gemini legacy."""
    result = _try_foundry_embed(text)
    if result is not None:
        return result

    voyage_key = os.getenv("VOYAGE_API_KEY")
    if _is_key_set(voyage_key):
        try:
            vo = voyageai.Client(api_key=voyage_key)
            result = vo.embed([text], model=VOYAGE_MODEL)
            return result.embeddings[0] if result.embeddings else []
        except Exception as exc:
            logger.warning("Voyage AI embed failed: %s", exc)

    gemini_key = os.getenv("GEMINI_API_KEY")
    if _is_key_set(gemini_key):
        try:
            client = google_genai.Client(api_key=gemini_key)
            result = client.models.embed_content(
                model="text-embedding-004",
                contents=text,
                config=genai_types.EmbedContentConfig(output_dimensionality=512),
            )
            return result.embeddings[0].values
        except Exception as exc:
            logger.warning("Gemini embed failed: %s", exc)

    return []


def _fmt_nok(value) -> str:
    if value is None:
        return "–"
    try:
        return f"{value / 1_000_000:,.1f} MNOK".replace(",", " ")
    except Exception:
        return str(value)


def _gemini_raw_with_fallback(prompt: str) -> Optional[str]:
    """Legacy Gemini fallback for `_llm_answer_raw` — tries multiple models on quota."""
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not _is_key_set(gemini_key):
        return None
    client = google_genai.Client(api_key=gemini_key)
    models_to_try = [
        "gemini-2.5-flash", GEMINI_MODEL, "gemini-2.0-flash",
        "gemini-2.0-flash-lite", "gemma-3-12b-it", "gemma-3-27b-it",
    ]
    seen: set = set()
    ordered = [m for m in models_to_try if not (m in seen or seen.add(m))]
    for model_name in ordered:
        try:
            with ThreadPoolExecutor(max_workers=1) as _pool:
                future = _pool.submit(client.models.generate_content, model_name, prompt)
                response = future.result(timeout=_LLM_TIMEOUT_SECONDS)
            return response.text
        except FuturesTimeoutError:
            logger.warning("Gemini model %s timed out after %ds", model_name, _LLM_TIMEOUT_SECONDS)
            continue
        except Exception as exc:
            err = str(exc)
            if "quota" in err.lower() or "429" in err or "RESOURCE_EXHAUSTED" in err:
                continue
            raise
    raise QuotaError(
        "Gemini free-tier quota exhausted on all models — wait a few minutes or enable billing."
    )


def _llm_answer_raw(prompt: str) -> Optional[str]:
    """Call LLM with a plain user prompt. Used for narrative and synthetic data generation.

    Foundry primary via LlmPort, Anthropic + Gemini as legacy fallback (removed in Phase 3).
    """
    _t0 = time.monotonic()
    _provider = "none"
    _outcome = "success"
    try:
        result = _try_foundry_chat(prompt)
        if result is not None:
            _provider = "azure_foundry"
            return result

        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if _is_key_set(anthropic_key):
            client = anthropic.Anthropic(api_key=anthropic_key)
            msg = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
                timeout=_LLM_TIMEOUT_SECONDS,
            )
            _provider = "claude"
            return msg.content[0].text

        result = _gemini_raw_with_fallback(prompt)
        if result is not None:
            _provider = "gemini"
            return result

        return None
    except Exception:
        _outcome = "error"
        raise
    finally:
        llm_duration_ms.record((time.monotonic() - _t0) * 1000, {"provider": _provider})
        llm_calls.add(1, {"provider": _provider, "outcome": _outcome})


def _compare_offers_with_llm(prompt: str) -> Optional[str]:
    """Run an insurance offer comparison prompt through the LLM.

    Phase 2.2 — Foundry primary via LlmPort, Gemini as legacy fallback.
    """
    result = _try_foundry_chat(prompt, max_tokens=4096)
    if result:
        return result
    return _gemini_generate_with_fallback([prompt])


def _gemini_generate_with_fallback(
    parts: list, timeout: int = 120, system_instruction: Optional[str] = None
) -> Optional[str]:
    """Try each Gemini model in order with the given content parts. Returns first successful text."""
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        return None
    config = genai_types.GenerateContentConfig(system_instruction=system_instruction) if system_instruction else None
    try:
        client = google_genai.Client(api_key=gemini_key, http_options={"timeout": timeout})
        for model in ["gemini-2.5-flash", "gemini-1.5-flash", GEMINI_MODEL]:
            try:
                resp = client.models.generate_content(model=model, contents=parts, config=config)
                return resp.text
            except Exception as exc:
                logger.warning("Gemini model %s failed: %s", model, exc)
                continue
    except Exception as exc:
        logger.error("Gemini generate_with_fallback failed: %s", exc)
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
    return _gemini_generate_with_fallback([pdf_a, pdf_b, prompt], timeout=280)


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
    user_prompt = f"Company data:\n{context}\n\nQuestion: {question}"

    # Phase 2.1 — Foundry primary via LlmPort.
    result = _try_foundry_chat(user_prompt, CHAT_SYSTEM_PROMPT, max_tokens=1024)
    if result:
        return result

    # Legacy fallback — Anthropic, then Gemini. Removed in Phase 3.
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if _is_key_set(anthropic_key):
        client = anthropic.Anthropic(api_key=anthropic_key)
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=CHAT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            timeout=_LLM_TIMEOUT_SECONDS,
        )
        return message.content[0].text

    result = _gemini_generate_with_fallback([user_prompt], system_instruction=CHAT_SYSTEM_PROMPT)
    if result is not None:
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
