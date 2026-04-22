"""Abstract web search port — lets us swap Bing / Serper / self-hosted
without touching discovery code."""

from abc import ABC, abstractmethod
from typing import List


class WebSearchPort(ABC):
    @abstractmethod
    def search_pdfs(self, query: str, max_results: int = 10) -> List[str]:
        """Return PDF URLs matching `query`, or [] if no results / rate-limited.

        Implementations MUST NOT raise — swallow network errors and return
        empty. Callers distinguish "search worked but found nothing" from
        "search broke" via logs, not exceptions.
        """
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        """True if the adapter has credentials and can make real calls."""
        ...
