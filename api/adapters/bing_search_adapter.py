"""Bing Web Search v7 API adapter.

Bing returns ~10 results per query by default. We append `+filetype:pdf`
to the query to filter server-side; Bing's native `filetype:` operator
works and returns only PDF URLs.

Designed as the replacement for the DDG HTML-scrape fallback that's been
silently broken since DuckDuckGo started returning HTTP 202 anti-bot pages
(discovered in the 2026-04-22 harness run, 0/20 recall). Bing's paid API
doesn't bot-detect and its F1 SKU gives 1K queries/month free, which
covers our expected discovery volume (~100-300 calls/month) with headroom.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

import requests

from api.ports.driven.web_search_port import WebSearchPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BingSearchConfig:
    endpoint: str
    api_key: Optional[str] = None
    market: str = "en-US"


class BingSearchAdapter(WebSearchPort):
    def __init__(self, config: BingSearchConfig) -> None:
        self._cfg = config

    def is_configured(self) -> bool:
        return bool(self._cfg.api_key)

    def search_pdfs(self, query: str, max_results: int = 10) -> List[str]:
        if not self.is_configured():
            logger.info("[bing] Not configured — skipping search for %r", query)
            return []
        try:
            resp = requests.get(
                self._cfg.endpoint,
                params={
                    "q": f"{query} filetype:pdf",
                    "count": max_results,
                    "mkt": self._cfg.market,
                    "responseFilter": "Webpages",
                },
                headers={"Ocp-Apim-Subscription-Key": self._cfg.api_key},
                timeout=15,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("[bing] Query %r failed: %s", query, exc)
            return []
        try:
            data = resp.json()
        except ValueError as exc:
            logger.warning("[bing] Non-JSON response for %r: %s", query, exc)
            return []
        pages = (data.get("webPages") or {}).get("value") or []
        urls = [
            p.get("url") for p in pages if p.get("url", "").lower().endswith(".pdf")
        ]
        logger.info("[bing] Query %r → %d PDF URLs", query, len(urls))
        return urls[:max_results]
