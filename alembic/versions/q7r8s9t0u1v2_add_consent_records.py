"""Add consent_records table for GDPR lawful-basis tracking.

Revision ID: q7r8s9t0u1v2
Revises: p6q7r8s9t0u1
Create Date: 2026-04-04

NOTE 2026-04-07: Rewrote to use `postgresql.ENUM` instead of `sa.Enum`. The
original version used `sa.Enum(..., name="lawful_basis", create_type=False)`
inside an `op.create_table` call, which LOOKS like it tells SQLAlchemy not to
create the enum type — but it doesn't. When op.create_table processes the
column, SQLAlchemy internally emits a CREATE TYPE statement for the enum,
conflicting with the explicit CREATE TYPE we ran above it. On prod (where this
migration actually runs end-to-end), the sequence was:

  1. Explicit op.execute("CREATE TYPE lawful_basis ...") → succeeds
  2. op.create_table(..., sa.Enum(..., create_type=False)) → SQLAlchemy still
     emits CREATE TYPE internally → fails with "type already exists"
  3. Whole migration rolls back → alembic_version stays at p6q7r8s9t0u1
  4. Next deploy attempt → same thing → silent crash loop

CI never caught this because CI runs against a fresh Postgres where the
explicit CREATE TYPE is the *only* creation attempt and the redundant one
SQLAlchemy emits internally collides in the same transaction.

The fix uses `postgresql.ENUM` which respects `create_type=False` correctly
in op.create_table context, and creates the type explicitly up front via
`.create(bind, checkfirst=True)` so re-runs are idempotent.

Verified by running `alembic upgrade q7r8s9t0u1v2` then `downgrade` on the
prod DB directly.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "q7r8s9t0u1v2"
down_revision = "p6q7r8s9t0u1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    lawful_basis = postgresql.ENUM(
        "consent",
        "legitimate_interest",
        "contract",
        "legal_obligation",
        name="lawful_basis",
        create_type=True,
    )
    # checkfirst=True → idempotent: skip CREATE TYPE if it already exists.
    lawful_basis.create(op.get_bind(), checkfirst=True)

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
            postgresql.ENUM(name="lawful_basis", create_type=False),
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
