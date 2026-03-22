"""add broker_firms and users tables

Revision ID: b1c2d3e4f5g6
Revises: a1b2c3d4e5f6
Create Date: 2026-03-22 09:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b1c2d3e4f5g6"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "broker_firms",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("orgnr", sa.String(9), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_broker_firms_id", "broker_firms", ["id"])

    # Seed the default firm so auto-provisioned users have a firm to join
    op.execute(
        "INSERT INTO broker_firms (id, name, created_at) "
        "VALUES (1, 'Default Firm', NOW()) "
        "ON CONFLICT DO NOTHING"
    )

    user_role = sa.Enum("admin", "broker", "viewer", name="user_role")
    user_role.create(op.get_bind())

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("firm_id", sa.Integer(), nullable=False),
        sa.Column("azure_oid", sa.String(64), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("role", sa.Enum("admin", "broker", "viewer", name="user_role", create_type=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["firm_id"], ["broker_firms.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("azure_oid"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_azure_oid", "users", ["azure_oid"])
    op.create_index("ix_users_firm_id", "users", ["firm_id"])


def downgrade() -> None:
    op.drop_index("ix_users_firm_id", table_name="users")
    op.drop_index("ix_users_azure_oid", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")
    sa.Enum(name="user_role").drop(op.get_bind())
    op.drop_index("ix_broker_firms_id", table_name="broker_firms")
    op.drop_table("broker_firms")
