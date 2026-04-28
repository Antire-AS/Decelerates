"""add insurance_products catalog table

Revision ID: n2o3p4q5r6s7
Revises: m1n2o3p4q5r6
Create Date: 2026-04-25 16:10:00.000000

User asked for a structured product catalog: 15+ products under
personell, more under bygning/ansvar/transport/etc. Today
`Tender.product_types` is `List[str]` with no schema; brokers type
free text. A real catalog lets us:

- Drive the tender-creation form with a tree-picker
- Power IDD/Behovsanalyse against a known product taxonomy
- Filter recommendations by product category

Schema:
- category, sub_category, name uniquely identify a product (composite
  unique). `category` is a string (not enum) so the vocabulary can grow.
- description holds the one-sentence broker pitch
- typical_coverage_limits is JSONB for things like
  `{"min": 1000000, "max": 50000000, "unit": "NOK"}`
- sort_order lets us hand-curate the display order within a category

The startup seed (api/services/insurance_product_seed.py) populates
the canonical Norwegian broker catalog idempotently via INSERT ... ON
CONFLICT DO NOTHING semantics, so re-runs of `init_db()` are safe.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "n2o3p4q5r6s7"
down_revision: str | None = "m1n2o3p4q5r6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "insurance_products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("sub_category", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("typical_coverage_limits", sa.JSON(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("category", "sub_category", "name", name="uq_product_triple"),
    )
    op.create_index(
        "ix_insurance_products_category", "insurance_products", ["category"]
    )


def downgrade() -> None:
    op.drop_index("ix_insurance_products_category", table_name="insurance_products")
    op.drop_table("insurance_products")
