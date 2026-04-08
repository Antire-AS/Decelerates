"""Add deal pipeline (PipelineStage + Deal) — plan §🟢 #9.

Creates the per-firm sales funnel infrastructure: PipelineStage rows hold the
columns of the kanban board, Deal rows hold the cards. Seeds 4 default stages
(Lead / Kvalifisert / Tilbud sendt / Bundet) for every existing BrokerFirm so
the kanban board has columns from day one.

Revision ID: s9t0u1v2w3x4
Revises: r8s9t0u1v2w3
Create Date: 2026-04-07
"""
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "s9t0u1v2w3x4"
down_revision = "r8s9t0u1v2w3"
branch_labels = None
depends_on = None


# Default stages seeded per firm. Order matches the typical sales funnel.
# Names are Norwegian to match the rest of the UI; `kind` is the locked
# semantic role used by analytics and cron jobs.
_DEFAULT_STAGES = [
    ("Lead",         "lead",      0, "#94A3B8"),  # slate
    ("Kvalifisert",  "qualified", 1, "#FCD34D"),  # amber
    ("Tilbud sendt", "quoted",    2, "#60A5FA"),  # blue
    ("Bundet",       "bound",     3, "#34D399"),  # emerald
]


def upgrade() -> None:
    # Postgres enum type — must exist before the column references it.
    pipeline_stage_kind = postgresql.ENUM(
        "lead", "qualified", "quoted", "bound", "won", "lost",
        name="pipeline_stage_kind",
        create_type=True,
    )
    pipeline_stage_kind.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "pipeline_stages",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "firm_id",
            sa.Integer(),
            sa.ForeignKey("broker_firms.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "kind",
            postgresql.ENUM(name="pipeline_stage_kind", create_type=False),
            nullable=False,
        ),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("color", sa.String(length=7), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("firm_id", "name", name="uq_pipeline_stage_firm_name"),
    )

    op.create_table(
        "deals",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "firm_id",
            sa.Integer(),
            sa.ForeignKey("broker_firms.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("orgnr", sa.String(length=9), nullable=False, index=True),
        sa.Column(
            "stage_id",
            sa.Integer(),
            sa.ForeignKey("pipeline_stages.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "owner_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("expected_premium_nok", sa.Float(), nullable=True),
        sa.Column("expected_close_date", sa.Date(), nullable=True, index=True),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("won_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lost_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lost_reason", sa.String(), nullable=True),
    )

    # Seed default stages for every existing broker firm.
    bind = op.get_bind()
    firm_ids = [row[0] for row in bind.execute(sa.text("SELECT id FROM broker_firms")).fetchall()]
    if firm_ids:
        now = datetime.now(timezone.utc)
        rows = [
            {
                "firm_id": firm_id,
                "name": name,
                "kind": kind,
                "order_index": order_index,
                "color": color,
                "created_at": now,
            }
            for firm_id in firm_ids
            for (name, kind, order_index, color) in _DEFAULT_STAGES
        ]
        op.bulk_insert(
            sa.table(
                "pipeline_stages",
                sa.column("firm_id", sa.Integer()),
                sa.column("name", sa.String()),
                sa.column("kind", postgresql.ENUM(name="pipeline_stage_kind", create_type=False)),
                sa.column("order_index", sa.Integer()),
                sa.column("color", sa.String()),
                sa.column("created_at", sa.DateTime(timezone=True)),
            ),
            rows,
        )


def downgrade() -> None:
    op.drop_table("deals")
    op.drop_table("pipeline_stages")
    postgresql.ENUM(name="pipeline_stage_kind").drop(op.get_bind(), checkfirst=True)
