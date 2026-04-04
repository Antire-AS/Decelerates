"""Add consent_records table for GDPR lawful-basis tracking.

Revision ID: q7r8s9t0u1v2
Revises: p6q7r8s9t0u1
Create Date: 2026-04-04
"""
from alembic import op
import sqlalchemy as sa

revision = "q7r8s9t0u1v2"
down_revision = "p6q7r8s9t0u1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE lawful_basis AS ENUM "
        "('consent', 'legitimate_interest', 'contract', 'legal_obligation')"
    )
    op.create_table(
        "consent_records",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("orgnr", sa.String(9), nullable=False, index=True),
        sa.Column(
            "firm_id",
            sa.Integer,
            sa.ForeignKey("broker_firms.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "lawful_basis",
            sa.Enum(
                "consent",
                "legitimate_interest",
                "contract",
                "legal_obligation",
                name="lawful_basis",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("purpose", sa.String, nullable=False),
        sa.Column("captured_by_email", sa.String, nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdrawal_reason", sa.String, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("consent_records")
    op.execute("DROP TYPE IF EXISTS lawful_basis")
