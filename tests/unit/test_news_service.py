"""Unit tests for api.services.news_service.

Verify the two dicey helpers: relative-date parsing (Serper's "3 days ago"
format) and the fetch-classify-upsert orchestration with mocked providers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from api.services import news_service
from api.services.news_service import _parse_published, refresh_company_news


# ── Date parsing ─────────────────────────────────────────────────────────────


def test_parse_published_hours_ago():
    now = datetime.now(timezone.utc)
    result = _parse_published("3 hours ago")
    assert result is not None
    delta = (now - result).total_seconds()
    assert 3 * 3600 - 5 <= delta <= 3 * 3600 + 5


def test_parse_published_days_ago():
    now = datetime.now(timezone.utc)
    result = _parse_published("7 days ago")
    assert result is not None
    # Allow ±1s drift; (now - result).days truncates so 6 days 23:59 reads as 6.
    delta_seconds = (now - result).total_seconds()
    assert abs(delta_seconds - 7 * 86400) <= 5


def test_parse_published_empty_returns_none():
    assert _parse_published("") is None


def test_parse_published_absolute_date_gives_up():
    """Serper sometimes returns absolute dates like 'Jan 15, 2026'. We
    don't parse those — fetched_at is accurate anyway."""
    assert _parse_published("Jan 15, 2026") is None


def test_parse_published_tolerates_malformed_input():
    assert _parse_published("ancient times") is None


# ── Refresh orchestration ────────────────────────────────────────────────────


class _FakeQuery:
    def __init__(self, result: Any = None):
        self._result = result
        self._filters: List[Any] = []

    def filter(self, *args, **kw) -> "_FakeQuery":
        self._filters.extend(args)
        return self

    def first(self):
        return self._result

    def all(self):
        return self._result if isinstance(self._result, list) else []

    def order_by(self, *args, **kw) -> "_FakeQuery":
        return self


class _FakeCompany:
    def __init__(self, orgnr: str, navn: str) -> None:
        self.orgnr = orgnr
        self.navn = navn


class _FakeDB:
    """Minimal SQLAlchemy Session stand-in. `query(X)` dispatches on the
    model class so Company / CompanyNews use separate result sets."""

    def __init__(
        self,
        company: Any = None,
        existing_urls: List[tuple] | None = None,
    ):
        self._company = company
        self._existing_urls = existing_urls or []
        self.added: List[Any] = []
        self.committed = False

    def query(self, *args):
        # First positional arg is either Company or a Column expression.
        arg = args[0]
        model_name = getattr(
            arg, "__name__", getattr(getattr(arg, "class_", None), "__name__", "")
        )
        if model_name == "Company":
            return _FakeQuery(self._company)
        # CompanyNews.url column query
        return _FakeQuery(self._existing_urls)

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    def commit(self) -> None:
        self.committed = True


def _article(url: str, title: str = "Headline") -> Dict[str, Any]:
    return {
        "link": url,
        "title": title,
        "snippet": "snippet text",
        "source": "DN",
        "date": "2 hours ago",
    }


def test_refresh_raises_notfound_when_company_missing():
    from api.domain.exceptions import NotFoundError

    db = _FakeDB(company=None)
    with pytest.raises(NotFoundError):
        refresh_company_news("999999999", db)  # type: ignore[arg-type]


def test_refresh_skips_articles_already_stored_by_url():
    db = _FakeDB(
        company=_FakeCompany("123456789", "Acme AS"),
        existing_urls=[("https://example.com/old-story",)],
    )
    fresh = [
        _article("https://example.com/old-story"),  # dup — should skip
        _article("https://example.com/new-story"),  # new — should store
    ]
    with (
        patch.object(news_service, "_fetch_serper_news", return_value=fresh),
        patch.object(
            news_service,
            "_classify_materiality",
            return_value={"material": True, "event_type": "other", "summary": "s"},
        ),
    ):
        added = refresh_company_news("123456789", db)  # type: ignore[arg-type]
    assert added == 1
    assert len(db.added) == 1
    assert db.added[0].url == "https://example.com/new-story"
    assert db.committed


def test_refresh_returns_zero_and_does_not_commit_when_no_new_articles():
    db = _FakeDB(
        company=_FakeCompany("123456789", "Acme AS"),
        existing_urls=[("https://example.com/x",), ("https://example.com/y",)],
    )
    with (
        patch.object(
            news_service,
            "_fetch_serper_news",
            return_value=[
                _article("https://example.com/x"),
                _article("https://example.com/y"),
            ],
        ),
        patch.object(news_service, "_classify_materiality") as clf,
    ):
        added = refresh_company_news("123456789", db)  # type: ignore[arg-type]
    assert added == 0
    assert not db.committed
    # Classifier shouldn't even run for dupes — pure waste of LLM budget
    clf.assert_not_called()


def test_refresh_tolerates_empty_serper_response():
    db = _FakeDB(
        company=_FakeCompany("123456789", "Acme AS"),
        existing_urls=[],
    )
    with patch.object(news_service, "_fetch_serper_news", return_value=[]):
        added = refresh_company_news("123456789", db)  # type: ignore[arg-type]
    assert added == 0
    assert not db.added


def test_refresh_stores_article_even_when_classifier_falls_back_to_default():
    """If the LLM is down, we still record the headline with material=False —
    never drop the data, broker can judge manually."""
    db = _FakeDB(
        company=_FakeCompany("123456789", "Acme AS"),
        existing_urls=[],
    )
    with (
        patch.object(
            news_service,
            "_fetch_serper_news",
            return_value=[_article("https://example.com/story")],
        ),
        patch.object(
            news_service,
            "_classify_materiality",
            return_value={"material": False, "event_type": "other", "summary": None},
        ),
    ):
        added = refresh_company_news("123456789", db)  # type: ignore[arg-type]
    assert added == 1
    stored = db.added[0]
    assert stored.material is False
    assert stored.summary is None
