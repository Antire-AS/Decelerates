"""add contact_persons, policies, claims, activities tables

Revision ID: c2d3e4f5g6h7
Revises: b1c2d3e4f5g6
Create Date: 2026-03-22 09:05:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c2d3e4f5g6h7"
down_revision: str | None = "b1c2d3e4f5g6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '60s'")
    # ── Enums ────────────────────────────────────────────────────────────────
    for typname, values in [
        ("policy_status", "('active', 'expired', 'cancelled', 'pending')"),
        ("claim_status",  "('open', 'in_review', 'settled', 'rejected')"),
        ("activity_type", "('call', 'email', 'meeting', 'note', 'task')"),
    ]:
        op.execute(
            f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{typname}') "
            f"THEN CREATE TYPE {typname} AS ENUM {values}; END IF; END $$"
        )

    # ── contact_persons ──────────────────────────────────────────────────────
    op.execute(
        "CREATE TABLE IF NOT EXISTS contact_persons ("
        "  id SERIAL NOT NULL, orgnr VARCHAR(9) NOT NULL, name VARCHAR NOT NULL,"
        "  title VARCHAR, email VARCHAR, phone VARCHAR,"
        "  is_primary BOOLEAN NOT NULL DEFAULT false, notes VARCHAR,"
        "  created_at TIMESTAMPTZ NOT NULL, PRIMARY KEY (id)"
        ")"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_contact_persons_id ON contact_persons (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contact_persons_orgnr ON contact_persons (orgnr)")

    # ── policies ─────────────────────────────────────────────────────────────
    op.execute(
        "CREATE TABLE IF NOT EXISTS policies ("
        "  id SERIAL NOT NULL, orgnr VARCHAR(9) NOT NULL, firm_id INTEGER NOT NULL,"
        "  contact_person_id INTEGER, policy_number VARCHAR(100), insurer VARCHAR NOT NULL,"
        "  product_type VARCHAR NOT NULL, coverage_amount_nok FLOAT, annual_premium_nok FLOAT,"
        "  start_date DATE, renewal_date DATE, status policy_status NOT NULL,"
        "  notes VARCHAR, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,"
        "  PRIMARY KEY (id),"
        "  FOREIGN KEY (firm_id) REFERENCES broker_firms(id) ON DELETE RESTRICT,"
        "  FOREIGN KEY (contact_person_id) REFERENCES contact_persons(id) ON DELETE SET NULL"
        ")"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_policies_id ON policies (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_policies_orgnr ON policies (orgnr)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_policies_firm_id ON policies (firm_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_policies_renewal_date ON policies (renewal_date)")

    # ── claims ───────────────────────────────────────────────────────────────
    op.execute(
        "CREATE TABLE IF NOT EXISTS claims ("
        "  id SERIAL NOT NULL, policy_id INTEGER NOT NULL, orgnr VARCHAR(9) NOT NULL,"
        "  firm_id INTEGER NOT NULL, claim_number VARCHAR(100), incident_date DATE,"
        "  reported_date DATE, status claim_status NOT NULL, description VARCHAR,"
        "  estimated_amount_nok FLOAT, settled_amount_nok FLOAT, insurer_contact VARCHAR,"
        "  notes VARCHAR, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,"
        "  PRIMARY KEY (id),"
        "  FOREIGN KEY (policy_id) REFERENCES policies(id) ON DELETE CASCADE,"
        "  FOREIGN KEY (firm_id) REFERENCES broker_firms(id) ON DELETE RESTRICT"
        ")"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_claims_id ON claims (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_claims_orgnr ON claims (orgnr)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_claims_policy_id ON claims (policy_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_claims_firm_id ON claims (firm_id)")

    # ── activities ───────────────────────────────────────────────────────────
    op.execute(
        "CREATE TABLE IF NOT EXISTS activities ("
        "  id SERIAL NOT NULL, orgnr VARCHAR(9), policy_id INTEGER, claim_id INTEGER,"
        "  firm_id INTEGER NOT NULL, created_by_email VARCHAR NOT NULL,"
        "  activity_type activity_type NOT NULL, subject VARCHAR NOT NULL, body VARCHAR,"
        "  due_date DATE, completed BOOLEAN NOT NULL DEFAULT false,"
        "  created_at TIMESTAMPTZ NOT NULL,"
        "  PRIMARY KEY (id),"
        "  FOREIGN KEY (policy_id) REFERENCES policies(id) ON DELETE SET NULL,"
        "  FOREIGN KEY (claim_id) REFERENCES claims(id) ON DELETE SET NULL,"
        "  FOREIGN KEY (firm_id) REFERENCES broker_firms(id) ON DELETE RESTRICT"
        ")"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_activities_id ON activities (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_activities_orgnr ON activities (orgnr)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_activities_firm_id ON activities (firm_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_activities_created_at ON activities (created_at)")


def downgrade() -> None:
    op.drop_index("ix_activities_created_at", table_name="activities")
    op.drop_index("ix_activities_firm_id", table_name="activities")
    op.drop_index("ix_activities_orgnr", table_name="activities")
    op.drop_index("ix_activities_id", table_name="activities")
    op.drop_table("activities")

    op.drop_index("ix_claims_firm_id", table_name="claims")
    op.drop_index("ix_claims_policy_id", table_name="claims")
    op.drop_index("ix_claims_orgnr", table_name="claims")
    op.drop_index("ix_claims_id", table_name="claims")
    op.drop_table("claims")

    op.drop_index("ix_policies_renewal_date", table_name="policies")
    op.drop_index("ix_policies_firm_id", table_name="policies")
    op.drop_index("ix_policies_orgnr", table_name="policies")
    op.drop_index("ix_policies_id", table_name="policies")
    op.drop_table("policies")

    op.drop_index("ix_contact_persons_orgnr", table_name="contact_persons")
    op.drop_index("ix_contact_persons_id", table_name="contact_persons")
    op.drop_table("contact_persons")

    sa.Enum(name="activity_type").drop(op.get_bind())
    sa.Enum(name="claim_status").drop(op.get_bind())
    sa.Enum(name="policy_status").drop(op.get_bind())
