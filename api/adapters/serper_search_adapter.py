"""Serper.dev Web Search API adapter.

Replacement for the Bing Web Search adapter after Microsoft discontinued
the Bing.Search.v7 Cognitive Service in 2024. Serper provides Google
search results via a single JSON POST endpoint — the free tier gives
2,500 one-time credits and the flat $5/mo plan covers 50K queries.

We use the `filetype:pdf` query operator (Google-native) to filter
server-side to PDF results, same pattern the dead Bing adapter used.

Implements the same `WebSearchPort` contract as the prior Bing adapter,
so `pdf_web.py` + `container.py` consume it without changes.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

import requests

from api.ports.driven.web_search_port import WebSearchPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SerperSearchConfig:
    endpoint: str = "https://google.serper.dev/search"
    api_key: Optional[str] = None
    country: str = "no"  # Norwegian results — the corpus is Norwegian companies
    locale: str = "no"


class SerperSearchAdapter(WebSearchPort):
    def __init__(self, config: SerperSearchConfig) -> None:
        self._cfg = config

    def is_configured(self) -> bool:
        return bool(self._cfg.api_key)

    def search_pdfs(self, query: str, max_results: int = 10) -> List[str]:
        if not self.is_configured():
            logger.info("[serper] Not configured — skipping search for %r", query)
            return []
        try:
            resp = requests.post(
                self._cfg.endpoint,
                json={
                    "q": f"{query} filetype:pdf",
                    "num": max_results,
                    "gl": self._cfg.country,
                    "hl": self._cfg.locale,
                },
                headers={
                    "X-API-KEY": self._cfg.api_key,
                    "Content-Type": "application/json",
                },
                timeout=15,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("[serper] Query %r failed: %s", query, exc)
            return []
        try:
            data = resp.json()
        except ValueError as exc:
            logger.warning("[serper] Non-JSON response for %r: %s", query, exc)
            return []
        organic = data.get("organic") or []
        urls = [
            r.get("link") for r in organic if r.get("link", "").lower().endswith(".pdf")
        ]
        logger.info("[serper] Query %r → %d PDF URLs", query, len(urls))
        return urls[:max_results]
