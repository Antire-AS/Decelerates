"""Port (driven) — abstract interface for LLM chat + embeddings.

Phase 2 surface: text chat + embeddings. Vision (PDF rasterization) is NOT
included — annual-report extraction stays on Gemini's native PDF support
because rasterizing 80-page PDFs through chat-completions is 20–100× more
expensive than Gemini's inline PDF input.
"""

from abc import ABC, abstractmethod
from typing import List, Optional


class LlmPort(ABC):
    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if the underlying LLM provider is reachable for chat."""

    @abstractmethod
    def chat(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        max_completion_tokens: int = 1024,
    ) -> Optional[str]:
        """Send a single-turn chat and return the assistant text, or None on failure."""

    @abstractmethod
    def embeddings_configured(self) -> bool:
        """Return True if an embeddings deployment is reachable."""

    def chat_stream(self, user_prompt: str, system_prompt=None, model=None, max_completion_tokens: int = 2048):
        """Yield text chunks via streaming. Default no-op for non-streaming adapters."""
        return iter([])

    @abstractmethod
    def embed(self, text: str) -> Optional[List[float]]:
        """Return an embedding vector for *text*, or None on failure."""
