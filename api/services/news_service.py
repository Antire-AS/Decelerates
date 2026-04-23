"""Company news monitor — Serper /news fetch + Foundry materiality classify.

The broker's question: "has anything material happened to this client in
the last 30 days?" Lawsuits, management changes, credit events, bankruptcy
filings — the things that change underwriting posture overnight.

Pipeline per refresh:

  1. Query Serper /news for the company name (+ "Norge" localiser)
  2. Dedupe against stored (orgnr, url) rows
  3. For each new article, classify via Foundry gpt-5.4-mini
     → {material: bool, event_type: str, summary: str}
  4. Upsert everything into company_news

Graceful degradation matches the rest of the stack:

  - SERPER_API_KEY unset → empty fetch, empty insert, no error
  - Foundry unreachable → article lands with material=False, summary=None
    (no hallucinated classification)
  - A broker's tab stays readable even when the providers are down
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy.orm import Session

from api.db import Company, CompanyNews
from api.domain.exceptions import NotFoundError
from api.services.llm import _llm_answer_raw, _parse_json_from_llm_response

logger = logging.getLogger(__name__)


SERPER_NEWS_ENDPOINT = "https://google.serper.dev/news"

# Bias the Serper query toward underwriter-relevant events. Without this
# the top hits for big companies are marketing coverage, analyst notes,
# and macro commentary — all correctly flagged non-material by the LLM
# but pure noise in the UI. Adding these keywords to the query lets
# Google's relevance ranking do half the filtering for us BEFORE we
# spend a Foundry call per article classifying them.
MATERIAL_KEYWORDS_QUERY = (
    '("konkurs" OR "restrukturering" OR "rettssak" OR "søksmål" OR '
    '"ledelsesbytte" OR "CEO slutter" OR "styreleder" OR '
    '"nedskrivning" OR "tap" OR "oppkjøp" OR "fusjon" OR '
    '"granskning" OR "pålegg" OR "erstatning")'
)


def _build_news_query(navn: str) -> str:
    """Company name + Norway locator + materiality keywords. Exposed for
    unit testing — Serper's own query parser isn't something we want to
    run live in tests."""
    return f"{navn} Norge {MATERIAL_KEYWORDS_QUERY}"


MATERIALITY_PROMPT = """Du er en erfaren risikoanalytiker for en norsk forsikringsmegler.
Analyser denne nyhetsoverskriften om selskapet "{navn}":

Overskrift: {headline}
Utdrag: {snippet}
Kilde: {source}

Er dette MATERIELT for en underwriter? Materielle hendelser inkluderer:
- Konkurs / restrukturering / gjeldsavtaler
- Ledelsesbytte (CEO, CFO, styreleder)
- Søksmål, store erstatningskrav, myndighetspålegg
- Rating-endringer, nedskrivninger, store tap
- Oppkjøp / fusjon / salg

