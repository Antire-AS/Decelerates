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
    # ── Enums ────────────────────────────────────────────────────────────────
    policy_status = sa.Enum("active", "expired", "cancelled", "pending", name="policy_status")
    claim_status  = sa.Enum("open", "in_review", "settled", "rejected", name="claim_status")
    activity_type = sa.Enum("call", "email", "meeting", "note", "task", name="activity_type")
    policy_status.create(op.get_bind(), checkfirst=True)
    claim_status.create(op.get_bind(), checkfirst=True)
    activity_type.create(op.get_bind(), checkfirst=True)

    # ── contact_persons ──────────────────────────────────────────────────────
    op.create_table(
        "contact_persons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("orgnr", sa.String(9), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contact_persons_id", "contact_persons", ["id"])
    op.create_index("ix_contact_persons_orgnr", "contact_persons", ["orgnr"])

    # ── policies ─────────────────────────────────────────────────────────────
    op.create_table(
        "policies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("orgnr", sa.String(9), nullable=False),
        sa.Column("firm_id", sa.Integer(), nullable=False),
        sa.Column("contact_person_id", sa.Integer(), nullable=True),
        sa.Column("policy_number", sa.String(100), nullable=True),
        sa.Column("insurer", sa.String(), nullable=False),
        sa.Column("product_type", sa.String(), nullable=False),
        sa.Column("coverage_amount_nok", sa.Float(), nullable=True),
        sa.Column("annual_premium_nok", sa.Float(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("renewal_date", sa.Date(), nullable=True),
        sa.Column("status", sa.Enum("active", "expired", "cancelled", "pending", name="policy_status", create_type=False), nullable=False),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["firm_id"], ["broker_firms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["contact_person_id"], ["contact_persons.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_policies_id", "policies", ["id"])
    op.create_index("ix_policies_orgnr", "policies", ["orgnr"])
    op.create_index("ix_policies_firm_id", "policies", ["firm_id"])
    op.create_index("ix_policies_renewal_date", "policies", ["renewal_date"])

    # ── claims ───────────────────────────────────────────────────────────────
    op.create_table(
        "claims",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("policy_id", sa.Integer(), nullable=False),
        sa.Column("orgnr", sa.String(9), nullable=False),
        sa.Column("firm_id", sa.Integer(), nullable=False),
        sa.Column("claim_number", sa.String(100), nullable=True),
        sa.Column("incident_date", sa.Date(), nullable=True),
        sa.Column("reported_date", sa.Date(), nullable=True),
        sa.Column("status", sa.Enum("open", "in_review", "settled", "rejected", name="claim_status", create_type=False), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("estimated_amount_nok", sa.Float(), nullable=True),
        sa.Column("settled_amount_nok", sa.Float(), nullable=True),
        sa.Column("insurer_contact", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["firm_id"], ["broker_firms.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_claims_id", "claims", ["id"])
    op.create_index("ix_claims_orgnr", "claims", ["orgnr"])
    op.create_index("ix_claims_policy_id", "claims", ["policy_id"])
    op.create_index("ix_claims_firm_id", "claims", ["firm_id"])

    # ── activities ───────────────────────────────────────────────────────────
    op.create_table(
        "activities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("orgnr", sa.String(9), nullable=True),
        sa.Column("policy_id", sa.Integer(), nullable=True),
        sa.Column("claim_id", sa.Integer(), nullable=True),
        sa.Column("firm_id", sa.Integer(), nullable=False),
        sa.Column("created_by_email", sa.String(), nullable=False),
        sa.Column("activity_type", sa.Enum("call", "email", "meeting", "note", "task", name="activity_type", create_type=False), nullable=False),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("body", sa.String(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["firm_id"], ["broker_firms.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_activities_id", "activities", ["id"])
    op.create_index("ix_activities_orgnr", "activities", ["orgnr"])
    op.create_index("ix_activities_firm_id", "activities", ["firm_id"])
    op.create_index("ix_activities_created_at", "activities", ["created_at"])


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
