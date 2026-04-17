"""Canonical name helpers for free-text insurer + product fields.

Background — UI audit F06 (2026-04-09): the broker analytics page showed
the same insurer twice with split totals because Policy.insurer is a
free-text column and brokers had typed "Tryg" in some rows and
"Tryg Forsikring" in others. Same problem for products
("Avbruddsforsikring" vs "Driftsavbruddsforsikring",
"Tingsskadeforsikring" vs "Tingsforsikring").

The fix is two layers:

1. **On write** — `PolicyService.create` / `PolicyService.update` route
   the broker's input through `canonical_insurer_name` /
   `canonical_product_name` so new rows are always normalised. Even if
   a broker types "tryg", the row stores "Tryg Forsikring".

2. **On read (defense in depth)** — `analytics.py::_aggregate` re-runs
   the canonicaliser on every row before bucketing, so old non-canonical
   rows still aggregate correctly without waiting for a backfill.

A separate one-shot Alembic backfill (alembic/versions/<…>_canon_insurer_backfill.py)
rewrites existing rows so the on-write path becomes the only source of
truth in steady state.

The synonym tables are intentionally short — only the cases we've seen
in real data. Adding entries is cheap; missing one means the analytics
page double-counts a single insurer until we notice.
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


# ── Insurer canonicalisation ──────────────────────────────────────────────────

# Maps lowercase synonym → canonical display form. Lookup is case- and
# whitespace-insensitive. Canonical forms match what `_DEMO_INSURERS` in
# demo_seed.py uses, so seed data and broker input converge on the same
# strings.
_INSURER_SYNONYMS: dict[str, str] = {
    "tryg": "Tryg Forsikring",
    "tryg forsikring": "Tryg Forsikring",
    "tryg forsikring as": "Tryg Forsikring",
    "gjensidige": "Gjensidige Forsikring",
    "gjensidige forsikring": "Gjensidige Forsikring",
    "if": "If Skadeforsikring",
    "if skadeforsikring": "If Skadeforsikring",
    "if skade": "If Skadeforsikring",
    "fremtind": "Fremtind Forsikring",
    "fremtind forsikring": "Fremtind Forsikring",
    "storebrand": "Storebrand Forsikring",
    "storebrand forsikring": "Storebrand Forsikring",
    "codan": "Codan Forsikring",
    "codan forsikring": "Codan Forsikring",
}


def canonical_insurer_name(name: str | None) -> str | None:
    """Return the canonical form of an insurer name, or the original if unknown.

    Returns None for None input. Returns "" for "" or whitespace-only input
    so callers can distinguish "broker explicitly cleared the field" from
    "broker never set it".
    """
    if name is None:
        return None
    stripped = name.strip()
    if not stripped:
        return ""
    return _INSURER_SYNONYMS.get(stripped.lower(), stripped)


# ── Product type canonicalisation ─────────────────────────────────────────────

_PRODUCT_SYNONYMS: dict[str, str] = {
    # Avbrudd / driftsavbrudd — both refer to business interruption cover
    "avbruddsforsikring": "Driftsavbruddsforsikring",
    "driftsavbruddsforsikring": "Driftsavbruddsforsikring",
    # Tings / tingsskade — both refer to property damage cover
    "tingsforsikring": "Tingsskadeforsikring",
    "tingsskadeforsikring": "Tingsskadeforsikring",
    # D&O — both Norwegian and abbreviated English forms
    "styreansvar": "Styreansvarsforsikring",
    "styreansvarsforsikring": "Styreansvarsforsikring",
    "styreansvar (d&o)": "Styreansvarsforsikring",
    "d&o": "Styreansvarsforsikring",
}


def canonical_product_name(name: str | None) -> str | None:
    """Return the canonical form of a product type, or the original if unknown."""
    if name is None:
        return None
    stripped = name.strip()
    if not stripped:
        return ""
    return _PRODUCT_SYNONYMS.get(stripped.lower(), stripped)
