"""add property_metadata JSONB to companies

Revision ID: o3p4q5r6s7t8
Revises: n2o3p4q5r6s7
Create Date: 2026-04-28 10:25:00.000000

User asked for property-specific fields: "Byggeår, brannalarm, brennbart
alt om selskaper". Storing a JSONB blob (vs typed columns) because:
- Field set will grow iteratively (broker conventions vary by industry)
- Most companies don't have building data, so per-field NULLs would
  bloat the row width
- Frontend can render whatever keys are present

Loose JSON shape — what the manual-entry UI populates today:
{
  "building_year": 1985,
  "ground_area_m2": 1200,
  "fire_alarm": "tilkoblet 110-sentral",
  "sprinkler": false,
  "flammable_materials": "ammoniakk, lager 800m²",
  "construction": "betong + stål",
  "roof_type": "papp",
  "fire_resistance_rating": "REI 60",
  "primary_use": "kontorbygg / lager / produksjon",
  "address": "Bergmannsveien 42, Oslo",
  "gnr_bnr": "208/4517",
  "notes": "renovert 2019, ny ventilasjon"
}

A future Matrikkel/Eiendomsverdi integration can populate the same
field set without a schema change.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "o3p4q5r6s7t8"
down_revision: str | None = "n2o3p4q5r6s7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column("property_metadata", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("companies", "property_metadata")
