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
    op.execute("SET LOCAL lock_timeout = '60s'")
    op.execute(
        "CREATE TABLE IF NOT EXISTS broker_firms ("
        "  id SERIAL NOT NULL,"
        "  name VARCHAR NOT NULL,"
        "  orgnr VARCHAR(9),"
        "  created_at TIMESTAMPTZ NOT NULL,"
        "  PRIMARY KEY (id)"
        ")"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_broker_firms_id ON broker_firms (id)")

    # Seed the default firm so auto-provisioned users have a firm to join
    op.execute(
        "INSERT INTO broker_firms (id, name, created_at) "
        "VALUES (1, 'Default Firm', NOW()) "
        "ON CONFLICT DO NOTHING"
    )

    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN "
        "CREATE TYPE user_role AS ENUM ('admin', 'broker', 'viewer'); "
        "END IF; END $$"
    )

    op.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        "  id SERIAL NOT NULL,"
        "  firm_id INTEGER NOT NULL,"
        "  azure_oid VARCHAR(64) NOT NULL,"
        "  email VARCHAR NOT NULL,"
        "  name VARCHAR NOT NULL,"
        "  role user_role NOT NULL,"
        "  created_at TIMESTAMPTZ NOT NULL,"
        "  PRIMARY KEY (id),"
        "  UNIQUE (azure_oid),"
        "  FOREIGN KEY (firm_id) REFERENCES broker_firms(id) ON DELETE RESTRICT"
        ")"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_id ON users (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_azure_oid ON users (azure_oid)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_firm_id ON users (firm_id)")


def downgrade() -> None:
    op.drop_index("ix_users_firm_id", table_name="users")
    op.drop_index("ix_users_azure_oid", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")
    sa.Enum(name="user_role").drop(op.get_bind())
    op.drop_index("ix_broker_firms_id", table_name="broker_firms")
    op.drop_table("broker_firms")
