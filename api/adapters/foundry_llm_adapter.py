"""Antire Azure AI Foundry adapter — implements LlmPort.

Foundry exposes hosted models under one Azure resource but with two URL
shapes:

* **Chat completions** at the OpenAI-v1 path
  ``/api/projects/<project>/openai/v1`` — used via the standard ``openai`` SDK.

* **Embeddings** at the Azure-OpenAI deployment path
  ``/openai/deployments/<deployment>/embeddings?api-version=...`` — called
  with raw ``requests`` to keep the dep surface small. The 2024-02-01 API
  version supports ``dimensions`` for ``text-embedding-3-*`` models, which
  we need to match the existing pgvector(512) column.
"""

import logging
from dataclasses import dataclass
from typing import Any, List, Optional
from urllib.parse import urlparse

import requests

from api.ports.driven.llm_port import LlmPort
from api.telemetry import llm_tokens_completion, llm_tokens_prompt

logger = logging.getLogger(__name__)


def _record_token_counts(
    prompt: int, completion: int, provider: str, model: str
) -> None:
    """Push prompt + completion token counts to OpenTelemetry histograms.

    Best-effort: a telemetry failure must never fail the LLM call. Attributes
    are `provider` (e.g. `foundry`, `foundry_embed`) + `model` so the App
    Insights dashboard can break cost down by model family.
    """
    try:
        attrs = {"provider": provider, "model": model or "unknown"}
        if prompt:
            llm_tokens_prompt.record(int(prompt), attrs)
        if completion:
            llm_tokens_completion.record(int(completion), attrs)
    except Exception:
        pass  # metering is best-effort


def _record_token_usage(resp: Any, provider: str, model: str) -> None:
    """Extract OpenAI-shaped `usage` from a chat completion response and
    record it. Accepts either SDK objects (with `.usage.prompt_tokens`)
    or dict-shaped responses. Silent no-op if usage is missing."""
    usage = getattr(resp, "usage", None)
    if usage is None:
        return
    prompt = getattr(usage, "prompt_tokens", None) or 0
    completion = getattr(usage, "completion_tokens", None) or 0
    _record_token_counts(prompt, completion, provider, model)


@dataclass(frozen=True)
class FoundryConfig:
    base_url: Optional[str] = None  # AZURE_FOUNDRY_BASE_URL  (chat path)
    api_key: Optional[str] = None  # AZURE_FOUNDRY_API_KEY
    default_text_model: str = "gpt-5.4-mini"  # AZURE_FOUNDRY_MODEL
    embedding_deployment: str = (
        "text-embedding-3-small"  # AZURE_FOUNDRY_EMBEDDING_DEPLOYMENT
    )
    embedding_dimensions: int = 512  # must match pgvector column dim
    embedding_api_version: str = "2024-02-01"


def _derive_azure_host(base_url: str) -> str:
    """Strip the project/openai/v1 suffix to get the bare Azure resource host."""
    parsed = urlparse(base_url)
    return f"{parsed.scheme}://{parsed.netloc}"


class FoundryLlmAdapter(LlmPort):
    def __init__(self, config: FoundryConfig) -> None:
        self._config = config
        self._chat_client = None

    def is_configured(self) -> bool:
        base = self._config.base_url or ""
        key = self._config.api_key or ""
        return bool(base and key and key != "your_key_here")

    def embeddings_configured(self) -> bool:
        return self.is_configured() and bool(self._config.embedding_deployment)

    def _get_chat_client(self):
        if self._chat_client is None:
            from openai import OpenAI

            self._chat_client = OpenAI(
                base_url=self._config.base_url,
                api_key=self._config.api_key,
            )
        return self._chat_client

    def chat(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        max_completion_tokens: int = 1024,
    ) -> Optional[str]:
        if not self.is_configured():
            return None
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        resolved_model = model or self._config.default_text_model
        try:
            resp = self._get_chat_client().chat.completions.create(
                model=resolved_model,
                messages=messages,
                max_completion_tokens=max_completion_tokens,
            )
            _record_token_usage(resp, "foundry", resolved_model)
            return resp.choices[0].message.content
        except Exception as exc:
            logger.warning("Foundry chat failed: %s", exc)
            return None

    def embed(self, text: str) -> Optional[List[float]]:
        if not self.embeddings_configured():
            return None
        host = _derive_azure_host(self._config.base_url or "")
        url = (
            f"{host}/openai/deployments/{self._config.embedding_deployment}"
            f"/embeddings?api-version={self._config.embedding_api_version}"
        )
        payload = {
            "input": text,
            "dimensions": self._config.embedding_dimensions,
        }
        try:
            resp = requests.post(
                url,
                json=payload,
                headers={
                    "api-key": self._config.api_key,
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            # Azure OpenAI REST response includes `usage.prompt_tokens`.
            # Embeddings have no "completion" side — record 0 there.
            usage = data.get("usage") or {}
            _record_token_counts(
                int(usage.get("prompt_tokens") or 0),
                0,
                "foundry_embed",
                self._config.embedding_deployment,
            )
            return data["data"][0]["embedding"]
        except Exception as exc:
            logger.warning("Foundry embed failed: %s", exc)
            return None
