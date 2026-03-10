"""LLM and embedding helpers — Claude, Gemini, Voyage AI."""
import os
from typing import Optional, List, Dict, Any

import anthropic
import voyageai
from google import genai as google_genai
from google.genai import types as genai_types

from constants import CLAUDE_MODEL, GEMINI_MODEL, VOYAGE_MODEL
from domain.exceptions import LlmUnavailableError, QuotaError
from prompts import CHAT_SYSTEM_PROMPT


def _embed(text: str) -> List[float]:
    voyage_key = os.getenv("VOYAGE_API_KEY")
    if voyage_key and voyage_key != "your_key_here":
        try:
            vo = voyageai.Client(api_key=voyage_key)
            result = vo.embed([text], model=VOYAGE_MODEL)
            return result.embeddings[0] if result.embeddings else []
        except Exception:
            pass

    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key and gemini_key != "your_key_here":
        try:
            client = google_genai.Client(api_key=gemini_key)
            result = client.models.embed_content(
                model="text-embedding-004",
                contents=text,
                config=genai_types.EmbedContentConfig(output_dimensionality=512),
            )
            return result.embeddings[0].values
        except Exception:
            pass

    return []


def _fmt_nok(value) -> str:
    if value is None:
        return "–"
    try:
        return f"{value / 1_000_000:,.1f} MNOK".replace(",", " ")
    except Exception:
        return str(value)


def _llm_answer_raw(prompt: str) -> Optional[str]:
    """Call LLM with a plain user prompt. Used for narrative and synthetic data generation."""
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key and anthropic_key != "your_key_here":
        client = anthropic.Anthropic(api_key=anthropic_key)
        msg = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text

    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key and gemini_key != "your_key_here":
        client = google_genai.Client(api_key=gemini_key)
        models_to_try = ["gemini-2.5-flash", GEMINI_MODEL, "gemini-2.0-flash", "gemini-2.0-flash-lite", "gemma-3-12b-it", "gemma-3-27b-it"]
        seen: set = set()
        ordered = [m for m in models_to_try if not (m in seen or seen.add(m))]
        last_exc: Optional[Exception] = None
        for model_name in ordered:
            try:
                response = client.models.generate_content(model=model_name, contents=prompt)
                return response.text
            except Exception as exc:
                msg = str(exc)
                if "quota" in msg.lower() or "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    last_exc = exc
                    continue
                raise
        raise QuotaError(
            "Gemini free-tier quota exhausted on all models — wait a few minutes or enable billing."
        )

    return None


def _compare_offers_with_llm(prompt: str) -> Optional[str]:
    """Run an insurance offer comparison prompt through Gemini and return the text response."""
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if not gemini_key:
        return None
    client = google_genai.Client(api_key=gemini_key)
    resp = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    return resp.text


def _analyze_document_with_gemini(pdf_bytes: bytes, prompt: str) -> Optional[str]:
    """Send a PDF to Gemini for analysis. Tries multiple models; returns text or None."""
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        return None
    try:
        client = google_genai.Client(api_key=gemini_key, http_options={"timeout": 120})
        pdf_part = genai_types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
        for model in ["gemini-2.5-flash", "gemini-1.5-flash", GEMINI_MODEL]:
            try:
                resp = client.models.generate_content(model=model, contents=[pdf_part, prompt])
                return resp.text
            except Exception:
                continue
    except Exception:
        pass
    return None


def _compare_documents_with_gemini(
    pdf_bytes_a: bytes, pdf_bytes_b: bytes, prompt: str
) -> Optional[str]:
    """Send two PDFs to Gemini for comparison. Tries multiple models; returns text or None."""
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        return None
    try:
        client = google_genai.Client(api_key=gemini_key, http_options={"timeout": 280})
        pdf_a = genai_types.Part.from_bytes(data=pdf_bytes_a, mime_type="application/pdf")
        pdf_b = genai_types.Part.from_bytes(data=pdf_bytes_b, mime_type="application/pdf")
        for model in ["gemini-2.5-flash", "gemini-1.5-flash", GEMINI_MODEL]:
            try:
                resp = client.models.generate_content(model=model, contents=[pdf_a, pdf_b, prompt])
                return resp.text
            except Exception:
                continue
    except Exception:
        pass
    return None


def _llm_answer(context: str, question: str) -> str:
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key and anthropic_key != "your_key_here":
        client = anthropic.Anthropic(api_key=anthropic_key)
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=CHAT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Company data:\n{context}\n\nQuestion: {question}"}],
        )
        return message.content[0].text

    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key and gemini_key != "your_key_here":
        client = google_genai.Client(api_key=gemini_key)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=f"Company data:\n{context}\n\nQuestion: {question}",
            config=genai_types.GenerateContentConfig(system_instruction=CHAT_SYSTEM_PROMPT),
        )
        return response.text

    raise LlmUnavailableError("No LLM API key configured (ANTHROPIC_API_KEY or GEMINI_API_KEY)")
