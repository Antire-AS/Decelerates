"""Canonicalise existing Policy.insurer + Policy.product_type free-text rows.

UI audit F06 (2026-04-09): brokers had typed both "Tryg" and "Tryg
Forsikring" into different rows, so /analytics/premiums showed the same
insurer twice with split totals. PolicyService.create / .update now
canonicalise on write, but existing rows still need a one-time backfill.

The on-read canonicaliser in api/routers/analytics.py masks this in the
analytics endpoints, but other call sites (CRM tab, exports, custom
reports) read the raw column. Backfilling once means everywhere agrees.

Revision ID: x4y5z6a7b8c9
Revises: w3x4y5z6a7b8
Create Date: 2026-04-09
"""
from alembic import op

revision = "x4y5z6a7b8c9"
down_revision = "w3x4y5z6a7b8"
branch_labels = None
depends_on = None


# Synonym tables — kept in sync with api/services/canon.py. Duplicated
# here on purpose: migrations should be self-contained and not depend on
# importable application code that may have moved/renamed by the time the
# migration is run on an old DB.
_INSURER_SYNONYMS: dict[str, str] = {
    "tryg":                  "Tryg Forsikring",
    "tryg forsikring as":    "Tryg Forsikring",
    "gjensidige":            "Gjensidige Forsikring",
    "if":                    "If Skadeforsikring",
    "if skade":              "If Skadeforsikring",
    "fremtind":              "Fremtind Forsikring",
    "storebrand":            "Storebrand Forsikring",
    "codan":                 "Codan Forsikring",
}

_PRODUCT_SYNONYMS: dict[str, str] = {
    "avbruddsforsikring":    "Driftsavbruddsforsikring",
    "tingsforsikring":       "Tingsskadeforsikring",
    "styreansvar":           "Styreansvarsforsikring",
    "styreansvar (d&o)":     "Styreansvarsforsikring",
    "d&o":                   "Styreansvarsforsikring",
}


def _backfill(table: str, column: str, mapping: dict[str, str]) -> None:
    """Run one UPDATE per synonym → canonical pair.

    Case-insensitive match on the existing column value. Limited to rows
    that don't already match the canonical form so the migration is
    idempotent (re-running it after a partial backfill is a no-op).
    """
    for synonym, canonical in mapping.items():
        op.execute(
            f"UPDATE {table} SET {column} = '{canonical}' "
            f"WHERE LOWER({column}) = '{synonym}' "
            f"AND {column} != '{canonical}'"
        )


def upgrade() -> None:
    _backfill("policies", "insurer", _INSURER_SYNONYMS)
    _backfill("policies", "product_type", _PRODUCT_SYNONYMS)


def downgrade() -> None:
    # Backfilling free-text fields is one-way. The original variants are
    # not recoverable from the canonical form (no audit trail). The on-read
    # canonicaliser in analytics.py is the only thing that depended on
    # raw values, and it works against canonical input too.
    pass
