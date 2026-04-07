"""Multi-user collaboration columns — plan §🟢 #14.

Adds:
  - activities.assigned_to_user_id  (FK users.id ON DELETE SET NULL)
  - broker_notes.mentions           (JSON; list of mentioned email strings)

Both nullable so existing rows remain valid without backfill.

Revision ID: u1v2w3x4y5z6
Revises: t0u1v2w3x4y5
Create Date: 2026-04-07
"""
import sqlalchemy as sa
from alembic import op

revision = "u1v2w3x4y5z6"
down_revision = "t0u1v2w3x4y5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "activities",
        sa.Column("assigned_to_user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_activities_assigned_to_user_id",
        "activities",
        "users",
        ["assigned_to_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_activities_assigned_to_user_id",
        "activities",
        ["assigned_to_user_id"],
    )

    op.add_column(
        "broker_notes",
        sa.Column("mentions", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("broker_notes", "mentions")
    op.drop_index("idx_activities_assigned_to_user_id", table_name="activities")
    op.drop_constraint(
        "fk_activities_assigned_to_user_id",
        "activities",
        type_="foreignkey",
    )
    op.drop_column("activities", "assigned_to_user_id")
