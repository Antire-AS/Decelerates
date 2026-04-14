"""Add azure_tenant_id to broker_firms + api_key to insurers.

Revision ID: c9d0e1f2g3h4
Revises: b8c9d0e1f2g3
Create Date: 2026-04-15
"""
import sqlalchemy as sa
from alembic import op

revision = "c9d0e1f2g3h4"
down_revision = "b8c9d0e1f2g3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SSO foundation: map Azure AD tenants to broker firms
    op.execute(
        "ALTER TABLE broker_firms ADD COLUMN IF NOT EXISTS "
        "azure_tenant_id VARCHAR(36) UNIQUE"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_broker_firms_azure_tenant_id "
        "ON broker_firms (azure_tenant_id) WHERE azure_tenant_id IS NOT NULL"
    )

    # Insurer API foundation: API key for external insurer access
    op.execute(
        "ALTER TABLE insurers ADD COLUMN IF NOT EXISTS "
        "api_key VARCHAR(64) UNIQUE"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_insurers_api_key "
        "ON insurers (api_key) WHERE api_key IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_index("ix_insurers_api_key", table_name="insurers")
    op.drop_column("insurers", "api_key")
    op.drop_index("ix_broker_firms_azure_tenant_id", table_name="broker_firms")
    op.drop_column("broker_firms", "azure_tenant_id")
