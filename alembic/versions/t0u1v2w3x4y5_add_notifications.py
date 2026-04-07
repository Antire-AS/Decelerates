"""Add in-app notifications table — plan §🟢 #17.

The bell-icon dropdown reads from this table. Cron jobs (portfolio digest,
renewal reminders, etc.) write rows here in addition to sending email so
brokers don't need to live in their inbox.

The composite (user_id, read, created_at desc) index covers the only hot
query: "list this user's most recent unread notifications".

Revision ID: t0u1v2w3x4y5
Revises: s9t0u1v2w3x4
Create Date: 2026-04-07
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "t0u1v2w3x4y5"
down_revision = "s9t0u1v2w3x4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    notification_kind = postgresql.ENUM(
        "renewal",
        "activity_overdue",
        "mention",
        "claim_new",
        "deal_won",
        "coverage_gap",
        "digest",
        name="notification_kind",
        create_type=True,
    )
    notification_kind.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "firm_id",
            sa.Integer(),
            sa.ForeignKey("broker_firms.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("orgnr", sa.String(length=9), nullable=True, index=True),
        sa.Column(
            "kind",
            postgresql.ENUM(name="notification_kind", create_type=False),
            nullable=False,
        ),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=True),
        sa.Column("link", sa.String(), nullable=True),
        sa.Column("read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Hot path: "list this user's recent unread notifications". Composite
    # index covers the WHERE + ORDER BY exactly so we never table-scan.
    op.create_index(
        "idx_notifications_user_read_created",
        "notifications",
        ["user_id", "read", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_notifications_user_read_created", table_name="notifications")
    op.drop_table("notifications")
    postgresql.ENUM(name="notification_kind").drop(op.get_bind(), checkfirst=True)