Returnér KUN gyldig JSON på denne formen:
{{
  "material": true/false,
  "event_type": "lawsuit" | "mgmt_change" | "credit_event" | "bankruptcy" | "ma" | "other",
  "summary": "1-setning norsk sammendrag av hva saken betyr for forsikringsrisikoen"
}}"""


# ── Serper fetch ─────────────────────────────────────────────────────────────


def _serper_key() -> Optional[str]:
    """Read Serper API key lazily — the same key powers PDF discovery,
    so one setting drives both features."""
    key = os.getenv("SERPER_API_KEY")
    return key if key and key != "your_key_here" else None


def _parse_published(s: str) -> Optional[datetime]:
    """Serper returns relative dates like '3 hours ago', '2 days ago', or
    absolute 'Jan 15, 2026'. Give up on absolute parsing — we only need
    a rough ordering, and fetched_at is always accurate."""
    if not s:
        return None
    now = datetime.now(timezone.utc)
    s = s.strip().lower()
    try:
        from datetime import timedelta

        if "hour" in s or "hr" in s:
            n = int(s.split()[0])
            return now - timedelta(hours=n)
        if "minute" in s or "min" in s:
            n = int(s.split()[0])
            return now - timedelta(minutes=n)
        if "day" in s:
            n = int(s.split()[0])
            return now - timedelta(days=n)
        if "week" in s:
            n = int(s.split()[0])
            return now - timedelta(weeks=n)
        if "month" in s:
            n = int(s.split()[0])
            return now - timedelta(days=n * 30)
        if "year" in s:
            n = int(s.split()[0])
            return now - timedelta(days=n * 365)
    except (ValueError, IndexError):
        pass
    return None


def _fetch_serper_news(navn: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """Single Serper /news POST. Returns empty list on any failure so the
    caller can still render a stale-but-valid tab."""
    key = _serper_key()
    if not key:
        logger.info("[news] SERPER_API_KEY not configured — skipping fetch")
        return []
    try:
        resp = requests.post(
            SERPER_NEWS_ENDPOINT,
            json={
                "q": _build_news_query(navn),
                "num": max_results,
                "gl": "no",
                "hl": "no",
            },
            headers={"X-API-KEY": key, "Content-Type": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("[news] Serper query %r failed: %s", navn, exc)
        return []
    try:
        data = resp.json()
    except ValueError as exc:
        logger.warning("[news] Non-JSON from Serper for %r: %s", navn, exc)
        return []
    return data.get("news") or []


# ── LLM classify ─────────────────────────────────────────────────────────────


def _classify_materiality(
    navn: str, headline: str, snippet: str, source: str
) -> Dict[str, Any]:
    """One Foundry call per article. Returns a safe default on any LLM
    failure so we never drop the article — a broker can still see the
    headline and judge manually."""
    default = {"material": False, "event_type": "other", "summary": None}
    try:
        prompt = MATERIALITY_PROMPT.format(
            navn=navn,
            headline=headline or "",
            snippet=snippet or "",
            source=source or "",
        )
        raw = _llm_answer_raw(prompt)
    except Exception as exc:
        logger.warning("[news] Materiality LLM call failed: %s", exc)
        return default
    if not raw:
        return default
    parsed = _parse_json_from_llm_response(raw)
    if not isinstance(parsed, dict):
        return default
    return {
        "material": bool(parsed.get("material", False)),
        "event_type": str(parsed.get("event_type") or "other")[:32],
        "summary": parsed.get("summary"),
    }


# ── Upsert + refresh orchestration ───────────────────────────────────────────


def _existing_urls(orgnr: str, db: Session) -> set[str]:
    rows = db.query(CompanyNews.url).filter(CompanyNews.orgnr == orgnr).all()
    return {r[0] for r in rows}


def _insert_article(
    orgnr: str, article: Dict[str, Any], classified: Dict[str, Any], db: Session
) -> None:
    db.add(
        CompanyNews(
            orgnr=orgnr,
            headline=str(article.get("title") or "")[:500],
            url=article["link"],
            source=str(article.get("source") or "")[:255] or None,
            published_at=_parse_published(str(article.get("date") or "")),
            snippet=article.get("snippet"),
            summary=classified.get("summary"),
            material=classified.get("material", False),
            event_type=classified.get("event_type"),
            fetched_at=datetime.now(timezone.utc),
        )
    )


def refresh_company_news(orgnr: str, db: Session, max_results: int = 10) -> int:
    """Fetch fresh news for an org, classify each new article, upsert.
    Returns the number of NEW articles stored (dedupe by orgnr+url).
    Raises NotFoundError if the company isn't in our DB."""
    company = db.query(Company).filter(Company.orgnr == orgnr).first()
    if not company:
        raise NotFoundError(f"Company {orgnr} not found")
    navn = company.navn or orgnr
    results = _fetch_serper_news(navn, max_results=max_results)
    seen = _existing_urls(orgnr, db)
    added = 0
    for article in results:
        url = article.get("link")
        if not url or url in seen:
            continue
        classified = _classify_materiality(
            navn,
            str(article.get("title") or ""),
            str(article.get("snippet") or ""),
            str(article.get("source") or ""),
        )
        _insert_article(orgnr, article, classified, db)
        seen.add(url)
        added += 1
    if added:
        db.commit()
    return added


def list_company_news(
    orgnr: str, db: Session, only_material: bool = False
) -> List[Dict[str, Any]]:
    """Return stored articles ordered newest-first. `only_material=True`
    filters to the underwriter-relevant subset so the portfolio alert
    widget can cheap-query by flag."""
    q = db.query(CompanyNews).filter(CompanyNews.orgnr == orgnr)
    if only_material:
        q = q.filter(CompanyNews.material.is_(True))
    # Order by published_at when we have it, else fetched_at.
    q = q.order_by(
        CompanyNews.published_at.desc().nullslast(),
        CompanyNews.fetched_at.desc(),
    )
    return [_row_to_dict(r) for r in q.all()]


def _row_to_dict(r: CompanyNews) -> Dict[str, Any]:
    return {
        "id": r.id,
        "orgnr": r.orgnr,
        "headline": r.headline,
        "url": r.url,
        "source": r.source,
        "published_at": r.published_at.isoformat() if r.published_at else None,
        "snippet": r.snippet,
        "summary": r.summary,
        "material": bool(r.material),
        "event_type": r.event_type,
        "fetched_at": r.fetched_at.isoformat() if r.fetched_at else None,
    }
