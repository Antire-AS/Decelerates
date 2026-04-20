"""In-process TTL cache for frequently re-fetched external data.

Problem: a single company-profile page load fires ~15 parallel requests, five
of which each call BRREG ``fetch_enhet_by_orgnr`` independently (the main
``/org/{orgnr}`` endpoint plus the ``/bankruptcy``, ``/koordinater``,
``/benchmark`` and ``/estimate`` enrichment endpoints). That's 5× the same
2-5 second BRREG round-trip for the same data.

Solution: wrap the fetcher in a thread-safe 5-minute TTL cache. The first
caller pays the BRREG cost; the next four within the window hit memory.
Cache size is bounded so this can't OOM on unbounded orgnr input.

Trade-off: data is stale for up to TTL seconds. BRREG data (company name,
NACE code, bankruptcy flags) changes rarely enough that a 5-minute window
is well within our freshness budget. For bankruptcy specifically the DB
``Company.konkurs`` flag is already eventually consistent anyway — the
page shows whatever /org/{orgnr} fetched on first open.

Per-process (not shared across replicas). With ``min_replicas=1`` in
``deploy.yml`` this is acceptable; a multi-replica deploy would benefit
from Redis, but that's a separate upgrade.
"""

from __future__ import annotations

import time
from threading import Lock
from typing import Any, Dict, Optional, Tuple

from api.services.external_apis import fetch_enhet_by_orgnr

_ENHET_TTL_SECONDS = 300  # 5 minutes
_ENHET_CACHE_MAX = 500  # bounded to prevent unbounded growth

# Maps orgnr -> (timestamp_monotonic, enhet_dict_or_None)
_enhet_cache: Dict[str, Tuple[float, Optional[Dict[str, Any]]]] = {}
_enhet_lock = Lock()


def _evict_oldest_locked() -> None:
    """Remove the oldest entry. Caller must hold the lock."""
    if not _enhet_cache:
        return
    oldest_key = min(_enhet_cache.items(), key=lambda item: item[1][0])[0]
    _enhet_cache.pop(oldest_key, None)


def cached_fetch_enhet(orgnr: str) -> Optional[Dict[str, Any]]:
    """Fetch BRREG enhet data with a 5-minute in-process cache.

    Same return shape as ``fetch_enhet_by_orgnr``. Cache hits never trigger
    network I/O; misses populate the cache with the fresh result (including
    ``None`` — we cache negative results too, so a 404 lookup doesn't keep
    pounding BRREG).
    """
    now = time.monotonic()
    with _enhet_lock:
        entry = _enhet_cache.get(orgnr)
        if entry is not None and now - entry[0] < _ENHET_TTL_SECONDS:
            return entry[1]

    # Miss: fetch outside the lock to avoid serialising all lookups on one mutex.
    result = fetch_enhet_by_orgnr(orgnr)

    with _enhet_lock:
        _enhet_cache[orgnr] = (now, result)
        if len(_enhet_cache) > _ENHET_CACHE_MAX:
            _evict_oldest_locked()
    return result


def clear_enhet_cache() -> None:
    """Drop all cached entries. Used by tests and potentially by an admin endpoint."""
    with _enhet_lock:
        _enhet_cache.clear()


def _cache_stats() -> Dict[str, Any]:
    """Inspection helper — current size. Useful for debugging."""
    with _enhet_lock:
        return {
            "size": len(_enhet_cache),
            "max": _ENHET_CACHE_MAX,
            "ttl_seconds": _ENHET_TTL_SECONDS,
        }


# Re-export for callers that want the direct symbol.
__all__ = ["cached_fetch_enhet", "clear_enhet_cache", "fetch_enhet_by_orgnr"]
