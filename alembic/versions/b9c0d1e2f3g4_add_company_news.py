"""add company_news table

Revision ID: b9c0d1e2f3g4
Revises: a8b9c0d1e2f3
Create Date: 2026-04-22 22:20:00.000000

Stores news articles fetched from Serper /news, classified for
materiality by Foundry gpt-5.4-mini. Fronts the NewsTab on company
profiles and the material-events chip on the portfolio dashboard.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b9c0d1e2f3g4"
down_revision: str | None = "a8b9c0d1e2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "company_news",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("orgnr", sa.String(length=9), nullable=False),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("material", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("event_type", sa.String(length=32), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("orgnr", "url", name="uq_company_news_orgnr_url"),
    )
    op.create_index(
        "ix_company_news_orgnr_published",
        "company_news",
        ["orgnr", sa.text("published_at DESC")],
    )
    op.create_index(
        "ix_company_news_orgnr_material_published",
        "company_news",
        ["orgnr", "material", sa.text("published_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_company_news_orgnr_material_published", table_name="company_news")
    op.drop_index("ix_company_news_orgnr_published", table_name="company_news")
    op.drop_table("company_news")
