"""Unit tests for api/services/caching.py — the 5-minute enhet TTL cache.

The cache is what makes Fix #3 work: /org/{orgnr} populates it, then the
4 parallel utility endpoints (/bankruptcy, /koordinater, /benchmark,
/estimate) hit memory instead of re-calling BRREG.
"""

from unittest.mock import patch

from api.services import caching


def setup_function() -> None:
    caching.clear_enhet_cache()


def test_first_call_hits_brreg_subsequent_calls_hit_cache() -> None:
    """Exactly one BRREG round-trip per orgnr per TTL window."""
    with patch(
        "api.services.caching.fetch_enhet_by_orgnr",
        return_value={"orgnr": "123", "navn": "Test"},
    ) as mock_fetch:
        for _ in range(3):
            result = caching.cached_fetch_enhet("123")
            assert result == {"orgnr": "123", "navn": "Test"}

        assert mock_fetch.call_count == 1


def test_negative_result_is_cached() -> None:
    """404 (None) results are cached too — prevents pounding BRREG on bad orgnr."""
    with patch(
        "api.services.caching.fetch_enhet_by_orgnr", return_value=None
    ) as mock_fetch:
        assert caching.cached_fetch_enhet("000000000") is None
        assert caching.cached_fetch_enhet("000000000") is None
        assert caching.cached_fetch_enhet("000000000") is None
        assert mock_fetch.call_count == 1


def test_different_orgnrs_are_independent() -> None:
    """Cache keys are per-orgnr; lookup for A does not serve B."""
    with patch(
        "api.services.caching.fetch_enhet_by_orgnr",
        side_effect=lambda orgnr: {"orgnr": orgnr, "navn": f"Co-{orgnr}"},
    ) as mock_fetch:
        assert caching.cached_fetch_enhet("111")["navn"] == "Co-111"
        assert caching.cached_fetch_enhet("222")["navn"] == "Co-222"
        assert caching.cached_fetch_enhet("111")["navn"] == "Co-111"
        assert caching.cached_fetch_enhet("222")["navn"] == "Co-222"
        assert mock_fetch.call_count == 2


def test_ttl_expiry_causes_refetch(monkeypatch) -> None:
    """After TTL, the next lookup refetches."""
    clock = [1000.0]
    monkeypatch.setattr(caching.time, "monotonic", lambda: clock[0])

    with patch(
        "api.services.caching.fetch_enhet_by_orgnr",
        return_value={"orgnr": "123", "navn": "Test"},
    ) as mock_fetch:
        caching.cached_fetch_enhet("123")
        caching.cached_fetch_enhet("123")
        assert mock_fetch.call_count == 1

        clock[0] += caching._ENHET_TTL_SECONDS + 1
        caching.cached_fetch_enhet("123")
        assert mock_fetch.call_count == 2


def test_cache_size_bounded(monkeypatch) -> None:
    """Cache evicts oldest when exceeding _ENHET_CACHE_MAX."""
    monkeypatch.setattr(caching, "_ENHET_CACHE_MAX", 3)

    with patch(
        "api.services.caching.fetch_enhet_by_orgnr",
        side_effect=lambda orgnr: {"orgnr": orgnr, "navn": f"Co-{orgnr}"},
    ):
        caching.cached_fetch_enhet("A")
        caching.cached_fetch_enhet("B")
        caching.cached_fetch_enhet("C")
        caching.cached_fetch_enhet("D")

        stats = caching._cache_stats()
        assert stats["size"] == 3


def test_clear_enhet_cache_empties_everything() -> None:
    """Admin helper resets the cache."""
    with patch(
        "api.services.caching.fetch_enhet_by_orgnr",
        return_value={"orgnr": "X", "navn": "X"},
    ):
        caching.cached_fetch_enhet("X")
        assert caching._cache_stats()["size"] == 1
        caching.clear_enhet_cache()
        assert caching._cache_stats()["size"] == 0
